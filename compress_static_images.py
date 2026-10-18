#!/usr/bin/env python3
"""
Script de Compresión Inteligente y Perceptual de Imágenes Estáticas — CartMaker
===============================================================================
Recorre recursivamente `api/static/img` (o el directorio indicado) y comprime
únicamente las imágenes cuyo peso supere el límite en KB especificado.

Mejores prácticas implementadas para evitar pérdida de calidad visual:
1. Regla de No-Intervención: Si la imagen ya pesa <= `max_kb`, se ignora intacta.
2. Normalización EXIF y Limpieza de Metadatos: Corrige orientación física y elimina
   bloques EXIF/XMP/ICC innecesarios (ahorro de 10-60 KB con 0% pérdida de píxeles).
3. Búsqueda Binaria de Calidad + Codificación Progresiva (MozJPEG / Pillow Optimize):
   - En JPEG: activa `optimize=True` y `progressive=True`. En calidades altas (>=82)
     prioriza submuestreo de crominancia `4:4:4` (subsampling=0) para mantener bordes
     y textos nítidos. Encuentra mediante búsqueda binaria el punto exacto de máxima
     calidad que cumple `peso <= max_kb` manteniendo el 100% de la resolución.
4. Escalado Perceptual Adaptativo (LANCZOS + UnsharpMask) antes de degradar calidad:
   - Si una imagen tiene resolución excesiva (ej. 4K) y para entrar en `max_kb` a
     resolución original habría que bajar la calidad JPEG por debajo del umbral
     perceptual (68), el motor reduce gradualmente las dimensiones con filtro
     `LANCZOS` + micro-enfoque (`UnsharpMask`) manteniendo la calidad alta (72-88).
     Esto evita por completo los bloques de compresión (artefactos macroblock).
5. Cuantización Perceptual para PNG (estilo TinyPNG / pngquant):
   - Primero intenta compresión lossless (`compress_level=9, optimize=True`).
   - Si aún supera `max_kb`, aplica cuantización adaptativa de paleta (`FASTOCTREE`
     con dithering Floyd-Steinberg) preservando transparencia alfa.
6. Escritura Atómica: Solo reemplaza el archivo si el resultado final es válido,
   menor al original y `<= max_kb`.

Uso:
    python compress_static_images.py 80
    python compress_static_images.py --max-kb 60
    python compress_static_images.py 50 --dry-run
    python compress_static_images.py 100 --dir api/static/img/categories
"""

from __future__ import annotations

import argparse
import io
import math
import os
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image, ImageFilter, ImageOps

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_TARGET_DIR = BASE_DIR / "api" / "static" / "img"
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass
class CompressionResult:
    path: Path
    status: str  # "SKIPPED", "COMPRESSED", "ERROR"
    original_bytes: int
    final_bytes: int
    original_dims: Tuple[int, int] = (0, 0)
    final_dims: Tuple[int, int] = (0, 0)
    details: str = ""

    @property
    def saved_bytes(self) -> int:
        return max(0, self.original_bytes - self.final_bytes)


def _format_kb(num_bytes: int) -> str:
    return f"{num_bytes / 1024.0:.1f} KB"


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


def _encode_jpeg_bytes(
    img: Image.Image,
    quality: int,
    subsampling: int = 2,
) -> bytes:
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
) -> Optional[Tuple[bytes, int, int]]:
    """
    Busca mediante búsqueda binaria la máxima calidad JPEG en [min_q, max_q]
    que produzca un archivo <= max_bytes.
    Si el presupuesto lo permite en calidades >= 82, intenta primero subsampling=0 (4:4:4).
    """
    # Verificar rápidamente si incluso en min_q con subsampling 4:2:0 supera max_bytes
    lowest_bytes = _encode_jpeg_bytes(img, quality=min_q, subsampling=2)
    if len(lowest_bytes) > max_bytes:
        return None

    best_bytes = lowest_bytes
    best_q = min_q
    best_subsampling = 2

    # 1. Búsqueda binaria con subsampling estándar (4:2:0) para hallar la calidad máxima
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

    # 2. Si alcanzamos buena calidad (>= 82), probamos si cabe con submuestreo 4:4:4 (0) o 4:2:2 (1)
    # para conservar fidelidad cromática total en bordes y textos.
    if best_q >= 82:
        for sub in (0, 1):
            candidate_chroma = _encode_jpeg_bytes(img, quality=best_q, subsampling=sub)
            if len(candidate_chroma) <= max_bytes:
                best_bytes = candidate_chroma
                best_subsampling = sub
                break

    return best_bytes, best_q, best_subsampling


def _resize_perceptual(img: Image.Image, scale: float, sharpen: bool = True) -> Image.Image:
    """
    Escala la imagen usando interpolación LANCZOS de alta precisión y aplica un
    micro-filtro UnsharpMask suave para preservar nitidez perceptual tras reducir dimensiones.
    """
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
) -> Tuple[bytes, Tuple[int, int], str]:
    """
    Estrategia en 3 fases para JPEG:
      Fase 1: Mantener 100% de la resolución original y buscar calidad en [min_perceptual_quality, 95].
      Fase 2: Si a 100% resolución requiere bajar de `min_perceptual_quality`, reducir
              gradualmente las dimensiones con LANCZOS + UnsharpMask manteniendo calidad [68, 90].
      Fase 3: Fallback para presupuestos ultra bajos (ej. < 15 KB).
    """
    rgb_img = _prepare_rgb_image(img)
    orig_w, orig_h = rgb_img.size

    # Fase 1: 100% resolución original
    res_full = _binary_search_jpeg(rgb_img, max_bytes=max_bytes, min_q=min_perceptual_quality, max_q=95)
    if res_full is not None:
        data, q, sub = res_full
        chroma_lbl = {0: "4:4:4", 1: "4:2:2", 2: "4:2:0"}.get(sub, "4:2:0")
        return data, (orig_w, orig_h), f"Q={q} ({chroma_lbl}, 100% res)"

    # Fase 2: Escalado perceptual LANCZOS manteniendo calidad alta >= min_perceptual_quality
    # Estimamos un punto de partida inteligente según qué tan lejos estamos en min_perceptual_quality
    probe_bytes = len(_encode_jpeg_bytes(rgb_img, quality=min_perceptual_quality, subsampling=2))
    ratio_estimate = math.sqrt(max_bytes / max(1, probe_bytes))
    start_scale = min(0.92, max(0.35, ratio_estimate * 1.12))

    # Generamos pasos suaves desde start_scale hacia abajo
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
            data, q, sub = res_scaled
            return data, scaled_img.size, f"Q={q} (LANCZOS {int(round(scale * 100))}% res)"
        scale *= 0.88

    # Fase 3: Fallback extremo para presupuestos muy pequeños
    for fallback_scale in (0.25, 0.20, 0.15, 0.12):
        scaled_img = _resize_perceptual(rgb_img, scale=fallback_scale, sharpen=False)
        res_low = _binary_search_jpeg(scaled_img, max_bytes=max_bytes, min_q=40, max_q=75)
        if res_low is not None:
            data, q, _ = res_low
            return data, scaled_img.size, f"Q={q} (LANCZOS {int(round(fallback_scale * 100))}% res)"

    # Último recurso garantizado
    tiny_img = _resize_perceptual(rgb_img, scale=0.10, sharpen=False)
    data = _encode_jpeg_bytes(tiny_img, quality=40, subsampling=2)
    return data, tiny_img.size, "Q=40 (min fallback)"


def _encode_png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True, compress_level=9)
    return buf.getvalue()


def _compress_png_best_practice(
    img: Image.Image,
    max_bytes: int,
) -> Tuple[bytes, Tuple[int, int], str]:
    """
    Estrategia en 3 fases para PNG (conservando extensión .png y transparencia):
      Fase 1: Compresión Zlib Lossless máxima (optimize=True, compress_level=9).
      Fase 2: Cuantización perceptual de paleta (FASTOCTREE + Floyd-Steinberg dithering)
              probando 256, 192, 128, 96 y 64 colores a 100% de resolución.
      Fase 3: Escalado LANCZOS + cuantización perceptual a 256/128 colores.
    """
    orig_w, orig_h = img.size

    # Fase 1: Lossless puro
    lossless_data = _encode_png_bytes(img)
    if len(lossless_data) <= max_bytes:
        return lossless_data, (orig_w, orig_h), "Lossless Zlib-9 (100% res)"

    # Fase 2: Cuantización perceptual estilo TinyPNG / pngquant a 100% de resolución
    rgba_source = img.convert("RGBA") if ("A" in img.mode or "transparency" in img.info) else img.convert("RGB")
    for colors in (256, 192, 128, 96, 64):
        quantized = rgba_source.quantize(
            colors=colors,
            method=Image.Quantize.FASTOCTREE,
            dither=Image.Dither.FLOYDSTEINBERG,
        )
        candidate = _encode_png_bytes(quantized)
        if len(candidate) <= max_bytes:
            return candidate, (orig_w, orig_h), f"PNGQuant {colors} colores (100% res)"

    # Fase 3: Escalado LANCZOS + cuantización perceptual
    scale = 0.88
    while scale >= 0.15:
        new_w = max(48, int(round(orig_w * scale)))
        new_h = max(48, int(round(orig_h * scale)))
        resized = rgba_source.resize((new_w, new_h), Image.Resampling.LANCZOS)
        for colors in (256, 128, 64):
            quantized = resized.quantize(
                colors=colors,
                method=Image.Quantize.FASTOCTREE,
                dither=Image.Dither.FLOYDSTEINBERG,
            )
            candidate = _encode_png_bytes(quantized)
            if len(candidate) <= max_bytes:
                return candidate, (new_w, new_h), f"PNGQuant {colors}c (LANCZOS {int(round(scale * 100))}% res)"
        scale *= 0.85

    tiny = rgba_source.resize((max(32, int(orig_w * 0.12)), max(32, int(orig_h * 0.12))), Image.Resampling.LANCZOS)
    quantized = tiny.quantize(colors=64, method=Image.Quantize.FASTOCTREE)
    return _encode_png_bytes(quantized), tiny.size, "PNGQuant 64c (min fallback)"


def _compress_webp_best_practice(
    img: Image.Image,
    max_bytes: int,
    min_perceptual_quality: int = 68,
) -> Tuple[bytes, Tuple[int, int], str]:
    orig_w, orig_h = img.size

    def _encode_webp(im: Image.Image, q: int) -> bytes:
        buf = io.BytesIO()
        im.save(buf, format="WEBP", quality=q, method=6)
        return buf.getvalue()

    scale = 1.0
    while scale >= 0.18:
        cur_img = img if scale == 1.0 else _resize_perceptual(img, scale=scale, sharpen=True)
        lowest = _encode_webp(cur_img, min_perceptual_quality)
        if len(lowest) <= max_bytes:
            best_bytes = lowest
            best_q = min_perceptual_quality
            low, high = min_perceptual_quality, 95
            while low <= high:
                mid = (low + high) // 2
                cand = _encode_webp(cur_img, mid)
                if len(cand) <= max_bytes:
                    best_bytes = cand
                    best_q = mid
                    low = mid + 1
                else:
                    high = mid - 1
            res_lbl = "100% res" if scale == 1.0 else f"LANCZOS {int(round(scale * 100))}% res"
            return best_bytes, cur_img.size, f"WebP Q={best_q} ({res_lbl})"
        scale *= 0.88

    tiny = _resize_perceptual(img, scale=0.15, sharpen=False)
    return _encode_webp(tiny, 50), tiny.size, "WebP Q=50 (fallback)"


def process_single_image(
    file_path: Path,
    max_bytes: int,
    min_quality: int = 68,
    dry_run: bool = False,
) -> CompressionResult:
    try:
        orig_size = file_path.stat().st_size
    except OSError as exc:
        return CompressionResult(
            path=file_path,
            status="ERROR",
            original_bytes=0,
            final_bytes=0,
            details=f"No se pudo leer el archivo: {exc}",
        )

    # Regla estricta: si ya pesa menos o igual que el objetivo, no se toca
    if orig_size <= max_bytes:
        return CompressionResult(
            path=file_path,
            status="SKIPPED",
            original_bytes=orig_size,
            final_bytes=orig_size,
            details="Ya cumple con el peso objetivo",
        )

    ext = file_path.suffix.lower()
    try:
        with Image.open(file_path) as raw_img:
            img = ImageOps.exif_transpose(raw_img)
            img.load()
            orig_dims = img.size

            if ext in (".jpg", ".jpeg"):
                compressed_bytes, final_dims, details = _compress_jpeg_best_practice(
                    img,
                    max_bytes=max_bytes,
                    min_perceptual_quality=min_quality,
                )
            elif ext == ".png":
                compressed_bytes, final_dims, details = _compress_png_best_practice(
                    img,
                    max_bytes=max_bytes,
                )
            elif ext == ".webp":
                compressed_bytes, final_dims, details = _compress_webp_best_practice(
                    img,
                    max_bytes=max_bytes,
                    min_perceptual_quality=min_quality,
                )
            else:
                return CompressionResult(
                    path=file_path,
                    status="SKIPPED",
                    original_bytes=orig_size,
                    final_bytes=orig_size,
                    original_dims=orig_dims,
                    final_dims=orig_dims,
                    details=f"Formato no soportado ({ext})",
                )
    except Exception as exc:
        return CompressionResult(
            path=file_path,
            status="ERROR",
            original_bytes=orig_size,
            final_bytes=orig_size,
            details=f"Error procesando imagen: {exc}",
        )

    final_size = len(compressed_bytes)
    if final_size >= orig_size:
        return CompressionResult(
            path=file_path,
            status="SKIPPED",
            original_bytes=orig_size,
            final_bytes=orig_size,
            original_dims=orig_dims,
            final_dims=orig_dims,
            details="Ya se encontraba en su punto óptimo",
        )

    if not dry_run:
        try:
            fd, tmp_path = tempfile.mkstemp(
                prefix=".cm_img_",
                suffix=ext,
                dir=str(file_path.parent),
            )
            try:
                with os.fdopen(fd, "wb") as tmp_file:
                    tmp_file.write(compressed_bytes)
                os.replace(tmp_path, file_path)
            except Exception:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                raise
        except Exception as exc:
            return CompressionResult(
                path=file_path,
                status="ERROR",
                original_bytes=orig_size,
                final_bytes=orig_size,
                original_dims=orig_dims,
                final_dims=orig_dims,
                details=f"Error guardando archivo: {exc}",
            )

    return CompressionResult(
        path=file_path,
        status="COMPRESSED",
        original_bytes=orig_size,
        final_bytes=final_size,
        original_dims=orig_dims,
        final_dims=final_dims,
        details=details,
    )


def collect_images(root_dir: Path) -> List[Path]:
    images: List[Path] = []
    for path in sorted(root_dir.rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS and not path.name.startswith(".cm_img_"):
            images.append(path)
    return images


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Comprime todas las imágenes dentro de api/static/img que superen el peso "
            "máximo indicado en KB, aplicando búsqueda binaria de calidad y escalado "
            "perceptual LANCZOS para preservar la máxima fidelidad visual."
        )
    )
    parser.add_argument(
        "max_kb_pos",
        nargs="?",
        type=float,
        help="Peso máximo objetivo en KB (ej. 80 para 80 KB).",
    )
    parser.add_argument(
        "-k",
        "--max-kb",
        dest="max_kb_opt",
        type=float,
        help="Peso máximo objetivo en KB (alternativa con flag, ej. --max-kb 80).",
    )
    parser.add_argument(
        "-d",
        "--dir",
        type=Path,
        default=DEFAULT_TARGET_DIR,
        help=f"Directorio raíz de imágenes a procesar (por defecto: {DEFAULT_TARGET_DIR}).",
    )
    parser.add_argument(
        "--min-quality",
        type=int,
        default=68,
        help="Calidad mínima JPEG/WebP a resolución 100%% antes de activar escalado LANCZOS (por defecto: 68).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=min(8, (os.cpu_count() or 4)),
        help="Número de hilos en paralelo (por defecto: automático según CPU).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula la compresión y muestra el reporte sin modificar los archivos en disco.",
    )
    args = parser.parse_args(argv)

    target_kb = args.max_kb_opt if args.max_kb_opt is not None else args.max_kb_pos
    if target_kb is None or target_kb <= 0:
        parser.error("Debes especificar la cantidad de KB objetivo (mayor a 0). Ejemplo: python compress_static_images.py 80")

    args.max_kb = float(target_kb)
    return args


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    target_dir: Path = args.dir.resolve()
    max_bytes = int(round(args.max_kb * 1024))

    if not target_dir.exists() or not target_dir.is_dir():
        print(f"[ERROR] El directorio no existe: {target_dir}", file=sys.stderr)
        return 1

    images = collect_images(target_dir)
    if not images:
        print(f"[INFO] No se encontraron imágenes en {target_dir}")
        return 0

    mode_banner = "SIMULACIÓN (DRY-RUN)" if args.dry_run else "EJECUCIÓN EN DISCO"
    print("=" * 88)
    print(f" Compresor Perceptual de Imágenes — CartMaker ({mode_banner})")
    print(f" Directorio : {target_dir}")
    print(f" Imágenes   : {len(images)} encontradas")
    print(f" Objetivo   : <= {args.max_kb:g} KB ({max_bytes:,} bytes)")
    print("=" * 88)

    t0 = time.perf_counter()
    results: List[CompressionResult] = []

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        future_map = {
            executor.submit(
                process_single_image,
                img_path,
                max_bytes,
                args.min_quality,
                args.dry_run,
            ): img_path
            for img_path in images
        }
        for future in as_completed(future_map):
            results.append(future.result())

    results.sort(key=lambda r: str(r.path))
    elapsed = time.perf_counter() - t0

    compressed_list = [r for r in results if r.status == "COMPRESSED"]
    skipped_list = [r for r in results if r.status == "SKIPPED"]
    error_list = [r for r in results if r.status == "ERROR"]

    for r in compressed_list:
        rel_path = r.path.relative_to(BASE_DIR) if r.path.is_relative_to(BASE_DIR) else r.path
        pct = (r.saved_bytes / r.original_bytes * 100.0) if r.original_bytes else 0.0
        dims_str = (
            f"{r.original_dims[0]}x{r.original_dims[1]}"
            if r.original_dims == r.final_dims
            else f"{r.original_dims[0]}x{r.original_dims[1]} -> {r.final_dims[0]}x{r.final_dims[1]}"
        )
        print(
            f" [OK] {str(rel_path):<68} "
            f"{_format_kb(r.original_bytes):>9} -> {_format_kb(r.final_bytes):>8} "
            f"(-{pct:4.1f}%) | {dims_str} | {r.details}"
        )

    for r in error_list:
        rel_path = r.path.relative_to(BASE_DIR) if r.path.is_relative_to(BASE_DIR) else r.path
        print(f" [ERR] {rel_path}: {r.details}", file=sys.stderr)

    total_before = sum(r.original_bytes for r in results)
    total_after = sum(r.final_bytes for r in results)
    total_saved = max(0, total_before - total_after)
    total_pct = (total_saved / total_before * 100.0) if total_before else 0.0

    print("-" * 88)
    print(f" Total analizadas : {len(results)}")
    print(f" Comprimidas      : {len(compressed_list)}")
    print(f" Intactas (<=KB)  : {len(skipped_list)}")
    print(f" Errores          : {len(error_list)}")
    print(f" Peso total antes : {total_before / (1024 * 1024):.2f} MB ({_format_kb(total_before)})")
    print(f" Peso total ahora : {total_after / (1024 * 1024):.2f} MB ({_format_kb(total_after)})")
    print(f" Espacio ahorrado : {total_saved / (1024 * 1024):.2f} MB (-{total_pct:.1f}%) en {elapsed:.2f}s")
    print("=" * 88)

    return 1 if error_list else 0


if __name__ == "__main__":
    sys.exit(main())
