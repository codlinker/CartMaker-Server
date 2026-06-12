from datetime import timedelta

from celery import shared_task
from django.contrib.auth import get_user_model
import logging
from django.utils import timezone

from web.core.firebase_admin import NotificationManager
from .core.platinum_manager import PlatinumEvaluator
from web.models import InventoryItemOffer, InventoryItem, Order
from django.core.cache import cache

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