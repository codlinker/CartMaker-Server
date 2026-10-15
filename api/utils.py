from datetime import datetime
import os
import re
import hashlib
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

def validate_venezuelan_rif_modulo11(raw_rif: str):
    """
    Valida sintaxis y dígito verificador Módulo 11 del SENIAT en el servidor.
    Retorna (is_valid: bool, normalized_rif: str, error_msg: str | None)
    """
    if not raw_rif:
        return False, "", "El número de RIF es obligatorio."
    cleaned = re.sub(r"[^A-Z0-9]", "", raw_rif.upper())
    match = re.match(r"^([JGVEP])(\d{8})(\d)$", cleaned)
    if not match:
        return False, "", "Formato de RIF inválido. Ejemplo válido: J-31234567-8."
    letter, body_digits, check_str = match.groups()
    provided_check = int(check_str)
    prefix_weights = {"V": 4, "E": 8, "J": 12, "P": 16, "G": 20}
    multipliers = [3, 2, 7, 6, 5, 4, 3, 2]
    total = prefix_weights.get(letter, 0)
    for i in range(8):
        total += int(body_digits[i]) * multipliers[i]
    remainder = 11 - (total % 11)
    expected_check = 0 if remainder >= 10 else remainder
    normalized = f"{letter}-{body_digits}-{provided_check}"
    if provided_check != expected_check:
        return (
            False,
            normalized,
            f"El RIF {normalized} no supera la validación matemática Módulo 11 del SENIAT (dígito esperado: -{expected_check})."
        )
    return True, normalized, None


# =========================================================================
# CONSTANTES Y NORMALIZACIÓN MATEMÁTICA BIOMÉTRICA (512 DIMENSIONES)
# =========================================================================
BIOMETRIC_VECTOR_DIMENSIONS = 512

# Umbral de Distancia Coseno (1 - cos(theta)) para detección de multicuentas en KYC (1:N).
# En espacios ArcFace/MobileFaceNet de 512-D sobre la hiperesfera unitaria S^511:
# - Dos selfies de la misma persona en distintas sesiones/iluminaciones caen en [0.06, 0.28].
# - Dos personas distintas tienen distancia esperada ~1.00 (sigma = 1/sqrt(512) = 0.0442).
# Al fijar 0.30 (>= BIOMETRIC_LOGIN_THRESHOLD_ACCEPTABLE), garantizamos que ninguna identidad
# que pueda hacer login pase desapercibida al intentar registrar una segunda cuenta.
BIOMETRIC_KYC_DUPLICATE_THRESHOLD = 0.30

# Umbrales de Distancia Coseno para Login Biométrico:
# - PERFECT (<= 0.18): Coincidencia de altísima confianza (cos(theta) >= 0.82). Único rango donde se permite
#   adaptación suave de plantilla (rolling template).
# - ACCEPTABLE (<= 0.26): Límite estricto para búsqueda global 1:N (cos(theta) >= 0.74).
# - 1TO1 (<= 0.30): Límite cuando el cliente especifica email o user_id (verificación 1:1).
# - MIN_MARGIN (0.08): Margen mínimo (Lowe's Ratio / Margin gap) requerido entre el 1.er y 2.do vecino
#   más cercano en búsquedas 1:N para rechazar colisiones ambiguas.
BIOMETRIC_LOGIN_THRESHOLD_PERFECT = 0.18
BIOMETRIC_LOGIN_THRESHOLD_ACCEPTABLE = 0.26
BIOMETRIC_LOGIN_THRESHOLD_1TO1 = 0.30
BIOMETRIC_LOGIN_MIN_MARGIN = 0.08


def normalize_biometric_vector(
    raw_vector,
    expected_dim: int = BIOMETRIC_VECTOR_DIMENSIONS,
) -> tuple[bool, list[float], str | None]:
    """
    Valida dimensionalidad, finitud, varianza no degenerada y proyecta el vector biométrico
    sobre la hiperesfera unitaria S^(d-1) mediante normalización L2 estricta (||v||_2 = 1.0).
    """
    if isinstance(raw_vector, str):
        try:
            import json
            raw_vector = json.loads(raw_vector)
        except Exception:
            return False, [], "Formato de vector biométrico inválido."

    if not isinstance(raw_vector, (list, tuple)) or len(raw_vector) != expected_dim:
        actual_len = len(raw_vector) if isinstance(raw_vector, (list, tuple)) else 0
        return (
            False,
            [],
            f"El vector biométrico debe tener exactamente {expected_dim} dimensiones (recibido: {actual_len}).",
        )

    try:
        floats = [float(x) for x in raw_vector]
    except (ValueError, TypeError):
        return False, [], "El vector biométrico contiene valores no numéricos."

    if any(math.isnan(x) or math.isinf(x) for x in floats):
        return False, [], "El vector biométrico contiene valores NaN o infinitos."

    norm_sq = sum(x * x for x in floats)
    norm = math.sqrt(norm_sq)
    if norm < 1e-6:
        return False, [], "Vector biométrico nulo o degenerado (norma cercana a cero)."

    mean_val = sum(floats) / expected_dim
    variance = sum((x - mean_val) ** 2 for x in floats) / expected_dim
    if variance < 1e-8:
        return False, [], "Vector biométrico inválido (varianza uniforme/sintética)."

    normalized = [x / norm for x in floats]
    return True, normalized, None