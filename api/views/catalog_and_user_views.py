"""Inventory Items, Products, Push Notifications, Client Contact Methods, Locations, and User Profile."""
from .base import *
from .base import _get_cached_bcv_rate, _extract_and_validate_category_ids

class InventoryItemViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'

    def get_queryset(self):
        return InventoryItem.objects.filter(store__company__owner=self.request.user).order_by('-creation')

    def create(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                store_id = request.data.get('store_id')
                product_id = request.data.get('product_id')
                stock = request.data.get('stock', 0)
                expiration_date_raw = request.data.get('expiration_date')
                custom_price = request.data.get('custom_price')

                store = CompanyStore.objects.select_related('company').get(id=store_id, company__owner=request.user)
                product = Product.objects.select_related('company').get(id=product_id, company__owner=request.user)

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
                    custom_price=custom_price if custom_price else None
                )
                InventoryItemTransaction.objects.create(
                    item=item,
                    units=int(stock),
                    transaction_type=TransactionType.CREATION
                )

                return Response({'success': True, 'data': item.get_json()}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def apply_offer(self, request, pk=None):
        item = self.get_object()
        percentage = request.data.get('percentage')
        valid_until_raw = request.data.get('valid_until')

        try:
            # Procesamos la fecha de la oferta
            parsed_date = parse_flexible_date(valid_until_raw)
            if not parsed_date:
                return Response({'error': 'La fecha de validez es obligatoria'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Seteamos la expiración a las 23:59:59 de ese día con su Timezone
            valid_datetime = timezone.make_aware(datetime.combine(parsed_date.date(), datetime.max.time()))

            InventoryItemOffer.objects.update_or_create(
                product_item=item,
                defaults={'percentage': int(percentage), 'valid_until': valid_datetime}
            )
            
            item.refresh_from_db()
            return Response({'success': True, 'data': item.get_json()}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    @action(detail=True, methods=['post'])
    def restock(self, request, pk=None):
        item = self.get_object()
        units_raw = request.data.get('units')

        try:
            units = int(units_raw)
            if units <= 0:
                return Response({'error': {'error': 'La cantidad a reponer debe ser mayor a cero.'}}, status=status.HTTP_400_BAD_REQUEST)
        except (ValueError, TypeError):
            return Response({'error': {'error': 'Cantidad inválida.'}}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                locked_item = InventoryItem.objects.select_for_update().get(pk=item.pk)
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

            item.refresh_from_db()
            return Response({'success': True, 'data': item.get_json()}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'success': False, 'error': {'error': str(e)}}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def destroy(self, request, *args, **kwargs):
        item = self.get_object()
        try:
            with transaction.atomic():
                # CART-67: Desvincular explícitamente cualquier video historia asociado antes de eliminar el InventoryItem
                CompanyVideoStory.objects.filter(associated_item_id=item.id).update(associated_item=None)
                item_id = item.id
                item.delete()
                transaction.on_commit(lambda: cache.delete(f"cartmaker:struct:item:{item_id}"))
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'navigation'
    
    # Fundamental para recibir tanto el JSON de datos como las imágenes físicas
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    def get_queryset(self):
        # Aseguramos que el usuario solo pueda interactuar con los productos de su compañía
        return Product.objects.select_related('company', 'category__parent_category').filter(company__owner=self.request.user).order_by('-creation')

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
        try:
            company = Company.objects.get(id=company_id, owner=request.user)
        except Company.DoesNotExist:
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

            return Response({'success': True, 'data': created_products_json}, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def create(self, request, *args, **kwargs):
        from api.core.category_schemas import validate_and_normalize_product_dynamic_data

        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response({'success': False, 'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
            
        d = serializer.validated_data
        
        try:
            with transaction.atomic():
                company_id = request.data.get('company_id')
                try:
                    company = Company.objects.get(id=company_id, owner=request.user)
                except Company.DoesNotExist:
                    return Response({'error': 'Compañía no encontrada'}, status=status.HTTP_404_NOT_FOUND)

                category = SubCategory.objects.select_related('parent_category').get(id=d['category_id'])
                raw_discounts = request.data.get('discounts_data')
                if isinstance(raw_discounts, str) and raw_discounts.strip():
                    discounts_data = json.loads(raw_discounts)
                elif isinstance(raw_discounts, (list, dict)):
                    discounts_data = raw_discounts
                else:
                    discounts_data = []

                dynamic_input = {}
                for dyn_key in (
                    'selling_unit', 'unit_label', 'allow_fractional_quantity',
                    'min_order_quantity', 'unit_step', 'attributes', 'variants', 'modifier_groups'
                ):
                    if dyn_key in d:
                        dynamic_input[dyn_key] = d[dyn_key]
                    elif dyn_key in request.data:
                        dynamic_input[dyn_key] = request.data.get(dyn_key)

                dynamic_data = validate_and_normalize_product_dynamic_data(
                    dynamic_input,
                    subcategory_name=category.name,
                    category_name=category.parent_category.name if category.parent_category_id else None,
                    base_price=float(d.get('price', 0.0) or 0.0),
                )

                product = Product.objects.create(
                    company=company,
                    name=d['name'],
                    price=d['price'],
                    description=d['description'],
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
                        # Si no es un archivo nuevo, asumimos que es una URL existente
                        final_images.append(item)
                product.images = final_images
                product.save()

                return Response({'success': True, 'data': product.get_json()}, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def update(self, request, *args, **kwargs):
        from api.core.category_schemas import validate_and_normalize_product_dynamic_data

        product_ref = self.get_object()
        serializer = self.get_serializer(product_ref, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response({'success': False, 'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
            
        d = serializer.validated_data

        try:
            with transaction.atomic():
                # Bloqueamos la fila de Product (of=('self',)) para serializar contra checkouts/cancelaciones de variantes
                product = (
                    Product.objects.select_for_update(of=('self',))
                    .select_related('category__parent_category', 'company')
                    .get(pk=product_ref.pk)
                )
                product.name = d.get('name', product.name)
                product.price = d.get('price', product.price)
                product.description = d.get('description', product.description)
                product.discounts_by_tokens_active = d.get('discounts_by_tokens_active', product.discounts_by_tokens_active)
                
                if 'category_id' in d:
                    product.category = SubCategory.objects.select_related('parent_category').get(id=d['category_id'])

                raw_discounts = request.data.get('discounts_data')
                if raw_discounts is not None:
                    product.discounts_data = json.loads(raw_discounts) if isinstance(raw_discounts, str) else raw_discounts

                dynamic_input = {}
                for dyn_key in (
                    'selling_unit', 'unit_label', 'allow_fractional_quantity',
                    'min_order_quantity', 'unit_step', 'attributes', 'variants', 'modifier_groups'
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

                product.selling_unit = dynamic_data['selling_unit']
                product.unit_label = dynamic_data['unit_label']
                product.allow_fractional_quantity = dynamic_data['allow_fractional_quantity']
                product.min_order_quantity = dynamic_data['min_order_quantity']
                product.unit_step = dynamic_data['unit_step']
                product.attributes = dynamic_data['attributes']
                product.variants = dynamic_data['variants']
                product.modifier_groups = dynamic_data['modifier_groups']

                # ===============================
                # MANEJO DE IMÁGENES CORREGIDO
                # ===============================
                if 'image_order' in request.data:
                    raw_image_order = request.data.get('image_order', '[]')
                    image_order_from_frontend = json.loads(raw_image_order) if isinstance(raw_image_order, str) else (raw_image_order or [])
                    
                    processed_image_order = []

                    # 1. TRADUCIR URLs ABSOLUTAS A RELATIVAS
                    for item in image_order_from_frontend:
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
                                clean_path = item.split('/media/')[-1] if '/media/' in item else item
                                processed_image_order.append(clean_path)
                    
                    # 2. BORRAR IMÁGENES DESCARTADAS
                    for old_url in product.images:
                        if old_url not in processed_image_order:
                            try:
                                storage_manager.delete_file(old_url)
                            except Exception as e:
                                print(f"Error borrando img descartada: {e}")

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

            return Response({'success': True, 'data': product.get_json()}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def destroy(self, request, *args, **kwargs):
        product = self.get_object()
        try:
            with transaction.atomic():
                affected_item_ids = list(
                    InventoryItem.objects.filter(product_id=product.id).values_list('id', flat=True)
                )
                # CART-67: Desvincular explícitamente los videos asociados antes de eliminar el producto o sus InventoryItem
                if affected_item_ids:
                    CompanyVideoStory.objects.filter(associated_item_id__in=affected_item_ids).update(
                        associated_item=None
                    )

                # Primero borramos las imágenes del storage
                for img in product.images:
                    try:
                        storage_manager.delete_file(img)
                    except Exception as e:
                        print(f"Error borrando imagen al eliminar producto: {e}")
                
                # Luego eliminamos el registro de la DB
                product.delete()

                if affected_item_ids:
                    transaction.on_commit(
                        lambda: cache.delete_many([f"cartmaker:struct:item:{iid}" for iid in affected_item_ids])
                    )
            return Response(status=status.HTTP_204_NO_CONTENT)
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def bulk_delete(self, request):
        """
        Recibe una lista de IDs y elimina los productos masivamente.
        CART-67: Antes de eliminar los productos, desvincula explícitamente los videos asociados.
        """
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
                products_to_delete = Product.objects.select_related('company').filter(id__in=product_ids, company__owner=request.user)
                valid_product_ids = [prod.id for prod in products_to_delete]
                affected_item_ids = list(
                    InventoryItem.objects.filter(product_id__in=valid_product_ids).values_list('id', flat=True)
                ) if valid_product_ids else []

                # CART-67: Desvincular explícitamente los videos asociados para que ningún video quede huérfano ni sea eliminado
                if affected_item_ids:
                    CompanyVideoStory.objects.filter(associated_item_id__in=affected_item_ids).update(
                        associated_item=None
                    )
                
                # Borramos las imágenes del storage iterando la consulta evaluada
                for product in products_to_delete:
                    for img in product.images:
                        try:
                            storage_manager.delete_file(img)
                        except Exception as e:
                            print(f"Error borrando imagen en bulk_delete: {e}")
                
                # Eliminación masiva a nivel de BD
                deleted_count, _ = products_to_delete.delete()

                if affected_item_ids:
                    transaction.on_commit(
                        lambda: cache.delete_many([f"cartmaker:struct:item:{iid}" for iid in affected_item_ids])
                    )

            return Response({'success': True, 'deleted_count': deleted_count}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class NotificationViewSet(viewsets.GenericViewSet, mixins.ListModelMixin):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # IMPORTANTE: Ordenamos para que las más nuevas salgan primero
        return Notification.objects.filter(user=self.request.user).order_by('-created_at')

    @action(detail=False, methods=['post'], url_path="mark-section-as-read")
    def mark_section_as_read(self, request):
        section = request.data.get('section')
        if section is None:
            return Response({"detail": "Falta la sección."}, status=status.HTTP_400_BAD_REQUEST)
            
        # 💡 Bulk update: Actualiza todas las no leídas de esta sección a True
        updated_count = self.get_queryset().filter(section=section, is_read=False).update(is_read=True)
        
        return Response({"updated_count": updated_count, "detail": "Sección marcada como leída."}, status=status.HTTP_200_OK)

    # -------------------------------------------------------------------------
    # ENDPOINT 1: Obtener TODAS las notificaciones agrupadas por sección (KISS)
    # -------------------------------------------------------------------------
    @action(detail=False, methods=['get'], url_path="all-grouped")
    def all_grouped(self, request):
        """
        Devuelve todas las notificaciones del usuario en un diccionario:
        { "0": [{...}, {...}], "1": [{...}] }
        Ideal para llenar el Provider en una sola petición al inicio.
        """
        notifications = self.get_queryset()
        
        grouped_data = {}
        for notif in notifications:
            sec_str = str(notif.section)
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
        notification.is_read = True
        notification.save(update_fields=['is_read'])
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

