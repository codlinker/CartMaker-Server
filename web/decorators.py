from functools import wraps
from urllib.parse import quote
from django.shortcuts import redirect
from django.urls import reverse

def payments_access_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated:
            # Pasan superusuarios O usuarios con permiso de pagos
            if request.user.is_superuser or getattr(request.user, 'can_check_payments', False):
                return view_func(request, *args, **kwargs)
            return redirect('web_home')
        return redirect(f"{reverse('web_login')}?next={quote(request.get_full_path())}")
    return _wrapped_view

def support_access_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated:
            # Pasan superusuarios O usuarios con permiso de soporte
            if request.user.is_superuser or getattr(request.user, 'can_check_support', False):
                return view_func(request, *args, **kwargs)
            return redirect('web_home')
        return redirect(f"{reverse('web_login')}?next={quote(request.get_full_path())}")
    return _wrapped_view