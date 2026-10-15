from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Avg, F, Q, OuterRef, Subquery
import json
import requests
from api.models import *
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.paginator import Paginator
from .decorators import *
from django.conf import settings
from django.utils.http import url_has_allowed_host_and_scheme

ALLOWED_AVATAR_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp', 'heic'}
MAX_AVATAR_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

# ==============================================================
# 🔒 VISTAS DE AUTENTICACIÓN (COMPARTIDAS)
# ==============================================================
def login_view(request):
    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url and not url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        next_url = None

    # 1. Si ya está logueado, lo enviamos a su área de trabajo
    if request.user.is_authenticated:
        if next_url:
            return redirect(next_url)
        elif getattr(request.user, 'can_check_support', False) or request.user.is_superuser:
            return redirect('web_dashboard')
        elif getattr(request.user, 'can_check_payments', False):
            return redirect('web_payments_dashboard')
        else:
            logout(request)
            messages.error(request, "Tu cuenta no posee permisos operativos para acceder a la consola web.")
            return redirect('web_login')

    # 2. Procesamiento del Formulario
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            
            is_authorized = (
                user.is_superuser or 
                getattr(user, 'can_check_support', False) or 
                getattr(user, 'can_check_payments', False)
            )
            
            if is_authorized:
                login(request, user)
                if next_url:
                    return redirect(next_url)
                elif getattr(user, 'can_check_support', False) or user.is_superuser:
                    return redirect('web_dashboard')
                elif getattr(user, 'can_check_payments', False):
                    return redirect('web_payments_dashboard')
            else:
                messages.error(request, "Acceso restringido. Consola exclusiva para el equipo operativo de CartMaker.")
        else:
            messages.error(request, "Credenciales inválidas. Verifica tu correo corporativo y contraseña.")
    else:
        form = AuthenticationForm()
        
    return render(request, 'auth/login.html', {'form': form})

@login_required(login_url='/auth/login/')
@require_POST
def logout_view(request):
    logout(request)
    return redirect('web_login')

# ==============================================================
# 💳 VISTAS PRIVADAS (PAGOS)
# ==============================================================
@login_required(login_url='/auth/login/')
@payments_access_required
def payments_dashboard_view(request):
    """
    Dashboard unificado para la conciliación y aprobación de pagos en CartMaker.
    """
    # ==============================================================
    # 🔄 LÓGICA DE RECARGA DE PANELES VIA AJAX (GET)
    # ==============================================================
    if request.method == 'GET' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        target_deck = request.GET.get('deck')
        
        if target_deck == 'merchant':
            merchant_pending = MerchantPlanPayment.objects.filter(status=0).select_related('subscription__merchant', 'subscription__plan', 'target_plan').order_by('-creation')
            merchant_history = MerchantPlanPayment.objects.filter(status__in=[1, 2]).select_related('subscription__merchant', 'subscription__plan', 'target_plan').order_by('-verified_at')[:15]
            
            html = render_to_string('support/partials/merchant_deck_content.html', {
                'merchant_pending': merchant_pending,
                'merchant_history': merchant_history
            })
            return JsonResponse({'success': True, 'html': html, 'pending_count': merchant_pending.count()})
            
        elif target_deck == 'atlas':
            atlas_pending = AtlasPlusPlanPayment.objects.filter(status=0).select_related('plan__user').order_by('-creation')
            atlas_history = AtlasPlusPlanPayment.objects.filter(status__in=[1, 2]).select_related('plan__user').order_by('-verified_at')[:15]
            
            html = render_to_string('support/partials/atlas_deck_content.html', {
                'atlas_pending': atlas_pending,
                'atlas_history': atlas_history
            })
            return JsonResponse({'success': True, 'html': html, 'pending_count': atlas_pending.count()})
    # ==============================================================
    # ⚡ PROCESAMIENTO DE ACCIONES VIA AJAX (POST)
    # ==============================================================
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            payment_type = data.get('payment_type') # 'merchant' o 'atlas'
            payment_id = data.get('payment_id')
            new_status = data.get('status')         # 1 = APPROVED, 2 = REJECTED
            reason_id = data.get('rejection_reason', None)

            if not payment_id or new_status is None:
                return JsonResponse({'success': False, 'error': 'Parámetros obligatorios ausentes.'}, status=400)

            if int(new_status) not in (1, 2):
                return JsonResponse({'success': False, 'error': 'Estado de pago inválido.'}, status=400)

            with transaction.atomic():
                # Selección de modelo con bloqueo de fila (select_for_update) para impedir doble aprobación simultánea
                if payment_type == 'merchant':
                    payment = get_object_or_404(MerchantPlanPayment.objects.select_for_update(), pk=payment_id)
                elif payment_type == 'atlas':
                    payment = get_object_or_404(AtlasPlusPlanPayment.objects.select_for_update(), pk=payment_id)
                else:
                    return JsonResponse({'success': False, 'error': 'Módulo de pago no identificado.'}, status=400)

                # Forzar transiciones de estado válidas basándose en el Enum real (0 = PENDING)
                if payment.status != 0:
                    return JsonResponse({'success': False, 'error': 'Este pago ya fue procesado previamente.'}, status=400)

                payment.status = int(new_status)

                # Si la acción es rechazar (status = 2), inyectamos la causa tipificada
                if int(new_status) == 2:
                    if not reason_id:
                        return JsonResponse({'success': False, 'error': 'Es obligatorio seleccionar un motivo de rechazo.'}, status=400)
                    payment.rejection_reason = int(reason_id)

                # full_clean() disparará las validaciones del modelo y clean() asociados
                payment.full_clean()
                payment.save() # Ejecuta el pre_save de tus signals asincrónicas de billetera y notificaciones

            return JsonResponse({
                'success': True,
                'message': f'El pago fue {"aprobado" if int(new_status) == 1 else "rechazado"} correctamente.'
            })

        except ValidationError as e:
            return JsonResponse({'success': False, 'error': str(e.message_dict)}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Fallo crítico: {str(e)}'}, status=500)

    # ==============================================================
    # 📊 CARGA OPTIMIZADA DE TABLEROS (GET) - ANTI N+1
    # ==============================================================
    # Filtro: status=0 (PENDING)
    merchant_pending = MerchantPlanPayment.objects.filter(status=0) \
        .select_related('subscription__merchant', 'subscription__plan', 'target_plan') \
        .order_by('-creation')

    atlas_pending = AtlasPlusPlanPayment.objects.filter(status=0) \
        .select_related('plan__user') \
        .order_by('-creation')

    # Historial reciente de transiciones resueltas (status 1 o 2)
    merchant_history = MerchantPlanPayment.objects.filter(status__in=[1, 2]) \
        .select_related('subscription__merchant', 'subscription__plan', 'target_plan') \
        .order_by('-verified_at')[:15]

    atlas_history = AtlasPlusPlanPayment.objects.filter(status__in=[1, 2]) \
        .select_related('plan__user') \
        .order_by('-verified_at')[:15]

    # Reconstrucción limpia de los Enums estructurales para consumo del Front-End sin romper traducciones
    rejection_choices = [
        {'id': int(choice[0]), 'label': str(choice[1])} 
        for choice in RejectionReason.choices
    ]

    context = {
        'merchant_pending': merchant_pending,
        'atlas_pending': atlas_pending,
        'merchant_history': merchant_history,
        'atlas_history': atlas_history,
        'rejection_choices': rejection_choices, 
        'rejection_choices_json': json.dumps(rejection_choices),
    }

    return render(request, 'support/payments_dashboard.html', context)


# ==============================================================
# 🎧 VISTAS PRIVADAS (SOPORTE)
# ==============================================================
@login_required(login_url='/auth/login/')
@support_access_required
def dashboard_view(request):
    # ==============================================================
    # 💡 LÓGICA DE ACTUALIZACIÓN DE PERFIL CON CLASE COS
    # ==============================================================
    if request.method == 'POST':
        if 'first_name' in request.POST and 'last_name' in request.POST:
            request.user.first_name = request.POST.get('first_name').strip()
            request.user.last_name = request.POST.get('last_name').strip()

            if 'profile_picture' in request.FILES:
                new_image = request.FILES['profile_picture']
                raw_name = getattr(new_image, 'name', '') or ''
                ext = raw_name.rsplit('.', 1)[-1].lower() if '.' in raw_name else ''
                if ext not in ALLOWED_AVATAR_EXTENSIONS:
                    messages.error(request, "Formato de imagen no permitido. Usa JPG, PNG o WEBP.")
                    return redirect('web_dashboard')
                if new_image.size > MAX_AVATAR_SIZE_BYTES:
                    messages.error(request, "La imagen no puede superar los 10MB.")
                    return redirect('web_dashboard')

                ts_str = timezone.localtime(timezone.now()).strftime('%Y%m%d_%H%M%S')
                file_name = f"agent_{request.user.id}_{ts_str}.{ext}"
                
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

    # Configuración de Paginación
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
        'active_tickets': active_page,  
        'closed_tickets': closed_page,  
        'analytics_json': json.dumps(analytics),
        'analytics_data': analytics,    
        'agent_id': str(request.user.id),
        'jwt_token': str(refresh.access_token),
    })

@login_required(login_url='/auth/login/')
@require_POST
@support_access_required
def close_ticket(request, ticket_id):  
    ticket = get_object_or_404(SupportTicket, id=ticket_id)
    if ticket.agent and ticket.agent != request.user and not request.user.is_superuser:
        messages.error(request, "No tienes permisos para cerrar un ticket asignado a otro agente.")
        return redirect('web_dashboard')

    reason_raw = request.POST.get('close_reason', CloseTicketReason.SOLVED)
    try:
        reason_val = int(reason_raw)
        if reason_val not in CloseTicketReason.values:
            reason_val = CloseTicketReason.SOLVED
    except (ValueError, TypeError):
        reason_val = CloseTicketReason.SOLVED
    
    ticket.closed = True
    ticket.close_time = timezone.now()
    ticket.close_reason = reason_val
    ticket.save(update_fields=['closed', 'close_time', 'close_reason'])
    
    # 💡 ALERTAMOS A NODE.JS EN TIEMPO REAL
    try:
        requests.post(
            f"{settings.INTERNAL_WEBSOCKETS_URL}internal/emit-ticket-closed",
            json={
                'ticket_id': str(ticket.id), 
                'reason': ticket.get_close_reason_display(),
                'client_id': str(ticket.client.id),
                'agent_id': str(ticket.agent.id) if ticket.agent else None
            },
            headers={'X-Microservice-Token': settings.SECRET_KEY},
            timeout=2
        )
    except Exception as e:
        print(f"Advertencia: No se pudo emitir alerta de cierre de ticket: {e}")
    
    messages.success(request, f"El ticket #{ticket.id} fue cerrado correctamente.")
    return redirect('web_dashboard')

@login_required(login_url='/auth/login/')
@support_access_required
def support_agent_chat(request, ticket_id):
    ticket = get_object_or_404(SupportTicket, id=ticket_id)
    if ticket.agent and ticket.agent != request.user and not request.user.is_superuser:
        messages.error(request, "No tienes permisos para acceder al chat de otro agente.")
        return redirect('web_dashboard')
    refresh = RefreshToken.for_user(request.user)
    return render(request, 'support/support_chat.html', {
        'ticket': ticket,
        'agent_id': str(request.user.id),
        'jwt_token': str(refresh.access_token)
    })

# ==============================================================
# 🌍 VISTA PÚBLICA
# ==============================================================
# Variable de comisión por cada venta completada (%).
# Si se coloca en 0 (ej. SALES_COMMISSION_PCT = 0), el frontend reacciona automáticamente
# y muestra únicamente que crear tu comercio y vender es 100% gratis.
SALES_COMMISSION_PCT = 0

def landing_view(request):
    """ Ecosistema hiper-local CartMaker: Descubrimiento comercial en tu zona, Inventario IA y Atlas IA """
    plans = MerchantPlan.objects.all().order_by('price')
    system_config = SystemConfig.objects.order_by('-creation').first()

    raw_commission = getattr(system_config, 'sales_commission_pct', None) if system_config else None
    commission_source = raw_commission if raw_commission is not None else SALES_COMMISSION_PCT
    try:
        commission_val = float(commission_source)
    except (TypeError, ValueError):
        commission_val = 0.0

    has_sales_commission = commission_val > 0
    commission_display = f"{commission_val:g}" if has_sales_commission else "0"

    context = {
        'plans': plans,
        'system_config': system_config,
        'atlas_plus_price': system_config.atlas_plus_price_usd if system_config else 3.99,
        'atlas_free_limit': system_config.atlas_free_daily_limit if system_config else 5,
        'atlas_plus_limit': system_config.atlas_plus_daily_limit if system_config else 75,
        'sales_commission_pct': commission_display,
        'sales_commission_num': commission_val,
        'has_sales_commission': has_sales_commission,
    }
    return render(request, 'home.html', context)

def pitch_deck_view(request):
    """ Presentación Ejecutiva interactiva para Socios Fundadores """
    return render(request, 'pitch_deck.html')