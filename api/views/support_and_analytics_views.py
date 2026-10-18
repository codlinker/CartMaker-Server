"""Support Tickets, Merchant Business Intelligence (Analytics), and Telemetry Interaction Logs."""
from .base import *
from .base import _get_cached_bcv_rate, _extract_and_validate_category_ids

####################################################
#################### VIEW SETS #####################
####################################################

class SupportTicketViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        tickets = SupportTicket.objects.filter(
            client=request.user
        ).select_related(
            'agent',
            'order',
            'order__store',
            'order__store__company',
        ).annotate(
            unread_client_count=Count(
                'messages',
                filter=Q(messages__status__lt=3) & ~Q(messages__sender_id=F('client_id'))
            ),
            unread_agent_count=Case(
                When(
                    agent__isnull=False,
                    then=Count(
                        'messages',
                        filter=Q(messages__status__lt=3) & ~Q(messages__sender_id=F('agent_id'))
                    )
                ),
                default=Count('messages'),
                output_field=IntegerField()
            )
        ).order_by('-creation')
        data = [ticket.get_json() for ticket in tickets]
        return Response({'data': data}, status=status.HTTP_200_OK)

    def create(self, request):
        if SupportTicket.objects.filter(client=request.user, closed=False).exists():
            return Response(
                {'error': 'Ya tienes un ticket de soporte en curso. Por favor, espera a que sea resuelto antes de abrir uno nuevo.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        topic_str = request.data.get('topic')
        title = request.data.get('title')
        description = request.data.get('description')

        if topic_str is None or topic_str == '' or not title or not description:
            return Response({'error': 'Faltan campos obligatorios'}, status=status.HTTP_400_BAD_REQUEST)

        TOPIC_MAP = {
            'Problema con una Orden': SupportTicket.TicketTopic.ORDER_ISSUE,
            'Reclamo sobre Tienda': SupportTicket.TicketTopic.STORE_COMPLAINT,
            'Problema con mi Cuenta': SupportTicket.TicketTopic.ACCOUNT_ISSUE,
            'Cuenta y Seguridad': SupportTicket.TicketTopic.ACCOUNT_ISSUE,
            'Privacidad y Habeas Data': SupportTicket.TicketTopic.PRIVACY_HABEAS_DATA,
            'Otro': SupportTicket.TicketTopic.OTHER,
        }
        if isinstance(topic_str, int) or (isinstance(topic_str, str) and topic_str.isdigit()):
            valid_int_choices = {choice[0] for choice in SupportTicket.TicketTopic.choices}
            topic_int = int(topic_str) if int(topic_str) in valid_int_choices else SupportTicket.TicketTopic.OTHER
        else:
            topic_int = TOPIC_MAP.get(str(topic_str).strip(), SupportTicket.TicketTopic.OTHER)

        # CART-76: Validación y vinculación opcional de la orden reportada (order_id / order)
        raw_order_id = request.data.get('order_id')
        if raw_order_id is None or str(raw_order_id).strip() == '':
            raw_order_id = request.data.get('order')

        linked_order = None
        if raw_order_id is not None:
            clean_order_id = str(raw_order_id).strip().lstrip('#').strip()
            if clean_order_id and clean_order_id.lower() not in ('null', 'none'):
                if not clean_order_id.isdigit():
                    return Response(
                        {
                            'error': 'El identificador de la orden es inválido.',
                            'order_id': ['El identificador de la orden es inválido.'],
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                linked_order = Order.objects.select_related(
                    'store', 'store__company'
                ).filter(pk=int(clean_order_id)).first()
                if not linked_order:
                    return Response(
                        {
                            'error': 'La orden seleccionada no existe.',
                            'order_id': ['La orden seleccionada no existe.'],
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                is_buyer = (linked_order.client_id == request.user.id)
                is_merchant_owner = bool(
                    linked_order.store
                    and linked_order.store.company
                    and linked_order.store.company.owner_id == request.user.id
                )
                if not (is_buyer or is_merchant_owner):
                    return Response(
                        {
                            'error': 'No puedes reportar una orden en la que no participas como comprador ni como comercio.',
                            'order_id': ['No puedes reportar una orden en la que no participas como comprador ni como comercio.'],
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        # =================================================================
        # 🧠 ALGORITMO DE ASIGNACIÓN INTELIGENTE
        # =================================================================
        
        # 1. Preguntamos a Node.js qué IDs de usuarios tienen sockets abiertos
        online_users = []
        try:
            resp = requests.get(
                f"{settings.INTERNAL_WEBSOCKETS_URL}internal/online-users", 
                headers={'X-Microservice-Token': settings.SECRET_KEY}, # o env_manager.DJANGO_SECRET_KEY
                timeout=2
            )
            if resp.status_code == 200:
                online_users = resp.json().get('online_users', [])
        except Exception as e:
            print(f"Advertencia: No se pudo conectar a Node.js para ver agentes online: {e}")

        with transaction.atomic():
            User.objects.select_for_update().get(pk=request.user.pk)
            if SupportTicket.objects.filter(client=request.user, closed=False).exists():
                return Response(
                    {'error': 'Ya tienes un ticket de soporte en curso. Por favor, espera a que sea resuelto antes de abrir uno nuevo.'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # 2. Buscamos a los SuperUsers. Filtramos primero a los que están online.
            all_agents = User.objects.filter(is_superuser=True)
            online_agents = all_agents.filter(id__in=online_users)

            # Si no hay nadie online, usamos a todos los agentes para que no quede huerfano
            agent_pool = online_agents if online_agents.exists() else all_agents

            # 3. Anotamos cuántos tickets ABIERTOS tiene asignados cada uno y sacamos al que tenga menos
            best_agent = agent_pool.annotate(
                active_tickets=Count('assigned_tickets', filter=Q(assigned_tickets__closed=False))
            ).order_by('active_tickets').first()

            # 4. Creamos el ticket ya asignado desde el nacimiento
            ticket = SupportTicket.objects.create(
                client=request.user,
                agent=best_agent,
                order=linked_order,
                topic=topic_int,
                title=title,
                description=description
            )

            ticket_json = ticket.get_json()

        # 5. Si encontramos agente, disparamos las alertas en tiempo real mediante Node.js
        if best_agent:
            try:
                requests.post(
                    f"{settings.INTERNAL_WEBSOCKETS_URL}internal/emit-assignment",
                    json={
                        'ticket': ticket_json, 
                        'agent_id': str(best_agent.id),
                        'client_id': str(request.user.id)
                    },
                    headers={'X-Microservice-Token': settings.SECRET_KEY},
                    timeout=2
                )
            except Exception:
                pass

        return Response({'success': True, 'data': ticket_json, **ticket_json}, status=status.HTTP_201_CREATED)

class AnalyticsViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    ANALYTICS_CACHE_TTL = 300  # 5 minutos

    # =========================================================================
    # 1. IMPACTO FINANCIERO Y RETORNO DE INVERSIÓN (ROI)
    # =========================================================================
    @action(detail=False, methods=['get'])
    def roi_impact(self, request):
        company = Company.objects.filter(owner=request.user).first()
        if not company:
            return Response({'error': 'Compañía no encontrada.'}, status=status.HTTP_404_NOT_FOUND)

        cache_key = f"cm:analytics:roi_impact:{company.id}"
        cached_payload = cache.get(cache_key)
        if cached_payload is not None:
            return Response(cached_payload, status=status.HTTP_200_OK)

        time_horizon = timezone.now() - timedelta(days=30)

        # --- 1. EMBUDO BASE (Vistas analíticas agregadas) ---
        total_views = ProductViewLog.objects.filter(
            inventory_item__store__company=company,
            start_time__gte=time_horizon
        ).count()

        # --- 2. TRANSMUTACIÓN FINANCIERA DESDE DIARIO DE INVENTARIO ---
        # Buscamos exclusivamente los EGRESOS (OUTCOME) que representan las ventas en CartMaker
        sales_transactions = InventoryItemTransaction.objects.filter(
            item__store__company=company,
            transaction_type=TransactionType.OUTCOME,
            creation__gte=time_horizon
        ).select_related('item__product', 'item__store')

        total_revenue = 0.0
        total_items_sold = 0
        
        organic_sales_count = 0
        atlas_sales_count = 0
        video_sales_count = 0

        product_financials = {}

        # Pre-cargamos en lote los timestamps de engagement de video y de Atlas IA para eliminar N+1 queries
        video_engagement_rows = VideoEngagementLog.objects.filter(
            video__company=company,
            video__associated_item__isnull=False,
            timestamp__gte=time_horizon - timedelta(hours=2)
        ).values_list('video__associated_item_id', 'timestamp')
        video_ts_by_item = {}
        for item_id_val, ts_val in video_engagement_rows:
            video_ts_by_item.setdefault(item_id_val, []).append(ts_val)

        atlas_view_rows = ProductViewLog.objects.filter(
            inventory_item__store__company=company,
            origin_source='atlas',
            start_time__gte=time_horizon - timedelta(days=7)
        ).values_list('inventory_item_id', 'start_time')
        atlas_ts_by_item = {}
        for item_id_val, ts_val in atlas_view_rows:
            atlas_ts_by_item.setdefault(item_id_val, []).append(ts_val)

        for trans in sales_transactions:
            qty = abs(trans.units)
            total_items_sold += qty

            # Deducción del precio basada en la jerarquía del inventario (Custom vs Base)
            price = float(trans.item.custom_price if trans.item.custom_price else trans.item.product.price)
            subtotal = qty * price
            total_revenue += subtotal

            # --- ATRIBUCIÓN LOGÍSTICA-TELEMETRÍCA (Sin Tabla de Órdenes) ---
            # Correlacionamos el momento exacto del egreso con los logs de interacción del cliente
            is_attributed = False
            tx_time = trans.creation
            window_video_start = tx_time - timedelta(hours=2)

            # A. Verificación de canal de Video Historias (Ventana de interacción de 2 horas previas)
            has_video_engagement = any(
                window_video_start <= ts <= tx_time
                for ts in video_ts_by_item.get(trans.item_id, ())
            )

            if has_video_engagement:
                video_sales_count += qty
                is_attributed = True

            # B. Verificación de recomendación de Atlas IA (Ventana de influencia de 7 días previos)
            if not is_attributed:
                window_atlas_start = tx_time - timedelta(days=7)
                has_atlas_influence = any(
                    window_atlas_start <= ts <= tx_time
                    for ts in atlas_ts_by_item.get(trans.item_id, ())
                )

                if has_atlas_influence:
                    atlas_sales_count += qty
                    is_attributed = True

            # C. Fallback: Si no hay marcas telemétricas, la venta es puramente Orgánica
            if not is_attributed:
                organic_sales_count += qty

            # --- MASTRUZACIÓN DEL RANKING FINANCIERO ---
            pid = str(trans.item.product.id)
            if pid not in product_financials:
                product_financials[pid] = {
                    'id': pid,
                    'name': trans.item.product.name,
                    'image': storage_manager.get_url(trans.item.product.images[0]) if trans.item.product.images else None,
                    'units_sold': 0,
                    'revenue': 0.0
                }
            product_financials[pid]['units_sold'] += qty
            product_financials[pid]['revenue'] += subtotal

        # Tasa de conversión basada en flujos reales
        conversion_rate = round((total_items_sold / total_views * 100), 2) if total_views > 0 else 0.0
        top_products = sorted(product_financials.values(), key=lambda x: x['revenue'], reverse=True)[:5]

        # Vender ya no tiene costo de plan. Las claves del JSON se conservan.
        plan_cost = 0.0
        roi_percentage = 0.0
        is_profitable = total_revenue >= plan_cost

        insights = {'roi': None, 'origin': None, 'products': None}

        if total_items_sold > 0:
            if atlas_sales_count >= organic_sales_count and atlas_sales_count >= video_sales_count:
                insights['origin'] = "Estoy conectando exitosamente tus productos con los clientes ideales mediante el chat. Mantén tus precios al día."
            elif video_sales_count >= organic_sales_count:
                insights['origin'] = "Tus Video Historias están liderando la conversión de existencias. Sigue explotando tu vitrina visual."
            else:
                insights['origin'] = "Tus clientes retiran stock principalmente por búsquedas orgánicas. Tienes buen posicionamiento local."

        if top_products:
            insights['products'] = f"'{top_products[0]['name']}' es el motor de tu negocio este mes. Vigila de cerca su inventario en tiempo real."

        payload = {
            'data': {
                'funnel': {
                    'views': total_views,
                    'sales': total_items_sold,
                    'conversion_rate': conversion_rate
                },
                'sales_distribution': {
                    'organic': organic_sales_count,
                    'atlas': atlas_sales_count,
                    'video': video_sales_count
                },
                'revenue_and_roi': {
                    'total_revenue_usd': round(total_revenue, 2),
                    'plan_cost_usd': plan_cost,
                    'roi_percentage': roi_percentage,
                    'is_profitable': is_profitable
                },
                'top_products': top_products,
                'insights': insights
            }
        }
        cache.set(cache_key, payload, timeout=self.ANALYTICS_CACHE_TTL)
        return Response(payload, status=status.HTTP_200_OK)

    # =========================================================================
    # 2. RENDIMIENTO DE CONTENIDO (Video Stories Metrics)
    # =========================================================================
    @action(detail=False, methods=['get'])
    def content_performance(self, request):
        company = Company.objects.filter(owner=request.user).first()
        if not company:
            return Response({'error': 'Compañía no encontrada.'}, status=status.HTTP_404_NOT_FOUND)

        cache_key = f"cm:analytics:content_perf:{company.id}"
        cached_payload = cache.get(cache_key)
        if cached_payload is not None:
            return Response(cached_payload, status=status.HTTP_200_OK)

        time_horizon = timezone.now() - timedelta(days=30)
        logs = list(VideoEngagementLog.objects.filter(video__company=company, timestamp__gte=time_horizon))

        total_views = len(logs)
        completed_views = sum(1 for l in logs if l.video_completed)
        abandoned_views = total_views - completed_views
        interacted = sum(1 for l in logs if l.interacted_with_product)
        added_to_cart = sum(1 for l in logs if l.added_to_cart_from_video)
        
        completion_rate = round((completed_views / total_views * 100), 1) if total_views > 0 else 0.0

        video_stats = {}
        total_video_revenue = 0.0
        total_watch_time_seconds_clean = 0.0

        company_videos = list(CompanyVideoStory.objects.filter(company=company))
        for v in company_videos:
            video_stats[str(v.id)] = {
                'id': str(v.id),
                'description': v.description or 'Video sin descripción',
                'thumbnail': storage_manager.get_url(v.thumbnail) if v.thumbnail else None,
                'duration_seconds': v.duration_seconds,
                'views': 0, 'completions': 0, 'watch_time_seconds': 0.0,
                'revenue': 0.0, 'units_sold': 0, 'interacted': 0
            }

        purchase_ts_by_video = {}
        for log in logs:
            vid = str(log.video_id)
            if log.bought_from_video:
                purchase_ts_by_video.setdefault(vid, []).append(log.timestamp)
            if vid in video_stats:
                video_stats[vid]['views'] += 1
                
                real_duration = video_stats[vid]['duration_seconds']
                logged_time = log.watch_time_seconds
                
                if real_duration > 0 and logged_time > real_duration:
                    capped_time = real_duration
                else:
                    capped_time = logged_time
                    
                video_stats[vid]['watch_time_seconds'] += capped_time
                total_watch_time_seconds_clean += capped_time

                if log.video_completed: video_stats[vid]['completions'] += 1
                if log.interacted_with_product: video_stats[vid]['interacted'] += 1

        # --- AUDITORÍA DE FACTURACIÓN POR VIDEO USANDO DIARIO CONTABLE (SIN N+1) ---
        associated_item_ids = {v.associated_item_id for v in company_videos if v.associated_item_id}
        txs_by_item = {}
        if associated_item_ids:
            all_related_txs = InventoryItemTransaction.objects.filter(
                item_id__in=associated_item_ids,
                transaction_type=TransactionType.OUTCOME,
                creation__gte=time_horizon
            ).select_related('item__product')
            for tx in all_related_txs:
                txs_by_item.setdefault(tx.item_id, []).append(tx)

        for v in company_videos:
            vid = str(v.id)
            if v.associated_item_id and v.associated_item_id in txs_by_item:
                vid_purchase_ts = purchase_ts_by_video.get(vid, ())
                if not vid_purchase_ts:
                    continue
                for tx in txs_by_item[v.associated_item_id]:
                    window_start = tx.creation - timedelta(hours=2)
                    has_purchase_log = any(window_start <= ts <= tx.creation for ts in vid_purchase_ts)
                    if has_purchase_log:
                        units = abs(tx.units)
                        price = float(tx.item.custom_price if tx.item.custom_price else tx.item.product.price)
                        revenue_tx = units * price
                        
                        video_stats[vid]['units_sold'] += units
                        video_stats[vid]['revenue'] += revenue_tx
                        total_video_revenue += revenue_tx

        top_videos = sorted(
            [v for v in video_stats.values() if v['views'] > 0 or v['revenue'] > 0], 
            key=lambda x: (x['revenue'], x['views']), 
            reverse=True
        )[:5]

        # Generación de insights telemétricos
        insights = {'funnel': None, 'retention': None, 'top': None}
        if total_views > 0:
            click_rate = interacted / total_views
            if click_rate < 0.05:
                insights['funnel'] = "Tus videos captan atención, pero no derivan clics al producto. Ajusta tu llamado a la acción."
            elif (added_to_cart / interacted) >= 0.3:
                insights['funnel'] = "¡Conversión óptima desde el reproductor! El contenido multimedia es altamente persuasivo."
                
            if completion_rate < 20:
                insights['retention'] = "Los usuarios abandonan el clip rápido. Intenta condensar el mensaje clave en menos segundos."

        if top_videos and top_videos[0]['revenue'] > 0:
            top_desc = top_videos[0]['description']
            clean_desc = top_desc[:25] + "..." if len(top_desc) > 25 else top_desc
            insights['top'] = f"Tu video '{clean_desc}' lidera los ingresos de almacén. Replica su estilo visual."

        payload = {
            'data': {
                'global_metrics': {
                    'total_views': total_views,
                    'completed_views': completed_views,
                    'abandoned_views': abandoned_views,
                    'total_watch_time_minutes': round(total_watch_time_seconds_clean / 60, 1),
                    'completion_rate': completion_rate,
                    'total_video_revenue': round(total_video_revenue, 2),
                },
                'funnel': {
                    'views': total_views,
                    'interacted': interacted,
                    'added_to_cart': added_to_cart,
                },
                'top_videos': top_videos,
                'insights': insights
            }
        }
        cache.set(cache_key, payload, timeout=self.ANALYTICS_CACHE_TTL)
        return Response(payload, status=status.HTTP_200_OK)

    # =========================================================================
    # 3. MOTOR DE FIDELIZACIÓN (Gamificación y Retención Telemétrica)
    # =========================================================================
    @action(detail=False, methods=['get'])
    def loyalty_performance(self, request):
        company = Company.objects.filter(owner=request.user).first()
        if not company:
            return Response({'error': 'Compañía no encontrada.'}, status=status.HTTP_404_NOT_FOUND)

        cache_key = f"cm:analytics:loyalty_perf:{company.id}"
        cached_payload = cache.get(cache_key)
        if cached_payload is not None:
            return Response(cached_payload, status=status.HTTP_200_OK)

        time_horizon = timezone.now() - timedelta(days=30)
        
        # --- 1. AUDITORÍA DE TOKENS ---
        tokens_emitted = TokenWalletTransaction.objects.filter(
            token_wallet__company=company,
            transaction_type=TransactionType.INCOME,
            creation__gte=time_horizon
        ).aggregate(Sum('amount'))['amount__sum'] or 0

        tokens_redeemed = TokenWalletTransaction.objects.filter(
            token_wallet__company=company,
            transaction_type=TransactionType.OUTCOME,
            creation__gte=time_horizon
        ).aggregate(Sum('amount'))['amount__sum'] or 0

        # --- 2. RETENCIÓN MEDIANTE LOGS DE TRÁFICO COMPRADOR ---
        # Usamos los logs analíticos donde se marca 'bought=True' para identificar clientes recurrentes
        purchase_logs_30d = ProductViewLog.objects.filter(
            inventory_item__store__company=company,
            bought=True,
            start_time__gte=time_horizon
        ).values('client').annotate(purchase_count=Count('id'))

        all_time_purchases = ProductViewLog.objects.filter(
            inventory_item__store__company=company,
            bought=True
        ).values('client').annotate(total_purchases=Count('id'))
        
        history_map = {item['client']: item['total_purchases'] for item in all_time_purchases}
        
        new_customers = 0
        returning_customers = 0
        vip_data = {}

        for log in purchase_logs_30d:
            client_id = log['client']
            if history_map.get(client_id, 0) > 1:
                returning_customers += 1
            else:
                new_customers += 1

        # --- 3. EXTRACCIÓN VIP Y ANALÍTICA DE GAMIFICACIÓN (EN LOTE, SIN N+1) ---
        gamified_sales_txs = InventoryItemTransaction.objects.filter(
            item__store__company=company,
            item__product__discounts_by_tokens_active=True,
            transaction_type=TransactionType.OUTCOME,
            creation__gte=time_horizon
        ).select_related('item__product')

        gamified_products_stats = {}
        revenue_from_token_orders = 0.0

        for tx in gamified_sales_txs:
            item = tx.item
            qty = abs(tx.units)
            price = float(item.custom_price if item.custom_price else item.product.price)
            subtotal = qty * price
            
            # Si hubo tokens redimidos en la ventana de tiempo, asumimos impacto del programa
            if tokens_redeemed > 0:
                revenue_from_token_orders += subtotal

            pid = str(item.product.id)
            if pid not in gamified_products_stats:
                gamified_products_stats[pid] = {
                    'id': pid,
                    'name': item.product.name,
                    'image': storage_manager.get_url(item.product.images[0]) if item.product.images else None,
                    'units_sold': 0,
                    'revenue': 0.0,
                    'discount_investment': 0.0
                }
            gamified_products_stats[pid]['units_sold'] += qty
            gamified_products_stats[pid]['revenue'] += subtotal

        # Construcción sintética del Top VIP basado en volumen analítico de compras
        top_vips_logs = ProductViewLog.objects.filter(
            inventory_item__store__company=company,
            bought=True,
            start_time__gte=time_horizon
        ).select_related('client').values(
            'client__id', 'client__first_name', 'client__last_name', 'client__profile_picture'
        ).annotate(total_purchases=Count('id'))[:5]

        top_vips = []
        for v in top_vips_logs:
            top_vips.append({
                'id': str(v['client__id']),
                'name': f"{v['client__first_name']} {v['client__last_name']}",
                'image': storage_manager.get_url(v['client__profile_picture']) if v['client__profile_picture'] else None,
                'orders': v['total_purchases'],
                'spent': 0.0  # Mantenemos firma del contrato de la API
            })

        top_gamified_products = sorted(gamified_products_stats.values(), key=lambda x: x['revenue'], reverse=True)[:10]

        # Insights contextuados
        insights = {'tokens': None, 'retention': None, 'general': None, 'products': None}
        if not company.gamification_enabled:
            insights['general'] = "No tienes la gamificación activada. Enciende los tokens para empezar a fidelizar clientes."
        else:
            if tokens_redeemed > 0:
                insights['tokens'] = "¡El sistema de fidelización funciona! Los clientes están retornando para liberar sus puntos."
            
            if returning_customers > new_customers:
                insights['retention'] = "¡Excelente retención telemétrica! Tienes una base de compradores altamente recurrentes."

        payload = {
            'data': {
                'gamification_enabled': company.gamification_enabled,
                'tokens': {
                    'emitted': tokens_emitted,
                    'redeemed': tokens_redeemed,
                    'revenue_from_token_orders': round(revenue_from_token_orders, 2)
                },
                'retention': {
                    'new_customers': new_customers,
                    'returning_customers': returning_customers
                },
                'top_vips': top_vips,
                'gamified_products': top_gamified_products,
                'insights': insights
            }
        }
        cache.set(cache_key, payload, timeout=self.ANALYTICS_CACHE_TTL)
        return Response(payload, status=status.HTTP_200_OK)

    # =========================================================================
    # 4. RADAR DE OPORTUNIDADES COMERCIALES (Geolocalización Analítica)
    # =========================================================================
    @action(detail=False, methods=['get'])
    def opportunities_radar(self, request):
        company = Company.objects.filter(owner=request.user).first()
        if not company:
            return Response({'error': 'Compañía no encontrada.'}, status=status.HTTP_404_NOT_FOUND)

        cache_key = f"cm:analytics:opp_radar:{company.id}"
        cached_payload = cache.get(cache_key)
        if cached_payload is not None:
            return Response(cached_payload, status=status.HTTP_200_OK)

        time_horizon = timezone.now() - timedelta(days=30)
        
        main_store = CompanyStore.objects.filter(company=company, is_main_store=True).select_related('location').first()
        if not main_store or not hasattr(main_store, 'location'):
            main_store = CompanyStore.objects.filter(company=company).select_related('location').first()
            
        if not main_store or not hasattr(main_store, 'location') or not main_store.location.coordinates:
            return Response({'error': 'Tu comercio no tiene una ubicación configurada para generar el radar.'}, status=status.HTTP_400_BAD_REQUEST)

        center_point = main_store.location.coordinates

        from django.contrib.gis.measure import D
        unmet_logs = UnmetDemandLog.objects.filter(
            creation__gte=time_horizon,
            coordinates__distance_lte=(center_point, D(km=15))
        )

        total_missed_searches = unmet_logs.count()
        top_terms = unmet_logs.values('search_term').annotate(count=Count('id')).order_by('-count')[:20]
        top_keywords = [{'term': item['search_term'].capitalize(), 'count': item['count']} for item in top_terms]

        features = []
        for log in unmet_logs:
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [log.coordinates.x, log.coordinates.y]
                },
                "properties": {
                    "weight": 1.0,
                    "term": log.search_term.capitalize() 
                }
            })
            
        heatmap_geojson = {
            "type": "FeatureCollection",
            "features": features
        }

        insights = {'radar': None, 'action': None}
        if total_missed_searches == 0:
            insights['radar'] = "Por ahora no detecto búsquedas fallidas relevantes cerca de tu ubicación."
        else:
            insights['radar'] = f"Detecté {total_missed_searches} clientes potenciales buscando productos sin stock en tu rango de entrega."
            if top_keywords:
                insights['action'] = f"La oportunidad de oro es '{top_keywords[0]['term']}'. Satisface esta demanda para dominar la zona."

        payload = {
            'data': {
                'center_lat': center_point.y,
                'center_lng': center_point.x,
                'total_missed_searches': total_missed_searches,
                'top_keywords': top_keywords,
                'heatmap_geojson': heatmap_geojson,
                'insights': insights
            }
        }
        cache.set(cache_key, payload, timeout=self.ANALYTICS_CACHE_TTL)
        return Response(payload, status=status.HTTP_200_OK)

    # =========================================================================
    # 5. GESTIÓN OPERATIVA DE SUCURSALES (Finanzas desde el Inventario)
    # =========================================================================
    @action(detail=False, methods=['get'])
    def operative_management(self, request):
        company = Company.objects.filter(owner=request.user).first()
        if not company:
            return Response({'error': 'Compañía no encontrada.'}, status=status.HTTP_404_NOT_FOUND)

        cache_key = f"cm:analytics:op_mgmt:{company.id}"
        cached_payload = cache.get(cache_key)
        if cached_payload is not None:
            return Response(cached_payload, status=status.HTTP_200_OK)

        time_horizon = timezone.now() - timedelta(days=30)
        
        # Traemos todas las transacciones de venta (OUTCOME) del mes con item__product pre-cargado
        sales_txs = list(InventoryItemTransaction.objects.filter(
            item__store__company=company,
            transaction_type=TransactionType.OUTCOME,
            creation__gte=time_horizon
        ).select_related('item__store', 'item__product'))

        total_revenue = 0.0
        # Consideramos cada transacción contable de venta como una entrada en caja
        total_sales_records = len(sales_txs)

        branches_data = {}
        stores = CompanyStore.objects.filter(company=company).annotate(
            total_items_count=Count('product_items'),
            low_stock_items_count=Count('product_items', filter=Q(product_items__stock__lte=5))
        )
        
        for store in stores:
            total_items = store.total_items_count
            low_stock_items = store.low_stock_items_count
            
            health_status = "Estable"
            if total_items > 0:
                low_pct = low_stock_items / total_items
                if low_pct > 0.5:
                    health_status = "Bajo"
                elif low_pct > 0.2:
                    health_status = "Medio"

            store_image = storage_manager.get_url(store.store_img_url) if store.store_img_url else ""
            
            branches_data[store.id] = {
                'id': str(store.id),
                'name': store.name,
                'orders': 0,
                'image': store_image,
                'revenue': 0.0,
                'inventory_health': health_status
            }

        # Procesamos los ingresos reales calculados desde el diario de stock
        for tx in sales_txs:
            qty = abs(tx.units)
            price = float(tx.item.custom_price if tx.item.custom_price else tx.item.product.price)
            subtotal = qty * price
            
            total_revenue += subtotal
            
            store_id = tx.item.store_id
            if store_id in branches_data:
                branches_data[store_id]['orders'] += 1
                branches_data[store_id]['revenue'] += subtotal

        average_ticket = round(total_revenue / total_sales_records, 2) if total_sales_records > 0 else 0.0
        sorted_branches = sorted(branches_data.values(), key=lambda x: x['revenue'], reverse=True)

        insights = {'accounting': None, 'branches': None}
        if total_sales_records > 0:
            if average_ticket > 20:
                insights['accounting'] = f"Tu ticket promedio de ${average_ticket} basado en flujo de stock es muy sólido."
            else:
                insights['accounting'] = f"Tu ticket promedio es de ${average_ticket}. Incentiva compras de mayor volumen."
                
            if len(sorted_branches) > 1 and sorted_branches[0]['revenue'] > 0:
                insights['branches'] = f"La sede '{sorted_branches[0]['name']}' lidera la facturación física."

        payload = {
            'data': {
                'accounting': {
                    'total_revenue': round(total_revenue, 2),
                    'total_orders': total_sales_records,
                    'average_ticket': average_ticket
                },
                'branches': sorted_branches,
                'insights': insights
            }
        }
        cache.set(cache_key, payload, timeout=self.ANALYTICS_CACHE_TTL)
        return Response(payload, status=status.HTTP_200_OK)

    # =========================================================================
    # 6. LIBRO MAYOR DETALLADO (Soporta VENTA, INGRESO STOCK y CREACION)
    # =========================================================================
    @action(detail=False, methods=['get'])
    def detailed_ledger(self, request):
        company = Company.objects.filter(owner=request.user).first()
        if not company:
            return Response({'error': 'Compañía no encontrada.'}, status=status.HTTP_404_NOT_FOUND)

        store_id = request.query_params.get('store_id', None)
        page = int(request.query_params.get('page', 1))
        is_export = request.query_params.get('export', 'false').lower() == 'true'
        limit = 10
        
        time_horizon = timezone.now() - timedelta(days=30)

        # Query limpia unificada: Traemos todo ordenado por fecha de creación decreciente
        queryset = InventoryItemTransaction.objects.filter(
            item__store__company=company,
            creation__gte=time_horizon
        ).select_related(
            'item__product', 
            'item__store'
        ).order_by('-creation')

        if store_id and store_id != 'all':
            queryset = queryset.filter(item__store_id=store_id)

        total_items = queryset.count()
        total_pages = (total_items + limit - 1) // limit if total_items > 0 else 1

        if not is_export:
            start_idx = (page - 1) * limit
            end_idx = start_idx + limit
            transactions = queryset[start_idx:end_idx]
        else:
            transactions = queryset

        ledger = []
        for trans in transactions:
            qty_val = abs(trans.units)
            
            # CASO A: Egresos (Ventas)
            if trans.transaction_type == TransactionType.OUTCOME:
                price = float(trans.item.custom_price if trans.item.custom_price else trans.item.product.price)
                gross = round(price * qty_val, 2)
                
                ledger.append({
                    'date': trans.creation,
                    'type': 'VENTA',
                    'store': trans.item.store.name,
                    'product': trans.item.product.name,
                    'qty': f"-{qty_val}",
                    'gross_amount': gross,
                    'discount_amount': 0.0,
                    'net_revenue': gross,
                    'origin': 'Venta Regular',
                    'client_or_reason': 'Cliente CartMaker',
                    'details': 'Procesado en caja / Checkout'
                })
                
            # CASO B: Ingresos por reposición de stock
            elif trans.transaction_type == TransactionType.INCOME:
                ledger.append({
                    'date': trans.creation,
                    'type': 'INGRESO STOCK',
                    'store': trans.item.store.name,
                    'product': trans.item.product.name,
                    'qty': f"+{qty_val}",
                    'gross_amount': 0.0,
                    'discount_amount': 0.0,
                    'net_revenue': 0.0,
                    'origin': 'Operativo',
                    'client_or_reason': 'Abastecimiento / Proveedor',
                    'details': 'Carga manual de inventario para reponer stock'
                })
                
            # 💡 CASO C: Registro del Lote Inicial de Creación del Producto
            elif trans.transaction_type == TransactionType.CREATION:
                ledger.append({
                    'date': trans.creation,
                    'type': 'CREACION LOTE',
                    'store': trans.item.store.name,
                    'product': trans.item.product.name,
                    'qty': f"+{qty_val}",
                    'gross_amount': 0.0,
                    'discount_amount': 0.0,
                    'net_revenue': 0.0,
                    'origin': 'Operativo',
                    'client_or_reason': 'Registro Inicial',
                    'details': 'Lote de inventario inicial creado en el sistema'
                })

        for entry in ledger:
            entry['date'] = timezone.localtime(entry['date']).strftime("%d/%m/%Y %I:%M %p")

        return Response({
            'data': {
                'ledger': ledger,
                'pagination': {
                    'current_page': page,
                    'total_pages': total_pages,
                    'has_next': page < total_pages,
                    'has_previous': page > 1,
                    'total_records': total_items
                }
            }
        }, status=status.HTTP_200_OK)

    # =========================================================================
    # 7. INVENTARIO VIVO DE SUCURSAL (Para Modal en Flutter)
    # =========================================================================
    @action(detail=False, methods=['get'])
    def branch_inventory(self, request):
        store_id = request.query_params.get('store_id')
        if not store_id:
            return Response({'error': 'ID de sucursal requerido.'}, status=status.HTTP_400_BAD_REQUEST)
            
        company = Company.objects.filter(owner=request.user).first()
        
        items = InventoryItem.objects.filter(
            store_id=store_id, 
            store__company=company,
            paused=False
        ).select_related('product')
        
        data = []
        for item in items:
            img_url = storage_manager.get_url(item.product.images[0]) if item.product.images else ""
            data.append({
                'id': str(item.id),
                'name': item.product.name,
                'stock': item.stock,
                'image': img_url
            })
            
        data.sort(key=lambda x: x['stock'])
        return Response({'data': data}, status=status.HTTP_200_OK)


class InteractionLogViewSet(viewsets.ViewSet):
    """
    API dedicada a registrar silenciosamente la telemetría del usuario en la App.
    Alimenta los modelos de Machine Learning y el Algoritmo de Recomendación.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'

    # ==========================================
    # HELPER: Procesador de Fechas
    # ==========================================
    def _parse_aware_datetime(self, datetime_raw):
        """
        Toma un string ISO, lo convierte a objeto datetime y se asegura
        de que sea 'aware' (consciente de la zona horaria del servidor)
        para evitar RuntimeWarnings de Django.
        """
        if not datetime_raw:
            return None
        
        parsed = parse_datetime(str(datetime_raw))
        if parsed and timezone.is_naive(parsed):
            return timezone.make_aware(parsed)
        return parsed

    # ==========================================
    # ENDPOINTS
    # ==========================================
    @action(detail=False, methods=['post'])
    def product_view(self, request):
        """
        Registra el Dwell Time e interacciones. Envía los datos a un Buffer en Redis.
        """
        data = request.data
        item_id = data.get('item_id')
        start_time_raw = data.get('start_time')

        if not item_id or not start_time_raw:
            return Response({'error': 'item_id y start_time son obligatorios.'}, status=status.HTTP_400_BAD_REQUEST)

        # Preparamos el payload añadiendo el ID del usuario y metadatos de atribución (Atlas IA / Orgánico)
        payload = {
            'client_id': str(request.user.id),
            'item_id': str(item_id),
            'added_to_cart': data.get('added_to_cart', False),
            'bought': data.get('bought', False),
            'start_time': start_time_raw,
            'end_time': data.get('end_time'),
            'origin_source': data.get('origin_source', 'organic'),
            'search_prompt': data.get('search_prompt'),
            'ai_keywords': data.get('ai_keywords'),
            'atlas_message_id': data.get('atlas_message_id'),
        }

        try:
            # Empujamos a la lista de Redis
            redis_conn = cache.client.get_client()
            redis_conn.rpush("telemetry:product_views", json.dumps(payload))
            return Response(status=status.HTTP_202_ACCEPTED) # 202 significa "Aceptado para procesamiento"
            
        except Exception as e:
            print(f"Error al encolar analítica en Redis: {e}")
            return Response({'error': 'Error interno'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def store_view(self, request):
        """
        Registra el comportamiento del usuario dentro del perfil de una tienda.
        """
        data = request.data
        store_id = data.get('store_id')
        join_time_raw = data.get('join_time')

        if not store_id or not join_time_raw:
            return Response({'error': 'store_id y join_time son obligatorios.'}, status=status.HTTP_400_BAD_REQUEST)

        payload = {
            'client_id': str(request.user.id),
            'store_id': str(store_id),
            'join_time': join_time_raw,
            'exit_time': data.get('exit_time'),
            'location_watched': data.get('location_watched', False),
            'presentation_video_watched': data.get('presentation_video_watched', False),
            'stories_watched': data.get('stories_watched', False),
            'products_watched': data.get('products_watched', False),
            'tryed_to_contact': data.get('tryed_to_contact', False)
        }

        try:
            redis_conn = cache.client.get_client()
            redis_conn.rpush("telemetry:store_views", json.dumps(payload))
            return Response(status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            print(f"Error al encolar analítica de store_view: {e}")
            return Response({'error': 'Error interno'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def navigation(self, request):
        """
        Registra el mapa de pantallas que el usuario visitó durante su sesión.
        """
        data = request.data
        navigation_record = data.get('navigation_record', {})
        login_time_raw = data.get('login_time')

        if not login_time_raw:
            return Response({'error': 'login_time es obligatorio.'}, status=status.HTTP_400_BAD_REQUEST)

        payload = {
            'client_id': str(request.user.id),
            'navigation_record': navigation_record,
            'login_time': login_time_raw,
            'logout_time': data.get('logout_time')
        }

        try:
            redis_conn = cache.client.get_client()
            redis_conn.rpush("telemetry:navigation_logs", json.dumps(payload))
            return Response(status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            print(f"Error al encolar analítica de navigation: {e}")
            return Response({'error': 'Error interno'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def video_engagement(self, request):
        """
        Registra interacciones de video y acumula el tiempo de visualización.
        """
        data = request.data
        video_id = data.get('video_id')
        
        if not video_id:
            return Response({'error': 'video_id es obligatorio.'}, status=status.HTTP_400_BAD_REQUEST)

        # Blindaje de parseo booleano desde Flutter
        def parse_bool(val):
            return str(val).lower() == 'true' if isinstance(val, str) else bool(val)

        payload = {
            'client_id': str(request.user.id),
            'video_id': str(video_id),
            'watch_time_seconds': float(data.get('watch_time_seconds', 0.0)),
            'video_completed': parse_bool(data.get('video_completed', False)),
            'interacted_with_product': parse_bool(data.get('interacted_with_product', False)),
            'added_to_cart_from_video': parse_bool(data.get('added_to_cart_from_video', False)),
            'bought_from_video': parse_bool(data.get('bought_from_video', False))
        }

        try:
            redis_conn = cache.client.get_client()
            redis_conn.rpush("telemetry:video_engagement", json.dumps(payload))
            return Response({'success': True}, status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            print(f"Error al encolar analítica de video_engagement: {e}")
            return Response({'error': 'Error interno'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

