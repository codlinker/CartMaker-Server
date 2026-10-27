"""
Backfill de variantes de imagen (thumb 320 px / medium 800 px en WebP) y de la cabecera
`Cache-Control: public, max-age=31536000, immutable` para las imágenes YA existentes.

Uso (siempre se puede interrumpir y reanudar: es idempotente y salta lo ya generado):

    python manage.py backfill_image_variants --dry-run
    python manage.py backfill_image_variants                       # genera variantes faltantes (4 hilos)
    python manage.py backfill_image_variants --cache-control       # además corrige Cache-Control de originales en S3
    python manage.py backfill_image_variants --only products combos --limit 500 --workers 8
    python manage.py backfill_image_variants --force               # regenera aunque ya existan
"""
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.core.management.base import BaseCommand

from api.core.image_variants import generate_image_variants
from api.cos import is_image_variant_eligible, storage_manager
from api.models import Company, CompanyStore, CompanyVideoStory, Product, ProductsCombo, User

SOURCES = ('products', 'combos', 'companies', 'stores', 'users', 'stories')


class Command(BaseCommand):
    help = "Genera variantes thumb/medium (WebP) y Cache-Control inmutable para las imágenes públicas existentes."

    def add_arguments(self, parser):
        parser.add_argument('--only', nargs='+', choices=SOURCES, default=list(SOURCES),
                            help="Limita las fuentes a procesar (por defecto todas).")
        parser.add_argument('--limit', type=int, default=0, help="Máximo de imágenes a procesar (0 = todas).")
        parser.add_argument('--workers', type=int, default=4, help="Hilos en paralelo (por defecto 4).")
        parser.add_argument('--dry-run', action='store_true', help="Solo cuenta lo pendiente, no genera nada.")
        parser.add_argument('--force', action='store_true', help="Regenera las variantes aunque ya existan.")
        parser.add_argument('--cache-control', action='store_true',
                            help="Además aplica Cache-Control inmutable a los originales ya subidos a S3.")

    # ------------------------------------------------------------------
    def _collect_paths(self, sources) -> list:
        raw_paths = []

        def _add(value):
            if isinstance(value, str) and value.strip():
                raw_paths.append(value.strip())

        if 'products' in sources:
            for images in Product.objects.exclude(images=[]).values_list('images', flat=True).iterator(chunk_size=500):
                for img in (images or []):
                    _add(img)
        if 'combos' in sources:
            for images in ProductsCombo.objects.values_list('custom_images', flat=True).iterator(chunk_size=500):
                for img in (images or []):
                    _add(img)
        if 'companies' in sources:
            for image, thumb in Company.objects.values_list('image', 'presentation_video_thumbnail').iterator(chunk_size=500):
                _add(image)
                _add(thumb)
        if 'stores' in sources:
            for value in CompanyStore.objects.values_list('store_img_url', flat=True).iterator(chunk_size=500):
                _add(value)
        if 'users' in sources:
            for value in User.objects.exclude(profile_picture='').values_list('profile_picture', flat=True).iterator(chunk_size=1000):
                _add(value)
        if 'stories' in sources:
            for value in CompanyVideoStory.objects.values_list('thumbnail', flat=True).iterator(chunk_size=500):
                _add(value)

        unique = []
        seen = set()
        for raw in raw_paths:
            clean = storage_manager.normalize_path(raw).lstrip('/')
            if clean in seen or not is_image_variant_eligible(clean):
                continue
            seen.add(clean)
            unique.append(clean)
        return unique

    def _process(self, path: str, force: bool, fix_cache_control: bool):
        cache_result = None
        if fix_cache_control:
            cache_result = storage_manager.ensure_immutable_cache_control(path)
        variants_result = generate_image_variants(path, force=force)
        return path, variants_result, cache_result

    # ------------------------------------------------------------------
    def handle(self, *args, **options):
        started = time.time()
        sources = set(options['only'])
        paths = self._collect_paths(sources)
        if options['limit'] and options['limit'] > 0:
            paths = paths[: options['limit']]

        pending = paths
        if not options['force']:
            pending = [p for p in paths if not storage_manager.variants_ready(p)]

        self.stdout.write(
            f"Imágenes elegibles: {len(paths)} | pendientes de variantes: {len(pending)} | "
            f"almacenamiento: {storage_manager.storage_type}"
        )
        if options['dry_run']:
            self.stdout.write(self.style.WARNING("--dry-run: no se generó nada."))
            return

        to_process = paths if options['cache_control'] else pending
        counters = {'generated': 0, 'exists': 0, 'missing': 0, 'skipped': 0, 'error': 0}
        cache_counters = {'updated': 0, 'ok': 0, 'skipped': 0, 'error': 0}
        done = 0
        total = len(to_process)

        with ThreadPoolExecutor(max_workers=max(1, int(options['workers']))) as pool:
            futures = [
                pool.submit(self._process, p, options['force'], options['cache_control']) for p in to_process
            ]
            for future in as_completed(futures):
                try:
                    path, variants_result, cache_result = future.result()
                except Exception as exc:  # pragma: no cover - defensivo
                    counters['error'] += 1
                    self.stderr.write(f"Error inesperado: {exc}")
                    continue
                counters[variants_result] = counters.get(variants_result, 0) + 1
                if cache_result:
                    cache_counters[cache_result] = cache_counters.get(cache_result, 0) + 1
                if variants_result in ('missing', 'error'):
                    self.stderr.write(f"  [{variants_result}] {path}")
                done += 1
                if done % 100 == 0 or done == total:
                    self.stdout.write(f"  progreso {done}/{total}")

        elapsed = time.time() - started
        self.stdout.write(self.style.SUCCESS(f"Variantes: {counters} | Cache-Control: {cache_counters} | {elapsed:.1f}s"))
        if counters.get('error'):
            self.stdout.write(self.style.WARNING("Hubo errores: vuelve a ejecutar el comando para reintentar solo lo pendiente."))
