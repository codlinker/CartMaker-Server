from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny

from api.core.firebase_admin import NotificationManager
from .models import ChatMessage, PredefinedMessage
from api.models import Order, SupportMessage, SupportTicket
from .permissions import IsNodeMicroservice
from django.db import transaction
from django.utils import timezone
from api.cos import storage_manager

ALLOWED_CHAT_MEDIA_EXTENSIONS = {
    'jpg', 'jpeg', 'png', 'webp', 'gif',
    'mp3', 'wav', 'ogg', 'm4a', 'aac', 'webm',
    'mp4', 'mov', 'pdf'
}
MAX_CHAT_MEDIA_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB


def _validate_chat_media(file_obj):
    if not file_obj:
        return None, Response({"error": "No se envió ningún archivo"}, status=status.HTTP_400_BAD_REQUEST)
    if file_obj.size > MAX_CHAT_MEDIA_SIZE_BYTES:
        return None, Response({"error": "El archivo supera el tamaño máximo permitido (15MB)."}, status=status.HTTP_400_BAD_REQUEST)
    extension = file_obj.name.rsplit('.', 1)[-1].lower() if '.' in file_obj.name else ''
    if extension not in ALLOWED_CHAT_MEDIA_EXTENSIONS:
        return None, Response({"error": "Formato de archivo no permitido."}, status=status.HTTP_400_BAD_REQUEST)
    return extension, None


def _parse_pagination(request, default_limit=15, max_limit=100):
    try:
        offset = max(0, int(request.query_params.get('offset', 0)))
    except (ValueError, TypeError):
        offset = 0
    try:
        limit = min(max_limit, max(1, int(request.query_params.get('limit', default_limit))))
    except (ValueError, TypeError):
        limit = default_limit
    return offset, limit


# =========================================================================
# 1. ENDPOINT PARA FLUTTER (Historial)
# =========================================================================
class ChatViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def history(self, request):
        """ Devuelve el historial paginado de un chat """
        order_id = request.query_params.get('order_id')
        offset, limit = _parse_pagination(request)
        
        if not order_id:
            return Response({"error": "Falta el ID de la orden."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            order = Order.objects.select_related('store__company').get(id=order_id)
            is_client = order.client_id == request.user.id
            is_merchant = order.store.company.owner_id == request.user.id

            if not is_client and not is_merchant:
                return Response({"error": "No tienes acceso."}, status=status.HTTP_403_FORBIDDEN)

            # 💡 Traemos los últimos X mensajes ordenados por fecha descendente
            messages = ChatMessage.objects.filter(order=order).select_related('sender').order_by('-created_at')[offset:offset+limit]
            
            # 💡 Invertimos la lista en memoria para que Flutter los reciba cronológicamente
            data = [msg.get_json() for msg in messages][::-1]
            
            return Response({
                'data': data,
                'next_offset': offset + limit if len(data) == limit else None
            }, status=status.HTTP_200_OK)
            
        except Order.DoesNotExist:
            return Response({"error": "La orden no existe."}, status=status.HTTP_404_NOT_FOUND)
        
    # =========================================================================
    # 💡 NUEVO ENDPOINT DEDICADO A LA MULTIMEDIA
    # =========================================================================
    @action(detail=False, methods=['post'], url_path='upload-media')
    def upload_media(self, request):
        file_obj = request.FILES.get('file')
        extension, error_response = _validate_chat_media(file_obj)
        if error_response:
            return error_response
        
        file_name = f"chat_{request.user.id}_{timezone.localtime(timezone.now()).strftime('%d-%m-%Y_%H-%M-%S')}.{extension}"
        folder = "chat_media"
        
        # Usamos tu storage_manager para guardarlo en local o S3
        relative_path = storage_manager.save_file(file_obj, folder, file_name)
        
        if relative_path:
            return Response({
                "message": "Archivo subido",
                "url": relative_path
            }, status=status.HTTP_200_OK)
            
        return Response({"error": "Error al guardar el archivo en el storage"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    
    @action(detail=False, methods=['get', 'post', 'delete'], url_path='predefined-messages')
    def predefined_messages(self, request):
        """ CRUD para mensajes rápidos de la compañía """
        # Obtenemos el order_id dependiendo del método HTTP
        order_id = request.query_params.get('order_id') if request.method in ['GET', 'DELETE'] else request.data.get('order_id')
        
        if not order_id:
            return Response({"error": "Falta el ID de la orden."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            order = Order.objects.select_related('store__company').get(id=order_id)
            company = order.store.company
            
            # Validamos que el usuario logueado sea el dueño
            if company.owner_id != request.user.id:
                return Response({"error": "No tienes acceso a esta compañía."}, status=status.HTTP_403_FORBIDDEN)

            if request.method == 'GET':
                msgs = PredefinedMessage.objects.filter(company=company)
                return Response({'data': [m.get_json() for m in msgs]}, status=status.HTTP_200_OK)
                
            elif request.method == 'POST':
                title = request.data.get('title', 'Mensaje Rápido')
                text = request.data.get('text')
                
                if not text:
                    return Response({"error": "El texto es requerido"}, status=status.HTTP_400_BAD_REQUEST)
                
                if PredefinedMessage.objects.filter(company=company).count() >= 20:
                    return Response({"error": "Límite alcanzado para esta empresa."}, status=status.HTTP_400_BAD_REQUEST)

                msg = PredefinedMessage.objects.create(company=company, title=title, text=text)
                return Response({'data': msg.get_json()}, status=status.HTTP_201_CREATED)

            # 💡 NUEVA LÓGICA DE ELIMINACIÓN
            elif request.method == 'DELETE':
                message_id = request.query_params.get('message_id')
                if not message_id:
                    return Response({"error": "Falta el ID del mensaje a eliminar."}, status=status.HTTP_400_BAD_REQUEST)
                
                try:
                    msg = PredefinedMessage.objects.get(id=message_id, company=company)
                    msg.delete()
                    return Response({"success": True, "message": "Eliminado correctamente"}, status=status.HTTP_200_OK)
                except PredefinedMessage.DoesNotExist:
                    return Response({"error": "El mensaje no existe o ya fue eliminado."}, status=status.HTTP_404_NOT_FOUND)

        except Order.DoesNotExist:
            return Response({"error": "La orden no existe."}, status=status.HTTP_404_NOT_FOUND)
        
class SupportChatViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def history(self, request):
        ticket_id = request.query_params.get('ticket_id')
        offset, limit = _parse_pagination(request)
        
        try:
            ticket = SupportTicket.objects.get(id=ticket_id)
            is_client = (ticket.client_id == request.user.id)
            is_agent = (ticket.agent_id == request.user.id)
            is_staff_support = request.user.is_superuser or getattr(request.user, 'can_check_support', False)

            if not (is_client or is_agent or is_staff_support):
                return Response({"error": "No tienes acceso a este ticket."}, status=status.HTTP_403_FORBIDDEN)

            messages = SupportMessage.objects.filter(ticket=ticket).select_related('sender').order_by('-created_at')[offset:offset+limit]
            data = [msg.get_json() for msg in messages][::-1]
            return Response({'data': data, 'next_offset': offset + limit if len(data) == limit else None}, status=status.HTTP_200_OK)
        except SupportTicket.DoesNotExist:
            return Response({"error": "No existe"}, status=status.HTTP_404_NOT_FOUND)
        
    @action(detail=False, methods=['post'], url_path='upload-media')
    def upload_media(self, request):
        file_obj = request.FILES.get('file')
        extension, error_response = _validate_chat_media(file_obj)
        if error_response:
            return error_response
        
        # Le ponemos "support_" al inicio para identificarlo rápido en el Storage
        file_name = f"support_{request.user.id}_{timezone.localtime(timezone.now()).strftime('%d-%m-%Y_%H-%M-%S')}.{extension}"
        
        # 💡 Guardamos en una carpeta dedicada
        folder = "support_media" 
        
        relative_path = storage_manager.save_file(file_obj, folder, file_name)
        
        if relative_path:
            return Response({
                "message": "Archivo de soporte subido",
                "url": relative_path
            }, status=status.HTTP_200_OK)
            
        return Response({"error": "Error al guardar el archivo en el storage"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# =========================================================================
# 2. ENDPOINT PARA NODE.JS (Webhook)
# =========================================================================
class ChatWebhookViewSet(viewsets.ViewSet):
    permission_classes = [IsNodeMicroservice] 

    @action(detail=False, methods=['post'])
    def process_message(self, request):
        order_id = request.data.get('order_id')
        sender_id = request.data.get('sender_id')
        text = request.data.get('text')
        message_type = request.data.get('message_type', 'text')
        media_url = request.data.get('media_url', None)
        recipient_connected = request.data.get('recipient_connected', False)

        try:
            order = Order.objects.select_related('store__company').get(id=order_id)
            if str(sender_id) not in (str(order.client_id), str(order.store.company.owner_id)):
                return Response({"error": "No tienes permiso para enviar mensajes en esta orden"}, status=status.HTTP_403_FORBIDDEN)

            if order.status >= 3:
                return Response({"error": "Orden cerrada"}, status=status.HTTP_403_FORBIDDEN)

            # Si la contraparte está activa en la sala, el mensaje nace como LEÍDO (3), sino como ENVIADO (1)
            initial_status = ChatMessage.DeliveryStatus.READ if recipient_connected else ChatMessage.DeliveryStatus.SENT

            msg = ChatMessage.objects.create(
                order=order,
                sender_id=sender_id,
                text=text,
                message_type=message_type,
                media_url=media_url,
                status=initial_status
            )

            if not recipient_connected:
                try:
                    NotificationManager.notify_new_chat_message(order=order, sender_id=sender_id, text=text or "🖼️ Foto")
                except Exception:
                    pass

            return Response({"success": True, "data": msg.get_json()}, status=status.HTTP_200_OK)
        except Order.DoesNotExist:
            return Response({"error": "Orden no encontrada"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['post'], url_path='mark_room_as_read')
    def mark_room_as_read(self, request):
        """ Cambia el estatus de todos los mensajes recibidos a LEÍDO (3) """
        order_id = request.data.get('order_id')
        reader_id = request.data.get('user_id') # Quién abrió el chat
        
        try:
            order = Order.objects.select_related('store__company').get(id=order_id)
            if str(reader_id) not in (str(order.client_id), str(order.store.company.owner_id)):
                return Response({"error": "No tienes acceso a esta sala"}, status=status.HTTP_403_FORBIDDEN)

            with transaction.atomic():
                ChatMessage.objects.filter(
                    order_id=order_id, 
                    status__lt=3
                ).exclude(sender_id=reader_id).update(status=3)
                
            return Response({"success": True}, status=status.HTTP_200_OK)
        except Order.DoesNotExist:
            return Response({"error": "Orden no encontrada"}, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=False, methods=['post'], url_path='process_support_message')
    def process_support_message(self, request):
        ticket_id = request.data.get('ticket_id')
        sender_id = request.data.get('sender_id')
        recipient_connected = request.data.get('recipient_connected', False)
        
        try:
            ticket = SupportTicket.objects.get(id=ticket_id)
            if ticket.closed:
                return Response({"error": "Ticket cerrado"}, status=status.HTTP_403_FORBIDDEN)

            allowed_senders = {str(ticket.client_id)}
            if ticket.agent_id:
                allowed_senders.add(str(ticket.agent_id))
            if str(sender_id) not in allowed_senders:
                return Response({"error": "No tienes acceso a este ticket"}, status=status.HTTP_403_FORBIDDEN)
            
            # Determinamos si se marca como LEÍDO o ENVIADO dependiendo de si la otra persona está en el chat
            msg_status = SupportMessage.DeliveryStatus.READ if recipient_connected else SupportMessage.DeliveryStatus.SENT
            
            msg = SupportMessage.objects.create(
                ticket=ticket, 
                sender_id=sender_id, 
                text=request.data.get('text'),
                message_type=request.data.get('message_type', 'text'), 
                media_url=request.data.get('media_url'),
                status=msg_status
            )
            
            # 💡 EL FIX: Calculamos exactamente quién es el que debe recibir la notificación global
            is_client = (str(sender_id) == str(ticket.client_id))
            recipient_id = str(ticket.agent_id) if (is_client and ticket.agent_id) else str(ticket.client_id)

            if not recipient_connected:
                try:
                    NotificationManager.notify_new_support_message(
                        ticket=ticket,
                        sender_id=sender_id,
                        text=request.data.get('text') or "🖼️ Archivo"
                    )
                except Exception as e:
                    print(f"⚠️ Error enviando push de soporte: {e}")
            
            return Response({
                "success": True, 
                "data": msg.get_json(), 
                # 💡 ESTO ES LO QUE NODE.JS ESTÁ ESPERANDO DESESPERADAMENTE
                "recipient_id": recipient_id 
            }, status=status.HTTP_200_OK)
            
        except SupportTicket.DoesNotExist:
            return Response({"error": "Ticket no encontrado"}, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=False, methods=['post'], url_path='mark_support_room_as_read')
    def mark_support_room_as_read(self, request):
        ticket_id = request.data.get('ticket_id')
        user_id = request.data.get('user_id')
        try:
            ticket = SupportTicket.objects.get(id=ticket_id)
            allowed_users = {str(ticket.client_id)}
            if ticket.agent_id:
                allowed_users.add(str(ticket.agent_id))
            if str(user_id) not in allowed_users:
                return Response({"error": "No tienes acceso a este ticket"}, status=status.HTTP_403_FORBIDDEN)

            with transaction.atomic():
                SupportMessage.objects.filter(ticket_id=ticket_id, status__lt=3).exclude(sender_id=user_id).update(status=3)
            return Response({"success": True}, status=status.HTTP_200_OK)
        except SupportTicket.DoesNotExist:
            return Response({"error": "Ticket no encontrado"}, status=status.HTTP_404_NOT_FOUND)