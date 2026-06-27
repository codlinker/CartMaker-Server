from django.urls import path
from . import views
from django.views.generic.base import RedirectView
from django.conf import settings

urlpatterns = [
    # 🌍 Zona Pública
    path('', views.landing_view, name='web_home'),
    
    # 🔒 Zona de Autenticación (Compartida)
    path('auth/login/', views.login_view, name='web_login'),
    path('auth/logout/', views.logout_view, name='web_logout'),
    
    # 🎧 Zona de Soporte
    path('support/dashboard/', views.dashboard_view, name='web_dashboard'),
    path('support/ticket/<int:ticket_id>/', views.support_agent_chat, name='support_agent_chat'),
    path('support/ticket/<int:ticket_id>/close/', views.close_ticket, name='close_ticket'),
    
    # 💳 Zona de Pagos
    path('payments/dashboard/', views.payments_dashboard_view, name='web_payments_dashboard'),
    
    # Utilidades
    path('favicon.ico', RedirectView.as_view(url=settings.STATIC_URL + 'img/favicon.ico')),
]