from celery import shared_task
from django.contrib.auth import get_user_model
import logging
from django.utils import timezone

from web.models import InventoryItemOffer

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
    Busca y elimina todas las ofertas de inventario cuya 
    fecha de validez ya haya pasado.
    """
    try:
        now = timezone.now()
        
        # Filtramos las ofertas donde 'valid_until' es menor estricto que la hora actual
        expired_offers = InventoryItemOffer.objects.filter(valid_until__lt=now)
        
        # Guardamos la cantidad antes de borrar para el log
        count = expired_offers.count()
        
        if count > 0:
            expired_offers.delete()
            logger.info(f"✅ Se eliminaron {count} ofertas expiradas del inventario.")
        
    except Exception as e:
        logger.error(f"❌ Error en cleanup_expired_offers: {e}")