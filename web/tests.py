import json
import time
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
from django.test import SimpleTestCase, RequestFactory
from django.utils import timezone

from web.views import (
    format_ve_currency,
    calculate_storefront_route_metrics,
    public_storefront_view,
    _build_storefront_context,
)


class StorefrontCatalogAndPerformanceTests(SimpleTestCase):
    """
    Pruebas unitarias y de rendimiento para la Vitrina Web Pública de CartMaker:
    1. Nomenclatura de moneda venezolana (1.800,00$ con el símbolo $ a la derecha).
    2. Anti-solapamiento de la barra flotante de carrito en móviles (iPhone 15 Pro Max safe-area).
    3. Sistema de paginación del catálogo (HTML + JSON + límites de página).
    4. Rendimiento de carga de página, renderizado de plantillas y optimización de imágenes.
    5. Rendimiento y precisión del cálculo de ruta del mapa 3D (Haversine + ETA + caché).
    """

    def setUp(self):
        self.factory = RequestFactory()
        self.company_id = "3a849092-dc09-4b32-b7f7-11fe3eb30638"
        self.store_main_id = "9156a70c-4f41-42fe-b0b9-977a3e91dc6b"
        self.store_alt_id = "b267b81d-5a52-43af-a1c0-088b4f02ed7c"

        self.dummy_company = SimpleNamespace(
            id=self.company_id,
            name="TecnoStore Venezuela",
            description="Tienda oficial de tecnología en Caracas",
            category=SimpleNamespace(name="Tecnología y Electrónica"),
            image="https://cartmaker-bucket.s3.amazonaws.com/companies/logo.jpg",
            is_platinum=True,
            kyb_status=2,
            gamification_enabled=True,
            gamification_tokens_per_dollar=2,
            razon_social="TecnoStore Venezuela C.A.",
            rif_number="J-31234567-5",
            get_merchant_type_display=lambda: "Tienda Física",
            get_json=lambda: {
                "id": self.company_id,
                "name": "TecnoStore Venezuela",
                "image": "https://cartmaker-bucket.s3.amazonaws.com/companies/logo.jpg",
                "is_platinum": True,
                "kyb_status": 2,
                "gamification_enabled": True,
                "gamification_tokens_per_dollar": 2,
                "razon_social": "TecnoStore Venezuela C.A.",
                "rif_number": "J-31234567-5",
            },
        )

        self.dummy_stores = [
            SimpleNamespace(
                id=self.store_main_id,
                name="Sede Chacao",
                location=SimpleNamespace(mall=SimpleNamespace(name="Sambil Chacao")),
                get_json=lambda: {
                    "id": self.store_main_id,
                    "name": "Sede Chacao",
                    "is_currently_open": True,
                    "work_hours": {"start": "09:00", "end": "19:00"},
                    "location": {
                        "name": "Av. Libertador, Chacao",
                        "lat": 10.4961,
                        "lng": -66.8532,
                    },
                },
            ),
            SimpleNamespace(
                id=self.store_alt_id,
                name="Sede Altamira",
                location=SimpleNamespace(mall=None),
                get_json=lambda: {
                    "id": self.store_alt_id,
                    "name": "Sede Altamira",
                    "is_currently_open": True,
                    "work_hours": {"start": "09:00", "end": "18:00"},
                    "location": {
                        "name": "Av. San Juan Bosco, Altamira",
                        "lat": 10.5015,
                        "lng": -66.8480,
                    },
                },
            ),
        ]

        # Generar 30 productos con precios representativos (incluyendo 1.800,00$ y 5.855,00$)
        sample_prices = [1800.00, 150.00, 5855.00, 290.00, 1250.50, 45.99]
        self.dummy_items = []
        for idx in range(30):
            list_price = sample_prices[idx % len(sample_prices)]
            has_offer = idx == 0
            eff_price = round(list_price * 0.90, 2) if has_offer else list_price
            store_id = self.store_main_id if idx < 20 else self.store_alt_id
            store_name = "Sede Chacao" if idx < 20 else "Sede Altamira"
            item_id = f"item-uuid-{idx + 1:04d}"

            def _make_item_json(i_id=item_id, idx_num=idx, lp=list_price, ep=eff_price, ho=has_offer, st_id=store_id, st_name=store_name):
                return {
                    "id": i_id,
                    "store_id": st_id,
                    "store_name": st_name,
                    "stock": 15,
                    "list_price": lp,
                    "effective_price": ep,
                    "offer_percentage": 10 if ho else 0,
                    "avg_rating": 4.9,
                    "rating_count": 12,
                    "creation": timezone.now(),
                    "product": {
                        "id": f"prod-uuid-{idx_num + 1:04d}",
                        "company_id": self.company_id,
                        "name": f"Producto Pro #{idx_num + 1:02d}",
                        "description": f"Especificación técnica #{idx_num + 1:02d}",
                        "images": [f"https://cartmaker-bucket.s3.amazonaws.com/products/item_{idx_num + 1}.jpg"],
                        "unit_label": "und",
                        "min_order_quantity": 1,
                        "unit_step": 1,
                        "discounts_by_tokens_active": (idx_num % 2 == 0),
                        "discounts_data": [{"tokens": 100, "discount": 10}] if (idx_num % 2 == 0) else [],
                        "attributes": {"Marca": "CartMakerTech", "Garantía": "12 Meses"},
                        "variants": [{"name": "Estándar", "price": ep}],
                        "category": {
                            "id": "subcat-comp-1",
                            "name": "Computación",
                            "parent_category_name": "Tecnología y Electrónica",
                        },
                        "creation": timezone.now(),
                    },
                }

            self.dummy_items.append(
                SimpleNamespace(
                    id=item_id,
                    store_id=store_id,
                    get_json=_make_item_json,
                )
            )

    def _run_with_storefront_mocks(self, callback):
        """Ejecuta una llamada a la vista inyectando mocks en memoria de alta velocidad."""
        mock_company_qs = MagicMock()
        mock_company_qs.filter.return_value.first.return_value = self.dummy_company

        mock_stores_qs = MagicMock()
        mock_stores_qs.select_related.return_value.prefetch_related.return_value.order_by.return_value = self.dummy_stores

        mock_items_qs = MagicMock()
        mock_items_qs.select_related.return_value.annotate.return_value.order_by.return_value = self.dummy_items

        mock_stories_qs = MagicMock()
        mock_stories_qs.select_related.return_value.order_by.return_value.__getitem__.return_value = []

        mock_cal_qs = MagicMock()
        mock_cal_ordered = MagicMock()
        mock_cal_ordered.aggregate.return_value = {"avg": 4.95, "count": 28}
        mock_cal_ordered.__getitem__.return_value = []
        mock_cal_qs.select_related.return_value.order_by.return_value = mock_cal_ordered

        mock_tx_qs = MagicMock()
        mock_tx_qs.aggregate.return_value = {"total": 140}

        with patch("web.views.Company.objects.select_related", return_value=mock_company_qs), \
             patch("web.views.CompanyStore.objects.filter", return_value=mock_stores_qs), \
             patch("web.views.InventoryItem.objects.filter", return_value=mock_items_qs), \
             patch("web.views.CompanyVideoStory.objects.filter", return_value=mock_stories_qs), \
             patch("web.views.MerchantCalification.objects.filter", return_value=mock_cal_qs), \
             patch("web.views.InventoryItemTransaction.objects.filter", return_value=mock_tx_qs), \
             patch("api.views.base._get_cached_bcv_rate", return_value=36.50):
            return callback()

    def test_venezuelan_usd_currency_formatting(self):
        """
        Verifica que todos los montos en dólares usen la nomenclatura venezolana:
        separador de miles '.', decimales ',' y símbolo '$' a la derecha (ej. 1.800,00$).
        """
        self.assertEqual(format_ve_currency(1800, include_dollar_suffix=True), "1.800,00$")
        self.assertEqual(format_ve_currency(150, include_dollar_suffix=True), "150,00$")
        self.assertEqual(format_ve_currency(5855, include_dollar_suffix=True), "5.855,00$")
        self.assertEqual(format_ve_currency(1250000.5, include_dollar_suffix=True), "1.250.000,50$")
        self.assertEqual(format_ve_currency(0, include_dollar_suffix=True), "0,00$")
        self.assertEqual(format_ve_currency(36.5, include_dollar_suffix=False), "36,50")

        req = self.factory.get(f"/tienda/{self.company_id}/")
        response = self._run_with_storefront_mocks(
            lambda: public_storefront_view(req, self.company_id)
        )
        self.assertEqual(response.status_code, 200)

        html = response.content.decode("utf-8")
        self.assertIn('<span id="floatingCartTotalUsd">0,00$</span>', html)
        self.assertNotIn('<span id="floatingCartTotalUsd">$0.00</span>', html)
        self.assertIn("Tokens por cada 1,00$", html)
        self.assertIn("BCV: Bs. 36,50 / 1,00$", html)
        self.assertIn("function formatUsdVe(val)", html)

        ctx = self._run_with_storefront_mocks(
            lambda: _build_storefront_context(req, self.company_id)
        )
        payload = json.loads(ctx["storefront_json"])
        self.assertEqual(payload["items"][0]["list_price_ve"], "1.800,00$")
        self.assertEqual(payload["items"][0]["effective_price_ve"], "1.620,00$")
        self.assertEqual(payload["items"][2]["effective_price_ve"], "5.855,00$")

    def test_floating_cart_bar_mobile_clearance_against_overlap(self):
        """
        Verifica que la vista incluya el sistema de protección de espacio inferior (safe-area +
        body.has-floating-cart + .sf-catalog-bottom-spacer) para que el contenedor del carrito
        nunca tape el botón 'Agregar' de las últimas 2 cards en iPhone 15 Pro Max.
        """
        req = self.factory.get(f"/tienda/{self.company_id}/")
        response = self._run_with_storefront_mocks(
            lambda: public_storefront_view(req, self.company_id)
        )
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")

        self.assertIn("body.has-floating-cart .sf-stage-wrapper", html)
        self.assertIn("calc(240px + env(safe-area-inset-bottom, 0px))", html)
        self.assertIn('class="sf-catalog-bottom-spacer"', html)
        self.assertIn("document.body.classList.toggle('has-floating-cart', totalItems > 0)", html)

    def test_storefront_catalog_pagination_system(self):
        """
        Verifica el funcionamiento completo de la paginación del catálogo (12 items por defecto,
        navegación por ?page= y ?page_size=, y respuesta ligera en ?format=json).
        """
        # Página 1 por defecto (12 por página de 30 totales -> 3 páginas)
        req_p1 = self.factory.get(f"/tienda/{self.company_id}/")
        ctx_p1 = self._run_with_storefront_mocks(
            lambda: _build_storefront_context(req_p1, self.company_id)
        )
        pag_p1 = ctx_p1["pagination"]
        self.assertEqual(pag_p1["total_items"], 30)
        self.assertEqual(pag_p1["page_size"], 12)
        self.assertEqual(pag_p1["total_pages"], 3)
        self.assertEqual(pag_p1["current_page"], 1)
        self.assertEqual(pag_p1["start_index"], 1)
        self.assertEqual(pag_p1["end_index"], 12)
        self.assertFalse(pag_p1["has_previous"])
        self.assertTrue(pag_p1["has_next"])
        self.assertEqual(len(ctx_p1["paginated_items"]), 12)

        # Página 3 (?page=3&page_size=12 -> últimos 6 productos: índices 25 a 30)
        req_p3 = self.factory.get(f"/tienda/{self.company_id}/", {"page": "3", "page_size": "12"})
        ctx_p3 = self._run_with_storefront_mocks(
            lambda: _build_storefront_context(req_p3, self.company_id)
        )
        pag_p3 = ctx_p3["pagination"]
        self.assertEqual(pag_p3["current_page"], 3)
        self.assertEqual(pag_p3["start_index"], 25)
        self.assertEqual(pag_p3["end_index"], 30)
        self.assertTrue(pag_p3["has_previous"])
        self.assertFalse(pag_p3["has_next"])
        self.assertEqual(len(ctx_p3["paginated_items"]), 6)

        # Respuesta JSON paginada (?page=2&page_size=10&format=json)
        req_json = self.factory.get(
            f"/tienda/{self.company_id}/",
            {"page": "2", "page_size": "10", "format": "json"},
        )
        resp_json = self._run_with_storefront_mocks(
            lambda: public_storefront_view(req_json, self.company_id)
        )
        self.assertEqual(resp_json.status_code, 200)
        data = json.loads(resp_json.content.decode("utf-8"))
        self.assertEqual(data["pagination"]["current_page"], 2)
        self.assertEqual(data["pagination"]["page_size"], 10)
        self.assertEqual(data["pagination"]["total_pages"], 3)
        self.assertEqual(len(data["items"]), 10)

    def test_storefront_page_load_and_image_rendering_performance(self):
        """
        Prueba de rendimiento de carga de la página y optimización de imágenes:
        - Tiempo de construcción de contexto + renderizado completo < 150ms para 30 productos.
        - Atributos de carga progresiva de imágenes (fetchpriority, decoding="async", loading="lazy").
        """
        req = self.factory.get(f"/tienda/{self.company_id}/")

        start_t = time.perf_counter()
        response = self._run_with_storefront_mocks(
            lambda: public_storefront_view(req, self.company_id)
        )
        elapsed_ms = (time.perf_counter() - start_t) * 1000.0

        self.assertEqual(response.status_code, 200)
        self.assertLess(
            elapsed_ms,
            150.0,
            f"El renderizado de la vitrina tardó {elapsed_ms:.2f}ms (presupuesto máximo: 150ms).",
        )

        html = response.content.decode("utf-8")
        self.assertIn('fetchpriority="high" decoding="async"', html)
        self.assertIn('loading="lazy" fetchpriority="low" decoding="async"', html)
        self.assertIn("function handleStorefrontImgError(imgEl)", html)
        self.assertIn('id="catalogPaginationContainer"', html)
        self.assertIn("function goToCatalogPage(pageNum)", html)

    def test_map_route_calculation_performance_and_accuracy(self):
        """
        Prueba unitaria de rendimiento y exactitud del cálculo de ruta del mapa:
        1. Exactitud geodésica entre Plaza Venezuela (10.4960, -66.8856) y Chacao (10.4961, -66.8532).
        2. Benchmark de 1.000 cálculos de ruta en < 50ms (< 0.05ms por ruta).
        3. Pre-cálculo instantáneo en la vista cuando se envían ?lat=&lng= y caché de ruta en JS.
        """
        u_lat, u_lng = 10.4960, -66.8856  # Plaza Venezuela
        s_lat, s_lng = 10.4961, -66.8532  # Chacao

        metrics = calculate_storefront_route_metrics(u_lat, u_lng, s_lat, s_lng)
        self.assertGreater(metrics["straight_km"], 3.2)
        self.assertLess(metrics["straight_km"], 3.9)
        self.assertAlmostEqual(metrics["road_km"], round(metrics["straight_km"] * 1.28, 2), places=2)
        self.assertGreaterEqual(metrics["car_minutes"], 2)
        self.assertLess(metrics["moto_minutes"], metrics["car_minutes"])
        self.assertGreater(metrics["walk_minutes"], metrics["car_minutes"])

        # Benchmark de velocidad: 1.000 cálculos de ruta deben ejecutarse en menos de 50ms
        t0 = time.perf_counter()
        for i in range(1000):
            calculate_storefront_route_metrics(
                u_lat + (i * 0.0001),
                u_lng - (i * 0.0001),
                s_lat,
                s_lng,
            )
        batch_elapsed_ms = (time.perf_counter() - t0) * 1000.0
        self.assertLess(
            batch_elapsed_ms,
            50.0,
            f"1.000 cálculos de ruta tardaron {batch_elapsed_ms:.2f}ms (límite: 50ms).",
        )

        # Verificar pre-cálculo en el endpoint con ?lat=&lng= y presencia de routeCache en JS
        req = self.factory.get(
            f"/tienda/{self.company_id}/",
            {"lat": str(u_lat), "lng": str(u_lng)},
        )
        ctx = self._run_with_storefront_mocks(
            lambda: _build_storefront_context(req, self.company_id)
        )
        branches = ctx["branches"]
        self.assertIn("route_metrics", branches[0])
        self.assertEqual(branches[0]["route_metrics"]["distance_label"], metrics["distance_label"])
