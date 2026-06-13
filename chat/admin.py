from django.contrib import admin
from .models import *
from unfold.admin import ModelAdmin

# Register your models here.

@admin.register(ChatMessage)
class NotificationAdmin(ModelAdmin):
    list_display = ('id', 'order', 'sender', 'text', 'message_type', 'status', 'created_at', 'media_url')