import logging
from typing import List, Dict, Optional
from firebase_admin import messaging
from firebase_admin.exceptions import FirebaseError
from .models import DeviceToken, User, Notification, NotificationCategory, NotificationSection

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
            raise e

    # =====================================================================
    # MÉTODOS PÚBLICOS (Los que llamarás desde tus vistas o señales)
    # =====================================================================

    @classmethod
    def notify_payment_check(cls, user_id:int, subscription_name:str, approved:bool, payment_id:id, rejection_reason="") -> None:
        """
        Notifica al usuario si su pago ha sido validado o no por un supervisor.
        """
        try:
            if approved:
                title = '¡Pago Validado!'
                body = f'Hemos aprobado el pago por la suscripción <b>{subscription_name}</b>. Ya puedes registrar tus productos en CartMaker.'
                Notification.objects.create(
                    user_id=user_id,
                    section=NotificationSection.HOME,
                    title=title,
                    body=body,
                    category=NotificationCategory.PAYMENT_APPROVED,
                    metadata={'payment_id':str(payment_id)}
                )
            else:
                title = 'Pago Rechazado'
                body = f'El pago por la suscripción <b>{subscription_name}</b> ha sido rechazado por el siguiente motivo: <b>{rejection_reason}</b>'
                Notification.objects.create(
                    user_id=user_id,
                    section=NotificationSection.HOME,
                    title=title,
                    body=body,
                    category=NotificationCategory.PAYMENT_REJECTED,
                    metadata={'payment_id':str(payment_id)}
                )

            data = {
                'type': 'merchant_payment_checked',
            }
        except Exception as e:
            print(f"Error armando las notificaciones: {e}")
            raise e
        try:
            user = User.objects.prefetch_related('fcm_tokens').get(id=user_id)
        except User.DoesNotExists:
            print("Error en Notification Manager -> No se encontro el usuario con id: ", user_id)
            raise User.DoesNotExist
        cls._send_multicast(user=user, title=title, body=body, data_payload=data)
