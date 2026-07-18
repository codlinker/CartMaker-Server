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
from django.core.cache import cache
from django.utils.dateparse import parse_datetime
from django.conf import settings
from django.contrib.gis.geos import Point
from django.db.models import Sum, F, FloatField, ExpressionWrapper

logger = logging.getLogger(__name__)
User = get_user_model()

@shared_task(ignore_result=True)
def update_rolling_template(user_id, new_vector):
    try:
        user = User.objects.only('biometric_vector').get(id=user_id)
        old_vector = user.biometric_vector
        if old_vector is None or len(old_vector) == 0:
            return

        # Alpha 0.1 (Aprendizaje suave)
        alpha = 0.1
        updated_vector = [(1 - alpha) * o + alpha * n for o, n in zip(old_vector, new_vector)]
        
        user.biometric_vector = updated_vector
        user.save(update_fields=['biometric_vector'])
        
        logger.info(f"✅ Rolling Template actualizado para el usuario {user_id}")
        
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
            
            # Iteramos los ítems afectados para limpiar el caché de sus respectivas zonas
            for item_id in affected_item_ids:
                try:
                    item = InventoryItem.objects.select_related('store__location').get(id=item_id)
                    location = item.store.location
                    approx_lat = round(location.coordinates.y, 3)
                    approx_lng = round(location.coordinates.x, 3)
                    
                    # Forzamos la regeneración del esqueleto estructural eliminando la llave de la zona
                    cache.delete_pattern(f"cartmaker:struct:home:{approx_lat}:{approx_lng}:*")
                    
                    # Adicionalmente, eliminamos su llave volátil para que el método _stitch_and_filter_results
                    # rehidrate en caliente el nuevo estado sin la oferta activa
                    cache.delete(f"cartmaker:volatile:item:{item_id}")
                    
                except Exception as e:
                    # Si un ítem fue borrado en paralelo, continuamos con el resto del lote de invalidación
                    logger.warning(f"No se pudo invalidar el caché para el item {item_id}: {e}")
                    continue
            
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
            matrix = json.loads(matrix_data) if isinstance(matrix_data, str) else matrix_data
            
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
                    ], capture_output=True, text=True)
                    
                    # 💡 2. Filtrar Thumbnail en S3
                    result_t = subprocess.run([
                        'ffmpeg', '-y', '-i', local_thumb_in, 
                        '-vf', vf_string, local_thumb_out
                    ], capture_output=True, text=True)

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
                ], capture_output=True, text=True)

                # 💡 2. Filtrar Thumbnail Local
                result_t = subprocess.run([
                    'ffmpeg', '-y', '-i', absolute_thumb_path, 
                    '-vf', vf_string, local_thumb_out_path
                ], capture_output=True, text=True)

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
            cache.delete_pattern("cartmaker:struct:*")
        except Exception:
            pass

    except Exception as e:
        logger.error(f"❌ Error crítico en la transcodificación de la historia {story_id}: {e}")

@shared_task(ignore_result=True)
def process_analytics_batch():
    """
    Barre todas las colas de telemetría de CartMaker en Redis y 
    procesa las inserciones y actualizaciones masivas hacia PostgreSQL.
    """
    try:
        redis_conn = cache.client.get_client()
    except Exception as e:
        logger.error(f"❌ Error al conectar con Redis para analíticas: {e}")
        return

    # Extraemos todo usando un Pipeline para máxima velocidad
    pipeline = redis_conn.pipeline()
    
    # 💡 Agregamos la nueva cola al final de la lista
    queues = [
        "telemetry:product_views", 
        "telemetry:store_views", 
        "telemetry:navigation_logs", 
        "telemetry:video_engagement",
        "telemetry:unmet_demand" 
    ]
    
    for q in queues:
        pipeline.lrange(q, 0, -1)
        pipeline.delete(q)
        
    results = pipeline.execute()
    
    # results agrupa en pares [lista_data, bool_delete, lista_data, bool_delete...]
    raw_products = results[0]
    raw_stores = results[2]
    raw_navigation = results[4]
    raw_video = results[6]
    raw_unmet_demand = results[8] # 💡 Extraemos la data de las búsquedas fallidas

    def parse_aware_datetime(dt_str):
        if not dt_str: return None
        parsed = parse_datetime(str(dt_str))
        if parsed and timezone.is_naive(parsed):
            return timezone.make_aware(parsed)
        return parsed

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
        if store_logs:
            StoreViewLog.objects.bulk_create(store_logs, batch_size=500)

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
        if nav_logs:
            UserNavigationLog.objects.bulk_create(nav_logs, batch_size=500)

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
                
        if unmet_logs:
            try:
                UnmetDemandLog.objects.bulk_create(unmet_logs, batch_size=500)
            except Exception as e:
                logger.error(f"❌ Error en bulk_create de unmet_demand: {e}")

@shared_task(ignore_result=True)
def refresh_admin_dashboard_metrics():
    try:
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

@shared_task(name="cartmaker.subscriptions.notify_expiring")
def notify_expiring_subscriptions():
    """
    Revisa suscripciones activas y notifica si están próximas a vencer.
    También auto-resetea las banderas si detecta que una suscripción fue renovada.
    """
    try:
        logger.info("⏳ Revisando suscripciones próximas a vencer...")
        now = timezone.now()
        
        # Filtramos suscripciones activas con fecha de expiración
        active_subs = MerchantSubscription.objects.select_related('merchant', 'plan').filter(
            valid_until__isnull=False, 
            merchant__company__isnull=False
        )
        
        for sub in active_subs:
            time_left = sub.valid_until - now
            
            # Si ya expiró, lo ignoramos en este bucle
            if time_left.total_seconds() <= 0:
                continue
                
            days_left = time_left.days
            hours_left = time_left.seconds // 3600
            
            # 🔄 AUTO-RESET: Si tiene más de 5 días, es una suscripción sana. Limpiamos.
            if days_left > 5:
                if sub.notified_5_days or sub.notified_1_day or sub.notified_hours:
                    sub.notified_5_days = False
                    sub.notified_1_day = False
                    sub.notified_hours = False
                    sub.save(update_fields=['notified_5_days', 'notified_1_day', 'notified_hours'])
                continue 
            
            # ⚠️ EVALUACIÓN DE ALERTAS
            if days_left == 5 and not sub.notified_5_days:
                _send_expiration_push(sub, "5 días")
                sub.notified_5_days = True
                sub.save(update_fields=['notified_5_days'])
                
            elif days_left == 1 and not sub.notified_1_day:
                _send_expiration_push(sub, "1 día")
                sub.notified_1_day = True
                sub.save(update_fields=['notified_1_day'])
                
            elif days_left == 0 and hours_left <= 12 and not sub.notified_hours:
                _send_expiration_push(sub, f"{hours_left} horas")
                sub.notified_hours = True
                sub.save(update_fields=['notified_hours'])
                
    except Exception as e:
        logger.error(f"❌ Error en notify_expiring_subscriptions: {e}")

def _send_expiration_push(subscription, time_str):
    """ Función helper para disparar la notificación Push usando Firebase """
    NotificationManager.send_push(
        user_id=subscription.merchant.id,
        title="¡Tu suscripción vence pronto! ⚠️",
        body=f"A tu plan {subscription.plan.name} le quedan {time_str}. Renueva a tiempo para no perder visibilidad.",
        data={
            "type": "subscription_expiring",
            "time_left": time_str
        }
    )