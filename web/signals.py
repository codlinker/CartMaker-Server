from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .firebase_admin import NotificationManager
from .models import *
from django.utils import timezone
from dateutil import relativedelta
from django.db import transaction

@receiver(pre_save, sender=MerchantPlanPayment)
def on_payment_created(sender, instance: MerchantPlanPayment, **kwargs):
    """
    Signal encargada de manejar el estado de los pagos.
    
    Si el pago esta pendiente por revision, se verifica si se cambio su estado,
    para determinar si fue rechazado o aprobado, lo cual crea la notificacion
    correspondiente al usuario a traves del modelo Notification.
    """
    if instance.pk:
        try:
            old_instance = sender.objects.select_related(
                'subscription__merchant', 'subscription__plan').only(
                    'status', 
                    'subscription__merchant__id', 
                    'subscription__plan__name', 
                    'subscription__valid_until'
                ).get(pk=instance.pk)
            if old_instance.status == PaymentStatus.PENDING:
                if instance.status != old_instance.status:
                    with transaction.atomic():
                        merchant_id = old_instance.subscription.merchant.id
                        plan_name = old_instance.subscription.plan.name
                        instance.verified_at = timezone.now()
                        if instance.status == PaymentStatus.REJECTED:
                            NotificationManager.notify_payment_check(
                                merchant_id, plan_name, False, instance.pk,
                                rejection_reason=instance.get_rejection_reason_display()
                                )
                        elif instance.status == PaymentStatus.APPROVED:
                            subscription_valid_until = timezone.now() + relativedelta(months=1)
                            instance.verified_at = timezone.now()
                            old_instance.subscription.__class__.objects.filter(
                                pk=old_instance.subscription.pk
                            ).update(valid_until=subscription_valid_until)
                            NotificationManager.notify_payment_check(
                                merchant_id, plan_name, True, instance.pk,
                                )
        except sender.DoesNotExist:
            pass # Se acaba de crear el pago