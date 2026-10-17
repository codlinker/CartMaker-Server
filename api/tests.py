import math
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
from django.test import SimpleTestCase, TestCase
from django.core.exceptions import ValidationError
from django.core.cache import cache

from api.utils import (
    validate_venezuelan_rif_modulo11,
    normalize_biometric_vector,
    BIOMETRIC_VECTOR_DIMENSIONS,
)
from api.core.category_schemas import (
    resolve_cart_item_dynamic_pricing,
    normalize_variants_payload,
    normalize_modifier_groups_payload,
)
from chat.views import _parse_pagination


class RifModulo11ValidationTests(SimpleTestCase):
    """Pruebas unitarias del algoritmo matemático Módulo-11 del SENIAT."""

    def test_valid_juridico_rif(self):
        # J (12) + 3*3 + 1*2 + 2*7 + 3*6 + 4*5 + 5*4 + 6*3 + 7*2
        # = 12 + 9 + 2 + 14 + 18 + 20 + 20 + 18 + 14 = 127
        # 127 % 11 = 6 -> 11 - 6 = 5
        is_valid, normalized, err = validate_venezuelan_rif_modulo11("j312345675")
        self.assertTrue(is_valid)
        self.assertEqual(normalized, "J-31234567-5")
        self.assertIsNone(err)

    def test_invalid_check_digit_rejected(self):
        is_valid, normalized, err = validate_venezuelan_rif_modulo11("J-31234567-9")
        self.assertFalse(is_valid)
        self.assertEqual(normalized, "J-31234567-9")
        self.assertIn("dígito esperado: -5", err)

    def test_malformed_rif_rejected(self):
        is_valid, _, err = validate_venezuelan_rif_modulo11("X-1234-1")
        self.assertFalse(is_valid)
        self.assertIsNotNone(err)


class BiometricVectorNormalizationTests(SimpleTestCase):
    """Pruebas de normalización L2 sobre la hiperesfera unitaria S^511 (512-D)."""

    def test_valid_512d_vector_projects_to_unit_hypersphere(self):
        raw = [math.sin(i * 0.17) + (i % 5) * 0.03 for i in range(BIOMETRIC_VECTOR_DIMENSIONS)]
        ok, norm_vec, err = normalize_biometric_vector(raw)
        self.assertTrue(ok)
        self.assertIsNone(err)
        self.assertEqual(len(norm_vec), BIOMETRIC_VECTOR_DIMENSIONS)
        l2_norm = math.sqrt(sum(x * x for x in norm_vec))
        self.assertAlmostEqual(l2_norm, 1.0, places=6)

    def test_wrong_dimension_rejected(self):
        ok, _, err = normalize_biometric_vector([0.1, 0.2, 0.3])
        self.assertFalse(ok)
        self.assertIn("512 dimensiones", err)

    def test_uniform_synthetic_vector_rejected(self):
        ok, _, err = normalize_biometric_vector([0.5] * BIOMETRIC_VECTOR_DIMENSIONS)
        self.assertFalse(ok)
        self.assertIn("varianza uniforme", err)

    def test_nan_or_inf_vector_rejected(self):
        raw = [float(i + 1) for i in range(BIOMETRIC_VECTOR_DIMENSIONS)]
        raw[10] = float("nan")
        ok, _, err = normalize_biometric_vector(raw)
        self.assertFalse(ok)
        self.assertIn("NaN o infinitos", err)


class DynamicPricingAndSchemasTests(SimpleTestCase):
    """Pruebas del motor SDUI de precios dinámicos, variantes y modificadores."""

    def _make_dummy_product(self, price=10.0, variants=None, modifier_groups=None):
        return SimpleNamespace(
            price=price,
            selling_unit="unit",
            unit_label="unidad",
            category=None,
            variants=normalize_variants_payload(variants or []),
            modifier_groups=normalize_modifier_groups_payload(modifier_groups or []),
        )

    def test_variant_price_delta_and_modifiers(self):
        product = self._make_dummy_product(
            price=10.0,
            variants=[
                {"id": "var_lg", "name": "Grande", "price_delta": 3.5, "stock": 5},
            ],
            modifier_groups=[
                {
                    "id": "grp_extras",
                    "name": "Extras",
                    "required": False,
                    "max_selections": 2,
                    "options": [
                        {"id": "opt_cheese", "name": "Extra Queso", "price_delta": 1.25},
                        {"id": "opt_bacon", "name": "Tocineta", "price_delta": 2.00},
                    ],
                }
            ],
        )
        req_line = {
            "variant_id": "var_lg",
            "selected_modifiers": [
                {"group_id": "grp_extras", "option_id": "opt_cheese"},
                {"group_id": "grp_extras", "option_id": "opt_bacon"},
            ],
        }
        unit_price, meta = resolve_cart_item_dynamic_pricing(product, req_line)
        self.assertAlmostEqual(unit_price, 10.0 + 3.5 + 1.25 + 2.00, places=2)
        self.assertEqual(meta["selected_variant"]["id"], "var_lg")
        self.assertEqual(len(meta["selected_modifiers"]), 2)


class ChatPaginationSanitizationTests(SimpleTestCase):
    """Verifica el blindaje contra DoS en offset y limit de historial de chat."""

    def test_pagination_clamps_high_limit_and_negative_offset(self):
        dummy_req = SimpleNamespace(query_params={"offset": "-50", "limit": "999999"})
        offset, limit = _parse_pagination(dummy_req)
        self.assertEqual(offset, 0)
        self.assertEqual(limit, 100)

    def test_pagination_handles_non_numeric_values(self):
        dummy_req = SimpleNamespace(query_params={"offset": "abc", "limit": "xyz"})
        offset, limit = _parse_pagination(dummy_req)
        self.assertEqual(offset, 0)
        self.assertEqual(limit, 15)


class WalletAndApiKeyUnitTests(SimpleTestCase):
    """Pruebas unitarias de lógica crítica de UserWallet y CartMakerApiKey sin requerir PostGIS."""

    def test_api_key_fast_cache_digest_avoids_repeated_pbkdf2(self):
        from api.models import CartMakerApiKey
        import hashlib

        raw_key = "cmk_live_abcdef12_9876543210fedcba"
        prefix = raw_key[:16]
        expected_fast_digest = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

        cached_data = {
            "hashed_key": "pbkdf2_sha256$600000$dummy$hash",
            "is_active": True,
            "_fast_cache_digest": expected_fast_digest,
        }
        with patch.object(cache, "get", return_value=cached_data), \
             patch("api.models.check_password") as mock_check_pw:
            self.assertTrue(CartMakerApiKey.verify_key(raw_key))
            mock_check_pw.assert_not_called()

    def test_user_wallet_insufficient_balance_raises_validation_error(self):
        from api.models import UserWallet

        dummy_wallet = UserWallet(balance=25.0)
        with patch("django.db.transaction.atomic"), \
             patch.object(UserWallet.objects, "select_for_update") as mock_sfu:
            mock_sfu.return_value.get.return_value = dummy_wallet
            with self.assertRaises(ValidationError):
                dummy_wallet.regist_transaction("subtract", 50.0, "Intento de sobregiro")


class Iteration2ArchitectureHardeningTests(SimpleTestCase):
    """Pruebas de blindaje arquitectónico de la Iteración 2 (Nivel Amazon)."""

    def test_search_engine_merchant_exclusion_scope_isolates_cache(self):
        from api.core.product_search_engine import ProductSearchEngine

        anon_engine = ProductSearchEngine(10.48, -66.87, user=None)
        self.assertEqual(anon_engine._get_merchant_exclusion_scope(), "pub")

        merchant_user = SimpleNamespace(
            is_authenticated=True,
            company=SimpleNamespace(id="comp-uuid-123"),
        )
        merchant_engine = ProductSearchEngine(10.48, -66.87, user=merchant_user)
        self.assertEqual(
            merchant_engine._get_merchant_exclusion_scope(),
            "excl:comp-uuid-123",
        )

    def test_atlas_json_parser_extracts_fenced_and_wrapped_json(self):
        from api.core.atlas import AtlasManager

        mgr = AtlasManager.__new__(AtlasManager)
        raw_text = (
            "Aquí tienes el análisis solicitado:\n"
            "```json\n"
            '{"products": [{"name": "Harina PAN", "price": 1.5}]}\n'
            "```\n"
            "Espero que sea de utilidad."
        )
        parsed = mgr._parse_gemini_json_response(raw_text)
        self.assertIn("products", parsed)
        self.assertEqual(parsed["products"][0]["name"], "Harina PAN")

    def test_drf_num_proxies_and_celery_timeouts_configured(self):
        from django.conf import settings

        self.assertEqual(settings.REST_FRAMEWORK.get("NUM_PROXIES"), 1)
        self.assertLessEqual(settings.CELERY_TASK_SOFT_TIME_LIMIT, 300)
        self.assertLessEqual(settings.CELERY_TASK_TIME_LIMIT, 360)


class MerchantGrowthAndAtlasCopilotTests(SimpleTestCase):
    """Pruebas unitarias para los 3 Pilares del Ecosistema de Comerciantes (Merchant OS)."""

    def test_storefront_theme_engine_resolves_distinct_themes_per_category(self):
        from api.core.storefront_themes import resolve_company_storefront_theme

        tech = resolve_company_storefront_theme("Tecnología y Electrónica")
        beauty = resolve_company_storefront_theme("Salud y Belleza")
        food = resolve_company_storefront_theme("Alimentos y Bebidas")
        fashion = resolve_company_storefront_theme("Moda y Accesorios")
        auto = resolve_company_storefront_theme("Carros, Motos y Otros")
        hardware = resolve_company_storefront_theme("Ferretería y Construcción")

        self.assertEqual(tech["theme_key"], "tech_cyber")
        self.assertEqual(beauty["theme_key"], "beauty_editorial")
        self.assertEqual(food["theme_key"], "gourmet_bistro")
        self.assertEqual(fashion["theme_key"], "fashion_runway")
        self.assertEqual(auto["theme_key"], "auto_telemetry")
        self.assertEqual(hardware["theme_key"], "industrial_pro")
        self.assertNotEqual(tech["bg_primary"], beauty["bg_primary"])
        self.assertNotEqual(food["card_style"], fashion["card_style"])

    def test_atlas_merchant_copilot_pilot_access_is_free_by_default(self):
        from api.core.atlas_merchant import AtlasMerchantCopilot

        dummy_company = SimpleNamespace(id="comp-1", subscription=None)
        status_info = AtlasMerchantCopilot.check_merchant_access(dummy_company)
        self.assertTrue(status_info["allowed"])
        self.assertTrue(status_info["is_pilot_free"])

    def test_atlas_merchant_smart_action_cards_generation(self):
        from api.core.atlas_merchant import AtlasMerchantCopilot

        copilot = AtlasMerchantCopilot.__new__(AtlasMerchantCopilot)
        copilot.company = SimpleNamespace(
            id="comp-uuid-999",
            name="Tech Store Caracas",
            gamification_enabled=False,
            gamification_tokens_per_dollar=10,
        )
        cards = copilot._build_smart_action_cards(
            rescue_opportunities=[
                {
                    "item_id": "item-uuid-12345678",
                    "product_id": "prod-uuid-1",
                    "name": "Audífonos Bluetooth Pro",
                    "undecided_buyers_count": 14,
                    "cart_adds_7d": 5,
                }
            ],
            stagnant_products=[],
            price_benchmarks=[
                {
                    "item_id": "item-uuid-87654321",
                    "product_id": "prod-uuid-2",
                    "name": "Cargador Rápido 20W",
                    "my_price_usd": 22.0,
                    "zone_avg_price_usd": 17.5,
                    "diff_percentage": 25.7,
                    "status": "OVERPRICED",
                }
            ],
            unmet_demand_list=[{"term": "Powerbank MagSafe", "searches": 42}],
            locked_in_customers=12,
        )
        action_types = [c["action_type"] for c in cards]
        self.assertIn("LAUNCH_RESCUE_CAMPAIGN", action_types)
        self.assertIn("CREATE_FLASH_OFFER", action_types)
        self.assertIn("ACTIVATE_TOKEN_DISCOUNT", action_types)
        self.assertIn("OPEN_SHARE_KIT", action_types)

    def test_format_ve_amount_venezuelan_nomenclature(self):
        from api.models import format_ve_amount

        self.assertEqual(format_ve_amount(3.99, 2, "$", True), "3,99$")
        self.assertEqual(format_ve_amount(1800, 2, "$", True), "1.800,00$")
        self.assertEqual(format_ve_amount(149.45, 2, " Bs.", True), "149,45 Bs.")

    def test_system_config_dynamic_billing_issuer_personal_and_company(self):
        from api.models import BillingIssuerType, BillingTaxRegime, SystemConfig

        cfg = SystemConfig(
            billing_issuer_type=BillingIssuerType.PERSONAL,
            billing_issuer_name="ATREYUS DE JESUS REYES ALVAREZ",
            billing_trade_name="CartMaker",
            billing_issuer_rif="V-30222103-7",
            billing_issuer_cedula="V-30.222.103",
            billing_fiscal_address=(
                "CTRA NACIONAL GUATIRE-GUARENAS CASA TOWN HOUSE NRO C-11 "
                "CONJUNTO RESIDENCIAL EL REFUGIO GUATIRE MIRANDA ZONA POSTAL 1221"
            ),
            billing_seniat_region=(
                "GERENCIA REGIONAL DE TRIBUTOS INTERNOS REGIÓN CAPITAL / "
                "SECTOR GUARENAS / GUATIRE"
            ),
            billing_rif_certificate_number="202401P0000063963955",
            billing_tax_regime=BillingTaxRegime.EXENTO_NO_SUJETO,
            billing_iva_percentage=0.0,
        )
        personal_json = cfg.get_billing_issuer_json()
        self.assertEqual(personal_json["issuer_type"], BillingIssuerType.PERSONAL)
        self.assertEqual(personal_json["rif"], "V-30222103-7")
        self.assertEqual(personal_json["cedula"], "V-30.222.103")
        self.assertEqual(personal_json["iva_percentage"], 0.0)

        # Switching dynamically to registered company mode (J-...) with 16% IVA
        cfg.billing_issuer_type = BillingIssuerType.COMPANY
        cfg.billing_issuer_name = "CARTMAKER TECHNOLOGIES, C.A."
        cfg.billing_issuer_rif = "J-50999999-0"
        cfg.billing_tax_regime = BillingTaxRegime.CONTRIBUYENTE_ORDINARIO
        cfg.billing_iva_percentage = 16.0
        company_json = cfg.get_billing_issuer_json()
        self.assertEqual(company_json["issuer_type"], BillingIssuerType.COMPANY)
        self.assertEqual(company_json["issuer_name"], "CARTMAKER TECHNOLOGIES, C.A.")
        self.assertEqual(company_json["rif"], "J-50999999-0")
        self.assertEqual(company_json["iva_percentage"], 16.0)

    def test_unified_atlas_plus_and_business_daily_budget(self):
        from datetime import timedelta
        from django.utils import timezone
        from api.core.atlas_merchant import AtlasMerchantCopilot
        from api.models import AtlasPlusPlan, AtlasSubscriptionTier, SystemConfig

        today = timezone.localdate()
        cfg = SystemConfig(
            atlas_plus_price_usd=3.99,
            atlas_free_daily_limit=7,
            atlas_plus_daily_limit=30,
        )

        # 1. Freemium user with 7 uses consumed today -> exhausted in both Buyer & Business
        free_plan = AtlasPlusPlan(
            tier=AtlasSubscriptionTier.FREEMIUM,
            valid_until=None,
            daily_usage_date=today,
            daily_usage_count=7,
        )
        dummy_company = SimpleNamespace(id="comp-free", atlas_plan=free_plan, owner=None)
        access_free = AtlasMerchantCopilot.check_merchant_access(dummy_company, config=cfg)
        self.assertFalse(access_free["is_premium"])
        self.assertFalse(access_free["has_quota_available"])
        self.assertEqual(access_free["daily_limit"], 7)
        self.assertEqual(access_free["used_today"], 7)
        self.assertEqual(access_free["free_interactions_left"], 0)
        self.assertTrue(access_free["requires_atlas_plus"])
        self.assertEqual(access_free["atlas_plus_price_formatted"], "3,99$")

        # 2. Upgrading to Atlas Plus unlocks 30 daily uses immediately (23 remaining)
        free_plan.tier = AtlasSubscriptionTier.PREMIUM
        free_plan.valid_until = timezone.now() + timedelta(days=30)
        access_plus = AtlasMerchantCopilot.check_merchant_access(dummy_company, config=cfg)
        self.assertTrue(access_plus["is_premium"])
        self.assertTrue(access_plus["has_quota_available"])
        self.assertEqual(access_plus["daily_limit"], 30)
        self.assertEqual(access_plus["used_today"], 7)
        self.assertEqual(access_plus["free_interactions_left"], 23)
        self.assertFalse(access_plus["requires_atlas_plus"])


