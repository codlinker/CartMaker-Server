import os
import re
import secrets
from urllib.parse import urlparse
from django.conf import settings
from django.http import JsonResponse


class CartMakerClientGatekeeperMiddleware:
    """
    Middleware de blindaje perimetral y validación criptográfica de CartMakerApiKey.
    Garantiza que las peticiones HTTP hacia el backend (/api/ y /chat/) provengan
    exclusivamente de clientes autorizados con una API Key activa y válida en base de datos:
      1. Aplicación móvil oficial de CartMaker (Flutter) enviando su CartMakerApiKey.
      2. Servidor de Chat / Microservicio Node.js enviando su CartMakerApiKey (o X-Microservice-Token).
      3. Portal Web oficial de CartMaker (protegido por ALLOWED_HOSTS / CSRF_TRUSTED_ORIGINS).
    """

    API_KEY_REGEX = re.compile(r"(cmk_live_[a-f0-9]{12}_[A-Za-z0-9_-]{20,})")

    # Herramientas de scraping y bots automatizados bloqueados en producción sobre /api/ y /chat/
    BLOCKED_AUTOMATION_AGENTS = (
        "python-requests",
        "python-urllib",
        "scrapy",
        "curl/",
        "wget/",
        "libwww-perl",
        "go-http-client",
        "java/",
        "httpclient",
        "sqlmap",
        "nikto",
        "nmap",
        "masscan",
        "zgrab",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def _is_trusted_host(self, hostname: str) -> bool:
        if not hostname:
            return False
        hostname = hostname.lower().strip()
        allowed_hosts = getattr(settings, "CARTMAKER_TRUSTED_HOSTS", set())
        root_domain = getattr(settings, "CARTMAKER_ROOT_DOMAIN", "cartmaker.app")

        if hostname in allowed_hosts:
            return True
        if root_domain and hostname.endswith(f".{root_domain}"):
            return True
        return False

    def _extract_api_key_and_sanitize_auth(self, request) -> str:
        """
        Extrae la CartMakerApiKey ('cmk_live_...') desde las cabeceras de autorización:
          - X-Api-Key / X-CartMaker-Api-Key / X-CartMaker-App-Key / Api-Key
          - X-Microservice-Token (si utiliza formato cmk_live_...)
          - Authorization (ej. 'Authorization: Api-Key cmk_live_...', 'Authorization: Bearer cmk_live_...',
            o combinado 'Authorization: Bearer <jwt>, Api-Key cmk_live_...')
        Si la API Key venía dentro de 'Authorization', limpia request.META['HTTP_AUTHORIZATION']
        para que SimpleJWT procese únicamente el JWT del usuario sin colisionar.
        """
        # 1. Cabeceras dedicadas (recomendadas cuando coexisten con Authorization: Bearer <JWT>)
        for header_name in (
            "X-Api-Key",
            "X-CartMaker-Api-Key",
            "X-CartMaker-App-Key",
            "Api-Key",
        ):
            raw_val = (request.headers.get(header_name) or "").strip()
            if raw_val:
                match = self.API_KEY_REGEX.search(raw_val)
                if match:
                    return match.group(1)
                return raw_val

        # 2. Cabecera X-Microservice-Token si contiene una CartMakerApiKey
        ms_val = (request.headers.get("X-Microservice-Token") or "").strip()
        if ms_val.startswith("cmk_live_"):
            return ms_val

        # 3. Cabecera estándar Authorization
        auth_header = (request.META.get("HTTP_AUTHORIZATION") or "").strip()
        if auth_header and "cmk_live_" in auth_header:
            match = self.API_KEY_REGEX.search(auth_header)
            if match:
                extracted_key = match.group(1)
                # Limpiamos el segmento que contiene cmk_live_ de HTTP_AUTHORIZATION
                # para que SimpleJWT no intente decodificar la API Key como si fuera un JWT
                parts = [p.strip() for p in auth_header.split(",") if p.strip()]
                remaining_parts = [p for p in parts if extracted_key not in p]

                if remaining_parts:
                    cleaned_auth = ", ".join(remaining_parts)
                else:
                    # Por si se envió en espacio simple: "Bearer <jwt> cmk_live_..."
                    cleaned_auth = re.sub(
                        r"(?:Api-Key|ApiKey|Bearer|Key)?\s*" + re.escape(extracted_key),
                        "",
                        auth_header,
                        flags=re.IGNORECASE,
                    ).strip(" ,")

                if cleaned_auth:
                    request.META["HTTP_AUTHORIZATION"] = cleaned_auth
                else:
                    request.META.pop("HTTP_AUTHORIZATION", None)

                # Refrescamos la propiedad cacheada request.headers de Django si ya fue leída
                request.__dict__.pop("headers", None)
                return extracted_key

        return ""

    def _is_authenticated_web_staff_bypass(self, request, path: str) -> bool:
        """
        Permite que el personal de soporte/admin autenticado por sesión en el portal web
        de CartMaker use la consola web de soporte (/chat/support/...) y Swagger (/api/docs/).
        """
        user = getattr(request, "user", None)
        if not (user and user.is_authenticated):
            return False

        is_staff_or_support = (
            user.is_superuser
            or user.is_staff
            or getattr(user, "can_check_support", False)
        )
        if not is_staff_or_support:
            return False

        if path.startswith("/api/docs") or path.startswith("/api/schema") or path.startswith("/chat/support/"):
            return True

        return False

    def __call__(self, request):
        path = request.path_info or ""
        is_api_or_chat = path.startswith("/api/") or path.startswith("/chat/")

        # 1. Validación estricta de cabecera Origin (Bloquea cualquier sitio web externo)
        origin = request.headers.get("Origin")
        if origin and origin != "null":
            parsed_origin = urlparse(origin)
            origin_host = (parsed_origin.hostname or "").lower()
            if not self._is_trusted_host(origin_host):
                return JsonResponse(
                    {
                        "error": "Acceso denegado: Origen web no autorizado por CartMaker.",
                        "code": "untrusted_origin",
                    },
                    status=403,
                )

        # 2. Validación de cabecera Referer en rutas de API y Chat
        referer = request.headers.get("Referer")
        if is_api_or_chat and referer:
            parsed_referer = urlparse(referer)
            referer_host = (parsed_referer.hostname or "").lower()
            is_google_oauth = referer_host.endswith("accounts.google.com")
            if referer_host and not is_google_oauth and not self._is_trusted_host(referer_host):
                return JsonResponse(
                    {
                        "error": "Acceso denegado: Referencia externa no autorizada.",
                        "code": "untrusted_referer",
                    },
                    status=403,
                )

        # 3. Verificación obligatoria de CartMakerApiKey en todos los endpoints de /api/ y /chat/
        if is_api_or_chat:
            # En producción (DEBUG=False), bloquea de inmediato agentes de scraping conocidos
            if not settings.DEBUG:
                user_agent = (request.headers.get("User-Agent") or "").lower().strip()
                if not user_agent or any(bot in user_agent for bot in self.BLOCKED_AUTOMATION_AGENTS):
                    return JsonResponse(
                        {
                            "error": "Acceso restringido exclusivamente a la App y servicios oficiales de CartMaker.",
                            "code": "unauthorized_client_agent",
                        },
                        status=403,
                    )

            required_scope = "chat" if path.startswith("/chat/") else "api"
            raw_api_key = self._extract_api_key_and_sanitize_auth(request)

            # Importación diferida para evitar referencias circulares en el arranque de Django
            from api.models import CartMakerApiKey

            is_valid_api_key = False
            if raw_api_key:
                is_valid_api_key = CartMakerApiKey.verify_key(
                    raw_key=raw_api_key,
                    required_scope=required_scope,
                )

            if is_valid_api_key:
                request.has_valid_cartmaker_api_key = True
                return self.get_response(request)

            # Respaldo de compatibilidad para comunicación interna de Node.js en /chat/webhook/
            if path.startswith("/chat/webhook/"):
                ms_token = request.headers.get("X-Microservice-Token") or ""
                django_secret = os.environ.get("DJANGO_SECRET_KEY") or ""
                if ms_token and django_secret and secrets.compare_digest(ms_token, django_secret):
                    request.has_valid_cartmaker_api_key = True
                    return self.get_response(request)

            # Respaldo para consola web interna de Soporte / Swagger usada por Staff autenticado
            if self._is_authenticated_web_staff_bypass(request, path):
                return self.get_response(request)

            # Si no envió API Key o es inválida/revocada -> Rechazo inmediato
            if not raw_api_key:
                return JsonResponse(
                    {
                        "error": "Acceso denegado: Se requiere una CartMaker API Key válida en los headers de autorización.",
                        "code": "missing_api_key",
                    },
                    status=401,
                )

            return JsonResponse(
                {
                    "error": "Acceso denegado: La CartMaker API Key proporcionada es inválida, expiró o fue revocada.",
                    "code": "invalid_api_key",
                },
                status=403,
            )

        return self.get_response(request)

