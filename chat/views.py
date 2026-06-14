from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny

from api.core.firebase_admin import NotificationManager
from .models import ChatMessage, PredefinedMessage
from api.models import Order
from .permissions import IsNodeMicroservice
from django.db import transaction
from django.utils import timezone
from api.cos import storage_manager

# =========================================================================
# 1. ENDPOINT PARA FLUTTER (Historial)
# =========================================================================
class ChatViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def history(self, request):
        """ Devuelve el historial paginado de un chat """
        order_id = request.query_params.get('order_id')
        offset = int(request.query_params.get('offset', 0))
        limit = int(request.query_params.get('limit', 15))
        
        if not order_id:
            return Response({"error": "Falta el ID de la orden."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            order = Order.objects.get(id=order_id)
            is_client = order.client == request.user
            is_merchant = order.store.company.owner == request.user

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
        if not file_obj:
            return Response({"error": "No se envió ningún archivo"}, status=status.HTTP_400_BAD_REQUEST)
        
        extension = file_obj.name.split('.')[-1]
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
            order = Order.objects.get(id=order_id)
            company = order.store.company
            
            # Validamos que el usuario logueado sea el dueño
            if company.owner != request.user:
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
            order = Order.objects.get(id=order_id)
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
                # Tu NotificationManager inteligente creado previamente
                NotificationManager.notify_new_chat_message(order=order, sender_id=sender_id, text=text or "🖼️ Foto")

            return Response({"success": True, "data": msg.get_json()}, status=status.HTTP_200_OK)
        except Order.DoesNotExist:
            return Response({"error": "Orden no encontrada"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['post'], url_path='mark_room_as_read')
    def mark_room_as_read(self, request):
        """ Cambia el estatus de todos los mensajes recibidos a LEÍDO (3) """
        order_id = request.data.get('order_id')
        reader_id = request.data.get('user_id') # Quién abrió el chat
        
        with transaction.atomic():
            ChatMessage.objects.filter(
                order_id=order_id, 
                status__lt=3
            ).exclude(sender_id=reader_id).update(status=3)
            
        return Response({"success": True}, status=status.HTTP_200_OK)