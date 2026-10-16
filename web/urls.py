from django.urls import path
from . import views
from django.views.generic.base import RedirectView
from django.conf import settings

urlpatterns = [
    # 🌍 Zona Pública
    path('', views.landing_view, name='web_home'),
    path('presentacion/', views.pitch_deck_view, name='web_pitch_deck'),
    path('tienda/<uuid:company_id>/', views.public_storefront_view, name='public_storefront'),
    path('t/<uuid:company_id>/', views.public_storefront_view, name='public_storefront_short'),
    path('p/<uuid:item_id>/', views.public_product_redirect_view, name='public_product_link'),
    path('orden-express/<str:token>/', views.public_express_order_view, name='public_express_order'),
    path('tienda/<uuid:company_id>/handoff-cart/', views.create_web_cart_handoff_ajax, name='web_cart_handoff_ajax'),

    # 🔒 Zona de Autenticación (Compartida)
    path('auth', views.login_view),
    path('auth/login/', views.login_view, name='web_login'),
    path('auth/logout/', views.logout_view, name='web_logout'),
    
    # 🎧 Zona de Soporte
    path('support/dashboard/', views.dashboard_view, name='web_dashboard'),
    path('support/ticket/<int:ticket_id>/', views.support_agent_chat, name='support_agent_chat'),
    path('support/ticket/<int:ticket_id>/close/', views.close_ticket, name='close_ticket'),
    path('support/close-ticket/<int:ticket_id>/', views.close_ticket, name='close_ticket_alias'),
    
    # 💳 Zona de Pagos
    path('payments/dashboard/', views.payments_dashboard_view, name='web_payments_dashboard'),
    
    # Utilidades
    path('favicon.ico', RedirectView.as_view(url=settings.STATIC_URL + 'img/favicon.ico')),
]