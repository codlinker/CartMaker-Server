from datetime import datetime
import os

from django.core.cache import cache
import random
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from rest_framework_simplejwt.tokens import RefreshToken
from django.db import connection
from django.db.models import Count, Q
from django.conf import settings
from email.mime.image import MIMEImage

def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }

def send_email_otp(user_email: str) -> str:
    otp_code = str(random.randint(10000, 99999))
    cache_key = f"otp_verification_{user_email}"
    cache.set(cache_key, otp_code, timeout=60)
    
    context = {
        'otp_code': otp_code,
        'timestamp': datetime.now().strftime("%d/%m/%Y %I:%M %p")
    }
    
    subject = "Tu código de verificación de CartMaker"
    from_email = settings.DEFAULT_FROM_EMAIL
    
    try:
        text_content = render_to_string('emails/otp_verification.txt', context)
        html_content = render_to_string('emails/otp_verification.html', context)
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=[user_email]
        )
        email.attach_alternative(html_content, "text/html")
        
        # --- LÓGICA PARA INCRUSTAR EL LOGO (CID INLINE) ---
        logo_path = os.path.join(settings.BASE_DIR, 'web', 'static', 'img', 'logo_sin_letras.png')
        
        try:
            with open(logo_path, 'rb') as f:
                logo_image = MIMEImage(f.read())
                # Le damos el ID exacto que usamos en el src="cid:logo_cartmaker" del HTML
                logo_image.add_header('Content-ID', '<logo_cartmaker>')
                # Indicamos que es un elemento en línea, no un archivo adjunto para descargar
                logo_image.add_header('Content-Disposition', 'inline', filename='logo.png')
                email.attach(logo_image)
        except Exception as img_error:
            print(f"No se pudo cargar el logo para el correo: {img_error}")
        # --------------------------------------------------

        email.send(fail_silently=False)
        print(f"OTP ENVIADO CON ÉXITO A {user_email}: {otp_code}")
        
    except Exception as e:
        print(f"Error crítico en el despacho del OTP hacia {user_email}: {str(e)}")
        raise e 

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
def parse_flexible_date(date_str):
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
    from .models import ProductViewLog, InventoryItem
    from django.utils import timezone
    from datetime import timedelta

    # 💡 LA MAGIA: Solo nos importa el engagement fresco de los últimos 14 días
    time_horizon = timezone.now() - timedelta(days=14)
    
    stats = ProductViewLog.objects.filter(
        inventory_item_id=inventory_item_id,
        start_time__gte=time_horizon # 👈 Filtro crítico
    ).aggregate(
        unique_viewers=Count('client', distinct=True),
        unique_carters=Count('client', filter=Q(added_to_cart=True), distinct=True),
        unique_buyers=Count('client', filter=Q(bought=True), distinct=True)
    )
    
    # Pesos comerciales exponenciales calibrados para el funnel
    views_score = (stats['unique_viewers'] or 0) * 1.0
    carts_score = (stats['unique_carters'] or 0) * 10.0
    buys_score = (stats['unique_buyers'] or 0) * 50.0 # Multiplicador de alto impacto
    
    total_popularity = views_score + carts_score + buys_score
    
    InventoryItem.objects.filter(id=inventory_item_id).update(
        cached_popularity_score=total_popularity
    )