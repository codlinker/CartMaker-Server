"""Company Video Stories, Gamification / CartMaker Tokens, and Universal Q&A Conversations."""
from .base import *
from .base import _get_cached_bcv_rate, _extract_and_validate_category_ids

class CompanyVideoStoryViewSet(viewsets.ModelViewSet):
    """
    Endpoints para gestionar los videos cortos de los comercios.
    """
    queryset = CompanyVideoStory.objects.all()
    serializer_class = CompanyVideoStorySerializer
    permission_classes = [IsAuthenticated]
    
    # 💡 MUY IMPORTANTE: Habilitamos a Django para recibir archivos pesados
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get_queryset(self):
        base_qs = CompanyVideoStory.objects.select_related(
            'company',
            'associated_item__product',
            'associated_item__store',
        )
        user = getattr(self.request, 'user', None)
        if not user or not user.is_authenticated:
            return base_qs.none()
        if self.action in ('update', 'partial_update', 'destroy'):
            return base_qs.filter(company__owner=user)
        if self.action in ('list', 'retrieve'):
            now = timezone.now()
            return base_qs.filter(
                Q(expires_at__gt=now, video_file__isnull=False) | Q(company__owner=user)
            )
        return base_qs

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.company.owner != request.user:
            return Response({"error": "No tienes permiso para modificar este video."}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.company.owner != request.user:
            return Response({"error": "No tienes permiso para modificar este video."}, status=status.HTTP_403_FORBIDDEN)
        return super().partial_update(request, *args, **kwargs)

    @action(detail=False, methods=['get'])
    def available_items(self, request):
        """
        Retorna todos los InventoryItems agrupados por sucursal.
        Indica si el ítem ya tiene un video vigente.
        """
        company = Company.objects.filter(owner=request.user).first()
        if not company:
            return Response({"error": "No tienes una compañía registrada."}, status=status.HTTP_403_FORBIDDEN)

        now = timezone.now()
        active_stories_prefetch = Prefetch(
            'linked_stories',
            queryset=CompanyVideoStory.objects.filter(expires_at__gt=now, video_file__isnull=False),
            to_attr='active_linked_stories'
        )
        active_items_prefetch = Prefetch(
            'product_items',
            queryset=InventoryItem.objects.filter(paused=False, stock__gt=0).select_related('product').prefetch_related(active_stories_prefetch),
            to_attr='active_product_items'
        )
        stores = company.stores.filter(is_active=True).prefetch_related(active_items_prefetch)
        
        data = []
        for store in stores:
            items_data = []
            inventory_items = getattr(store, 'active_product_items', [])
            
            for item in inventory_items:
                active_stories = getattr(item, 'active_linked_stories', [])
                active_story = active_stories[0] if active_stories else None
                
                img_url = ""
                if item.product.images and len(item.product.images) > 0:
                    img_url = storage_manager.get_url(item.product.images[0])

                items_data.append({
                    "id": str(item.id),
                    "product_name": item.product.name,
                    "image": img_url,
                    "active_video_expiration": timezone.localtime(active_story.expires_at).isoformat() if active_story else None
                })
            
            data.append({
                "store_id": str(store.id),
                "store_name": store.name,
                "items": items_data
            })
            
        return Response({"data": data}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def my_videos(self, request):
        company = Company.objects.filter(owner=request.user).first()
        if not company:
            return Response({"error": "No tienes una compañía registrada."}, status=status.HTTP_403_FORBIDDEN)

        videos = self.queryset.filter(company=company).select_related(
            'company',
            'associated_item',
            'associated_item__product',
            'associated_item__product__category',
            'associated_item__product__category__parent_category',
            'associated_item__product__company',
            'associated_item__offer',
            'associated_item__store',
            'associated_item__store__company',
        ).order_by('-creation')
        
        page_number = request.GET.get('page', 1)
        paginator = Paginator(videos, 10)
        page_obj = paginator.get_page(page_number)

        current_videos = list(page_obj.object_list)
        video_ids = [v.id for v in current_videos]
        video_ids_str = [str(vid) for vid in video_ids]

        # 1. Telemetría de engagement
        logs_data = VideoEngagementLog.objects.filter(
            video_id__in=video_ids
        ).values('video_id').annotate(
            total_views=Count('id'),
            completed_views=Count('id', filter=Q(video_completed=True)),
            product_clicks=Count('id', filter=Q(interacted_with_product=True)),
            added_to_cart_count=Count('id', filter=Q(added_to_cart_from_video=True)),
            sales_count=Count('id', filter=Q(bought_from_video=True)),
            total_watch_time=Sum('watch_time_seconds')
        )
        logs_map = {l['video_id']: l for l in logs_data}

        # 2. Likes polimórficos
        video_ct = ContentType.objects.get_for_model(CompanyVideoStory)
        likes_data = UniversalLike.objects.filter(
            content_type=video_ct,
            object_id__in=video_ids_str
        ).values('object_id').annotate(total_likes=Count('id'))
        likes_map = {l['object_id']: l['total_likes'] for l in likes_data}

        # 3. Preguntas/Comentarios polimórficos
        comments_data = UniversalComment.objects.filter(
            content_type=video_ct,
            object_id__in=video_ids_str
        ).values('object_id').annotate(total_comments=Count('id'))
        comments_map = {c['object_id']: c['total_comments'] for c in comments_data}

        data = []
        for video in current_videos:
            v_json = video.get_json()
            vid = video.id
            vid_str = str(vid)
            
            v_log = logs_map.get(vid, {})
            log_views = v_log.get('total_views', 0)
            total_views = max(video.views_count, log_views)
            
            likes_count = likes_map.get(vid_str, 0)
            comments_count = comments_map.get(vid_str, 0)
            product_clicks = v_log.get('product_clicks', 0)
            sales_count = v_log.get('sales_count', 0)
            added_to_cart_count = v_log.get('added_to_cart_count', 0)
            completed_views = v_log.get('completed_views', 0)
            watch_time = round(float(v_log.get('total_watch_time') or 0.0), 1)

            # Facturación estimada atribuida
            revenue = 0.0
            if video.associated_item and sales_count > 0:
                item_price = float(video.associated_item.custom_price if video.associated_item.custom_price else video.associated_item.product.price)
                revenue = round(sales_count * item_price, 2)

            metrics = {
                'views_count': total_views,
                'likes_count': likes_count,
                'comments_count': comments_count,
                'product_clicks': product_clicks,
                'sales_count': sales_count,
                'added_to_cart_count': added_to_cart_count,
                'completed_views': completed_views,
                'watch_time_seconds': watch_time,
                'revenue': revenue,
            }

            v_json['metrics'] = metrics
            v_json['views_count'] = total_views
            v_json['likes_count'] = likes_count
            v_json['comments_count'] = comments_count
            v_json['sales_count'] = sales_count
            v_json['product_clicks'] = product_clicks
            v_json['revenue'] = revenue

            data.append(v_json)

        return Response({
            "success": True,
            "data": {
                "videos": data,
                "pagination": {
                    "current_page": page_obj.number,
                    "total_pages": paginator.num_pages,
                    "has_next": page_obj.has_next(),
                    "total_items": paginator.count
                }
            }
        }, status=status.HTTP_200_OK)

    # 💡 2. OVERRIDE: Destrucción segura
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Validar que el dueño sea el que intenta borrar
        if instance.company.owner != request.user:
             return Response({"error": "No tienes permiso para eliminar este video."}, status=status.HTTP_403_FORBIDDEN)
        
        # Disparamos la limpieza física de AWS/Storage
        instance.clear_media_files()
        
        # Borramos de la BD (GenericRelation limpiará likes y comments en cascada)
        instance.delete()
        
        return Response({"success": True, "message": "Video eliminado correctamente."}, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        """
        Endpoint que recibe la petición desde Flutter (multipart/form-data).
        Maneja los archivos físicamente a través del COS (storage_manager).
        """
        try:
            # 1. Obtener la compañía del comerciante
            company = Company.objects.filter(owner=request.user).first()
            if not company:
                return Response({
                    "error": "No tienes una compañía registrada para subir videos."
                }, status=status.HTTP_403_FORBIDDEN)

            # 2. Extraer datos crudos del Request
            video_obj = request.FILES.get('video_file')
            thumb_obj = request.FILES.get('thumbnail')
            description = request.data.get('description', '')
            associated_item_id = request.data.get('associated_item_id')
            duration = float(request.data.get('duration_seconds', 0.0))

            filter_matrix_raw = request.data.get('applied_filter_matrix')
            filter_matrix = json.loads(filter_matrix_raw) if filter_matrix_raw else None

            if not video_obj or not thumb_obj:
                return Response({
                    "error": "Faltan los archivos físicos de video o miniatura."
                }, status=status.HTTP_400_BAD_REQUEST)

            v_ext = video_obj.name.rsplit('.', 1)[-1].lower() if '.' in getattr(video_obj, 'name', '') else ''
            t_ext = thumb_obj.name.rsplit('.', 1)[-1].lower() if '.' in getattr(thumb_obj, 'name', '') else ''
            if v_ext not in ('mp4', 'mov', 'm4v', 'webm'):
                return Response({"error": "Formato de video no permitido. Usa MP4, MOV, M4V o WEBM."}, status=status.HTTP_400_BAD_REQUEST)
            if t_ext not in ('jpg', 'jpeg', 'png', 'webp'):
                return Response({"error": "Formato de miniatura no permitido. Usa JPG, PNG o WEBP."}, status=status.HTTP_400_BAD_REQUEST)
            if getattr(video_obj, 'size', 0) > 60 * 1024 * 1024:
                return Response({"error": "El archivo de video excede el tamaño máximo permitido (60 MB)."}, status=status.HTTP_400_BAD_REQUEST)
            if getattr(thumb_obj, 'size', 0) > 10 * 1024 * 1024:
                return Response({"error": "La miniatura excede el tamaño máximo permitido (10 MB)."}, status=status.HTTP_400_BAD_REQUEST)

            # 3. Validar el producto vinculado (Si aplica)
            associated_item = None
            if associated_item_id and str(associated_item_id).strip():
                try:
                    associated_item = InventoryItem.objects.get(
                        id=associated_item_id, 
                        store__company=company
                    )
                except InventoryItem.DoesNotExist:
                    return Response({
                        "error": "El producto vinculado no existe o no te pertenece."
                    }, status=status.HTTP_400_BAD_REQUEST)

            # 4. Transacción Atómica y Guardado Físico
            with transaction.atomic():
                dtnow_str = timezone.localtime(timezone.now()).strftime('%d-%m-%Y_%H-%M-%S')
                
                # --- GUARDAR VIDEO ---
                v_name = f"story_video_{company.id}_{dtnow_str}.{v_ext}"
                v_folder = "stories/videos" 
                v_path = storage_manager.save_file(video_obj, v_folder, v_name)

                # --- GUARDAR MINIATURA ---
                t_name = f"story_thumb_{company.id}_{dtnow_str}.{t_ext}"
                t_folder = "stories/thumbnails"
                t_path = storage_manager.save_file(thumb_obj, t_folder, t_name)

                if not v_path or not t_path:
                    raise Exception("Fallo en el storage_manager al guardar los archivos.")

                # 5. Crear el registro en la Base de Datos
                expires_at = timezone.now() + timedelta(hours=72)

                # 💡 Creamos la historia. Como "associated_item" es un ForeignKey, 
                # la BD permite que varios videos apunten al mismo producto sin chocar.
                story = CompanyVideoStory.objects.create(
                    company=company,
                    video_file=v_path,
                    thumbnail=t_path,
                    description=description,
                    associated_item=associated_item,
                    applied_filter_matrix=filter_matrix,
                    expires_at=expires_at,
                    duration_seconds=duration
                )

                # 💡 Lanzamos la tarea a Celery
                optimize_and_transcode_video_story.delay(story.id)

                # 💡 Invalidación dirigida al ítem vinculado y a las cuadrículas geográficas de las tiendas de esta empresa
                try:
                    if associated_item:
                        cache.delete(f"cartmaker:struct:item:{associated_item.id}")
                    for store in company.stores.select_related('location').all():
                        if store.location and store.location.coordinates:
                            lat_r = round(store.location.coordinates.y, 2)
                            lng_r = round(store.location.coordinates.x, 2)
                            cache.delete_pattern(f"cartmaker:struct:home:{lat_r}:{lng_r}:*")
                except Exception as e:
                    print(f"Nota: No se pudo limpiar el caché por patrón: {e}")

            return Response({
                "success": True,
                "message": "Video publicado con éxito",
                "data": story.get_json()
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            print(f"Error al guardar la historia: {e}")
            return Response({
                "success": False,
                "error": f"Error interno: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UniversalConversationPagination(PageNumberPagination):
    page_size = 15
    page_size_query_param = 'page_size'
    max_page_size = 30

class UniversalConversationViewSet(viewsets.ViewSet):
    """
    API unificada para comentarios y preguntas en Productos y Videos.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'navigation'

    def get_permissions(self):
        if self.action in ('list_comments', 'single_feed_post'):
            return [AllowAny()]
        return [IsAuthenticated()]

    @action(detail=False, methods=['get'])
    def merchant_items_summary(self, request):
        """
        Retorna la TOTALIDAD de los productos y videos del comerciante,
        calculando sus preguntas pendientes para servir como panel histórico.
        """
        user = request.user
        item_ct = ContentType.objects.get_for_model(InventoryItem)
        video_ct = ContentType.objects.get_for_model(CompanyVideoStory)

        # ==========================================
        # 1. OBTENER TODO EL INVENTARIO Y SUS ALERTAS
        # ==========================================
        db_items = list(InventoryItem.objects.select_related('product').filter(
            store__company__owner=user
        ))
        items_ids_strs = [str(item.id) for item in db_items]

        products_summary = UniversalComment.objects.filter(
            content_type=item_ct,
            object_id__in=items_ids_strs
        ).values('object_id').annotate(
            pending=Count('id', filter=Q(answer_text__isnull=True) | Q(answer_text__exact=''))
        )
        products_dict = {item['object_id']: item['pending'] for item in products_summary}

        # ==========================================
        # 2. OBTENER TODAS LAS VIDEO HISTORIAS Y SUS ALERTAS
        # ==========================================
        db_videos = list(CompanyVideoStory.objects.filter(company__owner=user))
        videos_ids_strs = [str(vid.id) for vid in db_videos]

        videos_summary = UniversalComment.objects.filter(
            content_type=video_ct,
            object_id__in=videos_ids_strs
        ).values('object_id').annotate(
            pending=Count('id', filter=Q(answer_text__isnull=True) | Q(answer_text__exact=''))
        )
        videos_dict = {video['object_id']: video['pending'] for video in videos_summary}

        # ==========================================
        # 3. COMPILACIÓN DE DATA COMPLETA (SIN LLAMAR A get_json() COMPLETO)
        # ==========================================
        data = []

        # Mapeamos absolutamente todos los productos
        for item in db_items:
            item_id_str = str(item.id)
            prod = item.product
            first_img = storage_manager.get_url(prod.images[0]) if prod.images else ''
            
            data.append({
                "id": item_id_str,
                "name": prod.name or 'Producto sin nombre',
                "image": first_img,
                "type": "product",
                "pending_questions_count": products_dict.get(item_id_str, 0),
                "creation": item.creation # 💡 Inyectamos la fecha nativa para ordenar
            })

        # Mapeamos absolutamente todos los videos
        for vid in db_videos:
            vid_id_str = str(vid.id)
            raw_desc = vid.description or ''
            clean_desc = raw_desc.strip() if raw_desc else "Video Historia sin descripción"
            thumb_url = storage_manager.get_url(vid.thumbnail) if vid.thumbnail else ''
            
            data.append({
                "id": vid_id_str,
                "name": clean_desc if len(clean_desc) <= 40 else clean_desc[:40] + "...",
                "image": thumb_url, 
                "type": "video",
                "pending_questions_count": videos_dict.get(vid_id_str, 0),
                "creation": vid.creation # 💡 Inyectamos la fecha nativa para ordenar
            })

        # 📊 ORDENAMIENTO DOBLE CRÍTICO:
        # 1. Primero por cantidad de dudas pendientes (Mayor a menor)
        # 2. Segundo por fecha de creación (Más nuevo/reciente a más viejo)
        data.sort(key=lambda x: (x['pending_questions_count'], x['creation']), reverse=True)

        # 🧼 LIMPIEZA PRE-JSON: Eliminamos el objeto 'datetime' para que Django no explote
        # al serializar la respuesta hacia Flutter, ya que el móvil no necesita este campo.
        for item in data:
            item.pop('creation', None)

        return Response({'data': data}, status=200)

    @action(detail=False, methods=['get'])
    def list_comments(self, request):
        target_type = request.query_params.get('target_type')
        target_id = request.query_params.get('target_id')

        if not target_type or not target_id:
            return Response({'error': 'Faltan parámetros: target_type o target_id'}, status=status.HTTP_400_BAD_REQUEST)

        # Mapeo de tipos hacia los modelos nativos
        model_map = {
            'product': 'inventoryitem',
            'video': 'companyvideostory'
        }
        
        content_model = model_map.get(target_type)
        if not content_model:
            return Response({'error': 'Tipo de contenido no soportado.'}, status=status.HTTP_400_BAD_REQUEST)

        content_type_obj = ContentType.objects.get_for_model(
            InventoryItem if content_model == 'inventoryitem' else CompanyVideoStory
        )
        
        # Pre-resolvemos el objeto padre una sola vez con sus relaciones para evitar 60-80 N+1 GenericForeignKey queries
        target_obj = None
        if content_model == 'inventoryitem':
            target_obj = InventoryItem.objects.select_related('store__company', 'product').filter(id=target_id).first()
        else:
            target_obj = CompanyVideoStory.objects.select_related('company').filter(id=target_id).first()

        # Filtramos por el tipo y el ID
        comments = UniversalComment.objects.filter(
            content_type=content_type_obj,
            object_id=target_id
        ).select_related('client', 'content_type').order_by('-question_creation')

        paginator = UniversalConversationPagination()
        paginated_qs = paginator.paginate_queryset(comments, request)

        data = [q.get_json(target_obj=target_obj) for q in paginated_qs]
        return paginator.get_paginated_response(data)

    @action(detail=False, methods=['post'])
    def add_comment(self, request):
        target_type = request.data.get('target_type')
        target_id = request.data.get('target_id')
        question_text = request.data.get('question_text')

        if not target_type or not target_id or not question_text:
            return Response({'error': 'Faltan parámetros.'}, status=status.HTTP_400_BAD_REQUEST)

        clean_text = question_text.strip()
        if not clean_text:
            return Response({'error': 'El comentario no puede estar vacío.'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            try:
                if target_type == 'product':
                    target_obj = InventoryItem.objects.select_related('store__company__owner', 'product').get(id=target_id, paused=False)
                    owner_id = target_obj.store.company.owner.id
                    item_name = target_obj.product.name
                elif target_type == 'video':
                    target_obj = CompanyVideoStory.objects.select_related('company__owner').get(id=target_id)
                    owner_id = target_obj.company.owner.id
                    item_name = "tu Video Historia"
                else:
                    raise ValueError("Tipo inválido")
            except (InventoryItem.DoesNotExist, CompanyVideoStory.DoesNotExist, ValueError):
                return Response({'error': 'El contenido no existe o fue retirado.'}, status=status.HTTP_404_NOT_FOUND)

            content_type_obj = ContentType.objects.get_for_model(target_obj)
            
            comment = UniversalComment.objects.create(
                client=request.user,
                content_type=content_type_obj,
                object_id=target_id,
                question_text=clean_text
            )

            # Notificamos al dueño
            firebase_admin.NotificationManager.notify_new_question(
                merchant_user_id=owner_id,
                item_name=item_name,
                item_id=target_id,
                question_id=comment.id 
            )
            return Response({'message': 'Comentario enviado con éxito.', 'data': comment.get_json()}, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'])
    def answer_comment(self, request):
        question_id = request.data.get('question_id')
        answer_text = request.data.get('answer_text')

        if not question_id or not answer_text:
            return Response({'error': 'Faltan parámetros.'}, status=status.HTTP_400_BAD_REQUEST)

        clean_text = answer_text.strip()
        if not clean_text:
            return Response({'error': 'La respuesta no puede estar vacía.'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            try:
                comment = UniversalComment.objects.select_for_update().get(id=question_id)
            except UniversalComment.DoesNotExist:
                return Response({'error': 'La pregunta no existe.'}, status=status.HTTP_404_NOT_FOUND)

            # Extraemos dinámicamente al dueño para verificar permisos
            owner = None
            company_name = ""
            item_name = ""
            
            if comment.content_type.model == 'inventoryitem':
                owner = comment.content_object.store.company.owner
                company_name = comment.content_object.store.company.name
                item_name = comment.content_object.product.name
            elif comment.content_type.model == 'companyvideostory':
                owner = comment.content_object.company.owner
                company_name = comment.content_object.company.name
                item_name = "tu Video"

            if owner != request.user:
                return Response({'error': 'No tienes permisos para responder.'}, status=status.HTTP_403_FORBIDDEN)

            if comment.answer_text is not None:
                return Response({'error': 'Esta pregunta ya fue respondida.'}, status=status.HTTP_400_BAD_REQUEST)

            comment.answer_text = clean_text
            comment.answer_creation = timezone.now()
            comment.save()

            item_type = 'product' if comment.content_type.model == 'inventoryitem' else 'video'
            client_id = comment.client_id
            obj_id = comment.object_id
            comment_json = comment.get_json()

            transaction.on_commit(
                lambda: firebase_admin.NotificationManager.notify_new_answer(
                    user_id=client_id,
                    company_name=company_name,
                    item_name=item_name,
                    item_id=obj_id,
                    target_type=item_type
                )
            )

            return Response({'success': True, 'message': 'Respuesta enviada.', 'data': comment_json}, status=status.HTTP_200_OK)
        
    @action(detail=False, methods=['get'], url_path='single-feed-post')
    def single_feed_post(self, request):
        """
        Recupera un solo elemento (Producto o Video) y lo empaqueta con el
        formato exacto del Home Feed para inyecciones dinámicas en Flutter
        cuando el usuario entra desde una notificación push.
        """
        target_id = request.query_params.get('target_id')
        target_type = request.query_params.get('target_type')

        if not target_id or not target_type:
            return Response({'error': 'Faltan parámetros target_id o target_type.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if target_type == 'product':
                # 💡 Buscamos el ítem asegurándonos de que no esté pausado y precargando categoría/oferta
                item = InventoryItem.objects.select_related(
                    'product',
                    'product__category__parent_category',
                    'offer',
                    'store__company'
                ).get(id=target_id, paused=False)
                
                # 💡 Empaquetamos igual que tu Feed
                data = item.get_json()
                data['feed_type'] = 'product' 
                
                return Response({'data': data}, status=status.HTTP_200_OK)

            elif target_type == 'video':
                video = CompanyVideoStory.objects.select_related('company', 'associated_item').get(id=target_id)
                
                # 💡 Verificamos que el video no haya expirado
                if not video.is_media_available:
                    return Response({'error': 'El video expiró o fue eliminado.'}, status=status.HTTP_404_NOT_FOUND)

                data = video.get_json()
                data['feed_type'] = 'video'
                
                return Response({'data': data}, status=status.HTTP_200_OK)

            else:
                return Response({'error': 'Tipo de contenido no soportado.'}, status=status.HTTP_400_BAD_REQUEST)

        except InventoryItem.DoesNotExist:
            return Response({'error': 'El producto no existe o fue retirado.'}, status=status.HTTP_404_NOT_FOUND)
        except CompanyVideoStory.DoesNotExist:
            return Response({'error': 'El video no existe o fue retirado.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception(f"Error en single_feed_post: {e}")
            return Response({'error': 'Error interno al consultar el contenido.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
