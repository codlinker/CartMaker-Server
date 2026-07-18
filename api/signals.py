from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from .core.firebase_admin import NotificationManager
from .models import *
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from django.db import transaction
from .utils import *
from django.core.cache import cache

@receiver(pre_save, sender=MerchantPlanPayment)
def on_payment_created(sender, instance: MerchantPlanPayment, **kwargs):
    if instance.pk:
        try:
            # Traemos las relaciones necesarias, incluyendo el target_plan
            old_instance = sender.objects.select_related(
                'subscription__merchant', 'subscription__plan', 'subscription__merchant__wallet', 'target_plan'
            ).get(pk=instance.pk)

            if old_instance.status == PaymentStatus.PENDING and instance.status != old_instance.status:
                with transaction.atomic():
                    merchant = old_instance.subscription.merchant
                    current_subscription = old_instance.subscription
                    
                    target_plan = old_instance.target_plan if old_instance.target_plan else current_subscription.plan
                    plan_name = target_plan.name
                    instance.verified_at = timezone.now()

                    # --- CASO RECHAZADO ---
                    if instance.status == PaymentStatus.REJECTED:
                        if instance.rejection_reason == RejectionReason.FAKE_PROOF:
                            instance.rejection_help = RejectionHelpText.FAKE_PROOF
                        elif instance.rejection_reason == RejectionReason.NOT_ENOUGH_AMOUNT:
                            instance.rejection_help = RejectionHelpText.NOT_ENOUGH_AMOUNT
                        elif instance.rejection_reason == RejectionReason.INVALID_DATE:
                            instance.rejection_help = RejectionHelpText.INVALID_DATE
                        elif instance.rejection_reason == RejectionReason.INVALID_REFERENCE:
                            instance.rejection_help = RejectionHelpText.INVALID_REFERENCE
                        elif instance.rejection_reason == RejectionReason.OTHER:
                            instance.rejection_help = RejectionHelpText.OTHER
                        
                        # 💡 FIX: Capturamos el string de rechazo antes del closure
                        rejection_msg = instance.get_rejection_reason_display()
                        
                        # 💡 FIX: Postergamos la notificación
                        def notify_merchant_rejected():
                            NotificationManager.notify_payment_check(
                                merchant.id, plan_name, False, instance.pk,
                                rejection_reason=rejection_msg
                            )
                        transaction.on_commit(notify_merchant_rejected)

                    # --- CASO APROBADO (Con Prorrateo) ---
                    elif instance.status == PaymentStatus.APPROVED:
                        wallet = merchant.wallet
                        is_plan_change = current_subscription.plan.id != target_plan.id
                        
                        # 1. PRORRATEO
                        if is_plan_change and current_subscription.valid_until and current_subscription.valid_until > timezone.now():
                            days_left = (current_subscription.valid_until - timezone.now()).total_seconds() / 86400.0
                            daily_rate = float(current_subscription.plan.price) / 30.0
                            remanent_usd = Decimal(str(round(days_left * daily_rate, 2)))
                            
                            if remanent_usd > 0:
                                wallet.regist_transaction(
                                    amount=remanent_usd, sub_type='merchant', 
                                    description=f"Reintegro por cambio de plan ({current_subscription.plan.name})", transaction='add'
                                )

                        # 2. ACREDITAMOS EL PAGO MÓVIL/TRANSFERENCIA
                        monto_pagado_bs = Decimal(str(instance.amount))
                        tasa_bcv = Decimal(str(instance.bcv_taxes_to_day))
                        monto_pagado_usd = monto_pagado_bs / tasa_bcv
                        
                        wallet.regist_transaction(
                            amount=monto_pagado_usd, sub_type='merchant', 
                            description=f"Recarga mediante transferencia (Ref: {instance.reference_number})", transaction='add'
                        )
                        
                        # 3. VERIFICAMOS SI ALCANZA PARA EL NUEVO PLAN
                        plan_price_usd = Decimal(str(target_plan.price))
                        
                        if wallet.balance >= plan_price_usd:
                            excedente_usd = wallet.balance - plan_price_usd
                            excedente_bs = round(excedente_usd * tasa_bcv, 2)
                            
                            wallet.regist_transaction(
                                amount=plan_price_usd, sub_type='merchant', 
                                description=f"Cobro de suscripción: {plan_name}", transaction='substract'
                            )
                            
                            # 💡 FIX: Lógica de acumulación de tiempo y limpieza de banderas
                            now = timezone.now()
                            if current_subscription.valid_until and current_subscription.valid_until > now:
                                subscription_valid_until = current_subscription.valid_until + relativedelta(months=1)
                            else:
                                subscription_valid_until = now + relativedelta(months=1)

                            current_subscription.__class__.objects.filter(pk=current_subscription.pk).update(
                                plan=target_plan, 
                                valid_until=subscription_valid_until, 
                                adquired_at=now,
                                notified_5_days=False,
                                notified_1_day=False,
                                notified_hours=False
                            )
                        else:
                            # 4. SI NO ALCANZA EL DINERO A PESAR DEL REINTEGRO
                            instance.status = PaymentStatus.REJECTED
                            instance.rejection_reason = RejectionReason.NOT_ENOUGH_AMOUNT
                            instance.rejection_help = RejectionHelpText.NOT_ENOUGH_AMOUNT
                            
                            # 💡 FIX: Postergamos la notificación
                            def notify_insufficient_funds():
                                NotificationManager.notify_payment_check(
                                    merchant.id, plan_name, False, instance.pk,
                                    rejection_reason=f"Pago recibido, pero el monto total fue insuficiente para el nuevo plan. {round(float(monto_pagado_usd), 2)}$ fueron acreditados a tu saldo a favor."
                                )
                            transaction.on_commit(notify_insufficient_funds)

        except sender.DoesNotExist:
            pass

@receiver(pre_save, sender=AtlasPlusPlanPayment, dispatch_uid="on_atlas_payment_status_changed_unique")
def on_atlas_payment_status_changed(sender, instance: AtlasPlusPlanPayment, **kwargs):
    if instance.pk:
        try:
            old_instance = sender.objects.select_related('plan__user__wallet').get(pk=instance.pk)
            
            if old_instance.status == PaymentStatus.PENDING and instance.status != old_instance.status:
                with transaction.atomic():
                    user = old_instance.plan.user
                    atlas_plan = old_instance.plan
                    instance.verified_at = timezone.now()
                    config = SystemConfig.objects.latest('creation')

                    # --- CASO RECHAZADO ---
                    if instance.status == PaymentStatus.REJECTED:
                        instance.rejection_help = int(instance.rejection_reason)
                        rejection_msg = instance.get_rejection_reason_display()
                        
                        def notify_atlas_rejected():
                            NotificationManager.notify_payment_check(
                                user_id=user.id, subscription_name="Atlas Plus AI", 
                                approved=False, payment_id=instance.pk, 
                                rejection_reason=rejection_msg
                            )
                        transaction.on_commit(notify_atlas_rejected)

                    # --- CASO APROBADO ---
                    elif instance.status == PaymentStatus.APPROVED:
                        wallet = user.wallet
                        tasa_bcv = Decimal(str(instance.bcv_taxes_to_day))
                        monto_pagado_usd = Decimal(str(instance.amount)) / tasa_bcv
                        
                        wallet.regist_transaction(monto_pagado_usd, 'atlas', f"Abono por Reporte Atlas (Ref: {instance.reference_number})", 'add')
                        
                        plan_price_usd = Decimal(str(config.atlas_plus_price_usd))
                        
                        if wallet.balance >= plan_price_usd:
                            excedente_usd = wallet.balance - plan_price_usd
                            excedente_bs = round(excedente_usd * tasa_bcv, 2)
                            
                            wallet.regist_transaction(plan_price_usd, 'atlas', "Cobro automático de suscripción Atlas Plus", 'substract')
                            
                            atlas_plan.tier = AtlasSubscriptionTier.PREMIUM
                            atlas_plan.valid_until = timezone.now() + relativedelta(months=1)
                            atlas_plan.save()
                            
                            def finalize_atlas_approval():
                                cache.delete(f"cartmaker:tenant:{user.id}:subscriptions")
                                NotificationManager.notify_payment_check(
                                    user_id=user.id, subscription_name="Atlas Plus AI", 
                                    approved=True, payment_id=instance.pk, surplus_amount=float(excedente_bs)
                                )
                            transaction.on_commit(finalize_atlas_approval)
                        else:
                            instance.status = PaymentStatus.REJECTED
                            instance.rejection_reason = RejectionReason.NOT_ENOUGH_AMOUNT
                            instance.rejection_help = RejectionHelpText.NOT_ENOUGH_AMOUNT
                            
                            def notify_atlas_insufficient():
                                NotificationManager.notify_payment_check(
                                    user_id=user.id, subscription_name="Atlas Plus AI", 
                                    approved=False, payment_id=instance.pk,
                                    rejection_reason=f"Monto insuficiente para Atlas Plus. Los {round(float(monto_pagado_usd), 2)}$ se guardaron en tu monedero."
                                )
                            transaction.on_commit(notify_atlas_insufficient)
        except sender.DoesNotExist:
            pass


# ==========================================
# SECCIÓN REDIS CACHÉ: ENVOLTURA ON_COMMIT 
# ==========================================
# Ahora todas las invalidaciones de caché esperan al commit
# Esto evita que otro hilo reconstruya la caché con datos viejos de la BD.

@receiver(post_save, sender=AtlasPlusPlan, dispatch_uid="invalidate_atlas_plan_cache_unique")
@receiver(post_save, sender=AtlasPlusPlanPayment, dispatch_uid="invalidate_atlas_payment_cache_unique")
def invalidate_atlas_subscriptions_cache(sender, instance, **kwargs):
    user_id = instance.user_id if isinstance(instance, AtlasPlusPlan) else instance.plan.user_id
    if user_id:
        transaction.on_commit(lambda: cache.delete(f"cartmaker:tenant:{user_id}:subscriptions"))

@receiver(post_save, sender=ProductViewLog)
def on_view_log_saved(sender, instance, **kwargs):
    transaction.on_commit(lambda: recalculate_item_popularity(instance.inventory_item_id))

@receiver(post_delete, sender=ProductViewLog)
def on_view_log_deleted(sender, instance, **kwargs):
    transaction.on_commit(lambda: recalculate_item_popularity(instance.inventory_item_id))

@receiver(post_save, sender=InventoryItem)
def update_item_volatile_cache(sender, instance: InventoryItem, **kwargs):
    cache_key = f"cartmaker:volatile:item:{instance.id}"
    state = {
        "stock": instance.stock,
        "paused": instance.paused,
        "custom_price": float(instance.custom_price) if instance.custom_price else None
    }
    # Este sí se puede dejar directo porque escribe datos literales (no leídos de otra tabla conflictiva)
    transaction.on_commit(lambda: cache.set(cache_key, state, timeout=86400))

@receiver(post_delete, sender=InventoryItem)
def delete_item_volatile_cache(sender, instance: InventoryItem, **kwargs):
    def finalize_item_deletion():
        cache.delete(f"cartmaker:volatile:item:{instance.id}")
        try:
            location = instance.store.location
            approx_lat = round(location.coordinates.y, 3)
            approx_lng = round(location.coordinates.x, 3)
            cache.delete_pattern(f"cartmaker:struct:home:{approx_lat}:{approx_lng}:*")
        except Exception:
            pass
    transaction.on_commit(finalize_item_deletion)

@receiver(post_save, sender=Product)
def invalidate_structural_cache_on_product_change(sender, instance: Product, **kwargs):
    def clear_structure_cache():
        stores_ids = instance.inventory_items.values_list('store_id', flat=True).distinct()
        for store_id in stores_ids:
            try:
                store_location = StoreLocation.objects.get(store_id=store_id)
                approx_lat = round(store_location.coordinates.y, 3)
                approx_lng = round(store_location.coordinates.x, 3)
                cache.delete_pattern(f"cartmaker:struct:home:{approx_lat}:{approx_lng}:*")
            except StoreLocation.DoesNotExist:
                continue
    transaction.on_commit(clear_structure_cache)

# GLOBAL INVALIDATION
@receiver(post_save, sender=Mall)
@receiver(post_delete, sender=Mall)
def invalidate_malls_cache(sender, instance, **kwargs):
    transaction.on_commit(lambda: cache.delete("cartmaker:global:malls"))

@receiver(post_save, sender=Announcement)
@receiver(post_delete, sender=Announcement)
@receiver(post_save, sender=CompanyCategory)
def invalidate_home_cache(sender, instance, **kwargs):
    transaction.on_commit(lambda: cache.delete("cartmaker:global:home"))

@receiver(post_save, sender=Category)
@receiver(post_save, sender=SubCategory)
def invalidate_search_cache(sender, instance, **kwargs):
    transaction.on_commit(lambda: cache.delete("cartmaker:global:search"))

# ON CREATED
@receiver(post_save, sender=User)
def on_user_created(sender, created, instance: User, **kwargs):
    if created:
        UserWallet.objects.get_or_create(user=instance)
        AtlasPlusPlan.objects.get_or_create(user=instance)

# TENANT INVALIDATION
@receiver(post_save, sender=User)
def invalidate_user_profile_cache(sender, instance: User, **kwargs):
    transaction.on_commit(lambda: cache.delete(f"cartmaker:tenant:{instance.id}:profile"))

@receiver(post_save, sender=ClientLocation)
@receiver(post_delete, sender=ClientLocation)
@receiver(post_save, sender=ClientContactMethod)
@receiver(post_delete, sender=ClientContactMethod)
def invalidate_user_relations_cache(sender, instance, **kwargs):
    user_id = getattr(instance, 'user_id', None) or getattr(instance, 'client_id', None)
    if user_id:
        transaction.on_commit(lambda: cache.delete(f"cartmaker:tenant:{user_id}:profile"))

@receiver(post_save, sender=Company)
@receiver(post_save, sender=CompanyStore)
@receiver(post_delete, sender=CompanyStore)
def invalidate_company_cache(sender, instance, **kwargs):
    company_id = instance.id if isinstance(instance, Company) else instance.company.id
    owner_id = instance.owner_id if isinstance(instance, Company) else instance.company.owner_id
    
    def finalize_company_cache():
        cache.delete(f"cartmaker:tenant:{owner_id}:company")
        item_ids = list(InventoryItem.objects.filter(store__company_id=company_id).values_list('id', flat=True))
        keys_to_delete = [f"cartmaker:struct:item:{uid}" for uid in item_ids]
        if keys_to_delete:
            cache.delete_many(keys_to_delete)
            
    transaction.on_commit(finalize_company_cache)

@receiver(post_save, sender=UserWallet)
@receiver(post_save, sender=MerchantSubscription)
@receiver(post_save, sender=MerchantPlanPayment)
@receiver(post_save, sender=Notification)
def invalidate_subscriptions_cache(sender, instance, **kwargs):
    user_id = None
    if isinstance(instance, UserWallet):
        user_id = instance.user_id
    elif isinstance(instance, MerchantSubscription):
        user_id = instance.merchant_id
    elif isinstance(instance, MerchantPlanPayment):
        user_id = instance.subscription.merchant_id
    elif isinstance(instance, Notification):
        if instance.category in [NotificationCategory.PAYMENT_REJECTED, NotificationCategory.PAYMENT_APPROVED]:
            user_id = instance.user_id
            
    if user_id:
        def clear_sub_and_company():
            cache.delete(f"cartmaker:tenant:{user_id}:subscriptions")
            # El blindaje final que agregamos en el paso anterior, ahora dentro de on_commit
            if isinstance(instance, (MerchantSubscription, MerchantPlanPayment)):
                cache.delete(f"cartmaker:tenant:{user_id}:company")
                
        transaction.on_commit(clear_sub_and_company)