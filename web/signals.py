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
                    
                    # 💡 Identificamos el plan al que quiere suscribirse (o renovar)
                    target_plan = old_instance.target_plan if old_instance.target_plan else current_subscription.plan
                    plan_name = target_plan.name
                    instance.verified_at = timezone.now()

                    # --- CASO RECHAZADO (Mantenemos tu lógica intacta) ---
                    if instance.status == PaymentStatus.REJECTED:
                        # ... (Todo tu bloque de RejectionReason se mantiene idéntico aquí) ...
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
                        
                        NotificationManager.notify_payment_check(
                            merchant.id, plan_name, False, instance.pk,
                            rejection_reason=instance.get_rejection_reason_display()
                        )

                    # --- CASO APROBADO (Con Prorrateo) ---
                    elif instance.status == PaymentStatus.APPROVED:
                        wallet = merchant.wallet
                        
                        is_plan_change = current_subscription.plan.id != target_plan.id
                        
                        # 1. 💡 PRORRATEO: Acreditamos el tiempo no consumido si cambia de plan
                        if is_plan_change and current_subscription.valid_until and current_subscription.valid_until > timezone.now():
                            days_left = (current_subscription.valid_until - timezone.now()).total_seconds() / 86400.0
                            daily_rate = float(current_subscription.plan.price) / 30.0
                            remanent_usd = Decimal(str(round(days_left * daily_rate, 2)))
                            
                            if remanent_usd > 0:
                                wallet.regist_transaction(
                                    amount=remanent_usd, 
                                    sub_type='merchant', 
                                    description=f"Reintegro por cambio de plan ({current_subscription.plan.name})", 
                                    transaction='add'
                                )

                        # 2. ACREDITAMOS EL PAGO MÓVIL/TRANSFERENCIA
                        monto_pagado_bs = Decimal(str(instance.amount))
                        tasa_bcv = Decimal(str(instance.bcv_taxes_to_day))
                        monto_pagado_usd = monto_pagado_bs / tasa_bcv
                        
                        wallet.regist_transaction(
                            amount=monto_pagado_usd, 
                            sub_type='merchant', 
                            description=f"Recarga mediante transferencia (Ref: {instance.reference_number})", 
                            transaction='add'
                        )
                        
                        # 3. VERIFICAMOS SI ALCANZA PARA EL NUEVO PLAN
                        plan_price_usd = Decimal(str(target_plan.price))
                        
                        if wallet.balance >= plan_price_usd:
                            # A) Se cobra el plan
                            excedente_usd = wallet.balance - plan_price_usd
                            excedente_bs = round(excedente_usd * tasa_bcv, 2)
                            
                            wallet.regist_transaction(
                                amount=plan_price_usd, 
                                sub_type='merchant', 
                                description=f"Cobro de suscripción: {plan_name}", 
                                transaction='substract'
                            )
                            
                            # B) Se actualiza la suscripción al NUEVO plan
                            subscription_valid_until = timezone.now() + relativedelta(months=1)
                            current_subscription.__class__.objects.filter(pk=current_subscription.pk).update(
                                plan=target_plan,  # 💡 AQUÍ ocurre el cambio real de plan
                                valid_until=subscription_valid_until, 
                                adquired_at=timezone.now()
                            )
                            
                            NotificationManager.notify_payment_check(
                                merchant.id, 
                                plan_name, 
                                True, 
                                instance.pk,
                                surplus_amount=float(excedente_bs)
                            )
                        else:
                            # 4. SI NO ALCANZA EL DINERO A PESAR DEL REINTEGRO
                            instance.status = PaymentStatus.REJECTED
                            instance.rejection_reason = RejectionReason.NOT_ENOUGH_AMOUNT
                            instance.rejection_help = RejectionHelpText.NOT_ENOUGH_AMOUNT
                            NotificationManager.notify_payment_check(
                                merchant.id, plan_name, False, instance.pk,
                                rejection_reason=f"Pago recibido, pero el monto total fue insuficiente para el nuevo plan. {round(float(monto_pagado_usd), 2)}$ fueron acreditados a tu saldo a favor."
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

@receiver(post_save, sender=ProductViewLog)
def on_view_log_saved(sender, instance, **kwargs):
    """
    Se dispara cuando se registra una nueva vista o se actualiza 
    (ej: el usuario lo agregó al carrito minutos después de verlo).
    """
    recalculate_item_popularity(instance.inventory_item_id)

@receiver(post_delete, sender=ProductViewLog)
def on_view_log_deleted(sender, instance, **kwargs):
    """
    Se dispara si por alguna razón se elimina un log (limpieza de BD, etc).
    """
    recalculate_item_popularity(instance.inventory_item_id)

@receiver(post_save, sender=InventoryItem)
def update_item_volatile_cache(sender, instance: InventoryItem, **kwargs):
    """
    Cada vez que el stock, precio personalizado o estado de pausa cambie en la BD,
    actualizamos de inmediato el Nivel Volátil en Redis de forma síncrona.
    Escribir un string/dict simple en Redis toma menos de 1ms, no bloquea el hilo.
    """
    cache_key = f"cartmaker:volatile:item:{instance.id}"
    state = {
        "stock": instance.stock,
        "paused": instance.paused,
        "custom_price": float(instance.custom_price) if instance.custom_price else None
    }
    # Lo guardamos en RAM por 24 horas. Las señales posteriores se encargan de refrescarlo.
    cache.set(cache_key, state, timeout=86400)


@receiver(post_delete, sender=InventoryItem)
def delete_item_volatile_cache(sender, instance: InventoryItem, **kwargs):
    """
    Si un lote de inventario se elimina físicamente, limpiamos su estado volátil
    e invalidamos el caché estructural de su zona geográfica para que desaparezca del esqueleto.
    """
    cache_key = f"cartmaker:volatile:item:{instance.id}"
    cache.delete(cache_key)
    
    # Invalidación estructural zonal masiva
    try:
        location = instance.store.location
        approx_lat = round(location.coordinates.y, 3)
        approx_lng = round(location.coordinates.x, 3)
        
        # El método delete_pattern de django-redis busca y borra por comodines en una sola operación
        cache.delete_pattern(f"cartmaker:struct:home:{approx_lat}:{approx_lng}:*")
    except Exception:
        # Blindaje por si la sucursal no tenía una ubicación geográfica configurada todavía
        pass


@receiver(post_save, sender=Product)
def invalidate_structural_cache_on_product_change(sender, instance: Product, **kwargs):
    """
    Si los datos estructurales del catálogo maestro cambian (Nombre del producto, descripción, imágenes),
    debemos invalidar el esqueleto estructural indexado en Redis de las zonas donde se venda.
    """
    # Buscamos todas las sucursales que tienen este producto registrado en sus inventarios
    stores_ids = instance.inventory_items.values_list('store_id', flat=True).distinct()
    
    for store_id in stores_ids:
        try:
            store_location = StoreLocation.objects.get(store_id=store_id)
            approx_lat = round(store_location.coordinates.y, 3)
            approx_lng = round(store_location.coordinates.x, 3)
            
            # Borramos el feed estructural de esa coordenada truncada específica
            cache.delete_pattern(f"cartmaker:struct:home:{approx_lat}:{approx_lng}:*")
        except StoreLocation.DoesNotExist:
            continue

# ==========================================
# INVALIDACIÓN GLOBAL (Afecta a todos)
# ==========================================
@receiver(post_save, sender=Mall)
@receiver(post_delete, sender=Mall)
def invalidate_malls_cache(sender, instance, **kwargs):
    cache.delete("cartmaker:global:malls")

@receiver(post_save, sender=Announcement)
@receiver(post_delete, sender=Announcement)
@receiver(post_save, sender=CompanyCategory)
def invalidate_home_cache(sender, instance, **kwargs):
    cache.delete("cartmaker:global:home")

@receiver(post_save, sender=Category)
@receiver(post_save, sender=SubCategory)
def invalidate_search_cache(sender, instance, **kwargs):
    cache.delete("cartmaker:global:search")

# ==========================================
# INVALIDACIÓN POR TENANT (Afecta solo al dueño)
# ==========================================
@receiver(post_save, sender=User)
def invalidate_user_profile_cache(sender, instance: User, **kwargs):
    """Se dispara si cambia el nombre, foto, o correo del usuario"""
    cache.delete(f"cartmaker:tenant:{instance.id}:profile")

@receiver(post_save, sender=ClientLocation)
@receiver(post_delete, sender=ClientLocation)
@receiver(post_save, sender=ClientContactMethod)
@receiver(post_delete, sender=ClientContactMethod)
def invalidate_user_relations_cache(sender, instance, **kwargs):
    # En estos modelos, la relación hacia el usuario es 'user' o 'client'
    user_id = getattr(instance, 'user_id', None) or getattr(instance, 'client_id', None)
    if user_id:
        cache.delete(f"cartmaker:tenant:{user_id}:profile")

@receiver(post_save, sender=Company)
@receiver(post_save, sender=CompanyStore)
@receiver(post_delete, sender=CompanyStore)
def invalidate_company_cache(sender, instance, **kwargs):
    """Si el comerciante actualiza su empresa o agrega una sucursal"""
    owner_id = instance.owner_id if isinstance(instance, Company) else instance.company.owner_id
    cache.delete(f"cartmaker:tenant:{owner_id}:company")

# ==========================================
# INVALIDACIÓN DEL CACHÉ DE SUSCRIPCIONES Y BILLETERA
# ==========================================
@receiver(post_save, sender=UserWallet)
@receiver(post_save, sender=MerchantSubscription)
@receiver(post_save, sender=MerchantPlanPayment)
@receiver(post_save, sender=Notification)
def invalidate_subscriptions_cache(sender, instance, **kwargs):
    """
    Este es el caché más crítico. Si le aprueban un pago, le suman saldo a favor 
    o le llega una notificación de rechazo de pago, debe refrescarse inmediato.
    """
    user_id = None
    if isinstance(instance, UserWallet):
        user_id = instance.user_id
    elif isinstance(instance, MerchantSubscription):
        user_id = instance.merchant_id
    elif isinstance(instance, MerchantPlanPayment):
        user_id = instance.subscription.merchant_id
    elif isinstance(instance, Notification):
        # Solo invalidamos si es una notificación relacionada con pagos
        if instance.category in [NotificationCategory.PAYMENT_REJECTED, NotificationCategory.PAYMENT_APPROVED]:
            user_id = instance.user_id
            
    if user_id:
        cache.delete(f"cartmaker:tenant:{user_id}:subscriptions")