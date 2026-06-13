from django.db import models
from django.utils import timezone
from api.models import Order, User, Company
from api.cos import storage_manager # Usamos tu gestor de Object Storage

class ChatMessage(models.Model):
    class MessageType(models.TextChoices):
        TEXT = 'text', 'Texto'
        IMAGE = 'image', 'Imagen'
        AUDIO = 'audio', 'Nota de Voz'

    class DeliveryStatus(models.IntegerChoices):
        PENDING = 0, 'Enviando'
        SENT = 1, 'Enviado al Servidor'
        DELIVERED = 2, 'Entregado al Dispositivo'
        READ = 3, 'Leído'

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='chat_messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    text = models.TextField(blank=True, null=True) # Opcional si es multimedia
    
    # Nuevos campos estructurales para la modernización
    message_type = models.CharField(max_length=10, choices=MessageType.choices, default=MessageType.TEXT)
    media_url = models.TextField(null=True, blank=True)
    status = models.IntegerField(choices=DeliveryStatus.choices, default=DeliveryStatus.SENT)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def get_json(self) -> dict:
        time_str = timezone.localtime(self.created_at).strftime("%d/%m/%Y %I:%M %p").lower()
        
        # Si contiene multimedia, resolvemos la URL absoluta usando tu storage_manager
        absolute_media_url = ""
        if self.media_url:
            absolute_media_url = storage_manager.get_url(self.media_url)

        return {
            'id': self.id,
            'order_id': self.order.id,
            'sender_id': str(self.sender.id),
            'sender_name': f"{self.sender.first_name} {self.sender.last_name}",
            'text': self.text,
            'message_type': self.message_type,
            'media_url': absolute_media_url,
            'status': self.status,
            'created_at': time_str,
        }

class PredefinedMessage(models.Model):
    company = models.ForeignKey('api.Company', on_delete=models.CASCADE, related_name='predefined_messages')
    title = models.CharField(max_length=100, default="Mensaje Rápido") # 💡 Nuevo campo
    text = models.CharField(max_length=600)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def get_json(self):
        return {
            'id': self.id,
            'title': self.title,
            'text': self.text
        }