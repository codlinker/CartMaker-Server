from datetime import datetime
import json
import math
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
    # Contexto de sesión: los logins normales siempre emiten tokens de la cuenta personal
    refresh['ctx'] = 'personal'
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }

def _deliver_otp_email_sync(user_email: str, otp_code: str, timestamp_str: str) -> None:
    context = {
        'otp_code': otp_code,
        'timestamp': timestamp_str,
    }
    subject = "Tu código de verificación de CartMaker"
    from_email = settings.DEFAULT_FROM_EMAIL

    text_content = render_to_string('emails/otp_verification.txt', context)
    html_content = render_to_string('emails/otp_verification.html', context)

    email = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=from_email,
        to=[user_email],
    )
    email.attach_alternative(html_content, "text/html")

    logo_path = os.path.join(settings.BASE_DIR, 'web', 'static', 'img', 'logo_sin_letras.png')
    try:
        with open(logo_path, 'rb') as f:
            logo_image = MIMEImage(f.read())
            logo_image.add_header('Content-ID', '<logo_cartmaker>')
            logo_image.add_header('Content-Disposition', 'inline', filename='logo.png')
            email.attach(logo_image)
    except Exception as img_error:
        print(f"No se pudo cargar el logo para el correo: {img_error}")

    email.send(fail_silently=False)
    print(f"OTP ENVIADO CON ÉXITO A {user_email}: {otp_code}")


def send_email_otp(user_email: str) -> str:
    otp_code = str(random.randint(10000, 99999))
    cache_key = f"otp_verification_{user_email}"
    cache.set(cache_key, otp_code, timeout=120)
    timestamp_str = datetime.now().strftime("%d/%m/%Y %I:%M %p")

    try:
        from api.tasks import send_otp_email_task
        send_otp_email_task.delay(user_email, otp_code, timestamp_str)
    except Exception as broker_err:
        print(f"Fallback síncrono para despacho OTP ({broker_err}):")
        try:
            _deliver_otp_email_sync(user_email, otp_code, timestamp_str)
        except Exception as e:
            print(f"Error crítico en el despacho del OTP hacia {user_email}: {str(e)}")
            raise e

    return otp_code

def _deliver_employee_invitation_email_sync(to_email: str, context: dict) -> None:
    """
    Envía (de forma síncrona) el correo de invitación para trabajar en un comercio.
    `context` debe traer: company_name, role_label, link, short_code, expires_at, inviter_name.
    """
    safe_context = dict(context or {})
    safe_context.setdefault('domain', getattr(settings, 'DOMAIN', '') or '')
    subject = f"{safe_context.get('company_name') or 'Un comercio'} te invitó a trabajar en CartMaker"

    text_content = render_to_string('emails/employee_invitation.txt', safe_context)
    html_content = render_to_string('emails/employee_invitation.html', safe_context)

    email = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to_email],
    )
    email.attach_alternative(html_content, "text/html")

    logo_path = os.path.join(settings.BASE_DIR, 'web', 'static', 'img', 'logo_sin_letras.png')
    try:
        with open(logo_path, 'rb') as f:
            logo_image = MIMEImage(f.read())
            logo_image.add_header('Content-ID', '<logo_cartmaker>')
            logo_image.add_header('Content-Disposition', 'inline', filename='logo.png')
            email.attach(logo_image)
    except Exception as img_error:
        print(f"No se pudo cargar el logo para el correo de invitación: {img_error}")

    email.send(fail_silently=False)
    print(f"INVITACIÓN DE TRABAJADOR ENVIADA A {to_email}")


def send_employee_invitation_email(to_email: str, context: dict) -> None:
    """
    Despacha el correo de invitación por Celery (no bloquea el worker HTTP).
    Si el broker no está disponible, intenta el envío síncrono sin propagar errores.
    """
    try:
        from api.tasks import send_employee_invitation_email_task
        send_employee_invitation_email_task.delay(to_email, context)
    except Exception as broker_err:
        print(f"Fallback síncrono para invitación de trabajador ({broker_err}):")
        try:
            _deliver_employee_invitation_email_sync(to_email, context)
        except Exception as e:
            print(f"Error enviando la invitación de trabajador a {to_email}: {e}")

def get_email_otp(user_email) -> str:
    """
    Obtiene el otp generado para el correo del usuario si es que existe.

    Returns:
        otp_code(str): Codigo de verificacion de email.
    """
    cache_key = f"otp_verification_{user_email}"
    return cache.get(cache_key)


def _deliver_atlas_invoice_email_sync(invoice_id: str) -> bool:
    """
    Envía por correo electrónico el comprobante / factura digital de Atlas Plus
    con enlace directo al documento legal imprimible/PDF.
    """
    from .models import AtlasPlusInvoice

    invoice = AtlasPlusInvoice.objects.select_related('user', 'payment').filter(pk=invoice_id).first()
    if not invoice or not invoice.buyer_email:
        return False

    inv_data = invoice.get_json()
    issuer = inv_data['issuer']
    buyer = inv_data['buyer']
    amounts = inv_data['amounts']
    pay_info = inv_data['payment_details']
    doc_title = inv_data.get('document_title', 'COMPROBANTE DIGITAL DE PAGO')
    doc_num_label = inv_data.get('document_number_label', 'Comprobante N°')
    ctrl_label = inv_data.get('control_number_label', 'Control Interno N°')
    grand_total_label = inv_data.get('grand_total_label', 'TOTAL PAGADO')
    legal_note_text = inv_data.get('legal_note') or invoice.legal_note

    subject = f"{doc_title.title()} {invoice.invoice_number} — Plan Atlas Plus ({issuer['trade_name']})"
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@cartmaker.app')

    text_content = (
        f"{doc_title} | {doc_num_label.upper()} {invoice.invoice_number} | {ctrl_label.upper()} {invoice.control_number}\n"
        f"Emisor: {issuer['name']} — RIF: {issuer['rif']}"
        f"{(' | C.I.: ' + issuer['cedula']) if issuer.get('cedula') else ''}\n"
        f"Domicilio Fiscal: {issuer['fiscal_address']}\n"
        f"------------------------------------------------------------\n"
        f"Cliente / Adquiriente: {buyer['name']}\n"
        f"RIF / C.I.: {buyer['document']}\n"
        f"Domicilio: {buyer['address']}\n"
        f"Fecha de Emisión: {inv_data['issued_at']}\n"
        f"Concepto: {invoice.clean_concept_description} ({invoice.contracted_daily_limit} consultas diarias incluidas)\n"
        f"Vigencia: {inv_data['period_start']} al {inv_data['period_end']}\n"
        f"Tasa Oficial BCV: {pay_info['bcv_rate_formatted']}\n"
        f"{grand_total_label}: {amounts['total_bs_formatted']} (Equivalente: {amounts['total_usd_formatted']})\n"
        f"Método de Pago: {pay_info['payment_method']} (Ref: {pay_info['reference_number']})\n"
        f"------------------------------------------------------------\n"
        f"Ver y Descargar {doc_title.title()} (PDF / Impresión):\n"
        f"{invoice.invoice_url}\n"
    )

    cedula_badge = f" · C.I.: {issuer['cedula']}" if issuer.get('cedula') else ""
    html_content = f"""
    <div style="font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:640px;margin:0 auto;background:#f8fafc;padding:24px;color:#0f172a;">
      <div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:16px;overflow:hidden;box-shadow:0 10px 25px rgba(15,23,42,0.06);">
        <div style="background:linear-gradient(135deg,#4c1d95 0%,#6d28d9 50%,#7c3aed 100%);padding:24px 28px;color:#ffffff;">
          <div style="font-size:11px;letter-spacing:1.5px;text-transform:uppercase;opacity:0.85;font-weight:700;">República Bolivariana de Venezuela · {doc_title}</div>
          <h1 style="margin:6px 0 4px;font-size:22px;font-weight:800;">{doc_num_label} {invoice.invoice_number}</h1>
          <div style="font-size:13px;opacity:0.92;">{ctrl_label}: <strong>{invoice.control_number}</strong> · Código Verificador: <strong>{invoice.verification_code}</strong></div>
        </div>
        <div style="padding:24px 28px;">
          <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:14px 16px;margin-bottom:18px;">
            <div style="font-size:11px;text-transform:uppercase;letter-spacing:0.8px;color:#64748b;font-weight:700;">Datos del Emisor ({issuer['issuer_type_label']})</div>
            <div style="font-size:15px;font-weight:800;color:#0f172a;margin-top:4px;">{issuer['name']} ({issuer['trade_name']})</div>
            <div style="font-size:13px;color:#334155;margin-top:2px;"><strong>RIF SENIAT:</strong> {issuer['rif']}{cedula_badge}</div>
            <div style="font-size:12px;color:#475569;margin-top:4px;line-height:1.4;"><strong>Domicilio Fiscal:</strong> {issuer['fiscal_address']}</div>
          </div>

          <div style="margin-bottom:18px;font-size:13px;color:#334155;line-height:1.6;">
            <div><strong>Adquiriente / Cliente:</strong> {buyer['name']}</div>
            <div><strong>RIF / Cédula:</strong> {buyer['document']}</div>
            <div><strong>Domicilio / Ubicación:</strong> {buyer['address']}</div>
            <div><strong>Fecha de Emisión:</strong> {inv_data['issued_at']}</div>
            <div><strong>Periodo de Suscripción:</strong> {inv_data['period_start']} al {inv_data['period_end']}</div>
            <div><strong>Método de Pago:</strong> {pay_info['payment_method']} (Ref: {pay_info['reference_number']})</div>
            <div><strong>Tasa Oficial BCV Aplicada:</strong> {pay_info['bcv_rate_formatted']}</div>
          </div>

          <table style="width:100%;border-collapse:collapse;margin-bottom:18px;font-size:13px;">
            <thead>
              <tr style="background:#f1f5f9;color:#475569;text-align:left;">
                <th style="padding:10px 12px;border-bottom:1px solid #cbd5e1;">Concepto</th>
                <th style="padding:10px 12px;border-bottom:1px solid #cbd5e1;text-align:right;">Monto Bs.</th>
                <th style="padding:10px 12px;border-bottom:1px solid #cbd5e1;text-align:right;">Ref. USD</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td style="padding:12px;border-bottom:1px solid #e2e8f0;color:#0f172a;">{invoice.clean_concept_description} ({invoice.contracted_daily_limit} consultas diarias)</td>
                <td style="padding:12px;border-bottom:1px solid #e2e8f0;text-align:right;font-weight:700;">{amounts['subtotal_bs_formatted']}</td>
                <td style="padding:12px;border-bottom:1px solid #e2e8f0;text-align:right;font-weight:700;">{amounts['subtotal_usd_formatted']}</td>
              </tr>
            </tbody>
          </table>

          <div style="background:#faf5ff;border:1px solid #e9d5ff;border-radius:12px;padding:14px 16px;margin-bottom:20px;">
            <div style="display:flex;justify-content:space-between;font-size:13px;color:#4c1d95;margin-bottom:4px;">
              <span>Monto Exento / No Sujeto:</span>
              <strong>{amounts['exempt_amount_bs_formatted']} ({amounts['exempt_amount_usd_formatted']})</strong>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:16px;color:#3b0764;font-weight:800;margin-top:6px;padding-top:6px;border-top:1px dashed #d8b4fe;">
              <span>{grand_total_label}:</span>
              <span>{amounts['total_bs_formatted']} / {amounts['total_usd_formatted']}</span>
            </div>
          </div>

          <div style="text-align:center;margin:22px 0;">
            <a href="{invoice.invoice_url}" style="display:inline-block;background:#6d28d9;color:#ffffff;text-decoration:none;font-weight:700;font-size:14px;padding:12px 24px;border-radius:10px;">
              Ver / Descargar {doc_title.title()} en PDF
            </a>
          </div>

          <p style="font-size:11px;color:#64748b;line-height:1.5;margin-top:18px;border-top:1px solid #e2e8f0;padding-top:12px;">
            {legal_note_text}
          </p>
        </div>
      </div>
    </div>
    """

    email = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=from_email,
        to=[invoice.buyer_email],
    )
    email.attach_alternative(html_content, "text/html")
    email.send(fail_silently=True)
    return True


def send_atlas_invoice_email(invoice_id: str) -> None:
    try:
        from api.tasks import send_atlas_invoice_email_task
        send_atlas_invoice_email_task.delay(str(invoice_id))
    except Exception:
        try:
            _deliver_atlas_invoice_email_sync(str(invoice_id))
        except Exception as e:
            print(f"Aviso: No se pudo despachar correo de factura {invoice_id}: {e}")


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
    if not inventory_item_id:
        return
    try:
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
    except Exception:
        pass

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

# -------------------------------------------------------------------------
# VERSIONADO DEL MODELO FACIAL (migración fp32 -> int8 sin re-registro masivo)
# -------------------------------------------------------------------------
# Cada User guarda en `biometric_model_version` con qué modelo se generó su `biometric_vector`.
# Los embeddings de modelos distintos NO son comparables entre sí (espacios latentes distintos),
# por eso TODA comparación (login 1:1, login 1:N, duplicados KYC, rolling template) se hace
# exclusivamente entre vectores de la MISMA versión y con los umbrales de esa versión.
#
# LIMITACIÓN CONOCIDA: mientras convivan dos versiones, la detección de multicuenta (KYC 1:N)
# NO cruza versiones: una persona registrada con 'mobilefacenet-fp32-v1' podría abrir una segunda
# cuenta registrándose con 'mobilefacenet-int8-v1' sin ser detectada. Se mitiga acortando la
# ventana de convivencia (re-enrolamiento forzado de usuarios antiguos) y retirando la versión
# vieja de BIOMETRIC_ALLOWED_MODEL_VERSIONS cuando termine la migración.
BIOMETRIC_MODEL_CURRENT_DEFAULT = 'mobilefacenet-fp32-v1'
BIOMETRIC_MODEL_VERSION_MAX_LENGTH = 32
_BIOMETRIC_ALLOWED_MODEL_VERSIONS_FALLBACK = frozenset({'mobilefacenet-fp32-v1', 'mobilefacenet-int8-v1'})


def _load_allowed_model_versions() -> frozenset:
    """Versiones permitidas: settings.BIOMETRIC_ALLOWED_MODEL_VERSIONS (iterable) o el valor por defecto."""
    configured = getattr(settings, 'BIOMETRIC_ALLOWED_MODEL_VERSIONS', None)
    if configured:
        if isinstance(configured, str):
            configured = [p for p in configured.split(',')]
        allowed = {
            str(v).strip().lower()[:BIOMETRIC_MODEL_VERSION_MAX_LENGTH]
            for v in configured
            if str(v).strip()
        }
        if allowed:
            return frozenset(allowed)
    return _BIOMETRIC_ALLOWED_MODEL_VERSIONS_FALLBACK


BIOMETRIC_ALLOWED_MODEL_VERSIONS = _load_allowed_model_versions()

# Umbrales por versión (perfect, acceptable_1n, one_to_one, kyc_duplicate, min_margin).
# Inicialmente IGUALES a los de fp32 para ambas versiones: la cuantización int8 debe recalibrarse con
# `scripts/calibrate_biometric_thresholds.py` sobre un set real de pares antes de cambiarlos.
_BIOMETRIC_BASE_THRESHOLDS = {
    'perfect': BIOMETRIC_LOGIN_THRESHOLD_PERFECT,
    'acceptable_1n': BIOMETRIC_LOGIN_THRESHOLD_ACCEPTABLE,
    'one_to_one': BIOMETRIC_LOGIN_THRESHOLD_1TO1,
    'kyc_duplicate': BIOMETRIC_KYC_DUPLICATE_THRESHOLD,
    'min_margin': BIOMETRIC_LOGIN_MIN_MARGIN,
}
BIOMETRIC_THRESHOLD_KEYS = tuple(_BIOMETRIC_BASE_THRESHOLDS.keys())


def _build_thresholds_by_model() -> dict:
    """
    Construye {version: {umbral: valor}}. Se pueden sobrescribir vía settings.BIOMETRIC_THRESHOLD_OVERRIDES,
    p. ej. {'mobilefacenet-int8-v1': {'acceptable_1n': 0.27, 'kyc_duplicate': 0.31}} (dict, o string JSON).
    Claves/valores inválidos se ignoran.
    """
    table = {
        version: dict(_BIOMETRIC_BASE_THRESHOLDS)
        for version in set(BIOMETRIC_ALLOWED_MODEL_VERSIONS) | _BIOMETRIC_ALLOWED_MODEL_VERSIONS_FALLBACK
    }
    overrides = getattr(settings, 'BIOMETRIC_THRESHOLD_OVERRIDES', None)
    if isinstance(overrides, str):
        try:
            overrides = json.loads(overrides) if overrides.strip() else None
        except ValueError:
            overrides = None
    if isinstance(overrides, dict):
        for version, values in overrides.items():
            version_key = str(version).strip().lower()
            if not isinstance(values, dict):
                continue
            target = table.setdefault(version_key, dict(_BIOMETRIC_BASE_THRESHOLDS))
            for key, value in values.items():
                if key not in BIOMETRIC_THRESHOLD_KEYS:
                    continue
                try:
                    fval = float(value)
                except (TypeError, ValueError):
                    continue
                if math.isfinite(fval) and 0.0 <= fval <= 2.0:
                    target[key] = fval
    return table


BIOMETRIC_THRESHOLDS_BY_MODEL = _build_thresholds_by_model()


def normalize_embedding_model_version(raw) -> str:
    """
    Normaliza la versión del modelo facial enviada por el cliente (`embedding_model_version`):
    strip + minúsculas + máx. 32 caracteres. Vacío/None => BIOMETRIC_MODEL_CURRENT_DEFAULT
    (apps antiguas que no envían el campo). Valor no permitido => ValueError con mensaje claro.
    """
    if raw is None:
        return BIOMETRIC_MODEL_CURRENT_DEFAULT
    version = str(raw).strip().lower()
    if not version:
        return BIOMETRIC_MODEL_CURRENT_DEFAULT
    if len(version) > BIOMETRIC_MODEL_VERSION_MAX_LENGTH:
        raise ValueError(
            f"embedding_model_version excede {BIOMETRIC_MODEL_VERSION_MAX_LENGTH} caracteres y no es una versión soportada."
        )
    if version not in BIOMETRIC_ALLOWED_MODEL_VERSIONS:
        raise ValueError(
            f"Versión de modelo facial no soportada: '{version}'. "
            f"Versiones permitidas: {', '.join(sorted(BIOMETRIC_ALLOWED_MODEL_VERSIONS))}."
        )
    return version


def get_biometric_thresholds(version=None) -> dict:
    """Umbrales {perfect, acceptable_1n, one_to_one, kyc_duplicate, min_margin} de la versión (copia)."""
    key = str(version or BIOMETRIC_MODEL_CURRENT_DEFAULT).strip().lower()
    return dict(
        BIOMETRIC_THRESHOLDS_BY_MODEL.get(key)
        or BIOMETRIC_THRESHOLDS_BY_MODEL.get(BIOMETRIC_MODEL_CURRENT_DEFAULT)
        or _BIOMETRIC_BASE_THRESHOLDS
    )


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