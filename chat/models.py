from django.db import models
from django.utils import timezone
from api.models import Order, User, Company
from api.cos import storage_manager # Usamos tu gestor de Object Storage

class ChatMessage(models.Model):
    class MessageType(models.TextChoices):
        TEXT = 'text', 'Texto'
        IMAGE = 'image', 'Imagen'
        AUDIO = 'audio', 'Nota de Voz'
        PAYMENT_METHODS = 'payment_methods', 'Datos de Pago'
        PAYMENT_INFO = 'payment_info', 'Datos de Pago'

    class DeliveryStatus(models.IntegerChoices):
        PENDING = 0, 'Enviando'
        SENT = 1, 'Enviado al Servidor'
        DELIVERED = 2, 'Entregado al Dispositivo'
        READ = 3, 'Leído'

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='chat_messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    text = models.TextField(blank=True, null=True) # Opcional si es multimedia
    
    # Nuevos campos estructurales para la modernización
    message_type = models.CharField(max_length=24, choices=MessageType.choices, default=MessageType.TEXT)
    media_url = models.TextField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True, null=True)
    status = models.IntegerField(choices=DeliveryStatus.choices, default=DeliveryStatus.SENT)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['order', '-created_at'], name='chat_msg_order_created_idx'),
            models.Index(fields=['order', 'status'], name='chat_msg_order_status_idx'),
        ]

    def get_json(self, temp_id: str = None) -> dict:
        import re
        from api.models import MerchantPaymentMethod
        time_str = timezone.localtime(self.created_at).strftime("%d/%m/%Y %I:%M %p").lower()
        
        # Si contiene multimedia, resolvemos la URL absoluta usando tu storage_manager
        absolute_media_url = ""
        if self.media_url:
            absolute_media_url = storage_manager.get_url(self.media_url) or ""

        clean_text = self.text
        if clean_text and isinstance(clean_text, str):
            clean_text = re.sub(
                r'\b([VEJGP])[-\s]+(?:[VEJGP][-\s]+)+(\d)',
                r'\1-\2',
                clean_text,
                flags=re.IGNORECASE,
            )

        meta = dict(self.metadata) if isinstance(self.metadata, dict) else {}
        raw_pm_list = meta.get('payment_methods', []) if isinstance(meta.get('payment_methods'), list) else []
        payment_methods_list = []
        for pm in raw_pm_list:
            if not isinstance(pm, dict):
                continue
            pm_copy = dict(pm)
            if pm_copy.get('dni') or pm_copy.get('document_number') or pm_copy.get('identification'):
                raw_d = pm_copy.get('dni') or pm_copy.get('document_number') or pm_copy.get('identification') or ''
                c_type, c_digits, c_fmt = MerchantPaymentMethod.clean_dni_parts(pm_copy.get('document_type', 'V'), raw_d)
                pm_copy['document_type'] = c_type
                pm_copy['dni'] = c_digits
                pm_copy['document_number'] = c_digits
                pm_copy['identification'] = c_digits
                pm_copy['dni_formatted'] = c_fmt
                if isinstance(pm_copy.get('details'), dict):
                    det = dict(pm_copy['details'])
                    det['document_type'] = c_type
                    det['dni'] = c_digits
                    det['document_number'] = c_digits
                    det['identification'] = c_digits
                    det['dni_formatted'] = c_fmt
                    pm_copy['details'] = det
                if isinstance(pm_copy.get('copyable_fields'), list):
                    cf_list = []
                    for cf in pm_copy['copyable_fields']:
                        if isinstance(cf, dict) and cf.get('key') == 'dni':
                            cf = {**cf, 'value': c_fmt, 'copy_value': c_fmt}
                        cf_list.append(cf)
                    pm_copy['copyable_fields'] = cf_list
                if isinstance(pm_copy.get('formatted_text'), str):
                    pm_copy['formatted_text'] = re.sub(
                        r'\b([VEJGP])[-\s]+(?:[VEJGP][-\s]+)+(\d)',
                        r'\1-\2',
                        pm_copy['formatted_text'],
                        flags=re.IGNORECASE,
                    )
            payment_methods_list.append(pm_copy)
        if payment_methods_list:
            meta['payment_methods'] = payment_methods_list

        payload = {
            'id': self.id,
            'order_id': self.order_id,
            'sender_id': str(self.sender_id),
            'sender_name': f"{self.sender.first_name} {self.sender.last_name}".strip(),
            'text': clean_text,
            'message_type': self.message_type,
            'media_url': absolute_media_url,
            'metadata': meta,
            'payment_methods': payment_methods_list,
            'status': self.status if self.status is not None else 1,
            'is_read': bool(self.status and self.status >= self.DeliveryStatus.READ),
            'is_support': False,
            'created_at': time_str,
        }
        if temp_id:
            payload['temp_id'] = str(temp_id)
        return payload

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