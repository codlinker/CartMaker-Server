"""
Sistema Multicapa de Moderación de Contenido y Seguridad UGC (Google Play & App Store Compliance).

Barreras activas:
1. Moderación instantánea de texto (Léxico + Expresiones Regulares normalizadas sin acentos/leetspeak)
   para bloquear:
   - Desnudez explícita, genitales, pornografía y servicios sexuales (`NUDITY_OR_SEXUAL`).
   - Juguetes sexuales, consoladores, vibradores y artículos de sex-shop (`ADULT_TOYS`).
   - Cigarrillos, tabaco, vapers, cigarrillos electrónicos y nicotina (`TOBACCO_OR_VAPE`).
   - Drogas ilícitas, estupefacientes y parafernalia (`DRUGS_OR_NARCOTICS`).
   - Armas de fuego, municiones, explosivos y violencia gráfica (`WEAPONS_OR_VIOLENCE`).
2. Moderación automática de imágenes con IA de Visión ANTES de subir a AWS S3 (`COS.save_file`):
   - Soporta en cascada:
     a) OpenAI Moderation API (`omni-moderation-latest`, 100% gratuita) si `OPENAI_API_KEY` está definida.
     b) AWS Rekognition (`DetectModerationLabels`) si `USE_AWS_REKOGNITION_MODERATION=true`.
     c) OpenRouter / Google Gemini 2.5 Flash Vision (`OPENROUTER_API_KEY` / `GEMINI_API_KEY`) sobre el
        stream ya comprimido a <= 50 KB, con caché en Redis por hash SHA-256 (`cm:mod:img:v1:<sha256>`).
"""
import base64
import hashlib
import json
import logging
import os
import re
import unicodedata
from typing import Any, Dict, Iterable, Optional, Tuple

import requests
from django.conf import settings
from django.core.cache import cache
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_default_exception_handler

logger = logging.getLogger(__name__)


class ModerationCategory:
    SAFE = "SAFE"
    NUDITY_OR_SEXUAL = "NUDITY_OR_SEXUAL"
    ADULT_TOYS = "ADULT_TOYS"
    TOBACCO_OR_VAPE = "TOBACCO_OR_VAPE"
    DRUGS_OR_NARCOTICS = "DRUGS_OR_NARCOTICS"
    WEAPONS_OR_VIOLENCE = "WEAPONS_OR_VIOLENCE"


CATEGORY_MESSAGES_ES = {
    ModerationCategory.NUDITY_OR_SEXUAL: (
        "Contenido no permitido: Las políticas de CartMaker prohíben estrictamente imágenes o textos "
        "con desnudos, contenido sexual explícito o genitales."
    ),
    ModerationCategory.ADULT_TOYS: (
        "Contenido no permitido: Las políticas de CartMaker prohíben la publicación o venta de "
        "juguetes sexuales, consoladores o artículos para adultos (+18)."
    ),
    ModerationCategory.TOBACCO_OR_VAPE: (
        "Contenido no permitido: Las políticas de CartMaker y Google Play prohíben la publicación "
        "o comercialización de cigarrillos, tabaco, vapers y productos con nicotina."
    ),
    ModerationCategory.DRUGS_OR_NARCOTICS: (
        "Contenido no permitido: Las políticas de CartMaker prohíben estrictamente la publicación "
        "de drogas ilícitas, estupefacientes o sustancias controladas."
    ),
    ModerationCategory.WEAPONS_OR_VIOLENCE: (
        "Contenido no permitido: Las políticas de CartMaker prohíben la publicación de armas de fuego, "
        "municiones, explosivos o violencia gráfica."
    ),
}

DEFAULT_MODERATION_MESSAGE = (
    "Contenido no permitido: La imagen o el texto infringe las Políticas de Contenido Seguro de CartMaker "
    "(no se permiten desnudos, juguetes sexuales, tabaco/vapers, drogas ni armas)."
)


class ContentModerationError(Exception):
    """Excepción lanzada cuando una imagen o texto infringe las políticas de contenido UGC de CartMaker."""

    def __init__(
        self,
        message: Optional[str] = None,
        category: str = ModerationCategory.NUDITY_OR_SEXUAL,
        code: str = "PROHIBITED_CONTENT",
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ):
        self.category = category or ModerationCategory.NUDITY_OR_SEXUAL
        self.message = message or CATEGORY_MESSAGES_ES.get(self.category, DEFAULT_MODERATION_MESSAGE)
        self.code = code
        self.status_code = status_code
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": False,
            "code": self.code,
            "category": self.category,
            "error": self.message,
            "detail": self.message,
        }

    def to_response(self) -> Response:
        # Rechazo por moderación: eliminamos los archivos ya subidos en esta misma petición (sin huérfanos)
        try:
            from api.cos import storage_manager
            storage_manager.cleanup_request_saved_files()
        except Exception as exc:
            logger.warning(f"[ContentModeration] No se pudo limpiar archivos huérfanos: {exc}")
        return Response(self.to_dict(), status=self.status_code)


def cartmaker_exception_handler(exc, context):
    """
    Manejador global de excepciones de DRF que convierte cualquier `ContentModerationError`
    en una respuesta HTTP 400 limpia y estructurada para la app móvil.
    """
    if isinstance(exc, ContentModerationError):
        return exc.to_response()
    return drf_default_exception_handler(exc, context)


# =========================================================================
# 1. CAPA DE TEXTO: LÉXICO Y REGEX DE CONTENIDO PROHIBIDO (< 0.5 ms)
# =========================================================================

_LEET_MAP = str.maketrans({
    "0": "o",
    "1": "i",
    "3": "e",
    "4": "a",
    "5": "s",
    "@": "a",
    "$": "s",
})


def _normalize_text_for_moderation(raw_text: str) -> str:
    if not raw_text:
        return ""
    txt = str(raw_text).lower().strip()
    nfkd = unicodedata.normalize("NFKD", txt)
    no_accents = "".join(ch for ch in nfkd if not unicodedata.combining(ch))
    cleaned = re.sub(r"[^a-z0-9\s]", " ", no_accents)
    return re.sub(r"\s+", " ", cleaned).strip()


_TEXT_RULES: Tuple[Tuple[str, re.Pattern], ...] = (
    (
        ModerationCategory.ADULT_TOYS,
        re.compile(
            r"\b("
            r"consolador|consoladores|dildo|dildos|vibrador\s+sexual|vibradores\s+sexuales|"
            r"juguete\s+sexual|juguetes\s+sexuales|sex\s*shop|masturbador|masturbadores|"
            r"fleshlight|plug\s+anal|bolas\s+chinas|muneca\s+inflable|muneca\s+sexual|"
            r"arnes\s+sexual|anillo\s+vibrador|estimulador\s+clitorial|estimulador\s+prostatico|"
            r"lubricante\s+anal|lenceria\s+erotica\s+explicita|articulos\s+eroticos"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        ModerationCategory.NUDITY_OR_SEXUAL,
        re.compile(
            r"\b("
            r"pornografia|porno|xxx|videos\s+xxx|contenido\s+xxx|desnudo\s+explicito|desnudos\s+explicitos|"
            r"pene|vagina|pene\s+real|vagina\s+real|sexo\s+explicito|servicio\s+sexual|servicios\s+sexuales|"
            r"escort\s+sexual|prostitucion|pack\s+xxx|onlyfans\s+xxx"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        ModerationCategory.TOBACCO_OR_VAPE,
        re.compile(
            r"\b("
            r"cigarrillo|cigarrillos|cajetilla\s+de\s+cigarros|cajetilla\s+de\s+cigarrillos|"
            r"tabaco|tabaco\s+de\s+fumar|vaper|vapers|vapeador|vapeadores|vape\s+desechable|vapes\s+desechables|"
            r"cigarrillo\s+electronico|cigarrillos\s+electronicos|nicotina|pod\s+de\s+nicotina|sales\s+de\s+nicotina|"
            r"liquido\s+de\s+vapeo|e\s*liquid\s+nicotina|narguile|hookah|hookah\s+tabaco|marlboro|lucky\s+strike"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        ModerationCategory.DRUGS_OR_NARCOTICS,
        re.compile(
            r"\b("
            r"marihuana|cannabis\s+thc|weed\s+thc|cocaina|heroina|fentanilo|metanfetamina|cristal\s+meth|"
            r"extasis\s+mdma|pastillas\s+mdma|lsd\s+acido|tusi\s+droga|2cb\s+droga|cripy|"
            r"bong\s+para\s+fumar|pipa\s+de\s+crack|estupefacientes|drogas\s+ilicitas"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        ModerationCategory.WEAPONS_OR_VIOLENCE,
        re.compile(
            r"\b("
            r"arma\s+de\s+fuego|armas\s+de\s+fuego|pistola\s+9mm|pistola\s+calibre|revolver\s+calibre|"
            r"fusil\s+de\s+asalto|rifle\s+de\s+asalto|escopeta\s+calibre|municiones|municiones\s+9mm|"
            r"balas\s+calibre|granada\s+explosiva|silenciador\s+de\s+arma|explosivo\s+c4"
            r")\b",
            re.IGNORECASE,
        ),
    ),
)


# Frases legítimas que contienen términos sensibles y NO deben bloquearse (se eliminan antes de evaluar):
#  - Salud sexual y ginecología de farmacia (preservativos, lubricantes íntimos, óvulos, cremas o higiene íntima).
#  - Terapia de reemplazo de nicotina (farmacia): parches, chicles, gomas, pastillas, spray.
#  - Perfumería / velas / café / cosmética con "notas", "aroma" o "sabor" a tabaco.
#  - Artículos de juguete o decoración: "pistola de juguete/agua/silicon/pintura/clavos/grapas".
_SAFE_CONTEXT_PATTERN = re.compile(
    r"\b("
    r"(?:parche|parches|chicle|chicles|goma|gomas|pastilla|pastillas|spray|inhalador|terapia)\s+"
    r"(?:de\s+|para\s+)?(?:reemplazo\s+de\s+)?nicotina|"
    r"(?:nota|notas|aroma|aromas|sabor|sabores|esencia|fragancia)\s+(?:a\s+|de\s+)tabaco|"
    r"pistola\s+de\s+(?:juguete|agua|silicon|silicona|pintura|clavos|grapas)|"
    r"municion\s+de\s+(?:airsoft|paintball)|"
    r"(?:infeccion|infecciones|flora|hidratante|crema|gel|ovulo|ovulos|ducha|jabon|higiene|salud|cuidado)\s+"
    r"(?:de\s+|en\s+)?(?:la\s+)?vagina|"
    r"(?:preservativo|preservativos|condon|condones)\s+(?:para\s+|de\s+)?(?:el\s+)?pene"
    r")\b",
    re.IGNORECASE,
)


def moderate_text(text: Any, field_label: str = "") -> None:
    """
    Evalúa en < 0.5 ms si un texto contiene términos prohibidos por las políticas de CartMaker y Google Play.
    Lanza `ContentModerationError` si detecta una infracción.
    """
    if not text or not isinstance(text, str):
        return

    norm = _normalize_text_for_moderation(text)
    if not norm:
        return

    # Frases legítimas (farmacia, perfumería, cafetería) que contienen términos sensibles
    norm = _SAFE_CONTEXT_PATTERN.sub(" ", norm)

    # Evaluamos tanto el texto normalizado como su variante des-leetspeakeada
    candidates = (norm, norm.translate(_LEET_MAP))
    for candidate in candidates:
        for category, pattern in _TEXT_RULES:
            if pattern.search(candidate):
                msg = CATEGORY_MESSAGES_ES.get(category, DEFAULT_MODERATION_MESSAGE)
                if field_label:
                    msg = f"{msg} (Detectado en: {field_label})."
                raise ContentModerationError(message=msg, category=category)


def moderate_text_fields(fields_dict: Dict[str, Any]) -> None:
    """
    Valida múltiples campos de texto o estructuras JSON (ej. nombre, descripción, especificaciones).
    """
    if not fields_dict:
        return
    for label, val in fields_dict.items():
        if val is None:
            continue
        if isinstance(val, str):
            moderate_text(val, field_label=label)
        elif isinstance(val, (dict, list)):
            try:
                serialized = json.dumps(val, ensure_ascii=False)
                moderate_text(serialized, field_label=label)
            except ContentModerationError:
                raise
            except Exception:
                pass


# =========================================================================
# 2. CAPA DE VISIÓN IA: MODERACIÓN AUTOMÁTICA DE IMÁGENES ANTES DE S3
# =========================================================================

# Carpetas internas/administrativas donde se suben documentos legales o bancarios
# que no deben evaluarse como productos de catálogo (ej. cédula KYC, RIF SENIAT, recibos Pago Móvil).
EXEMPT_DOCUMENT_PREFIXES = (
    "identity_verifications/",
    "companies/kyb/",
    "subscriptions/",
    "payments/",
    "documents/",
)

# Carpetas de contenido generado por usuarios (UGC) que SIEMPRE pasan por el filtro de moderación visual
MODERATED_UGC_PREFIXES = (
    "product_pictures/",
    "products/",
    "combo_pictures/",
    "stories/",
    "company_profile_pictures/",
    "store_pictures/",
    "company_presentation_videos/",
    "profile_pictures/",
    "profiles/",
    "chat_media/",
    "support_media/",
)


def _should_moderate_folder(folder_path: str) -> bool:
    clean = str(folder_path or "").strip().replace("\\", "/").lstrip("/")
    if not clean:
        return True
    # Normalizamos con "/" final para que "identity_verifications" (sin slash) también quede exenta
    clean_slash = clean if clean.endswith("/") else clean + "/"
    for exempt in EXEMPT_DOCUMENT_PREFIXES:
        if clean_slash.startswith(exempt):
            return False
    return True


def _check_with_aws_rekognition(image_bytes: bytes) -> Optional[Tuple[bool, str, str]]:
    """
    Opción B: AWS Rekognition `DetectModerationLabels` (cuando `USE_AWS_REKOGNITION_MODERATION=true`).
    """
    use_rekognition = str(
        getattr(settings, "USE_AWS_REKOGNITION_MODERATION", None)
        or os.environ.get("USE_AWS_REKOGNITION_MODERATION", "false")
    ).strip().lower() in ("true", "1", "yes")
    if not use_rekognition:
        return None

    aws_key = getattr(settings, "AWS_ACCESS_KEY_ID", None) or os.environ.get("AWS_ACCESS_KEY_ID")
    aws_secret = getattr(settings, "AWS_SECRET_ACCESS_KEY", None) or os.environ.get("AWS_SECRET_ACCESS_KEY")
    aws_region = getattr(settings, "AWS_S3_REGION_NAME", None) or os.environ.get("AWS_S3_REGION_NAME") or "us-east-1"
    if not aws_key or not aws_secret:
        return None

    try:
        import boto3
        from botocore.config import Config

        client = boto3.client(
            "rekognition",
            aws_access_key_id=aws_key,
            aws_secret_access_key=aws_secret,
            region_name=aws_region,
            config=Config(connect_timeout=2, read_timeout=3, retries={"max_attempts": 1}),
        )
        resp = client.detect_moderation_labels(
            Image={"Bytes": image_bytes},
            MinConfidence=65.0,
        )
        labels = resp.get("ModerationLabels") or []
        for lbl in labels:
            name = str(lbl.get("Name") or "").lower()
            parent = str(lbl.get("ParentName") or "").lower()
            combined = f"{parent} {name}"
            if any(k in combined for k in ("adult toys", "sex toy")):
                return False, ModerationCategory.ADULT_TOYS, name
            if any(k in combined for k in ("explicit nudity", "genitalia", "sexual activity", "nudity", "illustrated explicit")):
                return False, ModerationCategory.NUDITY_OR_SEXUAL, name
            if any(k in combined for k in ("tobacco", "smoking", "vaping", "cigarette")):
                return False, ModerationCategory.TOBACCO_OR_VAPE, name
            if any(k in combined for k in ("drugs", "narcotics", "cannabis")) and "pills" not in name:
                return False, ModerationCategory.DRUGS_OR_NARCOTICS, name
            if any(k in combined for k in ("weapons", "weapon", "firearm", "graphic violence", "gore", "corpses")):
                return False, ModerationCategory.WEAPONS_OR_VIOLENCE, name
        return True, ModerationCategory.SAFE, "AWS Rekognition OK"
    except Exception as exc:
        logger.warning(f"[ContentModeration] AWS Rekognition fallback: {exc}")
        return None


def _check_with_openai_moderation(image_bytes: bytes) -> Optional[Tuple[bool, str, str]]:
    """
    Opción A: Endpoint oficial gratuito `/v1/moderations` (`omni-moderation-latest`) de OpenAI
    si `OPENAI_API_KEY` está configurada en el entorno.
    """
    openai_key = (
        getattr(settings, "OPENAI_API_KEY", None)
        or os.environ.get("OPENAI_API_KEY", "")
    ).strip()
    if not openai_key:
        return None

    try:
        b64 = base64.b64encode(image_bytes).decode("ascii")
        resp = requests.post(
            "https://api.openai.com/v1/moderations",
            headers={
                "Authorization": f"Bearer {openai_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "omni-moderation-latest",
                "input": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                    }
                ],
            },
            timeout=4.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results") or []
            if results:
                first = results[0]
                if first.get("flagged"):
                    cats = first.get("categories") or {}
                    if cats.get("sexual") or cats.get("sexual/minors"):
                        return False, ModerationCategory.NUDITY_OR_SEXUAL, "OpenAI sexual flag"
                    if cats.get("violence") or cats.get("violence/graphic") or cats.get("illicit/violent"):
                        return False, ModerationCategory.WEAPONS_OR_VIOLENCE, "OpenAI violence flag"
                    if cats.get("illicit"):
                        return False, ModerationCategory.DRUGS_OR_NARCOTICS, "OpenAI illicit flag"
                    return False, ModerationCategory.NUDITY_OR_SEXUAL, "OpenAI moderation flag"
                return True, ModerationCategory.SAFE, "OpenAI Moderation OK"
    except Exception as exc:
        logger.warning(f"[ContentModeration] OpenAI Moderation fallback: {exc}")
    return None


def _check_with_openrouter_vision(image_bytes: bytes) -> Optional[Tuple[bool, str, str]]:
    """
    Clasificador visual ultrarrápido usando `OPENROUTER_API_KEY` (`google/gemini-2.5-flash`)
    sobre la imagen ya comprimida a <= 50 KB. Detecta con precisión las 5 categorías prohibidas
    por CartMaker y Google Play (incluyendo consoladores/juguetes sexuales y cigarrillos/vapers).
    """
    openrouter_key = (
        getattr(settings, "OPENROUTER_API_KEY", None)
        or os.environ.get("OPENROUTER_API_KEY", "")
    ).strip()
    if not openrouter_key:
        return None

    try:
        b64 = base64.b64encode(image_bytes).decode("ascii")
        prompt = (
            "Eres el clasificador de seguridad de contenido de CartMaker (Google Play UGC Compliance). "
            "Analiza la imagen y responde ÚNICAMENTE un objeto JSON válido con el formato exacto: "
            '{"allowed": true|false, "category": "SAFE"|"NUDITY_OR_SEXUAL"|"ADULT_TOYS"|"TOBACCO_OR_VAPE"|"DRUGS_OR_NARCOTICS"|"WEAPONS_OR_VIOLENCE"}\n'
            "Marca allowed=false si la imagen muestra cualquiera de estos elementos:\n"
            "1. NUDITY_OR_SEXUAL: Desnudez humana, genitales (pene, vagina), pezones femeninos descubiertos, glúteos desnudos explícitos, pornografía o actos sexuales.\n"
            "2. ADULT_TOYS: Juguetes sexuales, consoladores, dildos, vibradores sexuales, muñecas sexuales o artículos eróticos de sex-shop con formas fálicas/anatómicas.\n"
            "3. TOBACCO_OR_VAPE: Cigarrillos, cajetillas de cigarros, tabaco, vapers, cigarrillos electrónicos, pods de nicotina o narguiles/hookahs.\n"
            "4. DRUGS_OR_NARCOTICS: Marihuana, cannabis, cocaína, pastillas ilícitas, drogas o bongs.\n"
            "5. WEAPONS_OR_VIOLENCE: Armas de fuego reales (pistolas, rifles, escopetas), municiones reales, explosivos o violencia sangrienta.\n"
            "EXCEPCIÓN DE FARMACIA Y SALUD SEXUAL (PERMITIDO): Los productos farmacéuticos de Salud Sexual y Planificación Familiar en su empaque comercial "
            "(cajas de preservativos/condones como Durex/Prudence/Duo, geles y lubricantes íntimos de farmacia como K-Y, pruebas de embarazo como Clearblue, "
            "pastillas anticonceptivas, óvulos, copas menstruales y jabones de higiene íntima) SÍ están permitidos: para ellos responde allowed=true y category='SAFE' "
            "siempre que no muestren desnudez humana ni juguetes sexuales.\n"
            "Para cualquier otro producto comercial normal (comida, ropa, calzado, electrónica, hogar, repuestos, cosméticos, farmacia, etc.), responde allowed=true y category='SAFE'."
        )

        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {openrouter_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": getattr(settings, "DOMAIN", "https://www.cartmaker.app"),
                "X-Title": "CartMaker Content Moderation",
            },
            json={
                "model": getattr(settings, "MODERATION_VISION_MODEL", "google/gemini-2.5-flash"),
                "temperature": 0.0,
                "max_tokens": 60,
                "response_format": {"type": "json_object"},
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                            },
                        ],
                    }
                ],
            },
            timeout=4.5,
        )
        if resp.status_code == 200:
            payload = resp.json()
            choices = payload.get("choices") or []
            if choices:
                raw_content = (choices[0].get("message") or {}).get("content") or ""
                # Extraemos JSON limpio incluso si viene envuelto en ```json
                cleaned = raw_content.strip()
                if cleaned.startswith("```"):
                    cleaned = re.sub(r"^```(?:json)?|```$", "", cleaned, flags=re.MULTILINE).strip()
                parsed = json.loads(cleaned)
                allowed = bool(parsed.get("allowed", True))
                category = str(parsed.get("category") or ModerationCategory.SAFE).upper().strip()
                if not allowed and category == ModerationCategory.SAFE:
                    category = ModerationCategory.NUDITY_OR_SEXUAL
                return allowed, category, "Gemini Vision Moderation"
    except Exception as exc:
        logger.warning(f"[ContentModeration] OpenRouter Vision fallback: {exc}")
    return None


def moderate_image_bytes(
    image_bytes: bytes,
    folder_path: str = "",
    file_name: str = "",
    schedule_recheck: bool = True,
) -> None:
    """
    Evalúa una imagen en memoria ANTES de subirla a AWS S3 o guardarla en disco.
    Si detecta contenido prohibido (desnudos, juguetes sexuales, tabaco/vapers, drogas o armas),
    lanza `ContentModerationError` bloqueando la subida.
    """
    if not image_bytes:
        return

    # 1. Revisamos también el nombre del archivo por si contiene palabras prohibidas explícitas
    if file_name:
        moderate_text(file_name)

    # 2. Omitimos carpetas de documentos privados KYC/KYB/pagos
    if not _should_moderate_folder(folder_path):
        return

    # Permitir desactivar moderación remota en tests unitarios si se configura explícitamente
    if getattr(settings, "DISABLE_IMAGE_MODERATION", False):
        return

    digest = hashlib.sha256(image_bytes).hexdigest()
    cache_key = f"cm:mod:img:v1:{digest}"
    try:
        cached = cache.get(cache_key)
        if isinstance(cached, dict):
            if not cached.get("allowed", True):
                cat = cached.get("category") or ModerationCategory.NUDITY_OR_SEXUAL
                raise ContentModerationError(category=cat)
            return
    except ContentModerationError:
        raise
    except Exception:
        pass

    # Ejecutamos los proveedores disponibles en orden de especificidad:
    # 1) AWS Rekognition (si está activo)
    # 2) OpenRouter / Gemini 2.5 Flash Vision (detecta las 5 categorías incluyendo consoladores y cigarrillos/vapers)
    # 3) OpenAI Moderation API (omni-moderation-latest)
    verdict = (
        _check_with_aws_rekognition(image_bytes)
        or _check_with_openrouter_vision(image_bytes)
        or _check_with_openai_moderation(image_bytes)
    )

    if verdict is None:
        # Fail-open controlado: la imagen se acepta para no bloquear al usuario si la IA no responde,
        # pero se agenda una RE-VERIFICACIÓN asíncrona con reintentos (si hay algún proveedor configurado).
        if schedule_recheck:
            _schedule_unverified_recheck(folder_path, file_name)
        return

    allowed, category, _provider = verdict
    try:
        cache.set(
            cache_key,
            {"allowed": allowed, "category": category},
            timeout=7 * 86400,
        )
    except Exception:
        pass

    if not allowed:
        raise ContentModerationError(category=category)


def classify_image_bytes(image_bytes: bytes) -> Optional[Tuple[bool, str, str]]:
    """Cadena de proveedores de visión. Devuelve (allowed, category, provider) o None si ninguno respondió."""
    return (
        _check_with_aws_rekognition(image_bytes)
        or _check_with_openrouter_vision(image_bytes)
        or _check_with_openai_moderation(image_bytes)
    )


def moderation_providers_configured() -> bool:
    """True si hay al menos un proveedor de visión configurado (sin él no tiene sentido reintentar)."""
    def _cfg(name: str) -> str:
        return str(getattr(settings, name, None) or os.environ.get(name, "") or "").strip()

    rekognition_on = _cfg("USE_AWS_REKOGNITION_MODERATION").lower() in ("true", "1", "yes")
    return bool(rekognition_on or _cfg("OPENROUTER_API_KEY") or _cfg("OPENAI_API_KEY"))


def _schedule_unverified_recheck(folder_path: str, file_name: str) -> None:
    """Agenda la re-verificación asíncrona de una imagen que se aceptó sin veredicto (proveedores caídos)."""
    if not file_name or not moderation_providers_configured():
        return
    full_path = os.path.join(str(folder_path or ""), str(file_name)).replace("\\", "/").lstrip("/")
    logger.warning(f"[ContentModeration] Imagen aceptada SIN veredicto, re-verificación agendada: {full_path}")
    try:
        from api.tasks import recheck_unverified_image
        recheck_unverified_image.apply_async(args=[full_path], countdown=45)
    except Exception as exc:
        logger.warning(f"[ContentModeration] No se pudo agendar re-verificación de {full_path}: {exc}")


# -------------------------------------------------------------------------
# Pre-moderación CONCURRENTE (reduce la latencia cuando se suben varias imágenes en una misma petición)
# -------------------------------------------------------------------------
_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".heic", ".gif")


def premoderate_uploaded_images(files: Iterable[Any], folder_path: str = "") -> None:
    """
    Modera EN PARALELO todas las imágenes subidas en una petición ANTES de abrir transacciones o subir a S3.
    Deja el veredicto en caché Redis (por hash del stream comprimido), de modo que el `save_file` posterior
    no repite la llamada a la IA. Lanza `ContentModerationError` en cuanto una imagen es rechazada.
    """
    from concurrent.futures import ThreadPoolExecutor

    from api.cos import compress_uploaded_image_stream

    payloads = []
    for f in files or []:
        name = str(getattr(f, "name", "") or "")
        if os.path.splitext(name)[1].lower() not in _IMAGE_EXTS:
            continue
        try:
            compressed, new_name = compress_uploaded_image_stream(f, file_name=name)
            if hasattr(compressed, "seek"):
                compressed.seek(0)
            data = compressed.read()
            if hasattr(compressed, "seek"):
                compressed.seek(0)
            if hasattr(f, "seek"):
                f.seek(0)
            payloads.append((data, new_name))
        except Exception:
            continue

    if not payloads:
        return

    def _run(item):
        data, name = item
        moderate_image_bytes(data, folder_path=folder_path, file_name=name, schedule_recheck=False)

    if len(payloads) == 1:
        _run(payloads[0])
        return

    with ThreadPoolExecutor(max_workers=min(6, len(payloads))) as pool:
        futures = [pool.submit(_run, p) for p in payloads]
        first_error: Optional[ContentModerationError] = None
        for fut in futures:
            try:
                fut.result()
            except ContentModerationError as exc:
                if first_error is None:
                    first_error = exc
            except Exception as exc:
                logger.warning(f"[ContentModeration] Pre-moderación omitida: {exc}")
    if first_error is not None:
        raise first_error


# -------------------------------------------------------------------------
# Moderación de VIDEO (frames clave con ffmpeg) y acciones automáticas del sistema
# -------------------------------------------------------------------------
def extract_video_frames(local_video_path: str, count: int = 3) -> list:
    """Extrae `count` fotogramas JPEG (≈512 px de ancho) repartidos a lo largo del video con ffmpeg."""
    import subprocess
    import tempfile

    duration = 0.0
    try:
        probe = subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", local_video_path,
            ],
            capture_output=True, text=True, timeout=30,
        )
        duration = float((probe.stdout or "0").strip() or 0)
    except Exception:
        duration = 0.0

    if duration > 1.0:
        stamps = [duration * frac for frac in ((0.12, 0.5, 0.88) if count >= 3 else (0.5,))]
    else:
        stamps = [0.0]

    frames = []
    with tempfile.TemporaryDirectory() as tmpdir:
        for idx, ts in enumerate(stamps[:count]):
            out_path = os.path.join(tmpdir, f"frame_{idx}.jpg")
            try:
                subprocess.run(
                    [
                        "ffmpeg", "-y", "-ss", f"{ts:.2f}", "-i", local_video_path,
                        "-frames:v", "1", "-vf", "scale=512:-2", "-q:v", "5", out_path,
                    ],
                    capture_output=True, timeout=60,
                )
                if os.path.isfile(out_path):
                    with open(out_path, "rb") as fh:
                        data = fh.read()
                    if data:
                        frames.append(data)
            except Exception as exc:
                logger.warning(f"[ContentModeration] No se pudo extraer frame {idx}: {exc}")
    return frames


def moderate_local_video(local_video_path: str) -> None:
    """Modera fotogramas clave de un video local. Lanza `ContentModerationError` si alguno es prohibido."""
    for frame in extract_video_frames(local_video_path):
        moderate_image_bytes(frame, folder_path="stories/frames", file_name="frame.jpg", schedule_recheck=False)


def record_system_report(target_type: str, target_id: str, category: str, description: str = "") -> None:
    """Registra una denuncia generada automáticamente por el sistema de moderación (sin usuario denunciante)."""
    try:
        from api.models import ContentReport

        reason = category if category in {c[0] for c in ContentReport.ReportReason.choices} else ContentReport.ReportReason.OTHER
        ContentReport.objects.create(
            reporter=None,
            target_type=target_type,
            target_id=str(target_id),
            reason=reason,
            description=(f"[Moderación automática] {description}")[:1000],
            status=ContentReport.ReportStatus.REMOVED,
        )
    except Exception as exc:
        logger.warning(f"[ContentModeration] No se pudo registrar el reporte del sistema: {exc}")


def purge_image_references(path: str) -> int:
    """
    Quita de la base de datos toda referencia a una imagen eliminada por moderación, para que la app
    no apunte a un archivo inexistente (productos, combos, perfiles, tiendas, videos).
    """
    from api.models import Company, CompanyStore, CompanyVideoStory, Product, ProductsCombo, User

    changed = 0
    clean = str(path or "").lstrip("/")
    if not clean:
        return 0
    try:
        for model, field in ((Product, "images"), (ProductsCombo, "custom_images")):
            for obj in model.objects.filter(**{f"{field}__contains": [clean]}):
                setattr(obj, field, [x for x in (getattr(obj, field) or []) if x != clean])
                obj.save(update_fields=[field])
                changed += 1
        changed += Company.objects.filter(image=clean).update(image=None)
        changed += Company.objects.filter(presentation_video_thumbnail=clean).update(presentation_video_thumbnail=None)
        changed += CompanyStore.objects.filter(store_img_url=clean).update(store_img_url=None)
        changed += User.objects.filter(profile_picture=clean).update(profile_picture="")
        changed += CompanyVideoStory.objects.filter(thumbnail=clean).update(thumbnail=None)
    except Exception as exc:
        logger.warning(f"[ContentModeration] Error purgando referencias de {clean}: {exc}")
    return changed
