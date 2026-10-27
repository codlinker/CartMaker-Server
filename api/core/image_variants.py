"""
Generación de variantes de imagen (miniaturas) para reducir datos, RAM y CPU en la app móvil.

Por cada imagen pública de UGC (producto, combo, miniatura de video/historia, empresa, sucursal, avatar) se crean:
  - `thumb`  : lado mayor 320 px  -> tarjetas y listados.
  - `medium` : lado mayor 800 px  -> detalle de producto / pantallas grandes.
Ambas en WebP calidad 80, con `Cache-Control: public, max-age=31536000, immutable`.
El original se conserva (vista completa) y NO se modifica.

Convención de nombres: `<ruta_sin_ext>__thumb.webp` / `<ruta_sin_ext>__medium.webp` (ver `api/cos.py`).
La generación corre en Celery (`generate_image_variants_task`) tras cada subida y de forma perezosa para imágenes
antiguas (`ensure_image_variants_task`). El comando `backfill_image_variants` rellena el histórico en bloque.
"""
import io
import logging
from typing import Optional

from celery import shared_task
from PIL import Image, ImageOps

from ..cos import (
    IMAGE_VARIANT_SPECS,
    IMAGE_VARIANT_WEBP_QUALITY,
    image_variant_key,
    is_image_variant_eligible,
    storage_manager,
)

logger = logging.getLogger(__name__)


def _encode_webp_variant(img: Image.Image, max_side: int) -> bytes:
    """Reduce (sin ampliar nunca) el lado mayor a `max_side` y codifica a WebP calidad 80."""
    working = img.copy()
    working.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    has_alpha = working.mode in ('RGBA', 'LA') or (working.mode == 'P' and 'transparency' in working.info)
    working = working.convert('RGBA' if has_alpha else 'RGB')
    buf = io.BytesIO()
    working.save(buf, format='WEBP', quality=IMAGE_VARIANT_WEBP_QUALITY, method=4)
    return buf.getvalue()


def generate_image_variants(relative_path: str, force: bool = False, original_bytes: Optional[bytes] = None) -> str:
    """
    Genera y sube `thumb` y `medium` de una imagen almacenada y registra la marca de variantes listas.

    Devuelve: 'generated' | 'exists' (ya estaban en el storage) | 'missing' (el original ya no existe) |
              'skipped' (ruta no elegible) | 'error'.
    """
    clean = storage_manager.normalize_path(relative_path).lstrip('/')
    if not is_image_variant_eligible(clean):
        return 'skipped'

    if not force and storage_manager.variants_ready(clean):
        return 'exists'

    if not force and all(
        storage_manager.file_exists(image_variant_key(clean, variant)) for variant in IMAGE_VARIANT_SPECS
    ):
        storage_manager.mark_variants_ready(clean)
        return 'exists'

    raw = original_bytes if original_bytes is not None else storage_manager.read_file_bytes(clean)
    if not raw:
        return 'missing'

    try:
        with Image.open(io.BytesIO(raw)) as opened:
            if getattr(opened, 'is_animated', False) and getattr(opened, 'n_frames', 1) > 1:
                opened.seek(0)
            source = ImageOps.exif_transpose(opened)
            source.load()

            for variant, max_side in IMAGE_VARIANT_SPECS.items():
                data = _encode_webp_variant(source, max_side)
                if not storage_manager.put_bytes(image_variant_key(clean, variant), data, content_type='image/webp'):
                    return 'error'
    except Exception as exc:
        logger.warning(f"⚠️ No se pudieron generar variantes de {clean}: {exc}")
        return 'error'

    storage_manager.mark_variants_ready(clean)
    return 'generated'


@shared_task(name='cartmaker.images.generate_variants', ignore_result=True, max_retries=2, default_retry_delay=20, bind=True)
def generate_image_variants_task(self, relative_path: str):
    """Genera thumb/medium tras subir una imagen. Reintenta si el storage aún no refleja el original."""
    result = generate_image_variants(relative_path, force=True)
    if result == 'missing' and self.request.retries < self.max_retries:
        raise self.retry()
    if result == 'error':
        logger.warning(f"⚠️ Variantes de imagen no generadas para {relative_path} (se reintentará perezosamente).")


@shared_task(name='cartmaker.images.ensure_variants', ignore_result=True)
def ensure_image_variants_task(relative_path: str):
    """Verifica/genera variantes de una imagen antigua (o con marca perdida). Idempotente y barata si ya existen."""
    generate_image_variants(relative_path, force=False)
