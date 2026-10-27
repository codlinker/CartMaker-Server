"""Inventory Items, Products, Push Notifications, Client Contact Methods, Locations, and User Profile."""
from .base import *
from .base import _get_cached_bcv_rate, _extract_and_validate_category_ids
from ..core.content_moderation import ContentModerationError, moderate_text_fields, premoderate_uploaded_images
from ..core.workforce import (
    WorkforceError,
    resolve_merchant_actor,
    user_can_manage_store,
    require_owner_for_destructive_action,
    require_employee_permission,
    validate_worker_price_change,
    validate_worker_offer_percentage,
    check_and_record_worker_catalog_mutation,
    snapshot_product,
    snapshot_inventory_item,
    snapshot_products_combo,
    record_employee_audit_log,
)


def _catalog_workforce_error_response(err: WorkforceError) -> Response:
    payload = {
        'success': False,
        'error': err.message,
        'detail': err.message,
    }
    if err.code:
        payload['code'] = err.code
    return Response(payload, status=err.status_code)


def _safe_delete_combo_own_images(combo: ProductsCombo) -> None:
    """
    Elimina del storage únicamente las imágenes personalizadas subidas para `combo.id`
    (`combo_pictures/<combo.id>/...`). Jamás toca las fotos de los `Product` individuales.
    """
    combo_id_str = str(combo.id)
    for img in (combo.custom_images or []):
        if not img or combo_id_str not in str(img):
            continue
        try:
            storage_manager.delete_file(img)
        except Exception as e:
            print(f"Error borrando imagen propia de combo {combo_id_str}: {e}")


def _safe_delete_product_own_images(product: Product) -> None:
    """
    Elimina del storage únicamente las imágenes propias subidas para `product.id`
    (`product_pictures/<product.id>/...`).
    """
    prod_id_str = str(product.id)
    for img in (product.images or []):
        if not img or prod_id_str not in str(img):
            continue
        try:
            storage_manager.delete_file(img)
        except Exception as e:
            print(f"Error borrando imagen propia de producto {prod_id_str}: {e}")


def _resolve_and_validate_combo_items(company: Company, store: CompanyStore, raw_combo_items) -> tuple:
    """
    Valida y resuelve relacionalmente la lista `combo_items` contra los modelos `Product`
    e `InventoryItem` del comercio y sucursal.
    Retorna `(resolved_specs, first_subcategory)` donde cada elemento de `resolved_specs` es:
    `{'product': Product, 'inventory_item': InventoryItem | None, 'quantity': int, 'selected_variant_id': str, 'notes': str, 'position': int}`
    """
    if isinstance(raw_combo_items, str):
        raw_str = raw_combo_items.strip()
        if not raw_str:
            raw_combo_items = []
        else:
            try:
                raw_combo_items = json.loads(raw_str)
            except Exception:
                raise ValueError("El formato JSON de combo_items es inválido.")

    if not isinstance(raw_combo_items, list) or not raw_combo_items:
        raise ValueError("Debes seleccionar los productos que conforman el combo en 'combo_items'.")

    product_ids = set()
    inv_item_ids = set()
    for entry in raw_combo_items:
        if not isinstance(entry, dict):
            continue
        pid = entry.get('product_id') or entry.get('product')
        iid = entry.get('inventory_item_id') or entry.get('item_id')
        if pid:
            product_ids.add(str(pid).strip())
        if iid:
            inv_item_ids.add(str(iid).strip())

    inv_by_id = {}
    if inv_item_ids:
        for inv in InventoryItem.objects.select_related('product__category__parent_category').filter(
            id__in=inv_item_ids, store__company=company
        ):
            inv_by_id[str(inv.id)] = inv
            product_ids.add(str(inv.product_id))

    products_by_id = {}
    if product_ids:
        for prod in Product.objects.select_related('category__parent_category').filter(
            id__in=product_ids, company=company
        ):
            products_by_id[str(prod.id)] = prod

    store_inv_by_product = {
        str(inv.product_id): inv
        for inv in InventoryItem.objects.filter(store=store, product_id__in=list(products_by_id.keys()))
    }

    resolved_specs = []
    first_subcategory = None
    total_units = 0

    for idx, entry in enumerate(raw_combo_items):
        if not isinstance(entry, dict):
            continue
        pid = str(entry.get('product_id') or entry.get('product') or '').strip()
        iid = str(entry.get('inventory_item_id') or entry.get('item_id') or '').strip()

        inv_obj = inv_by_id.get(iid) if iid else None
        prod_obj = products_by_id.get(pid) if pid else (inv_obj.product if inv_obj is not None else None)

        if prod_obj is None:
            raise ValueError("Uno o más productos seleccionados para el combo no existen o no pertenecen a tu comercio.")

        if inv_obj is None or inv_obj.store_id != store.id:
            inv_obj = store_inv_by_product.get(str(prod_obj.id))

        try:
            qty = max(1, int(float(entry.get('quantity') or 1)))
        except (TypeError, ValueError):
            qty = 1

        total_units += qty
        if first_subcategory is None and prod_obj.category is not None:
            first_subcategory = prod_obj.category

        resolved_specs.append({
            'product': prod_obj,
            'inventory_item': inv_obj,
            'quantity': qty,
            'selected_variant_id': str(entry.get('selected_variant_id') or entry.get('variant_id') or '').strip()[:100],
            'notes': str(entry.get('notes') or '').strip()[:255],
            'position': idx,
        })

    if not resolved_specs or total_units < 2:
        raise ValueError("Un combo debe incluir al menos 2 unidades de productos del catálogo (ej. 2 productos distintos o 2 unidades).")

    return resolved_specs, first_subcategory


class InventoryItemViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'

    def get_queryset(self):
        company, _emp, allowed_store_ids = resolve_merchant_actor(self.request)
        if company is None:
            return InventoryItem.objects.none()
        qs = InventoryItem.objects.select_related('store__company', 'product__company', 'product__category').filter(store__company=company)
        if allowed_store_ids is not None:
            qs = qs.filter(store_id__in=allowed_store_ids)
        return qs.order_by('-creation')

    def create(self, request, *args, **kwargs):
        if (
            not request.data.get('product_id')
            and (
                str(request.data.get('is_combo', '')).strip().lower() in ('true', '1', 'yes')
                or 'combo_items' in request.data
            )
        ):
            return self.combos(request)
        try:
            store_id = request.data.get('store_id')
            product_id = request.data.get('product_id')
            stock = request.data.get('stock', 0)
            expiration_date_raw = request.data.get('expiration_date')
            custom_price = request.data.get('custom_price')

            store = CompanyStore.objects.select_related('company').get(id=store_id)
            if not user_can_manage_store(request, store):
                return Response(
                    {'success': False, 'error': 'No tienes permisos operativos sobre esta sucursal.', 'code': 'store_not_allowed'},
                    status=status.HTTP_403_FORBIDDEN,
                )
            _company, emp, _allowed = resolve_merchant_actor(request, target_company_id=store.company_id)
            product = Product.objects.select_related('company').get(id=product_id, company=store.company)

            if emp is not None and custom_price not in (None, ''):
                validate_worker_price_change(emp, product.price, custom_price, target_label=product.name)

            with transaction.atomic():
                # Procesamos la fecha de caducidad usando nuestra función flexible
                exp_datetime = None
                if expiration_date_raw:
                    parsed_date = parse_flexible_date(expiration_date_raw)
                    if parsed_date:
                        # Lo hacemos consciente de la zona horaria y lo seteamos al final del día
                        exp_datetime = timezone.make_aware(datetime.combine(parsed_date.date(), datetime.max.time()))

                item = InventoryItem.objects.create(
                    store=store,
                    product=product,
                    stock=int(stock),
                    expiration_date=exp_datetime,
                    custom_price=custom_price if custom_price not in (None, '') else None
                )
                InventoryItemTransaction.objects.create(
                    item=item,
                    units=int(stock),
                    transaction_type=TransactionType.CREATION
                )
                if emp is not None:
                    record_employee_audit_log(
                        emp,
                        action='inventory_item_created',
                        target_type='inventory_item',
                        target_id=item.id,
                        target_label=f"{product.name} ({store.name})",
                        before_snapshot={},
                        after_snapshot=snapshot_inventory_item(item),
                        is_reversible=True,
                    )

                item_json = item.get_json()
                return Response({'success': True, 'id': str(item.id), 'data': item_json}, status=status.HTTP_201_CREATED)
        except WorkforceError as e:
            return _catalog_workforce_error_response(e)
        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def update(self, request, *args, **kwargs):
        pk = kwargs.get('pk')
        if pk and not InventoryItem.objects.filter(pk=pk).exists() and ProductsCombo.objects.filter(pk=pk).exists():
            return self.combos(request, item_id=str(pk))
        item_ref = self.get_object()
        try:
            _company, emp, _allowed = resolve_merchant_actor(request, target_company_id=item_ref.store.company_id)
            if emp is not None:
                require_employee_permission(emp, 'can_edit_products')

            data = request.data if isinstance(request.data, dict) else {}
            if emp is not None and 'custom_price' in data and data.get('custom_price') not in (None, ''):
                ref_price = item_ref.custom_price if item_ref.custom_price is not None else item_ref.product.price
                validate_worker_price_change(emp, ref_price, data.get('custom_price'), target_label=item_ref.product.name)

            zeroed_or_paused = False
            if emp is not None:
                if 'paused' in data:
                    new_paused = str(data.get('paused')).strip().lower() in ('1', 'true', 'yes', 'si', 'sí') if not isinstance(data.get('paused'), bool) else data.get('paused')
                    if new_paused and not item_ref.paused:
                        zeroed_or_paused = True
                if 'stock' in data and data.get('stock') not in (None, ''):
                    try:
                        if int(data.get('stock')) <= 0 and item_ref.stock > 0:
                            zeroed_or_paused = True
                    except (TypeError, ValueError):
                        pass
                check_and_record_worker_catalog_mutation(
                    emp,
                    f"item:{item_ref.id}",
                    zeroed_stock_or_paused=zeroed_or_paused,
                )

            with transaction.atomic():
                locked_item = (
                    InventoryItem.objects.select_for_update()
                    .select_related('product', 'store')
                    .get(pk=item_ref.pk)
                )
                before_snap = snapshot_inventory_item(locked_item)

                if 'paused' in data:
                    raw_paused = data.get('paused')
                    locked_item.paused = (
                        raw_paused
                        if isinstance(raw_paused, bool)
                        else str(raw_paused).strip().lower() in ('1', 'true', 'yes', 'si', 'sí')
                    )

                if 'custom_price' in data:
                    raw_cp = data.get('custom_price')
                    locked_item.custom_price = float(raw_cp) if raw_cp not in (None, '') else None

                if 'expiration_date' in data:
                    exp_raw = data.get('expiration_date')
                    if exp_raw in (None, ''):
                        locked_item.expiration_date = None
                    else:
                        parsed_date = parse_flexible_date(exp_raw)
                        if parsed_date:
                            locked_item.expiration_date = timezone.make_aware(
                                datetime.combine(parsed_date.date(), datetime.max.time())
                            )

                if 'stock' in data and data.get('stock') not in (None, ''):
                    new_stock = max(0, int(data.get('stock')))
                    delta = new_stock - int(locked_item.stock or 0)
                    locked_item.stock = new_stock
                    if delta != 0:
                        InventoryItemTransaction.objects.create(
                            item=locked_item,
                            units=abs(delta),
                            transaction_type=TransactionType.INCOME if delta > 0 else TransactionType.OUTCOME,
                        )

                locked_item.save()
                after_snap = snapshot_inventory_item(locked_item)

                if emp is not None:
                    record_employee_audit_log(
                        emp,
                        action='inventory_item_updated',
                        target_type='inventory_item',
                        target_id=locked_item.id,
                        target_label=f"{locked_item.product.name} ({locked_item.store.name})",
                        before_snapshot=before_snap,
                        after_snapshot=after_snap,
                        is_reversible=True,
                    )

                item_id = locked_item.id
                transaction.on_commit(lambda: cache.delete(f"cartmaker:struct:item:{item_id}"))

            locked_item.refresh_from_db()
            return Response({'success': True, 'data': locked_item.get_json()}, status=status.HTTP_200_OK)
        except WorkforceError as e:
            return _catalog_workforce_error_response(e)
        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    def toggle_pause(self, request, pk=None):
        if pk and not InventoryItem.objects.filter(pk=pk).exists() and ProductsCombo.objects.filter(pk=pk).exists():
            combo_view = ProductsComboViewSet()
            combo_view.request = request
            combo_view.action = 'toggle_pause'
            combo_view.kwargs = {'pk': pk}
            return combo_view.toggle_pause(request, pk=pk)
        item = self.get_object()
        desired_paused = request.data.get('paused')
        if desired_paused is None:
            desired_paused = not item.paused
        request._full_data = {'paused': desired_paused}
        return self.update(request, pk=pk)

    @action(detail=True, methods=['post'])
    def apply_offer(self, request, pk=None):
        item = self.get_object()
        percentage = request.data.get('percentage')
        valid_until_raw = request.data.get('valid_until')

        try:
            _company, emp, _allowed = resolve_merchant_actor(request, target_company_id=item.store.company_id)
            if emp is not None:
                require_employee_permission(emp, 'can_edit_products')
                validate_worker_offer_percentage(emp, percentage, target_label=item.product.name)
                check_and_record_worker_catalog_mutation(
                    emp,
                    f"item:{item.id}",
                    zeroed_stock_or_paused=False,
                )

            # Procesamos la fecha de la oferta
            parsed_date = parse_flexible_date(valid_until_raw)
            if not parsed_date:
                return Response({'error': 'La fecha de validez es obligatoria'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Seteamos la expiración a las 23:59:59 de ese día con su Timezone
            valid_datetime = timezone.make_aware(datetime.combine(parsed_date.date(), datetime.max.time()))

            with transaction.atomic():
                before_snap = snapshot_inventory_item(item)
                InventoryItemOffer.objects.update_or_create(
                    product_item=item,
                    defaults={'percentage': int(percentage), 'valid_until': valid_datetime}
                )
                item.refresh_from_db()
                after_snap = snapshot_inventory_item(item)
                if emp is not None:
                    record_employee_audit_log(
                        emp,
                        action='offer_applied',
                        target_type='inventory_item',
                        target_id=item.id,
                        target_label=f"{item.product.name} ({item.store.name})",
                        before_snapshot=before_snap,
                        after_snapshot=after_snap,
                        is_reversible=True,
                    )
                item_id = item.id
                transaction.on_commit(lambda: cache.delete(f"cartmaker:struct:item:{item_id}"))

            return Response({'success': True, 'data': item.get_json()}, status=status.HTTP_200_OK)
        except WorkforceError as e:
            return _catalog_workforce_error_response(e)
        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    @action(detail=True, methods=['post'])
    def restock(self, request, pk=None):
        if pk and not InventoryItem.objects.filter(pk=pk).exists() and ProductsCombo.objects.filter(pk=pk).exists():
            combo_view = ProductsComboViewSet()
            combo_view.request = request
            combo_view.action = 'restock'
            combo_view.kwargs = {'pk': pk}
            return combo_view.restock(request, pk=pk)
        item = self.get_object()
        units_raw = request.data.get('units')

        try:
            units = int(units_raw)
            if units <= 0:
                return Response({'error': {'error': 'La cantidad a reponer debe ser mayor a cero.'}}, status=status.HTTP_400_BAD_REQUEST)
        except (ValueError, TypeError):
            return Response({'error': {'error': 'Cantidad inválida.'}}, status=status.HTTP_400_BAD_REQUEST)

        try:
            _company, emp, _allowed = resolve_merchant_actor(request, target_company_id=item.store.company_id)
            with transaction.atomic():
                locked_item = InventoryItem.objects.select_for_update().select_related('product', 'store').get(pk=item.pk)
                before_snap = snapshot_inventory_item(locked_item)
                # 1. Actualizamos el stock de forma atómica
                locked_item.stock += units
                locked_item.creation = timezone.now()
                locked_item.save()

                # 2. Registramos el movimiento en el historial como INGRESO DE STOCK (TransactionType.INCOME = 0)
                InventoryItemTransaction.objects.create(
                    item=locked_item,
                    units=units,
                    transaction_type=TransactionType.INCOME
                )
                after_snap = snapshot_inventory_item(locked_item)
                if emp is not None:
                    record_employee_audit_log(
                        emp,
                        action='inventory_item_restocked',
                        target_type='inventory_item',
                        target_id=locked_item.id,
                        target_label=f"{locked_item.product.name} ({locked_item.store.name})",
                        before_snapshot=before_snap,
                        after_snapshot=after_snap,
                        is_reversible=False,
                    )

            item.refresh_from_db()
            return Response({'success': True, 'data': item.get_json()}, status=status.HTTP_200_OK)
        except WorkforceError as e:
            return _catalog_workforce_error_response(e)
        except Exception as e:
            return Response({'success': False, 'error': {'error': str(e)}}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(
        detail=False,
        methods=['get', 'post', 'put', 'patch', 'delete'],
        url_path='combos',
        parser_classes=[parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser],
    )
    def combos(self, request, item_id=None):
        """
        Alias en `InventoryItemViewSet` que delega al controlador relacional `ProductsComboViewSet`.
        """
        combo_view = ProductsComboViewSet()
        combo_view.request = request
        combo_view.format_kwarg = getattr(self, 'format_kwarg', None)
        target_id = (
            item_id
            or request.data.get('combo_id')
            or request.data.get('inventory_item_id')
            or request.data.get('item_id')
            or (request.data.get('id') if request.method in ('PUT', 'PATCH', 'DELETE') else None)
            or (request.query_params.get('combo_id') if request.method == 'DELETE' else None)
            or (request.query_params.get('item_id') if request.method == 'DELETE' else None)
        )
        if request.method == 'GET':
            if target_id:
                combo_view.action = 'retrieve'
                combo_view.kwargs = {'pk': target_id}
                return combo_view.retrieve(request, pk=target_id)
            combo_view.action = 'list'
            combo_view.kwargs = {}
            return combo_view.list(request)
        if request.method == 'DELETE':
            combo_view.action = 'destroy'
            combo_view.kwargs = {'pk': target_id}
            return combo_view.destroy(request, pk=target_id)
        if target_id or request.method in ('PUT', 'PATCH'):
            combo_view.action = 'partial_update' if request.method == 'PATCH' else 'update'
            combo_view.kwargs = {'pk': target_id}
            return combo_view.update(request, pk=target_id)
        combo_view.action = 'create'
        combo_view.kwargs = {}
        return combo_view.create(request)

    def destroy(self, request, *args, **kwargs):
        try:
            require_owner_for_destructive_action(request, resource_label='lotes de inventario')
        except WorkforceError as e:
            return _catalog_workforce_error_response(e)
        pk = kwargs.get('pk')
        try:
            if pk and not InventoryItem.objects.filter(pk=pk).exists() and ProductsCombo.objects.filter(pk=pk).exists():
                return self.combos(request, item_id=str(pk))
            item = self.get_object()
        except (ValidationError, ValueError, TypeError):
            return Response({'error': 'ID de lote inválido.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            with transaction.atomic():
                # CART-67: Desvincular explícitamente cualquier video historia asociado antes de eliminar el InventoryItem
                CompanyVideoStory.objects.filter(associated_item_id=item.id).update(associated_item=None)
                item_id = str(item.id)
                store_id = item.store_id
                product_id = item.product_id
                affected_combos = list(
                    ProductsCombo.objects.select_related('store__location')
                    .filter(store_id=store_id, combo_items__product_id=product_id)
                    .distinct()
                )
                item.delete()
                for c in affected_combos:
                    if hasattr(c, '_prefetched_objects_cache'):
                        c._prefetched_objects_cache.clear()
                    eff_stock = c.get_effective_stock()
                    c_id_str = str(c.id)
                    c_state = {"stock": eff_stock, "paused": bool(c.paused), "custom_price": None}
                    transaction.on_commit(
                        lambda cid=c_id_str, st=c_state: (
                            cache.set(f"cartmaker:volatile:item:{cid}", st, timeout=86400),
                            cache.set(f"cartmaker:volatile:combo:{cid}", st, timeout=86400),
                            cache.delete(f"cartmaker:struct:item:{cid}"),
                            cache.delete(f"cartmaker:struct:combo:{cid}"),
                        )
                    )
                transaction.on_commit(lambda: cache.delete(f"cartmaker:struct:item:{item_id}"))
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ProductsComboViewSet(viewsets.ModelViewSet):
    """
    Controlador REST dedicado para el modelo relacional `ProductsCombo` y sus `ProductsComboItem`.
    Rutas:
    - GET    /api/v1/products-combos/?store_id=<uuid>
    - POST   /api/v1/products-combos/
    - GET    /api/v1/products-combos/<id>/
    - PUT    /api/v1/products-combos/<id>/
    - PATCH  /api/v1/products-combos/<id>/
    - DELETE /api/v1/products-combos/<id>/
    - POST   /api/v1/products-combos/<id>/toggle_pause/
    - POST   /api/v1/products-combos/<id>/restock/
    """
    serializer_class = ProductsComboSerializer
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    def get_permissions(self):
        if getattr(self, 'action', None) in ('list', 'retrieve'):
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = (
            ProductsCombo.objects.select_related(
                'company',
                'store',
                'store__company',
                'category',
                'category__parent_category',
            )
            .prefetch_related(
                Prefetch(
                    'combo_items',
                    queryset=ProductsComboItem.objects.select_related('product', 'inventory_item').order_by('position', 'id'),
                )
            )
        )

        store_id = self.request.query_params.get('store_id')
        company_id = self.request.query_params.get('company_id')
        category_id = self.request.query_params.get('category_id') or self.request.query_params.get('subcategory_id')
        active_only_raw = str(self.request.query_params.get('active_only', '')).strip().lower()
        active_only = active_only_raw in ('1', 'true', 'yes')

        company, _emp, allowed_store_ids = (None, None, None)
        if getattr(self.request, 'user', None) and self.request.user.is_authenticated:
            try:
                company, _emp, allowed_store_ids = resolve_merchant_actor(self.request)
            except Exception:
                company, _emp, allowed_store_ids = (None, None, None)

        if getattr(self, 'action', None) == 'list':
            if store_id:
                qs = qs.filter(store_id=store_id)
            if company_id:
                qs = qs.filter(store__company_id=company_id)
            if category_id:
                qs = qs.filter(category_id=category_id)

            if not store_id and not company_id:
                if company is not None and not active_only:
                    qs = qs.filter(company=company)
                    if allowed_store_ids is not None:
                        qs = qs.filter(store_id__in=allowed_store_ids)
                else:
                    qs = qs.filter(paused=False, stock__gt=0, store__is_active=True)
            else:
                is_own_catalog = False
                if company is not None and not active_only:
                    if company_id and str(company.id) == str(company_id):
                        is_own_catalog = True
                    elif store_id and CompanyStore.objects.filter(id=store_id, company=company).exists():
                        is_own_catalog = True

                if is_own_catalog:
                    if allowed_store_ids is not None:
                        qs = qs.filter(store_id__in=allowed_store_ids)
                else:
                    qs = qs.filter(paused=False, stock__gt=0, store__is_active=True)

            return qs.order_by('-creation')

        if getattr(self, 'action', None) == 'retrieve':
            if company is not None and not active_only:
                qs = qs.filter(Q(company=company) | Q(paused=False, stock__gt=0, store__is_active=True))
            else:
                qs = qs.filter(paused=False, stock__gt=0, store__is_active=True)
            return qs

        if company is None:
            return ProductsCombo.objects.none()
        qs = qs.filter(company=company)
        if allowed_store_ids is not None:
            qs = qs.filter(store_id__in=allowed_store_ids)
        if store_id:
            qs = qs.filter(store_id=store_id)
        return qs.order_by('-creation')

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        combos_json = [c.get_json() for c in qs]
        return Response(
            {
                'success': True,
                'combos': combos_json,
                'items': combos_json,
                'results': combos_json,
                'data': combos_json,
            },
            status=status.HTTP_200_OK,
        )

    def retrieve(self, request, *args, **kwargs):
        combo = self.get_object()
        combo_json = combo.get_json()
        target_company = combo.store.company if combo.store else combo.company
        is_owner = False
        user_tokens = 0
        if getattr(request, 'user', None) and request.user.is_authenticated:
            if hasattr(request.user, 'company') and target_company:
                is_owner = (target_company.id == request.user.company.id)
            if target_company:
                try:
                    wallet = TokenWallet.objects.only('balance').get(
                        user=request.user,
                        company=target_company,
                    )
                    user_tokens = wallet.balance
                except TokenWallet.DoesNotExist:
                    user_tokens = 0
        combo_json['is_owner'] = is_owner
        combo_json['user_wallet_balance'] = user_tokens
        return Response(
            {
                'success': True,
                'combo': combo_json,
                'item': combo_json,
                'data': combo_json,
            },
            status=status.HTTP_200_OK,
        )

    def _save_combo(self, request, existing_combo: Optional[ProductsCombo] = None):
        try:
            store_id = (
                request.data.get('store_id')
                or (existing_combo.store_id if existing_combo is not None else None)
            )
            if not store_id:
                return Response(
                    {'success': False, 'error': 'store_id es requerido para guardar el combo en la sucursal.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            store = CompanyStore.objects.select_related('company').get(id=store_id)
            if not user_can_manage_store(request, store):
                return Response(
                    {'success': False, 'error': 'No tienes permisos operativos sobre esta sucursal.', 'code': 'store_not_allowed'},
                    status=status.HTTP_403_FORBIDDEN,
                )
            company, emp, _allowed = resolve_merchant_actor(request, target_company_id=store.company_id)
            if emp is not None:
                require_employee_permission(emp, 'can_edit_products')

            raw_combo_items = request.data.get('combo_items')
            if raw_combo_items is None and 'items' in request.data:
                raw_combo_items = request.data.get('items')

            resolved_specs = None
            first_subcat = None
            if raw_combo_items is not None or existing_combo is None:
                try:
                    resolved_specs, first_subcat = _resolve_and_validate_combo_items(
                        company, store, raw_combo_items
                    )
                except ValueError as ve:
                    return Response({'success': False, 'error': str(ve)}, status=status.HTTP_400_BAD_REQUEST)

            raw_price = (
                request.data.get('price')
                if request.data.get('price') not in (None, '')
                else request.data.get('custom_price')
            )
            if raw_price in (None, '') and existing_combo is not None:
                raw_price = existing_combo.price
            try:
                combo_price = Decimal(str(round(float(raw_price), 2)))
                if combo_price <= Decimal('0.00'):
                    raise ValueError()
            except (TypeError, ValueError, InvalidOperation):
                return Response(
                    {'success': False, 'error': 'El precio del combo debe ser mayor a 0.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            raw_stock = request.data.get('stock')
            if raw_stock in (None, '') and existing_combo is not None:
                stock_val = int(existing_combo.stock or 0)
            else:
                try:
                    stock_val = max(0, int(float(raw_stock if raw_stock not in (None, '') else 1)))
                except (TypeError, ValueError):
                    stock_val = 1

            combo_name = str(
                request.data.get('name')
                if request.data.get('name') not in (None, '')
                else (existing_combo.name if existing_combo is not None else 'Combo Especial')
            ).strip()
            if not combo_name:
                return Response(
                    {'success': False, 'error': 'El nombre del combo es obligatorio.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            combo_desc = str(
                request.data.get('description')
                if request.data.get('description') is not None
                else (existing_combo.description if existing_combo is not None else '')
            ).strip()

            raw_deduct = request.data.get('deduct_component_stock')
            if raw_deduct is None and existing_combo is not None:
                deduct_val = bool(existing_combo.deduct_component_stock)
            elif isinstance(raw_deduct, bool):
                deduct_val = raw_deduct
            elif raw_deduct is not None:
                deduct_val = str(raw_deduct).strip().lower() in ('1', 'true', 'yes', 'si', 'sí')
            else:
                deduct_val = False

            raw_paused = request.data.get('paused')
            if raw_paused is None and existing_combo is not None:
                paused_val = bool(existing_combo.paused)
            elif isinstance(raw_paused, bool):
                paused_val = raw_paused
            elif raw_paused is not None:
                paused_val = str(raw_paused).strip().lower() in ('1', 'true', 'yes', 'si', 'sí')
            else:
                paused_val = False

            exp_datetime = existing_combo.expiration_date if existing_combo is not None else None
            if 'expiration_date' in request.data:
                exp_raw = request.data.get('expiration_date')
                if exp_raw in (None, ''):
                    exp_datetime = None
                else:
                    parsed_date = parse_flexible_date(exp_raw)
                    if parsed_date:
                        exp_datetime = timezone.make_aware(
                            datetime.combine(parsed_date.date(), datetime.max.time())
                        )

            category = existing_combo.category if existing_combo is not None else None
            raw_cat_id = request.data.get('category_id')
            if raw_cat_id not in (None, ''):
                try:
                    category = SubCategory.objects.select_related('parent_category').filter(id=int(raw_cat_id)).first()
                except (TypeError, ValueError):
                    pass
            if category is None and first_subcat is not None:
                category = first_subcat

            tokens_active = existing_combo.discounts_by_tokens_active if existing_combo is not None else False
            if 'discounts_by_tokens_active' in request.data:
                raw_tok = request.data.get('discounts_by_tokens_active')
                tokens_active = (
                    raw_tok
                    if isinstance(raw_tok, bool)
                    else str(raw_tok).strip().lower() in ('1', 'true', 'yes', 'si', 'sí')
                )

            discounts_data = existing_combo.discounts_data if existing_combo is not None else {}
            if 'discounts_data' in request.data:
                raw_disc = request.data.get('discounts_data')
                if isinstance(raw_disc, str) and raw_disc.strip():
                    try:
                        discounts_data = json.loads(raw_disc)
                    except Exception:
                        discounts_data = {}
                elif isinstance(raw_disc, (dict, list)):
                    discounts_data = raw_disc

            if emp is not None:
                ref_price = existing_combo.price if existing_combo is not None else None
                validate_worker_price_change(emp, ref_price, combo_price, target_label=combo_name)
                if existing_combo is not None:
                    zeroed_or_paused = (paused_val and not existing_combo.paused) or (stock_val <= 0 and existing_combo.stock > 0)
                    check_and_record_worker_catalog_mutation(
                        emp,
                        f"combo:{existing_combo.id}",
                        zeroed_stock_or_paused=zeroed_or_paused,
                    )

            moderate_text_fields({
                'nombre del combo': combo_name,
                'descripción del combo': combo_desc,
            })
            # Pre-moderación concurrente de las imágenes nuevas ANTES de abrir la transacción
            premoderate_uploaded_images(request.FILES.values())

            # Validamos extensiones ANTES de la transacción (un `return` dentro de atomic haría commit parcial)
            for _uploaded in request.FILES.values():
                _fname = str(getattr(_uploaded, 'name', '') or '')
                _ext = _fname.rsplit('.', 1)[-1].lower() if '.' in _fname else ''
                if _ext not in ('jpg', 'jpeg', 'png', 'webp'):
                    return Response(
                        {'success': False, 'error': f"Formato de imagen no permitido ({_fname})."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            with transaction.atomic():
                created_new = existing_combo is None
                if existing_combo is not None:
                    combo = (
                        ProductsCombo.objects.select_for_update(of=('self',))
                        .select_related('company', 'store')
                        .get(pk=existing_combo.pk)
                    )
                    before_snap = snapshot_products_combo(combo)
                    combo.store = store
                    combo.category = category
                    combo.name = combo_name
                    combo.description = combo_desc
                    combo.price = combo_price
                    combo.stock = stock_val
                    combo.deduct_component_stock = deduct_val
                    combo.paused = paused_val
                    combo.expiration_date = exp_datetime
                    combo.discounts_by_tokens_active = tokens_active
                    combo.discounts_data = discounts_data
                    if stock_val > 0 and combo.sold_out_time is not None:
                        combo.sold_out_time = None
                else:
                    before_snap = {}
                    combo = ProductsCombo.objects.create(
                        company=company,
                        store=store,
                        category=category,
                        name=combo_name,
                        description=combo_desc,
                        price=combo_price,
                        custom_images=[],
                        stock=stock_val,
                        deduct_component_stock=deduct_val,
                        paused=paused_val,
                        expiration_date=exp_datetime,
                        discounts_by_tokens_active=tokens_active,
                        discounts_data=discounts_data,
                    )

                # Imágenes personalizadas opcionales (si no se envían, get_images() usa las de los productos reales)
                if any(k in request.data for k in ('image_order', 'custom_images', 'images')) or request.FILES:
                    raw_img_order = (
                        request.data.get('image_order')
                        if 'image_order' in request.data
                        else (request.data.get('custom_images') if 'custom_images' in request.data else request.data.get('images'))
                    )
                    if isinstance(raw_img_order, str):
                        try:
                            image_order = json.loads(raw_img_order)
                        except Exception:
                            image_order = [raw_img_order] if raw_img_order.strip() else []
                    elif isinstance(raw_img_order, list):
                        image_order = raw_img_order
                    else:
                        image_order = list(request.FILES.keys())

                    custom_imgs = []
                    dtnow_str = timezone.localtime(timezone.now()).strftime('%d-%m-%Y_%H-%M-%S')
                    for idx, img_entry in enumerate(image_order):
                        if not isinstance(img_entry, str) or not img_entry.strip():
                            continue
                        img_entry = img_entry.strip()
                        if img_entry in request.FILES:
                            file = request.FILES[img_entry]
                            extension = file.name.rsplit('.', 1)[-1].lower() if '.' in getattr(file, 'name', '') else ''
                            if extension not in ('jpg', 'jpeg', 'png', 'webp'):
                                return Response(
                                    {'success': False, 'error': f"Formato de imagen no permitido ({file.name})."},
                                    status=status.HTTP_400_BAD_REQUEST,
                                )
                            file_name = f"combo_{combo.id}_{idx}_{dtnow_str}.{extension}"
                            folder = f"combo_pictures/{combo.id}"
                            rel_path = storage_manager.save_file(file, folder, file_name)
                            if rel_path:
                                custom_imgs.append(rel_path)
                        else:
                            norm_img = storage_manager.normalize_path(img_entry)
                            if norm_img and norm_img not in custom_imgs:
                                custom_imgs.append(norm_img)
                    combo.custom_images = custom_imgs

                combo.save()

                if resolved_specs is not None:
                    combo.combo_items.all().delete()
                    ProductsComboItem.objects.bulk_create([
                        ProductsComboItem(
                            combo=combo,
                            product=spec['product'],
                            inventory_item=spec['inventory_item'],
                            quantity=spec['quantity'],
                            selected_variant_id=spec['selected_variant_id'],
                            notes=spec['notes'],
                            position=spec['position'],
                        )
                        for spec in resolved_specs
                    ])

                if emp is not None:
                    record_employee_audit_log(
                        emp,
                        action='products_combo_created' if created_new else 'products_combo_updated',
                        target_type='products_combo',
                        target_id=combo.id,
                        target_label=f"{combo.name} ({store.name})",
                        before_snapshot=before_snap,
                        after_snapshot=snapshot_products_combo(combo),
                        is_reversible=True,
                    )

            combo = self.get_queryset().get(pk=combo.pk)
            combo_json = combo.get_json()
            return Response(
                {
                    'success': True,
                    'id': str(combo.id),
                    'combo_id': str(combo.id),
                    'combo': combo_json,
                    'item': combo_json,
                    'data': combo_json,
                },
                status=status.HTTP_201_CREATED if created_new else status.HTTP_200_OK,
            )
        except CompanyStore.DoesNotExist:
            return Response({'success': False, 'error': 'Sucursal no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        except ContentModerationError as e:
            return e.to_response()
        except WorkforceError as e:
            return _catalog_workforce_error_response(e)
        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def create(self, request, *args, **kwargs):
        return self._save_combo(request, existing_combo=None)

    def update(self, request, *args, **kwargs):
        pk = kwargs.get('pk') or request.data.get('combo_id') or request.data.get('id') or request.data.get('item_id')
        combo = self.get_queryset().filter(pk=pk).first() if pk else None
        if combo is None:
            return Response({'success': False, 'error': 'Combo no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        return self._save_combo(request, existing_combo=combo)

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        try:
            require_owner_for_destructive_action(request, resource_label='combos')
        except WorkforceError as e:
            return _catalog_workforce_error_response(e)
        pk = (
            kwargs.get('pk')
            or request.data.get('combo_id')
            or request.data.get('id')
            or request.data.get('item_id')
            or request.query_params.get('combo_id')
            or request.query_params.get('item_id')
        )
        combo = self.get_queryset().filter(pk=pk).first() if pk else None
        if combo is None:
            return Response({'success': False, 'error': 'Combo no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            with transaction.atomic():
                _safe_delete_combo_own_images(combo)
                combo.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def toggle_pause(self, request, pk=None):
        combo = self.get_object()
        desired_paused = request.data.get('paused')
        if desired_paused is None:
            desired_paused = not combo.paused
        elif not isinstance(desired_paused, bool):
            desired_paused = str(desired_paused).strip().lower() in ('1', 'true', 'yes', 'si', 'sí')

        try:
            _company, emp, _allowed = resolve_merchant_actor(request, target_company_id=combo.company_id)
            if emp is not None:
                require_employee_permission(emp, 'can_edit_products')
                check_and_record_worker_catalog_mutation(
                    emp,
                    f"combo:{combo.id}",
                    zeroed_stock_or_paused=bool(desired_paused and not combo.paused),
                )
            with transaction.atomic():
                locked_combo = ProductsCombo.objects.select_for_update(of=('self',)).select_related('store').get(pk=combo.pk)
                before_snap = snapshot_products_combo(locked_combo)
                locked_combo.paused = bool(desired_paused)
                locked_combo.save(update_fields=['paused'])
                if emp is not None:
                    record_employee_audit_log(
                        emp,
                        action='products_combo_updated',
                        target_type='products_combo',
                        target_id=locked_combo.id,
                        target_label=f"{locked_combo.name} ({locked_combo.store.name})",
                        before_snapshot=before_snap,
                        after_snapshot=snapshot_products_combo(locked_combo),
                        is_reversible=True,
                    )
            combo = self.get_queryset().get(pk=combo.pk)
            return Response({'success': True, 'data': combo.get_json()}, status=status.HTTP_200_OK)
        except WorkforceError as e:
            return _catalog_workforce_error_response(e)
        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def restock(self, request, pk=None):
        combo = self.get_object()
        units_raw = request.data.get('units')
        try:
            units = int(units_raw)
            if units <= 0:
                return Response({'error': {'error': 'La cantidad a reponer debe ser mayor a cero.'}}, status=status.HTTP_400_BAD_REQUEST)
        except (ValueError, TypeError):
            return Response({'error': {'error': 'Cantidad inválida.'}}, status=status.HTTP_400_BAD_REQUEST)

        try:
            _company, emp, _allowed = resolve_merchant_actor(request, target_company_id=combo.company_id)
            with transaction.atomic():
                locked_combo = ProductsCombo.objects.select_for_update(of=('self',)).select_related('store').get(pk=combo.pk)
                before_snap = snapshot_products_combo(locked_combo)
                locked_combo.stock += units
                locked_combo.sold_out_time = None
                locked_combo.save(update_fields=['stock', 'sold_out_time'])
                if emp is not None:
                    record_employee_audit_log(
                        emp,
                        action='products_combo_restocked',
                        target_type='products_combo',
                        target_id=locked_combo.id,
                        target_label=f"{locked_combo.name} ({locked_combo.store.name})",
                        before_snapshot=before_snap,
                        after_snapshot=snapshot_products_combo(locked_combo),
                        is_reversible=False,
                    )
            combo = self.get_queryset().get(pk=combo.pk)
            return Response({'success': True, 'data': combo.get_json()}, status=status.HTTP_200_OK)
        except WorkforceError as e:
            return _catalog_workforce_error_response(e)
        except Exception as e:
            return Response({'success': False, 'error': {'error': str(e)}}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


InventoryItemComboViewSet = ProductsComboViewSet

class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'navigation'
    
    # Fundamental para recibir tanto el JSON de datos como las imágenes físicas
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    def get_queryset(self):
        # Aseguramos que el usuario solo pueda interactuar con los productos de la compañía activa (dueño o asistente)
        company, _emp, _allowed_store_ids = resolve_merchant_actor(self.request)
        if company is None:
            return Product.objects.none()
        qs = Product.objects.select_related('company', 'category__parent_category').filter(company=company)
        if getattr(self, 'action', None) == 'list':
            include_combos = str(self.request.query_params.get('include_combos', '')).strip().lower() in ('true', '1', 'yes')
            if not include_combos:
                qs = qs.exclude(Q(selling_unit='combo') | Q(attributes__is_combo=True))
        return qs.order_by('-creation')

    @action(detail=False, methods=['get'], url_path='schema', permission_classes=[AllowAny])
    def schema(self, request):
        """
        Devuelve el esquema dinámico de creación de producto para la subcategoría o categoría solicitada.
        GET /api/v1/products/schema/?subcategory_id=X
        """
        return CategoryProductSchemaAPI().get(request)
    
    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """
        Recibe un lote de productos y los guarda todos de golpe usando bulk_create.
        Soporta campos dinámicos por categoría (selling_unit, attributes, variants, modifier_groups).
        """
        from api.core.category_schemas import validate_and_normalize_product_dynamic_data

        company_id = request.data.get('company_id')
        company, emp, _allowed_store_ids = resolve_merchant_actor(request, target_company_id=company_id)
        if company is None:
            return Response({'error': 'Compañía no encontrada'}, status=status.HTTP_404_NOT_FOUND)

        raw_products = request.data.get('products_data')
        if not raw_products:
            return Response({'error': 'Faltan los datos de los productos.'}, status=status.HTTP_400_BAD_REQUEST)

        if isinstance(raw_products, list):
            products_list = raw_products
        else:
            try:
                products_list = json.loads(raw_products)
            except json.JSONDecodeError:
                return Response({'error': 'El formato de products_data es inválido.'}, status=status.HTTP_400_BAD_REQUEST)

        created_products_json = []
        dtnow_str = timezone.localtime(timezone.now()).strftime('%d-%m-%Y_%H-%M-%S')

        try:
            if emp is not None:
                for prod_data in products_list:
                    validate_worker_price_change(
                        emp,
                        None,
                        prod_data.get('price'),
                        target_label=prod_data.get('name', 'Producto'),
                    )

            # Pre-moderación concurrente de todas las imágenes del lote ANTES de abrir la transacción
            premoderate_uploaded_images(request.FILES.values())

            with transaction.atomic():
                # 1. Pre-cargar subcategorías involucradas en un solo viaje a la BD
                category_ids = {prod_data['category_id'] for prod_data in products_list if prod_data.get('category_id')}
                categories_map = {
                    cat.id: cat
                    for cat in SubCategory.objects.select_related('parent_category').filter(id__in=category_ids)
                }

                # 2. Preparar las instancias en memoria
                product_instances = []
                
                for prod_data in products_list:
                    cat_id = prod_data.get('category_id')
                    category = categories_map.get(int(cat_id)) if str(cat_id).isdigit() else categories_map.get(cat_id)
                    if not category:
                        raise SubCategory.DoesNotExist(f"Subcategoría {cat_id} no encontrada.")

                    discounts_data = prod_data.get('discounts_data', [])
                    if isinstance(discounts_data, str) and discounts_data.strip():
                        try:
                            discounts_data = json.loads(discounts_data)
                        except Exception:
                            discounts_data = []

                    dynamic_data = validate_and_normalize_product_dynamic_data(
                        prod_data,
                        subcategory_name=category.name,
                        category_name=category.parent_category.name if category.parent_category_id else None,
                        base_price=float(prod_data.get('price', 0.0) or 0.0),
                    )
                    moderate_text_fields({
                        'nombre del producto': prod_data.get('name'),
                        'descripción del producto': prod_data.get('description'),
                        'atributos': dynamic_data.get('attributes'),
                        'variantes': dynamic_data.get('variants'),
                        'extras/modificadores': dynamic_data.get('modifier_groups'),
                    })

                    # Instanciamos sin guardar en BD todavía
                    product = Product(
                        company=company,
                        name=prod_data['name'],
                        price=prod_data['price'],
                        description=prod_data['description'],
                        category=category,
                        discounts_by_tokens_active=prod_data.get('discounts_by_tokens_active', False),
                        discounts_data=discounts_data,
                        images=[],
                        selling_unit=dynamic_data['selling_unit'],
                        unit_label=dynamic_data['unit_label'],
                        allow_fractional_quantity=dynamic_data['allow_fractional_quantity'],
                        min_order_quantity=dynamic_data['min_order_quantity'],
                        unit_step=dynamic_data['unit_step'],
                        attributes=dynamic_data['attributes'],
                        variants=dynamic_data['variants'],
                        modifier_groups=dynamic_data['modifier_groups'],
                    )
                    product_instances.append(product)

                # 3. BULK CREATE REAL (Un solo viaje a la BD)
                created_products = Product.objects.bulk_create(product_instances)

                # 4. Manejo de imágenes (Requiere los IDs que acabamos de generar)
                for prod_index, product in enumerate(created_products):
                    prod_data = products_list[prod_index]
                    image_order = prod_data.get('image_order', [])
                    if isinstance(image_order, str) and image_order.strip():
                        try:
                            image_order = json.loads(image_order)
                        except Exception:
                            image_order = []
                    final_images = []

                    for img_index, item in enumerate(image_order):
                        if item.startswith('new_image_') and item in request.FILES:
                            file = request.FILES[item]
                            extension = file.name.rsplit('.', 1)[-1].lower() if '.' in getattr(file, 'name', '') else ''
                            if extension not in ('jpg', 'jpeg', 'png', 'webp'):
                                return Response({'success': False, 'error': f"Formato de imagen no permitido ({file.name}). Usa JPG, PNG o WEBP."}, status=status.HTTP_400_BAD_REQUEST)
                            if getattr(file, 'size', 0) > 10 * 1024 * 1024:
                                return Response({'success': False, 'error': f"La imagen {file.name} excede el límite de 10 MB."}, status=status.HTTP_400_BAD_REQUEST)
                            file_name = f"prod_{product.id}_{img_index}_{dtnow_str}.{extension}"
                            folder = f"product_pictures/{product.id}"
                            
                            relative_path = storage_manager.save_file(file, folder, file_name)
                            if relative_path:
                                final_images.append(relative_path)
                            else:
                                raise Exception(f"Error guardando la imagen {file.name}.")
                        else:
                            final_images.append(item)

                    product.images = final_images

                # 5. BULK UPDATE de imágenes en un solo viaje a la BD
                if created_products:
                    Product.objects.bulk_update(created_products, ['images'])

                for product in created_products:
                    created_products_json.append(product.get_json())
                    if emp is not None:
                        record_employee_audit_log(
                            emp,
                            action='product_created',
                            target_type='product',
                            target_id=product.id,
                            target_label=product.name,
                            before_snapshot={},
                            after_snapshot=snapshot_product(product),
                            is_reversible=False,
                        )

            return Response({'success': True, 'data': created_products_json}, status=status.HTTP_201_CREATED)

        except ContentModerationError as e:
            return e.to_response()
        except WorkforceError as e:
            return _catalog_workforce_error_response(e)
        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def create(self, request, *args, **kwargs):
        from api.core.category_schemas import validate_and_normalize_product_dynamic_data

        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response({'success': False, 'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
            
        d = serializer.validated_data
        
        try:
            company_id = request.data.get('company_id')
            company, emp, _allowed_store_ids = resolve_merchant_actor(request, target_company_id=company_id)
            if company is None:
                return Response({'error': 'Compañía no encontrada'}, status=status.HTTP_404_NOT_FOUND)

            if emp is not None:
                validate_worker_price_change(emp, None, d.get('price'), target_label=d.get('name', 'Producto'))

            with transaction.atomic():
                dynamic_input = {}
                for dyn_key in (
                    'selling_unit', 'unit_label', 'allow_fractional_quantity',
                    'min_order_quantity', 'unit_step', 'attributes', 'variants', 'modifier_groups',
                ):
                    if dyn_key in d:
                        dynamic_input[dyn_key] = d[dyn_key]
                    elif dyn_key in request.data:
                        dynamic_input[dyn_key] = request.data.get(dyn_key)

                cat_id = d.get('category_id')
                category = None
                if cat_id not in (None, ''):
                    category = SubCategory.objects.select_related('parent_category').get(id=cat_id)
                else:
                    category = (
                        SubCategory.objects.select_related('parent_category')
                        .filter(product__company=company)
                        .first()
                        or SubCategory.objects.select_related('parent_category').first()
                    )

                raw_discounts = request.data.get('discounts_data')
                if isinstance(raw_discounts, str) and raw_discounts.strip():
                    discounts_data = json.loads(raw_discounts)
                elif isinstance(raw_discounts, (list, dict)):
                    discounts_data = raw_discounts
                else:
                    discounts_data = []

                dynamic_data = validate_and_normalize_product_dynamic_data(
                    dynamic_input,
                    subcategory_name=category.name if category else None,
                    category_name=category.parent_category.name if (category and category.parent_category_id) else None,
                    base_price=float(d.get('price', 0.0) or 0.0),
                )
                moderate_text_fields({
                    'nombre del producto': d.get('name'),
                    'descripción del producto': d.get('description'),
                    'atributos': dynamic_data.get('attributes'),
                    'variantes': dynamic_data.get('variants'),
                    'extras/modificadores': dynamic_data.get('modifier_groups'),
                })
                premoderate_uploaded_images(request.FILES.values())

                product = Product.objects.create(
                    company=company,
                    name=d['name'],
                    price=d['price'],
                    description=d.get('description') or '',
                    category=category,
                    discounts_by_tokens_active=d.get('discounts_by_tokens_active', False),
                    discounts_data=discounts_data,
                    images=[], # Lo llenamos en el siguiente paso
                    selling_unit=dynamic_data['selling_unit'],
                    unit_label=dynamic_data['unit_label'],
                    allow_fractional_quantity=dynamic_data['allow_fractional_quantity'],
                    min_order_quantity=dynamic_data['min_order_quantity'],
                    unit_step=dynamic_data['unit_step'],
                    attributes=dynamic_data['attributes'],
                    variants=dynamic_data['variants'],
                    modifier_groups=dynamic_data['modifier_groups'],
                )

                # ===============================
                # MANEJO DE IMÁGENES (Array de Strings)
                # ===============================
                raw_image_order = request.data.get('image_order', '[]')
                image_order = json.loads(raw_image_order) if isinstance(raw_image_order, str) else (raw_image_order or [])
                
                final_images = []
                dtnow_str = timezone.localtime(timezone.now()).strftime('%d-%m-%Y_%H-%M-%S')
                
                for index, item in enumerate(image_order):
                    if not isinstance(item, str) or not item.strip():
                        continue
                    item = item.strip()
                    # Si el string dice "new_image_X", buscamos el archivo y lo subimos
                    if item.startswith('new_image_') and item in request.FILES:
                        file = request.FILES[item]
                        extension = file.name.rsplit('.', 1)[-1].lower() if '.' in getattr(file, 'name', '') else ''
                        if extension not in ('jpg', 'jpeg', 'png', 'webp'):
                            return Response({'success': False, 'error': f"Formato de imagen no permitido ({file.name}). Usa JPG, PNG o WEBP."}, status=status.HTTP_400_BAD_REQUEST)
                        if getattr(file, 'size', 0) > 10 * 1024 * 1024:
                            return Response({'success': False, 'error': f"La imagen {file.name} excede el límite de 10 MB."}, status=status.HTTP_400_BAD_REQUEST)
                        file_name = f"prod_{product.id}_{index}_{dtnow_str}.{extension}"
                        folder = f"product_pictures/{product.id}"
                        
                        relative_path = storage_manager.save_file(file, folder, file_name)
                        if relative_path:
                            final_images.append(relative_path)
                        else:
                            raise Exception(f"Error guardando la imagen {file.name}.")
                    else:
                        # Si no es un archivo nuevo, normalizamos la ruta/URL existente
                        norm_img = storage_manager.normalize_path(item)
                        if norm_img:
                            final_images.append(norm_img)

                product.images = final_images
                product.save()

                if emp is not None:
                    record_employee_audit_log(
                        emp,
                        action='product_created',
                        target_type='product',
                        target_id=product.id,
                        target_label=product.name,
                        before_snapshot={},
                        after_snapshot=snapshot_product(product),
                        is_reversible=False,
                    )

                prod_json = product.get_json()
                return Response({'success': True, 'id': str(product.id), 'data': prod_json}, status=status.HTTP_201_CREATED)

        except ContentModerationError as e:
            return e.to_response()
        except WorkforceError as e:
            return _catalog_workforce_error_response(e)
        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def update(self, request, *args, **kwargs):
        from api.core.category_schemas import validate_and_normalize_product_dynamic_data

        product_ref = self.get_object()
        try:
            company, emp, _allowed = resolve_merchant_actor(request, target_company_id=product_ref.company_id)
            if emp is not None:
                require_employee_permission(emp, 'can_edit_products')
        except WorkforceError as e:
            return _catalog_workforce_error_response(e)

        serializer = self.get_serializer(product_ref, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response({'success': False, 'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
            
        d = serializer.validated_data

        try:
            if emp is not None:
                if 'price' in d or 'price' in request.data:
                    new_price_val = d.get('price', request.data.get('price'))
                    validate_worker_price_change(
                        emp,
                        product_ref.price,
                        new_price_val,
                        target_label=product_ref.name,
                    )
                check_and_record_worker_catalog_mutation(
                    emp,
                    f"product:{product_ref.id}",
                    zeroed_stock_or_paused=False,
                )

            with transaction.atomic():
                # Bloqueamos la fila de Product (of=('self',)) para serializar contra checkouts/cancelaciones de variantes
                product = (
                    Product.objects.select_for_update(of=('self',))
                    .select_related('category__parent_category', 'company')
                    .get(pk=product_ref.pk)
                )
                before_snap = snapshot_product(product)

                product.name = d.get('name', product.name)
                product.price = d.get('price', product.price)
                product.description = d.get('description', product.description)
                product.discounts_by_tokens_active = d.get('discounts_by_tokens_active', product.discounts_by_tokens_active)
                
                if d.get('category_id') not in (None, ''):
                    product.category = SubCategory.objects.select_related('parent_category').get(id=d['category_id'])

                raw_discounts = request.data.get('discounts_data')
                if raw_discounts is not None:
                    product.discounts_data = json.loads(raw_discounts) if isinstance(raw_discounts, str) else raw_discounts

                dynamic_input = {}
                for dyn_key in (
                    'selling_unit', 'unit_label', 'allow_fractional_quantity',
                    'min_order_quantity', 'unit_step', 'attributes', 'variants', 'modifier_groups',
                ):
                    if dyn_key in request.data:
                        dynamic_input[dyn_key] = d[dyn_key] if dyn_key in d else request.data.get(dyn_key)

                cat_obj = product.category
                dynamic_data = validate_and_normalize_product_dynamic_data(
                    dynamic_input,
                    subcategory_name=cat_obj.name if cat_obj else None,
                    category_name=cat_obj.parent_category.name if (cat_obj and cat_obj.parent_category_id) else None,
                    base_price=float(product.price or 0.0),
                    existing_product=product,
                )
                moderate_text_fields({
                    'nombre del producto': product.name,
                    'descripción del producto': product.description,
                    'atributos': dynamic_data.get('attributes'),
                    'variantes': dynamic_data.get('variants'),
                    'extras/modificadores': dynamic_data.get('modifier_groups'),
                })
                premoderate_uploaded_images(request.FILES.values())

                product.selling_unit = dynamic_data['selling_unit']
                product.unit_label = dynamic_data['unit_label']
                product.allow_fractional_quantity = dynamic_data['allow_fractional_quantity']
                product.min_order_quantity = dynamic_data['min_order_quantity']
                product.unit_step = dynamic_data['unit_step']
                product.attributes = dynamic_data['attributes']
                product.variants = dynamic_data['variants']
                product.modifier_groups = dynamic_data['modifier_groups']

                discarded_image_paths = []

                # ===============================
                # MANEJO DE IMÁGENES CORREGIDO
                # ===============================
                if 'image_order' in request.data:
                    raw_image_order = request.data.get('image_order', '[]')
                    image_order_from_frontend = json.loads(raw_image_order) if isinstance(raw_image_order, str) else (raw_image_order or [])
                    
                    processed_image_order = []

                    # 1. TRADUCIR URLs ABSOLUTAS A RELATIVAS
                    for item in image_order_from_frontend:
                        if not isinstance(item, str) or not item.strip():
                            continue
                        item = item.strip()
                        if item.startswith('new_image_'):
                            processed_image_order.append(item)
                        else:
                            found = False
                            for old_relative_url in product.images:
                                if old_relative_url in item:
                                    processed_image_order.append(old_relative_url)
                                    found = True
                                    break
                            
                            if not found:
                                clean_path = storage_manager.normalize_path(item)
                                if clean_path:
                                    processed_image_order.append(clean_path)
                    
                    # 2. IDENTIFICAR IMÁGENES DESCARTADAS PROPIAS (Solo si edita el dueño y la foto pertenece a este product.id).
                    # El borrado físico se DIFIERE hasta que las nuevas imágenes hayan sido subidas, moderadas y
                    # el producto guardado; así un rechazo por moderación no destruye las fotos existentes.
                    if emp is None:
                        prod_id_str = str(product.id)
                        for old_url in product.images:
                            if old_url not in processed_image_order and prod_id_str in str(old_url):
                                discarded_image_paths.append(old_url)

                    final_images = []
                    dtnow_str = timezone.localtime(timezone.now()).strftime('%d-%m-%Y_%H-%M-%S')

                    # 3. CONSTRUIR NUEVO ARRAY (Subiendo nuevas y manteniendo las viejas)
                    for index, item in enumerate(processed_image_order):
                        if item.startswith('new_image_') and item in request.FILES:
                            file = request.FILES[item]
                            extension = file.name.rsplit('.', 1)[-1].lower() if '.' in getattr(file, 'name', '') else ''
                            if extension not in ('jpg', 'jpeg', 'png', 'webp'):
                                return Response({'success': False, 'error': f"Formato de imagen no permitido ({file.name}). Usa JPG, PNG o WEBP."}, status=status.HTTP_400_BAD_REQUEST)
                            if getattr(file, 'size', 0) > 10 * 1024 * 1024:
                                return Response({'success': False, 'error': f"La imagen {file.name} excede el límite de 10 MB."}, status=status.HTTP_400_BAD_REQUEST)
                            file_name = f"prod_{product.id}_{index}_{dtnow_str}.{extension}"
                            folder = f"product_pictures/{product.id}"
                            
                            relative_path = storage_manager.save_file(file, folder, file_name)
                            if relative_path:
                                final_images.append(relative_path)
                            else:
                                raise Exception("Error guardando nueva imagen.")
                        else:
                            final_images.append(item)

                    product.images = final_images

                product.save()
                after_snap = snapshot_product(product)

                # Borrado físico diferido de imágenes descartadas (ya con las nuevas moderadas y persistidas)
                for _old_path in discarded_image_paths:
                    try:
                        storage_manager.delete_file(_old_path)
                    except Exception as e:
                        print(f"Error borrando img descartada: {e}")

                if emp is not None:
                    record_employee_audit_log(
                        emp,
                        action='product_updated',
                        target_type='product',
                        target_id=product.id,
                        target_label=product.name,
                        before_snapshot=before_snap,
                        after_snapshot=after_snap,
                        is_reversible=True,
                    )

                prod_json = product.get_json()

            return Response({'success': True, 'id': str(product.id), 'data': prod_json}, status=status.HTTP_200_OK)

        except ContentModerationError as e:
            return e.to_response()
        except WorkforceError as e:
            return _catalog_workforce_error_response(e)
        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def destroy(self, request, *args, **kwargs):
        try:
            require_owner_for_destructive_action(request, resource_label='productos del catálogo')
        except WorkforceError as e:
            return _catalog_workforce_error_response(e)
        try:
            product = self.get_object()
        except (ValidationError, ValueError, TypeError):
            return Response({'error': 'ID de producto inválido.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            with transaction.atomic():
                affected_item_ids = [
                    str(iid) for iid in InventoryItem.objects.filter(product_id=product.id).values_list('id', flat=True)
                ]
                affected_combos = list(
                    ProductsCombo.objects.select_related('store__location')
                    .filter(combo_items__product_id=product.id)
                    .distinct()
                )
                affected_combo_ids = [str(c.id) for c in affected_combos]

                # CART-67: Desvincular explícitamente los videos asociados antes de eliminar el producto o sus InventoryItem
                if affected_item_ids:
                    CompanyVideoStory.objects.filter(associated_item_id__in=affected_item_ids).update(
                        associated_item=None
                    )

                # Primero borramos únicamente las imágenes propias del producto en el storage
                _safe_delete_product_own_images(product)
                
                # Luego eliminamos el registro de la DB
                product.delete()

                # Si algún combo quedó con menos de 2 unidades tras eliminar este producto componente, lo pausamos
                for combo in affected_combos:
                    if hasattr(combo, '_prefetched_objects_cache'):
                        combo._prefetched_objects_cache.clear()
                    remaining_units = sum(max(1, int(ci.quantity or 1)) for ci in combo.combo_items.all())
                    if remaining_units < 2 and not combo.paused:
                        combo.paused = True
                        combo.save(update_fields=['paused'])

                if affected_item_ids or affected_combo_ids:
                    def _clean_product_delete_caches():
                        keys_to_del = []
                        for iid in affected_item_ids:
                            keys_to_del.append(f"cartmaker:struct:item:{iid}")
                            keys_to_del.append(f"cartmaker:volatile:item:{iid}")
                        for cid in affected_combo_ids:
                            keys_to_del.append(f"cartmaker:struct:item:{cid}")
                            keys_to_del.append(f"cartmaker:struct:combo:{cid}")
                            keys_to_del.append(f"cartmaker:volatile:item:{cid}")
                            keys_to_del.append(f"cartmaker:volatile:combo:{cid}")
                        if keys_to_del:
                            cache.delete_many(keys_to_del)
                    transaction.on_commit(_clean_product_delete_caches)
            return Response(status=status.HTTP_204_NO_CONTENT)
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def bulk_delete(self, request):
        """
        Recibe una lista de IDs y elimina los productos masivamente.
        CART-67: Antes de eliminar los productos, desvincula explícitamente los videos asociados.
        """
        try:
            require_owner_for_destructive_action(request, resource_label='productos del catálogo')
        except WorkforceError as e:
            return _catalog_workforce_error_response(e)

        product_ids = request.data.get('product_ids') or request.data.get('ids') or []
        if isinstance(product_ids, str):
            try:
                product_ids = json.loads(product_ids)
            except Exception:
                product_ids = []
        if not product_ids or not isinstance(product_ids, list):
            return Response({'error': 'Se requiere una lista de IDs de productos válidos.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                # Filtramos para asegurar que pertenezcan al usuario dueño de la compañía
                products_to_delete = list(
                    Product.objects.select_related('company').filter(id__in=product_ids, company__owner=request.user)
                )
                valid_product_ids = [prod.id for prod in products_to_delete]
                affected_item_ids = [
                    str(iid) for iid in InventoryItem.objects.filter(product_id__in=valid_product_ids).values_list('id', flat=True)
                ] if valid_product_ids else []
                affected_combos = list(
                    ProductsCombo.objects.select_related('store__location')
                    .filter(combo_items__product_id__in=valid_product_ids)
                    .distinct()
                ) if valid_product_ids else []
                affected_combo_ids = [str(c.id) for c in affected_combos]

                # CART-67: Desvincular explícitamente los videos asociados para que ningún video quede huérfano ni sea eliminado
                if affected_item_ids:
                    CompanyVideoStory.objects.filter(associated_item_id__in=affected_item_ids).update(
                        associated_item=None
                    )
                
                # Borramos únicamente las imágenes propias de cada producto en el storage
                for product in products_to_delete:
                    _safe_delete_product_own_images(product)
                
                # Eliminación masiva a nivel de BD
                deleted_count, _ = Product.objects.filter(id__in=valid_product_ids).delete() if valid_product_ids else (0, {})

                for combo in affected_combos:
                    if hasattr(combo, '_prefetched_objects_cache'):
                        combo._prefetched_objects_cache.clear()
                    remaining_units = sum(max(1, int(ci.quantity or 1)) for ci in combo.combo_items.all())
                    if remaining_units < 2 and not combo.paused:
                        combo.paused = True
                        combo.save(update_fields=['paused'])

                if affected_item_ids or affected_combo_ids:
                    def _clean_bulk_delete_caches():
                        keys_to_del = []
                        for iid in affected_item_ids:
                            keys_to_del.append(f"cartmaker:struct:item:{iid}")
                            keys_to_del.append(f"cartmaker:volatile:item:{iid}")
                        for cid in affected_combo_ids:
                            keys_to_del.append(f"cartmaker:struct:item:{cid}")
                            keys_to_del.append(f"cartmaker:struct:combo:{cid}")
                            keys_to_del.append(f"cartmaker:volatile:item:{cid}")
                            keys_to_del.append(f"cartmaker:volatile:combo:{cid}")
                        if keys_to_del:
                            cache.delete_many(keys_to_del)
                    transaction.on_commit(_clean_bulk_delete_caches)

            return Response({'success': True, 'deleted_count': deleted_count}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class NotificationViewSet(viewsets.GenericViewSet, mixins.ListModelMixin):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    # Topes de retención y respuesta para proteger rendimiento en backend y app móvil:
    # - Todas las notificaciones NO leídas se entregan siempre (hasta un tope de seguridad de 100).
    # - De las notificaciones YA LEÍDAS (`is_read=True`), solo se conservan y devuelven las últimas 30
    #   globalmente (y máximo 15 leídas por sección en `all-grouped`), con antigüedad máxima de 30 días.
    MAX_READ_NOTIFICATIONS_TOTAL = 30
    MAX_READ_NOTIFICATIONS_PER_SECTION = 15
    MAX_UNREAD_NOTIFICATIONS_SAFETY_CAP = 100
    READ_RETENTION_DAYS = 30

    def get_queryset(self):
        # IMPORTANTE: Ordenamos para que las más nuevas salgan primero.
        # No aplicamos slice aquí porque `mark_section_as_read` y `clear_section` encadenan `.filter()` / `.update()`.
        return Notification.objects.filter(user=self.request.user).order_by('-created_at')

    def _prune_excess_read_notifications(self, user) -> int:
        """
        Poda automáticamente de PostgreSQL las notificaciones ya leídas (`is_read=True`)
        que tengan más de 30 días o que excedan las 30 más recientes del usuario.
        Las notificaciones no leídas (`is_read=False`) nunca se tocan aquí.
        """
        try:
            cutoff = timezone.now() - timedelta(days=self.READ_RETENTION_DAYS)
            deleted_old, _ = Notification.objects.filter(
                user=user,
                is_read=True,
                created_at__lt=cutoff,
            ).delete()

            overflow_ids = list(
                Notification.objects.filter(user=user, is_read=True)
                .order_by('-created_at')
                .values_list('id', flat=True)[self.MAX_READ_NOTIFICATIONS_TOTAL:]
            )
            deleted_overflow = 0
            if overflow_ids:
                deleted_overflow, _ = Notification.objects.filter(id__in=overflow_ids).delete()
            return deleted_old + deleted_overflow
        except Exception:
            return 0

    def _get_capped_notifications(self, user):
        """
        Devuelve la lista combinada de notificaciones activas para el usuario:
        todas las no leídas (hasta `MAX_UNREAD_NOTIFICATIONS_SAFETY_CAP`) +
        únicamente las últimas `MAX_READ_NOTIFICATIONS_TOTAL` leídas, ordenadas de más reciente a más antigua.
        """
        self._prune_excess_read_notifications(user)
        base_qs = self.get_queryset()
        unread_list = list(base_qs.filter(is_read=False)[:self.MAX_UNREAD_NOTIFICATIONS_SAFETY_CAP])
        read_list = list(base_qs.filter(is_read=True)[:self.MAX_READ_NOTIFICATIONS_TOTAL])
        combined = unread_list + read_list
        combined.sort(key=lambda n: n.created_at, reverse=True)
        return combined

    def list(self, request, *args, **kwargs):
        notifications = self._get_capped_notifications(request.user)
        serializer = self.get_serializer(notifications, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path="mark-section-as-read")
    def mark_section_as_read(self, request):
        section = request.data.get('section')
        if section is None:
            return Response({"detail": "Falta la sección."}, status=status.HTTP_400_BAD_REQUEST)
            
        # 💡 Bulk update: Actualiza todas las no leídas de esta sección a True
        updated_count = self.get_queryset().filter(section=section, is_read=False).update(is_read=True)
        if updated_count > 0:
            self._prune_excess_read_notifications(request.user)
        
        return Response({"updated_count": updated_count, "detail": "Sección marcada como leída."}, status=status.HTTP_200_OK)

    # -------------------------------------------------------------------------
    # ENDPOINT 1: Obtener TODAS las notificaciones agrupadas por sección (KISS)
    # -------------------------------------------------------------------------
    @action(detail=False, methods=['get'], url_path="all-grouped")
    def all_grouped(self, request):
        """
        Devuelve las notificaciones relevantes del usuario agrupadas por sección:
        { "0": [{...}, {...}], "1": [{...}] }
        Incluye todas las NO leídas + máximo las últimas 30 leídas (con tope de 15 leídas por sección).
        """
        notifications = self._get_capped_notifications(request.user)
        
        grouped_data = {}
        read_counts_per_section = {}
        for notif in notifications:
            sec_str = str(notif.section)
            if notif.is_read:
                current_sec_read = read_counts_per_section.get(sec_str, 0)
                if current_sec_read >= self.MAX_READ_NOTIFICATIONS_PER_SECTION:
                    continue
                read_counts_per_section[sec_str] = current_sec_read + 1

            if sec_str not in grouped_data:
                grouped_data[sec_str] = []
            
            # Usamos el get_json() que ya tienes implementado
            grouped_data[sec_str].append(notif.get_json())
            
        return Response(grouped_data, status=status.HTTP_200_OK)

    # -------------------------------------------------------------------------
    # ENDPOINT 2: Marcar UNA notificación como leída (Conservar en historial)
    # -------------------------------------------------------------------------
    @action(detail=True, methods=['post'], url_path="mark-as-read")
    def mark_as_read(self, request, pk=None):
        notification = self.get_object()
        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=['is_read'])
            self._prune_excess_read_notifications(request.user)
        return Response({"detail": "Notificación marcada como leída.", "id": notification.id}, status=status.HTTP_200_OK)

    # -------------------------------------------------------------------------
    # ENDPOINT 3: Limpiar TODA una sección
    # -------------------------------------------------------------------------
    @action(detail=False, methods=['post'], url_path="clear-section")
    def clear_section(self, request):
        section = request.data.get('section')
        if section is None:
            return Response({"detail": "Falta la sección."}, status=status.HTTP_400_BAD_REQUEST)
            
        deleted_count, _ = self.get_queryset().filter(section=section).delete()
        return Response({"deleted_count": deleted_count}, status=status.HTTP_200_OK)
    
    # -------------------------------------------------------------------------
    # ENDPOINT 4: Eliminar UNA notificación permanentemente
    # -------------------------------------------------------------------------
    @action(detail=True, methods=['delete'], url_path="delete")
    def delete_notification(self, request, pk=None):
        notification = self.get_object()
        notification.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class ClientContactMethodViewSet(viewsets.ModelViewSet):
    serializer_class = ClientContactMethodSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ClientContactMethod.objects.filter(client=self.request.user)

    def perform_create(self, serializer):
        serializer.save(client=self.request.user)
        
class ClientLocationViewSet(viewsets.ModelViewSet):
    serializer_class = ClientLocationSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ClientLocation.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['patch'], url_path='select-location')
    def select_location(self, request, pk=None):
        try:
            location = self.get_object()
            ClientLocation.objects.filter(
                user=request.user, 
                is_default=True
            ).exclude(pk=location.pk).update(is_default=False)
            location.is_default = True
            location.save()
            serializer = self.get_serializer(location)
            return Response({
                "message": "Ubicación activada correctamente.",
                "data": serializer.data
            }, status=200)
        except Exception as e:
            return Response({"error": f"Error al seleccionar la ubicación: {e}"}, status=500)

class UserViewSet(mixins.RetrieveModelMixin,
                  mixins.UpdateModelMixin,
                  viewsets.GenericViewSet):
    serializer_class = UserSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    permission_classes = [IsAuthenticated]
    parser_classes = (JSONParser, MultiPartParser, FormParser)

    def get_queryset(self):
        return User.objects.filter(id=self.request.user.id, is_active=True)

    def get_object(self):
        return self.request.user
    
    @action(detail=False, methods=['post'], url_path='upload-avatar')
    def upload_avatar(self, request):
        file_obj = request.FILES.get('photo')
        if not file_obj:
            return Response({"error": "No se envió ninguna imagen"}, status=400)
        raw_name = getattr(file_obj, 'name', '') or ''
        extension = raw_name.rsplit('.', 1)[-1].lower() if '.' in raw_name else ''
        if extension not in {'jpg', 'jpeg', 'png', 'webp', 'heic'}:
            return Response(
                {"error": "Formato de imagen no permitido. Usa JPG, PNG, WEBP o HEIC."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if file_obj.size > MAX_IMAGE_SIZE_MB * 1024 * 1024:
            return Response(
                {"error": f"La imagen no puede pesar más de {MAX_IMAGE_SIZE_MB}MB."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = request.user
        file_name = f"avatar_{user.id}_{timezone.localtime(timezone.now()).strftime('%d-%m-%Y_%H-%M-%S')}.{extension}"
        folder = "profiles/avatars"
        relative_path = storage_manager.save_file(file_obj, folder, file_name)
        if relative_path:
            if user.profile_picture:
                storage_manager.delete_file(user.profile_picture)
            user.profile_picture = relative_path
            user.save(update_fields=['profile_picture'])
            cache.delete(f"cartmaker:tenant:{user.id}:profile")
            return Response({
                "message": "Foto actualizada",
                "url": storage_manager.get_url(relative_path)
            })
        return Response({"error": "Error al guardar el archivo"}, status=500)

    @action(detail=False, methods=['get', 'post', 'put', 'patch'], url_path='preferences')
    def preferences(self, request):
        if request.method == 'GET':
            return Response(
                {"preferred_category_ids": request.user.get_preferred_category_ids()},
                status=status.HTTP_200_OK,
            )
        is_valid, clean_ids, error_msg = _extract_and_validate_category_ids(request.data)
        if not is_valid:
            return Response({"error": error_msg}, status=status.HTTP_400_BAD_REQUEST)

        valid_categories = list(Category.objects.filter(id__in=clean_ids).order_by('id'))
        valid_ids = [cat.id for cat in valid_categories]

        with transaction.atomic():
            request.user.preferred_categories.set(valid_categories)
            user_id = request.user.id
            transaction.on_commit(
                lambda: (
                    cache.delete(f"cartmaker:tenant:{user_id}:profile"),
                    cache.delete(f"cartmaker:affinity_profile:v1:{user_id}"),
                )
            )

        return Response(
            {"preferred_category_ids": valid_ids},
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=['post'],
        url_path='suppress-biometrics',
        permission_classes=[IsAuthenticated],
    )
    def suppress_biometrics(self, request):
        """
        CART-60: Derecho de Cancelación y Supresión (Habeas Data - Art. 28 CRBV).
        1. Elimina físicamente cedula_document y selfie_photo del bucket S3 / storage_manager.
        2. Anonimiza biometric_vector = None, cedula_number = None y revoca cedula_verified = False.
        3. Si deactivate_account=True, valida que no existan órdenes activas (como cliente o comerciante) y desactiva la cuenta.
        """
        user = request.user
        raw_confirm = request.data.get("confirm_suppression", False)
        confirm = (
            raw_confirm is True
            or str(raw_confirm).strip().lower() in ("true", "1", "yes")
        )
        if not confirm:
            return Response(
                {"detail": "Debes confirmar expresamente la solicitud de supresión."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        raw_deactivate = request.data.get("deactivate_account", False)
        deactivate_account = (
            raw_deactivate is True
            or str(raw_deactivate).strip().lower() in ("true", "1", "yes")
        )

        # Si solicita baja definitiva de cuenta, verificar que no tenga órdenes activas/en tránsito (cliente o comercio)
        if deactivate_account:
            active_statuses = [OrderStatus.WAITING, OrderStatus.DELIVERY_SENT, 2]
            has_active_orders = Order.objects.filter(
                Q(client=user) | Q(store__company__owner=user),
                status__in=active_statuses,
            ).exists()
            if has_active_orders:
                return Response(
                    {
                        "code": "ACTIVE_ORDERS_BLOCK",
                        "detail": "Tienes órdenes activas en curso. Finalízalas o cancélalas antes de dar de baja definitiva tu cuenta.",
                    },
                    status=status.HTTP_409_CONFLICT,
                )

        now = timezone.now()
        with transaction.atomic():
            locked_user = User.objects.select_for_update().get(pk=user.pk)
            old_cedula = locked_user.cedula_number

            # 1. Borrado físico en AWS S3 / storage_manager de las imágenes de cédula y selfie de auditoría
            paths_to_delete = set()
            if locked_user.cedula_document:
                paths_to_delete.add(locked_user.cedula_document)
            for ext in ("jpg", "jpeg", "png", "webp", "heic"):
                paths_to_delete.add(f"identity_verifications/cedula_{locked_user.id}.{ext}")
                paths_to_delete.add(f"identity_verifications/selfie_{locked_user.id}.{ext}")

            for rel_path in paths_to_delete:
                try:
                    storage_manager.delete_file(rel_path)
                except Exception:
                    pass

            # 2. Borrado / anonimización del vector biométrico facial (512-D) y estado de verificación
            locked_user.cedula_document = None
            locked_user.biometric_vector = None
            locked_user.cedula_verified = False
            locked_user.cedula_number = None
            locked_user.nacionality = None
            locked_user.biometric_suppressed_at = now

            # 3. Baja definitiva opcional
            if deactivate_account:
                locked_user.is_active = False
                DeviceToken.objects.filter(user=locked_user).delete()
                CompanyStore.objects.filter(company__owner=locked_user).update(is_active=False)
                InventoryItem.objects.filter(store__company__owner=locked_user).update(paused=True)

            locked_user.save()
            uid = locked_user.id

            def _clear_user_caches():
                cache.delete(f"cartmaker:tenant:{uid}:profile")
                cache.delete(f"cartmaker:tenant:{uid}:subscriptions")
                cache.delete(f"cartmaker:tenant:{uid}:company")
                if old_cedula:
                    digits = "".join(ch for ch in str(old_cedula) if ch.isdigit())
                    for nac in ("V", "E"):
                        cache.delete(f"cm:cne_cedula:{nac}:{digits}")

            transaction.on_commit(_clear_user_caches)

        return Response(
            {
                "status": "suppressed",
                "biometric_vector_cleared": True,
                "s3_identity_files_deleted": True,
                "account_deactivated": deactivate_account,
                "suppressed_at": now.isoformat(),
            },
            status=status.HTTP_200_OK,
        )

