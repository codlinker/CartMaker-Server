"""Company Video Stories, Gamification / CartMaker Tokens, and Universal Q&A Conversations."""
from .base import *
from .base import _get_cached_bcv_rate, _extract_and_validate_category_ids
from ..core.workforce import (
    WorkforceError,
    resolve_merchant_actor,
    user_can_manage_company,
    user_can_manage_store,
    require_owner_for_destructive_action,
    require_employee_permission,
    check_and_record_worker_catalog_mutation,
    snapshot_video_story,
    record_employee_audit_log,
)


def _story_workforce_error_response(err: WorkforceError) -> Response:
    payload = {
        'success': False,
        'error': err.message,
        'detail': err.message,
    }
    if err.code:
        payload['code'] = err.code
    return Response(payload, status=err.status_code)

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
            'associated_item__product__category',
            'associated_item__product__category__parent_category',
            'associated_item__product__company',
            'associated_item__offer',
            'associated_item__store',
            'associated_item__store__company',
        )
        user = getattr(self.request, 'user', None)
        if not user or not user.is_authenticated:
            return base_qs.none()
        if self.action in ('list', 'retrieve'):
            now = timezone.now()
            company, _, _ = resolve_merchant_actor(self.request)
            merchant_q = Q(company=company) if company is not None else Q(company__owner=user)
            return base_qs.filter(
                Q(expires_at__gt=now, video_file__isnull=False) | merchant_q
            )
        return base_qs

    @staticmethod
    def _parse_json_field(raw_val, default=None):
        if raw_val is None or raw_val == "":
            return default
        if isinstance(raw_val, (dict, list)):
            return raw_val
        if isinstance(raw_val, str):
            stripped = raw_val.strip()
            if not stripped or stripped.lower() in ("null", "none"):
                return default
            try:
                return json.loads(stripped)
            except Exception:
                return default
        return default

    @classmethod
    def _resolve_story_associated_item(cls, company, data):
        """
        Resuelve el InventoryItem vinculado a partir de `associated_item_id` o `tagged_products`.
        Retorna: (should_update: bool, item: InventoryItem | None, error_msg: str | None)
        """
        has_assoc_key = 'associated_item_id' in data
        has_tagged_key = 'tagged_products' in data
        if not has_assoc_key and not has_tagged_key:
            return False, None, None

        candidate_id = None
        if has_assoc_key:
            raw_id = data.get('associated_item_id')
            if raw_id is not None:
                cleaned = str(raw_id).strip()
                if cleaned and cleaned.lower() not in ('null', 'none', '[]'):
                    candidate_id = cleaned
        elif has_tagged_key:
            raw_tagged = data.get('tagged_products')
            if hasattr(data, 'getlist') and len(data.getlist('tagged_products')) > 1:
                parsed_list = data.getlist('tagged_products')
            else:
                parsed_list = cls._parse_json_field(raw_tagged, default=None)
                if parsed_list is None and isinstance(raw_tagged, str) and raw_tagged.strip():
                    parsed_list = [x.strip() for x in raw_tagged.split(',') if x.strip()]
            if isinstance(parsed_list, list) and len(parsed_list) > 0:
                first_entry = parsed_list[0]
                if isinstance(first_entry, dict):
                    candidate_id = str(first_entry.get('id') or first_entry.get('item_id') or '').strip()
                elif first_entry is not None:
                    candidate_id = str(first_entry).strip()

        if not candidate_id:
            return True, None, None

        item = InventoryItem.objects.filter(id=candidate_id, store__company=company).first()
        if not item:
            item = InventoryItem.objects.filter(product_id=candidate_id, store__company=company).first()
        if not item:
            return False, None, "El producto vinculado no existe o no te pertenece."
        return True, item, None

    @staticmethod
    def _invalidate_story_caches(company, item_ids=None):
        try:
            if item_ids:
                for iid in item_ids:
                    if iid:
                        cache.delete(f"cartmaker:struct:item:{iid}")
            for store in company.stores.select_related('location').all():
                if store.location and store.location.coordinates:
                    lat_r = round(store.location.coordinates.y, 2)
                    lng_r = round(store.location.coordinates.x, 2)
                    cache.delete_pattern(f"cartmaker:struct:home:{lat_r}:{lng_r}:*")
        except Exception as e:
            print(f"Nota: No se pudo limpiar el caché por patrón: {e}")

    def _perform_story_update(self, request, instance):
        if not user_can_manage_company(request, instance.company):
            return Response(
                {"error": "No tienes permisos para editar esta historia."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            _company, emp, _allowed = resolve_merchant_actor(request, target_company_id=instance.company_id)
            if emp is not None:
                require_employee_permission(emp, 'can_edit_products')
                check_and_record_worker_catalog_mutation(
                    emp,
                    f"story:{instance.id}",
                    zeroed_stock_or_paused=False,
                )
        except WorkforceError as e:
            return _story_workforce_error_response(e)

        before_snap = snapshot_video_story(instance)
        company = instance.company
        old_item_id = instance.associated_item_id
        update_fields = set()

        # 1. Validar duración si viene en el payload (CART-33: tolerancia <= 31.0s)
        if 'duration_seconds' in request.data or 'duration' in request.data:
            raw_dur = request.data.get('duration_seconds', request.data.get('duration'))
            if raw_dur is not None and str(raw_dur).strip() != "":
                try:
                    dur_val = float(raw_dur)
                except (ValueError, TypeError):
                    return Response(
                        {"error": "La duración del video debe ser un número válido."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if dur_val < 0 or dur_val > 31.0:
                    return Response(
                        {"error": "El video no puede superar los 30 segundos."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                instance.duration_seconds = dur_val
                update_fields.add('duration_seconds')

        # 2. Título y descripción (sincronizados para retrocompatibilidad total)
        has_title = 'title' in request.data
        has_desc = 'description' in request.data
        if has_title:
            clean_title = str(request.data.get('title') or '').strip()[:150]
            instance.title = clean_title
            update_fields.add('title')
            if not has_desc:
                instance.description = clean_title
                update_fields.add('description')
        if has_desc:
            clean_desc = str(request.data.get('description') or '').strip()
            instance.description = clean_desc
            update_fields.add('description')
            if not has_title:
                instance.title = clean_desc[:150]
                update_fields.add('title')

        # 3. Metadatos de edición y matriz de color (stickers, textos, trim, filtros)
        filter_changed = False
        if 'metadata' in request.data:
            parsed_meta = self._parse_json_field(request.data.get('metadata'), default={})
            if not isinstance(parsed_meta, dict):
                return Response(
                    {"error": "El campo metadata debe ser un objeto JSON válido."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            instance.metadata = parsed_meta
            update_fields.add('metadata')
            matrix_in_meta = parsed_meta.get('applied_filter_matrix') or parsed_meta.get('color_matrix')
            if isinstance(matrix_in_meta, list) and 'applied_filter_matrix' not in request.data:
                instance.applied_filter_matrix = matrix_in_meta
                update_fields.add('applied_filter_matrix')
                filter_changed = True

        if 'applied_filter_matrix' in request.data:
            raw_matrix = request.data.get('applied_filter_matrix')
            parsed_matrix = self._parse_json_field(raw_matrix, default=None)
            instance.applied_filter_matrix = parsed_matrix
            update_fields.add('applied_filter_matrix')
            filter_changed = True

        # 4. Producto etiquetado / vinculado (associated_item_id o tagged_products)
        should_update_item, resolved_item, item_err = self._resolve_story_associated_item(company, request.data)
        if item_err:
            return Response({"error": item_err}, status=status.HTTP_400_BAD_REQUEST)
        if should_update_item:
            instance.associated_item = resolved_item
            update_fields.add('associated_item')

        # 5. Reemplazo opcional de archivos multimedia (video_file y/o thumbnail)
        video_obj = request.FILES.get('video_file')
        thumb_obj = request.FILES.get('thumbnail')

        if video_obj:
            v_ext = video_obj.name.rsplit('.', 1)[-1].lower() if '.' in getattr(video_obj, 'name', '') else ''
            if v_ext not in ('mp4', 'mov', 'm4v', 'webm'):
                return Response(
                    {"error": "Formato de video no permitido. Usa MP4, MOV, M4V o WEBM."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if getattr(video_obj, 'size', 0) > 60 * 1024 * 1024:
                return Response(
                    {"error": "El archivo de video excede el tamaño máximo permitido (60 MB)."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if thumb_obj:
            t_ext = thumb_obj.name.rsplit('.', 1)[-1].lower() if '.' in getattr(thumb_obj, 'name', '') else ''
            if t_ext not in ('jpg', 'jpeg', 'png', 'webp'):
                return Response(
                    {"error": "Formato de miniatura no permitido. Usa JPG, PNG o WEBP."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if getattr(thumb_obj, 'size', 0) > 10 * 1024 * 1024:
                return Response(
                    {"error": "La miniatura excede el tamaño máximo permitido (10 MB)."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            with transaction.atomic():
                dtnow_str = timezone.localtime(timezone.now()).strftime('%d-%m-%Y_%H-%M-%S')

                if video_obj:
                    old_video = instance.video_file
                    v_ext = video_obj.name.rsplit('.', 1)[-1].lower()
                    v_name = f"story_video_{company.id}_{dtnow_str}.{v_ext}"
                    v_path = storage_manager.save_file(video_obj, "stories/videos", v_name)
                    if not v_path:
                        raise Exception("Fallo en el storage_manager al guardar el nuevo video.")
                    if old_video and old_video != v_path:
                        try:
                            storage_manager.delete_file(old_video)
                        except Exception as del_err:
                            print(f"Aviso: No se pudo eliminar el video anterior {old_video}: {del_err}")
                    instance.video_file = v_path
                    update_fields.add('video_file')
                    if instance.is_media_expired:
                        instance.expires_at = timezone.now() + timedelta(hours=72)
                        update_fields.add('expires_at')

                if thumb_obj:
                    old_thumb = instance.thumbnail
                    t_ext = thumb_obj.name.rsplit('.', 1)[-1].lower()
                    t_name = f"story_thumb_{company.id}_{dtnow_str}.{t_ext}"
                    t_path = storage_manager.save_file(thumb_obj, "stories/thumbnails", t_name)
                    if not t_path:
                        raise Exception("Fallo en el storage_manager al guardar la nueva miniatura.")
                    if old_thumb and old_thumb != t_path:
                        try:
                            storage_manager.delete_file(old_thumb)
                        except Exception as del_err:
                            print(f"Aviso: No se pudo eliminar la miniatura anterior {old_thumb}: {del_err}")
                    instance.thumbnail = t_path
                    update_fields.add('thumbnail')

                update_fields.add('updated_at')
                instance.save(update_fields=list(update_fields))

                if emp is not None:
                    record_employee_audit_log(
                        emp,
                        action='video_story_updated',
                        target_type='video_story',
                        target_id=instance.id,
                        target_label=instance.title or instance.description[:60] or 'Historia de video',
                        before_snapshot=before_snap,
                        after_snapshot=snapshot_video_story(instance),
                        is_reversible=True,
                    )

                if video_obj or (filter_changed and instance.video_file):
                    optimize_and_transcode_video_story.delay(instance.id)

                self._invalidate_story_caches(company, item_ids={old_item_id, instance.associated_item_id})

            story_json = instance.get_json()
            return Response(
                {
                    "success": True,
                    "message": "Historia actualizada con éxito.",
                    "data": story_json,
                    **story_json,
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            print(f"Error al actualizar la historia {instance.id}: {e}")
            return Response(
                {"success": False, "error": f"Error interno al actualizar la historia: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        return self._perform_story_update(request, instance)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        return self._perform_story_update(request, instance)

    @action(detail=False, methods=['get'])
    def available_items(self, request):
        """
        Retorna todos los InventoryItems agrupados por sucursal.
        Indica si el ítem ya tiene un video vigente.
        """
        company, _emp, allowed_store_ids = resolve_merchant_actor(request)
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
        stores_qs = company.stores.filter(is_active=True)
        if allowed_store_ids is not None:
            stores_qs = stores_qs.filter(id__in=allowed_store_ids)
        stores = stores_qs.prefetch_related(active_items_prefetch)
        
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
        company, _emp, _allowed_store_ids = resolve_merchant_actor(request)
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
        try:
            require_owner_for_destructive_action(request, resource_label='videos del comercio')
        except WorkforceError as e:
            return _story_workforce_error_response(e)

        instance = self.get_object()
        
        # Validar que el dueño de la compañía sea el que intenta borrar
        if not user_can_manage_company(request, instance.company):
             return Response({"error": "No tienes permiso para eliminar este video."}, status=status.HTTP_403_FORBIDDEN)
        
        old_item_id = instance.associated_item_id
        company = instance.company

        # Disparamos la limpieza física de AWS/Storage
        instance.clear_media_files()
        
        # Borramos de la BD (GenericRelation limpiará likes y comments en cascada)
        instance.delete()
        self._invalidate_story_caches(company, item_ids={old_item_id})
        
        return Response({"success": True, "message": "Video eliminado correctamente."}, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        """
        Endpoint que recibe la petición desde Flutter (multipart/form-data).
        Maneja los archivos físicamente a través del COS (storage_manager).
        """
        try:
            # 1. Obtener la compañía del comerciante o asistente
            company, emp, _allowed_store_ids = resolve_merchant_actor(request)
            if not company:
                return Response({
                    "error": "No tienes una compañía registrada para subir videos."
                }, status=status.HTTP_403_FORBIDDEN)

            # 2. Extraer datos crudos del Request
            video_obj = request.FILES.get('video_file')
            thumb_obj = request.FILES.get('thumbnail')
            raw_title = str(request.data.get('title') or '').strip()[:150]
            raw_desc = request.data.get('description')
            description = str(raw_desc).strip() if raw_desc is not None else raw_title
            title = raw_title or (description[:150] if description else '')

            raw_dur = request.data.get('duration_seconds', request.data.get('duration', 0.0))
            try:
                duration = float(raw_dur or 0.0)
            except (ValueError, TypeError):
                return Response({"error": "La duración del video debe ser un número válido."}, status=status.HTTP_400_BAD_REQUEST)

            # CART-33: Tolerancia de hasta 31.0s por redondeo de keyframes nativos en recortes de 30.0s
            if duration < 0 or duration > 31.0:
                return Response({"error": "El video no puede superar los 30 segundos."}, status=status.HTTP_400_BAD_REQUEST)

            metadata_parsed = self._parse_json_field(request.data.get('metadata'), default={})
            if not isinstance(metadata_parsed, dict):
                metadata_parsed = {}

            filter_matrix = self._parse_json_field(request.data.get('applied_filter_matrix'), default=None)
            if filter_matrix is None and isinstance(metadata_parsed.get('color_matrix'), list):
                filter_matrix = metadata_parsed.get('color_matrix')

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

            # 3. Validar el producto vinculado (associated_item_id o tagged_products)
            _, associated_item, item_err = self._resolve_story_associated_item(company, request.data)
            if item_err:
                return Response({"error": item_err}, status=status.HTTP_400_BAD_REQUEST)

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
                    title=title,
                    video_file=v_path,
                    thumbnail=t_path,
                    description=description,
                    associated_item=associated_item,
                    applied_filter_matrix=filter_matrix,
                    metadata=metadata_parsed,
                    expires_at=expires_at,
                    duration_seconds=duration
                )

                if emp is not None:
                    record_employee_audit_log(
                        emp,
                        action='video_story_created',
                        target_type='video_story',
                        target_id=story.id,
                        target_label=story.title or story.description[:60] or 'Historia de video',
                        before_snapshot={},
                        after_snapshot=snapshot_video_story(story),
                        is_reversible=False,
                    )

                # 💡 Lanzamos la tarea a Celery
                optimize_and_transcode_video_story.delay(story.id)

                # 💡 Invalidación dirigida al ítem vinculado y a las cuadrículas geográficas de las tiendas de esta empresa
                self._invalidate_story_caches(company, item_ids={associated_item.id if associated_item else None})

            story_json = story.get_json()
            return Response({
                "success": True,
                "message": "Video publicado con éxito",
                "data": story_json,
                **story_json,
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
        Retorna la TOTALIDAD de los productos y videos del comerciante (o de las sucursales
        asignadas al asistente de tienda), calculando sus preguntas pendientes para servir como panel histórico.
        """
        company, _emp, allowed_store_ids = resolve_merchant_actor(request)
        if company is None:
            return Response({'data': []}, status=200)

        item_ct = ContentType.objects.get_for_model(InventoryItem)
        video_ct = ContentType.objects.get_for_model(CompanyVideoStory)

        # ==========================================
        # 1. OBTENER TODO EL INVENTARIO Y SUS ALERTAS
        # ==========================================
        items_qs = InventoryItem.objects.select_related('product').filter(
            store__company=company
        )
        if allowed_store_ids is not None:
            items_qs = items_qs.filter(store_id__in=allowed_store_ids)
        db_items = list(items_qs)
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
        db_videos = list(CompanyVideoStory.objects.filter(company=company))
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

            # Validamos permisos operativos (dueño del comercio o asistente asignado)
            can_answer = False
            company_name = ""
            item_name = ""
            
            if comment.content_type.model == 'inventoryitem' and comment.content_object is not None:
                can_answer = user_can_manage_store(request, comment.content_object.store)
                company_name = comment.content_object.store.company.name
                item_name = comment.content_object.product.name
            elif comment.content_type.model == 'companyvideostory' and comment.content_object is not None:
                can_answer = user_can_manage_company(request, comment.content_object.company)
                company_name = comment.content_object.company.name
                item_name = "tu Video"

            if not can_answer:
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
    
