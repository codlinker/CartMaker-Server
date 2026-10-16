"""Company, Store, Subscriptions, KYB RIF Validation, Merchant Catalog, and Public Store Profile views."""
from .base import *
from .base import _get_cached_bcv_rate, _extract_and_validate_category_ids

######################################################
###################### ACTIONS #######################
######################################################

class CompanyMainBranchViewSet(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Devuelve todas las sucursales de la compañía del usuario.
        Incluye la foto de la sucursal y la lista de productos únicos 
        publicados en ella, con el conteo de sus lotes (InventoryItems) activos.
        """
        print("LLEGO:")
        user = request.user
        
        # 1. Optimizamos la consulta con Prefetch
        # Buscamos solo los InventoryItems activos (paused=False, stock>0)
        # y traemos el Product asociado de una vez para evitar consultas N+1
        active_inventory_prefetch = Prefetch(
            'product_items',
            queryset=InventoryItem.objects.filter(
                paused=False, 
                stock__gt=0
            ).select_related('product'),
            to_attr='active_items'
        )

        # 2. Obtenemos las tiendas que le pertenecen a la compañía de este usuario
        stores = CompanyStore.objects.filter(
            company__owner=user
        ).prefetch_related(active_inventory_prefetch)

        data = []

        # 3. Procesamos y agrupamos los datos
        for store in stores:
            product_map = {}
            
            # Iteramos sobre los ítems de inventario activos que ya trajimos a memoria
            for item in store.active_items:
                prod_id = str(item.product.id)
                
                if prod_id not in product_map:
                    # Extraemos la primera imagen del array de imágenes del producto (si existe)
                    prod_img = None
                    if item.product.images and len(item.product.images) > 0:
                        prod_img = storage_manager.get_url(item.product.images[0])
                        
                    # Inicializamos la estructura del Producto
                    product_map[prod_id] = {
                        "id": prod_id,
                        "name": item.product.name,
                        "image": prod_img,
                        "active_inventory_count": 0
                    }
                
                # Sumamos 1 al contador de items (lotes) activos para este producto
                product_map[prod_id]["active_inventory_count"] += 1

            # Formateamos la foto de la sucursal
            store_image = None
            if store.store_img_url:
                store_image = storage_manager.get_url(store.store_img_url)

            # Agregamos la sucursal a la respuesta
            data.append({
                "id": str(store.id),
                "name": store.name,
                "image": store_image,
                "is_main_store": store.is_main_store,
                "products": list(product_map.values()) # Convertimos el dict agrupado a lista
            })

        return Response({'data': data}, status=status.HTTP_200_OK)

    def post(self, request):
        """
        Recibe el id de una sucursal y la establece como la principal (is_main_store=True),
        apagando el flag en todas las demás sucursales de la misma compañía.
        """
        store_id = request.data.get('store_id')
        
        if not store_id:
            return Response({'error': 'El parámetro store_id es requerido.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Buscamos la tienda y validamos estrictamente que la compañía dueña de 
            # esta tienda le pertenezca al usuario que hace la petición
            store = CompanyStore.objects.select_related('company').get(
                id=store_id, 
                company__owner=request.user
            )
            company = store.company

            # Transacción atómica para evitar inconsistencias si algo falla en el medio
            with transaction.atomic():
                # Apagamos todas las sucursales de esta compañía
                CompanyStore.objects.filter(company=company).update(is_main_store=False)
                
                # Encendemos solo la seleccionada
                store.is_main_store = True
                store.save(update_fields=['is_main_store'])

            return Response({
                'success': True, 
                'message': f'La sucursal "{store.name}" ha sido establecida como la principal.'
            }, status=status.HTTP_200_OK)

        except CompanyStore.DoesNotExist:
            return Response({
                'error': 'La sucursal no existe o no tienes permisos para modificarla.'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'error': f'Error interno: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GetCompanyProducts(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    permission_classes = [IsAuthenticated]

    def get(self, request, company_id=None):
        """
        Devuelve el catálogo maestro de productos paginado + las categorías de la empresa.
        """
        try:
            company = Company.objects.get(id=company_id)
            if company.owner.id != request.user.id:
                return Response({'error': 'Usted no es el propietario de la compania.'}, status=status.HTTP_406_NOT_ACCEPTABLE)
            
            # Categorías globales de la empresa (siempre se devuelven todas)
            company_categories = SubCategory.objects.filter(
                product__company=company
            ).distinct().values('id', 'name')
            
            # 💡 NUEVO: Recibimos el parámetro del frontend
            category_id = request.GET.get('category_id')
            page = request.GET.get('page', 1)
            
            # 💡 NUEVO: Filtramos el queryset si viene el category_id
            products_query = company.products.select_related(
                'category', 'category__parent_category', 'company'
            ).all()
            if category_id:
                products_query = products_query.filter(category_id=category_id)
                
            products_query = products_query.order_by('-creation')
            
            paginator = Paginator(products_query, 10)
            
            try:
                current_products = paginator.page(page)
            except PageNotAnInteger:
                current_products = paginator.page(1)
            except EmptyPage:
                current_products = []

            products = [product.get_json() for product in current_products]
            
            return Response({
                'products': products,
                'company_categories': list(company_categories),
                'pagination': {
                    'has_next': current_products.has_next() if current_products else False,
                    'current_page': int(page),
                    'total_pages': paginator.num_pages
                }
            }, status=status.HTTP_200_OK)
        except Company.DoesNotExist:
            return Response({'error': 'No existe la compania especificada.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': f'Error interno: {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GetCompanySubCategories(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    permission_classes = [IsAuthenticated]

    def get(self, request, company_id=None):
        """
        Devuelve todas las subcategorías únicas que tienen productos registrados en la compañía.
        """
        try:
            company = Company.objects.get(id=company_id)
            if company.owner.id != request.user.id:
                return Response({'error': 'No autorizado.'}, status=status.HTTP_406_NOT_ACCEPTABLE)
            
            # ORM Mágico: Filtra las subcategorías cruzándolas con los productos de esta empresa
            company_categories = SubCategory.objects.filter(
                product__company=company
            ).distinct().values('id', 'name')
            
            return Response({'categories': list(company_categories)}, status=status.HTTP_200_OK)

        except Company.DoesNotExist:
            return Response({'error': 'Compañía no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': f'Error interno: {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GetStoreInventoryItems(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    permission_classes = [IsAuthenticated]

    def get(self, request, store_id=None):
        try:
            store = CompanyStore.objects.select_related('company').get(id=store_id)
            if store.company.owner_id != request.user.id:
                return Response({'error': 'No tiene permisos para esta sucursal.'}, status=status.HTTP_406_NOT_ACCEPTABLE)

            # 1. Categorías únicas del inventario de esta sucursal
            store_categories = SubCategory.objects.filter(
                product__inventory_items__store=store
            ).distinct().values('id', 'name')

            category_id = request.GET.get('category_id')
            page = request.GET.get('page', 1)
            out_of_stock = request.GET.get('out_of_stock') == 'true'

            # 2. QuerySet base optimizado con select_related
            items_query = InventoryItem.objects.filter(store=store).select_related(
                'product',
                'product__category',
                'product__category__parent_category',
                'product__company',
                'offer',
                'store',
                'store__company',
            )
            
            if category_id:
                items_query = items_query.filter(product__category_id=category_id)
                
            if out_of_stock:
                items_query = items_query.filter(stock=0)
                
            items_query = items_query.order_by('-creation')
            
            paginator = Paginator(items_query, 10)
            
            try:
                current_items = paginator.page(page)
            except PageNotAnInteger:
                current_items = paginator.page(1)
            except EmptyPage:
                current_items = []

            # =========================================================
            # 💡 CART-6: CÁLCULO DE NÚMEROS Y MÉTRICAS POR LOTE
            # =========================================================
            current_items_list = list(current_items)
            item_ids = [item.id for item in current_items_list]
            item_ids_str = [str(uid) for uid in item_ids]

            # A. Visualizaciones
            views_qs = ProductViewLog.objects.filter(
                inventory_item_id__in=item_ids
            ).values('inventory_item_id').annotate(total_views=Count('id'))
            views_map = {v['inventory_item_id']: v['total_views'] for v in views_qs}

            # B. Ventas y unidades egresadas
            sales_qs = InventoryItemTransaction.objects.filter(
                item_id__in=item_ids,
                transaction_type=TransactionType.OUTCOME
            ).values('item_id').annotate(
                units_sold=Sum('units'),
                sales_count=Count('id')
            )
            sales_map = {
                s['item_id']: {
                    'units_sold': abs(s['units_sold'] or 0),
                    'sales_count': s['sales_count'] or 0
                } for s in sales_qs
            }

            # C. Likes / Favoritos polimórficos
            item_ct = ContentType.objects.get_for_model(InventoryItem)
            likes_qs = UniversalLike.objects.filter(
                content_type=item_ct,
                object_id__in=item_ids_str
            ).values('object_id').annotate(total_likes=Count('id'))
            likes_map = {l['object_id']: l['total_likes'] for l in likes_qs}

            # D. Preguntas / Comentarios polimórficos
            comments_qs = UniversalComment.objects.filter(
                content_type=item_ct,
                object_id__in=item_ids_str
            ).values('object_id').annotate(total_comments=Count('id'))
            comments_map = {c['object_id']: c['total_comments'] for c in comments_qs}

            items = []
            for item in current_items_list:
                item_json = item.get_json()
                item_id = item.id
                item_str = str(item_id)
                
                views_count = views_map.get(item_id, 0)
                sold_info = sales_map.get(item_id, {'units_sold': 0, 'sales_count': 0})
                units_sold = sold_info['units_sold']
                sales_count = sold_info['sales_count']
                likes_count = likes_map.get(item_str, 0)
                questions_count = comments_map.get(item_str, 0)
                
                unit_price = float(item.custom_price if item.custom_price else item.product.price)
                revenue = round(units_sold * unit_price, 2)
                
                metrics = {
                    'views_count': views_count,
                    'units_sold': units_sold,
                    'sales_count': sales_count,
                    'revenue': revenue,
                    'likes_count': likes_count,
                    'questions_count': questions_count,
                }
                
                item_json['metrics'] = metrics
                item_json['views_count'] = views_count
                item_json['units_sold'] = units_sold
                item_json['revenue'] = revenue
                item_json['likes_count'] = likes_count
                item_json['questions_count'] = questions_count
                
                items.append(item_json)

            return Response({
                'items': items,
                'store_categories': list(store_categories),
                'pagination': {
                    'has_next': current_items.has_next() if current_items else False,
                    'current_page': int(page),
                    'total_pages': paginator.num_pages
                }
            }, status=status.HTTP_200_OK)

        except CompanyStore.DoesNotExist:
            return Response({'error': 'No existe la sucursal especificada.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': f'Error interno: {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GetCartMakerAccounts(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Devuelve todas las cuentas bancarias disponibles para CartMaker.
        """
        return Response({'data':[bank.get_json() for bank in CartMakerBankAccount.objects.filter(active=True)]}, status=status.HTTP_200_OK)


class GetMerchantPlans(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Devuelve todas los planes disponibles para comerciantes.
        """
        plans = [mp.get_json() for mp in MerchantPlan.objects.all().order_by('price')]
        dollar_bcv_tax = _get_cached_bcv_rate(default=0.0)
        bs_price = 0.0
        for plan in plans:
            if dollar_bcv_tax > 0.0:
                bs_price = plan['price'] * dollar_bcv_tax
            plan['bs_price'] = bs_price
            plan['dollar_bcv_tax'] = dollar_bcv_tax
        return Response({'data':plans}, status=status.HTTP_200_OK)
    
class GetAtlasPlusPlanDetails(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Devuelve los datos de configuración, límites y costos en tiempo real 
        (USD y Bs BCV) para el plan Atlas Plus.
        """
        config = SystemConfig.objects.latest('creation')
        
        dollar_bcv_tax = _get_cached_bcv_rate(default=1.0)
        bs_price = 0.0

        price_usd = float(config.atlas_plus_price_usd)
        if dollar_bcv_tax > 0.0:
            bs_price = price_usd * dollar_bcv_tax

        payload = {
            'atlas_plus_price_usd': price_usd,
            'bs_price': bs_price,
            'dollar_bcv_tax': dollar_bcv_tax,
            'atlas_plus_daily_limit': config.atlas_plus_daily_limit,
            'atlas_free_daily_limit': config.atlas_free_daily_limit,
        }
        
        return Response({'data': payload}, status=status.HTTP_200_OK)
    
class UploadSubscriptionPayment(APIView):
    permission_classes = [IsAuthenticated]

    def _try_automatic_bank_validation(self, reference_number, amount_bs) -> bool:
        """
        [Capa Defensiva] Intenta conciliar el pago móvil/transferencia con la API del banco.
        Si la API del banco falla, cae, o no encuentra coincidencia exacta, devuelve False
        para que el flujo pase a validación manual por supervisores sin trancar la app.
        """
        try:
            # Ejemplo analítico de consumo de webhook/API bancaria
            # payload = {"ref": reference_number, "amount": float(amount_bs)}
            # r = requests.post("https://api.tu-banco.com/v1/verify", json=payload, timeout=4)
            # return r.json().get("matched") == True
            return False  # Simulamos falla/no disponible para forzar validación manual segura
        except Exception as e:
            print(f"⚠️ API Bancaria no disponible: {e}")
            return False

    def post(self, request):
        serializer = UploadSubscriptionPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        
        subscription_type = data['subscription_type']
        dollar_bcv_tax = Decimal(str(data['dollar_bcv_tax']))
        monto_enviado_bs = Decimal(str(data['amount_sended']))

        # Intentar conciliación bancaria automática primero
        bank_api_available = self._try_automatic_bank_validation(data['reference_number'], monto_enviado_bs)

        # =========================================================================
        # CASO 1: SUSCRIPCIONES ATLAS PLUS
        # =========================================================================
        if subscription_type == 1:
            file_obj = data['payment_proof']
            extension = file_obj.name.rsplit('.', 1)[-1].lower() if '.' in getattr(file_obj, 'name', '') else ''
            if extension not in ('jpg', 'jpeg', 'png', 'webp', 'pdf'):
                return Response({'error': 'Formato de comprobante no permitido. Usa JPG, PNG, WEBP o PDF.'}, status=status.HTTP_400_BAD_REQUEST)
            if getattr(file_obj, 'size', 0) > 10 * 1024 * 1024:
                return Response({'error': 'El comprobante excede el límite máximo de 10 MB.'}, status=status.HTTP_400_BAD_REQUEST)

            atlas_plan, _ = AtlasPlusPlan.objects.get_or_create(user=request.user)
            if AtlasPlusPlanPayment.objects.filter(plan=atlas_plan, status=PaymentStatus.PENDING).exists():
                return Response({'error': "Ya tienes un pago pendiente por verificación para Atlas Plus."}, status=status.HTTP_406_NOT_ACCEPTABLE)

            file_name = f"atlas_payment_{atlas_plan.id}_{timezone.now().strftime('%d-%m-%Y_%H-%M-%S')}.{extension}"
            relative_path = storage_manager.save_file(file_obj, "subscriptions/atlas_plus", file_name)

            with transaction.atomic():
                atlas_plan = AtlasPlusPlan.objects.select_for_update().get(pk=atlas_plan.pk)
                if AtlasPlusPlanPayment.objects.filter(plan=atlas_plan, status=PaymentStatus.PENDING).exists():
                    return Response({'error': "Ya tienes un pago pendiente por verificación para Atlas Plus."}, status=status.HTTP_406_NOT_ACCEPTABLE)

                payment = AtlasPlusPlanPayment.objects.create(
                    plan=atlas_plan,
                    reference_number=data['reference_number'],
                    payment_proof_url=relative_path,
                    amount=monto_enviado_bs,
                    bcv_taxes_to_day=dollar_bcv_tax,
                    status=PaymentStatus.APPROVED if bank_api_available else PaymentStatus.PENDING,
                    verified_at=timezone.now() if bank_api_available else None
                )

            if bank_api_available:
                cache.delete(f"cartmaker:tenant:{request.user.id}:company")
                cache.delete(f"cartmaker:tenant:{request.user.id}:subscriptions")

            # Si la API del banco lo aprobó instantáneamente, se ejecutan las señales de activación de inmediato
            return Response({'payment_data': payment.get_json(), 'subscription_data': atlas_plan.get_json()}, status=status.HTTP_201_CREATED)

        elif subscription_type == 2:
            return Response(
                {'error': 'Vender en CartMaker ya no requiere un plan de pago. Configura tu compañía para empezar.'},
                status=status.HTTP_406_NOT_ACCEPTABLE,
            )


class FullPaySubscriptionWithWalletView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            plan_type = request.data.get('plan_type', 'merchant')
            if plan_type != 'atlas':
                return Response({
                    'success': False,
                    'message': 'Vender en CartMaker ya no requiere un plan de pago. Configura tu compañía para empezar.'
                }, status=status.HTTP_406_NOT_ACCEPTABLE)

            # Obtenemos la tasa BCV FUERA de la transacción atómica para no retener bloqueos de fila durante llamadas de red
            try:
                dollar_bcv_tax = _get_cached_bcv_rate(default=1.0, raise_on_failure=True)
            except Exception as e:
                print(f"Error obteniendo el precio del dolar bcv: {e}")
                return Response({'error': "No se pudo determinar la tasa del dolar."}, status=status.HTTP_423_LOCKED)

            with transaction.atomic():
                wallet = UserWallet.objects.select_for_update().get(user=request.user)

                config = SystemConfig.objects.latest('creation')
                atlas_plan = AtlasPlusPlan.objects.select_for_update().get(user=request.user)
                price_usd = config.atlas_plus_price_usd

                # Lógica de prorrateo para Atlas Plus si cambia/renueva antes de vencer
                if atlas_plan.tier == AtlasSubscriptionTier.PREMIUM and atlas_plan.valid_until and atlas_plan.valid_until > timezone.now():
                    days_left = (atlas_plan.valid_until - timezone.now()).total_seconds() / 86400.0
                    daily_rate = float(price_usd) / 30.0
                    remanent_usd = Decimal(str(round(days_left * daily_rate, 2)))
                    if remanent_usd > 0:
                        wallet.regist_transaction(remanent_usd, 'atlas', "Reintegro por tiempo no consumido de Atlas Plus", 'add')

                if wallet.balance < price_usd:
                    return Response({'success': False, 'message': 'Saldo insuficiente para Atlas Plus.'}, status=status.HTTP_400_BAD_REQUEST)

                wallet.regist_transaction(price_usd, 'atlas', "Pago de suscripción Atlas Plus", 'substract')

                atlas_plan.tier = AtlasSubscriptionTier.PREMIUM
                atlas_plan.valid_until = timezone.now() + relativedelta(months=1)
                atlas_plan.save()

                atlas_payment = AtlasPlusPlanPayment.objects.create(
                    plan=atlas_plan,
                    reference_number=f"WALLET-ATLAS-{uuid.uuid4().hex[:6].upper()}",
                    amount=0,
                    bcv_taxes_to_day=dollar_bcv_tax,
                    status=PaymentStatus.APPROVED,
                    verified_at=timezone.now()
                )

                Notification.objects.create(
                    user=request.user,
                    section=NotificationSection.HOME,
                    title="¡Atlas Plus Activo!",
                    body="Tu billetera cubrió la activación. Disfruta de tus 75 interacciones diarias.",
                    category=NotificationCategory.PAYMENT_APPROVED,
                    metadata={'payment_id': str(atlas_payment.id)}
                )

                user_id = request.user.id
                transaction.on_commit(lambda: cache.delete(f"cartmaker:tenant:{user_id}:subscriptions"))

                return Response({
                    'success': True,
                    'message': '¡Atlas Plus activado usando tu saldo a favor!',
                    'data': {'new_balance': float(wallet.balance), 'valid_until': atlas_plan.valid_until.strftime("%d/%m/%Y, %H:%M:%S")}
                }, status=status.HTTP_200_OK)

        except UserWallet.DoesNotExist:
            return Response({
                'success': False, 
                'message': 'No se encontró la billetera del usuario.'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            print("ERROR INTERNO EN EL SERVIDOR: ", e)
            return Response({
                'success': False, 
                'message': f'Ocurrió un error al procesar el pago: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CreateCompanyAPI(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    serializer_class = CreateCompanySerializer

    @staticmethod
    def _compute_file_sha256(file_obj) -> str:
        file_obj.seek(0)
        hasher = hashlib.sha256()
        if hasattr(file_obj, "chunks"):
            for chunk in file_obj.chunks():
                hasher.update(chunk)
        else:
            hasher.update(file_obj.read())
        file_obj.seek(0)
        return hasher.hexdigest()

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            print("ERRORES DE SERIALIZER:", serializer.errors)
            return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        user = request.user
        if user.user_type == UserType.MERCHANT or Company.objects.filter(owner=user).exists():
            return Response({"error": "Este usuario ya posee una compañia."}, status=status.HTTP_400_BAD_REQUEST)
        company_name = serializer.validated_data["name"].strip()
        comercial_entity_type = serializer.validated_data["comercial_entity_type"]
        store_type = serializer.validated_data["store_type"]
        selected_mall_id = serializer.validated_data.get("selected_mall_id")
        selected_mall_floor = serializer.validated_data.get("selected_mall_floor")
        company_category_id = serializer.validated_data["company_category"]
        lat = serializer.validated_data.get("lat")
        lng = serializer.validated_data.get("lng")
        address = serializer.validated_data.get("address")
        # --- DATOS KYB (SI ES EMPRESA: comercial_entity_type == 1) ---
        rif_number = (serializer.validated_data.get("rif_number") or "").strip()
        razon_social = (serializer.validated_data.get("razon_social") or "").strip()
        mercantil_oficina = (serializer.validated_data.get("mercantil_oficina") or "").strip()
        mercantil_numero = (serializer.validated_data.get("mercantil_numero") or "").strip()
        mercantil_tomo = (serializer.validated_data.get("mercantil_tomo") or "").strip()
        client_rep_cedula = (serializer.validated_data.get("representante_cedula") or "").strip()
        kyb_ocr_verified = serializer.validated_data.get("kyb_ocr_verified", False)
        kyb_confidence_score = serializer.validated_data.get("kyb_confidence_score", 0)
        rif_file = serializer.validated_data.get("rif_document")
        mercantil_file = serializer.validated_data.get("mercantil_document")
        if Company.objects.filter(name__iexact=company_name).exists():
            return Response({'error': 'El nombre de la compañia no esta disponible.'}, status=status.HTTP_400_BAD_REQUEST)
        locked_representante_cedula = None
        rif_sha256 = None
        mercantil_sha256 = None
        # =====================================================================
        # VALIDACIÓN ESTRICTA KYB (CAMINO 1) SI ES EMPRESA CONSTITUIDA (1)
        # =====================================================================
        if comercial_entity_type == MerchantType.BUSINESS:
            # 1. Exigir que la cuenta de CartMaker tenga su Cédula verificada biométricamente
            if not getattr(user, "cedula_verified", False) or not getattr(user, "cedula_number", None):
                return Response(
                    {'error': 'Debes verificar tu Cédula de Identidad biométricamente antes de registrar una Empresa Constituida.'},
                    status=status.HTTP_403_FORBIDDEN
                )
            # 2. Bloquear la Cédula del representante directamente a la del titular autenticado en BD
            user_digits = re.sub(r"[^0-9]", "", str(user.cedula_number))
            if client_rep_cedula:
                client_digits = re.sub(r"[^0-9]", "", client_rep_cedula)
                if client_digits and client_digits != user_digits:
                    return Response(
                        {'error': 'Alerta Antifraude: La Cédula del representante no coincide con la Cédula verificada de tu cuenta.'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            raw_nac = getattr(user, "nacionality", UserNacionality.VENEZOLANO)
            if isinstance(raw_nac, str):
                nac_prefix = raw_nac.strip().upper()
            else:
                nac_prefix = "E" if raw_nac == UserNacionality.EXTRANJERO else "V"
            if nac_prefix not in ("V", "E"):
                nac_prefix = "V"
            locked_representante_cedula = f"{nac_prefix}-{user_digits}"
            # 3. Validar campos obligatorios y documentos físicos escaneados
            if not rif_number or not razon_social or not mercantil_oficina or not mercantil_numero or not mercantil_tomo:
                return Response(
                    {'error': 'Debe consignar todos los datos mercantiles (RIF, Razón Social, Oficina, Número y Tomo).'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if not rif_file or not mercantil_file:
                return Response(
                    {'error': 'Debe adjuntar las capturas escaneadas del Comprobante RIF y del Registro Mercantil.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            # 4. Validar Checksum Módulo 11 del RIF en el servidor (protección contra Postman/scripts)
            is_valid_rif, normalized_rif, rif_error = validate_venezuelan_rif_modulo11(rif_number)
            if not is_valid_rif:
                return Response({'error': rif_error}, status=status.HTTP_400_BAD_REQUEST)
            rif_number = normalized_rif
            # 5. Calcular y validar hashes SHA-256 de las imágenes de RIF y Registro Mercantil
            rif_sha256 = self._compute_file_sha256(rif_file)
            mercantil_sha256 = self._compute_file_sha256(mercantil_file)
            if rif_sha256 == mercantil_sha256:
                return Response(
                    {'error': 'Las imágenes del Comprobante RIF y del Registro Mercantil no pueden ser el mismo archivo.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if Company.objects.filter(Q(rif_image_sha256=rif_sha256) | Q(mercantil_image_sha256=rif_sha256)).exists():
                return Response(
                    {'error': 'La imagen del Comprobante RIF ya fue utilizada en otro registro.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if Company.objects.filter(Q(mercantil_image_sha256=mercantil_sha256) | Q(rif_image_sha256=mercantil_sha256)).exists():
                return Response(
                    {'error': 'La imagen del Registro Mercantil ya fue utilizada en otro registro.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            # 6. Validar que no exista otra empresa con el mismo RIF, Razón Social o Asiento Mercantil
            if Company.objects.filter(rif_number__iexact=rif_number).exists():
                return Response(
                    {'error': f'El RIF {rif_number} ya se encuentra registrado en otra empresa.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if Company.objects.filter(razon_social__iexact=razon_social).exists():
                return Response(
                    {'error': f'La Razón Social "{razon_social}" ya se encuentra registrada en otra empresa.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if Company.objects.filter(
                mercantil_oficina__iexact=mercantil_oficina,
                mercantil_numero__iexact=mercantil_numero,
                mercantil_tomo__iexact=mercantil_tomo,
            ).exists():
                return Response(
                    {'error': f'El asiento mercantil (Nro. {mercantil_numero}, Tomo {mercantil_tomo}) ya fue registrado por otra empresa.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        try:
            company_category = CompanyCategory.objects.get(id=company_category_id)
        except CompanyCategory.DoesNotExist:
            return Response({"error": "La categoria especificada no existe."}, status=status.HTTP_400_BAD_REQUEST)
        if store_type == StoreType.IN_MALL:
            if selected_mall_id is None or selected_mall_floor is None:
                return Response({'error': 'Debes especificar el centro comercial y el piso.'}, status=status.HTTP_400_BAD_REQUEST)
            try:
                mall = Mall.objects.get(id=selected_mall_id)
                location = mall.coordinates
                if not address:
                    address = mall.name
            except Mall.DoesNotExist:
                return Response({'error': 'El centro comercial seleccionado no existe.'}, status=status.HTTP_404_NOT_FOUND)
        else:
            if lat is None or lng is None or address is None:
                return Response({'error': 'Debes especificar las coordenadas y la dirección.'}, status=status.HTTP_400_BAD_REQUEST)
            location = Point(float(lng), float(lat), srid=4326)
            mall = None
        # Subida de documentos KYB a Cloud Object Storage (si aplica)
        rif_doc_url = None
        mercantil_doc_url = None
        if comercial_entity_type == MerchantType.BUSINESS:
            dtnow_str = timezone.localtime(timezone.now()).strftime('%d-%m-%Y_%H-%M-%S')
            rif_ext = rif_file.name.rsplit('.', 1)[-1].lower() if '.' in getattr(rif_file, 'name', '') else 'jpg'
            mercantil_ext = mercantil_file.name.rsplit('.', 1)[-1].lower() if '.' in getattr(mercantil_file, 'name', '') else 'jpg'
            rif_filename = f"rif_{user.id}_{dtnow_str}.{rif_ext}"
            mercantil_filename = f"mercantil_{user.id}_{dtnow_str}.{mercantil_ext}"
            rif_rel_path = storage_manager.save_file(rif_file, "companies/kyb/rif", rif_filename)
            mercantil_rel_path = storage_manager.save_file(mercantil_file, "companies/kyb/mercantil", mercantil_filename)
            if not rif_rel_path or not mercantil_rel_path:
                return Response(
                    {'error': 'Error al almacenar los documentos mercantiles en el servidor. Intente nuevamente.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            rif_doc_url = storage_manager.get_url(rif_rel_path)
            mercantil_doc_url = storage_manager.get_url(mercantil_rel_path)
        with transaction.atomic():
            locked_user = User.objects.select_for_update().get(pk=user.pk)
            if locked_user.user_type == UserType.MERCHANT or Company.objects.filter(owner=locked_user).exists():
                return Response({"error": "Este usuario ya posee una compañia."}, status=status.HTTP_400_BAD_REQUEST)
            if Company.objects.filter(name__iexact=company_name).exists():
                return Response({'error': 'El nombre de la compañia no esta disponible.'}, status=status.HTTP_400_BAD_REQUEST)

            company = Company.objects.create(
                owner=locked_user,
                name=company_name,
                merchant_type=comercial_entity_type,
                category=company_category,
                rif_number=rif_number if comercial_entity_type == MerchantType.BUSINESS else None,
                razon_social=razon_social if comercial_entity_type == MerchantType.BUSINESS else None,
                mercantil_oficina=mercantil_oficina if comercial_entity_type == MerchantType.BUSINESS else None,
                mercantil_numero=mercantil_numero if comercial_entity_type == MerchantType.BUSINESS else None,
                mercantil_tomo=mercantil_tomo if comercial_entity_type == MerchantType.BUSINESS else None,
                # Siempre guardamos la Cédula bloqueada del titular autenticado (nunca un string libre)
                representante_cedula=locked_representante_cedula if comercial_entity_type == MerchantType.BUSINESS else None,
                rif_document_url=rif_doc_url,
                mercantil_document_url=mercantil_doc_url,
                rif_image_sha256=rif_sha256 if comercial_entity_type == MerchantType.BUSINESS else None,
                mercantil_image_sha256=mercantil_sha256 if comercial_entity_type == MerchantType.BUSINESS else None,
                kyb_ocr_verified=kyb_ocr_verified if comercial_entity_type == MerchantType.BUSINESS else False,
                kyb_confidence_score=kyb_confidence_score if comercial_entity_type == MerchantType.BUSINESS else 0,
            )
            main_store = CompanyStore.objects.create(
                company=company,
                name="Sucursal Principal",
                store_type=store_type,
                is_main_store=True,
                is_active=True,
            )
            StoreLocation.objects.create(
                store=main_store,
                mall=mall if store_type == StoreType.IN_MALL else None,
                mall_floor=selected_mall_floor if store_type == StoreType.IN_MALL else None,
                coordinates=location,
                name=address or company_name,
            )
            user.user_type = UserType.MERCHANT
            user.save(update_fields=['user_type'])
        return Response(
            {
                "message": "Compañía creada exitosamente.",
                "company": company.get_json(),
                "store": main_store.get_json(),
            },
            status=status.HTTP_201_CREATED,
        )

class CheckCompanyNameAvailableAPI(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    permission_classes = [IsAuthenticated]

    def get(self, request, name:str):
        return Response(status=status.HTTP_202_ACCEPTED) if Company.objects.only('name').filter(name=name).exists()\
            == False else Response(status=status.HTTP_406_NOT_ACCEPTABLE)

class UpdateCompanyAPI(APIView):
    """
    Actualiza la compañía y la sucursal principal. Vender no depende de un plan.
    """
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = UpdateCompanySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            company = Company.objects.get(id=data['company_id'])
        except Company.DoesNotExist:
            return Response({'error': 'No se encontro la compania.'}, status=status.HTTP_404_NOT_FOUND)
        if company.owner_id != request.user.id:
            return Response({'error': 'No tienes permisos para modificar esta compañía.'}, status=status.HTTP_403_FORBIDDEN)
        main_store = company.stores.filter(is_main_store=True).first()
        if main_store == None:
            first = company.stores.all().order_by('-creation').first()
            if first == None:
                return Response({'error': 'No hay una tienda configurada'}, status=status.HTTP_409_CONFLICT)
            first.is_main_store = True
            first.save()
            main_store = first
        profile_img = data.get('profile_img')
        main_store_img = data.get('main_store_img')
        presentation_video = data.get('presentation_video')
        presentation_video_thumbnail = data.get('presentation_video_thumbnail')
        category_id = data.get('category_id')
        name = data.get('name')
        gamification_enabled = data.get('gamification_enabled')
        gamification_tokens_per_dollar = data.get('gamification_tokens_per_dollar')
        work_hours = data.get('work_hours')
        whatsapp_number = data.get('whatsapp_number')
        instagram_handle = data.get('instagram_handle')
        phone_number = data.get('phone_number')
        work_days = data.get('work_days')
        
        # Extracción de campos de ubicación
        store_type = data.get('store_type')
        is_mall = data.get('is_mall')
        lat = data.get('lat')
        lng = data.get('lng')
        address = data.get('address')
        selected_mall_id = data.get('selected_mall_id')
        selected_mall_floor = data.get('selected_mall_floor')
        print("DATA QUE LLEGA DEL REQUEST: ", data)
        company_has_changed = False
        store_has_changed = False

        with transaction.atomic():
            dtnow_str = timezone.localtime(timezone.now()).strftime('%d-%m-%Y_%H-%M-%S')
            
            # ===============================
            # 1. MANEJO DE ARCHIVOS (MULTIMEDIA)
            # ===============================
            if profile_img:
                # NUEVO: Limpiamos la imagen de perfil anterior
                if company.image:
                    try:
                        storage_manager.delete_file(company.image)
                    except Exception as e:
                        print(f"Error borrando img vieja: {e}")

                extension = profile_img.name.split('.')[-1]
                file_name = f"{company.id}_{dtnow_str}.{extension}"
                folder = "company_profile_pictures"
                relative_path = storage_manager.save_file(profile_img, folder, file_name)
                
                if relative_path:
                    company.image = relative_path
                    company_has_changed = True
                else:
                    raise Exception("Error al guardar la imagen de perfil en el storage.")
            
            if main_store_img:
                # NUEVO: Limpiamos la foto de tienda anterior
                if main_store.store_img_url:
                    try:
                        storage_manager.delete_file(main_store.store_img_url)
                    except Exception as e:
                        print(f"Error borrando img de tienda vieja: {e}")

                extension = main_store_img.name.split('.')[-1]
                file_name = f"{dtnow_str}.{extension}"
                folder = f"store_pictures/{main_store.id}"
                relative_path = storage_manager.save_file(main_store_img, folder, file_name)
                
                if relative_path:
                    main_store.store_img_url = relative_path
                    store_has_changed = True
                else:
                    raise Exception("Error al guardar la imagen de la tienda en el storage.")
            
            if presentation_video:
                # NUEVO: ¡Aquí matamos el video viejo!
                if company.presentation_video_url:
                    try:
                        storage_manager.delete_file(company.presentation_video_url)
                    except Exception as e:
                        # Hacemos un print/log pero NO detenemos la ejecución si falla
                        # (es mejor dejar un archivo huérfano que bloquearle la app al usuario)
                        print(f"Atención: No se pudo borrar el video anterior en {company.presentation_video_url}. Error: {e}")

                extension = presentation_video.name.split('.')[-1]
                file_name = f"{company.id}_video_{dtnow_str}.{extension}"
                folder = "company_presentation_videos"
                relative_path = storage_manager.save_file(presentation_video, folder, file_name)
                
                if relative_path:
                    company.presentation_video_url = relative_path
                    company_has_changed = True
                else:
                    raise Exception("Error al guardar el video en el storage.")
            
            if presentation_video_thumbnail:
                # NUEVO: Limpiamos la miniatura vieja
                if company.presentation_video_thumbnail:
                    try:
                        storage_manager.delete_file(company.presentation_video_thumbnail)
                    except Exception as e:
                        print(f"Error borrando thumbnail viejo: {e}")

                extension = presentation_video_thumbnail.name.split('.')[-1]
                file_name = f"{company.id}_thumbnail_{dtnow_str}.{extension}"
                folder = "company_presentation_videos"
                relative_path = storage_manager.save_file(presentation_video_thumbnail, folder, file_name)
                
                if relative_path:
                    company.presentation_video_thumbnail = relative_path
                    company_has_changed = True
                else:
                    raise Exception("Error al guardar el thumbnail del video en el storage.")

            
            # =========================
            # 2. ACTUALIZACIÓN DE DATOS (Empresa)
            # =========================
            if name:
                company.name = name
                company_has_changed = True
            
            if category_id:
                company.category_id = category_id
                company_has_changed = True
                
            if gamification_enabled is not None:
                company.gamification_enabled = gamification_enabled
                company_has_changed = True
                
            if gamification_tokens_per_dollar is not None:
                company.gamification_tokens_per_dollar = gamification_tokens_per_dollar
                company_has_changed = True

            if work_hours:
                company.main_work_hours = work_hours 
                company_has_changed = True
                
            # <-- 2. Agrega este bloque para work_days
            if work_days is not None: 
                # Si llega como string (por el FormData de Flutter), lo convertimos
                if isinstance(work_days, str):
                    import json
                    try:
                        company.main_work_days = json.loads(work_days)
                    except json.JSONDecodeError:
                        pass
                else:
                    company.main_work_days = work_days
                company_has_changed = True
                
            # Métodos de contacto
            contact_data = [
                (whatsapp_number, ContactMethodType.WHATSAPP),
                (instagram_handle, ContactMethodType.INSTAGRAM),
                (phone_number, ContactMethodType.PHONE),
            ]
            for value, method_type in contact_data:
                if value is not None:
                    StoreContactMethod.objects.update_or_create(
                        store=main_store,
                        method_type=method_type,
                        defaults={'value': value}
                    )

            # =========================
            # 3. ACTUALIZACIÓN DE UBICACIÓN
            # =========================
            if store_type is not None:
                main_store.store_type = store_type
                store_has_changed = True

            if is_mall is not None:
                location, _ = StoreLocation.objects.get_or_create(store=main_store)
                
                if is_mall:
                    try:
                        mall = Mall.objects.get(id=selected_mall_id)
                        location.mall = mall
                        location.coordinates = mall.coordinates
                        location.name = address  # Nombre del C.C.
                        
                        # NUEVO: Guardamos el piso en su campo dedicado
                        if selected_mall_floor is not None:
                            location.mall_floor = selected_mall_floor
                        
                        location.save()
                    except Mall.DoesNotExist:
                        return Response({'error': "El centro comercial seleccionado no existe."}, status=status.HTTP_400_BAD_REQUEST)
                else:
                    # Si ya no está en un mall, limpiamos los campos
                    location.mall = None
                    location.mall_floor = None 
                    location.details = None
                    if lat is not None and lng is not None:
                        location.coordinates = Point(x=lng, y=lat)
                    if address:
                        location.name = address
                    location.save()

            # ===============================
            # 4. GUARDADO FINAL
            # ===============================
            if company_has_changed:
                company.save()
            
            if store_has_changed:
                main_store.save()
                
        return Response({'message': 'Compañía actualizada exitosamente'}, status=status.HTTP_200_OK)
    
class CompanyStoreViewSet(viewsets.ModelViewSet):
    queryset = CompanyStore.objects.select_related('company').all()
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return CompanyStore.objects.select_related('company').filter(company__owner=self.request.user)

    @action(detail=True, methods=['post'])
    def set_main_store(self, request, pk=None):
        """
        Setea la tienda actual como la principal y desmarca cualquier otra 
        tienda de la misma compañía.
        """
        store = self.get_object()
        company = store.company

        # 1. Validar que el usuario que hace la petición es el dueño real de la compañía
        if company.owner != request.user:
            return Response(
                {'error': 'No tienes permisos para modificar las sucursales de esta compañía.'}, 
                status=status.HTTP_403_FORBIDDEN
            )

        # 2. Transacción segura para hacer el "switch"
        try:
            with transaction.atomic():
                # A. Apagamos el flag en todas las tiendas de esta compañía
                CompanyStore.objects.filter(company=company).update(is_main_store=False)
                
                # B. Encendemos el flag SOLO en la tienda solicitada
                store.is_main_store = True
                store.save(update_fields=['is_main_store'])

            return Response({
                'success': True, 
                'message': f'La sucursal "{store.name}" ha sido establecida como la principal.'
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {'error': f'Error interno al actualizar: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class CheckCompanyKybAvailableAPI(APIView):
    """
    Verifica en tiempo real (Etapa 2.5):
    1. Que el usuario autenticado tenga KYC biométrico verificado (Camino 1 Estricto).
    2. Que el RIF sea válido en Módulo 11 (SENIAT).
    3. Que ni el RIF, ni la Razón Social, ni el asiento mercantil (Oficina + Número + Tomo)
       estén ya registrados por otra empresa en CartMaker.
    """
    permission_classes = [IsAuthenticated]
    def post(self, request):
        user = request.user
        # 1. CAMINO 1 (ESTRICTO): Exigir KYC biométrico activo en la cuenta del titular
        if not getattr(user, "cedula_verified", False) or not getattr(user, "cedula_number", None):
            return Response(
                {
                    "available": False,
                    "error": "Tu cuenta personal debe tener la Cédula verificada biométricamente antes de registrar una Empresa Constituida."
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        rif_raw = (request.data.get("rif_number") or "").strip()
        razon_social = (request.data.get("razon_social") or "").strip()
        mercantil_oficina = (request.data.get("mercantil_oficina") or "").strip()
        mercantil_numero = (request.data.get("mercantil_numero") or "").strip()
        mercantil_tomo = (request.data.get("mercantil_tomo") or "").strip()
        # 2. Validar que si el cliente envía representante_cedula, coincida con request.user.cedula_number
        client_rep_cedula = (request.data.get("representante_cedula") or "").strip()
        user_digits = re.sub(r"[^0-9]", "", str(user.cedula_number))
        client_digits = re.sub(r"[^0-9]", "", client_rep_cedula)
        if client_digits and user_digits != client_digits:
            return Response(
                {
                    "available": False,
                    "error": "Alerta Antifraude: La Cédula del representante no coincide con la Cédula verificada del titular de la cuenta."
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        # 3. Validar Módulo 11 del RIF
        is_valid_rif, normalized_rif, rif_error = validate_venezuelan_rif_modulo11(rif_raw)
        if not is_valid_rif:
            return Response(
                {"available": False, "error": rif_error},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # 4. Verificar duplicidad de RIF
        if Company.objects.filter(rif_number__iexact=normalized_rif).exists():
            return Response(
                {
                    "available": False,
                    "error": f"El RIF {normalized_rif} ya se encuentra registrado por otra empresa en CartMaker."
                },
                status=status.HTTP_409_CONFLICT,
            )
        # 5. Verificar duplicidad de Razón Social
        if razon_social and Company.objects.filter(razon_social__iexact=razon_social).exists():
            return Response(
                {
                    "available": False,
                    "error": f"La Razón Social '{razon_social}' ya se encuentra registrada en CartMaker."
                },
                status=status.HTTP_409_CONFLICT,
            )
        # 6. Verificar duplicidad de Asiento en Registro Mercantil (Oficina + Número + Tomo)
        if mercantil_oficina and mercantil_numero and mercantil_tomo:
            asiento_duplicado = Company.objects.filter(
                mercantil_oficina__iexact=mercantil_oficina,
                mercantil_numero__iexact=mercantil_numero,
                mercantil_tomo__iexact=mercantil_tomo,
            ).exists()
            if asiento_duplicado:
                return Response(
                    {
                        "available": False,
                        "error": f"El asiento mercantil (Nro. {mercantil_numero}, Tomo {mercantil_tomo}) ya fue registrado por otra empresa."
                    },
                    status=status.HTTP_409_CONFLICT,
                )
        # 7. Verificar duplicidad de hashes SHA-256 de imágenes si el cliente los envía
        rif_sha256 = (request.data.get("rif_image_sha256") or "").strip().lower()
        mercantil_sha256 = (request.data.get("mercantil_image_sha256") or "").strip().lower()
        if rif_sha256 and mercantil_sha256 and rif_sha256 == mercantil_sha256:
            return Response(
                {
                    "available": False,
                    "error": "Las imágenes del Comprobante RIF y del Registro Mercantil no pueden ser el mismo archivo."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if rif_sha256 and Company.objects.filter(
            Q(rif_image_sha256__iexact=rif_sha256) | Q(mercantil_image_sha256__iexact=rif_sha256)
        ).exists():
            return Response(
                {
                    "available": False,
                    "error": "La imagen del Comprobante RIF ya fue utilizada en otro registro en CartMaker."
                },
                status=status.HTTP_409_CONFLICT,
            )
        if mercantil_sha256 and Company.objects.filter(
            Q(mercantil_image_sha256__iexact=mercantil_sha256) | Q(rif_image_sha256__iexact=mercantil_sha256)
        ).exists():
            return Response(
                {
                    "available": False,
                    "error": "La imagen del Registro Mercantil ya fue utilizada en otro registro en CartMaker."
                },
                status=status.HTTP_409_CONFLICT,
            )
        return Response(
            {
                "available": True,
                "normalized_rif": normalized_rif,
                "locked_representante_cedula": user_digits,
            },
            status=status.HTTP_200_OK,
        )
    
class CreateStoreAPI(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CreateStoreSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False, 
                'error': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
            
        d = serializer.validated_data
        
        try:
            with transaction.atomic():
                # 1. Verificar propiedad de la compañía
                try:
                    company = Company.objects.get(id=d['company_id'], owner=request.user)
                except Company.DoesNotExist:
                    return Response({
                        'success': False, 
                        'error': "La compañía no existe o no tienes permisos."
                    }, status=status.HTTP_404_NOT_FOUND)
                
                work_days_raw = d.get('work_days')
                parsed_work_days = [0, 1, 2, 3, 4] # Valor por defecto si no envían nada
                
                if work_days_raw is not None:
                    if isinstance(work_days_raw, str):
                        import json
                        try:
                            parsed_work_days = json.loads(work_days_raw)
                        except json.JSONDecodeError:
                            pass
                    else:
                        parsed_work_days = work_days_raw

                # 2. Crear instancia de Sucursal (primero sin imagen para obtener el ID)
                store = CompanyStore.objects.create(
                    company=company,
                    name=d['name'],
                    work_hours=d['work_hours'],
                    work_days=parsed_work_days,
                    store_type=d['store_type'],
                    is_active=True
                )

                # 3. Manejo de Imagen de la Sucursal (Storage)
                store_img = d.get('store_img')
                if store_img:
                    dtnow_str = timezone.localtime(timezone.now()).strftime('%d-%m-%Y_%H-%M-%S')
                    extension = store_img.name.split('.')[-1]
                    # Usamos el ID de la nueva sucursal para la carpeta
                    file_name = f"store_{store.id}_{dtnow_str}.{extension}"
                    folder = f"store_pictures/{store.id}"
                    
                    relative_path = storage_manager.save_file(store_img, folder, file_name)
                    
                    if relative_path:
                        store.store_img_url = relative_path
                        store.save()
                    else:
                        raise Exception("Error al guardar la imagen de la sucursal en el storage.")

                # 4. Crear Ubicación (StoreLocation)
                is_mall = d['is_mall']
                location = StoreLocation(store=store)
                
                if is_mall:
                    selected_mall_id = d.get('selected_mall_id')
                    try:
                        mall = Mall.objects.get(id=selected_mall_id)
                        location.mall = mall
                        location.coordinates = mall.coordinates
                        location.name = d['address'] # Usualmente el nombre del local o C.C.
                        location.mall_floor = d.get('selected_mall_floor')
                    except Mall.DoesNotExist:
                        raise Exception("El centro comercial seleccionado no existe.")
                else:
                    # Ubicación de calle
                    location.coordinates = Point(x=d['lng'], y=d['lat'])
                    location.name = d['address']
                
                location.save()

                # 5. Crear Métodos de Contacto Iniciales
                # Mapeo de campos del serializer a tipos de contacto
                contacts_to_create = [
                    (d.get('whatsapp_number'), ContactMethodType.WHATSAPP),
                    (d.get('instagram_handle'), ContactMethodType.INSTAGRAM),
                    (d.get('phone_number'), ContactMethodType.PHONE),
                ]

                for value, method_type in contacts_to_create:
                    if value: # Solo si el valor no es None o vacío
                        StoreContactMethod.objects.create(
                            store=store,
                            method_type=method_type,
                            value=value
                        )

                # 6. Respuesta Exitosa
                return Response({
                    'success': True, 
                    'message': 'Sucursal creada exitosamente.',
                    'data': store.get_json() 
                }, status=status.HTTP_201_CREATED)

        except Exception as e:
            # Si algo falla, el transaction.atomic() hará rollback de todo
            return Response({
                'success': False, 
                'error': f"Error interno: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
class UpdateStoreAPI(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    permission_classes = [IsAuthenticated]

    def delete(self, request, store_id=None):
        try:
            store = CompanyStore.objects.prefetch_related('company__owner').only('id', 'company', 'is_main_store').get(id=store_id)
            
            if request.user.id != store.company.owner_id:
                return Response({"error": "Usted no tiene permisos para eliminar esta tienda."}, status=status.HTTP_406_NOT_ACCEPTABLE)
            
            is_main = store.is_main_store
            company = store.company
            
            with transaction.atomic():
                store.delete()
                if is_main:
                    oldest_remaining = CompanyStore.objects.filter(company=company).order_by('creation').first()
                    if oldest_remaining:
                        oldest_remaining.is_main_store = True
                        oldest_remaining.save(update_fields=['is_main_store'])
                        
            return Response(status=status.HTTP_204_NO_CONTENT)
            
        except CompanyStore.DoesNotExist:
            return Response({"error": "La tienda que tratas de eliminar no existe."}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request, store_id=None):
        serializer = UpdateStoreSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        
        try:
            # Obtenemos la tienda directamente por su ID
            store = CompanyStore.objects.get(id=data['store_id'])
        except CompanyStore.DoesNotExist:
            return Response({'error': 'No se encontró la sucursal.'}, status=status.HTTP_404_NOT_FOUND)

        if store.company.owner != request.user:
            return Response({'error': 'No tienes permisos para editar esta sucursal.'}, status=status.HTTP_403_FORBIDDEN)
        
        store_img = data.get('store_img')
        name = data.get('name')
        is_active = data.get('is_active')
        work_hours = data.get('work_hours')
        work_days = data.get('work_days')
        
        whatsapp_number = data.get('whatsapp_number')
        instagram_handle = data.get('instagram_handle')
        phone_number = data.get('phone_number')
        
        # Extracción de campos de ubicación
        store_type = data.get('store_type')
        is_mall = data.get('is_mall')
        lat = data.get('lat')
        lng = data.get('lng')
        address = data.get('address')
        selected_mall_id = data.get('selected_mall_id')
        selected_mall_floor = data.get('selected_mall_floor')
        
        store_has_changed = False

        with transaction.atomic():
            dtnow_str = timezone.localtime(timezone.now()).strftime('%d-%m-%Y_%H-%M-%S')
            
            # ===============================
            # 1. MANEJO DE ARCHIVOS (FOTO SUCURSAL)
            # ===============================
            if store_img:
                # Limpiamos la foto de tienda anterior
                if store.store_img_url:
                    try:
                        storage_manager.delete_file(store.store_img_url)
                    except Exception as e:
                        print(f"Error borrando img de tienda vieja: {e}")

                extension = store_img.name.split('.')[-1]
                file_name = f"{dtnow_str}.{extension}"
                folder = f"store_pictures/{store.id}"
                relative_path = storage_manager.save_file(store_img, folder, file_name)
                
                if relative_path:
                    store.store_img_url = relative_path
                    store_has_changed = True
                else:
                    raise Exception("Error al guardar la imagen de la tienda en el storage.")
            
            # =========================
            # 2. ACTUALIZACIÓN DE DATOS
            # =========================
            if name:
                store.name = name
                store_has_changed = True
                
            if is_active is not None:
                store.is_active = is_active
                store_has_changed = True

            if work_hours:
                store.work_hours = work_hours
                store_has_changed = True

            if work_days is not None:
                if isinstance(work_days, str):
                    import json
                    try:
                        store.work_days = json.loads(work_days)
                    except json.JSONDecodeError:
                        pass
                else:
                    store.work_days = work_days
                store_has_changed = True
                
            # Métodos de contacto (específicos de esta tienda)
            contact_data = [
                (whatsapp_number, ContactMethodType.WHATSAPP),
                (instagram_handle, ContactMethodType.INSTAGRAM),
                (phone_number, ContactMethodType.PHONE),
            ]
            for value, method_type in contact_data:
                if value is not None: # Si mandan "" se actualizará a vacío, respetando tu frontend
                    StoreContactMethod.objects.update_or_create(
                        store=store,
                        method_type=method_type,
                        defaults={'value': value}
                    )

            # =========================
            # 3. ACTUALIZACIÓN DE UBICACIÓN
            # =========================
            if store_type is not None:
                store.store_type = store_type
                store_has_changed = True

            if is_mall is not None:
                location, _ = StoreLocation.objects.get_or_create(store=store)
                
                if is_mall:
                    try:
                        mall = Mall.objects.get(id=selected_mall_id)
                        location.mall = mall
                        location.coordinates = mall.coordinates
                        location.name = address  # Nombre del C.C.
                        
                        if selected_mall_floor is not None:
                            location.mall_floor = selected_mall_floor
                        
                        location.save()
                    except Mall.DoesNotExist:
                        return Response({'error': "El centro comercial seleccionado no existe."}, status=status.HTTP_400_BAD_REQUEST)
                else:
                    # Si ya no está en un mall, limpiamos los campos del CC
                    location.mall = None
                    location.mall_floor = None 
                    location.details = None
                    if lat is not None and lng is not None:
                        location.coordinates = Point(x=lng, y=lat)
                    if address:
                        location.name = address
                    location.save()

            # ===============================
            # 4. GUARDADO FINAL
            # ===============================
            if store_has_changed:
                store.save()
                
        return Response({'message': 'Sucursal actualizada exitosamente'}, status=status.HTTP_200_OK)

class DeleteStoreContactMethodAPI(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    permission_classes = [IsAuthenticated]

    def delete(self, request, method_id:int):
        try:
            contact_method = StoreContactMethod.objects.prefetch_related('store__company__owner').get(id=method_id)
            if not request.user.id == contact_method.store.company.owner.id:
                return Response({'error': 'Usted no es propietario de esta compania.'}, status=status.HTTP_406_NOT_ACCEPTABLE)
        except StoreContactMethod.DoesNotExist:
            return Response({'error': 'No existe ese metodo de contacto.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            contact_method.delete()
        except Exception as e:
            print(f"Error al eliminar el metodo de contacto: {e}")
            return Response({'error': f"{e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({'text':"Exito"}, status=status.HTTP_204_NO_CONTENT)


# ============================================================================
# 1. MÓDULO DE PERFILES DE EMPRESA
# ============================================================================
class ClientCompanyViewSet(viewsets.ViewSet):
    """
    API dedicada a la obtención de perfiles públicos de tiendas y compañías
    desde la perspectiva del cliente final.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'navigation'

    def get_permissions(self):
        if self.action == 'profile':
            return [AllowAny()]
        return [IsAuthenticated()]

    @action(detail=False, methods=['get'])
    def profile(self, request):
        """
        Retorna la metadata pública de la tienda y su compañía (estadísticas, horarios, info).
        QueryParam: store_id o company_id
        """
        store_id = request.query_params.get('store_id')
        company_id = request.query_params.get('company_id')

        if not store_id and not company_id:
            return Response(
                {'error': 'Debe proveer store_id o company_id'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # 1. Determinar qué tienda consultar (PRIORIDAD AL STORE_ID)
            # 💡 Agregamos "!= 'null'" por si el frontend manda la palabra string por error en la URL
            base_store_qs = CompanyStore.objects.select_related(
                'company', 'company__category', 'location', 'location__mall'
            ).prefetch_related('contact_methods')

            if store_id and store_id != 'null': 
                store = base_store_qs.filter(
                    id=store_id,
                    is_active=True
                ).first()

                # Parche: Si no la encontró, verificamos si por error Flutter mandó el ID de la compañía aquí
                if not store:
                    store = base_store_qs.filter(
                        company_id=store_id,
                        is_main_store=True,
                        is_active=True
                    ).first()

                if not store:
                    return Response({'error': 'La tienda solicitada no existe, fue eliminada o está inactiva.'}, status=status.HTTP_404_NOT_FOUND)
                company = store.company
                
            elif company_id and company_id != 'null':
                # Solo entramos aquí si Flutter explícitamente NO mandó un store_id
                store = base_store_qs.filter(
                    company_id=company_id, 
                    is_active=True
                ).order_by('-is_main_store', 'creation').first()
                
                if not store:
                    return Response({'error': 'La compañía no tiene tiendas activas.'}, status=status.HTTP_404_NOT_FOUND)
                company = store.company
                
            else:
                return Response({'error': 'Faltan parámetros válidos.'}, status=status.HTTP_400_BAD_REQUEST)
            
            # =======================================================
            # 2. CÁLCULO DE MÉTRICAS GLOBALES DE LA COMPAÑÍA
            # =======================================================
            
            # A) Promedio de calificación
            rating_aggr = MerchantCalification.objects.filter(merchant=company).aggregate(Avg('rating'))
            avg_rating = round(rating_aggr['rating__avg'] or 0.0, 2)
            
            # B) Total de ventas de TODAS las sucursales
            sales_aggr = InventoryItemTransaction.objects.filter(
                item__store__company=company,
                transaction_type=1  # OUTCOME
            ).aggregate(Sum('units'))
            total_sales = sales_aggr['units__sum'] or 0
            formatted_sales = f"{total_sales // 1000}k" if total_sales >= 1000 else str(total_sales)

            # C) Categorías disponibles para esta compañía
            available_categories = SubCategory.objects.filter(
                product__inventory_items__store__company=company,
                product__inventory_items__paused=False
            ).distinct().values('id', 'name')

            available_stores_qs = CompanyStore.objects.select_related(
                'company', 'location', 'location__mall'
            ).prefetch_related('contact_methods').filter(
                company=company,
                is_active=True
            ).order_by('-is_main_store', 'creation')

            available_stores = [s.get_json() for s in available_stores_qs]

            # =======================================================
            # 3. CONSTRUCCIÓN DE LA RESPUESTA
            # =======================================================
            company_metadata = company.get_json()
            company_metadata['avg_rating'] = avg_rating
            company_metadata['total_sales'] = formatted_sales
            company_metadata['total_sales_raw'] = total_sales
            company_metadata['merchant_type'] = company.get_merchant_type_display()
            
            store_metadata = store.get_json()

            if request.user.is_authenticated:
                token_wallet = company.issued_wallets.filter(user=request.user).first()
            else:
                token_wallet = None

            return Response({
                'store_metadata': store_metadata,
                'company_metadata': company_metadata,
                'token_wallet': token_wallet.get_json() if token_wallet else None,
                'available_categories': list(available_categories),
                'available_stores': available_stores # 👈 LA LISTA DE SUCURSALES
            }, status=status.HTTP_200_OK)

        except CompanyStore.DoesNotExist:
            return Response({'error': 'La tienda solicitada no existe o fue eliminada.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception(f"Error en ClientCompanyViewSet.profile: {e}")
            return Response({'error': 'Error interno al cargar el perfil del comercio.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GamificationViewSet(viewsets.ViewSet):
    """
    API dedicada al motor de gamificación del comerciante.
    Maneja la activación global y por producto.
    """
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def status(self, request):
        """ Obtiene el estado actual de la empresa y la lista de sus productos. """
        company = Company.objects.filter(owner=request.user).first()
        if not company:
            return Response({'error': 'No se encontró la empresa del comerciante.'}, status=status.HTTP_404_NOT_FOUND)

        # Traemos los productos de esta empresa
        products = Product.objects.filter(company=company).order_by('-creation')
        
        products_data = []
        for p in products:
            image_url = ""
            if p.images and len(p.images) > 0:
                image_url = storage_manager.get_url(p.images[0])
                
            products_data.append({
                'id': str(p.id),
                'name': p.name,
                'image': image_url,
                'discounts_by_tokens_active': p.discounts_by_tokens_active
            })

        return Response({
            'gamification_enabled': company.gamification_enabled,
            'gamification_tokens_per_dollar': company.gamification_tokens_per_dollar,
            'products': products_data
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['patch'])
    def update_company_settings(self, request):
        """ Actualiza los settings globales de la empresa. """
        company = Company.objects.filter(owner=request.user).first()
        if not company:
            return Response({'error': 'Compañía no encontrada.'}, status=status.HTTP_404_NOT_FOUND)

        enabled = request.data.get('gamification_enabled')
        tokens = request.data.get('gamification_tokens_per_dollar')

        update_fields = []
        if enabled is not None:
            company.gamification_enabled = bool(enabled)
            update_fields.append('gamification_enabled')
            
        if tokens is not None:
            try:
                company.gamification_tokens_per_dollar = int(tokens)
                update_fields.append('gamification_tokens_per_dollar')
            except ValueError:
                return Response({'error': 'El valor de tokens debe ser numérico.'}, status=status.HTTP_400_BAD_REQUEST)

        if update_fields:
            company.save(update_fields=update_fields)

        return Response({'success': True, 'message': 'Configuración actualizada.'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['patch'])
    def toggle_product(self, request):
        """ Activa o desactiva la gamificación para un producto individual. """
        product_id = request.data.get('product_id')
        active = request.data.get('active')

        if product_id is None or active is None:
            return Response({'error': 'Faltan parámetros.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Aseguramos que el producto le pertenezca a la empresa del usuario
            product = Product.objects.get(id=product_id, company__owner=request.user)
            product.discounts_by_tokens_active = bool(active)
            product.save(update_fields=['discounts_by_tokens_active'])
            return Response({'success': True}, status=status.HTTP_200_OK)
        except Product.DoesNotExist:
            return Response({'error': 'Producto no encontrado o no tienes permisos.'}, status=status.HTTP_404_NOT_FOUND)

