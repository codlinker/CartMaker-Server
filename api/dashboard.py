import json
import requests
from datetime import timedelta, datetime
from django.utils import timezone
from django.core.cache import cache
from django.db.models import Count, Q, Sum, F, FloatField, ExpressionWrapper
from django.db.models.functions import TruncDate
from api.models import (
    User, Order, MerchantSubscription, AtlasPlusPlan,
    ProductViewLog, UnmetDemandLog, SupportTicket,
    UserNavigationLog, MerchantPlanPayment, AtlasPlusPlanPayment
)

def build_metrics_for_range(start_date, end_date):
    """
    Motor central de cálculos del dashboard. 
    Aplica los filtros de fecha a todos los modelos relevantes.
    """
    # Función auxiliar para inyectar filtros dinámicamente
    def date_filter(field="creation"):
        if start_date:
            return {f"{field}__range": (start_date, end_date)}
        return {f"{field}__lte": end_date}

    # 1. KPIs Globales
    total_users = User.objects.filter(creation__lte=end_date).count()
    active_users = UserNavigationLog.objects.filter(**date_filter("login_time")).values('user').distinct().count()
    total_orders = Order.objects.filter(**date_filter("creation")).count()
    active_merchants = MerchantSubscription.objects.filter(valid_until__gt=end_date).count()
    open_tickets = SupportTicket.objects.filter(closed=False, **date_filter("creation")).count()

    # 2. Órdenes
    orders_status = Order.objects.filter(**date_filter("creation")).values('status').annotate(total=Count('id'))
    order_labels_map = {0: 'Esperando', 1: 'Delivery', 3: 'Cancelada', 4: 'Completada', 5: 'Resuelta'}
    orders_data = {order_labels_map.get(item['status'], 'Otro'): item['total'] for item in orders_status}

    # 3. Telemetría
    telemetry = ProductViewLog.objects.filter(**date_filter("start_time")).aggregate(
        views=Count('id'),
        carts=Count('id', filter=Q(added_to_cart=True)),
        purchases=Count('id', filter=Q(bought=True))
    )

    # 4. Ecosistema B2B y Atlas
    atlas_active = AtlasPlusPlan.objects.filter(valid_until__gt=end_date, tier=1).count()
    subscriptions_data = {
        'Comercios Premium': active_merchants,
        'Usuarios Atlas+': atlas_active,
        'Usuarios Freemium': User.objects.count() - active_merchants - atlas_active
    }

    # 5. Radar
    unmet_demand = UnmetDemandLog.objects.filter(**date_filter("creation")) \
        .values('search_term').annotate(total=Count('id')).order_by('-total')[:5]

    # 6. Motor Financiero (Gráficos)
    revenue_dict = {}
    if start_date:
        delta = (end_date.date() - start_date.date()).days
        date_list = [(start_date + timedelta(days=i)).date() for i in range(delta + 1)]
    else:
        # Si es "Todo el historial", buscamos la fecha del primer pago
        first_payment = MerchantPlanPayment.objects.filter(status=1).order_by('verified_at').first()
        if first_payment and first_payment.verified_at:
            start_calc = first_payment.verified_at
            delta = (end_date.date() - start_calc.date()).days
            date_list = [(start_calc + timedelta(days=i)).date() for i in range(delta + 1)]
        else:
            date_list = [end_date.date()]

    for d in date_list:
        revenue_dict[d.strftime('%d/%m/%Y')] = 0.0

    merch_payments = MerchantPlanPayment.objects.filter(status=1, **date_filter("verified_at")) \
        .annotate(date=TruncDate('verified_at')).values('date').annotate(total=Sum('amount'))
    
    atlas_payments = AtlasPlusPlanPayment.objects.filter(status=1, **date_filter("verified_at")) \
        .annotate(date=TruncDate('verified_at')).values('date').annotate(total=Sum('amount'))

    for p in merch_payments:
        if p['date']:
            key = p['date'].strftime('%d/%m/%Y')
            if key in revenue_dict: revenue_dict[key] += float(p['total'] or 0)
            
    for p in atlas_payments:
        if p['date']:
            key = p['date'].strftime('%d/%m/%Y')
            if key in revenue_dict: revenue_dict[key] += float(p['total'] or 0)

    revenue_values = list(revenue_dict.values())

    # 💡 7. TRIPLE VISIÓN FINANCIERA (Movida aquí para que el HTML siempre la reciba)
    try:
        res = requests.get('https://ve.dolarapi.com/v1/dolares/oficial', timeout=5)
        bcv_today = float(res.json().get('promedio', 1.0))
    except:
        bcv_today = 1.0

    df_verified = date_filter("verified_at")

    total_bs = MerchantPlanPayment.objects.filter(status=1, **df_verified).aggregate(s=Sum('amount'))['s'] or 0
    total_bs += AtlasPlusPlanPayment.objects.filter(status=1, **df_verified).aggregate(s=Sum('amount'))['s'] or 0
    
    usd_hist_calc = ExpressionWrapper(F('amount') / F('bcv_taxes_to_day'), output_field=FloatField())
    usd_historic = MerchantPlanPayment.objects.filter(status=1, **df_verified).aggregate(s=Sum(usd_hist_calc))['s'] or 0
    usd_historic += AtlasPlusPlanPayment.objects.filter(status=1, **df_verified).aggregate(s=Sum(usd_hist_calc))['s'] or 0

    usd_today = float(total_bs) / bcv_today
    differential = usd_today - float(usd_historic)

    return {
        'kpis': {
            'users': total_users, 'active_users': active_users,
            'orders_month': total_orders, 'active_merchants': active_merchants,
            'open_tickets': open_tickets, 'total_revenue': round(sum(revenue_values), 2),
            # Inyectamos de forma segura las llaves para que Django las consiga
            'revenue_bs': float(total_bs),
            'revenue_usd_historic': float(usd_historic),
            'revenue_usd_today': float(usd_today),
            'revenue_differential': float(differential)
        },
        'charts_json': json.dumps({
            'orders_labels': list(orders_data.keys()),
            'orders_values': list(orders_data.values()),
            'funnel_labels': ['Vistas', 'Carritos', 'Compras'],
            'funnel_values': [telemetry['views'] or 0, telemetry['carts'] or 0, telemetry['purchases'] or 0],
            'subs_labels': list(subscriptions_data.keys()),
            'subs_values': list(subscriptions_data.values()),
            'unmet_labels': [item['search_term'].capitalize() for item in unmet_demand],
            'unmet_values': [item['total'] for item in unmet_demand],
            'revenue_labels': list(revenue_dict.keys()),
            'revenue_values': revenue_values
        })
    }


def custom_dashboard_context(request, context):
    """
    Recibe la solicitud del usuario, identifica el filtro y busca en Redis.
    Si es un rango personalizado, lo calcula en vivo (on-the-fly).
    """
    period = request.GET.get('period', '30d') 
    now = timezone.now()
    
    if period == 'custom':
        start_str = request.GET.get('start')
        end_str = request.GET.get('end')
        try:
            start_date = timezone.make_aware(datetime.strptime(start_str, '%Y-%m-%d'))
            end_date = timezone.make_aware(datetime.strptime(end_str, '%Y-%m-%d')).replace(hour=23, minute=59, second=59)
            metrics = build_metrics_for_range(start_date, end_date)
        except Exception:
            metrics = None # Fallback en caso de fechas inválidas
    else:
        # Extrae los datos precalculados por Celery de la RAM
        metrics = cache.get(f'admin_dashboard_metrics_{period}')

    # Seguro anti-fallos por si Celery no ha corrido o el caché se borró
    if not metrics:
        if period == 'all': start = None
        elif period == '365d': start = now - timedelta(days=365)
        elif period == '180d': start = now - timedelta(days=180)
        elif period == '90d': start = now - timedelta(days=90)
        else: start = now - timedelta(days=30)
        
        metrics = build_metrics_for_range(start, now)
        if period != 'custom':
            cache.set(f'admin_dashboard_metrics_{period}', metrics, timeout=900)

    context.update(metrics)
    
    # Pasamos las variables al frontend para mantener el estado del formulario
    context['current_period'] = period
    context['custom_start'] = request.GET.get('start', '')
    context['custom_end'] = request.GET.get('end', '')
    
    # Calculamos una etiqueta legible para el gráfico de ingresos
    period_labels = {
        '30d': 'Último Mes', '90d': 'Último Trimestre', '180d': 'Último Semestre', 
        '365d': 'Último Año', 'all': 'Histórico Completo', 'custom': 'Rango Personalizado'
    }
    context['revenue_label'] = period_labels.get(period, 'Rango Personalizado')
    
    return context