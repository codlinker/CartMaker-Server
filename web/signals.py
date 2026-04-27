from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .firebase_admin import NotificationManager
from .models import *
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from django.db import transaction

@receiver(pre_save, sender=MerchantPlanPayment)
def on_payment_created(sender, instance: MerchantPlanPayment, **kwargs):
    if instance.pk:
        try:
            old_instance = sender.objects.select_related(
                'subscription__merchant', 'subscription__plan', 'subscription__merchant__wallet'
            ).only(
                'status', 
                'subscription__merchant__id', 
                'subscription__plan__name', 
                'subscription__plan__price',
                'subscription__valid_until',
                'subscription__merchant__wallet'
            ).get(pk=instance.pk)

            if old_instance.status == PaymentStatus.PENDING and instance.status != old_instance.status:
                with transaction.atomic():
                    merchant = old_instance.subscription.merchant
                    plan_name = old_instance.subscription.plan.name
                    instance.verified_at = timezone.now()

                    # --- CASO RECHAZADO ---
                    if instance.status == PaymentStatus.REJECTED:
                        if instance.rejection_reason == RejectionReason.FAKE_PROOF:
                            instance.rejection_help = RejectionHelpText.FAKE_PROOF
                        elif instance.rejection_reason == RejectionReason.INSUFFICIENT_AMOUNT:
                            instance.rejection_help = RejectionHelpText.INSUFFICIENT_AMOUNT
                        elif instance.rejection_reason == RejectionReason.INVALID_DATE:
                            instance.rejection_help = RejectionHelpText.INVALID_DATE
                        elif instance.rejection_reason == RejectionReason.INVALID_REFERENCE:
                            instance.rejection_help = RejectionHelpText.INVALID_REFERENCE
                        elif instance.rejection_reason == RejectionReason.OTHER:
                            instance.rejection_help = RejectionHelpText.OTHER
                        
                        NotificationManager.notify_payment_check(
                            merchant.id, plan_name, False, instance.pk,
                            rejection_reason=instance.get_rejection_reason_display()
                        )

                    # --- CASO APROBADO ---
                    elif instance.status == PaymentStatus.APPROVED:
                        wallet = merchant.wallet
                        monto_pagado_bs = Decimal(str(instance.amount))
                        tasa_bcv = Decimal(str(instance.bcv_taxes_to_day))
                        monto_pagado_usd = monto_pagado_bs / tasa_bcv
                        plan_price_usd = Decimal(str(old_instance.subscription.plan.price))
                        wallet.regist_transaction(
                            amount=monto_pagado_usd, 
                            sub_type='merchant', 
                            description=f"Recarga mediante transferencia (Ref: {instance.reference_number})", 
                            transaction='add'
                        )
                        if wallet.balance >= plan_price_usd:
                            excedente_usd = wallet.balance - plan_price_usd
                            excedente_bs = round(excedente_usd * tasa_bcv, 2)
                            wallet.regist_transaction(
                                amount=plan_price_usd, 
                                sub_type='merchant', 
                                description=f"Cobro de suscripción: {plan_name}", 
                                transaction='substract'
                            )
                            subscription_valid_until = timezone.now() + relativedelta(months=1)
                            old_instance.subscription.__class__.objects.filter(
                                pk=old_instance.subscription.pk
                            ).update(valid_until=subscription_valid_until)
                            NotificationManager.notify_payment_check(
                                merchant.id, 
                                plan_name, 
                                True, 
                                instance.pk,
                                surplus_amount=float(excedente_bs)
                            )
                        else:
                            instance.status = PaymentStatus.REJECTED
                            instance.rejection_reason = RejectionReason.NOT_ENOUGH_AMOUNT
                            instance.rejection_help = RejectionHelpText.NOT_ENOUGH_AMOUNT
                            NotificationManager.notify_payment_check(
                                merchant.id, plan_name, False, instance.pk,
                                rejection_reason=f"Pago recibido, pero el monto fue insuficiente. {round(float(monto_pagado_usd), 2)}$ fueron acreditados a tu saldo a favor."
                            )

        except sender.DoesNotExist:
            pass # Se acaba de crear el pago

@receiver(post_save, sender=User)
def on_user_created(sender, created, instance: User, **kwargs):
    """
    Signal encargada de manejar el post de la creacion de un usuario.
    """
    if created:
        UserWallet.objects.create(user=instance)