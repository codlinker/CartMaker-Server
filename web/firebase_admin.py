import logging
from typing import List, Dict, Optional
from firebase_admin import messaging
from firebase_admin.exceptions import FirebaseError
from .models import DeviceToken 

logger = logging.getLogger(__name__)

class NotificationManager:
    """
    Gestor centralizado para el envío de notificaciones push vía Firebase FCM.
    """

    @classmethod
    def _clean_dead_tokens(cls, failed_tokens: List[str]) -> None:
        """
        [Método Privado] Elimina de la base de datos los tokens que Firebase 
        reporta como inválidos o desinstalados.
        """
        if not failed_tokens:
            return
            
        try:
            deleted_count, _ = DeviceToken.objects.only('token').filter(token__in=failed_tokens).delete()
            logger.info(f"Limpieza FCM: Se eliminaron {deleted_count} tokens inactivos de la base de datos.")
        except Exception as e:
            logger.error(f"Error al intentar limpiar tokens muertos en la BD: {e}")

    @classmethod
    def _send_multicast(cls, user, title: str, body: str, data_payload: Optional[Dict] = None) -> None:
        tokens = list(user.fcm_tokens.values_list('token', flat=True))
        print("TOKENS: ", tokens)

        if not tokens:
            print(f"FCM Abortado: Usuario {user.id} sin dispositivos.")
            return
        message = messaging.MulticastMessage(
            notification=messaging.Notification(title=title, body=body),
            data=data_payload or {},
            tokens=tokens,
        )
        try:
            response = messaging.send_each_for_multicast(message)
            
            print(f"FCM Enviado: {response.success_count} éxitos, {response.failure_count} fallos.")

            if response.failure_count > 0:
                failed_tokens = []
                for idx, resp in enumerate(response.responses):
                    if not resp.success:
                        failed_tokens.append(tokens[idx])
                        print(f"Error en token {tokens[idx]}: {resp.exception}")
                cls._clean_dead_tokens(failed_tokens)
        except FirebaseError as e:
            print(f"Error de Firebase: {e}")

    # =====================================================================
    # MÉTODOS PÚBLICOS (Los que llamarás desde tus vistas o señales)
    # =====================================================================

    @classmethod
    def notify_payment_check(cls, user) -> None:
        """
        Notifica al usuario que su pago ha sido validado por un supervisor
        y que su cuenta ha sido convertida a comerciante.
        """
        title = '¡Pago Validado! ✅'
        body = 'Tu suscripción ha sido procesada exitosamente. Ya puedes registrar tus productos en CartMaker.'
        
        # El payload invisible que lee Flutter para actualizar la vista
        data = {
            'type': 'payment_verified',
            'action': 'refresh_home_status'
        }

        logger.info(f"Iniciando notificación de validación de pago para usuario {user.id}")
        cls._send_multicast(user=user, title=title, body=body, data_payload=data)
