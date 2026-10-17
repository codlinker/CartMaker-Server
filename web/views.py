from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Avg, Sum, F, Q, OuterRef, Subquery
from django.db.models.functions import Coalesce
import json
import requests
from api.models import *
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.paginator import Paginator
from .decorators import *
from django.conf import settings
from django.core.exceptions import ValidationError
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

    reason_raw = request.POST.get('close_reason', SupportTicket.CloseReason.SOLVED)
    try:
        reason_val = int(reason_raw)
        if reason_val not in SupportTicket.CloseReason.values:
            reason_val = SupportTicket.CloseReason.SOLVED
    except (ValueError, TypeError):
        reason_val = SupportTicket.CloseReason.SOLVED
    
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


# ==============================================================
# 🛍️ VITRINA WEB PÚBLICA INTERACTIVA (PILAR 1 - OMNICANALIDAD)
# ==============================================================
def format_ve_currency(val, include_dollar_suffix: bool = False) -> str:
    """
    Formatea un monto numérico según la convención monetaria en Venezuela:
    separador de miles con punto (.), separador decimal con coma (,) y, cuando es USD,
    el símbolo de dólar ($) ubicado a la derecha del monto (ej. 1.800,00$).
    """
    try:
        num = float(val or 0.0)
    except (TypeError, ValueError):
        num = 0.0
    sign = "-" if num < 0 else ""
    abs_num = abs(num)
    us_formatted = f"{abs_num:,.2f}"
    ve_str = us_formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{sign}{ve_str}$" if include_dollar_suffix else f"{sign}{ve_str}"


def calculate_storefront_route_metrics(
    u_lat: float,
    u_lng: float,
    s_lat: float,
    s_lng: float,
) -> dict:
    """
    Calcula en sub-milisegundos la distancia geodésica Haversine, la distancia vial
    estimada urbana (factor de tortuosidad 1.28x) y los tiempos estimados de llegada (ETA)
    en Carro, Moto y A pie para la Vitrina Pública de CartMaker.
    """
    import math

    R = 6371.0
    lat1_rad = math.radians(float(u_lat))
    lat2_rad = math.radians(float(s_lat))
    d_lat = math.radians(float(s_lat) - float(u_lat))
    d_lng = math.radians(float(s_lng) - float(u_lng))

    a = (
        math.sin(d_lat / 2.0) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * (math.sin(d_lng / 2.0) ** 2)
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
    straight_km = R * c
    road_km = straight_km * 1.28

    car_minutes = max(2, int(round((road_km / 28.0) * 60.0)))
    moto_minutes = max(1, int(round(car_minutes * 0.68)))
    walk_minutes = max(3, int(round((road_km / 4.8) * 60.0)))

    return {
        'straight_km': round(straight_km, 3),
        'road_km': round(road_km, 2),
        'car_minutes': car_minutes,
        'moto_minutes': moto_minutes,
        'walk_minutes': walk_minutes,
        'distance_label': f"{road_km:.1f} km",
        'eta_car_label': f"{car_minutes} min",
        'eta_moto_label': f"{moto_minutes} min",
        'eta_walk_label': f"{walk_minutes} min",
    }


def _build_storefront_context(
    request,
    company_or_store_id,
    highlight_item_id: str = None,
    express_order_draft: dict = None,
):
    from api.views.base import _get_cached_bcv_rate
    from api.core.storefront_themes import STOREFRONT_THEMES, resolve_company_storefront_theme
    from api.core.ve_geo import describe_zone
    from django.http import Http404
    import math
    import secrets

    company = Company.objects.select_related('category').filter(id=company_or_store_id).first()
    initial_store_id = request.GET.get('store_id')

    if not company:
        store_obj = CompanyStore.objects.select_related('company', 'company__category').filter(
            id=company_or_store_id, is_active=True
        ).first()
        if not store_obj:
            raise Http404("El comercio solicitado no existe o no está disponible.")
        company = store_obj.company
        initial_store_id = str(store_obj.id)

    stores_qs = (
        CompanyStore.objects.filter(company=company, is_active=True)
        .select_related('location', 'location__mall')
        .prefetch_related('contact_methods')
        .order_by('-is_main_store', 'creation')
    )
    stores_list = list(stores_qs)
    if not stores_list:
        raise Http404("Este comercio no tiene sucursales activas actualmente.")

    # Inventario activo en todas las sucursales de la compañía
    items_qs = (
        InventoryItem.objects.filter(store__company=company, store__is_active=True, paused=False, stock__gt=0)
        .select_related(
            'product',
            'product__category',
            'product__category__parent_category',
            'store',
            'store__location',
            'offer',
        )
        .annotate(
            avg_rating=Coalesce(Avg('product__califications__rating'), 0.0),
            rating_count=Count('product__califications', distinct=True),
        )
        .order_by('-cached_popularity_score', '-creation')
    )
    items_raw = list(items_qs)

    bcv_rate = _get_cached_bcv_rate(default=0.0)
    bcv_rate_ve = format_ve_currency(bcv_rate, include_dollar_suffix=False)

    # Determinar categoría padre dominante para el motor de 14 temas visuales
    parent_cat_counts = {}
    subcategories_map = {}
    serialized_items = []

    for it in items_raw:
        item_json = it.get_json()
        eff_usd = float(item_json.get('effective_price') or 0.0)
        list_usd = float(item_json.get('list_price') or eff_usd)
        eff_bs = round(eff_usd * bcv_rate, 2) if bcv_rate > 0 else None
        list_bs = round(list_usd * bcv_rate, 2) if bcv_rate > 0 else None
        item_json['effective_price_bs'] = eff_bs
        item_json['list_price_bs'] = list_bs
        item_json['effective_price_ve'] = format_ve_currency(eff_usd, include_dollar_suffix=True)
        item_json['list_price_ve'] = format_ve_currency(list_usd, include_dollar_suffix=True)
        item_json['effective_price_bs_ve'] = format_ve_currency(eff_bs, include_dollar_suffix=False) if eff_bs is not None else None
        item_json['list_price_bs_ve'] = format_ve_currency(list_bs, include_dollar_suffix=False) if list_bs is not None else None
        item_json['store_id_str'] = str(it.store_id)
        if item_json.get('creation'):
            item_json['creation'] = item_json['creation'].isoformat() if hasattr(item_json['creation'], 'isoformat') else str(item_json['creation'])
        if item_json.get('sold_out_time'):
            item_json['sold_out_time'] = str(item_json['sold_out_time'])
        if item_json.get('expiration_date'):
            item_json['expiration_date'] = str(item_json['expiration_date'])
        if item_json.get('offer') and item_json['offer'].get('valid_until'):
            vu = item_json['offer']['valid_until']
            item_json['offer']['valid_until'] = vu.isoformat() if hasattr(vu, 'isoformat') else str(vu)
        if item_json.get('product') and item_json['product'].get('creation'):
            pc = item_json['product']['creation']
            item_json['product']['creation'] = pc.isoformat() if hasattr(pc, 'isoformat') else str(pc)
        if item_json.get('product'):
            item_json['product']['company_id'] = str(item_json['product']['company_id'])

        cat_info = (item_json.get('product') or {}).get('category') or {}
        sub_id = cat_info.get('id')
        sub_name = cat_info.get('name') or 'General'
        parent_name = cat_info.get('parent_category_name') or ''
        if parent_name:
            parent_cat_counts[parent_name] = parent_cat_counts.get(parent_name, 0) + 1
        if sub_id:
            subcategories_map[sub_id] = {'id': sub_id, 'name': sub_name, 'parent_name': parent_name}

        serialized_items.append(item_json)

    dominant_parent = (
        max(parent_cat_counts.items(), key=lambda x: x[1])[0]
        if parent_cat_counts
        else ''
    )

    theme = resolve_company_storefront_theme(
        company_category_name=company.category.name if company.category else '',
        dominant_parent_category=dominant_parent,
    )

    # Coordenadas opcionales del visitante (?lat=&lng=) para pre-calcular ruta al instante
    req_lat = request.GET.get('lat')
    req_lng = request.GET.get('lng')
    user_coords = None
    if req_lat is not None and req_lng is not None:
        try:
            user_coords = (float(req_lat), float(req_lng))
        except (TypeError, ValueError):
            user_coords = None

    # Sucursales enriquecidas con zona geográfica y coordenadas para el mapa interactivo
    branches_data = []
    for s in stores_list:
        s_json = s.get_json()
        s_json['id'] = str(s.id)
        loc = s_json.get('location')
        if loc and loc.get('lat') is not None and loc.get('lng') is not None:
            loc['zone_name'] = describe_zone(loc['lat'], loc['lng'])
            if getattr(s.location, 'mall', None):
                loc['mall_name'] = s.location.mall.name
            if user_coords:
                s_json['route_metrics'] = calculate_storefront_route_metrics(
                    user_coords[0], user_coords[1], loc['lat'], loc['lng']
                )
        branches_data.append(s_json)

    # Video Stories activas de la compañía
    now = timezone.now()
    stories_qs = (
        CompanyVideoStory.objects.filter(company=company, expires_at__gt=now)
        .select_related('associated_item', 'associated_item__product', 'associated_item__store')
        .order_by('-creation')[:12]
    )
    stories_data = []
    for st in stories_qs:
        if not st.video_file:
            continue
        assoc_price = float(st.associated_item.get_effective_price()) if st.associated_item else None
        stories_data.append({
            'id': str(st.id),
            'video_url': storage_manager.get_url(st.video_file),
            'thumbnail_url': storage_manager.get_url(st.thumbnail) if st.thumbnail else None,
            'description': st.description or company.name,
            'duration_seconds': float(st.duration_seconds or 15.0),
            'views_count': int(st.views_count or 0),
            'associated_item_id': str(st.associated_item_id) if st.associated_item_id else None,
            'associated_item_name': (
                st.associated_item.product.name
                if (st.associated_item and st.associated_item.product)
                else None
            ),
            'associated_item_price_usd': assoc_price,
            'associated_item_price_ve': format_ve_currency(assoc_price, include_dollar_suffix=True) if assoc_price is not None else None,
        })

    # Reputación, calificaciones y volumen de ventas
    califications_qs = MerchantCalification.objects.filter(merchant=company).select_related('client').order_by('-creation')
    rating_aggr = califications_qs.aggregate(avg=Avg('rating'), count=Count('id'))
    avg_rating = round(float(rating_aggr['avg'] or 0.0), 2)
    rating_count = int(rating_aggr['count'] or 0)

    star_counts = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
    recent_reviews = []
    for cal in califications_qs[:25]:
        bucket = max(1, min(5, int(round(float(cal.rating or 5)))))
        star_counts[bucket] += 1
        if len(recent_reviews) < 8:
            c_name = f"{cal.client.first_name} {cal.client.last_name[:1]}." if cal.client else "Cliente Verificado"
            recent_reviews.append({
                'client_name': c_name.strip(),
                'rating': round(float(cal.rating), 1),
                'date': timezone.localtime(cal.creation).strftime("%d/%m/%Y"),
            })

    total_sales_units = (
        InventoryItemTransaction.objects.filter(
            item__store__company=company,
            transaction_type=TransactionType.OUTCOME,
        ).aggregate(total=Sum('units'))['total']
        or 0
    )
    total_sales_units = abs(int(total_sales_units))

    main_branch = branches_data[0]
    active_store_id = str(initial_store_id) if initial_store_id else main_branch['id']
    if highlight_item_id:
        hl_match = next((x for x in serialized_items if str(x.get('id')) == str(highlight_item_id)), None)
        hl_store_id = hl_match.get('store_id_str') if hl_match else active_store_id
        app_deep_link = f"cartmaker://product/{highlight_item_id}?store_id={hl_store_id}&company_id={company.id}"
    else:
        app_deep_link = f"cartmaker://store/{active_store_id}?company_id={company.id}"

    # Paginación del catálogo (soporta ?page= y ?page_size=, por defecto 12 productos por página)
    try:
        page_size = int(request.GET.get('page_size') or 12)
    except (TypeError, ValueError):
        page_size = 12
    page_size = max(4, min(48, page_size))

    total_items = len(serialized_items)
    total_pages = max(1, math.ceil(total_items / page_size)) if total_items > 0 else 1

    try:
        current_page = int(request.GET.get('page') or 1)
    except (TypeError, ValueError):
        current_page = 1
    current_page = max(1, min(total_pages, current_page))

    start_idx = (current_page - 1) * page_size
    end_idx = min(total_items, start_idx + page_size)
    paginated_items = serialized_items[start_idx:end_idx]

    pagination_meta = {
        'current_page': current_page,
        'page_size': page_size,
        'total_items': total_items,
        'total_pages': total_pages,
        'has_previous': current_page > 1,
        'has_next': current_page < total_pages,
        'previous_page': current_page - 1 if current_page > 1 else None,
        'next_page': current_page + 1 if current_page < total_pages else None,
        'start_index': (start_idx + 1) if total_items > 0 else 0,
        'end_index': end_idx,
    }

    company_data = company.get_json()
    company_data['id'] = str(company.id)
    company_data['avg_rating'] = avg_rating
    company_data['rating_count'] = rating_count
    company_data['total_sales_units'] = total_sales_units
    company_data['merchant_type_label'] = company.get_merchant_type_display()

    mapbox_api_key = getattr(settings, 'MAPBOX_APIKEY', '')
    mapbox_style_url = getattr(settings, 'MAPBOX_STYLE_URL', '')

    storefront_payload = {
        'company': company_data,
        'theme': theme,
        'branches': branches_data,
        'initial_store_id': str(initial_store_id) if initial_store_id else main_branch['id'],
        'subcategories': list(subcategories_map.values()),
        'items': serialized_items,
        'pagination': pagination_meta,
        'stories': stories_data,
        'reputation': {
            'avg_rating': avg_rating,
            'rating_count': rating_count,
            'star_distribution': star_counts,
            'recent_reviews': recent_reviews,
            'total_sales_units': total_sales_units,
        },
        'bcv_rate': bcv_rate,
        'bcv_rate_ve': bcv_rate_ve,
        'app_deep_link': app_deep_link,
        'highlight_item_id': str(highlight_item_id) if highlight_item_id else None,
        'express_order_draft': express_order_draft,
        'handoff_endpoint': f"/tienda/{company.id}/handoff-cart/",
        'mapbox_api_key': mapbox_api_key,
        'mapbox_style_url': mapbox_style_url,
    }

    from django.core.serializers.json import DjangoJSONEncoder

    return {
        'company': company_data,
        'theme': theme,
        'branches': branches_data,
        'items_count': total_items,
        'paginated_items': paginated_items,
        'pagination': pagination_meta,
        'bcv_rate': bcv_rate,
        'bcv_rate_ve': bcv_rate_ve,
        'app_deep_link': app_deep_link,
        'mapbox_api_key': mapbox_api_key,
        'mapbox_style_url': mapbox_style_url,
        'storefront_json': json.dumps(storefront_payload, cls=DjangoJSONEncoder, ensure_ascii=False),
    }


def public_storefront_view(request, company_id):
    """
    Vitrina Web Pública Interactiva de un Comerciante en CartMaker.
    Diseñada con motor camaleónico de 14 categorías, mapa interactivo con cálculo de ruta,
    reproductor de Video Stories, filtros en tiempo real, paginación y Checkout exclusivo hacia CartMaker App.
    """
    context = _build_storefront_context(
        request=request,
        company_or_store_id=company_id,
        highlight_item_id=request.GET.get('item_id'),
    )
    if request.GET.get('format') == 'json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'company_id': context['company']['id'],
            'company_name': context['company']['name'],
            'bcv_rate': context['bcv_rate'],
            'bcv_rate_ve': context['bcv_rate_ve'],
            'pagination': context['pagination'],
            'items': context['paginated_items'],
            'branches': context['branches'],
        })
    return render(request, 'storefront/public_catalog.html', context)


def public_product_redirect_view(request, item_id):
    """
    Enlace corto de producto (/p/<item_id>/) compartido desde WhatsApp Status o Instagram Stories.
    Abre la Vitrina Pública de la compañía con el modal interactivo del producto pre-abierto.
    """
    from django.http import Http404

    item = (
        InventoryItem.objects.select_related('store__company')
        .filter(id=item_id, paused=False)
        .first()
    )
    if not item:
        prod = Product.objects.filter(id=item_id).first()
        if prod:
            item = InventoryItem.objects.filter(product=prod, paused=False).first()
    if not item:
        raise Http404("El producto solicitado ya no se encuentra disponible.")

    context = _build_storefront_context(
        request=request,
        company_or_store_id=item.store.company_id,
        highlight_item_id=str(item.id),
    )
    return render(request, 'storefront/public_catalog.html', context)


def public_express_order_view(request, token: str):
    """
    Vista pública de un Link de Orden Express (/orden-express/<token>/) o Carrito Web compartido.
    Pre-carga los artículos en la vitrina y abre el puente directo hacia la App de CartMaker.
    """
    from django.http import Http404

    draft = cache.get(f"cm:handoff_token:{token}")
    if not draft or not draft.get('company_id'):
        raise Http404("Este enlace de orden express ha expirado o no es válido.")

    context = _build_storefront_context(
        request=request,
        company_or_store_id=draft['company_id'],
        express_order_draft=draft,
    )
    return render(request, 'storefront/public_catalog.html', context)


@require_POST
def create_web_cart_handoff_ajax(request, company_id):
    """
    Endpoint AJAX de la Vitrina Web Pública para empaquetar el carrito armado por el visitante
    y generar un token de traspaso directo (`cmw_...`) hacia la App Móvil de CartMaker.
    """
    from api.views.base import _get_cached_bcv_rate
    from datetime import timedelta
    import secrets

    try:
        body = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        return JsonResponse({'error': 'Payload JSON inválido.'}, status=400)

    raw_items = body.get('items') or []
    store_id = body.get('store_id')
    if not isinstance(raw_items, list) or not raw_items:
        return JsonResponse({'error': 'El carrito está vacío.'}, status=400)

    company = get_object_or_404(Company, id=company_id)
    item_ids = [str(x.get('item_id')) for x in raw_items if isinstance(x, dict) and x.get('item_id')]
    db_items = {
        str(it.id): it
        for it in InventoryItem.objects.filter(
            id__in=item_ids, store__company=company, paused=False
        ).select_related('product', 'store', 'offer')
    }

    packaged = []
    total_usd = 0.0
    resolved_store_id = str(store_id) if store_id else None

    for entry in raw_items:
        if not isinstance(entry, dict):
            continue
        iid = str(entry.get('item_id') or '')
        if iid not in db_items:
            continue
        inv = db_items[iid]
        if inv.stock <= 0:
            continue
        qty = max(0.1, min(float(inv.stock), float(entry.get('quantity', 1) or 1)))
        u_price = inv.get_effective_price()
        line_usd = round(u_price * qty, 2)
        total_usd += line_usd
        if not resolved_store_id:
            resolved_store_id = str(inv.store_id)
        images = [storage_manager.get_url(img) for img in (inv.product.images or []) if img]
        packaged.append({
            'item_id': iid,
            'product_id': str(inv.product_id),
            'name': inv.product.name,
            'image_url': images[0] if images else None,
            'quantity': qty if inv.product.allow_fractional_quantity else int(qty),
            'unit_price_usd': u_price,
            'line_total_usd': line_usd,
            'selected_variant': entry.get('selected_variant'),
            'selected_modifiers': entry.get('selected_modifiers') or [],
            'order_note': (entry.get('order_note') or '')[:250],
        })

    if not packaged:
        return JsonResponse({'error': 'No hay productos disponibles con stock.'}, status=400)

    token = f"cmw_{secrets.token_urlsafe(12)}"
    bcv_rate = _get_cached_bcv_rate(default=0.0)
    total_usd = round(total_usd, 2)
    total_bs = round(total_usd * bcv_rate, 2) if bcv_rate > 0 else None

    payload = {
        'token': token,
        'type': 'WEB_STOREFRONT_CART',
        'company_id': str(company.id),
        'company_name': company.name,
        'store_id': resolved_store_id,
        'items': packaged,
        'total_usd': total_usd,
        'total_bs': total_bs,
        'bcv_rate': bcv_rate,
        'created_at': timezone.now().isoformat(),
        'expires_at': (timezone.now() + timedelta(hours=72)).isoformat(),
    }
    cache.set(f"cm:handoff_token:{token}", payload, timeout=72 * 3600)

    domain = (getattr(settings, 'DOMAIN', 'https://www.cartmaker.app') or 'https://www.cartmaker.app').rstrip('/')
    return JsonResponse({
        'success': True,
        'token': token,
        'app_deep_link': f"cartmaker://web-cart?token={token}",
        'web_resume_url': f"{domain}/orden-express/{token}/",
        'cart': payload,
    })