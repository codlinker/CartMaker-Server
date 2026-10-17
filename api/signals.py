from django.db.models.signals import post_save, pre_save, post_delete, m2m_changed
from django.dispatch import receiver
from .core.firebase_admin import NotificationManager
from .models import *
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from django.db import transaction
from .utils import *
from django.core.cache import cache

@receiver(pre_save, sender=MerchantPlanPayment, dispatch_uid="capture_merchant_payment_prev_status")
def _capture_merchant_payment_prev_status(sender, instance: MerchantPlanPayment, **kwargs):
    if instance.pk:
        old_row = sender.objects.filter(pk=instance.pk).values('status', 'verified_at').first()
        if old_row:
            instance._prev_status = old_row['status']
            instance._prev_verified_at = old_row['verified_at']
    else:
        instance._prev_status = None
        instance._prev_verified_at = None


@receiver(post_save, sender=MerchantPlanPayment, dispatch_uid="on_merchant_payment_status_changed_post_save")
def on_payment_created(sender, instance: MerchantPlanPayment, created: bool, **kwargs):
    if created:
        return
    prev_status = getattr(instance, '_prev_status', None)
    if prev_status != PaymentStatus.PENDING or instance.status == PaymentStatus.PENDING:
        return

    try:
        with transaction.atomic():
            # Bloqueamos la fila del pago ya persistida y verificamos idempotencia con verified_at
            locked_payment = sender.objects.select_for_update(of=('self',)).select_related(
                'subscription__merchant', 'subscription__plan', 'target_plan'
            ).get(pk=instance.pk)

            if locked_payment.verified_at is not None:
                return

            merchant = locked_payment.subscription.merchant
            current_subscription = locked_payment.subscription
            target_plan = locked_payment.target_plan if locked_payment.target_plan else current_subscription.plan
            plan_name = target_plan.name
            now = timezone.now()

            # --- CASO RECHAZADO ---
            if instance.status == PaymentStatus.REJECTED:
                rejection_help = locked_payment.rejection_help
                if instance.rejection_reason == RejectionReason.FAKE_PROOF:
                    rejection_help = RejectionHelpText.FAKE_PROOF
                elif instance.rejection_reason == RejectionReason.NOT_ENOUGH_AMOUNT:
                    rejection_help = RejectionHelpText.NOT_ENOUGH_AMOUNT
                elif instance.rejection_reason == RejectionReason.INVALID_DATE:
                    rejection_help = RejectionHelpText.INVALID_DATE
                elif instance.rejection_reason == RejectionReason.INVALID_REFERENCE:
                    rejection_help = RejectionHelpText.INVALID_REFERENCE
                elif instance.rejection_reason == RejectionReason.OTHER:
                    rejection_help = RejectionHelpText.OTHER

                sender.objects.filter(pk=instance.pk).update(
                    verified_at=now,
                    rejection_help=rejection_help
                )
                instance.verified_at = now
                instance.rejection_help = rejection_help

                rejection_msg = instance.get_rejection_reason_display()

                def notify_merchant_rejected():
                    try:
                        NotificationManager.notify_payment_check(
                            merchant.id, plan_name, False, instance.pk,
                            rejection_reason=rejection_msg
                        )
                    except Exception as e:
                        print(f"[Signals] Error enviando push notify_merchant_rejected: {e}")
                transaction.on_commit(notify_merchant_rejected)

            # --- CASO APROBADO (Con Prorrateo) ---
            elif instance.status == PaymentStatus.APPROVED:
                wallet, _ = UserWallet.objects.select_for_update().get_or_create(user=merchant)
                is_plan_change = current_subscription.plan.id != target_plan.id

                # 1. PRORRATEO
                if is_plan_change and current_subscription.valid_until and current_subscription.valid_until > now:
                    days_left = (current_subscription.valid_until - now).total_seconds() / 86400.0
                    daily_rate = float(current_subscription.plan.price) / 30.0
                    remanent_usd = Decimal(str(round(days_left * daily_rate, 2)))

                    if remanent_usd > 0:
                        wallet.regist_transaction(
                            amount=remanent_usd, sub_type='merchant',
                            description=f"Reintegro por cambio de plan ({current_subscription.plan.name})",
                            transaction='add'
                        )

                # 2. ACREDITAMOS EL PAGO MÓVIL/TRANSFERENCIA
                monto_pagado_bs = Decimal(str(instance.amount))
                tasa_bcv = Decimal(str(instance.bcv_taxes_to_day))
                monto_pagado_usd = monto_pagado_bs / tasa_bcv

                wallet.regist_transaction(
                    amount=monto_pagado_usd, sub_type='merchant',
                    description=f"Recarga mediante transferencia (Ref: {instance.reference_number})",
                    transaction='add'
                )

                # 3. VERIFICAMOS SI ALCANZA PARA EL NUEVO PLAN
                plan_price_usd = Decimal(str(target_plan.price))

                if wallet.balance >= plan_price_usd:
                    excedente_usd = wallet.balance - plan_price_usd
                    excedente_bs = round(excedente_usd * tasa_bcv, 2)

                    wallet.regist_transaction(
                        amount=plan_price_usd, sub_type='merchant',
                        description=f"Cobro de suscripción: {plan_name}",
                        transaction='substract'
                    )

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
                    sender.objects.filter(pk=instance.pk).update(verified_at=now)
                    instance.verified_at = now

                    def notify_merchant_approved():
                        try:
                            NotificationManager.notify_payment_check(
                                user_id=merchant.id,
                                subscription_name=plan_name,
                                approved=True,
                                payment_id=instance.pk,
                                surplus_amount=float(excedente_bs)
                            )
                        except Exception as e:
                            print(f"[Signals] Error enviando push notify_merchant_approved: {e}")
                    transaction.on_commit(notify_merchant_approved)
                else:
                    # 4. SI NO ALCANZA EL DINERO A PESAR DEL REINTEGRO
                    sender.objects.filter(pk=instance.pk).update(
                        status=PaymentStatus.REJECTED,
                        rejection_reason=RejectionReason.NOT_ENOUGH_AMOUNT,
                        rejection_help=RejectionHelpText.NOT_ENOUGH_AMOUNT,
                        verified_at=now
                    )
                    instance.status = PaymentStatus.REJECTED
                    instance.rejection_reason = RejectionReason.NOT_ENOUGH_AMOUNT
                    instance.rejection_help = RejectionHelpText.NOT_ENOUGH_AMOUNT
                    instance.verified_at = now

                    def notify_insufficient_funds():
                        try:
                            NotificationManager.notify_payment_check(
                                merchant.id, plan_name, False, instance.pk,
                                rejection_reason=f"Pago recibido, pero el monto total fue insuficiente para el nuevo plan. {round(float(monto_pagado_usd), 2)}$ fueron acreditados a tu saldo a favor."
                            )
                        except Exception as e:
                            print(f"[Signals] Error enviando push notify_insufficient_funds: {e}")
                    transaction.on_commit(notify_insufficient_funds)
    except sender.DoesNotExist:
        pass


@receiver(pre_save, sender=AtlasPlusPlanPayment, dispatch_uid="capture_atlas_payment_prev_status")
def _capture_atlas_payment_prev_status(sender, instance: AtlasPlusPlanPayment, **kwargs):
    if instance.pk:
        old_row = sender.objects.filter(pk=instance.pk).values('status', 'verified_at').first()
        if old_row:
            instance._prev_status = old_row['status']
            instance._prev_verified_at = old_row['verified_at']
    else:
        instance._prev_status = None
        instance._prev_verified_at = None


@receiver(post_save, sender=AtlasPlusPlanPayment, dispatch_uid="on_atlas_payment_status_changed_unique")
def on_atlas_payment_status_changed(sender, instance: AtlasPlusPlanPayment, created: bool, **kwargs):
    if created:
        return
    prev_status = getattr(instance, '_prev_status', None)
    if prev_status != PaymentStatus.PENDING or instance.status == PaymentStatus.PENDING:
        return

    try:
        with transaction.atomic():
            # Bloqueamos únicamente la fila del pago (of=('self',)) para evitar FOR UPDATE sobre LEFT OUTER JOINs
            locked_payment = sender.objects.select_for_update(of=('self',)).select_related('plan__user').get(pk=instance.pk)
            if locked_payment.verified_at is not None:
                return

            user = locked_payment.plan.user
            atlas_plan = AtlasPlusPlan.objects.select_for_update().get(pk=locked_payment.plan_id)
            now = timezone.now()
            config = SystemConfig.objects.order_by('-creation').first() or SystemConfig.objects.create()

            # --- CASO RECHAZADO ---
            if instance.status == PaymentStatus.REJECTED:
                rejection_help = int(instance.rejection_reason) if instance.rejection_reason is not None else None
                sender.objects.filter(pk=instance.pk).update(
                    verified_at=now,
                    rejection_help=rejection_help
                )
                instance.verified_at = now
                instance.rejection_help = rejection_help
                rejection_msg = instance.get_rejection_reason_display()

                def notify_atlas_rejected():
                    try:
                        NotificationManager.notify_payment_check(
                            user_id=user.id, subscription_name="Atlas Plus AI",
                            approved=False, payment_id=instance.pk,
                            rejection_reason=rejection_msg
                        )
                    except Exception as e:
                        print(f"[Signals] Error enviando push notify_atlas_rejected: {e}")
                transaction.on_commit(notify_atlas_rejected)

            # --- CASO APROBADO ---
            elif instance.status == PaymentStatus.APPROVED:
                wallet, _ = UserWallet.objects.select_for_update().get_or_create(user=user)
                tasa_bcv = Decimal(str(instance.bcv_taxes_to_day))
                monto_pagado_usd = Decimal(str(instance.amount)) / tasa_bcv

                wallet.regist_transaction(
                    monto_pagado_usd, 'atlas',
                    f"Abono por Reporte Atlas (Ref: {instance.reference_number})", 'add'
                )

                plan_price_usd = Decimal(str(config.atlas_plus_price_usd))

                if wallet.balance >= plan_price_usd:
                    excedente_usd = wallet.balance - plan_price_usd
                    excedente_bs = round(excedente_usd * tasa_bcv, 2)

                    wallet.regist_transaction(
                        plan_price_usd, 'atlas',
                        "Cobro automático de suscripción Atlas Plus", 'substract'
                    )

                    period_start = (
                        atlas_plan.valid_until
                        if (atlas_plan.tier == AtlasSubscriptionTier.PREMIUM and atlas_plan.valid_until and atlas_plan.valid_until > now)
                        else now
                    )
                    atlas_plan.tier = AtlasSubscriptionTier.PREMIUM
                    atlas_plan.valid_until = period_start + relativedelta(months=1)
                    atlas_plan.save()

                    sender.objects.filter(pk=instance.pk).update(verified_at=now)
                    instance.verified_at = now
                    locked_payment.verified_at = now

                    invoice = AtlasPlusInvoice.issue_for_payment(
                        payment=locked_payment,
                        config=config,
                        payment_method='Pago Móvil / Transferencia Bancaria',
                        surplus_usd=excedente_usd,
                        period_start=period_start,
                        period_end=atlas_plan.valid_until,
                    )
                    inv_id = str(invoice.id)
                    inv_num = invoice.invoice_number
                    inv_url = invoice.invoice_url

                    def finalize_atlas_approval():
                        try:
                            cache.delete(f"cartmaker:tenant:{user.id}:subscriptions")
                        except Exception:
                            pass
                        try:
                            NotificationManager.notify_payment_check(
                                user_id=user.id,
                                subscription_name="Atlas Plus AI",
                                approved=True,
                                payment_id=instance.pk,
                                surplus_amount=float(excedente_bs),
                                invoice_id=inv_id,
                                invoice_number=inv_num,
                                invoice_url=inv_url,
                            )
                        except Exception as e:
                            print(f"[Signals] Error enviando push finalize_atlas_approval: {e}")
                        try:
                            from api.utils import send_atlas_invoice_email
                            send_atlas_invoice_email(inv_id)
                        except Exception as e:
                            print(f"[Signals] Error enviando email de factura Atlas Plus: {e}")
                    transaction.on_commit(finalize_atlas_approval)
                else:
                    sender.objects.filter(pk=instance.pk).update(
                        status=PaymentStatus.REJECTED,
                        rejection_reason=RejectionReason.NOT_ENOUGH_AMOUNT,
                        rejection_help=RejectionHelpText.NOT_ENOUGH_AMOUNT,
                        verified_at=now
                    )
                    instance.status = PaymentStatus.REJECTED
                    instance.rejection_reason = RejectionReason.NOT_ENOUGH_AMOUNT
                    instance.rejection_help = RejectionHelpText.NOT_ENOUGH_AMOUNT
                    instance.verified_at = now

                    def notify_atlas_insufficient():
                        try:
                            NotificationManager.notify_payment_check(
                                user_id=user.id, subscription_name="Atlas Plus AI",
                                approved=False, payment_id=instance.pk,
                                rejection_reason=f"Monto insuficiente para Atlas Plus. Los {round(float(monto_pagado_usd), 2)}$ se guardaron en tu monedero."
                            )
                        except Exception as e:
                            print(f"[Signals] Error enviando push notify_atlas_insufficient: {e}")
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
    item_id = instance.inventory_item_id
    client_id = instance.client_id
    high_signal = bool(getattr(instance, 'added_to_cart', False) or getattr(instance, 'bought', False))

    def _run():
        if high_signal and client_id:
            try:
                cache.delete(f"cartmaker:affinity_profile:v1:{client_id}")
            except Exception:
                pass
        debounce_key = f"cartmaker:pop_debounce:{item_id}"
        if not high_signal:
            try:
                if cache.get(debounce_key) is not None:
                    return
                cache.set(debounce_key, 1, timeout=30)
            except Exception:
                pass
        recalculate_item_popularity(item_id)

    transaction.on_commit(_run)

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
            if hasattr(cache, 'delete_pattern'):
                cache.delete_pattern(f"cartmaker:struct:home:{approx_lat}:{approx_lng}:*")
        except Exception:
            pass
    transaction.on_commit(finalize_item_deletion)

@receiver(post_save, sender=Product)
def invalidate_structural_cache_on_product_change(sender, instance: Product, **kwargs):
    def clear_structure_cache():
        rows = list(
            instance.inventory_items.select_related('store__location').values_list(
                'id', 'store__location__coordinates'
            )
        )
        if not rows:
            return
        cache.delete_many([f"cartmaker:struct:item:{uid}" for uid, _ in rows])
        seen_coords = set()
        for _, coords in rows:
            if not coords:
                continue
            key_pair = (round(coords.y, 3), round(coords.x, 3))
            if key_pair in seen_coords:
                continue
            seen_coords.add(key_pair)
            try:
                if hasattr(cache, 'delete_pattern'):
                    cache.delete_pattern(f"cartmaker:struct:home:{key_pair[0]}:{key_pair[1]}:*")
            except Exception:
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
@receiver(post_delete, sender=Category)
@receiver(post_save, sender=SubCategory)
@receiver(post_delete, sender=SubCategory)
def invalidate_search_cache(sender, instance, **kwargs):
    def _clear_categories_caches():
        cache.delete("cartmaker:global:search")
        cache.delete("cartmaker:global:categories")
    transaction.on_commit(_clear_categories_caches)

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

@receiver(m2m_changed, sender=User.preferred_categories.through)
def invalidate_user_preferences_cache(sender, instance, action, **kwargs):
    if action in ("post_add", "post_remove", "post_clear") and getattr(instance, "id", None):
        user_id = instance.id
        transaction.on_commit(lambda: cache.delete(f"cartmaker:tenant:{user_id}:profile"))

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


@receiver(post_save, sender=AtlasPlusInvoice)
def invalidate_subscriptions_on_invoice_created(sender, instance: AtlasPlusInvoice, **kwargs):
    if instance.user_id:
        transaction.on_commit(lambda: cache.delete(f"cartmaker:tenant:{instance.user_id}:subscriptions"))


@receiver(post_save, sender=SystemConfig)
@receiver(post_delete, sender=SystemConfig)
@receiver(post_save, sender=CartMakerBankAccount)
@receiver(post_delete, sender=CartMakerBankAccount)
def invalidate_system_config_cache(sender, instance, **kwargs):
    transaction.on_commit(lambda: cache.delete("cartmaker:global:system_config"))