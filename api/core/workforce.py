"""
Sistema de Trabajadores (Workforce) de CartMaker.

Contiene las reglas de negocio de:
- Pertenencia de usuarios a sucursales (dueño / trabajador asignado).
- Invitaciones (crear, previsualizar, aceptar, rechazar, revocar).
- Gestión de trabajadores por parte del dueño (rol, sucursales, suspender, revocar).
- Contexto de sesión (JWT "personal" vs. "worker") y espacios de trabajo (workspaces).
- Caché de revocación inmediata `emp:active:<emp_id>` y aviso a Node.

Las vistas (`api/views/workforce_views.py`) solo traducen HTTP <-> estas funciones.
"""
import logging
import uuid
from typing import Optional

import requests
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from ..cos import storage_manager
from ..models import (
    User,
    Company,
    CompanyStore,
    Employee,
    EmployeePermission,
    EmployeeStoreAssignment,
    EmployeeInvitation,
    EmployeeRole,
    EmployeeStatus,
    VehicleType,
    InvitationChannel,
    InvitationStatus,
    NotificationCategory,
    NotificationSection,
    EMPLOYEE_ROLE_SLUGS,
    INVITATION_SHORT_CODE_LENGTH,
)

logger = logging.getLogger(__name__)

# =========================================================================
# CONSTANTES DE CONTEXTO (claims del JWT)
# =========================================================================
CTX_CLAIM = 'ctx'
CTX_PERSONAL = 'personal'
CTX_WORKER = 'worker'
EMP_ID_CLAIM = 'emp_id'
COMPANY_ID_CLAIM = 'company_id'
ROLE_CLAIM = 'role'

EMP_ACTIVE_CACHE_TTL = 300  # 5 minutos
MAX_PENDING_INVITATIONS_PER_COMPANY = 100

CHANNEL_SLUGS = {
    'email': InvitationChannel.EMAIL,
    'in_app': InvitationChannel.IN_APP,
    'inapp': InvitationChannel.IN_APP,
    'qr_link': InvitationChannel.QR_LINK,
    'qr': InvitationChannel.QR_LINK,
    'link': InvitationChannel.QR_LINK,
}
VEHICLE_SLUGS = {
    'moto': VehicleType.MOTO,
    'bici': VehicleType.BICI,
    'bicicleta': VehicleType.BICI,
    'bike': VehicleType.BICI,
    'carro': VehicleType.CARRO,
    'car': VehicleType.CARRO,
    'pie': VehicleType.PIE,
    'a_pie': VehicleType.PIE,
    'foot': VehicleType.PIE,
}
STATUS_SLUGS = {
    'active': EmployeeStatus.ACTIVE,
    'suspended': EmployeeStatus.SUSPENDED,
    'revoked': EmployeeStatus.REVOKED,
}
STATUS_ACTION_SLUGS = {
    'reactivate': EmployeeStatus.ACTIVE,
    'activate': EmployeeStatus.ACTIVE,
    'suspend': EmployeeStatus.SUSPENDED,
    'revoke': EmployeeStatus.REVOKED,
}
ROLE_SLUGS_REVERSE = {slug: int(role) for role, slug in EMPLOYEE_ROLE_SLUGS.items()}


class WorkforceError(Exception):
    """
    Error de negocio del sistema de trabajadores. Las vistas lo convierten en
    `Response({'error': message, 'code': code}, status=status_code)`.
    """

    def __init__(self, message: str, status_code: int = 400, code: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


# =========================================================================
# 1. PERTENENCIA A COMERCIOS Y SUCURSALES
# =========================================================================
def get_owned_company(user) -> Optional[Company]:
    """ Retorna la compañía de la que el usuario es dueño, o None. """
    if not user or not getattr(user, 'is_authenticated', False):
        return None
    return Company.objects.filter(owner=user).first()


def require_owned_company(user) -> Company:
    company = get_owned_company(user)
    if company is None:
        raise WorkforceError(
            "Solo el dueño del comercio puede gestionar a sus trabajadores.",
            status_code=403,
            code='not_company_owner',
        )
    return company


def user_works_at_store(user, store) -> bool:
    """
    True si el usuario es trabajador ACTIVO de la compañía de la sucursal y está asignado a ella
    (EmployeeStoreAssignment o EmployeePermission.allowed_stores).
    """
    if not user or not getattr(user, 'is_authenticated', False) or store is None:
        return False
    return Employee.objects.filter(
        user=user,
        company_id=store.company_id,
        status=EmployeeStatus.ACTIVE,
    ).filter(
        Q(employeestoreassignment__store=store) | Q(permissions__allowed_stores=store)
    ).exists()


def user_is_store_owner_or_worker(user, store) -> bool:
    """ True si el usuario es el dueño de la compañía de la sucursal o trabaja en ella. """
    if not user or not getattr(user, 'is_authenticated', False) or store is None:
        return False
    company = getattr(store, 'company', None)
    if company is not None and company.owner_id == user.id:
        return True
    return user_works_at_store(user, store)


# =========================================================================
# 2. CACHÉ DE REVOCACIÓN INMEDIATA (emp:active:<emp_id>)
# =========================================================================
def emp_active_cache_key(emp_id) -> str:
    return f"emp:active:{emp_id}"


def _load_employee_state_from_db(emp_id) -> dict:
    emp = (
        Employee.objects.select_related('user', 'company')
        .filter(id=emp_id)
        .first()
    )
    if emp is None:
        return {'active': False, 'role': None, 'user_id': None, 'company_id': None}
    is_active = (
        emp.status == EmployeeStatus.ACTIVE
        and bool(emp.user.is_active)
        and emp.company.owner_id != emp.user_id
    )
    return {
        'active': bool(is_active),
        'role': EMPLOYEE_ROLE_SLUGS.get(emp.role, 'assistant'),
        'user_id': str(emp.user_id),
        'company_id': str(emp.company_id),
    }


def get_employee_state(emp_id, use_cache: bool = True) -> dict:
    """
    Estado vigente del trabajador: {'active', 'role', 'user_id', 'company_id'}.
    Usa Redis (TTL 5 min) con respaldo en PostgreSQL. Si Redis falla, consulta la BD.
    """
    try:
        emp_id = int(emp_id)
    except (TypeError, ValueError):
        return {'active': False, 'role': None, 'user_id': None, 'company_id': None}

    key = emp_active_cache_key(emp_id)
    if use_cache:
        try:
            cached = cache.get(key)
            if isinstance(cached, dict):
                return cached
        except Exception as e:
            logger.warning(f"Workforce: caché no disponible leyendo {key}: {e}")

    state = _load_employee_state_from_db(emp_id)
    try:
        cache.set(key, state, timeout=EMP_ACTIVE_CACHE_TTL)
    except Exception as e:
        logger.warning(f"Workforce: caché no disponible escribiendo {key}: {e}")
    return state


def is_employee_active(emp_id, user_id=None, use_cache: bool = True) -> bool:
    """ True si el trabajador sigue activo (y pertenece a `user_id`, si se indica). """
    state = get_employee_state(emp_id, use_cache=use_cache)
    if not state.get('active'):
        return False
    if user_id is not None and str(state.get('user_id')) != str(user_id):
        return False
    return True


def invalidate_employee_cache(emp_id) -> None:
    try:
        cache.delete(emp_active_cache_key(emp_id))
    except Exception as e:
        logger.warning(f"Workforce: no se pudo invalidar la caché del trabajador {emp_id}: {e}")


def _post_worker_revoked_to_node(user_id, employee_id, company_id, reason: str) -> None:
    """ Pide a Node que desconecte los sockets de trabajador de ese empleo. Nunca lanza errores. """
    try:
        requests.post(
            f"{settings.INTERNAL_WEBSOCKETS_URL}internal/emit-worker-revoked",
            json={
                'user_id': str(user_id),
                'employee_id': int(employee_id),
                'company_id': str(company_id),
                'reason': reason,
            },
            headers={'X-Microservice-Token': settings.SECRET_KEY},
            timeout=2,
        )
    except Exception as e:
        logger.warning(f"Workforce: no se pudo avisar a Node la revocación del trabajador {employee_id}: {e}")


def schedule_worker_revocation(employee: Employee, reason: str) -> None:
    """
    Invalida la caché del trabajador ahora y después del commit, y avisa a Node tras el commit.
    Debe llamarse dentro de la transacción que cambió el estado.
    """
    emp_id = employee.id
    user_id = employee.user_id
    company_id = employee.company_id
    invalidate_employee_cache(emp_id)

    def _after_commit():
        invalidate_employee_cache(emp_id)
        _post_worker_revoked_to_node(user_id, emp_id, company_id, reason)

    transaction.on_commit(_after_commit)


# =========================================================================
# 3. ESPACIOS DE TRABAJO (workspaces) Y TOKENS DE CONTEXTO
# =========================================================================
def _company_image_url(company) -> str:
    return storage_manager.get_url(company.image) if company and company.image else ''


def build_personal_workspace(user) -> dict:
    return {
        'type': CTX_PERSONAL,
        'label': 'Cuenta personal',
        'user_id': str(user.id),
    }


def build_worker_workspace(employee: Employee) -> dict:
    company = employee.company
    return {
        'type': CTX_WORKER,
        'label': f"Trabajador en {company.name}",
        'employee_id': employee.id,
        'company_id': str(company.id),
        'company_name': company.name,
        'company_image': _company_image_url(company),
        'role': employee.role_slug,
        'role_id': int(employee.role),
        'role_label': str(employee.get_role_display()),
        'vehicle_type': int(employee.vehicle_type) if employee.vehicle_type is not None else None,
        'display_alias': employee.display_alias or '',
        'stores': employee.get_store_list(),
    }


def get_active_employments(user):
    """ Empleos ACTIVOS del usuario (excluye cualquier registro en su propio comercio). """
    return (
        Employee.objects.select_related('company')
        .prefetch_related('employeestoreassignment_set__store')
        .filter(user=user, status=EmployeeStatus.ACTIVE)
        .exclude(company__owner=user)
        .order_by('hired_at')
    )


def get_user_workspaces(user) -> list:
    """
    Lista de espacios de trabajo del usuario: siempre la cuenta personal y luego
    cada empleo activo. Se incluye en la respuesta del login.
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return []
    workspaces = [build_personal_workspace(user)]
    try:
        for emp in get_active_employments(user):
            workspaces.append(build_worker_workspace(emp))
    except Exception as e:
        logger.error(f"Workforce: error armando workspaces de {user.id}: {e}")
    return workspaces


def issue_workspace_tokens(user, employee: Optional[Employee] = None) -> dict:
    """
    Emite un par refresh/access de SimpleJWT con el contexto de sesión.
    - Personal: claim `ctx='personal'`.
    - Trabajador: claims `ctx='worker'`, `emp_id`, `company_id`, `role`.
    Los claims viven en el refresh y SimpleJWT los copia al access en cada refresh.
    """
    refresh = RefreshToken.for_user(user)
    if employee is None:
        refresh[CTX_CLAIM] = CTX_PERSONAL
    else:
        refresh[CTX_CLAIM] = CTX_WORKER
        refresh[EMP_ID_CLAIM] = int(employee.id)
        refresh[COMPANY_ID_CLAIM] = str(employee.company_id)
        refresh[ROLE_CLAIM] = employee.role_slug
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
        'ctx': CTX_WORKER if employee is not None else CTX_PERSONAL,
    }


def select_workspace(user, workspace_type: str, employee_id=None) -> dict:
    """
    Cambia de espacio de trabajo y emite tokens nuevos.

    Returns:
        dict: {refresh, access, ctx, workspace, workspaces}
    """
    workspace_type = str(workspace_type or '').strip().lower()
    if workspace_type == CTX_PERSONAL:
        tokens = issue_workspace_tokens(user)
        tokens['workspace'] = build_personal_workspace(user)
        tokens['workspaces'] = get_user_workspaces(user)
        return tokens

    if workspace_type != CTX_WORKER:
        raise WorkforceError("El campo 'type' debe ser 'personal' o 'worker'.", code='invalid_workspace_type')

    emp_id = _parse_int(employee_id, 'employee_id')
    employee = (
        Employee.objects.select_related('company')
        .filter(id=emp_id, user=user)
        .first()
    )
    if employee is None:
        raise WorkforceError("No perteneces a este comercio.", status_code=404, code='employment_not_found')
    if employee.status != EmployeeStatus.ACTIVE:
        raise WorkforceError(
            "Tu acceso como trabajador de este comercio está suspendido o fue revocado.",
            status_code=403,
            code='worker_access_revoked',
        )
    if employee.company.owner_id == user.id:
        raise WorkforceError("No puedes ser trabajador de tu propio comercio.", status_code=403, code='owner_cannot_be_employee')
    if employee.role == EmployeeRole.DELIVERY and not user.cedula_verified:
        raise WorkforceError(
            "Para trabajar como repartidor debes verificar tu identidad en CartMaker.",
            status_code=403,
            code='cedula_not_verified',
        )

    Employee.objects.filter(pk=employee.pk).update(last_seen_at=timezone.now())
    invalidate_employee_cache(employee.id)

    tokens = issue_workspace_tokens(user, employee)
    tokens['workspace'] = build_worker_workspace(employee)
    tokens['workspaces'] = get_user_workspaces(user)
    return tokens


# =========================================================================
# 4. PARSEO Y VALIDACIÓN DE ENTRADAS
# =========================================================================
def _parse_int(raw, field_name: str) -> int:
    if isinstance(raw, bool):
        raise WorkforceError(f"El campo '{field_name}' es inválido.", code='invalid_field')
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        raise WorkforceError(f"El campo '{field_name}' es obligatorio y debe ser numérico.", code='invalid_field')


def _parse_choice(raw, enum_cls, slugs: dict, field_name: str, allow_none: bool = False):
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        if allow_none:
            return None
        raise WorkforceError(f"El campo '{field_name}' es obligatorio.", code='invalid_field')
    if isinstance(raw, bool):
        raise WorkforceError(f"El valor de '{field_name}' no es válido.", code='invalid_field')
    if isinstance(raw, str):
        clean = raw.strip().lower()
        if clean in slugs:
            return int(slugs[clean])
        if not clean.lstrip('-').isdigit():
            raise WorkforceError(f"El valor de '{field_name}' no es válido.", code='invalid_field')
        raw = int(clean)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise WorkforceError(f"El valor de '{field_name}' no es válido.", code='invalid_field')
    if value not in enum_cls.values:
        raise WorkforceError(f"El valor de '{field_name}' no es válido.", code='invalid_field')
    return value


def parse_role(raw) -> int:
    return _parse_choice(raw, EmployeeRole, ROLE_SLUGS_REVERSE, 'role')


def parse_channel(raw) -> int:
    return _parse_choice(raw, InvitationChannel, CHANNEL_SLUGS, 'channel')


def parse_vehicle_type(raw):
    return _parse_choice(raw, VehicleType, VEHICLE_SLUGS, 'vehicle_type', allow_none=True)


def _resolve_company_stores(company: Company, store_ids, default_all: bool) -> list:
    """
    Valida que las sucursales existan, estén activas y pertenezcan a la compañía.
    Si `store_ids` viene vacío y `default_all=True`, retorna todas las sucursales activas.
    """
    if store_ids is None or (isinstance(store_ids, (list, tuple)) and len(store_ids) == 0):
        if not default_all:
            raise WorkforceError("Debes asignar al menos una sucursal.", code='stores_required')
        stores = list(CompanyStore.objects.filter(company=company, is_active=True))
        if not stores:
            raise WorkforceError(
                "Tu comercio no tiene sucursales activas para asignar trabajadores.",
                code='no_active_stores',
            )
        return stores

    if not isinstance(store_ids, (list, tuple)):
        raise WorkforceError("El campo 'store_ids' debe ser una lista de IDs de sucursales.", code='invalid_field')

    clean_ids = set()
    for raw in store_ids:
        try:
            clean_ids.add(uuid.UUID(str(raw).strip()))
        except (TypeError, ValueError, AttributeError):
            raise WorkforceError(f"ID de sucursal inválido: {raw!r}.", code='invalid_store')

    stores = list(CompanyStore.objects.filter(company=company, is_active=True, id__in=clean_ids))
    if len(stores) != len(clean_ids):
        raise WorkforceError(
            "Una o más sucursales no existen, están inactivas o no pertenecen a tu comercio.",
            code='invalid_store',
        )
    return stores


def _sync_employee_stores(employee: Employee, stores: list) -> None:
    """ Sincroniza EmployeeStoreAssignment y EmployeePermission.allowed_stores con `stores`. """
    store_ids = {s.id for s in stores}
    EmployeeStoreAssignment.objects.filter(employee=employee).exclude(store_id__in=store_ids).delete()
    existing_ids = set(
        EmployeeStoreAssignment.objects.filter(employee=employee).values_list('store_id', flat=True)
    )
    EmployeeStoreAssignment.objects.bulk_create(
        [EmployeeStoreAssignment(employee=employee, store=s) for s in stores if s.id not in existing_ids],
        ignore_conflicts=True,
    )
    permission, _created = EmployeePermission.objects.get_or_create(employee=employee)
    permission.allowed_stores.set(stores)


def get_public_join_base() -> str:
    domain = getattr(settings, 'DOMAIN', '') or 'https://www.cartmaker.app'
    domain = domain.strip().rstrip('/')
    if '://' not in domain:
        domain = f"https://{domain}"
    return domain


def build_invitation_link(raw_token: str) -> str:
    return f"{get_public_join_base()}/join/{raw_token}"


def _user_display_name(user) -> str:
    if user is None:
        return ''
    full = f"{user.first_name or ''} {user.last_name or ''}".strip()
    return full or user.email


# =========================================================================
# 5. INVITACIONES
# =========================================================================
def create_invitation(owner, data: dict) -> tuple:
    """
    Crea una invitación (solo el dueño del comercio).

    Body esperado: {role, channel, target_email?, target_user_id?, store_ids?, ttl_hours?}

    Returns:
        tuple: (invitation, raw_token, link)
    """
    company = require_owned_company(owner)
    data = data or {}

    role = parse_role(data.get('role'))
    channel = parse_channel(data.get('channel') if data.get('channel') is not None else 'qr_link')

    target_email = (data.get('target_email') or data.get('email') or '').strip().lower() or None
    target_user_id = data.get('target_user_id') or None
    target_user = None

    if target_email:
        try:
            validate_email(target_email)
        except ValidationError:
            raise WorkforceError("El correo del destinatario no es válido.", code='invalid_email')

    if target_user_id:
        try:
            target_user = User.objects.filter(id=uuid.UUID(str(target_user_id)), is_active=True).first()
        except (TypeError, ValueError, AttributeError):
            target_user = None
        if target_user is None:
            raise WorkforceError("El usuario destinatario no existe.", status_code=404, code='target_user_not_found')

    if channel == InvitationChannel.EMAIL and not target_email:
        raise WorkforceError("Para invitar por correo debes indicar 'target_email'.", code='target_email_required')

    if channel == InvitationChannel.IN_APP and target_user is None:
        if not target_email:
            raise WorkforceError(
                "Para invitar dentro de la app debes indicar 'target_user_id' o 'target_email'.",
                code='target_required',
            )
        target_user = User.objects.filter(email__iexact=target_email, is_active=True).first()
        if target_user is None:
            raise WorkforceError(
                "No existe una cuenta de CartMaker con ese correo. Puedes invitarlo por correo o con un enlace.",
                status_code=404,
                code='target_user_not_found',
            )

    # El dueño nunca puede ser trabajador de su propio comercio
    if (target_user and target_user.id == company.owner_id) or (
        target_email and owner.email and target_email == owner.email.strip().lower()
    ):
        raise WorkforceError("No puedes invitarte a tu propio comercio.", code='owner_cannot_be_employee')

    if target_user is not None and Employee.objects.filter(
        user=target_user, company=company, status=EmployeeStatus.ACTIVE
    ).exists():
        raise WorkforceError("Esta persona ya trabaja en tu comercio.", status_code=409, code='already_employee')

    pending_count = EmployeeInvitation.objects.filter(
        company=company, status=InvitationStatus.PENDING, expires_at__gt=timezone.now()
    ).count()
    if pending_count >= MAX_PENDING_INVITATIONS_PER_COMPANY:
        raise WorkforceError(
            "Tienes demasiadas invitaciones pendientes. Revoca algunas antes de crear nuevas.",
            status_code=429,
            code='too_many_pending_invitations',
        )

    stores = _resolve_company_stores(company, data.get('store_ids'), default_all=True)

    ttl_hours = 72
    if data.get('ttl_hours') not in (None, ''):
        ttl_hours = _parse_int(data.get('ttl_hours'), 'ttl_hours')
        if ttl_hours < 1 or ttl_hours > 168:
            raise WorkforceError("La vigencia de la invitación debe estar entre 1 y 168 horas.", code='invalid_ttl')

    with transaction.atomic():
        try:
            invitation, raw_token = EmployeeInvitation.create_with_token(
                company=company,
                invited_by=owner,
                role=role,
                channel=channel,
                target_email=target_email,
                target_user=target_user,
                stores=stores,
                ttl_hours=ttl_hours,
            )
        except (IntegrityError, ValidationError):
            raise WorkforceError("No se pudo generar la invitación. Inténtalo de nuevo.", status_code=503, code='invitation_collision')

        link = build_invitation_link(raw_token)
        role_label = str(invitation.get_role_display())
        company_name = company.name
        inviter_name = _user_display_name(owner)
        invitation_id = invitation.id
        expires_str = timezone.localtime(invitation.expires_at).strftime("%d/%m/%Y %I:%M %p")
        short_code = invitation.short_code

        # Destinatario con cuenta en CartMaker: notificación dentro de la app
        in_app_recipient_id = None
        if target_user is not None:
            in_app_recipient_id = target_user.id
        elif target_email:
            existing = User.objects.filter(email__iexact=target_email, is_active=True).only('id').first()
            in_app_recipient_id = existing.id if existing else None

        def _after_commit():
            from .firebase_admin import NotificationManager
            if in_app_recipient_id:
                NotificationManager.notify_workforce_event(
                    user_id=in_app_recipient_id,
                    title="Te invitaron a trabajar",
                    body=f"{company_name} te invitó a unirte a su equipo como {role_label}.",
                    event_type='employee_invitation',
                    category=NotificationCategory.EMPLOYEE_INVITATION,
                    section=NotificationSection.HOME,
                    extra_data={
                        'invitation_id': invitation_id,
                        'company_id': str(company.id),
                        'role': EMPLOYEE_ROLE_SLUGS.get(role, 'assistant'),
                    },
                )
            if channel == InvitationChannel.EMAIL and target_email:
                from ..utils import send_employee_invitation_email
                send_employee_invitation_email(target_email, {
                    'company_name': company_name,
                    'role_label': role_label,
                    'link': link,
                    'short_code': short_code,
                    'expires_at': expires_str,
                    'inviter_name': inviter_name,
                })

        transaction.on_commit(_after_commit)

    return invitation, raw_token, link


def find_invitation_by_secret(token: Optional[str] = None, short_code: Optional[str] = None, queryset=None):
    """
    Busca una invitación por token en claro (vía hash SHA-256) o por código corto.
    Si solo se recibe `token` y tiene la forma de un código corto, se trata como tal.
    """
    qs = (
        queryset
        if queryset is not None
        else EmployeeInvitation.objects.select_related('company', 'company__category', 'invited_by')
    )
    token = (token or '').strip()
    code = EmployeeInvitation.normalize_short_code(short_code) if short_code else ''

    if token and not code and len(EmployeeInvitation.normalize_short_code(token)) == INVITATION_SHORT_CODE_LENGTH:
        code = EmployeeInvitation.normalize_short_code(token)
        token = ''

    if token:
        return qs.filter(token_hash=EmployeeInvitation.hash_token(token)).first()
    if code and len(code) == INVITATION_SHORT_CODE_LENGTH:
        return qs.filter(short_code=code).first()
    return None


def _mark_expired(invitation: EmployeeInvitation) -> None:
    EmployeeInvitation.objects.filter(pk=invitation.pk, status=InvitationStatus.PENDING).update(
        status=InvitationStatus.EXPIRED
    )
    invitation.status = InvitationStatus.EXPIRED


def build_invitation_preview(invitation: EmployeeInvitation) -> dict:
    """ Vista pública de la invitación con los datos del comercio y sucursales (no revela destinatario ni token_hash). """
    company = invitation.company
    invited_by = invitation.invited_by
    eff_status = invitation.effective_status
    company_img = _company_image_url(company)
    company_cat = company.category.name if (company and getattr(company, 'category_id', None) and company.category) else ''
    company_rif = (getattr(company, 'rif', '') or '').strip() if company else ''
    inviter_name = _user_display_name(invited_by) if invited_by else ''

    stores_payload = []
    for s in invitation.allowed_stores.select_related('location').all():
        loc = getattr(s, 'location', None)
        addr = (loc.name or '').strip() if loc else ''
        stores_payload.append({
            'id': str(s.id),
            'name': s.name,
            'address': addr,
        })

    return {
        'id': invitation.id,
        'company_id': str(company.id),
        'company_name': company.name,
        'company_image': company_img,
        'company_rif': company_rif,
        'company_category': company_cat,
        'company': {
            'id': str(company.id),
            'name': company.name,
            'image': company_img,
            'rif': company_rif,
            'category': company_cat,
        },
        'invited_by_name': inviter_name,
        'invited_by': {
            'id': str(invited_by.id),
            'first_name': (invited_by.first_name or '').strip(),
            'last_name': (invited_by.last_name or '').strip(),
            'full_name': inviter_name,
        } if invited_by else None,
        'role': int(invitation.role),
        'role_id': int(invitation.role),
        'role_slug': invitation.role_slug,
        'role_label': str(invitation.get_role_display()),
        'short_code': invitation.short_code,
        'status': int(eff_status),
        'status_label': str(InvitationStatus(eff_status).label),
        'is_valid': eff_status == InvitationStatus.PENDING,
        'is_targeted': bool(invitation.target_user_id or invitation.target_email),
        'requires_cedula_verified': invitation.role == EmployeeRole.DELIVERY,
        'stores': stores_payload,
        'expires_at': timezone.localtime(invitation.expires_at).isoformat() if invitation.expires_at else None,
    }


def preview_invitation(secret: str) -> dict:
    invitation = find_invitation_by_secret(token=secret)
    if invitation is None:
        raise WorkforceError("La invitación no existe o el enlace es inválido.", status_code=404, code='invitation_not_found')
    if invitation.status == InvitationStatus.PENDING and invitation.is_expired():
        _mark_expired(invitation)
    return build_invitation_preview(invitation)


def _invitation_targets_user(invitation: EmployeeInvitation, user) -> bool:
    """ True si la invitación está dirigida a este usuario (por cuenta o por correo). """
    if invitation.target_user_id and invitation.target_user_id == user.id:
        return True
    if invitation.target_email and user.email and invitation.target_email.strip().lower() == user.email.strip().lower():
        return True
    return False


def _status_error_for_invitation(invitation: EmployeeInvitation) -> Optional[WorkforceError]:
    status_value = invitation.effective_status
    if status_value == InvitationStatus.PENDING:
        return None
    messages = {
        InvitationStatus.ACCEPTED: ("Esta invitación ya fue utilizada.", 'invitation_used'),
        InvitationStatus.DECLINED: ("Esta invitación fue rechazada.", 'invitation_declined'),
        InvitationStatus.REVOKED: ("El comercio revocó esta invitación.", 'invitation_revoked'),
        InvitationStatus.EXPIRED: ("Esta invitación expiró. Pide al comercio una nueva.", 'invitation_expired'),
    }
    msg, code = messages.get(status_value, ("La invitación no es válida.", 'invitation_invalid'))
    return WorkforceError(msg, status_code=410, code=code)


def accept_invitation(user, token: Optional[str] = None, short_code: Optional[str] = None,
                      invitation_id=None) -> Employee:
    """
    Acepta una invitación de forma atómica (bloqueando la fila de la invitación) y crea o
    reactiva el registro `Employee` con su rol, permisos y sucursales.
    """
    if not token and not short_code and not invitation_id:
        raise WorkforceError("Debes enviar 'token' o 'short_code'.", code='secret_required')

    if invitation_id:
        inv_pk = _parse_int(invitation_id, 'invitation_id')
        invitation = EmployeeInvitation.objects.select_related('company').filter(pk=inv_pk).first()
        # Por ID solo se aceptan invitaciones dirigidas a este usuario
        if invitation is not None and not _invitation_targets_user(invitation, user):
            invitation = None
    else:
        invitation = find_invitation_by_secret(token=token, short_code=short_code)

    if invitation is None:
        raise WorkforceError("La invitación no existe o el código es inválido.", status_code=404, code='invitation_not_found')

    if invitation.status == InvitationStatus.PENDING and invitation.is_expired():
        _mark_expired(invitation)

    with transaction.atomic():
        invitation = (
            EmployeeInvitation.objects.select_for_update(of=('self',))
            .select_related('company')
            .get(pk=invitation.pk)
        )
        status_error = _status_error_for_invitation(invitation)
        if status_error is not None:
            raise status_error

        company = invitation.company
        if (invitation.target_user_id or invitation.target_email) and not _invitation_targets_user(invitation, user):
            raise WorkforceError("Esta invitación fue enviada a otra cuenta.", status_code=403, code='invitation_not_for_user')

        if company.owner_id == user.id:
            raise WorkforceError("No puedes ser trabajador de tu propio comercio.", status_code=403, code='owner_cannot_be_employee')

        if invitation.role == EmployeeRole.DELIVERY and not user.cedula_verified:
            raise WorkforceError(
                "Para trabajar como repartidor debes verificar tu identidad (cédula) en CartMaker.",
                status_code=403,
                code='cedula_not_verified',
            )

        employee = (
            Employee.objects.select_for_update(of=('self',))
            .filter(user=user, company=company)
            .first()
        )
        if employee is not None and employee.status == EmployeeStatus.ACTIVE:
            raise WorkforceError("Ya trabajas en este comercio.", status_code=409, code='already_employee')

        # Un trabajador suspendido o revocado no puede reincorporarse con un enlace abierto
        # (p. ej. un QR pensado para otra persona): necesita una invitación dirigida a su cuenta.
        if employee is not None and not _invitation_targets_user(invitation, user):
            raise WorkforceError(
                "Tu acceso a este comercio fue suspendido o finalizado. Pide al dueño una invitación dirigida a tu cuenta.",
                status_code=403,
                code='rehire_requires_targeted_invitation',
            )

        try:
            with transaction.atomic():
                if employee is None:
                    employee = Employee.objects.create(
                        user=user,
                        company=company,
                        role=invitation.role,
                        status=EmployeeStatus.ACTIVE,
                    )
                else:
                    employee.role = invitation.role
                    employee.status = EmployeeStatus.ACTIVE
                    employee.save(update_fields=['role', 'status', 'is_active'])
        except IntegrityError:
            raise WorkforceError("Ya trabajas en este comercio.", status_code=409, code='already_employee')

        stores = list(invitation.allowed_stores.filter(company=company, is_active=True))
        if not stores:
            stores = list(CompanyStore.objects.filter(company=company, is_active=True))
        _sync_employee_stores(employee, stores)

        now = timezone.now()
        invitation.status = InvitationStatus.ACCEPTED
        invitation.accepted_by = user
        invitation.accepted_at = now
        invitation.save(update_fields=['status', 'accepted_by', 'accepted_at'])

        invalidate_employee_cache(employee.id)

        owner_id = company.owner_id
        emp_id = employee.id
        worker_name = _user_display_name(user)
        role_label = str(employee.get_role_display())
        company_name = company.name

        def _after_commit():
            from .firebase_admin import NotificationManager
            invalidate_employee_cache(emp_id)
            NotificationManager.notify_workforce_event(
                user_id=owner_id,
                title="Nuevo trabajador en tu equipo",
                body=f"{worker_name} aceptó tu invitación y ya trabaja en {company_name} como {role_label}.",
                event_type='employee_joined',
                category=NotificationCategory.EMPLOYEE_UPDATE,
                section=NotificationSection.MERCHANT_EMPLOYEES,
                extra_data={'employee_id': emp_id, 'invitation_id': invitation.id},
            )

        transaction.on_commit(_after_commit)

    return employee


def decline_invitation(user, invitation_id) -> EmployeeInvitation:
    inv_pk = _parse_int(invitation_id, 'invitation_id')
    with transaction.atomic():
        invitation = (
            EmployeeInvitation.objects.select_for_update(of=('self',))
            .select_related('company')
            .filter(pk=inv_pk)
            .first()
        )
        if invitation is None or not _invitation_targets_user(invitation, user):
            raise WorkforceError("La invitación no existe.", status_code=404, code='invitation_not_found')
        status_error = _status_error_for_invitation(invitation)
        if status_error is not None:
            raise status_error

        invitation.status = InvitationStatus.DECLINED
        invitation.save(update_fields=['status'])

        owner_id = invitation.company.owner_id
        invited_name = _user_display_name(user)
        inv_id = invitation.id

        def _after_commit():
            from .firebase_admin import NotificationManager
            NotificationManager.notify_workforce_event(
                user_id=owner_id,
                title="Invitación rechazada",
                body=f"{invited_name} rechazó tu invitación para trabajar en tu comercio.",
                event_type='employee_invitation_declined',
                category=NotificationCategory.EMPLOYEE_UPDATE,
                section=NotificationSection.MERCHANT_EMPLOYEES,
                extra_data={'invitation_id': inv_id},
            )

        transaction.on_commit(_after_commit)
    return invitation


def revoke_invitation(owner, invitation_id) -> EmployeeInvitation:
    company = require_owned_company(owner)
    inv_pk = _parse_int(invitation_id, 'invitation_id')
    with transaction.atomic():
        invitation = (
            EmployeeInvitation.objects.select_for_update(of=('self',))
            .filter(pk=inv_pk, company=company)
            .first()
        )
        if invitation is None:
            raise WorkforceError("La invitación no existe.", status_code=404, code='invitation_not_found')
        if invitation.status != InvitationStatus.PENDING:
            raise WorkforceError("Solo puedes revocar invitaciones pendientes.", status_code=409, code='invitation_not_pending')
        invitation.status = InvitationStatus.REVOKED
        invitation.save(update_fields=['status'])
    return invitation


def list_company_invitations(owner, status_filter=None):
    company = require_owned_company(owner)
    qs = (
        EmployeeInvitation.objects.select_related('company', 'invited_by', 'target_user', 'accepted_by')
        .prefetch_related('allowed_stores')
        .filter(company=company)
    )
    if status_filter not in (None, ''):
        status_value = _parse_choice(
            status_filter, InvitationStatus,
            {'pending': 0, 'accepted': 1, 'declined': 2, 'revoked': 3, 'expired': 4},
            'status',
        )
        now = timezone.now()
        if status_value == InvitationStatus.PENDING:
            qs = qs.filter(status=InvitationStatus.PENDING, expires_at__gt=now)
        elif status_value == InvitationStatus.EXPIRED:
            qs = qs.filter(Q(status=InvitationStatus.EXPIRED) | Q(status=InvitationStatus.PENDING, expires_at__lte=now))
        else:
            qs = qs.filter(status=status_value)
    return qs.order_by('-created_at')


def list_my_invitations(user):
    """ Invitaciones PENDIENTES y vigentes dirigidas al usuario (por cuenta o por correo). """
    target_q = Q(target_user=user)
    if user.email:
        target_q |= Q(target_email=user.email.strip().lower())
    return (
        EmployeeInvitation.objects.select_related('company', 'invited_by', 'target_user', 'accepted_by')
        .prefetch_related('allowed_stores')
        .filter(target_q, status=InvitationStatus.PENDING, expires_at__gt=timezone.now())
        .exclude(company__owner=user)
        .order_by('-created_at')
    )


# =========================================================================
# 6. GESTIÓN DE TRABAJADORES (DUEÑO)
# =========================================================================
def list_company_employees(owner, include_revoked: bool = False):
    company = require_owned_company(owner)
    qs = (
        Employee.objects.select_related('user', 'company')
        .prefetch_related('employeestoreassignment_set__store')
        .filter(company=company)
        .exclude(user_id=company.owner_id)
    )
    if not include_revoked:
        qs = qs.exclude(status=EmployeeStatus.REVOKED)
    return qs.order_by('status', 'hired_at')


def get_company_employee(owner, employee_id) -> Employee:
    company = require_owned_company(owner)
    emp_pk = _parse_int(employee_id, 'employee_id')
    employee = (
        Employee.objects.select_related('user', 'company')
        .prefetch_related('employeestoreassignment_set__store')
        .filter(pk=emp_pk, company=company)
        .first()
    )
    if employee is None:
        raise WorkforceError("El trabajador no existe en tu comercio.", status_code=404, code='employee_not_found')
    return employee


def update_employee(owner, employee_id, data: dict) -> Employee:
    """
    Actualiza un trabajador (solo el dueño). Campos aceptados:
    role, vehicle_type, display_alias, store_ids, status ('active'|'suspended'|'revoked' o 0/1/2)
    o action ('suspend'|'reactivate'|'revoke').
    """
    company = require_owned_company(owner)
    emp_pk = _parse_int(employee_id, 'employee_id')
    data = data or {}

    with transaction.atomic():
        employee = (
            Employee.objects.select_for_update(of=('self',))
            .select_related('user', 'company')
            .filter(pk=emp_pk, company=company)
            .first()
        )
        if employee is None:
            raise WorkforceError("El trabajador no existe en tu comercio.", status_code=404, code='employee_not_found')

        old_status = employee.status
        old_role = employee.role
        update_fields = []

        # --- Estado (suspender / reactivar / revocar) ---
        new_status = None
        if data.get('action') not in (None, ''):
            action_slug = str(data.get('action')).strip().lower()
            if action_slug not in STATUS_ACTION_SLUGS:
                raise WorkforceError("La acción debe ser 'suspend', 'reactivate' o 'revoke'.", code='invalid_action')
            new_status = int(STATUS_ACTION_SLUGS[action_slug])
        elif data.get('status') not in (None, ''):
            new_status = _parse_choice(data.get('status'), EmployeeStatus, STATUS_SLUGS, 'status')

        if new_status is not None and new_status != old_status:
            if old_status == EmployeeStatus.REVOKED:
                raise WorkforceError(
                    "Este trabajador fue revocado. Para volver a contratarlo envíale una nueva invitación.",
                    status_code=409,
                    code='employee_revoked',
                )
            employee.status = new_status
            update_fields += ['status', 'is_active']

        # --- Rol ---
        if data.get('role') not in (None, ''):
            new_role = parse_role(data.get('role'))
            if new_role != old_role:
                if new_role == EmployeeRole.DELIVERY and not employee.user.cedula_verified:
                    raise WorkforceError(
                        "Este usuario debe verificar su identidad antes de trabajar como repartidor.",
                        code='cedula_not_verified',
                    )
                employee.role = new_role
                update_fields.append('role')

        # --- Vehículo ---
        if 'vehicle_type' in data:
            employee.vehicle_type = parse_vehicle_type(data.get('vehicle_type'))
            update_fields.append('vehicle_type')

        # --- Alias visible para el cliente ---
        if 'display_alias' in data:
            alias = str(data.get('display_alias') or '').strip()
            if len(alias) > 60:
                raise WorkforceError("El alias no puede superar los 60 caracteres.", code='invalid_alias')
            employee.display_alias = alias
            update_fields.append('display_alias')

        if update_fields:
            employee.save(update_fields=list(dict.fromkeys(update_fields)))

        # --- Sucursales ---
        store_ids = data.get('store_ids', data.get('allowed_store_ids'))
        if store_ids is not None:
            stores = _resolve_company_stores(company, store_ids, default_all=False)
            _sync_employee_stores(employee, stores)

        status_changed = employee.status != old_status
        role_changed = employee.role != old_role
        invalidate_employee_cache(employee.id)

        if status_changed and employee.status in (EmployeeStatus.SUSPENDED, EmployeeStatus.REVOKED):
            schedule_worker_revocation(
                employee,
                reason='suspended' if employee.status == EmployeeStatus.SUSPENDED else 'revoked',
            )
        elif role_changed and employee.status == EmployeeStatus.ACTIVE:
            # El token de trabajador lleva el rol: forzamos a la app a re-seleccionar el espacio
            schedule_worker_revocation(employee, reason='role_changed')
        else:
            emp_id_for_cache = employee.id
            transaction.on_commit(lambda: invalidate_employee_cache(emp_id_for_cache))

        if status_changed or role_changed:
            worker_user_id = employee.user_id
            company_name = company.name
            emp_id = employee.id
            if status_changed and employee.status == EmployeeStatus.SUSPENDED:
                title, body = "Acceso suspendido", f"{company_name} suspendió temporalmente tu acceso como trabajador."
            elif status_changed and employee.status == EmployeeStatus.REVOKED:
                title, body = "Acceso revocado", f"{company_name} revocó tu acceso como trabajador."
            elif status_changed and employee.status == EmployeeStatus.ACTIVE:
                title, body = "Acceso reactivado", f"{company_name} reactivó tu acceso como trabajador."
            else:
                title, body = "Tu rol cambió", f"Ahora trabajas en {company_name} como {employee.get_role_display()}."
            new_status_value = int(employee.status)
            new_role_slug = employee.role_slug

            def _after_commit():
                from .firebase_admin import NotificationManager
                NotificationManager.notify_workforce_event(
                    user_id=worker_user_id,
                    title=title,
                    body=body,
                    event_type='employee_status_changed',
                    category=NotificationCategory.EMPLOYEE_UPDATE,
                    section=NotificationSection.HOME,
                    extra_data={
                        'employee_id': emp_id,
                        'company_id': str(company.id),
                        'status': new_status_value,
                        'role': new_role_slug,
                    },
                )

            transaction.on_commit(_after_commit)

    return get_company_employee(owner, employee.id)


def leave_company(user, employee_id) -> Employee:
    """ El trabajador renuncia: su empleo pasa a REVOKED y se cierran sus sesiones de trabajador. """
    emp_pk = _parse_int(employee_id, 'employee_id')
    with transaction.atomic():
        employee = (
            Employee.objects.select_for_update(of=('self',))
            .select_related('company')
            .filter(pk=emp_pk, user=user)
            .first()
        )
        if employee is None:
            raise WorkforceError("No perteneces a este comercio.", status_code=404, code='employment_not_found')
        if employee.status == EmployeeStatus.REVOKED:
            raise WorkforceError("Ya no trabajas en este comercio.", status_code=409, code='employee_revoked')

        employee.status = EmployeeStatus.REVOKED
        employee.save(update_fields=['status', 'is_active'])
        schedule_worker_revocation(employee, reason='left')

        owner_id = employee.company.owner_id
        worker_name = _user_display_name(user)
        emp_id = employee.id

        def _after_commit():
            from .firebase_admin import NotificationManager
            NotificationManager.notify_workforce_event(
                user_id=owner_id,
                title="Un trabajador dejó tu equipo",
                body=f"{worker_name} dejó de trabajar en tu comercio.",
                event_type='employee_left',
                category=NotificationCategory.EMPLOYEE_UPDATE,
                section=NotificationSection.MERCHANT_EMPLOYEES,
                extra_data={'employee_id': emp_id},
            )

        transaction.on_commit(_after_commit)
    return employee
