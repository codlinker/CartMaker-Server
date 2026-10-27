"""
Middleware que rastrea los archivos guardados en S3/disco durante cada petición HTTP.
Si la petición termina rechazada por moderación de contenido (ContentModerationError), el rastro permite
borrar los archivos que ya se habían subido (ej. la 1.ª foto cuando la 2.ª es rechazada) y evitar huérfanos.
"""
from api.cos import begin_request_file_tracking, end_request_file_tracking


class RequestFileTrackingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = begin_request_file_tracking()
        try:
            return self.get_response(request)
        finally:
            end_request_file_tracking(token)
