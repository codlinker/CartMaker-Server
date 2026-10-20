from rest_framework.permissions import BasePermission, SAFE_METHODS
from api.models import Company, CompanyStore
from api.core.workforce import (
    CTX_CLAIM,
    CTX_PERSONAL,
    CTX_WORKER,
    EMP_ID_CLAIM,
    get_employee_state,
    user_works_at_store,
)


def get_token_claim(request, claim: str, default=None):
    """
    Lee un claim del JWT ya validado (`request.auth`, AccessToken de SimpleJWT).
    Retorna `default` si no hay token o si el claim no existe.
    """
    auth = getattr(request, 'auth', None)
    if auth is None:
        return default
    try:
        return auth.get(claim, default)
    except AttributeError:
        if isinstance(auth, dict):
            return auth.get(claim, default)
        return default


def get_request_ctx(request) -> str:
    """
    Contexto de sesión del request. Los tokens emitidos antes del sistema de trabajadores
    no traen `ctx`, por lo que se asumen como cuenta personal (compatibilidad hacia atrás).
    """
    ctx = get_token_claim(request, CTX_CLAIM, None)
    return str(ctx) if ctx else CTX_PERSONAL


class IsCompanyOwner(BasePermission):
    """
    Verifica que el usuario autenticado posea una Company activa y,
    a nivel de objeto, sea el propietario directo del recurso comercial.
    """
    message = "No tienes permisos sobre este comercio."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        return Company.objects.filter(owner=request.user).exists()

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        if hasattr(obj, 'owner_id'):
            return obj.owner_id == request.user.id
        if hasattr(obj, 'company'):
            return obj.company.owner_id == request.user.id
        if hasattr(obj, 'store') and hasattr(obj.store, 'company'):
            return obj.store.company.owner_id == request.user.id
        return False


class IsStoreOperatorOrOwner(BasePermission):
    """
    Permite operaciones sobre sucursales o inventario tanto al dueño de la Company
    como a los trabajadores ACTIVOS asignados a la sucursal
    (EmployeeStoreAssignment o EmployeePermission.allowed_stores).
    """
    message = "No tienes permisos operativos sobre esta sucursal."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        store = None
        if isinstance(obj, CompanyStore):
            store = obj
        elif hasattr(obj, 'store'):
            store = obj.store

        if store is None:
            return False

        if store.company.owner_id == request.user.id:
            return True
        return user_works_at_store(request.user, store)


class IsOrderParticipant(BasePermission):
    """
    Garantiza que únicamente el comprador (Order.client) o el propietario/trabajador asignado
    del comercio receptor (Order.store.company.owner / EmployeeStoreAssignment) puedan interactuar con una orden.
    """
    message = "No eres participante autorizado de esta orden."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        if getattr(obj, 'client_id', None) == request.user.id:
            return True
        store = getattr(obj, 'store', None)
        if store is not None:
            if store.company.owner_id == request.user.id:
                return True
            if user_works_at_store(request.user, store):
                return True
        return False


class IsPersonalContext(BasePermission):
    """
    Exige un token de la cuenta personal (ctx='personal' o sin ctx).
    Con un token de trabajador no se puede comprar, ni gastar la billetera, ni ver órdenes personales.
    """
    message = "Esta acción solo está disponible desde tu cuenta personal. Cambia de espacio de trabajo para continuar."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return get_request_ctx(request) == CTX_PERSONAL


class IsWorkerContext(BasePermission):
    """
    Exige un token de trabajador (ctx='worker') cuyo empleo siga ACTIVO.
    El estado se valida contra Redis (`emp:active:<emp_id>`, TTL 5 min) con respaldo en la BD,
    así una suspensión o revocación surte efecto de inmediato aunque el JWT siga vigente.

    `required_roles` (slugs: 'assistant', 'delivery') restringe el rol vigente del trabajador.
    Si la validación pasa, se exponen `request.worker_employee_id` y `request.worker_company_id`.
    """
    required_roles = None
    message = "Esta acción requiere iniciar sesión como trabajador del comercio."

    @classmethod
    def for_roles(cls, *roles):
        """ Crea una subclase que exige alguno de los roles indicados (ej. IsWorkerContext.for_roles('delivery')). """
        return type(f"IsWorkerContext_{'_'.join(roles)}", (cls,), {'required_roles': tuple(roles)})

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if get_request_ctx(request) != CTX_WORKER:
            return False

        emp_id = get_token_claim(request, EMP_ID_CLAIM, None)
        if not emp_id:
            return False

        state = get_employee_state(emp_id)
        if not state.get('active') or str(state.get('user_id')) != str(request.user.id):
            self.message = "Tu acceso como trabajador fue suspendido o revocado."
            return False

        if self.required_roles and state.get('role') not in self.required_roles:
            self.message = "Tu rol en este comercio no permite realizar esta acción."
            return False

        request.worker_employee_id = int(emp_id)
        request.worker_company_id = state.get('company_id')
        return True


class IsDeliveryWorker(IsWorkerContext):
    """ Trabajador activo con rol de repartidor. """
    required_roles = ('delivery',)
    message = "Esta acción requiere iniciar sesión como repartidor del comercio."
