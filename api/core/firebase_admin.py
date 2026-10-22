from django.utils import timezone
from django.conf import settings
import logging
import requests
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

        # Garantizamos que todo push de FCM lleve siempre recipient_id y valores tipo string
        normalized_data: Dict[str, str] = {
            'recipient_id': str(user.id),
            'target_user_id': str(user.id),
        }
        if data_payload:
            for k, v in data_payload.items():
                if v is not None:
                    normalized_data[str(k)] = str(v)

        message = messaging.MulticastMessage(
            notification=messaging.Notification(title=title, body=body),
            data=normalized_data,
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
        except Exception as e:
            print(f"Error inesperado enviando FCM multicast: {e}")

    # =====================================================================
    # MÉTODOS PÚBLICOS (Los que llamarás desde tus vistas o señales)
    # =====================================================================

    @classmethod
    def notify_payment_check(
        cls,
        user_id: int,
        subscription_name: str,
        approved: bool,
        payment_id,
        rejection_reason: str = "",
        surplus_amount: float = 0.0,
        invoice_id: str = "",
        invoice_number: str = "",
        invoice_url: str = "",
    ) -> None:
        """
        Notifica al usuario si su pago ha sido validado o no por un supervisor.
        """
        try:
            objective_type = 'atlas' if 'Atlas' in subscription_name else 'merchant'
            
            if approved:
                title = '¡Pago Validado!'
                invoice_suffix = (
                    f" Tu comprobante digital de pago N° <b>{invoice_number}</b> ya está emitido."
                    if invoice_number else ""
                )
                if objective_type == 'atlas':
                    if surplus_amount > 0:
                        body = (
                            f'Hemos aprobado tu pago por la suscripción <b>{subscription_name}</b> y acreditamos '
                            f'tu excedente de <b>{surplus_amount} Bs.</b> a tu billetera.{invoice_suffix}'
                        )
                    else:
                        body = (
                            f'Hemos aprobado tu pago por la suscripción <b>{subscription_name}</b>. '
                            f'Disfruta de tu límite ampliado en Atlas Comprador y Atlas Negocios.{invoice_suffix}'
                        )
                else:
                    if surplus_amount > 0:
                        body = f'Hemos aprobado el pago por la suscripción <b>{subscription_name}</b> y acreditamos tu excedente de <b>{surplus_amount} Bs</b> a tu billetera. Ya puedes configurar tu comercio.'
                    else:
                        body = f'Hemos aprobado el pago por la suscripción <b>{subscription_name}</b>. Ya puedes registrar tus productos en CartMaker.'

                meta = {
                    'payment_id': str(payment_id),
                    'type': 'subscription_payment_checked',
                    'objective': objective_type,
                    'status': 'approved',
                }
                if invoice_id:
                    meta['invoice_id'] = str(invoice_id)
                if invoice_number:
                    meta['invoice_number'] = str(invoice_number)
                if invoice_url:
                    meta['invoice_url'] = str(invoice_url)

                notification = Notification.objects.create(
                    user_id=user_id,
                    section=NotificationSection.HOME,
                    title=title,
                    body=body,
                    category=NotificationCategory.PAYMENT_APPROVED,
                    metadata=meta,
                )
            else:
                title = 'Pago Rechazado'
                body = f'El pago por la suscripción <b>{subscription_name}</b> ha sido rechazado por el siguiente motivo: <b>{rejection_reason}</b>'
                
                notification = Notification.objects.create(
                    user_id=user_id,
                    section=NotificationSection.HOME,
                    title=title,
                    body=body,
                    category=NotificationCategory.PAYMENT_REJECTED,
                    metadata={
                        'payment_id': str(payment_id),
                        'type': 'subscription_payment_checked',
                        'objective': objective_type,
                        'status': 'rejected'
                    }
                )
            
            data = {
                'type': 'subscription_payment_checked',
                'objective': objective_type,
                'notification_id': f"{notification.id}",
                'status': 'approved' if approved else 'rejected',
            }
            if invoice_id:
                data['invoice_id'] = str(invoice_id)
            if invoice_number:
                data['invoice_number'] = str(invoice_number)
            if invoice_url:
                data['invoice_url'] = str(invoice_url)
        except Exception as e:
            print(f"Error armando las notificaciones: {e}")
            return
            
        try:
            user = User.objects.prefetch_related('fcm_tokens').get(id=user_id)
        except User.DoesNotExist:
            print("Error en Notification Manager -> No se encontro el usuario con id: ", user_id)
            return
            
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
            metadata={
                'order_id': str(order_id),
                'recipient_id': str(merchant_id),
                'is_merchant_receiver': True,
            }
        )
        
        # 💡 CAMBIO AQUÍ: Ahora especificamos que el evento es 'new_order' e incluimos recipient_id
        data = {
            'type': 'new_order',
            'order_id': str(order_id),
            'recipient_id': str(merchant_id),
            'is_merchant_receiver': 'true',
        } 
        
        try:
            user = User.objects.prefetch_related('fcm_tokens').get(id=merchant_id)
            cls._send_multicast(user=user, title=title, body=body, data_payload=data)
        except Exception as e:
            logger.error(f"Fallo al notificar creación de orden al comerciante: {e}")

    @classmethod
    def notify_order_status_change(
        cls,
        user_id: int,
        order_id: int,
        title: str,
        body: str,
        is_merchant: bool,
        new_status: int = -1,
        reported_by_role: Optional[str] = None,
        reporter_id: Optional[str] = None,
        support_ticket_id: Optional[int] = None,
        extra_data: Optional[Dict] = None,
    ) -> None:
        """ 
        Notifica cambios de estado (Cancelado, Enviado, Completado, Reportado, Resuelto) cruzados entre cliente y comerciante. 
        """
        section = NotificationSection.MERCHANT_ORDERS if is_merchant else NotificationSection.ORDERS
        meta = {
            'order_id': str(order_id),
            'recipient_id': str(user_id),
            'is_merchant_receiver': bool(is_merchant),
            'status': int(new_status),
        }
        if reported_by_role:
            meta['reported_by_role'] = str(reported_by_role)
        if reporter_id:
            meta['reporter_id'] = str(reporter_id)
            meta['reported_by_user_id'] = str(reporter_id)
        if support_ticket_id is not None:
            meta['support_ticket_id'] = int(support_ticket_id)
            meta['active_ticket_id'] = int(support_ticket_id)
        if extra_data:
            for k, v in extra_data.items():
                if v is not None:
                    meta[str(k)] = v

        notification = Notification.objects.create(
            user_id=user_id,
            section=section,
            title=title,
            body=body,
            category=NotificationCategory.ORDER_STATUS_CHANGED,
            metadata=meta
        )
        
        # 💡 AÑADIMOS EL FLAG DE MERCHANT, RECIPIENT_ID Y ATRIBUCIÓN DE REPORTE PARA FLUTTER
        data = {
            'type': 'order_status_changed',
            'order_id': str(order_id),
            'status': str(new_status),
            'recipient_id': str(user_id),
            'target_user_id': str(user_id),
            'is_merchant_receiver': str(is_merchant).lower(),
            'notification_id': str(notification.id),
        }
        if reported_by_role:
            data['reported_by_role'] = str(reported_by_role)
        if reporter_id:
            data['reporter_id'] = str(reporter_id)
            data['reported_by_user_id'] = str(reporter_id)
        if support_ticket_id is not None:
            data['support_ticket_id'] = str(support_ticket_id)
            data['active_ticket_id'] = str(support_ticket_id)
        if extra_data:
            for k, v in extra_data.items():
                if v is not None:
                    data[str(k)] = str(v)

        # Emitimos también por WebSocket en tiempo real hacia la sala del usuario y de la orden
        try:
            requests.post(
                f"{settings.INTERNAL_WEBSOCKETS_URL}internal/emit-order-status",
                json={
                    'order_id': order_id,
                    'status': int(new_status),
                    'recipient_id': str(user_id),
                    'is_merchant_receiver': bool(is_merchant),
                    'reported_by_role': reported_by_role,
                    'reporter_id': str(reporter_id) if reporter_id else None,
                    'reported_by_user_id': str(reporter_id) if reporter_id else None,
                    'support_ticket_id': support_ticket_id,
                    'active_ticket_id': support_ticket_id,
                    'title': title,
                    'body': body,
                },
                headers={'X-Microservice-Token': settings.SECRET_KEY},
                timeout=2,
            )
        except Exception:
            pass
        
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
        is_client_sender = (str(order.client.id) == str(sender_id))
        
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

    @classmethod
    def notify_new_support_message(cls, ticket, sender_id: int, text: str) -> None:
        sender_id_str = str(sender_id)
        sender_role = ticket.get_participant_role(sender_id) if hasattr(ticket, 'get_participant_role') else 'support'
        if sender_role == 'support':
            title = f"Soporte CartMaker (Ticket #{ticket.id})"
        elif sender_role == 'merchant':
            company = ticket.get_merchant_company() if hasattr(ticket, 'get_merchant_company') else None
            m_name = company.name if (company and company.name) else "Comercio"
            title = f"{m_name} en Soporte (Ticket #{ticket.id})"
        else:
            buyer = ticket.get_buyer_user() if hasattr(ticket, 'get_buyer_user') else ticket.client
            b_name = f"{buyer.first_name} {buyer.last_name}".strip() if buyer else "Comprador"
            title = f"{b_name} en Soporte (Ticket #{ticket.id})"

        body = text if len(text) <= 60 else text[:60] + '...'

        target_users = []
        if ticket.client_id and str(ticket.client_id) != sender_id_str:
            target_users.append(ticket.client_id)
        if ticket.order_id and ticket.order:
            if ticket.order.client_id and str(ticket.order.client_id) != sender_id_str and ticket.order.client_id not in target_users:
                target_users.append(ticket.order.client_id)
            company = ticket.get_merchant_company() if hasattr(ticket, 'get_merchant_company') else None
            if company and company.owner_id and str(company.owner_id) != sender_id_str and company.owner_id not in target_users:
                target_users.append(company.owner_id)

        for target_uid in target_users:
            try:
                existing_notif = Notification.objects.filter(
                    user_id=target_uid,
                    category=NotificationCategory.NEW_CHAT_MESSAGE,
                    is_read=False,
                    metadata__ticket_id=str(ticket.id),
                ).first()
                if existing_notif:
                    existing_notif.title = title
                    existing_notif.body = body
                    existing_notif.created_at = timezone.now()
                    existing_notif.save(update_fields=['title', 'body', 'created_at'])
                    notification = existing_notif
                else:
                    notification = Notification.objects.create(
                        user_id=target_uid,
                        section=NotificationSection.HELP,
                        title=title,
                        body=body,
                        category=NotificationCategory.NEW_CHAT_MESSAGE,
                        metadata={
                            'type': 'new_support_message',
                            'ticket_id': str(ticket.id),
                            'order_id': str(ticket.order_id) if ticket.order_id else None,
                            'recipient_id': str(target_uid),
                            'sender_role': sender_role,
                        },
                    )
                data = {
                    'type': 'new_support_message',
                    'ticket_id': str(ticket.id),
                    'notification_id': str(notification.id),
                    'recipient_id': str(target_uid),
                    'sender_role': sender_role,
                }
                if ticket.order_id:
                    data['order_id'] = str(ticket.order_id)
                user_obj = User.objects.prefetch_related('fcm_tokens').get(id=target_uid)
                cls._send_multicast(user=user_obj, title=title, body=body, data_payload=data)
            except Exception as e:
                logger.error(f"Fallo al notificar mensaje de soporte a {target_uid}: {e}")

    @classmethod
    def notify_ticket_closed(
        cls,
        user_id,
        ticket_id: int,
        reason_str: str,
        resolution_note: Optional[str] = None,
        order_id: Optional[int] = None,
    ) -> None:
        title = f"Ticket de Soporte #{ticket_id} Cerrado"
        body = f"Soporte CartMaker ha finalizado la revisión del ticket #{ticket_id} ({reason_str})."
        if resolution_note:
            body += f" Conclusión: {resolution_note}"
        try:
            notification = Notification.objects.create(
                user_id=user_id,
                section=NotificationSection.HELP,
                title=title,
                body=body,
                category=NotificationCategory.ORDER_STATUS_CHANGED,
                metadata={
                    'type': 'ticket_closed',
                    'ticket_id': str(ticket_id),
                    'order_id': str(order_id) if order_id else None,
                    'close_reason': reason_str,
                    'resolution_note': resolution_note,
                    'recipient_id': str(user_id),
                },
            )
            data = {
                'type': 'ticket_closed',
                'ticket_id': str(ticket_id),
                'notification_id': str(notification.id),
                'close_reason': str(reason_str),
                'recipient_id': str(user_id),
            }
            if resolution_note:
                data['resolution_note'] = str(resolution_note)
            if order_id:
                data['order_id'] = str(order_id)
            user_obj = User.objects.prefetch_related('fcm_tokens').get(id=user_id)
            cls._send_multicast(user=user_obj, title=title, body=body, data_payload=data)
        except Exception as e:
            logger.error(f"Fallo al notificar cierre de ticket a {user_id}: {e}")

    @classmethod
    def notify_workforce_event(
        cls,
        user_id,
        title: str,
        body: str,
        event_type: str = 'workforce_update',
        category: int = NotificationCategory.EMPLOYEE_UPDATE,
        section: int = NotificationSection.MERCHANT_EMPLOYEES,
        extra_data: Optional[Dict] = None,
    ) -> None:
        """
        Notifica eventos del sistema de trabajadores (invitaciones, altas, suspensiones, renuncias).
        Persiste la notificación en la bandeja de la app y envía el push FCM.
        """
        meta = {
            'type': event_type,
            'recipient_id': str(user_id),
        }
        if extra_data:
            for k, v in extra_data.items():
                if v is not None:
                    meta[str(k)] = v
        try:
            notification = Notification.objects.create(
                user_id=user_id,
                section=section,
                title=title,
                body=body,
                category=category,
                metadata=meta,
            )
        except Exception as e:
            logger.error(f"Fallo al registrar notificación de trabajadores para {user_id}: {e}")
            return

        data = {
            'type': event_type,
            'notification_id': str(notification.id),
            'recipient_id': str(user_id),
        }
        if extra_data:
            for k, v in extra_data.items():
                if v is not None:
                    data[str(k)] = str(v)
        try:
            user_obj = User.objects.prefetch_related('fcm_tokens').get(id=user_id)
            cls._send_multicast(user=user_obj, title=title, body=body, data_payload=data)
        except Exception as e:
            logger.error(f"Fallo al enviar push de trabajadores a {user_id}: {e}")
