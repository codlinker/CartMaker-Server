from django.urls import path
from . import views

urlpatterns = [
    # 🌍 Zona Pública
    path('', views.landing_view, name='web_home'),
    # 🔒 Zona Privada (Agentes)
    path('support/', views.login_view, name='web_login'),
    path('support/logout/', views.logout_view, name='web_logout'),
    path('support/dashboard/', views.dashboard_view, name='web_dashboard'),
    path('support/ticket/<int:ticket_id>/', views.support_agent_chat, name='support_agent_chat'),
]