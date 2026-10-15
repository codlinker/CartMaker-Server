import os
import secrets
from rest_framework.permissions import BasePermission
from api.models import CartMakerApiKey


class IsNodeMicroservice(BasePermission):
    """
    Permite el acceso al webhook interno del servidor de Chat (Node.js) si:
      1. Envía una CartMakerApiKey válida y activa con alcance 'chat' o 'all'
         (en X-Api-Key, X-CartMaker-Api-Key, X-Microservice-Token o Authorization).
      2. O envía el 'X-Microservice-Token' coincidente con DJANGO_SECRET_KEY.
    """

    def has_permission(self, request, view):
        if getattr(request, "has_valid_cartmaker_api_key", False):
            return True

        token_recibido = (
            request.headers.get("X-Microservice-Token")
            or request.headers.get("X-Api-Key")
            or request.headers.get("X-CartMaker-Api-Key")
            or ""
        ).strip()

        if token_recibido.startswith("cmk_live_"):
            return CartMakerApiKey.verify_key(token_recibido, required_scope="chat")

        token_real = os.environ.get("DJANGO_SECRET_KEY") or ""
        return bool(token_recibido and token_real and secrets.compare_digest(token_recibido, token_real))