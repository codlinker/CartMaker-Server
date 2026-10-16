from rest_framework.permissions import BasePermission, SAFE_METHODS
from api.models import Company, CompanyStore


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
    como a los operadores asignados a la sucursal (CompanyStore.operators).
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
        return store.operators.filter(id=request.user.id).exists()


class IsOrderParticipant(BasePermission):
    """
    Garantiza que únicamente el comprador (Order.client) o el propietario/operador
    del comercio receptor (Order.store.company.owner) puedan interactuar con una orden.
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
            if store.operators.filter(id=request.user.id).exists():
                return True
        return False
