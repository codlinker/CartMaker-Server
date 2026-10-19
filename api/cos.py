import os
import mimetypes
import boto3
from django.conf import settings
from botocore.exceptions import ClientError

class COS:
    """
    Administrador de Cloud Object Storage (COS) con soporte híbrido:
    Local (Carpeta Media) o AWS S3.
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
        '.pdf': 'application/pdf',
    }

    KNOWN_STORAGE_FOLDERS = (
        'chat_media/',
        'support_media/',
        'profiles/',
        'stories/',
        'products/',
        'payments/',
        'documents/',
    )

    def __init__(self):
        self.storage_type = getattr(settings, 'STORAGE_TYPE', 'local')
        self._verified_local_to_s3 = set()
        
        if self.storage_type == 'aws':
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME
            )
            self.bucket_name = settings.AWS_STORAGE_BUCKET_NAME

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
        Normaliza cualquier valor de media_url (sea ruta relativa 'chat_media/...'
        o una URL completa corrupta/absoluta como 'https://www.cartmaker.app/chat_media/...'
        o 'https://.../media/chat_media/...') a la clave relativa limpia en el storage.
        """
        if not raw_path:
            return ""

        clean = str(raw_path).strip().replace("\\", "/")
        if not clean:
            return ""

        # Si contiene una carpeta conocida (ej. chat_media/ o support_media/), extraemos desde ahí
        for folder_prefix in self.KNOWN_STORAGE_FOLDERS:
            idx = clean.find(folder_prefix)
            if idx != -1:
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

    def save_file(self, file_obj, folder_path, file_name):
        full_path = os.path.join(folder_path, file_name).replace("\\", "/")

        if self.storage_type == 'aws':
            try:
                # Detectamos el MIME type dinámicamente con mapa explícito para notas de voz (.m4a, .aac, etc.)
                content_type = self._guess_content_type(file_name)
                extra_args = {}
                if content_type:
                    extra_args['ContentType'] = content_type

                # Reseteamos el puntero del archivo por seguridad
                if hasattr(file_obj, 'seek'):
                    file_obj.seek(0)

                self.s3_client.upload_fileobj(
                    file_obj,
                    self.bucket_name,
                    full_path,
                    ExtraArgs=extra_args
                )
                return full_path
            except ClientError as e:
                print(f"❌ Error subiendo a AWS S3: {e}")
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
            
            return full_path

    def get_url(self, relative_path: str, skip_media=False):
        if not relative_path:
            return None

        # Auto-reparación de rutas que fueron guardadas como URL completa (ej. https://www.cartmaker.app/chat_media/...)
        normalized = self.normalize_path(relative_path)
        if not normalized:
            return None

        # Si tras normalizar sigue siendo una URL externa genuina (no perteneciente a carpetas internas), la devolvemos tal cual
        if normalized.startswith('http://') or normalized.startswith('https://'):
            return normalized

        clean_path = normalized.lstrip('/')

        if self.storage_type == 'aws':
            # Auto-curación (Self-Healing): si el archivo fue guardado en MEDIA_ROOT cuando
            # STORAGE_TYPE estaba en 'local', lo sincronizamos automáticamente hacia S3
            # para que tanto la App Móvil como la Web lo carguen desde S3 sin error 403.
            if clean_path not in self._verified_local_to_s3:
                local_full_path = os.path.join(settings.MEDIA_ROOT, clean_path)
                if os.path.isfile(local_full_path):
                    try:
                        content_type = self._guess_content_type(local_full_path)
                        extra_args = {'ContentType': content_type} if content_type else {}
                        with open(local_full_path, 'rb') as local_f:
                            self.s3_client.upload_fileobj(
                                local_f,
                                self.bucket_name,
                                clean_path,
                                ExtraArgs=extra_args,
                            )
                        self._verified_local_to_s3.add(clean_path)
                    except Exception as e:
                        print(f"⚠️ Fallback a media local para {clean_path}: {e}")
                        base_url = f"{settings.DOMAIN}{settings.MEDIA_URL}" if not skip_media else settings.DOMAIN
                        if not base_url.endswith('/'):
                            base_url += "/"
                        return f"{base_url}{clean_path}"
                else:
                    self._verified_local_to_s3.add(clean_path)

            return f"https://{self.bucket_name}.s3.{settings.AWS_S3_REGION_NAME}.amazonaws.com/{clean_path}"
        else:
            base_url = f"{settings.DOMAIN}{settings.MEDIA_URL}" if not skip_media else settings.DOMAIN
            if not base_url.endswith('/'):
                base_url += "/"
            return f"{base_url}{clean_path}"

    def delete_file(self, relative_path):
        if not relative_path:
            return False

        clean_path = self.normalize_path(relative_path).lstrip('/')

        if self.storage_type == 'aws':
            try:
                self.s3_client.delete_object(Bucket=self.bucket_name, Key=clean_path)
                return True
            except ClientError as e:
                print(f"❌ Error borrando archivo de S3: {e}")
                return False
        else:
            full_path = os.path.join(settings.MEDIA_ROOT, clean_path)
            if os.path.exists(full_path):
                os.remove(full_path)
                return True
            return False

storage_manager = COS()