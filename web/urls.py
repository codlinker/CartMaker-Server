from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from .views import CartMakerTokenView, RegisterView, Home, GoogleLoginView, GoogleClientId,\
VerifyEmailView, ResendEmailView, ClientLocationViewSet
from rest_framework_simplejwt.views import (
    TokenRefreshView,
)
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'locations', ClientLocationViewSet, basename='client-location')

# --- DEFINICIÓN DE RUTAS (URLS) ---
urlpatterns = [
    # Rutas para la documentación de la API
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    # Autenticacion
    path('api/v1/token', CartMakerTokenView.as_view(), name='token_obtain_pair'),
    path('api/v1/token/refresh', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/v1/register', RegisterView.as_view(), name="register"),
    path('api/v1/google/auth', GoogleLoginView.as_view(), name='google_login'),
    path('api/v1/google/get-client-id', GoogleClientId.as_view(), name='google_client_id'),
    path('api/v1/email/verify', VerifyEmailView.as_view(), name='verify_email'),
    path('api/v1/email/resend', ResendEmailView.as_view(), name='resend_email'),
    # CRUD de modelos (viewsets)
    path('api/v1/', include(router.urls)),
    # Vistas web
    path('', Home.as_view(), name="home"),
]