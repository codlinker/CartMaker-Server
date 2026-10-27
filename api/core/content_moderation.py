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
    for exempt in EXEMPT_DOCUMENT_PREFIXES:
        if clean.startswith(exempt):
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
            if any(k in combined for k in ("tobacco", "smoking", "vaping", "cigarette", "pills")):
                return False, ModerationCategory.TOBACCO_OR_VAPE, name
            if any(k in combined for k in ("drugs", "drug", "narcotics", "cannabis")):
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
            "2. ADULT_TOYS: Juguetes sexuales, consoladores, dildos, vibradores sexuales, muñecas sexuales o artículos de sex-shop.\n"
            "3. TOBACCO_OR_VAPE: Cigarrillos, cajetillas de cigarros, tabaco, vapers, cigarrillos electrónicos, pods de nicotina o narguiles/hookahs.\n"
            "4. DRUGS_OR_NARCOTICS: Marihuana, cannabis, cocaína, pastillas ilícitas, drogas o bongs.\n"
            "5. WEAPONS_OR_VIOLENCE: Armas de fuego reales (pistolas, rifles, escopetas), municiones reales, explosivos o violencia sangrienta.\n"
            "Para cualquier otro producto comercial normal (comida, ropa, calzado, electrónica, hogar, repuestos, cosméticos, etc.), responde allowed=true y category='SAFE'."
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
