from django.utils import timezone
import logging
from typing import List, Dict, Optional
from firebase_admin import messaging
from firebase_admin.exceptions import FirebaseError
from ..models import DeviceToken, User, Notification, NotificationCategory, NotificationSection

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
    def notify_payment_check(cls, user_id:int, subscription_name:str, approved:bool, payment_id:id, rejection_reason="", surplus_amount:float=0.0) -> None:
        """
        Notifica al usuario si su pago ha sido validado o no por un supervisor.
        """
        try:
            if approved:
                title = '¡Pago Validado!'
                
                # Lógica del Saldo a Favor
                if surplus_amount > 0:
                    body = f'Hemos aprobado el pago por la suscripción <b>{subscription_name}</b> y acreditamos tu excedente de <b>{surplus_amount} Bs</b> a tu billetera. Ya puedes configurar tu comercio.'
                else:
                    body = f'Hemos aprobado el pago por la suscripción <b>{subscription_name}</b>. Ya puedes registrar tus productos en CartMaker.'
                    
                notification = Notification.objects.create(
                    user_id=user_id,
                    section=NotificationSection.HOME,
                    title=title,
                    body=body,
                    category=NotificationCategory.PAYMENT_APPROVED,
                    metadata={'payment_id':str(payment_id)}
                )
            else:
                # Lógica de rechazo (se mantiene igual)
                title = 'Pago Rechazado'
                body = f'El pago por la suscripción <b>{subscription_name}</b> ha sido rechazado por el siguiente motivo: <b>{rejection_reason}</b>'
                notification = Notification.objects.create(
                    user_id=user_id,
                    section=NotificationSection.HOME,
                    title=title,
                    body=body,
                    category=NotificationCategory.PAYMENT_REJECTED,
                    metadata={'payment_id':str(payment_id)}
                )
            
            data = {
                'type': 'merchant_payment_checked',
                'notification_id':f"{notification.id}",
                'status':'approved' if approved else 'rejected'
            }
        except Exception as e:
            print(f"Error armando las notificaciones: {e}")
            raise e
            
        try:
            user = User.objects.prefetch_related('fcm_tokens').get(id=user_id)
        except User.DoesNotExists:
            print("Error en Notification Manager -> No se encontro el usuario con id: ", user_id)
            raise User.DoesNotExist
            
        cls._send_multicast(user=user, title=title, body=body.replace('<b>', '').replace('</b>', ''), data_payload=data)

    @classmethod
    def notify_new_question(cls, merchant_user_id: int, item_name: str, item_id: str, question_id: int) -> None:
        """ Notifica al dueño del comercio que tiene una nueva pregunta en su producto. """
        title = 'Tienes una nueva duda'
        body = f'Un cliente acaba de preguntar sobre tu producto: {item_name}.'
        
        notification = Notification.objects.create(
            user_id=merchant_user_id,
            section=NotificationSection.MERCHANT_QUESTIONS,
            title=title,
            body=body,
            category=NotificationCategory.NEW_QUESTION,
            metadata={
                'type': 'new_question',
                'item_id': str(item_id),
                'question_id': str(question_id) # 💡 Vital para Flutter
            }
        )
        
        # 💡 Este es el payload silencioso que despierta a Flutter
        data = {'type': 'new_question', 'question_id': str(question_id)} 
        
        try:
            user = User.objects.prefetch_related('fcm_tokens').get(id=merchant_user_id)
            cls._send_multicast(user=user, title=title, body=body, data_payload=data)
        except Exception as e:
            logger.error(f"Fallo al notificar pregunta: {e}")

    @classmethod
    def notify_new_answer(cls, user_id: int, company_name: str, item_name: str, item_id: str, target_type: str) -> None:
        title = 'Te respondieron'
        body = f'{company_name} acaba de responderte sobre el producto: {item_name}.'
        
        notification = Notification.objects.create(
            user_id=user_id,
            section=NotificationSection.HOME,
            title=title,
            body=body,
            category=NotificationCategory.NEW_ANSWER,
            metadata={
                'type': 'new_answer',
                'item_id': str(item_id),
                'target_type': target_type # 💡 AHORA FLUTTER SABRÁ QUÉ ABRIR
            }
        )
        
        data = {'type': 'generic_refresh'} 
        
        try:
            user = User.objects.prefetch_related('fcm_tokens').get(id=user_id)
            cls._send_multicast(user=user, title=title, body=body, data_payload=data)
        except Exception as e:
            logger.error(f"Fallo al notificar pregunta: {e}")

    @classmethod
    def notify_order_created(cls, merchant_id: int, order_id: int, store_name: str, total: float) -> None:
        """ Notifica al comerciante que ha ingresado una nueva venta en su sucursal. """
        title = '¡Nueva orden recibida!'
        body = f'Has recibido el pedido N° {order_id} en {store_name} por un total de {total}$.'
        
        notification = Notification.objects.create(
            user_id=merchant_id,
            section=NotificationSection.MERCHANT_ORDERS,
            title=title,
            body=body,
            category=NotificationCategory.NEW_ORDER,
            metadata={'order_id': str(order_id)}
        )
        
        # 💡 CAMBIO AQUÍ: Ahora especificamos que el evento es 'new_order'
        data = {'type': 'new_order', 'order_id': str(order_id)} 
        
        try:
            user = User.objects.prefetch_related('fcm_tokens').get(id=merchant_id)
            cls._send_multicast(user=user, title=title, body=body, data_payload=data)
        except Exception as e:
            logger.error(f"Fallo al notificar creación de orden al comerciante: {e}")

    @classmethod
    def notify_order_status_change(cls, user_id: int, order_id: int, title: str, body: str, is_merchant: bool, new_status: int = -1) -> None:
        """ 
        Notifica cambios de estado (Cancelado, Enviado, Completado) cruzados entre cliente y comerciante. 
        """
        section = NotificationSection.MERCHANT_ORDERS if is_merchant else NotificationSection.ORDERS
        
        notification = Notification.objects.create(
            user_id=user_id,
            section=section,
            title=title,
            body=body,
            category=NotificationCategory.ORDER_STATUS_CHANGED,
            metadata={'order_id': str(order_id)}
        )
        
        # 💡 AÑADIMOS EL FLAG DE MERCHANT PARA FLUTTER
        data = {
            'type': 'order_status_changed',
            'order_id': str(order_id),
            'status': str(new_status),
            'is_merchant_receiver': str(is_merchant).lower() # <-- ¡Línea clave!
        } 
        
        try:
            user = User.objects.prefetch_related('fcm_tokens').get(id=user_id)
            cls._send_multicast(user=user, title=title, body=body, data_payload=data)
        except Exception as e:
            logger.error(f"Fallo en cruce de notificación de orden: {e}")

    @classmethod
    def notify_new_chat_message(cls, order, sender_id: int, text: str) -> None:
        """ 
        Notifica un nuevo mensaje de chat cruzado entre cliente y vendedor.
        Agrupa inteligentemente los mensajes para no saturar la BD.
        """
        is_client_sender = (order.client.id == sender_id)
        
        if is_client_sender:
            receiver = order.store.company.owner
            title = f"Nuevo mensaje de {order.client.first_name}"
        else:
            receiver = order.client
            title = f"Nuevo mensaje de {order.store.company.name}"
            
        # Acortamos el texto para la previsualización
        body = text if len(text) <= 45 else text[:45] + '...'
        
        try:
            # =====================================================================
            # 💡 MAGIA DE AGRUPACIÓN: Buscamos una alerta previa no leída de esta orden
            # =====================================================================
            existing_notif = Notification.objects.filter(
                user_id=receiver.id,
                category=NotificationCategory.NEW_CHAT_MESSAGE,
                is_read=False,
                metadata__order_id=str(order.id) # Magia de Postgres para buscar dentro del JSON
            ).first()

            if existing_notif:
                # ACTUALIZAMOS: Pisamos el texto viejo con el nuevo y renovamos la fecha
                existing_notif.body = body
                existing_notif.created_at = timezone.now() # Para que suba al tope de la lista en Flutter
                existing_notif.save(update_fields=['body', 'created_at'])
                
                notification = existing_notif
                logger.info(f"FCM: Notificación de chat agrupada/actualizada (ID: {notification.id})")
            else:
                # CREAMOS: Es el primer mensaje o el usuario ya había leído los anteriores
                notification = Notification.objects.create(
                    user_id=receiver.id,
                    section=NotificationSection.HOME, 
                    title=title,
                    body=body,
                    category=NotificationCategory.NEW_CHAT_MESSAGE,
                    metadata={
                        'type': 'new_chat_message',
                        'order_id': str(order.id),
                        'is_merchant_receiver': is_client_sender
                    }
                )
                logger.info(f"FCM: Nueva notificación de chat creada (ID: {notification.id})")
            
            # =====================================================================
            # 🚀 ENVIAMOS EL PAYLOAD ACTUALIZADO A FIREBASE
            # =====================================================================
            data = {
                'type': 'new_chat_message',
                'order_id': str(order.id),
                'notification_id': str(notification.id),
                'is_merchant_receiver': str(is_client_sender).lower()
            }
            
            user_obj = User.objects.prefetch_related('fcm_tokens').get(id=receiver.id)
            cls._send_multicast(user=user_obj, title=title, body=body, data_payload=data)
            
        except Exception as e:
            logger.error(f"Fallo al notificar mensaje de chat agrupado: {e}")
