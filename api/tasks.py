from datetime import timedelta

import boto3
from celery import shared_task
from django.contrib.auth import get_user_model
import logging
from django.utils import timezone

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
    Orquestador fail-safe para transcodificación de video.
    Si detecta almacenamiento AWS, intenta delegar la segmentación HLS a MediaConvert.
    Si falla o estamos en entorno local, aborta elegantemente manteniendo el .mp4 original.
    """
    try:
        story = CompanyVideoStory.objects.get(id=story_id)
        
        # 💡 CASO 1: Entorno de Desarrollo Local
        if settings.STORAGE_TYPE != 'aws':
            logger.info(f"ℹ️ Entorno local detectado. Se mantiene el archivo original .mp4 para la historia {story_id}.")
            return

        # Validamos que tengamos las credenciales mínimas configuradas para no disparar llamadas en falso
        if not settings.AWS_MEDIACONVERT_ROLE_ARN or not story.video_file:
            logger.warning(f"⚠️ MediaConvert omitido: Falta AWS_MEDIACONVERT_ROLE_ARN o el archivo base en la historia {story_id}.")
            return

        logger.info(f"📡 Inicializando cliente AWS Elemental MediaConvert para historia {story_id}...")

        # 1. AWS MediaConvert requiere consultar tu endpoint único regional antes de operar
        client_discover = boto3.client(
            'mediaconvert',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME
        )
        
        endpoints = client_discover.describe_endpoints()
        mediaconvert_endpoint = endpoints['Endpoints'][0]['Url']

        # 2. Instanciamos el cliente real conectado a tu endpoint dedicado
        media_client = boto3.client(
            'mediaconvert',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
            endpoint_url=mediaconvert_endpoint
        )

        # Definimos las rutas S3 usando el formato nativo URI s3://
        input_s3_uri = f"s3://{settings.AWS_STORAGE_BUCKET_NAME}/{story.video_file}"
        output_folder_key = f"stories/videos/hls_{story_id}/"
        output_s3_uri = f"s3://{settings.AWS_STORAGE_BUCKET_NAME}/{output_folder_key}"

        # 3. Construimos la estructura de la tarea (Job JSON) para segmentación HLS Serverless
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
                        "SegmentLength": 3, # Segmentos de 3 segundos para el 4G de Venezuela
                        "Destination": output_s3_uri,
                        "MinSegmentLength": 0
                    }
                },
                "Outputs": [{
                    "VideoDescription": {
                        "CodecSettings": {
                            "Codec": "H_264",
                            "H264Settings": {
                                "RateControlMode": "QVBR", # Calidad variable inteligente (Ahorra megas)
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
                    "NameModifier": "_v720p" # Esto generará el archivo index_v720p.m3u8
                }]
            }]
        }

        # 4. Despachamos el Job a la infraestructura de AWS
        logger.info("Sending transcode job to AWS Elemental MediaConvert...")
        response = media_client.create_job(
            Role=settings.AWS_MEDIACONVERT_ROLE_ARN,
            Settings=job_settings
        )
        
        logger.info(f"Job creado exitosamente. ID: {response['Job']['Id']}")

        # 5. Como el proceso es exitoso, actualizamos la firma del video en BD apuntando al playlist index
        # MediaConvert generará el m3u8 sumándole el NameModifier
        story.video_file = f"{output_folder_key}index_v720p.m3u8"
        story.save(update_fields=['video_file'])

        # Limpiamos el caché estructural para forzar la inyección en vivo
        try:
            cache.delete_pattern("cartmaker:struct:*")
        except Exception:
            pass

    except Exception as e:
        # 💡 EL EMBUDO FAIL-SAFE: Si AWS no está configurado, da error de red o no existe el rol,
        # atrapamos el error aquí. El .mp4 original ya está guardado en el bucket, así que no hacemos nada
        # y la aplicación continuará reproduciendo el video de forma tradicional sin romperse.
        print(
            f"""🔔 [Modo Híbrido Activo]: Omitiendo MediaConvert para la historia {story_id}. 
            Motivo: El servicio de transcodificación no está activo o configurado en AWS. 
            Detalle técnico: {e}"""
        )