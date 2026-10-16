import json
import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional

from asgiref.sync import sync_to_async
from django.conf import settings
from django.contrib.gis.measure import D
from django.core.cache import cache
from django.db import transaction
from django.db.models import Avg, Count, F, Q, Sum
from django.utils import timezone
from openai import AsyncOpenAI

from ..cos import storage_manager
from ..models import (
    Company,
    CompanyStore,
    CompanyVideoStory,
    InventoryItem,
    InventoryItemOffer,
    InventoryItemTransaction,
    MerchantCalification,
    Notification,
    NotificationCategory,
    NotificationSection,
    Product,
    ProductViewLog,
    TokenWallet,
    TokenWalletTransaction,
    TransactionType,
    UnmetDemandLog,
    VideoEngagementLog,
)
from ..tasks import send_push_notification_task
from .ve_geo import describe_zone

logger = logging.getLogger(__name__)


class AtlasMerchantCopilot:
    """
    Atlas Business Copilot (Modo Comerciante).
    Analiza en tiempo real la telemetría financiera, espacial y de conversión de una Compañía:
      - Demanda insatisfecha hiper-local (UnmetDemandLog en radio de 15 km).
      - Benchmarking competitivo de precios en la zona (radio de 10 km).
      - Fugas del embudo, tiempo de visualización y carritos abandonados (ProductViewLog).
      - Retención de Video Stories (VideoEngagementLog) y fidelización por Tokens (TokenWallet).
      - Ejecución de acciones comerciales en 1 toque (Ofertas Flash, Activación de Tokens, Campañas de Rescate).

    NOTA DE MODELO DE NEGOCIO:
    Actualmente es 100% gratuito para los comerciantes piloto (`ATLAS_MERCHANT_REQUIRE_SUBSCRIPTION = False`).
    Cuando se reactive el cobro por planes de comerciante en el futuro, basta con activar el flag
    `ATLAS_MERCHANT_REQUIRE_SUBSCRIPTION = True` en `settings.py`.
    """

    THREAD_CACHE_TTL = 86400 * 14  # 14 días de memoria conversacional por compañía
    SNAPSHOT_CACHE_TTL = 180       # 3 minutos de caché para snapshot analítico pesado

    def __init__(self, company: Company, user: Any = None):
        self.company = company
        self.user = user or company.owner
        self.model_name = getattr(settings, "ATLAS_MODEL", "google/gemini-2.5-flash")

        self.client: Optional[AsyncOpenAI] = None
        api_key = getattr(settings, "OPENROUTER_API_KEY", None)
        if api_key:
            self.client = AsyncOpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key,
                timeout=28.0,
                max_retries=1,
                default_headers={
                    "HTTP-Referer": getattr(settings, "DOMAIN", "https://www.cartmaker.app"),
                    "X-Title": "CartMaker Atlas Business Copilot",
                },
            )

    # =========================================================================
    # 🔐 CONTROL DE ACCESO (PILOTO GRATUITO -> FUTURA SUSCRIPCIÓN)
    # =========================================================================
    @classmethod
    def check_merchant_access(cls, company: Company) -> Dict[str, Any]:
        """
        Verifica si la compañía tiene acceso a Atlas Business Copilot.
        Por defecto durante la fase piloto retorna `allowed=True, is_pilot_free=True`.
        """
        require_sub = getattr(settings, "ATLAS_MERCHANT_REQUIRE_SUBSCRIPTION", False)
        if not require_sub:
            return {
                "allowed": True,
                "is_pilot_free": True,
                "plan_name": "Piloto Fundadores (Acceso Total Gratuito)",
                "reason": None,
            }

        sub = getattr(company, "subscription", None)
        if sub and sub.valid_until and sub.valid_until >= timezone.now():
            return {
                "allowed": True,
                "is_pilot_free": False,
                "plan_name": sub.plan.name if sub.plan else "Plan Activo",
                "reason": None,
            }

        return {
            "allowed": False,
            "is_pilot_free": False,
            "plan_name": None,
            "reason": "Atlas Business Copilot requiere una suscripción comercial activa.",
        }

    # =========================================================================
    # 📊 RADIOGRAFÍA 360° DEL NEGOCIO Y SU ZONA GEOGRÁFICA
    # =========================================================================
    def build_company_intelligence_snapshot(self, force_refresh: bool = False) -> Dict[str, Any]:
        cache_key = f"cm:atlas_merchant:snapshot:{self.company.id}"
        if not force_refresh:
            cached = cache.get(cache_key)
            if cached is not None:
                return cached

        now = timezone.now()
        horizon_30d = now - timedelta(days=30)
        horizon_7d = now - timedelta(days=7)

        # 1. Sucursales y ubicación principal
        stores = list(
            CompanyStore.objects.filter(company=self.company, is_active=True)
            .select_related("location", "location__mall")
            .order_by("-is_main_store", "creation")
        )
        main_store = stores[0] if stores else None
        center_point = (
            main_store.location.coordinates
            if (main_store and hasattr(main_store, "location") and main_store.location and main_store.location.coordinates)
            else None
        )
        zone_label = (
            describe_zone(center_point.y, center_point.x)
            if center_point
            else "Zona no configurada"
        )

        # 2. Ventas y facturación (últimos 30 días)
        sales_txs = list(
            InventoryItemTransaction.objects.filter(
                item__store__company=self.company,
                transaction_type=TransactionType.OUTCOME,
                creation__gte=horizon_30d,
            ).select_related("item__product", "item__store")
        )

        total_revenue_30d = 0.0
        total_units_30d = 0
        sales_by_item: Dict[str, Dict[str, Any]] = {}

        for tx in sales_txs:
            qty = abs(int(tx.units or 0))
            price = float(tx.item.custom_price if tx.item.custom_price is not None else tx.item.product.price)
            rev = round(qty * price, 2)
            total_units_30d += qty
            total_revenue_30d += rev

            iid = str(tx.item_id)
            if iid not in sales_by_item:
                sales_by_item[iid] = {
                    "item_id": iid,
                    "product_id": str(tx.item.product_id),
                    "name": tx.item.product.name,
                    "store_name": tx.item.store.name,
                    "units_sold": 0,
                    "revenue_usd": 0.0,
                    "price_usd": price,
                }
            sales_by_item[iid]["units_sold"] += qty
            sales_by_item[iid]["revenue_usd"] = round(sales_by_item[iid]["revenue_usd"] + rev, 2)

        # 3. Tráfico, intención de compra y carritos abandonados (últimos 7 y 30 días)
        total_views_30d = ProductViewLog.objects.filter(
            inventory_item__store__company=self.company,
            start_time__gte=horizon_30d,
        ).count()

        conversion_rate = round((total_units_30d / total_views_30d * 100.0), 2) if total_views_30d > 0 else 0.0

        recent_logs_7d = list(
            ProductViewLog.objects.filter(
                inventory_item__store__company=self.company,
                start_time__gte=horizon_7d,
            ).select_related("inventory_item__product", "inventory_item__store")
        )

        intent_by_item: Dict[str, Dict[str, Any]] = {}
        for log in recent_logs_7d:
            iid = str(log.inventory_item_id)
            dwell_s = 0.0
            if log.end_time and log.start_time:
                dwell_s = max(0.0, (log.end_time - log.start_time).total_seconds())

            entry = intent_by_item.setdefault(
                iid,
                {
                    "item_id": iid,
                    "product_id": str(log.inventory_item.product_id),
                    "name": log.inventory_item.product.name,
                    "store_name": log.inventory_item.store.name,
                    "price_usd": float(log.inventory_item.get_effective_price()),
                    "stock": int(log.inventory_item.stock),
                    "views_7d": 0,
                    "high_dwell_views_7d": 0,
                    "cart_adds_7d": 0,
                    "purchases_7d": 0,
                    "undecided_clients": set(),
                },
            )
            entry["views_7d"] += 1
            if dwell_s >= 12.0:
                entry["high_dwell_views_7d"] += 1
            if log.added_to_cart:
                entry["cart_adds_7d"] += 1
            if log.bought:
                entry["purchases_7d"] += 1
            elif (log.added_to_cart or dwell_s >= 12.0) and log.client_id:
                entry["undecided_clients"].add(str(log.client_id))

        rescue_opportunities = []
        for iid, info in intent_by_item.items():
            undecided_count = len(info["undecided_clients"])
            if undecided_count > 0 and info["stock"] > 0:
                rescue_opportunities.append({
                    "item_id": iid,
                    "product_id": info["product_id"],
                    "name": info["name"],
                    "store_name": info["store_name"],
                    "price_usd": info["price_usd"],
                    "stock": info["stock"],
                    "views_7d": info["views_7d"],
                    "cart_adds_7d": info["cart_adds_7d"],
                    "undecided_buyers_count": undecided_count,
                })
        rescue_opportunities.sort(
            key=lambda x: (x["cart_adds_7d"], x["undecided_buyers_count"], x["views_7d"]),
            reverse=True,
        )

        # 4. Inventario actual, alertas de stock bajo y productos estancados ("Stock Frío")
        active_items = list(
            InventoryItem.objects.filter(store__company=self.company, paused=False)
            .select_related("product", "product__category", "store", "offer")
        )
        low_stock_alerts = []
        stagnant_products = []

        for item in active_items:
            iid = str(item.id)
            sold_30d = sales_by_item.get(iid, {}).get("units_sold", 0)
            views_7d = intent_by_item.get(iid, {}).get("views_7d", 0)
            eff_price = item.get_effective_price()

            if item.stock <= 5 and (sold_30d > 0 or views_7d >= 3):
                low_stock_alerts.append({
                    "item_id": iid,
                    "product_id": str(item.product_id),
                    "name": item.product.name,
                    "store_name": item.store.name,
                    "stock": item.stock,
                    "units_sold_30d": sold_30d,
                })

            if item.stock >= 5 and sold_30d == 0:
                stagnant_products.append({
                    "item_id": iid,
                    "product_id": str(item.product_id),
                    "name": item.product.name,
                    "store_name": item.store.name,
                    "stock": item.stock,
                    "price_usd": eff_price,
                    "views_7d": views_7d,
                    "discounts_by_tokens_active": bool(item.product.discounts_by_tokens_active),
                    "has_active_offer": item._active_offer() is not None,
                })

        stagnant_products.sort(key=lambda x: (x["views_7d"], x["stock"]), reverse=True)

        # 5. Benchmarking competitivo de precios en la zona (Radio 10 km)
        price_benchmarks = []
        if center_point and active_items:
            my_subcat_ids = {it.product.category_id for it in active_items if it.product.category_id}
            if my_subcat_ids:
                competitor_stats = (
                    InventoryItem.objects.filter(
                        paused=False,
                        stock__gt=0,
                        product__category_id__in=my_subcat_ids,
                        store__location__coordinates__distance_lte=(center_point, D(km=10)),
                    )
                    .exclude(store__company=self.company)
                    .values("product__category_id", "product__category__name")
                    .annotate(
                        avg_price=Avg(F("product__price")),
                        competitor_items=Count("id"),
                    )
                )
                comp_map = {
                    row["product__category_id"]: {
                        "avg_price": round(float(row["avg_price"] or 0.0), 2),
                        "competitor_items": row["competitor_items"],
                        "subcategory_name": row["product__category__name"],
                    }
                    for row in competitor_stats
                    if row["avg_price"]
                }

                for item in active_items[:15]:
                    sub_id = item.product.category_id
                    if sub_id in comp_map and comp_map[sub_id]["avg_price"] > 0:
                        zone_avg = comp_map[sub_id]["avg_price"]
                        my_price = item.get_effective_price()
                        diff_pct = round(((my_price - zone_avg) / zone_avg) * 100.0, 1)
                        if abs(diff_pct) >= 12.0:
                            price_benchmarks.append({
                                "item_id": str(item.id),
                                "product_id": str(item.product_id),
                                "name": item.product.name,
                                "subcategory": comp_map[sub_id]["subcategory_name"],
                                "my_price_usd": my_price,
                                "zone_avg_price_usd": zone_avg,
                                "diff_percentage": diff_pct,
                                "status": "OVERPRICED" if diff_pct > 0 else "COMPETITIVE_ADVANTAGE",
                                "competitors_analyzed": comp_map[sub_id]["competitor_items"],
                            })
                price_benchmarks.sort(key=lambda x: x["diff_percentage"], reverse=True)

        # 6. Demanda Insatisfecha Hiper-Local (UnmetDemandLog a 15 km)
        unmet_demand_list = []
        total_unmet_searches = 0
        if center_point:
            unmet_qs = UnmetDemandLog.objects.filter(
                creation__gte=horizon_30d,
                coordinates__distance_lte=(center_point, D(km=15)),
            )
            total_unmet_searches = unmet_qs.count()
            top_unmet = (
                unmet_qs.values("search_term")
                .annotate(searches=Count("id"))
                .order_by("-searches")[:10]
            )
            unmet_demand_list = [
                {"term": row["search_term"].capitalize(), "searches": row["searches"]}
                for row in top_unmet
                if row.get("search_term")
            ]

        # 7. Fidelización y Candado de Clientes (TokenWallets)
        active_wallets_qs = TokenWallet.objects.filter(company=self.company, balance__gt=0)
        locked_in_customers = active_wallets_qs.count()
        total_tokens_in_circulation = active_wallets_qs.aggregate(total=Sum("balance"))["total"] or 0

        # 8. Rendimiento de Video Stories
        video_logs_30d = list(
            VideoEngagementLog.objects.filter(video__company=self.company, timestamp__gte=horizon_30d)
        )
        video_views_30d = len(video_logs_30d)
        video_completions_30d = sum(1 for v in video_logs_30d if v.video_completed)
        video_completion_rate = round((video_completions_30d / video_views_30d * 100.0), 1) if video_views_30d > 0 else 0.0

        # 9. Calificación reputacional
        rating_aggr = MerchantCalification.objects.filter(merchant=self.company).aggregate(
            avg=Avg("rating"), count=Count("id")
        )
        avg_rating = round(float(rating_aggr["avg"] or 0.0), 2)
        rating_count = int(rating_aggr["count"] or 0)

        top_selling_products = sorted(
            sales_by_item.values(), key=lambda x: (x["revenue_usd"], x["units_sold"]), reverse=True
        )[:5]

        # 10. Construcción de Tarjetas de Acción Ejecutables en 1 Toque (Action Cards)
        action_cards = self._build_smart_action_cards(
            rescue_opportunities=rescue_opportunities,
            stagnant_products=stagnant_products,
            price_benchmarks=price_benchmarks,
            unmet_demand_list=unmet_demand_list,
            locked_in_customers=locked_in_customers,
        )

        # 11. Cálculo del Health & Opportunity Score (0 - 100)
        health_score = 60
        if total_revenue_30d > 0:
            health_score += 10
        if conversion_rate >= 3.0:
            health_score += 10
        if self.company.gamification_enabled:
            health_score += 10
        if avg_rating >= 4.5:
            health_score += 10
        health_score = min(100, health_score)

        snapshot = {
            "company": {
                "id": str(self.company.id),
                "name": self.company.name,
                "category": self.company.category.name if self.company.category else "General",
                "is_platinum": bool(self.company.is_platinum),
                "gamification_enabled": bool(self.company.gamification_enabled),
                "gamification_tokens_per_dollar": int(self.company.gamification_tokens_per_dollar or 0),
                "avg_rating": avg_rating,
                "rating_count": rating_count,
                "branches_count": len(stores),
                "primary_zone": zone_label,
            },
            "health_score": health_score,
            "financials_30d": {
                "total_revenue_usd": round(total_revenue_30d, 2),
                "total_units_sold": total_units_30d,
                "total_product_views": total_views_30d,
                "conversion_rate_pct": conversion_rate,
                "top_products": top_selling_products,
            },
            "rescue_opportunities": rescue_opportunities[:6],
            "stagnant_products": stagnant_products[:6],
            "low_stock_alerts": low_stock_alerts[:6],
            "price_benchmarks": price_benchmarks[:6],
            "unmet_demand_radar": {
                "zone_name": zone_label,
                "radius_km": 15,
                "total_missed_searches_30d": total_unmet_searches,
                "top_keywords": unmet_demand_list,
            },
            "customer_lock_in": {
                "customers_with_active_tokens": locked_in_customers,
                "total_tokens_in_circulation": total_tokens_in_circulation,
                "video_views_30d": video_views_30d,
                "video_completion_rate_pct": video_completion_rate,
            },
            "recommended_actions": action_cards,
        }

        cache.set(cache_key, snapshot, timeout=self.SNAPSHOT_CACHE_TTL)
        return snapshot

    def _build_smart_action_cards(
        self,
        rescue_opportunities: List[Dict[str, Any]],
        stagnant_products: List[Dict[str, Any]],
        price_benchmarks: List[Dict[str, Any]],
        unmet_demand_list: List[Dict[str, Any]],
        locked_in_customers: int,
    ) -> List[Dict[str, Any]]:
        cards: List[Dict[str, Any]] = []

        # Acción 1: Rescate de Casi-Clientes (Pilar 3)
        if rescue_opportunities:
            top_rescue = rescue_opportunities[0]
            cards.append({
                "id": f"act_rescue_{top_rescue['item_id'][:8]}",
                "action_type": "LAUNCH_RESCUE_CAMPAIGN",
                "badge": "🎯 Retargeting Hiper-Local",
                "title": f"Rescatar {top_rescue['undecided_buyers_count']} clientes indecisos en '{top_rescue['name']}'",
                "description": (
                    f"{top_rescue['undecided_buyers_count']} usuarios vieron detenidamente o agregaron al carrito "
                    f"'{top_rescue['name']}' esta semana sin completar el pago. Envíales una alerta Push con "
                    f"10% de descuento Flash en la App."
                ),
                "button_label": "Lanzar Campaña de Rescate (-10% por 24h)",
                "payload": {
                    "item_id": top_rescue["item_id"],
                    "offer_percentage": 10,
                    "duration_hours": 24,
                },
            })

        # Acción 2: Ajuste Competitivo / Oferta Relámpago sobre producto sobrepreciado o estancado
        overpriced = [p for p in price_benchmarks if p["status"] == "OVERPRICED"]
        if overpriced:
            top_over = overpriced[0]
            suggested_disc = min(25, max(10, int(round(top_over["diff_percentage"]))))
            cards.append({
                "id": f"act_price_{top_over['item_id'][:8]}",
                "action_type": "CREATE_FLASH_OFFER",
                "badge": "⚡ Competitividad de Zona",
                "title": f"Nivelar precio de '{top_over['name']}' frente a tu zona",
                "description": (
                    f"Tu precio (${top_over['my_price_usd']}) está {top_over['diff_percentage']}% por encima "
                    f"del promedio en 10 km (${top_over['zone_avg_price_usd']}). Activa una Oferta Flash de "
                    f"{suggested_disc}% por 48h para subir al Top de Atlas."
                ),
                "button_label": f"Activar Oferta Flash -{suggested_disc}% (48h)",
                "payload": {
                    "item_id": top_over["item_id"],
                    "percentage": suggested_disc,
                    "duration_hours": 48,
                },
            })
        elif stagnant_products:
            top_stag = stagnant_products[0]
            cards.append({
                "id": f"act_flash_{top_stag['item_id'][:8]}",
                "action_type": "CREATE_FLASH_OFFER",
                "badge": "🔥 Rotación de Stock Frío",
                "title": f"Impulsar rotación de '{top_stag['name']}' ({top_stag['stock']} en stock)",
                "description": (
                    f"Tienes {top_stag['stock']} unidades sin ventas recientes. "
                    f"Una Oferta Relámpago de 15% por 24 horas lo destacará en el radar de ofertas de tu zona."
                ),
                "button_label": "Crear Oferta Flash -15% (24h)",
                "payload": {
                    "item_id": top_stag["item_id"],
                    "percentage": 15,
                    "duration_hours": 24,
                },
            })

        # Acción 3: Activar Gamificación / Descuento con Tokens
        if not self.company.gamification_enabled or (
            stagnant_products and not stagnant_products[0].get("discounts_by_tokens_active")
        ):
            target_prod = stagnant_products[0] if stagnant_products else None
            cards.append({
                "id": "act_enable_tokens",
                "action_type": "ACTIVATE_TOKEN_DISCOUNT",
                "badge": "🪙 Fidelización & Lock-In",
                "title": (
                    f"Activar canje de Tokens en '{target_prod['name']}'"
                    if target_prod
                    else "Encender Club de Tokens de tu Compañía"
                ),
                "description": (
                    "Los clientes que acumulan Tokens en tu tienda tienen 3.2x más probabilidad de recomprar "
                    "porque sus puntos solo valen en tu negocio."
                ),
                "button_label": "Activar Fidelización con Tokens",
                "payload": {
                    "product_id": target_prod["product_id"] if target_prod else None,
                    "tokens_per_dollar": max(5, int(self.company.gamification_tokens_per_dollar or 10)),
                },
            })

        # Acción 4: Kit QR & Vitrina Web Pública
        cards.append({
            "id": "act_share_storefront",
            "action_type": "OPEN_SHARE_KIT",
            "badge": "🌐 Crecimiento Externo",
            "title": "Compartir tu Vitrina Interactiva y QR de Mostrador",
            "description": (
                "Comparte tu catálogo web interactivo en WhatsApp e Instagram o imprime tu QR de mostrador "
                "para capturar clientes hacia la App de CartMaker."
            ),
            "button_label": "Abrir Kit QR y Link Público",
            "payload": {
                "company_id": str(self.company.id),
            },
        })

        return cards

    # =========================================================================
    # 🧠 CONSULTORÍA CONVERSACIONAL CON IA (GEMINI / OPENROUTER)
    # =========================================================================
    def _thread_cache_key(self) -> str:
        return f"cm:atlas_merchant:thread:{self.company.id}"

    def get_thread_history(self) -> List[Dict[str, Any]]:
        return cache.get(self._thread_cache_key()) or []

    def clear_thread_history(self) -> None:
        cache.delete(self._thread_cache_key())

    async def consult_async(self, user_prompt: str, reset_thread: bool = False) -> Dict[str, Any]:
        if reset_thread:
            await sync_to_async(self.clear_thread_history)()

        snapshot = await sync_to_async(self.build_company_intelligence_snapshot)()
        history = await sync_to_async(self.get_thread_history)()

        system_prompt = f"""
# ROL E IDENTIDAD: ATLAS BUSINESS COPILOT (DIRECTOR COMERCIAL DE CARTMAKER)
Eres 'Atlas Business', el consultor estratégico de Inteligencia Artificial exclusivo para comerciantes de CartMaker en Venezuela.
Estás hablando directamente con el dueño/operador de la compañía **{snapshot['company']['name']}** (Categoría: {snapshot['company']['category']}, Zona principal: {snapshot['company']['primary_zone']}).

# REGLAS DE ORO DEL MODELO DE NEGOCIO CARTMAKER
1. NUNCA sugieras vender por fuera de la aplicación CartMaker (prohibido sugerir cerrar ventas por WhatsApp directo o fuera de la plataforma).
2. Cuando recomiendes promocionar en redes externas (WhatsApp Status, Instagram, TikTok, QR en tienda física), explica que deben usar el **Link de Vitrina Pública de CartMaker** o los **Links de Orden Express de CartMaker** para que el comprador descargue/abra la App de CartMaker y complete su compra protegida adentro.
3. Español venezolano ejecutivo, cercano, claro y orientado a resultados financieros ("margen", "rotación", "conversión", "ticket promedio", "demanda en tu zona"). Prohibido usar jerga callejera como "convive", "mano", "bro".
4. Basa TODOS tus consejos en los números reales de la radiografía en vivo que tienes abajo. Cita cifras exactas (vistas, búsquedas insatisfechas en su radio de 15 km, precios comparados en 10 km, clientes indecisos).
5. Sé conciso y estructurado (máximo 3 párrafos cortos o viñetas ejecutivas accionables).

# RADIOGRAFÍA EN VIVO DEL NEGOCIO (DATOS REALES DE HOY):
```json
{json.dumps(snapshot, ensure_ascii=False)}
```
""".strip()

        reply_text = ""
        if self.client:
            try:
                messages_payload = [{"role": "system", "content": system_prompt}]
                for h in history[-8:]:
                    messages_payload.append({
                        "role": "user" if h.get("origin") == "merchant" else "assistant",
                        "content": h.get("text", ""),
                    })
                messages_payload.append({"role": "user", "content": user_prompt})

                completion = await self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages_payload,
                    temperature=0.35,
                    max_tokens=700,
                )
                reply_text = (completion.choices[0].message.content or "").strip()
            except Exception as exc:
                logger.warning(f"AtlasMerchantCopilot OpenRouter fallback activado: {exc}")

        if not reply_text:
            reply_text = self._deterministic_fallback_response(user_prompt, snapshot)

        # Persistimos el turno en la memoria conversacional de la compañía
        now_iso = timezone.now().isoformat()
        history.append({"origin": "merchant", "text": user_prompt, "timestamp": now_iso})
        history.append({
            "origin": "atlas_merchant",
            "text": reply_text,
            "timestamp": now_iso,
            "action_cards": snapshot["recommended_actions"][:3],
        })
        history = history[-20:]
        await sync_to_async(cache.set)(self._thread_cache_key(), history, timeout=self.THREAD_CACHE_TTL)

        return {
            "success": True,
            "response": reply_text,
            "health_score": snapshot["health_score"],
            "kpis_highlighted": {
                "revenue_30d_usd": snapshot["financials_30d"]["total_revenue_usd"],
                "conversion_rate_pct": snapshot["financials_30d"]["conversion_rate_pct"],
                "unmet_searches_15km": snapshot["unmet_demand_radar"]["total_missed_searches_30d"],
                "undecided_buyers_count": sum(
                    r["undecided_buyers_count"] for r in snapshot["rescue_opportunities"]
                ),
                "locked_in_token_customers": snapshot["customer_lock_in"]["customers_with_active_tokens"],
            },
            "action_cards": snapshot["recommended_actions"],
            "access_status": self.check_merchant_access(self.company),
        }

    def _deterministic_fallback_response(self, user_prompt: str, snapshot: Dict[str, Any]) -> str:
        fin = snapshot["financials_30d"]
        unmet = snapshot["unmet_demand_radar"]
        rescues = snapshot["rescue_opportunities"]
        comp = snapshot["company"]

        parts = [
            f"📊 **Diagnóstico Ejecutivo para {comp['name']} ({comp['primary_zone']}):** "
            f"En los últimos 30 días registras **${fin['total_revenue_usd']} USD** en ventas "
            f"({fin['total_units_sold']} unidades) con una tasa de conversión de **{fin['conversion_rate_pct']}%**."
        ]

        if unmet["top_keywords"]:
            top_kw = ", ".join(f"'{k['term']}' ({k['searches']} búsquedas)" for k in unmet["top_keywords"][:3])
            parts.append(
                f"📍 **Demanda Insatisfecha en tu Zona (15 km):** Detecté **{unmet['total_missed_searches_30d']} búsquedas** "
                f"sin stock cercano, lideradas por {top_kw}. Publicar estos artículos en tu catálogo de CartMaker "
                f"te posicionará primero en el radar de Atlas."
            )

        if rescues:
            top_r = rescues[0]
            parts.append(
                f"🎯 **Oportunidad Inmediata de Cierre:** Tienes **{top_r['undecided_buyers_count']} clientes indecisos** "
                f"que vieron o agregaron al carrito **'{top_r['name']}'** esta semana. Usa la tarjeta de acción de abajo "
                f"para enviarles una notificación Push con descuento Flash directo a su App de CartMaker."
            )
        else:
            parts.append(
                "🚀 **Crecimiento Externo:** Comparte tu link de Vitrina Pública e imprime tu QR de mostrador "
                "desde la sección 'Mi Compañía' para que tus clientes de Instagram y tienda física descarguen "
                "CartMaker y acumulen Tokens en tu negocio."
            )

        return "\n\n".join(parts)

    # =========================================================================
    # ⚡ EJECUTOR DE ACCIONES COMERCIALES EN 1 TOQUE
    # =========================================================================
    def execute_action(self, action_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        action_type = (action_type or "").strip().upper()
        payload = payload or {}

        if action_type == "CREATE_FLASH_OFFER":
            item_id = payload.get("item_id")
            percentage = int(payload.get("percentage", 15) or 15)
            duration_hours = int(payload.get("duration_hours", 24) or 24)
            percentage = max(5, min(80, percentage))
            duration_hours = max(1, min(168, duration_hours))

            item = InventoryItem.objects.filter(
                id=item_id, store__company=self.company
            ).select_related("product", "store").first()
            if not item:
                return {"success": False, "error": "El ítem de inventario no existe o no pertenece a tu compañía."}

            valid_until = timezone.now() + timedelta(hours=duration_hours)
            with transaction.atomic():
                offer, _ = InventoryItemOffer.objects.update_or_create(
                    product_item=item,
                    defaults={
                        "percentage": percentage,
                        "valid_until": valid_until,
                    },
                )
            cache.delete(f"cm:atlas_merchant:snapshot:{self.company.id}")
            return {
                "success": True,
                "action_executed": "CREATE_FLASH_OFFER",
                "message": (
                    f"⚡ ¡Oferta Flash del {percentage}% activada en '{item.product.name}' "
                    f"por {duration_hours} horas! Ya destaca en el radar de tu zona."
                ),
                "offer": {
                    "item_id": str(item.id),
                    "product_name": item.product.name,
                    "percentage": offer.percentage,
                    "valid_until": offer.valid_until.isoformat(),
                    "new_effective_price_usd": item.get_effective_price(),
                },
            }

        if action_type == "ACTIVATE_TOKEN_DISCOUNT":
            product_id = payload.get("product_id")
            tokens_per_dollar = int(payload.get("tokens_per_dollar", 10) or 10)
            tokens_per_dollar = max(1, min(100, tokens_per_dollar))

            with transaction.atomic():
                self.company.gamification_enabled = True
                if not self.company.gamification_tokens_per_dollar:
                    self.company.gamification_tokens_per_dollar = tokens_per_dollar
                self.company.save(update_fields=["gamification_enabled", "gamification_tokens_per_dollar"])

                updated_product_name = None
                if product_id:
                    prod = Product.objects.filter(id=product_id, company=self.company).first()
                    if prod:
                        prod.discounts_by_tokens_active = True
                        prod.save(update_fields=["discounts_by_tokens_active"])
                        updated_product_name = prod.name

            cache.delete(f"cm:atlas_merchant:snapshot:{self.company.id}")
            msg = (
                f"🪙 Fidelización por Tokens activada para '{updated_product_name}' y tu compañía."
                if updated_product_name
                else "🪙 Club de Fidelización por Tokens activado exitosamente en tu compañía."
            )
            return {
                "success": True,
                "action_executed": "ACTIVATE_TOKEN_DISCOUNT",
                "message": msg,
                "gamification_enabled": True,
                "gamification_tokens_per_dollar": self.company.gamification_tokens_per_dollar,
            }

        if action_type == "LAUNCH_RESCUE_CAMPAIGN":
            return self.launch_lead_rescue_campaign(
                item_id=payload.get("item_id"),
                offer_percentage=int(payload.get("offer_percentage", 10) or 10),
                duration_hours=int(payload.get("duration_hours", 24) or 24),
            )

        if action_type == "GENERATE_STORY_SCRIPT":
            item_id = payload.get("item_id")
            item = InventoryItem.objects.filter(
                id=item_id, store__company=self.company
            ).select_related("product").first()
            prod_name = item.product.name if item else self.company.name
            price_str = f"${item.get_effective_price()}" if item else "el mejor precio"
            script = {
                "hook_0_3s": f"¿Buscando {prod_name} en tu zona sin pagar de más?",
                "body_3_10s": f"En {self.company.name} lo tenemos disponible hoy mismo por {price_str} y además ganas Tokens para tu próxima compra.",
                "cta_10_15s": "Toca el botón del producto aquí abajo en CartMaker y pídelo antes de que se agote el lote.",
            }
            return {
                "success": True,
                "action_executed": "GENERATE_STORY_SCRIPT",
                "message": f"🎬 Guion de 15 segundos generado para '{prod_name}'.",
                "script": script,
            }

        return {"success": False, "error": f"Tipo de acción '{action_type}' no reconocido."}

    # =========================================================================
    # 🎯 PILAR 3: CAMPAÑA DE RESCATE DE "CASI-CLIENTES" (RETARGETING INTERNO)
    # =========================================================================
    def launch_lead_rescue_campaign(
        self,
        item_id: str,
        offer_percentage: int = 10,
        duration_hours: int = 24,
        custom_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not item_id:
            return {"success": False, "error": "Se requiere el ID del producto en inventario (item_id)."}

        item = InventoryItem.objects.filter(
            id=item_id, store__company=self.company, paused=False
        ).select_related("product", "store").first()
        if not item:
            return {"success": False, "error": "El producto no existe o está pausado."}

        if item.stock <= 0:
            return {"success": False, "error": "No puedes lanzar una campaña de rescate sobre un producto sin stock."}

        # Cooldown anti-spam por producto (máximo 1 campaña cada 24 horas por ítem)
        cooldown_key = f"cm:rescue_campaign:cooldown:{item.id}"
        if cache.get(cooldown_key) is not None:
            return {
                "success": False,
                "error": "Ya lanzaste una campaña de rescate para este producto en las últimas 24 horas.",
                "cooldown_active": True,
            }

        horizon_7d = timezone.now() - timedelta(days=7)
        logs = list(
            ProductViewLog.objects.filter(
                inventory_item=item,
                start_time__gte=horizon_7d,
                bought=False,
            ).select_related("client")
        )

        # Filtramos clientes que agregaron al carrito o vieron >= 12s y que no hayan comprado luego ese ítem
        bought_client_ids = set(
            ProductViewLog.objects.filter(
                inventory_item=item,
                start_time__gte=horizon_7d,
                bought=True,
            ).values_list("client_id", flat=True)
        )

        target_client_ids = set()
        for log in logs:
            if not log.client_id or log.client_id in bought_client_ids:
                continue
            if str(log.client_id) == str(self.company.owner_id):
                continue
            dwell_s = 0.0
            if log.end_time and log.start_time:
                dwell_s = max(0.0, (log.end_time - log.start_time).total_seconds())
            if log.added_to_cart or dwell_s >= 12.0:
                target_client_ids.add(log.client_id)

        offer_percentage = max(0, min(70, int(offer_percentage or 0)))
        duration_hours = max(1, min(72, int(duration_hours or 24)))

        with transaction.atomic():
            if offer_percentage > 0:
                InventoryItemOffer.objects.update_or_create(
                    product_item=item,
                    defaults={
                        "percentage": offer_percentage,
                        "valid_until": timezone.now() + timedelta(hours=duration_hours),
                    },
                )

            new_price = item.get_effective_price()
            title = (
                f"🎁 -{offer_percentage}% Flash en {item.product.name[:35]}"
                if offer_percentage > 0
                else f"⚡ ¡Últimas unidades de {item.product.name[:35]}!"
            )
            body = custom_message or (
                f"{self.company.name} activó un precio especial de ${new_price:.2f} por {duration_hours}h "
                f"en el producto que estuviste viendo. ¡Aprovecha en CartMaker antes de que se agote!"
            )

            notified_count = 0
            for cid in target_client_ids:
                # Límite anti-spam por comprador (máx 2 notificaciones de rescate al día)
                buyer_cap_key = f"cm:rescue_buyer_cap:{cid}:{timezone.now().strftime('%Y%m%d')}"
                buyer_received = int(cache.get(buyer_cap_key) or 0)
                if buyer_received >= 2:
                    continue

                Notification.objects.create(
                    user_id=cid,
                    section=NotificationSection.HOME,
                    category=NotificationCategory.GAMIFICATION_ALERT,
                    title=title,
                    body=body,
                    metadata={
                        "type": "MERCHANT_RESCUE_OFFER",
                        "item_id": str(item.id),
                        "product_id": str(item.product_id),
                        "store_id": str(item.store_id),
                        "company_id": str(self.company.id),
                        "offer_percentage": offer_percentage,
                        "effective_price_usd": new_price,
                        "app_deep_link": f"cartmaker://product/{item.id}",
                    },
                )
                try:
                    send_push_notification_task.delay(
                        user_id=str(cid),
                        title=title,
                        body=body,
                        data={
                            "type": "MERCHANT_RESCUE_OFFER",
                            "item_id": str(item.id),
                            "store_id": str(item.store_id),
                            "company_id": str(self.company.id),
                            "deep_link": f"cartmaker://product/{item.id}",
                        },
                    )
                except Exception as exc:
                    logger.warning(f"No se pudo encolar push de rescate para {cid}: {exc}")

                cache.set(buyer_cap_key, buyer_received + 1, timeout=86400)
                notified_count += 1

        cache.set(cooldown_key, 1, timeout=86400)
        cache.delete(f"cm:atlas_merchant:snapshot:{self.company.id}")

        return {
            "success": True,
            "action_executed": "LAUNCH_RESCUE_CAMPAIGN",
            "item_id": str(item.id),
            "product_name": item.product.name,
            "undecided_buyers_targeted": len(target_client_ids),
            "notifications_dispatched": notified_count,
            "offer_percentage_applied": offer_percentage,
            "effective_price_usd": item.get_effective_price(),
            "message": (
                f"🎯 Campaña activada: Se enviaron alertas directas a la App de CartMaker de {notified_count} "
                f"clientes interesados en '{item.product.name}' con un precio de ${item.get_effective_price():.2f}."
            ),
        }
