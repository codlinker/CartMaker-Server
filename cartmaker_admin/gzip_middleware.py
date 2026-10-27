"""
Compresión gzip selectiva: solo respuestas de texto (JSON, HTML, JS, CSS, XML, SVG).
`GZipMiddleware` de Django comprime cualquier cuerpo >= 200 bytes, incluidas imágenes/videos/PDF ya comprimidos,
lo que solo gasta CPU y batería sin reducir el tamaño. Si nginx ya comprime (Content-Encoding presente) no se recomprime.
"""
from django.middleware.gzip import GZipMiddleware

_COMPRESSIBLE_PREFIXES = (
    'application/json',
    'application/ld+json',
    'application/javascript',
    'application/xml',
    'application/xhtml+xml',
    'image/svg+xml',
    'text/',
)


class SelectiveGZipMiddleware(GZipMiddleware):
    def process_response(self, request, response):
        if response.status_code != 200:
            return response
        content_type = (response.headers.get('Content-Type') or '').split(';')[0].strip().lower()
        if not content_type.startswith(_COMPRESSIBLE_PREFIXES):
            return response
        return super().process_response(request, response)
