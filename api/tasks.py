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
from api.core.firebase_admin import NotificationManager
from .core.platinum_manager import PlatinumEvaluator
from api.models import CompanyVideoStory, InventoryItemOffer, InventoryItem, Order
from django.core.cache import cache
from django.conf import settings

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