"""
Servicios del ciclo de vida de la orden (despacho y finalización).

Se extrajeron de `OrderViewSet.merchant_ship_order` y `OrderViewSet.complete_order` para que
el futuro flujo de delivery (repartidor: PICKED_UP / DELIVERED) reutilice exactamente la
misma lógica. Los endpoints existentes conservan su contrato de request/response.

IMPORTANTE: Todas las funciones esperan recibir la orden YA BLOQUEADA dentro de una
transacción, es decir:

    with transaction.atomic():
        order = Order.objects.select_for_update(of=('self',)).select_related('store__company').get(...)
        ship_order_service(order, request.user)

Los errores de negocio se lanzan como `OrderServiceError` (mensaje + status HTTP). Como se lanzan
antes de modificar datos, el rollback de la transacción no altera el comportamiento previo.
Las notificaciones se despachan con `transaction.on_commit`.
"""
import math
from typing import Optional

from django.db import transaction
from django.utils import timezone

from ..models import (
    Order,
    OrderStatus,
    WithdrawalType,
    Notification,
    InventoryItem,
    InventoryItemTransaction,
    TransactionType,
    VideoEngagementLog,
    TokenWallet,
    TokenWalletTransaction,
    MerchantCalification,
    ProductCalification,
)
from .firebase_admin import NotificationManager

ACTOR_CLIENT = 'client'
ACTOR_MERCHANT = 'merchant'
ACTOR_RIDER = 'rider'


class OrderServiceError(Exception):
    """ Error de negocio del ciclo de vida de la orden. """

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


# =========================================================================
# DESPACHO (WAITING -> DELIVERY_SENT)
# =========================================================================
def ship_order_service(order: Order, actor_user=None,
                       notify_title: Optional[str] = None,
                       notify_body: Optional[str] = None) -> Order:
    """
    Marca una orden de delivery como enviada (DELIVERY_SENT) y notifica al cliente tras el commit.

    La validación de pertenencia (dueño del comercio / repartidor asignado) la hace quien llama.
    `actor_user` se recibe para auditoría y para el futuro flujo del repartidor.
    """
    if order.withdrawal_type != WithdrawalType.DELIVERY: # DELIVERY
        raise OrderServiceError("Esta orden no requiere despacho a domicilio.")

    if order.status == OrderStatus.REPORTED:
        raise OrderServiceError(
            "Esta orden ha sido reportada y se encuentra en revisión por Soporte CartMaker. No puede despacharse hasta que finalice la revisión."
        )

    if order.status != OrderStatus.WAITING: # WAITING
        raise OrderServiceError("La orden ya ha cambiado de estado.")

    order.status = OrderStatus.DELIVERY_SENT # ENVIADO / EN CAMINO
    order.save(update_fields=['status'])

    # 💡 SOLUCIÓN CASO BORDE 1: Marcamos como leídas las notificaciones previas de esta orden
    Notification.objects.filter(metadata__order_id=str(order.id), is_read=False).update(is_read=True)

    client_id = order.client_id
    target_order_id = order.id
    company_name = order.store.company.name
    title = notify_title or "¡Tu orden va en camino!"
    body = notify_body or f"El repartidor de {company_name} ha salido con tus productos."

    transaction.on_commit(
        lambda: NotificationManager.notify_order_status_change(
            user_id=client_id,
            order_id=target_order_id,
            title=title,
            body=body,
            is_merchant=False,
            new_status=OrderStatus.DELIVERY_SENT
        )
    )
    return order


# =========================================================================
# FINALIZACIÓN (-> COMPLETED) Y CALIFICACIÓN DEL CLIENTE
# =========================================================================
def resolve_order_actor_role(order: Order, actor_user) -> Optional[str]:
    """ 'client' si es el comprador, 'merchant' si es el dueño del comercio, o None. """
    if actor_user is None:
        return None
    if order.client_id == actor_user.id:
        return ACTOR_CLIENT
    if order.store.company.owner_id == actor_user.id:
        return ACTOR_MERCHANT
    return None


def apply_order_completion_side_effects(order: Order) -> float:
    """
    Efectos de completar la orden: estado COMPLETED, egresos de stock, atribución de video,
    lectura de notificaciones previas y tokens de gamificación.
    No guarda la orden (lo hace quien llama). Retorna los tokens ganados por el cliente.
    """
    cart_data = order.cart if isinstance(order.cart, dict) else {}
    cart_items = cart_data.get('items', [])
    tokens_earned = 0.0
    company = order.store.company

    order.status = OrderStatus.COMPLETED
    order.end_time = timezone.now()

    for item in cart_items:
        inv_item_id = item.get('inventory_item_id')
        raw_qty = float(item.get('quantity', 0) or 0)
        qty = int(item.get('stock_units_deducted') or (max(1, math.ceil(raw_qty)) if raw_qty > 0 else 0))

        # 💡 EXTRAEMOS LA ETIQUETA DEL VIDEO DEL SNAPSHOT DE LA ORDEN
        source_video_id = item.get('source_video_id')

        if inv_item_id and qty > 0:
            try:
                inv_item = InventoryItem.objects.get(id=inv_item_id)
                InventoryItemTransaction.objects.create(
                    item=inv_item,
                    units=qty,
                    transaction_type=TransactionType.OUTCOME
                )
            except InventoryItem.DoesNotExist:
                pass # Si el producto ya no existe, ignoramos

        # =========================================================
        # 💡 REGISTRO DE COMPRA DE VIDEO (Atribución Real en Checkout)
        # =========================================================
        if source_video_id:
            try:
                log = VideoEngagementLog.objects.filter(
                    client=order.client,
                    video_id=source_video_id
                ).order_by('-timestamp').first()

                if log:
                    log.bought_from_video = True
                    log.save(update_fields=['bought_from_video'])
                else:
                    VideoEngagementLog.objects.create(
                        client=order.client,
                        video_id=source_video_id,
                        bought_from_video=True
                    )
            except Exception as e:
                print(f"❌ Error actualizando atribución de video: {e}")

    Notification.objects.filter(metadata__order_id=str(order.id), is_read=False).update(is_read=True)

    if company.gamification_enabled and company.gamification_tokens_per_dollar > 0:
        order_total = max(0.0, float(cart_data.get('total', 0.0)))
        tokens_earned = int(order_total * company.gamification_tokens_per_dollar)

        if tokens_earned > 0:
            wallet, _ = TokenWallet.objects.select_for_update().get_or_create(
                user=order.client,
                company=company
            )
            wallet.balance += tokens_earned
            wallet.save(update_fields=['balance'])

            TokenWalletTransaction.objects.create(
                token_wallet=wallet, amount=tokens_earned,
                transaction_type=TransactionType.INCOME, order=order
            )

    return tokens_earned


def apply_client_rating(order: Order, client_user, merchant_rating=0, product_ratings=None,
                        was_already_completed: bool = False) -> bool:
    """
    El cliente califica (una sola vez por orden, validando pertenencia y rango [1.0, 5.0]).
    Marca `cart['client_rated']` si calificó algo o si la orden se completó en esta misma llamada.
    No guarda la orden (lo hace quien llama). Retorna True si se registró alguna calificación.
    """
    cart_data = order.cart if isinstance(order.cart, dict) else {}
    cart_items = cart_data.get('items', [])
    rated_any = False
    try:
        m_rating_val = float(merchant_rating or 0)
    except (ValueError, TypeError):
        m_rating_val = 0.0
    if m_rating_val > 0:
        clamped_m_rating = min(5.0, max(1.0, m_rating_val))
        MerchantCalification.objects.create(
            merchant=order.store.company,
            client=client_user,
            rating=clamped_m_rating
        )
        rated_any = True
    valid_product_ids = {str(item.get('product_id')) for item in cart_items if item.get('product_id')}
    seen_product_ids = set()
    if isinstance(product_ratings, list):
        for pr in product_ratings:
            if not isinstance(pr, dict):
                continue
            product_id = pr.get('product_id')
            pid_str = str(product_id) if product_id else ''
            if not pid_str or pid_str in seen_product_ids or pid_str not in valid_product_ids:
                continue
            try:
                rating_val = float(pr.get('rating', 0) or 0)
            except (ValueError, TypeError):
                rating_val = 0.0
            if rating_val > 0:
                seen_product_ids.add(pid_str)
                clamped_p_rating = min(5.0, max(1.0, rating_val))
                ProductCalification.objects.create(
                    product_id=product_id,
                    client=client_user,
                    rating=clamped_p_rating
                )
                rated_any = True
    if rated_any or not was_already_completed:
        cart_data['client_rated'] = True
        order.cart = cart_data
    return rated_any


def complete_order_service(order: Order, actor_user, merchant_rating=0, product_ratings=None,
                           actor_role: Optional[str] = None) -> dict:
    """
    Completa la orden (o registra la calificación pendiente del cliente si ya estaba completada).

    Args:
        order: Orden bloqueada con select_for_update(of=('self',)) y select_related('store__company').
        actor_user: Usuario que ejecuta la acción.
        merchant_rating / product_ratings: Calificaciones del cliente (solo aplican si actor es el cliente).
        actor_role: 'client' | 'merchant' | 'rider'. Si es None se deduce de `actor_user`.
            El rol 'rider' lo debe validar quien llama (flujo de delivery con PIN).

    Returns:
        dict: {'tokens_earned': float, 'already_completed': bool, 'actor_role': str}
    """
    if actor_role is None:
        actor_role = resolve_order_actor_role(order, actor_user)
    if actor_role not in (ACTOR_CLIENT, ACTOR_MERCHANT, ACTOR_RIDER):
        raise OrderServiceError("No tienes permisos sobre esta orden.", status_code=403)

    is_client = actor_role == ACTOR_CLIENT
    is_merchant = actor_role == ACTOR_MERCHANT

    if order.status == OrderStatus.REPORTED:
        raise OrderServiceError(
            "Esta orden ha sido reportada y se encuentra en revisión por Soporte CartMaker. No puede completarse hasta que finalice la revisión."
        )

    if order.status in (OrderStatus.CANCELLED, OrderStatus.SOLVED):
        raise OrderServiceError("No se puede completar una orden cancelada o cerrada.")

    cart_data = order.cart if isinstance(order.cart, dict) else {}
    already_completed = (order.status == OrderStatus.COMPLETED)
    client_already_rated = bool(cart_data.get('client_rated', False))

    # Si la orden ya estaba completada, solo permitimos que el cliente envíe su calificación pendiente una única vez
    if already_completed and (not is_client or client_already_rated):
        raise OrderServiceError("Esta orden ya se encuentra completada.")

    tokens_earned = 0.0
    if not already_completed:
        tokens_earned = apply_order_completion_side_effects(order)

    if is_client and not client_already_rated:
        apply_client_rating(
            order,
            client_user=actor_user,
            merchant_rating=merchant_rating,
            product_ratings=product_ratings,
            was_already_completed=already_completed,
        )

    order.save()

    if not already_completed:
        owner_id = order.store.company.owner_id
        client_id = order.client_id
        company_name = order.store.company.name
        oid = order.id

        if is_client:
            transaction.on_commit(lambda: NotificationManager.notify_order_status_change(
                user_id=owner_id,
                order_id=oid,
                title="Cliente confirmó entrega",
                body=f"El cliente de la orden N° {oid} la ha marcado como completada.",
                is_merchant=True,
                new_status=OrderStatus.COMPLETED
            ))
        elif is_merchant:
            transaction.on_commit(lambda: NotificationManager.notify_order_status_change(
                user_id=client_id,
                order_id=oid,
                title="Tu orden fue completada",
                body=f"{company_name} ha marcado tu pedido como completado exitosamente.",
                is_merchant=False,
                new_status=OrderStatus.COMPLETED
            ))
        else:
            # Entrega confirmada por el repartidor: se avisa a ambas partes
            transaction.on_commit(lambda: NotificationManager.notify_order_status_change(
                user_id=client_id,
                order_id=oid,
                title="Tu pedido fue entregado",
                body=f"El repartidor de {company_name} confirmó la entrega de tu pedido.",
                is_merchant=False,
                new_status=OrderStatus.COMPLETED
            ))
            transaction.on_commit(lambda: NotificationManager.notify_order_status_change(
                user_id=owner_id,
                order_id=oid,
                title="Pedido entregado",
                body=f"El repartidor confirmó la entrega de la orden N° {oid}.",
                is_merchant=True,
                new_status=OrderStatus.COMPLETED
            ))

    return {
        'tokens_earned': round(float(tokens_earned), 2),
        'already_completed': already_completed,
        'actor_role': actor_role,
    }
