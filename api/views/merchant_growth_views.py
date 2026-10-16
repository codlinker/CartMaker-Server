"""
Herramientas de Crecimiento Omnicanal (Pilar 1) y Motor FOMO / Rescate de Clientes (Pilar 3)
para Comerciantes en CartMaker.

REGLA DE ORO ARQUITECTÓNICA:
Todo canal externo (Vitrina Web Pública, QR de Mostrador Físico, Tarjetas 9:16 para WhatsApp/Instagram
y Links de Orden Express) redirige EXCLUSIVAMENTE al ecosistema de CartMaker (App Móvil CartMaker)
para completar la compra protegida. Jamás se desvía el checkout hacia canales externos.
"""
from .base import *
from .base import _get_cached_bcv_rate
from ..core.atlas_merchant import AtlasMerchantCopilot
from ..core.storefront_themes import resolve_company_storefront_theme
from ..core.ve_geo import describe_zone


def _get_merchant_company_for_user(user) -> Optional[Company]:
    """
    Obtiene la compañía del dueño autenticado o del empleado activo con permisos.
    """
    if not user or not user.is_authenticated:
        return None
    company = Company.objects.select_related("category").filter(owner=user).first()
    if company:
        return company
    emp = (
        Employee.objects.select_related("company", "company__category")
        .filter(user=user, is_active=True)
        .first()
    )
    return emp.company if emp else None


def _get_public_domain() -> str:
    domain = getattr(settings, "DOMAIN", "https://www.cartmaker.app") or "https://www.cartmaker.app"
    return domain.rstrip("/")


class MerchantGrowthViewSet(viewsets.ViewSet):
    """
    Suite de herramientas de crecimiento externo, QR Phygital, Links de Orden Express
    y Retargeting Hiper-Local ("Rescate de Casi-Clientes") para la vista 'Mi Compañía'.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "actions"

    def get_permissions(self):
        if self.action in (
            "web_cart_handoff",
            "web_cart_handoff_dash",
            "resolve_handoff_token",
            "resolve_handoff_token_dash",
        ):
            return [AllowAny()]
        return [IsAuthenticated()]

    # =========================================================================
    # 1. KIT DE PROMOCIÓN EXTERNA Y QR PHYGITAL (GET /api/v1/merchant-growth/share-kit/)
    # =========================================================================
    def _handle_share_kit(self, request):
        company = _get_merchant_company_for_user(request.user)
        if not company:
            return Response(
                {"error": "No se encontró una compañía asociada a tu cuenta."},
                status=status.HTTP_404_NOT_FOUND,
            )

        domain = _get_public_domain()
        stores = list(
            CompanyStore.objects.filter(company=company, is_active=True)
            .select_related("location", "location__mall")
            .order_by("-is_main_store", "creation")
        )
        main_store = stores[0] if stores else None

        # Categoría dominante de sus productos para resolver el tema visual de la vitrina
        dominant_sub = (
            Product.objects.filter(company=company, category__isnull=False)
            .select_related("category__parent_category")
            .first()
        )
        dominant_parent_name = (
            dominant_sub.category.parent_category.name
            if (dominant_sub and dominant_sub.category and dominant_sub.category.parent_category)
            else ""
        )
        theme = resolve_company_storefront_theme(
            company_category_name=company.category.name if company.category else "",
            dominant_parent_category=dominant_parent_name,
        )

        storefront_url = f"{domain}/tienda/{company.id}/"
        short_storefront_url = f"{domain}/t/{company.id}/"
        qr_physical_url = f"{domain}/t/{company.id}/?src=qr_counter"
        app_deep_link = (
            f"cartmaker://store/{main_store.id}?company_id={company.id}"
            if main_store
            else f"cartmaker://company/{company.id}"
        )

        bcv_rate = _get_cached_bcv_rate(default=0.0)
        rating_aggr = MerchantCalification.objects.filter(merchant=company).aggregate(
            avg=Avg("rating"), count=Count("id")
        )
        avg_rating = round(float(rating_aggr["avg"] or 0.0), 2)

        branches_kits = []
        for s in stores:
            loc = s.location if hasattr(s, "location") else None
            zone_name = (
                describe_zone(loc.coordinates.y, loc.coordinates.x)
                if (loc and loc.coordinates)
                else s.name
            )
            branches_kits.append({
                "store_id": str(s.id),
                "store_name": s.name,
                "is_main_store": bool(s.is_main_store),
                "zone_name": zone_name,
                "public_url": f"{domain}/tienda/{company.id}/?store_id={s.id}",
                "qr_counter_url": f"{domain}/t/{company.id}/?store_id={s.id}&src=qr_counter",
                "app_deep_link": f"cartmaker://store/{s.id}?company_id={company.id}",
            })

        token_callout = (
            f"¡Gana {company.gamification_tokens_per_dollar} Tokens por cada $1 de compra en la App de CartMaker!"
            if company.gamification_enabled and company.gamification_tokens_per_dollar > 0
            else "Compra 100% protegida desde la App oficial de CartMaker."
        )

        return Response({
            "company": {
                "id": str(company.id),
                "name": company.name,
                "logo_url": storage_manager.get_url(company.image) if company.image else None,
                "category_name": company.category.name if company.category else "General",
                "is_platinum": bool(company.is_platinum),
                "kyb_verified": company.kyb_status == 2,
                "avg_rating": avg_rating,
                "gamification_enabled": bool(company.gamification_enabled),
                "gamification_tokens_per_dollar": int(company.gamification_tokens_per_dollar or 0),
                "bcv_rate": bcv_rate,
            },
            "storefront_theme": theme,
            "links": {
                "public_storefront_url": storefront_url,
                "short_storefront_url": short_storefront_url,
                "qr_counter_url": qr_physical_url,
                "app_deep_link": app_deep_link,
            },
            "printable_qr_standee": {
                "headline": f"Explora el catálogo oficial de {company.name}",
                "subheadline": "Escanea el QR para ver precios en USD / Bs. BCV en tiempo real y pedir por CartMaker App",
                "qr_data": qr_physical_url,
                "app_deep_link": app_deep_link,
                "token_reward_banner": token_callout,
                "badges": [
                    b for b in [
                        "Comercio Platinum" if company.is_platinum else None,
                        "Empresa Verificada KYB" if company.kyb_status == 2 else "Comercio Oficial CartMaker",
                        "Club de Tokens Activo" if company.gamification_enabled else None,
                    ] if b
                ],
            },
            "social_share_templates": {
                "whatsapp_status": (
                    f"🛒✨ ¡Mira todo nuestro catálogo actualizado en vivo en CartMaker!\n"
                    f"Precios al día en USD y Bs. BCV, stock en tiempo real y compra protegida en la App:\n"
                    f"👉 {short_storefront_url}"
                ),
                "instagram_bio": f"🛒 Catálogo Oficial & Pedidos por CartMaker App 👇\n{short_storefront_url}",
                "direct_client_reply": (
                    f"¡Hola! Puedes ver la disponibilidad en vivo, elegir tu talla/variante y hacer tu pedido "
                    f"directamente desde nuestro catálogo en CartMaker aquí: {short_storefront_url}"
                ),
            },
            "branches": branches_kits,
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="share-kit")
    def share_kit_dash(self, request):
        return self._handle_share_kit(request)

    @action(detail=False, methods=["get"], url_path="share_kit")
    def share_kit(self, request):
        return self._handle_share_kit(request)

    # =========================================================================
    # 2. GENERADOR DE TARJETA 9:16 PARA STORIES / WHATSAPP STATUS
    #    POST /api/v1/merchant-growth/product-story-card/
    # =========================================================================
    def _handle_product_story_card(self, request):
        company = _get_merchant_company_for_user(request.user)
        if not company:
            return Response({"error": "Compañía no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        item_id = request.data.get("item_id")
        custom_headline = (request.data.get("headline") or "").strip()
        if not item_id:
            return Response({"error": "El campo 'item_id' es obligatorio."}, status=status.HTTP_400_BAD_REQUEST)

        item = (
            InventoryItem.objects.filter(id=item_id, store__company=company)
            .select_related("product", "product__category", "product__category__parent_category", "store", "store__location", "offer")
            .first()
        )
        if not item:
            return Response(
                {"error": "El producto no existe o no pertenece a tu compañía."},
                status=status.HTTP_404_NOT_FOUND,
            )

        domain = _get_public_domain()
        bcv_rate = _get_cached_bcv_rate(default=0.0)
        list_price = item.get_list_price()
        eff_price = item.get_effective_price()
        eff_price_bs = round(eff_price * bcv_rate, 2) if bcv_rate > 0 else None
        active_offer = item._active_offer()

        parent_cat_name = (
            item.product.category.parent_category.name
            if (item.product.category and item.product.category.parent_category)
            else ""
        )
        theme = resolve_company_storefront_theme(
            company_category_name=company.category.name if company.category else "",
            dominant_parent_category=parent_cat_name,
        )

        product_web_url = f"{domain}/p/{item.id}/"
        app_deep_link = f"cartmaker://product/{item.id}?store_id={item.store_id}&company_id={company.id}"
        images = [storage_manager.get_url(img) for img in (item.product.images or []) if img]

        loc = item.store.location if hasattr(item.store, "location") else None
        zone_name = (
            describe_zone(loc.coordinates.y, loc.coordinates.x)
            if (loc and loc.coordinates)
            else item.store.name
        )

        headline = custom_headline or (
            f"⚡ ¡-{active_offer.percentage}% DE DESCUENTO HOY!"
            if active_offer
            else f"✨ Disponible hoy en {zone_name}"
        )

        return Response({
            "story_card": {
                "aspect_ratio": "9:16",
                "headline": headline,
                "product_id": str(item.product_id),
                "item_id": str(item.id),
                "product_name": item.product.name,
                "description_short": (item.product.description or "")[:120],
                "primary_image_url": images[0] if images else None,
                "gallery_urls": images[:4],
                "list_price_usd": list_price,
                "effective_price_usd": eff_price,
                "effective_price_bs": eff_price_bs,
                "bcv_rate": bcv_rate,
                "offer_percentage": int(active_offer.percentage) if active_offer else 0,
                "offer_valid_until": active_offer.valid_until.isoformat() if active_offer else None,
                "accepts_tokens": bool(company.gamification_enabled and item.product.discounts_by_tokens_active),
                "tokens_earned_on_purchase": (
                    int(round(eff_price * company.gamification_tokens_per_dollar))
                    if company.gamification_enabled
                    else 0
                ),
                "company_name": company.name,
                "company_logo_url": storage_manager.get_url(company.image) if company.image else None,
                "is_platinum": bool(company.is_platinum),
                "store_name": item.store.name,
                "zone_name": zone_name,
                "theme": theme,
                "qr_payload": product_web_url,
                "public_product_url": product_web_url,
                "app_deep_link": app_deep_link,
                "cta_label": "Pídelo en la App de CartMaker",
                "share_caption": (
                    f"🔥 {item.product.name} disponible en {company.name} ({zone_name}) por ${eff_price:.2f} "
                    f"{f'(Bs. {eff_price_bs}) ' if eff_price_bs else ''}🛒\n"
                    f"Pídelo con compra protegida en CartMaker aquí: {product_web_url}"
                ),
            }
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="product-story-card")
    def product_story_card_dash(self, request):
        return self._handle_product_story_card(request)

    @action(detail=False, methods=["post"], url_path="product_story_card")
    def product_story_card(self, request):
        return self._handle_product_story_card(request)

    # =========================================================================
    # 3. GENERADOR DE LINKS DE ORDEN EXPRESS (PARA CERRAR VENTAS EN LA APP)
    #    POST /api/v1/merchant-growth/express-order-link/
    # =========================================================================
    def _handle_express_order_link(self, request):
        company = _get_merchant_company_for_user(request.user)
        if not company:
            return Response({"error": "Compañía no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        raw_items = request.data.get("items") or []
        note = (request.data.get("note") or "").strip()[:300]
        expires_in_hours = max(1, min(72, int(request.data.get("expires_in_hours", 24) or 24)))

        if not isinstance(raw_items, list) or not raw_items:
            return Response(
                {"error": "Debes incluir al menos un producto en 'items'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        item_ids = [str(entry.get("item_id")) for entry in raw_items if isinstance(entry, dict) and entry.get("item_id")]
        db_items = {
            str(it.id): it
            for it in InventoryItem.objects.filter(
                id__in=item_ids, store__company=company, paused=False
            ).select_related("product", "store", "offer")
        }

        if not db_items:
            return Response(
                {"error": "Ninguno de los ítems seleccionados está activo en tu inventario."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        packaged_items = []
        total_usd = 0.0
        primary_store_id = None

        for entry in raw_items:
            if not isinstance(entry, dict):
                continue
            iid = str(entry.get("item_id") or "")
            if iid not in db_items:
                continue
            inv_item = db_items[iid]
            if inv_item.stock <= 0:
                return Response(
                    {"error": f"El producto '{inv_item.product.name}' no tiene stock disponible."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            qty = float(entry.get("quantity", 1) or 1)
            qty = max(0.1, min(float(inv_item.stock), qty))
            unit_price = inv_item.get_effective_price()
            line_total = round(unit_price * qty, 2)
            total_usd += line_total
            primary_store_id = str(inv_item.store_id)

            images = [storage_manager.get_url(img) for img in (inv_item.product.images or []) if img]
            packaged_items.append({
                "item_id": iid,
                "product_id": str(inv_item.product_id),
                "name": inv_item.product.name,
                "image_url": images[0] if images else None,
                "quantity": qty if inv_item.product.allow_fractional_quantity else int(qty),
                "unit_label": inv_item.product.unit_label or "und",
                "unit_price_usd": unit_price,
                "line_total_usd": line_total,
                "selected_variant": entry.get("selected_variant"),
                "selected_modifiers": entry.get("selected_modifiers") or [],
            })

        if not packaged_items:
            return Response({"error": "No se pudieron empaquetar los productos."}, status=status.HTTP_400_BAD_REQUEST)

        token = f"cme_{secrets.token_urlsafe(12)}"
        bcv_rate = _get_cached_bcv_rate(default=0.0)
        total_usd = round(total_usd, 2)
        total_bs = round(total_usd * bcv_rate, 2) if bcv_rate > 0 else None

        draft_payload = {
            "token": token,
            "type": "EXPRESS_ORDER",
            "company_id": str(company.id),
            "company_name": company.name,
            "store_id": primary_store_id,
            "items": packaged_items,
            "total_usd": total_usd,
            "total_bs": total_bs,
            "bcv_rate": bcv_rate,
            "merchant_note": note,
            "created_at": timezone.now().isoformat(),
            "expires_at": (timezone.now() + timedelta(hours=expires_in_hours)).isoformat(),
        }
        cache.set(f"cm:handoff_token:{token}", draft_payload, timeout=expires_in_hours * 3600)

        domain = _get_public_domain()
        web_url = f"{domain}/orden-express/{token}/"
        app_deep_link = f"cartmaker://express-order?token={token}"

        return Response({
            "success": True,
            "token": token,
            "web_url": web_url,
            "app_deep_link": app_deep_link,
            "summary": draft_payload,
            "share_message": (
                f"🛍️ *{company.name}* te preparó una Orden Express en CartMaker (${total_usd:.2f}"
                f"{f' / Bs. {total_bs}' if total_bs else ''}).\n"
                f"Ábrela aquí para completar tu compra protegida en la App de CartMaker:\n👉 {web_url}"
            ),
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="express-order-link")
    def express_order_link_dash(self, request):
        return self._handle_express_order_link(request)

    @action(detail=False, methods=["post"], url_path="express_order_link")
    def express_order_link(self, request):
        return self._handle_express_order_link(request)

    # =========================================================================
    # 4. PUENTE DE CARRITO WEB -> APP CARTMAKER (HANDOFF TOKEN)
    #    POST /api/v1/merchant-growth/web-cart-handoff/
    #    GET  /api/v1/merchant-growth/resolve-handoff-token/?token=...
    # =========================================================================
    def _handle_web_cart_handoff(self, request):
        company_id = request.data.get("company_id")
        store_id = request.data.get("store_id")
        raw_items = request.data.get("items") or []

        if not company_id or not isinstance(raw_items, list) or not raw_items:
            return Response(
                {"error": "Se requiere 'company_id' y una lista de 'items'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        company = Company.objects.filter(id=company_id).first()
        if not company:
            return Response({"error": "Compañía no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        item_ids = [str(x.get("item_id")) for x in raw_items if isinstance(x, dict) and x.get("item_id")]
        db_items = {
            str(it.id): it
            for it in InventoryItem.objects.filter(
                id__in=item_ids, store__company=company, paused=False
            ).select_related("product", "store", "offer")
        }

        packaged = []
        total_usd = 0.0
        resolved_store_id = str(store_id) if store_id else None

        for entry in raw_items:
            if not isinstance(entry, dict):
                continue
            iid = str(entry.get("item_id") or "")
            if iid not in db_items:
                continue
            inv = db_items[iid]
            if inv.stock <= 0:
                continue
            qty = max(0.1, min(float(inv.stock), float(entry.get("quantity", 1) or 1)))
            u_price = inv.get_effective_price()
            line_usd = round(u_price * qty, 2)
            total_usd += line_usd
            if not resolved_store_id:
                resolved_store_id = str(inv.store_id)
            images = [storage_manager.get_url(img) for img in (inv.product.images or []) if img]
            packaged.append({
                "item_id": iid,
                "product_id": str(inv.product_id),
                "name": inv.product.name,
                "image_url": images[0] if images else None,
                "quantity": qty if inv.product.allow_fractional_quantity else int(qty),
                "unit_price_usd": u_price,
                "line_total_usd": line_usd,
                "selected_variant": entry.get("selected_variant"),
                "selected_modifiers": entry.get("selected_modifiers") or [],
                "order_note": (entry.get("order_note") or "")[:250],
            })

        if not packaged:
            return Response({"error": "No hay productos válidos con stock en el carrito."}, status=status.HTTP_400_BAD_REQUEST)

        token = f"cmw_{secrets.token_urlsafe(12)}"
        bcv_rate = _get_cached_bcv_rate(default=0.0)
        total_usd = round(total_usd, 2)
        total_bs = round(total_usd * bcv_rate, 2) if bcv_rate > 0 else None

        payload = {
            "token": token,
            "type": "WEB_STOREFRONT_CART",
            "company_id": str(company.id),
            "company_name": company.name,
            "store_id": resolved_store_id,
            "items": packaged,
            "total_usd": total_usd,
            "total_bs": total_bs,
            "bcv_rate": bcv_rate,
            "created_at": timezone.now().isoformat(),
            "expires_at": (timezone.now() + timedelta(hours=72)).isoformat(),
        }
        cache.set(f"cm:handoff_token:{token}", payload, timeout=72 * 3600)

        domain = _get_public_domain()
        return Response({
            "success": True,
            "token": token,
            "app_deep_link": f"cartmaker://web-cart?token={token}",
            "web_resume_url": f"{domain}/orden-express/{token}/",
            "cart": payload,
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="web-cart-handoff")
    def web_cart_handoff_dash(self, request):
        return self._handle_web_cart_handoff(request)

    @action(detail=False, methods=["post"], url_path="web_cart_handoff")
    def web_cart_handoff(self, request):
        return self._handle_web_cart_handoff(request)

    def _handle_resolve_handoff_token(self, request):
        token = (request.query_params.get("token") or "").strip()
        if not token:
            return Response({"error": "El parámetro 'token' es obligatorio."}, status=status.HTTP_400_BAD_REQUEST)

        draft = cache.get(f"cm:handoff_token:{token}")
        if not draft:
            return Response(
                {"error": "El enlace de orden o carrito ha expirado o no existe."},
                status=status.HTTP_404_NOT_FOUND,
            )

        item_ids = [x.get("item_id") for x in (draft.get("items") or []) if x.get("item_id")]
        fresh_items = {
            str(it.id): it.get_json()
            for it in InventoryItem.objects.filter(id__in=item_ids, paused=False).select_related(
                "product", "product__category", "store", "store__company", "store__location", "offer"
            )
        }

        hydrated_items = []
        for entry in draft.get("items") or []:
            iid = str(entry.get("item_id"))
            hydrated_items.append({
                **entry,
                "live_inventory_item": fresh_items.get(iid),
                "is_available_now": iid in fresh_items and (fresh_items[iid].get("stock", 0) > 0),
            })

        return Response({
            "success": True,
            "token": token,
            "type": draft.get("type"),
            "company_id": draft.get("company_id"),
            "company_name": draft.get("company_name"),
            "store_id": draft.get("store_id"),
            "merchant_note": draft.get("merchant_note"),
            "total_usd": draft.get("total_usd"),
            "total_bs": draft.get("total_bs"),
            "bcv_rate": _get_cached_bcv_rate(default=draft.get("bcv_rate") or 0.0),
            "items": hydrated_items,
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="resolve-handoff-token")
    def resolve_handoff_token_dash(self, request):
        return self._handle_resolve_handoff_token(request)

    @action(detail=False, methods=["get"], url_path="resolve_handoff_token")
    def resolve_handoff_token(self, request):
        return self._handle_resolve_handoff_token(request)

    # =========================================================================
    # 5. PILAR 3: OPORTUNIDADES DE RESCATE Y CAMPAÑAS DE RETARGETING
    #    GET  /api/v1/merchant-growth/rescue-opportunities/
    #    POST /api/v1/merchant-growth/launch-rescue-campaign/
    # =========================================================================
    def _handle_rescue_opportunities(self, request):
        company = _get_merchant_company_for_user(request.user)
        if not company:
            return Response({"error": "Compañía no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        copilot = AtlasMerchantCopilot(company=company, user=request.user)
        snapshot = copilot.build_company_intelligence_snapshot()
        opportunities = snapshot.get("rescue_opportunities", [])

        for opp in opportunities:
            opp["cooldown_active"] = cache.get(f"cm:rescue_campaign:cooldown:{opp['item_id']}") is not None

        return Response({
            "company_id": str(company.id),
            "total_undecided_buyers": sum(x["undecided_buyers_count"] for x in opportunities),
            "opportunities": opportunities,
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="rescue-opportunities")
    def rescue_opportunities_dash(self, request):
        return self._handle_rescue_opportunities(request)

    @action(detail=False, methods=["get"], url_path="rescue_opportunities")
    def rescue_opportunities(self, request):
        return self._handle_rescue_opportunities(request)

    def _handle_launch_rescue_campaign(self, request):
        company = _get_merchant_company_for_user(request.user)
        if not company:
            return Response({"error": "Compañía no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        copilot = AtlasMerchantCopilot(company=company, user=request.user)
        result = copilot.launch_lead_rescue_campaign(
            item_id=request.data.get("item_id"),
            offer_percentage=int(request.data.get("offer_percentage", 10) or 10),
            duration_hours=int(request.data.get("duration_hours", 24) or 24),
            custom_message=request.data.get("custom_message"),
        )
        status_code = status.HTTP_200_OK if result.get("success") else status.HTTP_400_BAD_REQUEST
        return Response(result, status=status_code)

    @action(detail=False, methods=["post"], url_path="launch-rescue-campaign")
    def launch_rescue_campaign_dash(self, request):
        return self._handle_launch_rescue_campaign(request)

    @action(detail=False, methods=["post"], url_path="launch_rescue_campaign")
    def launch_rescue_campaign(self, request):
        return self._handle_launch_rescue_campaign(request)

    # =========================================================================
    # 6. PILAR 3: RADAR FOMO COMPETITIVO DE LA ZONA Y CANDADO DE FIDELIZACIÓN
    #    GET /api/v1/merchant-growth/zone-fomo-radar/
    # =========================================================================
    def _handle_zone_fomo_radar(self, request):
        company = _get_merchant_company_for_user(request.user)
        if not company:
            return Response({"error": "Compañía no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        copilot = AtlasMerchantCopilot(company=company, user=request.user)
        snapshot = copilot.build_company_intelligence_snapshot()

        return Response({
            "company_id": str(company.id),
            "primary_zone": snapshot["company"]["primary_zone"],
            "health_score": snapshot["health_score"],
            "unmet_demand_radar": snapshot["unmet_demand_radar"],
            "price_benchmarks": snapshot["price_benchmarks"],
            "customer_lock_in": snapshot["customer_lock_in"],
            "rescue_summary": {
                "products_with_abandoned_intent": len(snapshot["rescue_opportunities"]),
                "total_undecided_buyers_7d": sum(
                    r["undecided_buyers_count"] for r in snapshot["rescue_opportunities"]
                ),
            },
            "recommended_actions": snapshot["recommended_actions"],
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="zone-fomo-radar")
    def zone_fomo_radar_dash(self, request):
        return self._handle_zone_fomo_radar(request)

    @action(detail=False, methods=["get"], url_path="zone_fomo_radar")
    def zone_fomo_radar(self, request):
        return self._handle_zone_fomo_radar(request)
