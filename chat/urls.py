from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ChatViewSet, ChatWebhookViewSet

router = DefaultRouter()
router.register(r'messages', ChatViewSet, basename='chat_messages')
router.register(r'webhook', ChatWebhookViewSet, basename='chat_webhook')

urlpatterns = [
    path('', include(router.urls)),
]