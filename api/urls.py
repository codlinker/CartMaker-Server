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
router.register(r'products', ProductViewSet, basename='products')
router.register(r'inventory-items', InventoryItemViewSet, basename='inventory-items')
router.register(r'atlas', AtlasViewSet, basename='atlas')
router.register(r'search-engine', ProductSearchEngineViewSet, basename='search-engine')
router.register(r'cartmaker-map', CartMakerMapViewSet, basename='cartmaker_map')
router.register(r'client-company', ClientCompanyViewSet, basename="client_company")
router.register(r'universal-conversation', UniversalConversationViewSet, basename="universal_conversation")
router.register(r'logs', InteractionLogViewSet, basename="logs")
router.register(r'cart', CartViewSet, basename='cart')
router.register(r'orders', OrderViewSet, basename='orders')
router.register(r'story-video', CompanyVideoStoryViewSet, basename='story-video')
router.register(r'gamification', GamificationViewSet, basename="gamification")
router.register(r'analytics', AnalyticsViewSet, basename='analytics')

# --- DEFINICIÓN DE RUTAS (URLS) ---
urlpatterns = [
    # Rutas para la documentación de la API
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger_ui'),
    # Rutas para la obtencion de datos
    path('v1/cache/user', UserCacheAPI.as_view(), name="user_cache"),
    path('v1/cache/home', HomeCacheAPI.as_view(), name="home_cache"),
    path('v1/cache/search', SearchCacheAPI.as_view(), name="search_cache"),
    path('v1/cache/company', CompanyCacheAPI.as_view(), name='company_cache'),
    path('v1/cache/maps', GetMallsCache.as_view(), name='get_malls'),
    path('v1/cache/subscriptions', SubscriptionsCacheAPI.as_view(), name="subscriptions_cache"),
    path('v1/cache/system-config', SystemConfigCacheAPI.as_view(), name="system_config_cache"),
    path('v1/get-merchant-plans', GetMerchantPlans.as_view(), name="get_merchant_plans"),
    path('v1/get-atlas-plus-plan', GetAtlasPlusPlanDetails.as_view(), name='get_atlas_plus_plan'),
    path('v1/full-pay-subscription', FullPaySubscriptionWithWalletView.as_view(), name='full_pay_subscription'),
    path('v1/get-cartmaker-bank-accounts', GetCartMakerAccounts.as_view(), name='get_cartmaker_bank_accounts'),
    path('v1/get-stores-locations/', GetStoresLocations.as_view(), name='get_stores_locations'),
    path('v1/check-company-name-available/<str:name>/', CheckCompanyNameAvailableAPI.as_view(), name='check_company_name_available'),
    path('v1/create-company', CreateCompanyAPI.as_view(), name='create_company'),
    path('v1/update-company', UpdateCompanyAPI.as_view(), name="update_company"),
    path('v1/create-store', CreateStoreAPI.as_view(), name="create_store"),
    path('v1/update-store', UpdateStoreAPI.as_view(), name="update_store"),
    path('v1/delete-store/<uuid:store_id>/', UpdateStoreAPI.as_view(), name="delete_store"),
    path('v1/delete-store-contact-method/<int:method_id>/', DeleteStoreContactMethodAPI.as_view(), name='delete_contact_method'),
    path('v1/delete-store/<uuid:store_id>/', UpdateStoreAPI.as_view(), name="delete_store"),
    path('v1/get-company-products/<uuid:company_id>/', GetCompanyProducts.as_view(), name="get_company_products"),
    path('v1/get-store-inventory-items/<uuid:store_id>/', GetStoreInventoryItems.as_view(), name="get_store_inventory_items"),
    path('v1/get-company-sub-categories/<uuid:company_id>/', GetCompanySubCategories.as_view(), name="get_company_sub_categories"),
    path('v1/main-branch/', CompanyMainBranchViewSet.as_view(), name='main_branch'),
    # Rutas para manejo de pagos
    path('v1/upload-subscription-payment', UploadSubscriptionPayment.as_view(), name='upload_subscription_payment'),
    # Rutas para la autenticacion
    path('v1/regist-new-device', RegistDeviceView.as_view(), name="regist_new_device"),
    path('v1/token', CartMakerTokenView.as_view(), name='token_obtain_pair'),
    path('v1/biometric-login', BiometricLoginView.as_view(), name='biometric_login'),
    path('v1/token/refresh', TokenRefreshView.as_view(), name='token_refresh'),
    path('v1/register', RegisterView.as_view(), name="register"),
    path('v1/google/auth', GoogleLoginView.as_view(), name='google_login'),
    path('v1/google/regist', GoogleRegistView.as_view(), name='google_regist'),
    path('v1/google/get-client-id', GoogleClientId.as_view(), name='google_client_id'),
    path('v1/email/verify', VerifyEmailView.as_view(), name='verify_email'),
    path('v1/email/resend', ResendEmailView.as_view(), name='resend_email'),
    path('v1/verify-password', VerifyPasswordAPI.as_view(), name='verify_password'),
    # Rutas para la verificacion de usuarios
    path('v1/check-cedula/<str:cedula_number>/', CheckIfCedulaExists.as_view(), name='check-cedula-exists'),
    path('v1/verify-user', VerifyUser.as_view(), name='verify_user'),
    # CRUD de modelos (viewsets)
    path('v1/', include(router.urls)),
    # Vistas web
    path('', Home.as_view(), name="home"),
    # Rutas para testing
    path('test/send-notification', SendNotificationToUser.as_view(), name="send_notification"),
]