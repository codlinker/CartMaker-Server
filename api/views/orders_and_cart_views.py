"""Order Lifecycle, Escrow, Checkout Cart, Multi-Store Reservations, and Disputes."""
from .base import *
from .base import _get_cached_bcv_rate, _extract_and_validate_category_ids

class OrderViewSet(viewsets.ViewSet):
    """
    API para la gestión y consulta de órdenes de compra del usuario.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'

    # 💡 NUEVO ENDPOINT PARA RECUPERAR UNA ORDEN INDIVIDUAL
    def retrieve(self, request, pk=None):
        """
        GET /api/v1/orders/<id>/
        Permite recuperar una orden individual si eres el cliente O el comerciante dueño.
        """
        try:
            # Buscamos la orden garantizando que el usuario sea el cliente O el dueño de la compañía
            order = Order.objects.select_related(
                'client',
                'store__company',
                'store__company__owner',
                'store__location',
                'client_location'
            ).prefetch_related(
                'client__contact_methods',
                'store__contact_methods'
            ).get(
                Q(id=pk) & (Q(client=request.user) | Q(store__company__owner=request.user))
            )
            
            # Formateamos la data exactamente igual que en tus otros métodos
            company = order.store.company
            store_image_url = storage_manager.get_url(company.image) if company.image else ""
            creation_str = timezone.localtime(order.creation).strftime("%d/%m/%Y %I:%M %p").lower() if order.creation else None
            
            store_lat = float(order.store.location.coordinates.y) if hasattr(order.store, 'location') and order.store.location and order.store.location.coordinates else None
            store_lng = float(order.store.location.coordinates.x) if hasattr(order.store, 'location') and order.store.location and order.store.location.coordinates else None
            store_address = "Dirección no registrada"
            if hasattr(order.store, 'location') and order.store.location:
                store_address = order.store.location.name
            store_email = company.owner.email if company and company.owner else "Sin correo"
            
            client_lat = float(order.client_location.coordinates.y) if order.client_location else None
            client_lng = float(order.client_location.coordinates.x) if order.client_location else None
            client_address = order.client_location.description if order.client_location else None

            is_merchant_mode = (company.owner_id == request.user.id)

            contact_methods_dict = {
                ContactMethodType(contact.method_type).name.lower(): contact.get_json()
                for contact in order.client.contact_methods.all()
            }

            store_contact_methods_dict = {
                str(ContactMethodType(contact.method_type).name).lower(): contact.get_json()
                for contact in order.store.contact_methods.all()
            }

            # Mandamos la estructura limpia que espera Flutter
            payload = {
                'id': order.id, 
                "is_merchant_mode":is_merchant_mode,
                'status': order.status,
                'withdrawal_type': order.withdrawal_type,
                'store_id': str(order.store_id),
                'store_name': company.name,
                'store_image': store_image_url,
                'store_lat': store_lat,
                'store_lng': store_lng,
                'store_contact_methods':store_contact_methods_dict,
                'store_address': store_address,
                'store_email': store_email,
                'cart': order.cart,
                'creation': creation_str,
                'client_lat': client_lat,
                'client_lng': client_lng,
                'client_address': client_address,
                "client_image": storage_manager.get_url(order.client.profile_picture) if order.client.profile_picture else None,
                'client_name': f"{order.client.first_name} {order.client.last_name}",
                'client_contact_methods':contact_methods_dict,
                'end_time': timezone.localtime(order.end_time).strftime("%d/%m/%Y %I:%M %p").lower() if order.end_time else creation_str,
                'client_cedula': order.client.cedula_number,
                'client_email': order.client.email,
            }
            
            return Response(payload, status=status.HTTP_200_OK)

        except Order.DoesNotExist:
            return Response(
                {"error": "La orden no existe o no tienes permisos para verla."}, 
                status=status.HTTP_404_NOT_FOUND
            )

    def list(self, request):
        # 💡 Optimizamos con select_related para traer la info de la tienda, la compañía y la ubicación de entrega de un solo golpe
        orders = Order.objects.select_related(
            'client',
            'store__company',
            'store__company__owner',
            'store__location',
            'client_location'
        ).prefetch_related(
            'store__contact_methods',
            'client__contact_methods'
        ).filter(client=request.user).order_by('-creation')
        
        orders_data = []
        for order in orders:
            company = order.store.company
            
            # Obtenemos el logo de la empresa usando tu storage_manager
            store_image_url = ""
            if company.image:
                store_image_url = storage_manager.get_url(company.image)
                
            # Formateamos la fecha exacto como el Mockup: "17/01/2026 09:26 am"
            creation_str = timezone.localtime(order.creation).strftime("%d/%m/%Y %I:%M %p").lower() if order.creation else None
            
            # 💡 EXTRACCIÓN DE COORDENADAS DESDE EL ONE-TO-ONE FIELD Y POINTFIELD
            store_lat = None
            store_lng = None
            client_lat = None     # 💡 CORRECCIÓN: Inicializados en None para evitar UnboundLocalError
            client_lng = None     # 💡 CORRECCIÓN: Inicializados en None para evitar UnboundLocalError
            client_address = None
            store_address = "Dirección no registrada"
            store_email = "Sin correo"
            if hasattr(order.store, 'location') and order.store.location:
                location = order.store.location
                if location.coordinates:
                    store_lat = float(location.coordinates.y)  # Eje Y = Latitud
                    store_lng = float(location.coordinates.x)  # Eje X = Longitud
                store_address = order.store.location.name
                store_email = company.owner.email if company and company.owner else "Sin correo"
            
            if order.client_location:
                client_lat = float(order.client_location.coordinates.y)
                client_lng = float(order.client_location.coordinates.x)
                client_address = order.client_location.description

            # 💡 EXTRACCIÓN DE MÉTODOS DE CONTACTO (Tienda -> Cliente)
            contact_methods_dict = {
                ContactMethodType(contact.method_type).name.lower(): contact.get_json()
                for contact in order.client.contact_methods.all()
            }

            store_contact_methods_dict = {
                str(ContactMethodType(contact.method_type).name).lower(): contact.get_json()
                for contact in order.store.contact_methods.all()
            }

            orders_data.append({
                'id': order.id, 
                'status': order.status,
                'withdrawal_type': order.withdrawal_type,
                'store_id': str(order.store.id),
                'store_name': company.name,
                'store_image': store_image_url,
                'store_contact_methods': store_contact_methods_dict,
                'store_lat': store_lat,
                'store_lng': store_lng,
                'store_address': store_address,
                'store_email': store_email,
                'cart': order.cart,
                'creation': creation_str,
                'client_lat': client_lat,
                'client_lng': client_lng,
                'client_address': client_address,
                'client_contact_methods': contact_methods_dict,
                'end_time': timezone.localtime(order.end_time).strftime("%d/%m/%Y %I:%M %p").lower() if order.end_time else creation_str,
                'client_cedula': order.client.cedula_number,
                'client_email': order.client.email,
            })

        return Response({'data': orders_data}, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def merchant_orders(self, request):
        """ Retorna las órdenes pertenecientes a las tiendas del comerciante autenticado """
        orders = Order.objects.select_related(
            'store__company', 
            'store__location', 
            'client',
            'client_location'
        ).prefetch_related(
            'client__contact_methods'
        ).filter(
            store__company__owner=request.user
        ).order_by('-creation')
        
        orders_data = []
        for order in orders:
            creation_str = timezone.localtime(order.creation).strftime("%d/%m/%Y %I:%M %p").lower() if order.creation else None
            
            # Extraemos la imagen de perfil usando tu método del modelo User
            client_image_url = order.client.get_profile_picture_url() if order.client.profile_picture else ""

            # EXTRACCIÓN DE MÉTODOS DE CONTACTO (Cliente -> Tienda)
            contact_methods_dict = {
                str(ContactMethodType(contact.method_type).name).lower(): contact.get_json()
                for contact in order.client.contact_methods.all()
            }

            # =========================================================================
            # 💡 RESOLUCIÓN DE DATA LOGÍSTICA COMPLETA PARA EL COMERCIANTE
            # =========================================================================
            company = order.store.company
            
            # Imagen corporativa de la Company
            store_image_url = ""
            if company.image:
                store_image_url = storage_manager.get_url(company.image)

            # Coordenadas geográficas de la sucursal emisora
            store_lat = None
            store_lng = None
            if hasattr(order.store, 'location') and order.store.location and order.store.location.coordinates:
                store_lat = float(order.store.location.coordinates.y)
                store_lng = float(order.store.location.coordinates.x)

            # Coordenadas geográficas fijas del destino del cliente
            client_lat = None
            client_lng = None
            client_address = None
            if order.client_location:
                client_lat = float(order.client_location.coordinates.y)
                client_lng = float(order.client_location.coordinates.x)
                client_address = order.client_location.description

            orders_data.append({
                'id': order.id,
                'status': order.status,
                'withdrawal_type': order.withdrawal_type,
                'client_name': f"{order.client.first_name} {order.client.last_name}",
                'client_image': client_image_url,
                'client_contact_methods': contact_methods_dict,
                'store_name': order.store.name,
                
                # Datos estructurados inyectados para MerchantRouteMap
                'store_image': store_image_url,
                'store_lat': store_lat,
                'store_lng': store_lng,
                'client_lat': client_lat,
                'client_lng': client_lng,
                'client_address': client_address,
                
                'cart': order.cart,
                'creation': creation_str,
            })
        return Response({'data': orders_data}, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['post'])
    def merchant_ship_order(self, request):
        """ Permite al comerciante marcar un delivery como enviado (Status 1) """
        order_id = request.data.get('order_id')
        try:
            with transaction.atomic():
                order = (
                    Order.objects.select_for_update(of=('self',))
                    .select_related('store__company')
                    .get(id=order_id, store__company__owner=request.user)
                )
                if order.withdrawal_type != WithdrawalType.DELIVERY: # DELIVERY
                    return Response({"error": "Esta orden no requiere despacho a domicilio."}, status=status.HTTP_400_BAD_REQUEST)
                    
                if order.status != OrderStatus.WAITING: # WAITING
                    return Response({"error": "La orden ya ha cambiado de estado."}, status=status.HTTP_400_BAD_REQUEST)

                order.status = OrderStatus.DELIVERY_SENT # ENVIADO / EN CAMINO
                order.save(update_fields=['status'])
                
                # 💡 SOLUCIÓN CASO BORDE 1: Marcamos como leídas las notificaciones previas de esta orden
                Notification.objects.filter(metadata__order_id=str(order.id), is_read=False).update(is_read=True)

                client_id = order.client_id
                target_order_id = order.id
                company_name = order.store.company.name

                transaction.on_commit(
                    lambda: NotificationManager.notify_order_status_change(
                        user_id=client_id,
                        order_id=target_order_id,
                        title="¡Tu orden va en camino!",
                        body=f"El repartidor de {company_name} ha salido con tus productos.",
                        is_merchant=False,
                        new_status=OrderStatus.DELIVERY_SENT
                    )
                )
            return Response({"success": True, "message": "Orden marcada como enviada."}, status=status.HTTP_200_OK)
        except Order.DoesNotExist:
            return Response({"error": "La orden no existe o no eres el dueño del comercio."}, status=status.HTTP_404_NOT_FOUND)

    # =========================================================================
    # 💡 OBTENER TÓPICOS DIRECTO DEL CÓDIGO (Sin tocar la BD)
    # =========================================================================
    @action(detail=False, methods=['get'])
    def cancellation_topics(self, request):
        try:
            # Transformamos el Enum de Django en una lista de diccionarios para Flutter
            topics = [{'id': choice[0], 'name': str(choice[1])} for choice in CancellationReason.choices]
            return Response({'data': topics}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"Error obteniendo tópicos: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # =========================================================================
    # 💡 CANCELAR ORDEN (Con reintegro de Stock Físico y Digital)
    # =========================================================================
    @action(detail=False, methods=['post'])
    def cancel_order(self, request):
        order_id = request.data.get('order_id')
        topic_id = request.data.get('cancellation_topic_id') 

        if not order_id or not topic_id:
            return Response({"error": "Se requiere order_id y cancellation_topic_id."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            topic_id = int(topic_id)
            if topic_id not in dict(CancellationReason.choices):
                raise ValueError
        except (TypeError, ValueError):
            return Response({"error": "El motivo de cancelación seleccionado no es válido."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                order = (
                    Order.objects.select_for_update(of=('self',))
                    .select_related('store__company')
                    .get(id=order_id, client=request.user)
                )

                if order.status != OrderStatus.WAITING: 
                    return Response({"error": "Solo puedes cancelar órdenes pendientes."}, status=status.HTTP_400_BAD_REQUEST)

                # =============================================================
                # 1. REINTEGRO DE STOCK FÍSICO Y VARIANTES CON BLOQUEO ATÓMICO
                # =============================================================
                cart_items = order.cart.get('items', [])
                restored_item_ids = []
                for item in cart_items:
                    inv_item_id = item.get('inventory_item_id')
                    raw_qty = float(item.get('quantity', 0) or 0)
                    stock_units = int(item.get('stock_units_deducted') or (max(1, math.ceil(raw_qty)) if raw_qty > 0 else 0))
                    if inv_item_id and stock_units > 0:
                        try:
                            inv_item = InventoryItem.objects.select_for_update(of=('self',)).get(id=inv_item_id)
                            inv_item.stock += stock_units
                            inv_item.save(update_fields=['stock'])
                            restored_item_ids.append(inv_item.id)

                            # Si se descontó stock de una variante específica, bloqueamos Product y lo reintegramos
                            sel_var = item.get('selected_variant')
                            if isinstance(sel_var, dict) and sel_var.get('id'):
                                locked_product = Product.objects.select_for_update().get(id=inv_item.product_id)
                                if isinstance(locked_product.variants, list):
                                    updated_vars = False
                                    for v in locked_product.variants:
                                        if isinstance(v, dict) and str(v.get('id')) == str(sel_var.get('id')) and v.get('stock') is not None:
                                            try:
                                                v['stock'] = int(v['stock']) + stock_units
                                                v['is_available'] = v['stock'] > 0
                                                updated_vars = True
                                            except (ValueError, TypeError):
                                                pass
                                    if updated_vars:
                                        locked_product.save(update_fields=['variants'])
                        except (InventoryItem.DoesNotExist, Product.DoesNotExist):
                            pass 

                # =============================================================
                # 💡 2. REINTEGRO DE TOKENS (Gamificación)
                # =============================================================
                spent_transactions = TokenWalletTransaction.objects.filter(
                    order=order, 
                    transaction_type=TransactionType.OUTCOME
                )
                
                total_tokens_to_refund = sum(t.amount for t in spent_transactions)

                if total_tokens_to_refund > 0:
                    try:
                        wallet = TokenWallet.objects.select_for_update().get(
                            user=order.client, 
                            company=order.store.company
                        )
                        wallet.balance += total_tokens_to_refund
                        wallet.save(update_fields=['balance'])
                        
                        TokenWalletTransaction.objects.create(
                            token_wallet=wallet,
                            amount=total_tokens_to_refund,
                            transaction_type=TransactionType.INCOME,
                            order=order
                        )
                    except TokenWallet.DoesNotExist:
                        pass

                # =============================================================
                # 3. ACTUALIZACIÓN DE ESTADO Y NOTIFICACIONES POST-COMMIT
                # =============================================================
                order.status = OrderStatus.CANCELLED
                order.cancellation_topic = topic_id 
                order.end_time = timezone.now()
                order.save(update_fields=['status', 'cancellation_topic', 'end_time'])

                Notification.objects.filter(metadata__order_id=str(order.id), is_read=False).update(is_read=True)

                merchant_owner_id = order.store.company.owner_id
                cancelled_order_id = order.id
                cache_keys_to_del = (
                    [f"cartmaker:volatile:item:{iid}" for iid in restored_item_ids]
                    + [f"cartmaker:struct:item:{iid}" for iid in restored_item_ids]
                )

                def _post_cancel_commit():
                    if cache_keys_to_del:
                        cache.delete_many(cache_keys_to_del)
                    NotificationManager.notify_order_status_change(
                        user_id=merchant_owner_id,
                        order_id=cancelled_order_id,
                        title="Orden Cancelada",
                        body=f"El cliente ha cancelado la orden N° {cancelled_order_id}.",
                        is_merchant=True,
                        new_status=OrderStatus.CANCELLED 
                    )

                transaction.on_commit(_post_cancel_commit)

            return Response({"success": True, "message": "Orden cancelada exitosamente y stock/tokens devueltos."}, status=status.HTTP_200_OK)
        except Order.DoesNotExist:
            return Response({"error": "La orden no existe."}, status=status.HTTP_404_NOT_FOUND)

    # =========================================================================
    # 💡 MARCAR ORDEN COMO RECIBIDA Y CALIFICAR (TODO EN 1)
    # =========================================================================
    @action(detail=False, methods=['post'])
    def complete_order(self, request):
        """ Endpoint unificado de finalización con lógica de cross-notification """
        order_id = request.data.get('order_id')
        merchant_rating = request.data.get('merchant_rating', 0)
        product_ratings = request.data.get('product_ratings', [])

        try:
            with transaction.atomic():
                # Bloqueamos únicamente la fila de la orden (of=('self',)) para evitar bloqueos innecesarios en tablas relacionadas
                order = Order.objects.select_for_update(of=('self',)).select_related('store__company').get(id=order_id)
                is_client = order.client == request.user
                is_merchant = order.store.company.owner == request.user

                if not is_client and not is_merchant:
                    return Response({"error": "No tienes permisos sobre esta orden."}, status=status.HTTP_403_FORBIDDEN)

                if order.status in (OrderStatus.CANCELLED, OrderStatus.SOLVED):
                    return Response({"error": "No se puede completar una orden cancelada o cerrada."}, status=status.HTTP_400_BAD_REQUEST)

                cart_data = order.cart if isinstance(order.cart, dict) else {}
                already_completed = (order.status == OrderStatus.COMPLETED)
                client_already_rated = bool(cart_data.get('client_rated', False))

                # Si la orden ya estaba completada, solo permitimos que el cliente envíe su calificación pendiente una única vez
                if already_completed and (not is_client or client_already_rated):
                    return Response({"error": "Esta orden ya se encuentra completada."}, status=status.HTTP_400_BAD_REQUEST)

                cart_items = cart_data.get('items', [])
                tokens_earned = 0.0
                company = order.store.company

                if not already_completed:
                    order.status = OrderStatus.COMPLETED
                    order.end_time = timezone.now()

                    for item in cart_items:
                        inv_item_id = item.get('inventory_item_id')
                        raw_qty = float(item.get('quantity', 0) or 0)
                        qty = int(item.get('stock_units_deducted') or (max(1, math.ceil(raw_qty)) if raw_qty > 0 else 0))
                        
                        # 💡 EXTRAEMOS LA ETIQUETA DEL VIDEO DEL SNAPSHOT DE LA ORDEN
                        source_video_id = item.get('source_video_id')
                        
                        if inv_item_id and qty > 0:
                            try:
                                inv_item = InventoryItem.objects.get(id=inv_item_id)
                                InventoryItemTransaction.objects.create(
                                    item=inv_item,
                                    units=qty,
                                    transaction_type=TransactionType.OUTCOME
                                )
                            except InventoryItem.DoesNotExist:
                                pass # Si el producto ya no existe, ignoramos

                        # =========================================================
                        # 💡 REGISTRO DE COMPRA DE VIDEO (Atribución Real en Checkout)
                        # =========================================================
                        if source_video_id:
                            try:
                                log = VideoEngagementLog.objects.filter(
                                    client=order.client,
                                    video_id=source_video_id
                                ).order_by('-timestamp').first()

                                if log:
                                    log.bought_from_video = True
                                    log.save(update_fields=['bought_from_video'])
                                else:
                                    VideoEngagementLog.objects.create(
                                        client=order.client,
                                        video_id=source_video_id,
                                        bought_from_video=True
                                    )
                            except Exception as e:
                                print(f"❌ Error actualizando atribución de video: {e}")

                    Notification.objects.filter(metadata__order_id=str(order.id), is_read=False).update(is_read=True)

                    if company.gamification_enabled and company.gamification_tokens_per_dollar > 0:
                        order_total = max(0.0, float(cart_data.get('total', 0.0)))
                        tokens_earned = int(order_total * company.gamification_tokens_per_dollar)
                        
                        if tokens_earned > 0:
                            wallet, _ = TokenWallet.objects.select_for_update().get_or_create(
                                user=order.client,
                                company=company
                            )
                            wallet.balance += tokens_earned
                            wallet.save(update_fields=['balance'])
                            
                            TokenWalletTransaction.objects.create(
                                token_wallet=wallet, amount=tokens_earned,
                                transaction_type=TransactionType.INCOME, order=order
                            )

                # El cliente califica (una sola vez por orden, validando pertenencia y rango [1.0, 5.0])
                if is_client and not client_already_rated:
                    rated_any = False
                    try:
                        m_rating_val = float(merchant_rating or 0)
                    except (ValueError, TypeError):
                        m_rating_val = 0.0
                    if m_rating_val > 0:
                        clamped_m_rating = min(5.0, max(1.0, m_rating_val))
                        MerchantCalification.objects.create(
                            merchant=order.store.company,
                            client=request.user,
                            rating=clamped_m_rating
                        )
                        rated_any = True
                    valid_product_ids = {str(item.get('product_id')) for item in cart_items if item.get('product_id')}
                    seen_product_ids = set()
                    if isinstance(product_ratings, list):
                        for pr in product_ratings:
                            if not isinstance(pr, dict):
                                continue
                            product_id = pr.get('product_id')
                            pid_str = str(product_id) if product_id else ''
                            if not pid_str or pid_str in seen_product_ids or pid_str not in valid_product_ids:
                                continue
                            try:
                                rating_val = float(pr.get('rating', 0) or 0)
                            except (ValueError, TypeError):
                                rating_val = 0.0
                            if rating_val > 0:
                                seen_product_ids.add(pid_str)
                                clamped_p_rating = min(5.0, max(1.0, rating_val))
                                ProductCalification.objects.create(
                                    product_id=product_id,
                                    client=request.user,
                                    rating=clamped_p_rating
                                )
                                rated_any = True
                    if rated_any or not already_completed:
                        cart_data['client_rated'] = True
                        order.cart = cart_data

                order.save()

                if not already_completed:
                    owner_id = order.store.company.owner.id
                    client_id = order.client.id
                    company_name = order.store.company.name
                    oid = order.id

                    if is_client:
                        transaction.on_commit(lambda: NotificationManager.notify_order_status_change(
                            user_id=owner_id,
                            order_id=oid,
                            title="Cliente confirmó entrega",
                            body=f"El cliente de la orden N° {oid} la ha marcado como completada.",
                            is_merchant=True,
                            new_status=OrderStatus.COMPLETED
                        ))
                    elif is_merchant:
                        transaction.on_commit(lambda: NotificationManager.notify_order_status_change(
                            user_id=client_id,
                            order_id=oid,
                            title="Tu orden fue completada",
                            body=f"{company_name} ha marcado tu pedido como completado exitosamente.",
                            is_merchant=False,
                            new_status=OrderStatus.COMPLETED
                        ))

                return Response({
                    "success": True, 
                    "tokens_earned": round(float(tokens_earned), 2),
                    "message": "Orden completada con éxito."
                }, status=status.HTTP_200_OK)
        except Order.DoesNotExist:
            return Response({"error": "La orden no existe."}, status=status.HTTP_404_NOT_FOUND)


class CartViewSet(viewsets.ViewSet):
    """
    API ultra-optimizada para la gestión del carrito de compras.
    Utiliza MGET y Split Caching para resolver carritos masivos en milisegundos.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'

    @action(detail=False, methods=['post'])
    def details(self, request):
        item_ids = request.data.get('item_ids', [])

        print("ITEM IDS: ", item_ids)
        
        if not item_ids or not isinstance(item_ids, list):
            return Response({'data': []}, status=status.HTTP_200_OK)

        # =========================================================================
        # 1. CACHÉ ESTRUCTURAL (Fotos, Nombres, Empresa)
        # =========================================================================
        struct_keys = {f"cartmaker:struct:item:{uid}": uid for uid in item_ids}
        cached_structs = cache.get_many(struct_keys.keys())

        missing_ids = [uid for key, uid in struct_keys.items() if key not in cached_structs]
        struct_data_map = {uid: cached_structs[f"cartmaker:struct:item:{uid}"] for uid in item_ids if f"cartmaker:struct:item:{uid}" in cached_structs}

        # RESOLUCIÓN DE CACHE MISS (Solo va a BD por los productos que no están en RAM)
        if missing_ids:
            qs = InventoryItem.objects.select_related(
                'product', 'product__category__parent_category', 'offer', 'store__company'
            ).filter(id__in=missing_ids)
            
            new_structs_to_cache = {}
            for item in qs:
                item_json = item.get_json()
                
                # 💡 Inyección Táctica: Ponemos los datos de la empresa a mano 
                # para que el frontend de Flutter no tenga que escarbar en el JSON
                company = item.store.company
                print(f"IMAGEN DE LAA COMPNY {company}: {company.image}")
                item_json['company_info'] = {
                    'id': str(company.id),
                    'name': company.name,
                    'image': storage_manager.get_url(company.image) if company.image else None
                }

                struct_data_map[str(item.id)] = item_json
                new_structs_to_cache[f"cartmaker:struct:item:{item.id}"] = item_json
            
            if new_structs_to_cache:
                cache.set_many(new_structs_to_cache, timeout=86400) # Estructura cacheada por 24h

        # =========================================================================
        # 2. STITCHING VOLÁTIL EN TIEMPO REAL (Stock y Precios Exactos)
        # =========================================================================
        volatile_keys = {f"cartmaker:volatile:item:{uid}": uid for uid in item_ids}
        cached_volatiles = cache.get_many(volatile_keys.keys())

        final_data = []
        for uid in item_ids:
            item_data = struct_data_map.get(uid)
            if not item_data:
                continue # El ítem fue eliminado físicamente de la BD

            v_key = f"cartmaker:volatile:item:{uid}"
            state = cached_volatiles.get(v_key)

            if not state:
                state = {
                    "stock": int(item_data.get("stock", 0)),
                    "paused": bool(item_data.get("paused", False)),
                    "custom_price": item_data.get("custom_price")
                }
                cache.set(v_key, state, timeout=86400)
            
            # Fusión en RAM
            item_data["stock"] = state["stock"]
            item_data["paused"] = state["paused"]
            item_data["custom_price"] = state["custom_price"]

            final_data.append(item_data)

        return Response({'data': final_data}, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['post'])
    def create_order(self, request):
        from api.core.category_schemas import resolve_cart_item_dynamic_pricing

        if request.user.cedula_verified == False:
            return Response({
                "error": "No puedes comprar sin antes verificar tu identidad."
            }, status=status.HTTP_406_NOT_ACCEPTABLE)
        store_id = request.data.get('store_id')
        items_data = request.data.get('items', [])  # Ej: [{'id': 'uid', 'quantity': 2, 'selected_variant': ..., 'selected_modifiers': [...]}]
        withdrawal_type = request.data.get('withdrawal_type', 0)
        location_id = request.data.get('delivery_location_id')

        if not store_id or not items_data or not isinstance(items_data, list):
            return Response({
                "error": "El carrito está vacío o faltan datos para procesar tu orden."
            }, status=status.HTTP_400_BAD_REQUEST)

        # Validamos estructura y cantidades estrictamente positivas (> 0), soportando enteros y decimales (ej. 0.5 kg)
        item_qty_map = {}
        item_discount_map = {}
        items_lines_by_id = {}
        for item_entry in items_data:
            if not isinstance(item_entry, dict) or not item_entry.get('id'):
                return Response({"error": "Formato de productos inválido."}, status=status.HTTP_400_BAD_REQUEST)
            try:
                qty_val = float(item_entry.get('quantity', 0))
            except (ValueError, TypeError):
                qty_val = 0.0
            if qty_val <= 0 or math.isnan(qty_val) or math.isinf(qty_val):
                return Response({
                    "error": "La cantidad de cada producto debe ser mayor a cero."
                }, status=status.HTTP_400_BAD_REQUEST)
            entry_id = str(item_entry['id'])
            item_qty_map[entry_id] = round(item_qty_map.get(entry_id, 0.0) + qty_val, 3)
            items_lines_by_id.setdefault(entry_id, []).append(item_entry)
            if item_entry.get('selected_discount'):
                item_discount_map[entry_id] = item_entry.get('selected_discount')

        item_ids = list(item_qty_map.keys())

        # =========================================================================
        # 1. VALIDACIONES PRELIMINARES (Ahorran recursos)
        # =========================================================================
        try:
            store = CompanyStore.objects.select_related(
                'company'
            ).get(id=store_id)
            if hasattr(request.user, 'company'):
                if store.company.id == request.user.company.id:
                    return Response({
                        "error": "No puedes comprar tus mismos productos."
                    }, status=status.HTTP_406_NOT_ACCEPTABLE)
        except CompanyStore.DoesNotExist:
            return Response({
                "error": "La tienda en la que intentas comprar ya no se encuentra disponible en la plataforma."
            }, status=status.HTTP_404_NOT_FOUND)

        if not store.is_active:
            return Response({
                "error": f"Lo sentimos, {store.name} se encuentra inactiva en este momento. Por favor, intenta más tarde."
            }, status=status.HTTP_403_FORBIDDEN)

        if not store.is_currently_open:
            return Response({
                "error": "La tienda se encuentra fuera de horario laboral.",
                "work_hours": store.effective_work_hours,
                "work_days": store.effective_work_days
            }, status=status.HTTP_403_FORBIDDEN)

        # Validar que el usuario NO tenga órdenes activas en esta misma tienda
        has_active_order = Order.objects.filter(
            client=request.user, 
            store_id=store_id, 
            status=OrderStatus.WAITING
        ).exists()

        if has_active_order:
            return Response({
                "error": "ORDEN_DUPLICADA",
                "message": f"Ya tienes un pedido en curso en {store.company.name}. Por favor espera a que finalice o cancélalo si deseas modificar tu compra."
            }, status=status.HTTP_409_CONFLICT)

        # 💡 Buscamos la ubicación de forma segura
        client_location = None
        if location_id is not None:
            try:
                client_location = ClientLocation.objects.get(id=location_id, user=request.user)
            except (ClientLocation.DoesNotExist, ValueError, TypeError):
                return Response({"error": "La dirección seleccionada no es válida."}, status=status.HTTP_404_NOT_FOUND)
        elif withdrawal_type == WithdrawalType.DELIVERY:
            return Response({"error": "Debes seleccionar una dirección de entrega para pedidos con delivery."}, status=status.HTTP_400_BAD_REQUEST)

        # =========================================================================
        # 2. BLOQUEO ATÓMICO Y HARD RESERVATION
        # =========================================================================
        try:
            with transaction.atomic():
                # Filtramos explícitamente por store=store y usamos of=('self',) porque 'offer' es un OneToOne inverso (LEFT OUTER JOIN en PostgreSQL)
                inventory_items = list(
                    InventoryItem.objects.select_for_update(of=('self',))
                    .select_related('product', 'product__category', 'offer')
                    .filter(id__in=item_ids, store=store)
                )

                # 💡 CASO 1: Un producto fue borrado de la BD o no pertenece a la tienda
                if len(inventory_items) != len(item_ids):
                    found_ids = set(str(item.id) for item in inventory_items)
                    missing_ids = set(item_ids) - found_ids
                    return Response({
                        "error": "PRODUCTO_ELIMINADO",
                        "product_id": list(missing_ids)[0],
                        "message": "Uno de los productos en tu carrito fue retirado del catálogo por el vendedor. Hemos actualizado tu carrito."
                    }, status=status.HTTP_404_NOT_FOUND)

                # Bloqueamos también las filas de Product para evitar race conditions al descontar stock en Product.variants (JSON)
                locked_products_by_id = {
                    p.id: p
                    for p in Product.objects.select_for_update(of=('self',))
                    .select_related('category')
                    .filter(id__in=[it.product_id for it in inventory_items])
                }
                for it in inventory_items:
                    if it.product_id in locked_products_by_id:
                        it.product = locked_products_by_id[it.product_id]

                # Validamos en servidor los descuentos por tokens contra item.product.discounts_data real en BD
                validated_discount_map = {}
                total_tokens_needed = 0
                for item in inventory_items:
                    item_id_str = str(item.id)
                    req_discount = item_discount_map.get(item_id_str)
                    if not req_discount:
                        continue
                    if not isinstance(req_discount, dict):
                        return Response({"error": "Formato de descuento inválido."}, status=status.HTTP_400_BAD_REQUEST)
                    if not store.company.gamification_enabled or not item.product.discounts_by_tokens_active:
                        return Response({
                            "error": "DESCUENTO_NO_DISPONIBLE",
                            "message": f"Los descuentos por tokens no están habilitados para '{item.product.name}'."
                        }, status=status.HTTP_409_CONFLICT)
                    try:
                        req_tokens = int(req_discount.get('tokens', 0))
                        req_pct = float(req_discount.get('percentage', 0))
                    except (ValueError, TypeError):
                        return Response({"error": "Valores de descuento inválidos."}, status=status.HTTP_400_BAD_REQUEST)

                    matched_tier = None
                    for tier in (item.product.discounts_data or []):
                        if not isinstance(tier, dict):
                            continue
                        try:
                            tier_tokens = int(tier.get('tokens', -1))
                            tier_pct = float(tier.get('percentage', -1))
                        except (ValueError, TypeError):
                            continue
                        if tier_tokens == req_tokens and abs(tier_pct - req_pct) < 0.01 and tier_tokens > 0 and 0 < tier_pct <= 100:
                            matched_tier = {'tokens': tier_tokens, 'percentage': tier_pct}
                            break

                    if not matched_tier:
                        return Response({
                            "error": "DESCUENTO_INVALIDO",
                            "message": f"El descuento por tokens seleccionado para '{item.product.name}' ya no es válido."
                        }, status=status.HTTP_409_CONFLICT)

                    validated_discount_map[item_id_str] = matched_tier
                    total_tokens_needed += matched_tier['tokens']

                # 💡 BLOQUEO ATÓMICO 1: Validamos que el cliente SÍ tenga los tokens en esta compañía
                token_wallet = None
                if total_tokens_needed > 0:
                    try:
                        token_wallet = TokenWallet.objects.select_for_update().get(user=request.user, company=store.company)
                        if token_wallet.balance < total_tokens_needed:
                            return Response({
                                "error": "TOKENS_INSUFICIENTES",
                                "message": f"Necesitas {total_tokens_needed} tokens, pero tu saldo actual es de {token_wallet.balance} T."
                            }, status=status.HTTP_409_CONFLICT)
                    except TokenWallet.DoesNotExist:
                        return Response({
                            "error": "SIN_BILLETERA",
                            "message": "No tienes tokens registrados con este comercio."
                        }, status=status.HTTP_409_CONFLICT)

                cart_snapshot = []
                total_price = 0.0

                for item in inventory_items:
                    item_id_str = str(item.id)
                    requested_qty_total = item_qty_map[item_id_str]
                    stock_units_to_deduct = max(1, int(math.ceil(requested_qty_total)))
                    
                    # 💡 CASO 2: El producto fue pausado
                    if item.paused:
                        return Response({
                            "error": "PRODUCTO_PAUSADO",
                            "product_id": item_id_str,
                            "message": f"El vendedor acaba de pausar la venta de '{item.product.name}'. Por favor, retíralo de tu carrito para continuar."
                        }, status=status.HTTP_409_CONFLICT)
                    
                    # 💡 CASO 3: Stock agotado totalmente o parcialmente
                    if item.stock < stock_units_to_deduct:
                        if item.stock == 0:
                            msg = f"¡Ups! Alguien más acaba de comprar la última unidad de '{item.product.name}'. Lo hemos retirado de tu carrito."
                        else:
                            msg = f"Hemos ajustado tu pedido de '{item.product.name}' de {requested_qty_total:g} a {item.stock} {item.product.unit_label or 'unidades'}, que es el stock disponible actualmente."
                            
                        return Response({
                            "error": "STOCK_INSUFICIENTE",
                            "product_id": item_id_str,
                            "available_stock": item.stock,
                            "message": msg
                        }, status=status.HTTP_409_CONFLICT)
                    
                    # Todo en orden: Descontamos del inventario de la sucursal
                    item.stock -= stock_units_to_deduct
                    if item.stock <= 0:
                        item.sold_out_time = timezone.now()
                        if item.stock < 0:
                            item.stock = 0
                    item.save()

                    # Oferta estándar activa sobre el lote
                    standard_offer_pct = None
                    if hasattr(item, 'offer') and item.offer and item.offer.valid_until >= timezone.now():
                        standard_offer_pct = int(item.offer.percentage)

                    applied_token_discount = validated_discount_map.get(item_id_str)
                    if standard_offer_pct and applied_token_discount:
                        return Response({
                            "error": "OFERTAS_NO_ACUMULABLES",
                            "message": f"El producto '{item.product.name}' ya tiene una oferta de la tienda, por lo que no es acumulable con descuentos por tokens."
                        }, status=status.HTTP_409_CONFLICT)

                    img_url = storage_manager.get_url(item.product.images[0]) if item.product.images else ""
                    token_discount_already_applied_for_item = False
                    product_variants_modified = False

                    for req_line in items_lines_by_id.get(item_id_str, []):
                        line_qty_float = float(req_line.get('quantity', 1))
                        line_qty = int(line_qty_float) if line_qty_float.is_integer() else round(line_qty_float, 3)
                        line_stock_units = max(1, int(math.ceil(line_qty_float)))

                        # Cálculo dinámico de precio (variantes + modificadores/extras)
                        dynamic_unit_price, selection_meta = resolve_cart_item_dynamic_pricing(item.product, req_line)

                        # Si el InventoryItem tiene custom_price y la variante no definió precio absoluto propio,
                        # usamos custom_price como base + deltas de variante y modificadores
                        sel_var = selection_meta.get("selected_variant")
                        if item.custom_price is not None:
                            var_delta = float(sel_var.get("price_delta", 0.0)) if sel_var else 0.0
                            mod_delta = float(selection_meta.get("modifiers_total_delta", 0.0))
                            line_base_unit_price = max(0.0, float(item.custom_price) + var_delta + mod_delta)
                        else:
                            line_base_unit_price = dynamic_unit_price

                        # Validar y descontar stock específico de la variante (si el comerciante definió stock por variante)
                        if sel_var and isinstance(item.product.variants, list):
                            for raw_v in item.product.variants:
                                if isinstance(raw_v, dict) and str(raw_v.get('id')) == str(sel_var.get('id')):
                                    if raw_v.get('stock') is not None:
                                        try:
                                            v_stock = int(raw_v['stock'])
                                        except (ValueError, TypeError):
                                            v_stock = None
                                        if v_stock is not None:
                                            if v_stock < line_stock_units:
                                                return Response({
                                                    "error": "STOCK_VARIANTE_INSUFICIENTE",
                                                    "product_id": item_id_str,
                                                    "variant_id": sel_var.get("id"),
                                                    "available_stock": v_stock,
                                                    "message": f"La variante '{sel_var.get('name')}' de '{item.product.name}' solo tiene {v_stock} disponible(s)."
                                                }, status=status.HTTP_409_CONFLICT)
                                            raw_v['stock'] = max(0, v_stock - line_stock_units)
                                            raw_v['is_available'] = raw_v['stock'] > 0
                                            product_variants_modified = True
                                    break

                        if standard_offer_pct:
                            line_base_unit_price = round(
                                line_base_unit_price - (line_base_unit_price * (standard_offer_pct / 100.0)),
                                2,
                            )

                        subtotal = round(line_base_unit_price * line_qty_float, 2)

                        line_token_discount = None
                        if applied_token_discount and not token_discount_already_applied_for_item:
                            pct = float(applied_token_discount['percentage'])
                            ahorro = line_base_unit_price * (pct / 100.0)
                            subtotal = round(max(0.0, subtotal - ahorro), 2)
                            line_token_discount = applied_token_discount
                            token_discount_already_applied_for_item = True

                        source_video_id = req_line.get('source_video_id')
                        is_from_atlas = req_line.get('isFromAtlas', False)

                        # Construir título descriptivo si tiene variante (mantiene 'name' limpio y agrega 'display_name')
                        display_name = item.product.name
                        if sel_var and sel_var.get("name"):
                            display_name = f"{item.product.name} ({sel_var['name']})"

                        cart_snapshot.append({
                            "product_id": str(item.product.id),
                            "inventory_item_id": item_id_str,
                            "name": item.product.name,
                            "display_name": display_name,
                            "quantity": line_qty,
                            "stock_units_deducted": line_stock_units,
                            "selling_unit": selection_meta["selling_unit"],
                            "unit_label": selection_meta["unit_label"],
                            "unit_price": round(line_base_unit_price, 2),
                            "subtotal": subtotal,
                            "product_image": img_url,
                            "selected_variant": sel_var,
                            "selected_modifiers": selection_meta["selected_modifiers"],
                            "selected_options": selection_meta["selected_options"],
                            "customer_notes": selection_meta["customer_notes"],
                            "standard_offer_applied": standard_offer_pct,
                            "token_discount_applied": line_token_discount,
                            "source_video_id": source_video_id,
                            "is_from_atlas": is_from_atlas
                        })
                        total_price = round(total_price + subtotal, 2)

                    if product_variants_modified:
                        item.product.save(update_fields=['variants'])

                # 3. Creamos la orden oficial
                order = Order.objects.create(
                    store=store,
                    client=request.user,
                    client_location=client_location,
                    cart={"items": cart_snapshot, "total": round(total_price, 2)},
                    status=OrderStatus.WAITING, 
                    withdrawal_type=withdrawal_type
                )

                # 💡 COBRAMOS LOS TOKENS AL FINALIZAR LA ORDEN
                if token_wallet and total_tokens_needed > 0:
                    token_wallet.balance -= total_tokens_needed
                    token_wallet.save(update_fields=['balance'])
                    
                    TokenWalletTransaction.objects.create(
                        token_wallet=token_wallet,
                        amount=total_tokens_needed,
                        transaction_type=TransactionType.OUTCOME,
                        order=order
                    )
                
                # Invalidamos caché volátil y notificamos tras commit exitoso
                volatile_keys_to_del = [f"cartmaker:volatile:item:{item.id}" for item in inventory_items]
                struct_keys_to_del = [f"cartmaker:struct:item:{item.id}" for item in inventory_items]
                merchant_id = store.company.owner_id
                final_order_id = order.id
                final_store_name = store.name
                final_total = order.cart.get('total', 0.0)

                def _post_order_commit():
                    cache.delete_many(volatile_keys_to_del + struct_keys_to_del)
                    firebase_admin.NotificationManager.notify_order_created(
                        merchant_id=merchant_id,
                        order_id=final_order_id,
                        store_name=final_store_name,
                        total=final_total
                    )

                transaction.on_commit(_post_order_commit)

            return Response({
                "success": True, 
                "order_id": str(order.id), 
                "message": "¡Orden creada exitosamente!"
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.exception(f"Error en create_order: {e}")
            return Response({"error": "Ocurrió un error inesperado al procesar tu compra. Por favor, intenta de nuevo."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

