from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.db.models import Count, Avg, F, Q, OuterRef, Subquery
import json
import requests
from api.models import *
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.paginator import Paginator

# ==============================================================
# 🌍 VISTA PÚBLICA
# ==============================================================
def landing_view(request):
    """ Exclusivo para branding y descarga de la App """
    # Traemos los planes ordenados por precio
    plans = MerchantPlan.objects.all().order_by('price')
    return render(request, 'home.html', {'plans': plans})

@login_required(login_url='/support/login/')
@require_POST
def close_ticket(request, ticket_id):
    if not request.user.is_superuser:
        return redirect('web_home')
        
    ticket = get_object_or_404(SupportTicket, id=ticket_id)
    reason_id = request.POST.get('close_reason', 0) # Capturamos el select
    
    ticket.closed = True
    ticket.close_time = timezone.now()
    ticket.close_reason = int(reason_id)
    ticket.save(update_fields=['closed', 'close_time', 'close_reason'])
    
    # 💡 ALERTAMOS A NODE.JS EN TIEMPO REAL
    try:
        requests.post(
            "http://127.0.0.1:3000/internal/emit-ticket-closed",
            json={
                'ticket_id': str(ticket.id), 
                'reason': ticket.get_close_reason_display(),
                'client_id': str(ticket.client.id), # 💡 NUEVO
                'agent_id': str(ticket.agent.id)    # 💡 NUEVO
            },
            headers={'X-Microservice-Token': settings.SECRET_KEY},
            timeout=2
        )
    except Exception as e:
        print(f"Advertencia: No se pudo emitir alerta de cierre de ticket: {e}")
    
    messages.success(request, f"El ticket #{ticket.id} fue cerrado correctamente.")
    return redirect('web_dashboard')


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
    if not request.user.is_superuser:
        return redirect('web_home')

    # ==============================================================
    # 💡 LÓGICA DE ACTUALIZACIÓN DE PERFIL CON CLASE COS
    # ==============================================================
    if request.method == 'POST':
        if 'first_name' in request.POST and 'last_name' in request.POST:
            request.user.first_name = request.POST.get('first_name').strip()
            request.user.last_name = request.POST.get('last_name').strip()

            if 'profile_picture' in request.FILES:
                new_image = request.FILES['profile_picture']
                file_name = f"agent_{request.user.id}_{new_image.name}"
                
                # Asumiendo que storage_manager está importado o instanciado globalmente
                saved_path = storage_manager.save_file(
                    file_obj=new_image,
                    folder_path='profiles/avatars',
                    file_name=file_name
                )
                
                if saved_path:
                    request.user.profile_picture = saved_path

            request.user.save(update_fields=['first_name', 'last_name', 'profile_picture'])
            messages.success(request, "Tu perfil ha sido actualizado con éxito.")
            return redirect('web_dashboard')

    # ==============================================================
    # 📊 LÓGICA DE PANEL, PAGINACIÓN Y OPTIMIZACIÓN (N+1)
    # ==============================================================
    agent_tickets = SupportTicket.objects.filter(agent=request.user)
    
    # Subquery super optimizada para obtener el último mensaje sin colapsar la RAM
    last_msg_qs = SupportMessage.objects.filter(
        ticket=OuterRef('pk')
    ).order_by('-created_at')

    # Querysets Anotados
    active_tickets = agent_tickets.filter(closed=False)\
        .select_related('client')\
        .annotate(
            unread_agent=Count(
                'messages', 
                filter=Q(messages__status__lt=3) & ~Q(messages__sender=request.user)
            ),
            last_msg_text=Subquery(last_msg_qs.values('text')[:1]),
            last_msg_type=Subquery(last_msg_qs.values('message_type')[:1]),
            last_msg_sender_id=Subquery(last_msg_qs.values('sender_id')[:1]),
        )\
        .order_by('-creation')
        
    closed_tickets = agent_tickets.filter(closed=True)\
        .select_related('client')\
        .order_by('-close_time')

    # Configuración de Paginación (ajusta el 15 por 3 si sigues haciendo pruebas)
    items_per_page = 15
    active_paginator = Paginator(active_tickets, items_per_page)
    closed_paginator = Paginator(closed_tickets, items_per_page)

    # 🔄 Manejo de peticiones AJAX (Botones "Cargar más")
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        tab = request.GET.get('tab')
        page = request.GET.get('page', 1)

        if tab == 'active':
            page_obj = active_paginator.get_page(page)
            html = render_to_string('support/partials/active_tickets.html', {
                'active_tickets': page_obj, 
                'agent_id': str(request.user.id)
            })
        elif tab == 'closed':
            page_obj = closed_paginator.get_page(page)
            html = render_to_string('support/partials/closed_tickets.html', {
                'closed_tickets': page_obj
            })
        else:
            return JsonResponse({'error': 'Tab no válida'}, status=400)

        return JsonResponse({
            'html': html,
            'has_next': page_obj.has_next()
        })

    # Carga normal inicial (Página 1)
    active_page = active_paginator.get_page(1)
    closed_page = closed_paginator.get_page(1)

    # ==============================================================
    # 📈 ANALÍTICAS CON .order_by() CORREGIDO
    # ==============================================================
    topic_map = {0: 'Problema con Orden', 1: 'Reclamo sobre Tienda', 2: 'Problema con Cuenta', 3: 'Otro'}
    reason_map = {0: 'Resuelto con éxito', 1: 'No resuelto', 2: 'Spam / Inválido', 3: 'El cliente no responde'}

    topics_data = closed_tickets.order_by().values('topic').annotate(count=Count('id'))
    topics_labels = [topic_map.get(t['topic'], 'Otro') for t in topics_data]
    topics_values = [t['count'] for t in topics_data]

    reasons_data = closed_tickets.order_by().values('close_reason').annotate(count=Count('id'))
    reasons_labels = [reason_map.get(r['close_reason'], 'Desconocido') for r in reasons_data]
    reasons_values = [r['count'] for r in reasons_data]

    avg_time = closed_tickets.aggregate(avg_diff=Avg(F('close_time') - F('creation')))['avg_diff']
    avg_hours = round(avg_time.total_seconds() / 3600, 1) if avg_time else 0

    analytics = {
        'total_active': active_tickets.count(),
        'total_closed': closed_tickets.count(),
        'avg_hours': avg_hours,
        'topics': {'labels': topics_labels, 'data': topics_values},
        'reasons': {'labels': reasons_labels, 'data': reasons_values}
    }

    refresh = RefreshToken.for_user(request.user)
    
    return render(request, 'support/dashboard.html', {
        'active_tickets': active_page,  # Retornamos el objeto paginado
        'closed_tickets': closed_page,  # Retornamos el objeto paginado
        'analytics_json': json.dumps(analytics),
        'analytics_data': analytics,    # Pasamos el diccionario original para el filtro |json_script
        'agent_id': str(request.user.id),
        'jwt_token': str(refresh.access_token)
    })

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