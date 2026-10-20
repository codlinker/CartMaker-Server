from datetime import timedelta
import json
import boto3
from celery import shared_task
from django.contrib.auth import get_user_model
import logging
from django.utils import timezone
import os
import subprocess
import tempfile

import requests
from api.core.firebase_admin import NotificationManager
from .core.platinum_manager import PlatinumEvaluator
from api.models import *
from .utils import (
    recalculate_item_popularity,
    normalize_biometric_vector,
    BIOMETRIC_VECTOR_DIMENSIONS,
    BIOMETRIC_LOGIN_THRESHOLD_PERFECT,
)
from django.core.cache import cache
from django.utils.dateparse import parse_datetime
from django.conf import settings
from django.contrib.gis.geos import Point
from django.db import transaction
from django.db.models import Sum, F, FloatField, ExpressionWrapper

logger = logging.getLogger(__name__)
User = get_user_model()

@shared_task(ignore_result=True)
def update_rolling_template(user_id, new_vector):
    try:
        is_valid_new, norm_new, _ = normalize_biometric_vector(
            new_vector, expected_dim=BIOMETRIC_VECTOR_DIMENSIONS
        )
        if not is_valid_new:
            return

        with transaction.atomic():
            user = User.objects.select_for_update().only('biometric_vector').get(id=user_id)
            old_vector = user.biometric_vector
            if old_vector is None or len(old_vector) != BIOMETRIC_VECTOR_DIMENSIONS:
                return

            is_valid_old, norm_old, _ = normalize_biometric_vector(
                list(old_vector), expected_dim=BIOMETRIC_VECTOR_DIMENSIONS
            )
            if not is_valid_old:
                return

            # Defensa en profundidad: verificar distancia coseno antes de mezclar plantillas
            cosine_sim = sum(o * n for o, n in zip(norm_old, norm_new))
            cosine_dist = 1.0 - cosine_sim
            if cosine_dist < 0.06 or cosine_dist > BIOMETRIC_LOGIN_THRESHOLD_PERFECT:
                return

            # Adaptación conservadora (alpha = 0.05) + re-proyección a la hiperesfera unitaria S^511 (||v||_2 = 1.0)
            alpha = 0.05
            blended = [(1.0 - alpha) * o + alpha * n for o, n in zip(norm_old, norm_new)]
            is_valid_blend, norm_blended, _ = normalize_biometric_vector(
                blended, expected_dim=BIOMETRIC_VECTOR_DIMENSIONS
            )
            if not is_valid_blend:
                return

            user.biometric_vector = norm_blended
            user.save(update_fields=['biometric_vector'])

        logger.info(f"✅ Rolling Template (512-D L2-normalizado) actualizado para el usuario {user_id}")

    except User.DoesNotExist:
        pass
    except Exception as e:
        logger.error(f"❌ Error en update_rolling_template: {e}")

@shared_task(ignore_result=True)
def cleanup_expired_offers():
    """
    Busca, elimina todas las ofertas de inventario cuya fecha de validez 
    ya haya pasado e invalida la estructura de las zonas geográficas afectadas.
    """
    try:
        now = timezone.now()
        expired_offers = InventoryItemOffer.objects.filter(valid_until__lt=now)
        
        # Extraemos los IDs de los ítems afectados antes de ejecutar el borrado físico
        affected_item_ids = list(expired_offers.values_list('product_item_id', flat=True))
        count = expired_offers.count()
        
        if count > 0:
            # Borrado masivo en base de datos
            expired_offers.delete()
            logger.info(f"✅ Se eliminaron {count} ofertas expiradas del inventario.")
            
            # Pre-cargamos los ítems afectados y sus coordenadas en un solo viaje a la BD
            affected_items = InventoryItem.objects.filter(
                id__in=affected_item_ids
            ).select_related('store__location')

            invalidated_zones = set()
            for item in affected_items:
                try:
                    location = getattr(item.store, 'location', None)
                    if location and location.coordinates:
                        approx_lat = round(location.coordinates.y, 3)
                        approx_lng = round(location.coordinates.x, 3)
                        zone_key = (approx_lat, approx_lng)
                        if zone_key not in invalidated_zones:
                            invalidated_zones.add(zone_key)
                            cache.delete_pattern(f"cartmaker:struct:home:{approx_lat}:{approx_lng}:*")
                except Exception as e:
                    logger.warning(f"No se pudo invalidar el caché de zona para el item {item.id}: {e}")

            volatile_keys = [f"cartmaker:volatile:item:{item_id}" for item_id in affected_item_ids]
            if volatile_keys:
                cache.delete_many(volatile_keys)
            
    except Exception as e:
        logger.error(f"❌ Error en cleanup_expired_offers: {e}")

@shared_task(ignore_result=True)
def evaluate_platinum_status():
    """
    Tarea nocturna para evaluar el desempeño de todas las tiendas
    y otorgar/revocar el estatus Platinum para el motor de búsqueda.
    """
    try:
        logger.info("⏳ Iniciando evaluación nocturna de estatus Platinum...")
        
        PlatinumEvaluator.evaluate_all_companies()
        
        logger.info("✅ Evaluación Platinum completada con éxito.")
    except Exception as e:
        logger.error(f"❌ Error en evaluate_platinum_status: {e}")

@shared_task(name="cartmaker.orders.send_merchant_reminders")
def send_uncompleted_orders_reminders_to_merchants():
    """ Barre órdenes activas estancadas y recuerda al comerciante su gestión cada 6h """
    time_threshold = timezone.now() - timedelta(hours=6)
    
    # Buscamos órdenes que sigan en WAITING (0) o SHIPPED (1) creadas hace más de 6 horas
    pending_orders = Order.objects.select_related('store__company').filter(
        status__in=[0, 1],
        creation__lte=time_threshold
    )
    
    for order in pending_orders:
        merchant_id = order.store.company.owner.id
        NotificationManager.notify_order_status_change(
            user_id=merchant_id,
            order_id=order.id,
            title="⚠️ Pedido pendiente por cerrar",
            body=f"La orden N° {order.id} aún no ha sido marcada como completada. Gestiona tu entrega.",
            is_merchant=True
        )

@shared_task(ignore_result=True)
def cleanup_expired_video_stories():
    """
    Busca todas las Video Historias que hayan superado su tiempo de vida estipulado (3 días)
    y elimina los archivos pesados (video y miniatura) del Cloud Object Storage (o local)
    para ahorrar espacio y costos, conservando el registro intacto para las analíticas.
    """
    try:
        now = timezone.now()
        
        # 💡 Optimizamos la query buscando SOLO historias expiradas 
        # que todavía tengan archivos vinculados (evita procesar el historial limpio)
        expired_stories = CompanyVideoStory.objects.filter(
            expires_at__lt=now
        ).exclude(
            video_file__isnull=True, 
            thumbnail__isnull=True
        )
        
        count = expired_stories.count()
        
        if count > 0:
            logger.info(f"🧹 Iniciando limpieza de {count} historias de video expiradas...")
            
            # Iteramos e invocamos la limpieza física archivo por archivo
            for story in expired_stories:
                try:
                    story.clear_media_files()
                except Exception as file_error:
                    # Aislamos el error para que un archivo corrupto no detenga todo el bucle
                    logger.warning(f"⚠️ No se pudo limpiar la historia {story.id}: {file_error}")
                    continue
            
            logger.info(f"✅ Limpieza multimedia completada con éxito.")
            
    except Exception as e:
        logger.error(f"❌ Error crítico en cleanup_expired_video_stories: {e}")

@shared_task(ignore_result=True)
def optimize_and_transcode_video_story(story_id):
    """
    Orquestador fail-safe adaptativo.
    Aplica el filtro de color de FFmpeg en local o AWS S3, y luego
    delega la segmentación HLS a MediaConvert si está en producción.
    """
    try:
        story = CompanyVideoStory.objects.get(id=story_id)
        matrix_data = getattr(story, 'applied_filter_matrix', None)
        
        # =========================================================================
        # 🎨 FASE 1: APLICACIÓN DEL FILTRO DE COLOR (Video y Thumbnail)
        # =========================================================================
        if matrix_data:
            logger.info(f"🎨 Matriz de color detectada para la historia {story_id}. Procesando...")
            raw_matrix = json.loads(matrix_data) if isinstance(matrix_data, str) else matrix_data
            if not isinstance(raw_matrix, list) or len(raw_matrix) < 14:
                raise ValueError("Matriz de filtro inválida o incompleta.")
            matrix = [round(float(val), 6) for val in raw_matrix[:20]]
            
            vf_string = (
                f"colorchannelmixer="
                f"rr={matrix[0]}:rg={matrix[1]}:rb={matrix[2]}:ra={matrix[3]}:"
                f"gr={matrix[5]}:gg={matrix[6]}:gb={matrix[7]}:ga={matrix[8]}:"
                f"br={matrix[10]}:bg={matrix[11]}:bb={matrix[12]}:ba={matrix[13]}"
            )

            # 🛠️ SUB-CASO A: Procesamiento en Entorno AWS S3
            if settings.STORAGE_TYPE == 'aws':
                input_s3_key = str(story.video_file)
                thumb_s3_key = str(story.thumbnail) # 💡 Obtenemos la llave de la miniatura
                bucket_name = settings.AWS_STORAGE_BUCKET_NAME
                
                s3_client = boto3.client(
                    's3',
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                    region_name=settings.AWS_S3_REGION_NAME
                )

                with tempfile.TemporaryDirectory() as tmpdir:
                    local_input = os.path.join(tmpdir, "input.mp4")
                    local_output = os.path.join(tmpdir, "output.mp4")
                    local_thumb_in = os.path.join(tmpdir, "thumb_in.jpg")
                    local_thumb_out = os.path.join(tmpdir, "thumb_out.jpg")

                    # Descargas
                    s3_client.download_file(bucket_name, input_s3_key, local_input)
                    s3_client.download_file(bucket_name, thumb_s3_key, local_thumb_in)

                    # 1. Filtrar Video
                    result_v = subprocess.run([
                        'ffmpeg', '-y', '-i', local_input, 
                        '-vf', vf_string, 
                        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-profile:v', 'main', '-level:v', '4.0',
                        '-c:a', 'copy', local_output
                    ], capture_output=True, text=True, timeout=180)
                    
                    # 💡 2. Filtrar Thumbnail en S3
                    result_t = subprocess.run([
                        'ffmpeg', '-y', '-i', local_thumb_in, 
                        '-vf', vf_string, local_thumb_out
                    ], capture_output=True, text=True, timeout=180)

                    if result_v.returncode != 0 or result_t.returncode != 0:
                        raise Exception(f"FFmpeg S3 Error. Video: {result_v.stderr} | Thumb: {result_t.stderr}")

                    # Subidas / Sobrescritura
                    s3_client.upload_file(local_output, bucket_name, input_s3_key)
                    s3_client.upload_file(local_thumb_out, bucket_name, thumb_s3_key)
                    logger.info("✅ Filtro aplicado y archivos originales sobrescritos en S3 (Video y Thumbnail).")

            # 🛠️ SUB-CASO B: Procesamiento en Entorno Local (Desarrollo)
            else:
                absolute_input_path = os.path.join(settings.MEDIA_ROOT, str(story.video_file))
                absolute_thumb_path = os.path.join(settings.MEDIA_ROOT, str(story.thumbnail)) # 💡 Ruta de la imagen local
                
                # Temporales para evitar colisión de descriptores de archivos
                with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_v:
                    local_output_path = tmp_v.name
                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp_t:
                    local_thumb_out_path = tmp_t.name

                logger.info(f"⏳ Renderizando filtros FFmpeg locales...")
                
                # 1. Filtrar Video Local
                result_v = subprocess.run([
                    'ffmpeg', '-y', '-i', absolute_input_path, 
                    '-vf', vf_string, 
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-profile:v', 'main', '-level:v', '4.0',
                    '-c:a', 'copy', local_output_path
                ], capture_output=True, text=True, timeout=180)

                # 💡 2. Filtrar Thumbnail Local
                result_t = subprocess.run([
                    'ffmpeg', '-y', '-i', absolute_thumb_path, 
                    '-vf', vf_string, local_thumb_out_path
                ], capture_output=True, text=True, timeout=180)

                if result_v.returncode != 0 or result_t.returncode != 0:
                    if os.path.exists(local_output_path): os.remove(local_output_path)
                    if os.path.exists(local_thumb_out_path): os.remove(local_thumb_out_path)
                    raise Exception(f"FFmpeg Local Error. Video: {result_v.stderr} | Thumb: {result_t.stderr}")

                # Reemplazo atómico de archivos originales en disco
                import shutil
                shutil.move(local_output_path, absolute_input_path)
                shutil.move(local_thumb_out_path, absolute_thumb_path)
                logger.info("✅ Filtro aplicado localmente sobrescribiendo video y thumbnail originales.")

        # =========================================================================
        # 📡 FASE 2: ORQUESTACIÓN HLS CON MEDIACONVERT (Solo producción AWS)
        # =========================================================================
        if settings.STORAGE_TYPE != 'aws':
            logger.info(f"ℹ️ Finalizado: Entorno local no requiere segmentación HLS.")
            return

        if not settings.AWS_MEDIACONVERT_ROLE_ARN:
            logger.warning(f"⚠️ Omitiendo AWS MediaConvert: Falta AWS_MEDIACONVERT_ROLE_ARN.")
            return

        # De aquí en adelante, tu lógica original de MediaConvert se ejecuta usando
        # el archivo que YA fue filtrado en la FASE 1...
        bucket_name = settings.AWS_STORAGE_BUCKET_NAME
        input_s3_key = str(story.video_file)
        
        client_discover = boto3.client(
            'mediaconvert',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME
        )
        mediaconvert_endpoint = client_discover.describe_endpoints()['Endpoints'][0]['Url']

        media_client = boto3.client(
            'mediaconvert',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
            endpoint_url=mediaconvert_endpoint
        )

        input_s3_uri = f"s3://{bucket_name}/{input_s3_key}"
        output_folder_key = f"stories/videos/hls_{story_id}/"
        output_s3_uri = f"s3://{bucket_name}/{output_folder_key}"

        job_settings = {
            "Inputs": [{
                "FileInput": input_s3_uri,
                "VideoSelector": {},
                "AudioSelectors": {"Audio Selector 1": {"DefaultSelection": "DEFAULT"}}
            }],
            "OutputGroups": [{
                "Name": "Apple HLS",
                "OutputGroupSettings": {
                    "Type": "HLS_GROUP_SETTINGS",
                    "HlsGroupSettings": {
                        "SegmentLength": 3,
                        "Destination": output_s3_uri,
                        "MinSegmentLength": 0
                    }
                },
                "Outputs": [{
                    "VideoDescription": {
                        "CodecSettings": {
                            "Codec": "H_264",
                            "H264Settings": {
                                "RateControlMode": "QVBR", 
                                "SceneChangeDetect": "ENABLED",
                                "MaxBitrate": 2000000,
                            }
                        }
                    },
                    "AudioDescriptions": [{
                        "CodecSettings": {
                            "Codec": "AAC",
                            "AacSettings": {
                                "Bitrate": 96000,
                                "CodingMode": "CODING_MODE_2_0",
                                "SampleRate": 44100
                            }
                        }
                    }],
                    "OutputSettings": {
                        "HlsSettings": {
                            "AudioGroupId": "program_audio",
                            "IFrameOnlyPlaylists": "DISABLED"
                        }
                    },
                    "NameModifier": "_v720p" 
                }]
            }]
        }

        logger.info("Sending transcode job to AWS Elemental MediaConvert...")
        response = media_client.create_job(
            Role=settings.AWS_MEDIACONVERT_ROLE_ARN,
            Settings=job_settings
        )
        
        story.video_file = f"{output_folder_key}index_v720p.m3u8"
        story.save(update_fields=['video_file'])

        try:
            from django.core.cache import cache
            if story.associated_item_id:
                cache.delete(f"cartmaker:struct:item:{story.associated_item_id}")
            if story.company_id:
                for store in story.company.stores.select_related('location').all():
                    if store.location and store.location.coordinates:
                        lat_r = round(store.location.coordinates.y, 2)
                        lng_r = round(store.location.coordinates.x, 2)
                        cache.delete_pattern(f"cartmaker:struct:home:{lat_r}:{lng_r}:*")
        except Exception:
            pass

    except Exception as e:
        logger.error(f"❌ Error crítico en la transcodificación de la historia {story_id}: {e}")

@shared_task(ignore_result=True)
def process_analytics_batch():
    """
    Barre todas las colas de telemetría de CartMaker en Redis y 
    procesa las inserciones y actualizaciones masivas hacia PostgreSQL.
    Usa LTRIM post-commit por cola para evitar pérdida de datos si falla la BD
    y preservar nuevos eventos insertados por RPUSH durante el procesamiento.
    """
    try:
        redis_conn = cache.client.get_client()
    except Exception as e:
        logger.error(f"❌ Error al conectar con Redis para analíticas: {e}")
        return

    # Leemos lotes actuales sin borrar antes de persistir en PostgreSQL
    pipeline = redis_conn.pipeline()
    
    queues = [
        "telemetry:product_views", 
        "telemetry:store_views", 
        "telemetry:navigation_logs", 
        "telemetry:video_engagement",
        "telemetry:unmet_demand" 
    ]
    
    for q in queues:
        pipeline.lrange(q, 0, -1)
        
    results = pipeline.execute()
    
    raw_products = results[0]
    raw_stores = results[1]
    raw_navigation = results[2]
    raw_video = results[3]
    raw_unmet_demand = results[4]

    def parse_aware_datetime(dt_str):
        if not dt_str: return None
        parsed = parse_datetime(str(dt_str))
        if parsed and timezone.is_naive(parsed):
            return timezone.make_aware(parsed)
        return parsed

    # ==========================================
    # 0. PRODUCT VIEWS (Bulk Create + Popularity Recalc)
    # ==========================================
    if raw_products:
        product_logs = []
        affected_item_ids = set()
        for item_bytes in raw_products:
            try:
                data = json.loads(item_bytes.decode('utf-8'))
                inv_item_id = data.get('item_id') or data.get('inventory_item_id')
                start_dt = parse_aware_datetime(data.get('start_time'))
                if not inv_item_id or not start_dt or not data.get('client_id'):
                    continue
                origin_src = data.get('origin_source') or 'organic'
                if origin_src not in ('organic', 'atlas'):
                    origin_src = 'organic'
                product_logs.append(ProductViewLog(
                    client_id=data['client_id'],
                    inventory_item_id=inv_item_id,
                    added_to_cart=bool(data.get('added_to_cart', False)),
                    bought=bool(data.get('bought', False)),
                    start_time=start_dt,
                    end_time=parse_aware_datetime(data.get('end_time')),
                    origin_source=origin_src,
                    search_prompt=data.get('search_prompt'),
                    ai_keywords=data.get('ai_keywords'),
                    atlas_message_id=data.get('atlas_message_id'),
                ))
                affected_item_ids.add(str(inv_item_id))
            except Exception as e:
                logger.warning(f"⚠️ Error parseando log de ProductViewLog (se omitirá): {e}")

        try:
            if product_logs:
                ProductViewLog.objects.bulk_create(product_logs, batch_size=500)
            redis_conn.ltrim("telemetry:product_views", len(raw_products), -1)
            for item_id_str in affected_item_ids:
                try:
                    recalculate_item_popularity(item_id_str)
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"❌ Error en bulk_create de product_views: {e}")

    # ==========================================
    # 1. STORE VIEWS (Bulk Create)
    # ==========================================
    if raw_stores:
        store_logs = []
        for item_bytes in raw_stores:
            try:
                data = json.loads(item_bytes.decode('utf-8'))
                store_logs.append(StoreViewLog(
                    client_id=data['client_id'],
                    store_id=data['store_id'],
                    join_time=parse_aware_datetime(data['join_time']),
                    exit_time=parse_aware_datetime(data.get('exit_time')),
                    location_watched=data['location_watched'],
                    presentation_video_watched=data['presentation_video_watched'],
                    stories_watched=data['stories_watched'],
                    products_watched=data['products_watched'],
                    tryed_to_contact=data['tryed_to_contact']
                ))
            except Exception: pass
        try:
            if store_logs:
                StoreViewLog.objects.bulk_create(store_logs, batch_size=500)
            redis_conn.ltrim("telemetry:store_views", len(raw_stores), -1)
        except Exception as e:
            logger.error(f"❌ Error en bulk_create de store_views: {e}")

    # ==========================================
    # 2. NAVIGATION LOGS (Bulk Create)
    # ==========================================
    if raw_navigation:
        nav_logs = []
        for item_bytes in raw_navigation:
            try:
                data = json.loads(item_bytes.decode('utf-8'))
                nav_logs.append(UserNavigationLog(
                    user_id=data['client_id'],
                    navigation_record=data['navigation_record'],
                    login_time=parse_aware_datetime(data['login_time']),
                    logout_time=parse_aware_datetime(data.get('logout_time'))
                ))
            except Exception: pass
        try:
            if nav_logs:
                UserNavigationLog.objects.bulk_create(nav_logs, batch_size=500)
            redis_conn.ltrim("telemetry:navigation_logs", len(raw_navigation), -1)
        except Exception as e:
            logger.error(f"❌ Error en bulk_create de navigation_logs: {e}")

    # ==========================================
    # 3. VIDEO ENGAGEMENT (Agrupación en RAM + Bulk Upsert)
    # ==========================================
    if raw_video:
        aggregated_metrics = {}
        for item_bytes in raw_video:
            try:
                data = json.loads(item_bytes.decode('utf-8'))
                key = (data['client_id'], data['video_id'])
                
                if key not in aggregated_metrics:
                    aggregated_metrics[key] = {
                        'watch_time_seconds': 0.0,
                        'video_completed': False,
                        'interacted_with_product': False,
                        'added_to_cart_from_video': False,
                        'bought_from_video': False
                    }
                
                metrics = aggregated_metrics[key]
                metrics['watch_time_seconds'] += data['watch_time_seconds']
                metrics['video_completed'] |= data['video_completed']
                metrics['interacted_with_product'] |= data['interacted_with_product']
                metrics['added_to_cart_from_video'] |= data['added_to_cart_from_video']
                metrics['bought_from_video'] |= data['bought_from_video']
            except Exception: pass

        try:
            if aggregated_metrics:
                client_ids = [k[0] for k in aggregated_metrics.keys()]
                video_ids = [k[1] for k in aggregated_metrics.keys()]
                
                existing_logs = VideoEngagementLog.objects.filter(
                    client_id__in=client_ids, 
                    video_id__in=video_ids
                )
                existing_map = {(str(log.client_id), str(log.video_id)): log for log in existing_logs}

                to_update = []
                to_create = []

                for (cid, vid), m in aggregated_metrics.items():
                    if (cid, vid) in existing_map:
                        log = existing_map[(cid, vid)]
                        log.watch_time_seconds += m['watch_time_seconds']
                        log.video_completed = log.video_completed or m['video_completed']
                        log.interacted_with_product = log.interacted_with_product or m['interacted_with_product']
                        log.added_to_cart_from_video = log.added_to_cart_from_video or m['added_to_cart_from_video']
                        log.bought_from_video = log.bought_from_video or m['bought_from_video']
                        to_update.append(log)
                    else:
                        to_create.append(VideoEngagementLog(
                            client_id=cid, video_id=vid, **m
                        ))

                if to_update:
                    VideoEngagementLog.objects.bulk_update(to_update, [
                        'watch_time_seconds', 'video_completed', 'interacted_with_product', 
                        'added_to_cart_from_video', 'bought_from_video'
                    ], batch_size=500)
                
                if to_create:
                    VideoEngagementLog.objects.bulk_create(to_create, batch_size=500)
            redis_conn.ltrim("telemetry:video_engagement", len(raw_video), -1)
        except Exception as e:
            logger.error(f"❌ Error en persistencia de video_engagement: {e}")

    # ==========================================
    # 4. UNMET DEMAND (Bulk Create)
    # ==========================================
    if raw_unmet_demand:
        unmet_logs = []
        for item_bytes in raw_unmet_demand:
            try:
                data = json.loads(item_bytes.decode('utf-8'))
                lat = data.get('lat')
                lng = data.get('lng')
                
                # Nos aseguramos de tener coordenadas válidas antes de instanciar Point
                if lat is not None and lng is not None:
                    unmet_logs.append(UnmetDemandLog(
                        client_id=data.get('client_id'), # Soporta None tranquilamente
                        search_term=data['search_term'],
                        coordinates=Point(x=float(lng), y=float(lat)) # 💡 x=Longitud, y=Latitud
                    ))
            except Exception as e:
                logger.warning(f"⚠️ Error parseando log de UnmetDemandLog (se omitirá): {e}")
                
        try:
            if unmet_logs:
                UnmetDemandLog.objects.bulk_create(unmet_logs, batch_size=500)
            redis_conn.ltrim("telemetry:unmet_demand", len(raw_unmet_demand), -1)
        except Exception as e:
            logger.error(f"❌ Error en bulk_create de unmet_demand: {e}")

@shared_task(ignore_result=True)
def refresh_admin_dashboard_metrics():
    try:
        try:
            res = requests.get('https://ve.dolarapi.com/v1/dolares/oficial', timeout=5)
            bcv_rate = float(res.json().get('promedio', 0.0) or 0.0)
            if bcv_rate > 0:
                cache.set('cm:bcv_official_rate', bcv_rate, timeout=86400)
        except Exception as bcv_err:
            logger.warning(f"⚠️ No se pudo refrescar cm:bcv_official_rate desde dolarapi: {bcv_err}")

        from api.dashboard import build_metrics_for_range
        logger.info("📊 Calculando métricas del Dashboard Admin...")
        now = timezone.now()
        
        periods = {
            '30d': now - timedelta(days=30),
            '90d': now - timedelta(days=90),
            '180d': now - timedelta(days=180),
            '365d': now - timedelta(days=365),
            'all': None
        }
        
        for period, start_date in periods.items():
            # El constructor ya trae las métricas financieras (Bs, USD Actual, Histórico y Diferencial)
            metrics = build_metrics_for_range(start_date, now)
            cache.set(f'admin_dashboard_metrics_{period}', metrics, timeout=86400)
            
        logger.info("✅ Métricas actualizadas con éxito.")
    except Exception as e:
        logger.error(f"❌ Error al calcular métricas: {e}")


@shared_task(bind=True, ignore_result=True, max_retries=2, default_retry_delay=5)
def send_otp_email_task(self, user_email: str, otp_code: str, timestamp_str: str):
    """Despacha el correo OTP de forma asíncrona en Celery para no bloquear workers HTTP."""
    try:
        from api.utils import _deliver_otp_email_sync
        _deliver_otp_email_sync(user_email, otp_code, timestamp_str)
    except Exception as exc:
        logger.error(f"❌ Error en send_otp_email_task hacia {user_email}: {exc}")
        raise self.retry(exc=exc)


@shared_task(name="cartmaker.subscriptions.notify_expiring")
def notify_expiring_subscriptions():
    """Vender ya no depende de una suscripción. El nombre de la tarea se conserva por si queda un mensaje en cola."""
    return


@shared_task(ignore_result=True)
def send_push_notification_task(user_id: str, title: str, body: str, data: dict = None):
    """Despacha notificaciones Push FCM de forma asíncrona en Celery usando NotificationManager."""
    try:
        user = User.objects.filter(id=user_id).first()
        if not user:
            return
        safe_data = {str(k): str(v) for k, v in (data or {}).items()}
        NotificationManager._send_multicast(user=user, title=title, body=body, data_payload=safe_data)
    except Exception as exc:
        logger.warning(f"⚠️ No se pudo enviar push FCM asíncrono al usuario {user_id}: {exc}")


@shared_task(bind=True, ignore_result=True, max_retries=2, default_retry_delay=5)
def send_atlas_invoice_email_task(self, invoice_id: str):
    """Despacha el correo con la factura digital legal de Atlas Plus de forma asíncrona."""
    try:
        from api.utils import _deliver_atlas_invoice_email_sync
        _deliver_atlas_invoice_email_sync(invoice_id)
    except Exception as exc:
        logger.warning(f"⚠️ Error despachando factura digital {invoice_id}: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, ignore_result=True, max_retries=2, default_retry_delay=10)
def send_employee_invitation_email_task(self, to_email: str, context: dict):
    """Despacha el correo de invitación para trabajar en un comercio (sistema de trabajadores)."""
    try:
        from api.utils import _deliver_employee_invitation_email_sync
        _deliver_employee_invitation_email_sync(to_email, context)
    except Exception as exc:
        logger.warning(f"⚠️ Error enviando invitación de trabajador a {to_email}: {exc}")
        raise self.retry(exc=exc)


@shared_task(ignore_result=True)
def expire_and_retry_delivery_offers_task():
    """Expira ofertas de 45 s sin respuesta y reintenta la auto-asignación cada 30 s."""
    try:
        from api.core.delivery import expire_and_retry_offers
        expire_and_retry_offers()
    except Exception as exc:
        logger.warning(f"⚠️ Error en expire_and_retry_delivery_offers_task: {exc}")


@shared_task(bind=True, ignore_result=True, max_retries=2, default_retry_delay=10)
def persist_delivery_trace_task(self, delivery_id: int):
    """Mueve el stream de Redis `dlv:{id}:trace` a `DeliveryTrace` (msgpack+gzip) al concluir la entrega."""
    try:
        from api.core.delivery import persist_delivery_trace
        persist_delivery_trace(delivery_id)
    except Exception as exc:
        logger.warning(f"⚠️ Error persistiendo traza de delivery #{delivery_id}: {exc}")
        raise self.retry(exc=exc)


@shared_task(ignore_result=True)
def cleanup_expired_delivery_traces_task():
    """Borra las trazas GPS con más de 30 días de antigüedad (cumplimiento de Habeas Data, Art. 28)."""
    try:
        from api.core.delivery import cleanup_expired_traces
        cleanup_expired_traces()
    except Exception as exc:
        logger.warning(f"⚠️ Error limpiando trazas vencidas de delivery: {exc}")


@shared_task(ignore_result=True)
def cleanup_old_notifications():
    """
    Mantenimiento nocturno de la tabla `Notification`:
    1. Elimina notificaciones leídas (`is_read=True`) con más de 30 días de antigüedad.
    2. Elimina notificaciones no leídas (`is_read=False`) abandonadas con más de 90 días.
    3. Recorta el exceso de notificaciones leídas para usuarios que superen las 30 más recientes.
    """
    try:
        now = timezone.now()
        read_cutoff = now - timedelta(days=30)
        unread_cutoff = now - timedelta(days=90)

        deleted_old_read, _ = Notification.objects.filter(
            is_read=True,
            created_at__lt=read_cutoff,
        ).delete()

        deleted_stale_unread, _ = Notification.objects.filter(
            is_read=False,
            created_at__lt=unread_cutoff,
        ).delete()

        # Recorte por usuario para quienes acumulen >30 notificaciones leídas
        from django.db.models import Count
        heavy_user_ids = list(
            Notification.objects.filter(is_read=True)
            .values('user_id')
            .annotate(read_count=Count('id'))
            .filter(read_count__gt=30)
            .values_list('user_id', flat=True)[:500]
        )
        deleted_overflow = 0
        for uid in heavy_user_ids:
            overflow_ids = list(
                Notification.objects.filter(user_id=uid, is_read=True)
                .order_by('-created_at')
                .values_list('id', flat=True)[30:]
            )
            if overflow_ids:
                cnt, _ = Notification.objects.filter(id__in=overflow_ids).delete()
                deleted_overflow += cnt

        if deleted_old_read or deleted_stale_unread or deleted_overflow:
            logger.info(
                f"🧹 [Cleanup Notifications] Eliminadas: {deleted_old_read} leídas (>30d), "
                f"{deleted_overflow} leídas excedentes (>30/usuario), {deleted_stale_unread} no leídas (>90d)."
            )
    except Exception as exc:
        logger.warning(f"⚠️ Error en cleanup_old_notifications: {exc}")
