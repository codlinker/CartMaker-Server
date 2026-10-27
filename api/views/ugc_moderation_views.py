"""
Endpoints de Moderación de Contenido Generado por Usuarios (UGC),
Denuncias en 1 Toque ("Denunciar contenido/producto/video/comercio/comentario")
y Bloqueo de Comercios/Usuarios ("Bloquear comercio/usuario") para cumplimiento
con Google Play User-Generated Content Policy.
"""
from .base import *

SEVERE_REPORT_REASONS = {
    ContentReport.ReportReason.NUDITY_OR_SEXUAL,
    ContentReport.ReportReason.ADULT_TOYS,
    ContentReport.ReportReason.TOBACCO_OR_VAPE,
    ContentReport.ReportReason.DRUGS_OR_NARCOTICS,
    ContentReport.ReportReason.WEAPONS_OR_VIOLENCE,
}

AUTO_QUARANTINE_SEVERE_THRESHOLD = 3


def _normalize_report_reason(raw_reason: str) -> str:
    if not raw_reason:
        return ContentReport.ReportReason.OTHER
    upper = str(raw_reason).strip().upper()
    valid_codes = {choice[0] for choice in ContentReport.ReportReason.choices}
    if upper in valid_codes:
        return upper

    lowered = upper.lower()
    # Mapeo directo 1:1 de los 5 reason_code oficiales de CartMaker-App (Flutter)
    flutter_map = {
        'sexual_or_nudity': ContentReport.ReportReason.NUDITY_OR_SEXUAL,
        'tobacco_or_vapes': ContentReport.ReportReason.TOBACCO_OR_VAPE,
        'illegal_or_weapons': ContentReport.ReportReason.WEAPONS_OR_VIOLENCE,
        'scam_or_fake': ContentReport.ReportReason.SCAM_OR_FAKE,
        'harassment_or_hate': ContentReport.ReportReason.HARASSMENT_OR_HATE,
    }
    if lowered in flutter_map:
        return flutter_map[lowered]

    if any(k in lowered for k in ('nud', 'desnud', 'sex', 'porno', 'obsc', 'erot')):
        return ContentReport.ReportReason.NUDITY_OR_SEXUAL
    if any(k in lowered for k in ('toy', 'juguete', 'consolador', 'dildo', 'adult')):
        return ContentReport.ReportReason.ADULT_TOYS
    if any(k in lowered for k in ('tabac', 'tobac', 'cigarr', 'vape', 'nicot', 'hookah')):
        return ContentReport.ReportReason.TOBACCO_OR_VAPE
    if any(k in lowered for k in ('drog', 'drug', 'narc', 'estupef', 'marihuan', 'cocain', 'fentanil')):
        return ContentReport.ReportReason.DRUGS_OR_NARCOTICS
    if any(k in lowered for k in ('arm', 'weap', 'violenc', 'explos', 'muni', 'illegal', 'ilegal')):
        return ContentReport.ReportReason.WEAPONS_OR_VIOLENCE
    if any(k in lowered for k in ('estaf', 'scam', 'fraud', 'fake', 'fals')):
        return ContentReport.ReportReason.SCAM_OR_FAKE
    if any(k in lowered for k in ('acos', 'harass', 'odio', 'hate', 'insult', 'ofens')):
        return ContentReport.ReportReason.HARASSMENT_OR_HATE
    return ContentReport.ReportReason.OTHER


def _normalize_target_type(raw_type: str, data: dict) -> str:
    cleaned = str(raw_type or '').strip().lower()
    mapping = {
        'product': ContentReport.TargetType.PRODUCT,
        'inventory_item': ContentReport.TargetType.PRODUCT,
        'item': ContentReport.TargetType.PRODUCT,
        'combo': ContentReport.TargetType.COMBO,
        'products_combo': ContentReport.TargetType.COMBO,
        'video': ContentReport.TargetType.VIDEO,
        'story': ContentReport.TargetType.VIDEO,
        'video_story': ContentReport.TargetType.VIDEO,
        'company': ContentReport.TargetType.COMPANY,
        'merchant': ContentReport.TargetType.COMPANY,
        'commerce': ContentReport.TargetType.COMPANY,
        'store': ContentReport.TargetType.STORE,
        'branch': ContentReport.TargetType.STORE,
        'comment': ContentReport.TargetType.COMMENT,
        'question': ContentReport.TargetType.COMMENT,
        'user': ContentReport.TargetType.USER,
    }
    if cleaned in mapping:
        return mapping[cleaned]
    if data.get('video_id') or data.get('story_id'):
        return ContentReport.TargetType.VIDEO
    if data.get('combo_id'):
        return ContentReport.TargetType.COMBO
    if data.get('product_id') or data.get('item_id') or data.get('inventory_item_id'):
        return ContentReport.TargetType.PRODUCT
    if data.get('comment_id') or data.get('question_id'):
        return ContentReport.TargetType.COMMENT
    if data.get('store_id'):
        return ContentReport.TargetType.STORE
    if data.get('company_id') or data.get('merchant_id'):
        return ContentReport.TargetType.COMPANY
    if data.get('user_id'):
        return ContentReport.TargetType.USER
    return ContentReport.TargetType.PRODUCT


def _extract_target_id(data: dict) -> str:
    for key in (
        'target_id',
        'id',
        'item_id',
        'inventory_item_id',
        'product_id',
        'combo_id',
        'video_id',
        'story_id',
        'company_id',
        'merchant_id',
        'store_id',
        'comment_id',
        'question_id',
        'user_id',
    ):
        val = data.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    return ''


def _resolve_company_from_target(target_type: str, target_id: str, explicit_company_id: str = ''):
    """
    Intenta resolver la Company propietaria del recurso denunciado/bloqueado.
    """
    if explicit_company_id:
        try:
            comp = Company.objects.filter(id=str(explicit_company_id).strip()).first()
            if comp:
                return comp
        except (ValidationError, ValueError, TypeError):
            pass
    if not target_id:
        return None
    try:
        if target_type == ContentReport.TargetType.COMPANY:
            return Company.objects.filter(id=target_id).first()
        if target_type == ContentReport.TargetType.STORE:
            store = Store.objects.select_related('company').filter(id=target_id).first()
            return store.company if store else None
        if target_type in (ContentReport.TargetType.PRODUCT, ContentReport.TargetType.COMBO):
            item = InventoryItem.objects.select_related('store__company').filter(id=target_id).first()
            if item and item.store:
                return item.store.company
            prod = Product.objects.select_related('company').filter(id=target_id).first()
            if prod:
                return prod.company
            combo = ProductsCombo.objects.select_related('company', 'store__company').filter(id=target_id).first()
            if combo:
                return combo.company or (combo.store.company if combo.store else None)
        if target_type == ContentReport.TargetType.VIDEO:
            story = CompanyVideoStory.objects.select_related('company').filter(id=target_id).first()
            return story.company if story else None
        if target_type == ContentReport.TargetType.COMMENT:
            comment = UniversalComment.objects.filter(id=target_id).first()
            if comment and comment.content_object is not None:
                obj = comment.content_object
                if hasattr(obj, 'company') and obj.company:
                    return obj.company
                if hasattr(obj, 'store') and obj.store and obj.store.company:
                    return obj.store.company
    except (ValidationError, ValueError, TypeError):
        return None
    return None


def _evaluate_auto_quarantine(target_type: str, target_id: str) -> bool:
    """
    Si un producto, combo o video acumula >= 3 denuncias distintas por motivos graves
    (desnudez, juguetes sexuales, tabaco/vapes, drogas o armas/violencia),
    se pone en cuarentena preventiva automática (paused=True o expiración inmediata).
    """
    severe_count = (
        ContentReport.objects.filter(
            target_type=target_type,
            target_id=str(target_id),
            reason__in=SEVERE_REPORT_REASONS,
        )
        .values('reporter_id')
        .distinct()
        .count()
    )
    if severe_count < AUTO_QUARANTINE_SEVERE_THRESHOLD:
        return False

    quarantined = False
    try:
        if target_type in (ContentReport.TargetType.PRODUCT, ContentReport.TargetType.COMBO):
            updated_items = InventoryItem.objects.filter(id=target_id, paused=False).update(paused=True)
            updated_prod_items = InventoryItem.objects.filter(product_id=target_id, paused=False).update(paused=True)
            updated_combos = ProductsCombo.objects.filter(id=target_id, paused=False).update(paused=True)
            quarantined = bool(updated_items or updated_prod_items or updated_combos)
            try:
                cache.delete(f"cartmaker:struct:item:{target_id}")
            except Exception:
                pass
        elif target_type == ContentReport.TargetType.VIDEO:
            now = timezone.now()
            updated_stories = CompanyVideoStory.objects.filter(
                id=target_id,
                expires_at__gt=now,
            ).update(expires_at=now)
            quarantined = bool(updated_stories)

        if quarantined:
            ContentReport.objects.filter(
                target_type=target_type,
                target_id=str(target_id),
                status=ContentReport.ReportStatus.PENDING,
            ).update(status=ContentReport.ReportStatus.QUARANTINED)
    except Exception as exc:
        logger.warning(f"No se pudo aplicar cuarentena preventiva a {target_type}:{target_id}: {exc}")
    return quarantined


class ReportContentAPIView(APIView):
    """
    POST /api/v1/moderation/report/
    GET  /api/v1/moderation/report/ -> Retorna el catálogo oficial de motivos de denuncia.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'navigation'

    def get(self, request):
        reasons = [
            {"code": code, "label": label}
            for code, label in ContentReport.ReportReason.choices
        ]
        target_types = [
            {"code": code, "label": label}
            for code, label in ContentReport.TargetType.choices
        ]
        return Response(
            {
                "success": True,
                "reasons": reasons,
                "target_types": target_types,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        data = request.data if isinstance(request.data, dict) else request.data.dict()
        target_type = _normalize_target_type(data.get('target_type') or data.get('type'), data)
        target_id = _extract_target_id(data)
        if not target_id:
            return Response(
                {
                    "success": False,
                    "error": "Debes indicar el identificador del contenido a denunciar (target_id).",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        raw_reason = (
            data.get('reason_code')
            or data.get('reason')
            or data.get('category')
            or data.get('motive')
            or data.get('reason_label')
            or ''
        )
        reason = _normalize_report_reason(raw_reason)
        raw_details = str(data.get('details') or data.get('description') or data.get('comment') or '').strip()
        target_title = str(data.get('target_title') or '').strip()
        reason_label = str(data.get('reason_label') or '').strip()
        company_name = str(data.get('company_name') or '').strip()
        meta_parts = []
        if target_title:
            meta_parts.append(f"Título: {target_title}")
        if company_name:
            meta_parts.append(f"Comercio: {company_name}")
        if reason_label:
            meta_parts.append(f"Motivo: {reason_label}")
        if raw_details:
            meta_parts.append(f"Detalles: {raw_details}")
        description = " | ".join(meta_parts)[:1000] if meta_parts else raw_details[:1000]

        also_block_raw = data.get('block_merchant', data.get('also_block', False))
        also_block = bool(also_block_raw) and str(also_block_raw).strip().lower() not in ('false', '0', 'no', '')
        explicit_company_id = str(data.get('company_id') or '').strip()

        with transaction.atomic():
            report, created = ContentReport.objects.update_or_create(
                reporter=request.user,
                target_type=target_type,
                target_id=target_id,
                defaults={
                    'reason': reason,
                    'description': description,
                },
            )
            quarantined = _evaluate_auto_quarantine(target_type, target_id)

            blocked_company_id = None
            if also_block:
                company = _resolve_company_from_target(
                    target_type,
                    target_id,
                    explicit_company_id=explicit_company_id,
                )
                if company and company.owner_id != request.user.id:
                    UserBlock.objects.get_or_create(
                        blocker=request.user,
                        target_type=UserBlock.BlockTargetType.COMPANY,
                        blocked_company=company,
                        defaults={'reason': (reason_label or report.get_reason_display())[:160]},
                    )
                    UserBlock.invalidate_user_cache(request.user.id)
                    blocked_company_id = str(company.id)

        return Response(
            {
                "success": True,
                "created": created,
                "quarantined": quarantined,
                "blocked_company_id": blocked_company_id,
                "message": "Gracias por tu reporte. Nuestro equipo y sistema de moderación revisarán este contenido de inmediato.",
                "report": report.get_json(),
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class BlockTargetAPIView(APIView):
    """
    POST   /api/v1/moderation/block/ -> Bloquea un comercio o usuario en 1 toque.
    DELETE /api/v1/moderation/block/ -> Desbloquea un comercio o usuario.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'navigation'

    def post(self, request):
        data = request.data if isinstance(request.data, dict) else request.data.dict()
        raw_type = str(data.get('target_type') or data.get('type') or '').strip().lower()
        target_id = _extract_target_id(data)
        reason = str(data.get('reason') or '').strip()[:160]

        if not target_id:
            return Response(
                {
                    "success": False,
                    "error": "Debes indicar el comercio o usuario que deseas bloquear (target_id / company_id / user_id).",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if raw_type == 'user' or ('user_id' in data and 'company_id' not in data):
            try:
                target_user = User.objects.filter(id=target_id, is_active=True).first()
            except (ValidationError, ValueError, TypeError):
                target_user = None
            if not target_user:
                return Response({"success": False, "error": "El usuario indicado no existe."}, status=status.HTTP_404_NOT_FOUND)
            if target_user.id == request.user.id:
                return Response({"success": False, "error": "No puedes bloquearte a ti mismo."}, status=status.HTTP_400_BAD_REQUEST)

            block_obj, created = UserBlock.objects.get_or_create(
                blocker=request.user,
                target_type=UserBlock.BlockTargetType.USER,
                blocked_user=target_user,
                defaults={'reason': reason},
            )
            UserBlock.invalidate_user_cache(request.user.id)
            return Response(
                {
                    "success": True,
                    "created": created,
                    "message": "Usuario bloqueado. Ya no verás su contenido ni interacciones.",
                    "block": block_obj.get_json(),
                    "blocked_company_ids": UserBlock.get_blocked_company_ids(request.user.id),
                    "blocked_user_ids": UserBlock.get_blocked_user_ids(request.user.id),
                },
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
            )

        # Por defecto: bloquear comercio (directamente por company_id o resolviendo desde producto/video/sucursal)
        norm_type = _normalize_target_type(raw_type or 'company', data)
        company = _resolve_company_from_target(
            norm_type,
            target_id,
            explicit_company_id=str(data.get('company_id') or '').strip(),
        )
        if not company:
            try:
                company = Company.objects.filter(id=target_id).first()
            except (ValidationError, ValueError, TypeError):
                company = None
        if not company:
            return Response(
                {"success": False, "error": "El comercio indicado no existe."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if company.owner_id == request.user.id:
            return Response(
                {"success": False, "error": "No puedes bloquear tu propio comercio."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        block_obj, created = UserBlock.objects.get_or_create(
            blocker=request.user,
            target_type=UserBlock.BlockTargetType.COMPANY,
            blocked_company=company,
            defaults={'reason': reason},
        )
        UserBlock.invalidate_user_cache(request.user.id)
        return Response(
            {
                "success": True,
                "created": created,
                "message": f"Has bloqueado a {company.name}. Sus productos y videos ya no aparecerán en tu cuenta.",
                "block": block_obj.get_json(),
                "blocked_company_ids": UserBlock.get_blocked_company_ids(request.user.id),
                "blocked_user_ids": UserBlock.get_blocked_user_ids(request.user.id),
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def delete(self, request):
        return _perform_unblock(request)


def _perform_unblock(request) -> Response:
    data = {}
    if isinstance(request.data, dict):
        data.update(request.data)
    elif hasattr(request.data, 'dict'):
        data.update(request.data.dict())
    if hasattr(request, 'query_params'):
        for k, v in request.query_params.items():
            data.setdefault(k, v)

    target_id = _extract_target_id(data)
    if not target_id:
        return Response(
            {"success": False, "error": "Debes indicar el ID del comercio, usuario o bloqueo a desbloquear."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    qs = UserBlock.objects.filter(blocker=request.user).filter(
        Q(id=target_id) | Q(blocked_company_id=target_id) | Q(blocked_user_id=target_id)
    )
    deleted_count, _ = qs.delete()
    UserBlock.invalidate_user_cache(request.user.id)
    return Response(
        {
            "success": True,
            "unblocked": deleted_count > 0,
            "message": "Bloqueo eliminado correctamente.",
            "blocked_company_ids": UserBlock.get_blocked_company_ids(request.user.id),
            "blocked_user_ids": UserBlock.get_blocked_user_ids(request.user.id),
        },
        status=status.HTTP_200_OK,
    )


class UnblockTargetAPIView(APIView):
    """
    POST /api/v1/moderation/unblock/
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'navigation'

    def post(self, request):
        return _perform_unblock(request)


class BlockedTargetsListAPIView(APIView):
    """
    GET /api/v1/moderation/blocked/
    Retorna la lista de comercios y usuarios bloqueados por el usuario autenticado.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'navigation'

    def get(self, request):
        blocks = (
            UserBlock.objects.filter(blocker=request.user)
            .select_related('blocked_company', 'blocked_user')
            .order_by('-created_at')
        )
        results = [b.get_json() for b in blocks]
        return Response(
            {
                "success": True,
                "blocked_company_ids": UserBlock.get_blocked_company_ids(request.user.id),
                "blocked_user_ids": UserBlock.get_blocked_user_ids(request.user.id),
                "results": results,
                "data": results,
            },
            status=status.HTTP_200_OK,
        )
