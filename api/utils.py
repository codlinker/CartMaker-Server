from datetime import datetime

from django.core.cache import cache
import random
from rest_framework_simplejwt.tokens import RefreshToken
from django.db import connection
from django.db.models import Count, Q

def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }

def send_email_otp(user_email) -> str:
    """
    Genera el otp para el correo del usuario.

    Returns:
        otp_code(str): Codigo de verificacion de email.
    """
    otp_code = str(random.randint(10000, 99999))
    cache_key = f"otp_verification_{user_email}"
    cache.set(cache_key, otp_code, timeout=60)
    print(f"OTP CODE GENERADO PARA EL CORREO {user_email}: ", otp_code)
    return otp_code

def get_email_otp(user_email) -> str:
    """
    Obtiene el otp generado para el correo del usuario si es que existe.

    Returns:
        otp_code(str): Codigo de verificacion de email.
    """
    cache_key = f"otp_verification_{user_email}"
    return cache.get(cache_key)


def activate_pgvector(sender, **kwargs):
    with connection.cursor() as cursor:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")

# ==========================================
# FUNCIÓN AUXILIAR PARA PARSEAR FECHAS FLEXIBLES
# ==========================================
def _parse_flexible_date(date_str):
    if not date_str:
        return None
    # 1. Quitamos cualquier hora extraña que mande Flutter (Ej: "2026-10-25 00:00:00.000" -> "2026-10-25")
    clean_str = str(date_str).split(' ')[0].split('T')[0]
    try:
        # 2. Intentar formato estándar YYYY-MM-DD
        return datetime.strptime(clean_str, '%Y-%m-%d')
    except ValueError:
        try:
            # 3. Intentar formato latino DD/MM/YYYY
            return datetime.strptime(clean_str, '%d/%m/%Y')
        except ValueError:
            try:
                # 4. Intentar formato DD-MM-YYYY
                return datetime.strptime(clean_str, '%d-%m-%Y')
            except ValueError:
                raise ValueError(f"Formato de fecha no reconocido: {date_str}")
            
def recalculate_item_popularity(inventory_item_id: str):
    """
    Función de utilidad que recalcula y actualiza la popularidad 
    de un solo ítem específico de forma atómica.
    """
    from .models import ProductViewLog, InventoryItem
    # 1. Agrupamos rápido solo para este ítem específico
    stats = ProductViewLog.objects.filter(inventory_item_id=inventory_item_id).aggregate(
        views=Count('id'),
        carts=Count('id', filter=Q(added_to_cart=True)),
        buys=Count('id', filter=Q(bought=True)) # Añadimos compras para el futuro
    )
    
    # 2. Aplicamos los pesos de la fórmula comercial
    views_score = (stats['views'] or 0) * 1.0
    carts_score = (stats['carts'] or 0) * 5.0
    buys_score = (stats['buys'] or 0) * 15.0 # Mayor peso si terminó en compra
    
    total_popularity = views_score + carts_score + buys_score
    
    # 3. Actualización atómica en BD sin disparar el método save() completo
    InventoryItem.objects.filter(id=inventory_item_id).update(
        cached_popularity_score=total_popularity
    )