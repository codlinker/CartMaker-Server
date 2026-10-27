import contextvars
import hashlib
import io
import math
import mimetypes
import os
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from django.conf import settings
from django.core.cache import cache
from PIL import Image, ImageFilter, ImageOps


# Archivos guardados durante la petición HTTP actual. Si la petición termina rechazada por moderación
# (ContentModerationError), esos archivos se borran para no dejar huérfanos en S3 / disco.
_REQUEST_SAVED_FILES: contextvars.ContextVar = contextvars.ContextVar('cm_request_saved_files', default=None)


def begin_request_file_tracking():
    """Inicia el rastreo de archivos guardados en la petición actual. Devuelve el token para `end_...`."""
    return _REQUEST_SAVED_FILES.set([])


def end_request_file_tracking(token) -> None:
    try:
        _REQUEST_SAVED_FILES.reset(token)
    except Exception:
        _REQUEST_SAVED_FILES.set(None)


def track_saved_file(full_path: str) -> None:
    tracked = _REQUEST_SAVED_FILES.get()
    if tracked is not None and full_path:
        tracked.append(full_path)

# Límite estricto por defecto (50 KB) para todas las imágenes subidas por usuarios
try:
    DEFAULT_MAX_IMAGE_KB = int(getattr(settings, 'COS_MAX_IMAGE_KB', 50) or 50) if settings.configured else 50
except Exception:
    DEFAULT_MAX_IMAGE_KB = 50
DEFAULT_MAX_IMAGE_BYTES = DEFAULT_MAX_IMAGE_KB * 1024
COMPRESSIBLE_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.heic'}


def _prepare_rgb_image(img: Image.Image) -> Image.Image:
    """Convierte cualquier modo (RGBA, P, CMYK, LA) a RGB limpio sobre fondo blanco."""
    if img.mode == "RGB":
        return img
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.split()[3])
        return background
    return img.convert("RGB")


def _encode_jpeg_bytes(img: Image.Image, quality: int, subsampling: int = 2) -> bytes:
    buf = io.BytesIO()
    img.save(
        buf,
        format="JPEG",
        quality=int(quality),
        optimize=True,
        progressive=True,
        subsampling=subsampling,
    )
    return buf.getvalue()


def _binary_search_jpeg(
    img: Image.Image,
    max_bytes: int,
    min_q: int = 68,
    max_q: int = 95,
):
    lowest_bytes = _encode_jpeg_bytes(img, quality=min_q, subsampling=2)
    if len(lowest_bytes) > max_bytes:
        return None

    best_bytes = lowest_bytes
    best_q = min_q
    best_subsampling = 2

    low, high = min_q, max_q
    while low <= high:
        mid = (low + high) // 2
        candidate = _encode_jpeg_bytes(img, quality=mid, subsampling=2)
        if len(candidate) <= max_bytes:
            best_bytes = candidate
            best_q = mid
            low = mid + 1
        else:
            high = mid - 1

    if best_q >= 82:
        for sub in (0, 1):
            candidate_chroma = _encode_jpeg_bytes(img, quality=best_q, subsampling=sub)
            if len(candidate_chroma) <= max_bytes:
                best_bytes = candidate_chroma
                best_subsampling = sub
                break

    return best_bytes, best_q, best_subsampling


def _resize_perceptual(img: Image.Image, scale: float, sharpen: bool = True) -> Image.Image:
    orig_w, orig_h = img.size
    new_w = max(64, int(round(orig_w * scale)))
    new_h = max(64, int(round(orig_h * scale)))
    if new_w == orig_w and new_h == orig_h:
        return img
    resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    if sharpen and resized.mode in ("RGB", "L"):
        resized = resized.filter(ImageFilter.UnsharpMask(radius=0.75, percent=32, threshold=3))
    return resized


def _compress_jpeg_best_practice(
    img: Image.Image,
    max_bytes: int,
    min_perceptual_quality: int = 68,
) -> bytes:
    """
    Motor idéntico 1:1 a `compress_static_images.py`:
      Fase 1: Mantener 100% de la resolución original y buscar calidad en [min_perceptual_quality, 95]
              con submuestreo 4:4:4 cuando la calidad >= 82.
      Fase 2: Si a 100% resolución requiere bajar de `min_perceptual_quality`, reducir
              gradualmente las dimensiones con LANCZOS + UnsharpMask manteniendo calidad [68, 90]
              y 16.7 millones de colores (24-bit RGB, cero cuantización de paleta).
      Fase 3: Fallback para presupuestos ultra bajos.
    """
    rgb_img = _prepare_rgb_image(img)

    # Fase 1: 100% resolución original
    res_full = _binary_search_jpeg(rgb_img, max_bytes=max_bytes, min_q=min_perceptual_quality, max_q=95)
    if res_full is not None:
        return res_full[0]

    # Fase 2: Escalado perceptual LANCZOS manteniendo calidad alta >= min_perceptual_quality
    probe_bytes = len(_encode_jpeg_bytes(rgb_img, quality=min_perceptual_quality, subsampling=2))
    ratio_estimate = math.sqrt(max_bytes / max(1, probe_bytes))
    start_scale = min(0.92, max(0.35, ratio_estimate * 1.12))

    scale = start_scale
    while scale >= 0.18:
        scaled_img = _resize_perceptual(rgb_img, scale=scale, sharpen=True)
        res_scaled = _binary_search_jpeg(
            scaled_img,
            max_bytes=max_bytes,
            min_q=min_perceptual_quality,
            max_q=90,
        )
        if res_scaled is not None:
            return res_scaled[0]
        scale *= 0.88

    # Fase 3: Fallback extremo
    for fallback_scale in (0.25, 0.20, 0.15, 0.12):
        scaled_img = _resize_perceptual(rgb_img, scale=fallback_scale, sharpen=False)
        res_low = _binary_search_jpeg(scaled_img, max_bytes=max_bytes, min_q=40, max_q=75)
        if res_low is not None:
            return res_low[0]

    tiny_img = _resize_perceptual(rgb_img, scale=0.10, sharpen=False)
    return _encode_jpeg_bytes(tiny_img, quality=40, subsampling=2)


def compress_uploaded_image_stream(
    file_obj,
    file_name: str,
    max_bytes: int = DEFAULT_MAX_IMAGE_BYTES,
) -> tuple[object, str]:
    """
    Intercepta en memoria (`io.BytesIO`) cualquier imagen subida por un usuario
    y la comprime perceptualmente a `<= max_bytes` (50 KB por defecto) usando
    exactamente el motor JPEG 24-bit RGB de `compress_static_images.py`
    (preservando los 16.7 millones de colores sin posterización ni pérdida de gradientes,
    incluso cuando el usuario sube capturas de pantalla en formato `.png`).
    Devuelve `(stream_comprimido, nuevo_file_name)`.
    """
    base_name, ext = os.path.splitext(str(file_name or ""))
    ext_lower = ext.lower()
    if ext_lower not in COMPRESSIBLE_IMAGE_EXTENSIONS:
        return file_obj, file_name

    try:
        if hasattr(file_obj, "seek"):
            file_obj.seek(0)
        raw_bytes = file_obj.read()
        if hasattr(file_obj, "seek"):
            file_obj.seek(0)
    except Exception:
        return file_obj, file_name

    if not raw_bytes or len(raw_bytes) <= max_bytes:
        return (io.BytesIO(raw_bytes) if raw_bytes else file_obj), file_name

    try:
        with Image.open(io.BytesIO(raw_bytes)) as raw_img:
            if getattr(raw_img, "is_animated", False) and getattr(raw_img, "n_frames", 1) > 1:
                return io.BytesIO(raw_bytes), file_name

            img = ImageOps.exif_transpose(raw_img)
            img.load()

            compressed_bytes = _compress_jpeg_best_practice(img, max_bytes=max_bytes)

        if compressed_bytes and len(compressed_bytes) < len(raw_bytes):
            new_file_name = f"{base_name}.jpg" if ext_lower not in (".jpg", ".jpeg") else file_name
            return io.BytesIO(compressed_bytes), new_file_name
    except Exception as exc:
        print(f"⚠️ Compresión perceptual omitida para {file_name}: {exc}")

    return io.BytesIO(raw_bytes), file_name


class COS:
    """
    Administrador de Cloud Object Storage (COS) con soporte híbrido y arquitectura Dual-Bucket:
    - Modo Local (`STORAGE_TYPE='local'`): Carpeta `MEDIA_ROOT`.
    - Modo AWS S3 (`STORAGE_TYPE='aws'`):
        1. Bucket Público (`AWS_PUBLIC_BUCKET_NAME` / `AWS_STORAGE_BUCKET_NAME`):
           Catálogo de productos, historias de video (72h + HLS), logos y fachadas de tiendas,
           videos de presentación y avatares públicos. Se sirven con URLs públicas directas
           para máximo rendimiento de caché en la App y Web.
        2. Bucket Privado (`AWS_PRIVATE_BUCKET_NAME`):
           Documentos sensibles KYC (cédula + selfie biométrica), documentos legales/fiscales KYB
           (RIF SENIAT + Registro Mercantil SAREN), comprobantes bancarios de pago de suscripciones,
           multimedia privada del chat de órdenes y evidencias de tickets de soporte/disputas.
           Se almacenan con cifrado en reposo SSE-S3 (`AES256`), bloqueo total de acceso público
           y se sirven exclusivamente mediante AWS S3 Presigned URLs temporales (firmadas con SigV4).
    """

    EXPLICIT_CONTENT_TYPES = {
        '.m4a': 'audio/mp4',
        '.aac': 'audio/aac',
        '.mp3': 'audio/mpeg',
        '.wav': 'audio/wav',
        '.ogg': 'audio/ogg',
        '.webm': 'audio/webm',
        '.mp4': 'video/mp4',
        '.mov': 'video/quicktime',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.webp': 'image/webp',
        '.gif': 'image/gif',
        '.heic': 'image/heic',
        '.pdf': 'application/pdf',
    }

    # 🔒 Prefijos que SIEMPRE se enrutan al Bucket Privado (AWS_PRIVATE_BUCKET_NAME)
    # y requieren URLs pre-firmadas temporales (Presigned URLs).
    PRIVATE_STORAGE_PREFIXES = (
        'identity_verifications/',  # Cédula de identidad y selfie biométrica KYC (Habeas Data)
        'companies/kyb/',           # RIF fiscal (SENIAT) y Acta/Registro Mercantil (SAREN)
        'subscriptions/',           # Comprobantes de pago de suscripciones (Atlas Plus / Planes)
        'payments/',                # Capturas y recibos de transferencias / Pago Móvil
        'chat_media/',              # Adjuntos privados del chat de una orden (fotos, audios, PDFs, captures)
        'support_media/',           # Evidencias privadas de tickets de soporte y disputas
        'documents/',               # Documentos administrativos o legales privados
    )

    # 🌍 Prefijos que se enrutan al Bucket Público (AWS_PUBLIC_BUCKET_NAME / AWS_STORAGE_BUCKET_NAME)
    # y se sirven mediante URL directa para CDN y caché de catálogo.
    PUBLIC_STORAGE_PREFIXES = (
        'product_pictures/',            # Fotografías de productos del catálogo
        'products/',                    # Alias de fotografías de productos
        'stories/',                     # Video historias promocionales (72h), HLS y miniaturas
        'company_profile_pictures/',    # Logos e imagen de perfil de comercios
        'store_pictures/',              # Fotos de fachada/interior de sucursales
        'company_presentation_videos/', # Videos de presentación comercial de tiendas y miniaturas
        'profile_pictures/',            # Fotos de perfil de usuarios (legacy)
        'profiles/',                    # Avatares públicos de usuarios y agentes (profiles/avatars/)
        'static/',                      # Activos estáticos públicos
    )

    # Unión de todas las carpetas conocidas para normalización y auto-reparación de rutas
    KNOWN_STORAGE_FOLDERS = PRIVATE_STORAGE_PREFIXES + PUBLIC_STORAGE_PREFIXES

    def __init__(self):
        self.storage_type = getattr(settings, 'STORAGE_TYPE', 'local')
        self._verified_local_to_s3 = set()

        self.public_bucket_name = (
            getattr(settings, 'AWS_PUBLIC_BUCKET_NAME', None)
            or getattr(settings, 'AWS_STORAGE_BUCKET_NAME', None)
        )
        self.private_bucket_name = (
            getattr(settings, 'AWS_PRIVATE_BUCKET_NAME', None)
            or self.public_bucket_name
        )
        # Alias por retrocompatibilidad con código que lea storage_manager.bucket_name
        self.bucket_name = self.public_bucket_name
        self.presigned_url_expiration = int(
            getattr(settings, 'AWS_PRIVATE_URL_EXPIRATION', 3600) or 3600
        )

        if self.storage_type == 'aws':
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME,
                config=Config(
                    signature_version='s3v4',
                    s3={'addressing_style': 'virtual'},
                ),
            )

    @classmethod
    def _guess_content_type(cls, file_name: str):
        if not file_name:
            return None
        ext = os.path.splitext(str(file_name))[1].lower()
        if ext in cls.EXPLICIT_CONTENT_TYPES:
            return cls.EXPLICIT_CONTENT_TYPES[ext]
        content_type, _ = mimetypes.guess_type(str(file_name))
        return content_type

    def normalize_path(self, raw_path: str) -> str:
        """
        Normaliza cualquier valor de ruta o URL (sea ruta relativa 'companies/kyb/rif/...'
        o una URL completa heredada como 'https://bucket.s3.amazonaws.com/companies/kyb/rif/...'
        o 'https://.../media/chat_media/...') a la clave relativa limpia en el storage.
        """
        if not raw_path:
            return ""

        clean = str(raw_path).strip().replace("\\", "/")
        if not clean:
            return ""

        # Si contiene una carpeta interna conocida, extraemos desde ese prefijo y descartamos query params
        for folder_prefix in self.KNOWN_STORAGE_FOLDERS:
            idx = clean.find(folder_prefix)
            if idx != -1:
                # Verificamos que sea inicio de ruta o vaya precedido por '/'
                if idx == 0 or clean[idx - 1] == '/':
                    return clean[idx:].split('?', 1)[0].lstrip('/')

        # Si es una URL con /media/, extraemos la ruta relativa posterior a /media/
        media_marker = '/media/'
        media_idx = clean.find(media_marker)
        if media_idx != -1:
            return clean[media_idx + len(media_marker):].split('?', 1)[0].lstrip('/')

        # Si empieza con el dominio propio sin /media/, removemos el dominio
        domain = getattr(settings, 'DOMAIN', '') or ''
        if domain and clean.startswith(domain):
            return clean[len(domain):].split('?', 1)[0].lstrip('/')

        if clean.startswith('http://') or clean.startswith('https://'):
            return clean

        return clean.lstrip('/')

    def is_private_path(self, path: str) -> bool:
        """
        Determina si una ruta pertenece al Bucket Privado según su carpeta prefijo.
        """
        if not path:
            return False
        clean = self.normalize_path(path).lstrip('/')
        if not clean or clean.startswith(('http://', 'https://')):
            return False
        return any(clean.startswith(prefix) for prefix in self.PRIVATE_STORAGE_PREFIXES)

    def _resolve_bucket(self, path: str, is_private: bool | None = None) -> tuple[str, bool]:
        """
        Retorna `(bucket_name, resolved_is_private)` para la ruta dada.
        """
        resolved_private = self.is_private_path(path) if is_private is None else bool(is_private)
        if resolved_private and self.private_bucket_name:
            return self.private_bucket_name, True
        return self.public_bucket_name, False

    @staticmethod
    def _presigned_cache_key(bucket_name: str, clean_path: str, expiration: int) -> str:
        digest = hashlib.sha256(f"{bucket_name}:{clean_path}:{expiration}".encode('utf-8')).hexdigest()[:32]
        return f"cartmaker:cos:presigned:v1:{digest}"

    def save_file(
        self,
        file_obj,
        folder_path,
        file_name,
        is_private: bool | None = None,
        max_image_kb: int | None = None,
    ):
        """
        Almacena un archivo en S3 (enrutando automáticamente entre el bucket público y el privado)
        o en la carpeta local `MEDIA_ROOT`.
        Todas las imágenes (`.jpg`, `.jpeg`, `.png`, `.webp`, `.heic`) se comprimen perceptualmente
        en memoria a `<= 50 KB` (o `max_image_kb` si se indica) antes de guardarse.
        Retorna la ruta relativa limpia (`folder_path/file_name`).
        """
        target_max_bytes = (
            int(max_image_kb) * 1024
            if max_image_kb is not None and int(max_image_kb) > 0
            else DEFAULT_MAX_IMAGE_BYTES
        )
        file_obj, file_name = compress_uploaded_image_stream(
            file_obj,
            file_name=file_name,
            max_bytes=target_max_bytes,
        )

        # 🛡️ Barrera de moderación visual IA antes de guardar en AWS S3 o disco local
        ext_check = os.path.splitext(str(file_name or ""))[1].lower()
        if ext_check in COMPRESSIBLE_IMAGE_EXTENSIONS or ext_check == '.gif':
            from .core.content_moderation import moderate_image_bytes
            if hasattr(file_obj, 'seek'):
                file_obj.seek(0)
            img_bytes_for_mod = file_obj.read()
            if hasattr(file_obj, 'seek'):
                file_obj.seek(0)
            moderate_image_bytes(
                img_bytes_for_mod,
                folder_path=str(folder_path or ""),
                file_name=str(file_name or ""),
            )

        full_path = os.path.join(folder_path, file_name).replace("\\", "/").lstrip("/")

        if self.storage_type == 'aws':
            target_bucket, resolved_private = self._resolve_bucket(full_path, is_private=is_private)
            try:
                content_type = self._guess_content_type(file_name)
                extra_args = {}
                if content_type:
                    extra_args['ContentType'] = content_type

                if resolved_private:
                    # Cifrado en reposo en el servidor (SSE-S3 AES-256) para todos los documentos sensibles
                    extra_args['ServerSideEncryption'] = 'AES256'
                    extra_args['ContentDisposition'] = 'inline'

                if hasattr(file_obj, 'seek'):
                    file_obj.seek(0)

                self.s3_client.upload_fileobj(
                    file_obj,
                    target_bucket,
                    full_path,
                    ExtraArgs=extra_args,
                )
                track_saved_file(full_path)
                return full_path
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', '') if hasattr(e, 'response') else ''
                # Fallback defensivo si el bucket privado aún no ha sido creado en AWS pero ya está en variables.sh
                if (
                    resolved_private
                    and target_bucket != self.public_bucket_name
                    and self.public_bucket_name
                    and error_code == 'NoSuchBucket'
                ):
                    try:
                        print(
                            f"⚠️ Bucket privado '{target_bucket}' no encontrado en AWS; "
                            f"usando '{self.public_bucket_name}' temporalmente para {full_path}."
                        )
                        if hasattr(file_obj, 'seek'):
                            file_obj.seek(0)
                        self.s3_client.upload_fileobj(
                            file_obj,
                            self.public_bucket_name,
                            full_path,
                            ExtraArgs=extra_args,
                        )
                        track_saved_file(full_path)
                        return full_path
                    except ClientError as inner_e:
                        print(f"❌ Error subiendo a AWS S3 (fallback): {inner_e}")
                        return None
                print(f"❌ Error subiendo a AWS S3 ({target_bucket}): {e}")
                return None
        else:
            # Lógica Local
            media_path = os.path.join(settings.MEDIA_ROOT, folder_path)
            if not os.path.exists(media_path):
                os.makedirs(media_path, exist_ok=True)

            save_path = os.path.join(media_path, file_name)

            if hasattr(file_obj, 'seek'):
                file_obj.seek(0)

            with open(save_path, 'wb+') as destination:
                if hasattr(file_obj, 'chunks'):
                    for chunk in file_obj.chunks():
                        destination.write(chunk)
                else:
                    destination.write(file_obj.read())

            track_saved_file(full_path)
            return full_path

    def cleanup_request_saved_files(self) -> int:
        """
        Borra los archivos guardados durante la petición actual (si hay rastreo activo).
        Se invoca cuando la petición es rechazada por moderación para no dejar huérfanos.
        """
        tracked = _REQUEST_SAVED_FILES.get()
        if not tracked:
            return 0
        paths = list(dict.fromkeys(tracked))
        tracked.clear()
        deleted = 0
        for path in paths:
            try:
                if self.delete_file(path):
                    deleted += 1
            except Exception as exc:
                print(f"⚠️ No se pudo limpiar archivo huérfano {path}: {exc}")
        return deleted

    def read_file_bytes(self, relative_path: str, max_bytes: int = 15 * 1024 * 1024):
        """
        Lee (hasta `max_bytes`) los bytes de un archivo almacenado. Retorna `None` si no existe o falla.
        """
        if not relative_path:
            return None
        clean_path = self.normalize_path(relative_path).lstrip('/')
        if not clean_path or clean_path.startswith(('http://', 'https://')):
            return None
        try:
            if self.storage_type == 'aws':
                target_bucket, _ = self._resolve_bucket(clean_path)
                obj = self.s3_client.get_object(Bucket=target_bucket, Key=clean_path)
                return obj['Body'].read(max_bytes)
            full_path = os.path.join(settings.MEDIA_ROOT, clean_path)
            if not os.path.isfile(full_path):
                return None
            with open(full_path, 'rb') as fh:
                return fh.read(max_bytes)
        except Exception as exc:
            print(f"⚠️ No se pudo leer {clean_path}: {exc}")
            return None

    def download_to_path(self, relative_path: str, dest_path: str) -> bool:
        """Descarga un archivo almacenado a una ruta local (para procesarlo con ffmpeg)."""
        if not relative_path:
            return False
        clean_path = self.normalize_path(relative_path).lstrip('/')
        if not clean_path or clean_path.startswith(('http://', 'https://')):
            return False
        try:
            if self.storage_type == 'aws':
                target_bucket, _ = self._resolve_bucket(clean_path)
                self.s3_client.download_file(target_bucket, clean_path, dest_path)
                return True
            full_path = os.path.join(settings.MEDIA_ROOT, clean_path)
            if not os.path.isfile(full_path):
                return False
            import shutil
            shutil.copyfile(full_path, dest_path)
            return True
        except Exception as exc:
            print(f"⚠️ No se pudo descargar {clean_path}: {exc}")
            return False

    def get_url(
        self,
        relative_path: str,
        skip_media: bool = False,
        is_private: bool | None = None,
        expires_in: int | None = None,
    ):
        """
        Retorna la URL accesible para un archivo almacenado:
        - Si el archivo pertenece al Bucket Público: devuelve la URL pública directa de S3.
        - Si el archivo pertenece al Bucket Privado: genera una Presigned URL temporal (SigV4)
          cacheada en Redis durante el 75% de su vida útil para que la App y el navegador
          no re-descarguen la imagen en cada refresco de pantalla.
        """
        if not relative_path:
            return None

        normalized = self.normalize_path(relative_path)
        if not normalized:
            return None

        # Si tras normalizar sigue siendo una URL externa genuina (ej. avatar de Google OAuth), se devuelve tal cual
        if normalized.startswith('http://') or normalized.startswith('https://'):
            return normalized

        clean_path = normalized.lstrip('/')

        if self.storage_type == 'aws':
            target_bucket, resolved_private = self._resolve_bucket(clean_path, is_private=is_private)

            # Auto-curación (Self-Healing): si el archivo fue guardado en MEDIA_ROOT cuando
            # STORAGE_TYPE estaba en 'local', lo sincronizamos hacia el bucket correspondiente.
            verified_key = f"{target_bucket}:{clean_path}"
            if verified_key not in self._verified_local_to_s3:
                local_full_path = os.path.join(settings.MEDIA_ROOT, clean_path)
                if os.path.isfile(local_full_path):
                    try:
                        content_type = self._guess_content_type(local_full_path)
                        extra_args = {'ContentType': content_type} if content_type else {}
                        if resolved_private:
                            extra_args['ServerSideEncryption'] = 'AES256'
                            extra_args['ContentDisposition'] = 'inline'
                        with open(local_full_path, 'rb') as local_f:
                            self.s3_client.upload_fileobj(
                                local_f,
                                target_bucket,
                                clean_path,
                                ExtraArgs=extra_args,
                            )
                        self._verified_local_to_s3.add(verified_key)
                    except Exception as e:
                        print(f"⚠️ Fallback a media local para {clean_path}: {e}")
                        base_url = f"{settings.DOMAIN}{settings.MEDIA_URL}" if not skip_media else settings.DOMAIN
                        if not base_url.endswith('/'):
                            base_url += "/"
                        return f"{base_url}{clean_path}"
                else:
                    self._verified_local_to_s3.add(verified_key)

            # 🔒 Archivos Privados -> Presigned URL temporal firmada con SigV4
            if resolved_private and target_bucket:
                ttl = int(expires_in or self.presigned_url_expiration or 3600)
                ttl = max(60, min(ttl, 604800))  # Entre 1 min y 7 días
                cache_key = self._presigned_cache_key(target_bucket, clean_path, ttl)
                try:
                    cached_signed_url = cache.get(cache_key)
                    if cached_signed_url:
                        return cached_signed_url
                except Exception:
                    pass

                try:
                    presigned_url = self.s3_client.generate_presigned_url(
                        ClientMethod='get_object',
                        Params={
                            'Bucket': target_bucket,
                            'Key': clean_path,
                        },
                        ExpiresIn=ttl,
                    )
                    # Guardamos en Redis por el 75% del TTL (ej. 45 min para enlaces de 60 min)
                    # para mantener la misma URL en caché de imágenes de Flutter/Web sin riesgo de expirar.
                    cache_ttl = max(30, min(ttl - 60, int(ttl * 0.75)))
                    try:
                        cache.set(cache_key, presigned_url, timeout=cache_ttl)
                    except Exception:
                        pass
                    return presigned_url
                except Exception as e:
                    print(f"❌ Error generando Presigned URL para {clean_path} en {target_bucket}: {e}")
                    return f"https://{target_bucket}.s3.{settings.AWS_S3_REGION_NAME}.amazonaws.com/{clean_path}"

            # 🌍 Archivos Públicos -> URL pública directa de S3
            return f"https://{self.public_bucket_name}.s3.{settings.AWS_S3_REGION_NAME}.amazonaws.com/{clean_path}"
        else:
            base_url = f"{settings.DOMAIN}{settings.MEDIA_URL}" if not skip_media else settings.DOMAIN
            if not base_url.endswith('/'):
                base_url += "/"
            return f"{base_url}{clean_path}"

    def delete_file(self, relative_path: str, is_private: bool | None = None):
        """
        Elimina físicamente el objeto del bucket correspondiente (y limpia copias heredadas
        en el bucket público si el archivo es privado) además de invalidar su Presigned URL en caché.
        """
        if not relative_path:
            return False

        clean_path = self.normalize_path(relative_path).lstrip('/')
        if not clean_path or clean_path.startswith(('http://', 'https://')):
            return False

        if self.storage_type == 'aws':
            target_bucket, resolved_private = self._resolve_bucket(clean_path, is_private=is_private)
            try:
                self.s3_client.delete_object(Bucket=target_bucket, Key=clean_path)
                # Si es privado y existen dos buckets distintos, eliminamos también cualquier copia
                # previa en el bucket público (ej. Habeas Data / supresión biométrica de cuentas antiguas).
                if (
                    resolved_private
                    and self.public_bucket_name
                    and self.public_bucket_name != target_bucket
                ):
                    try:
                        self.s3_client.delete_object(Bucket=self.public_bucket_name, Key=clean_path)
                    except Exception:
                        pass
                # Invalidamos la caché de Presigned URL
                if resolved_private:
                    try:
                        cache.delete(
                            self._presigned_cache_key(
                                target_bucket, clean_path, self.presigned_url_expiration
                            )
                        )
                    except Exception:
                        pass
                return True
            except ClientError as e:
                print(f"❌ Error borrando archivo de S3 ({target_bucket}): {e}")
                return False
        else:
            full_path = os.path.join(settings.MEDIA_ROOT, clean_path)
            if os.path.exists(full_path):
                os.remove(full_path)
                return True
            return False


storage_manager = COS()
