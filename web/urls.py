from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from .views import *
from rest_framework_simplejwt.views import (
    TokenRefreshView,
)
from rest_framework.routers import DefaultRouter
from django.conf import settings
from django.conf.urls.static import static

router = DefaultRouter()
router.register(r'locations', ClientLocationViewSet, basename='client-locations')
router.register(r'user', UserViewSet, basename='user')
router.register(r'client-contact-methods', ClientContactMethodViewSet, basename='client-contact-methods')
router.register(r'notifications', NotificationViewSet, basename='notifications')

# --- DEFINICIÓN DE RUTAS (URLS) ---
urlpatterns = [
    # Rutas para la documentación de la API
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger_ui'),
    # Rutas para la obtencion de datos
    path('api/v1/cache/user', UserCacheAPI.as_view(), name="user_cache"),
    path('api/v1/cache/home', HomeCacheAPI.as_view(), name="home_cache"),
    path('api/v1/cache/subscriptions', SubscriptionsCacheAPI.as_view(), name="subscriptions_cache"),
    path('api/v1/get-merchant-plans', GetMerchantPlans.as_view(), name="get_merchant_plans"),
    path('api/v1/full-pay-subscription', FullPaySubscriptionWithWalletView.as_view(), name='full_pay_subscription'),
    path('api/v1/get-cartmaker-bank-accounts', GetCartMakerAccounts.as_view(), name='get_cartmaker_bank_accounts'),
    # Rutas para manejo de pagos
    path('api/v1/upload-subscription-payment', UploadSubscriptionPayment.as_view(), name='upload_subscription_payment'),
    # Rutas para la autenticacion
    path('api/v1/regist-new-device', RegistDeviceView.as_view(), name="regist_new_device"),
    path('api/v1/token', CartMakerTokenView.as_view(), name='token_obtain_pair'),
    path('api/v1/biometric-login', BiometricLoginView.as_view(), name='biometric_login'),
    path('api/v1/token/refresh', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/v1/register', RegisterView.as_view(), name="register"),
    path('api/v1/google/auth', GoogleLoginView.as_view(), name='google_login'),
    path('api/v1/google/regist', GoogleRegistView.as_view(), name='google_regist'),
    path('api/v1/google/get-client-id', GoogleClientId.as_view(), name='google_client_id'),
    path('api/v1/email/verify', VerifyEmailView.as_view(), name='verify_email'),
    path('api/v1/email/resend', ResendEmailView.as_view(), name='resend_email'),
    path('api/v1/verify-password', VerifyPasswordAPI.as_view(), name='verify_password'),
    # Rutas para la verificacion de usuarios
    path('api/v1/check-cedula/<str:cedula_number>/', CheckIfCedulaExists.as_view(), name='check-cedula-exists'),
    path('api/v1/verify-user', VerifyUser.as_view(), name='verify_user'),
    # CRUD de modelos (viewsets)
    path('api/v1/', include(router.urls)),
    # Vistas web
    path('', Home.as_view(), name="home"),
    # Rutas para testing
    path('test/send-notification', SendNotificationToUser.as_view(), name="send_notification"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)