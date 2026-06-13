import os
from rest_framework.permissions import BasePermission

class IsNodeMicroservice(BasePermission):
    """
    Permite el acceso ÚNICAMENTE si la petición HTTP trae el header 
    'X-Microservice-Token' con la llave secreta del servidor.
    """
    def has_permission(self, request, view):
        # Capturamos el header que nos envía Node.js
        token_recibido = request.headers.get('X-Microservice-Token')
        
        # Lo comparamos con el secreto real en las variables de entorno
        token_real = os.environ.get('DJANGO_SECRET_KEY')
        
        # Si coinciden, pasa. Si no (o si viene vacío), da error 403 Forbidden.
        return token_recibido == token_real and token_real is not None