from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from api.models import SupportTicket
from rest_framework_simplejwt.tokens import RefreshToken

# ==============================================================
# 🌍 VISTA PÚBLICA
# ==============================================================
def landing_view(request):
    """ Exclusivo para branding y descarga de la App """
    return render(request, 'home.html')


# ==============================================================
# 🔒 VISTAS PRIVADAS (SOPORTE)
# ==============================================================
def login_view(request):
    # Si ya está logueado y es admin, va al dashboard
    if request.user.is_authenticated and request.user.is_superuser:
        return redirect('web_dashboard')
        
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            
            # 💡 FILTRO ESTRICTO: Solo superusuarios entran por la web
            if user.is_superuser:
                login(request, user)
                return redirect('web_dashboard')
            else:
                messages.error(request, "Acceso denegado. Solo personal autorizado de CartMaker.")
        else:
            messages.error(request, "Credenciales inválidas.")
    else:
        form = AuthenticationForm()
        
    return render(request, 'auth/login.html', {'form': form})

@login_required(login_url='/support/login/')
@require_POST
def logout_view(request):
    logout(request)
    return redirect('web_login')

@login_required(login_url='/support/login/')
def dashboard_view(request):
    # Bloqueo adicional por si un usuario normal llega a esta URL directamente
    if not request.user.is_superuser:
        return redirect('web_home')
        
    active_tickets = SupportTicket.objects.filter(closed=False).select_related('client').order_by('-creation')
    return render(request, 'support/dashboard.html', {'active_tickets': active_tickets})

@login_required(login_url='/support/login/')
def support_agent_chat(request, ticket_id):
    if not request.user.is_superuser:
        return redirect('web_home')
        
    ticket = get_object_or_404(SupportTicket, id=ticket_id)
    refresh = RefreshToken.for_user(request.user)
    return render(request, 'support/support_chat.html', {
        'ticket': ticket,
        'agent_id': str(request.user.id),
        'jwt_token': str(refresh.access_token)
    })