from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from .views import CartMakerTokenView, RegisterView, Home
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

urlpatterns = [
    # Rutas para la documentación de la API
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    # Rutas de la api
    path('api/v1/token', CartMakerTokenView.as_view(), name='token_obtain_pair'),
    path('api/v1/token/refresh', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/v1/register', RegisterView.as_view(), name="register"),
    # Vistas web
    path('', Home.as_view(), name="home"),
]