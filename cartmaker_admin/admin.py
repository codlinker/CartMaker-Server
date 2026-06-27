import json
from datetime import timedelta
from django.utils import timezone
from django.core.cache import cache
from django.db.models import Count, Q
from django.contrib import admin
from unfold.sites import UnfoldAdminSite

# Importa tus modelos aquí
from api.models import (
    User, Order, MerchantSubscription, AtlasPlusPlan, 
    ProductViewLog, UnmetDemandLog, SupportTicket
)

class CartMakerAdminSite(UnfoldAdminSite):
    def index(self, request, extra_context=None):
        # 💡 Usamos Redis (configurado en tu settings.py) para guardar el dashboard por 30 mins
        cache_key = 'admin_dashboard_metrics_v1'
        metrics = cache.get(cache_key)

        if not metrics:
            now = timezone.now()
            thirty_days_ago = now - timedelta(days=30)

            # 1. KPIs Globales (Tarjetas superiores)
            total_users = User.objects.count()
            total_orders_month = Order.objects.filter(creation__gte=thirty_days_ago).count()
            active_merchants = MerchantSubscription.objects.filter(valid_until__gt=now).count()
            open_tickets = SupportTicket.objects.filter(closed=False).count()

            # 2. Estado de Órdenes (Doughnut Chart)
            orders_status = Order.objects.values('status').annotate(total=Count('id'))
            order_labels = {0: 'Esperando', 1: 'En Camino', 3: 'Cancelada', 4: 'Completada', 5: 'Resuelta'}
            orders_data = {order_labels.get(item['status'], 'Otro'): item['total'] for item in orders_status}

            # 3. Embudo de Conversión (Bar Chart - Telemetría)
            telemetry = ProductViewLog.objects.aggregate(
                views=Count('id'),
                carts=Count('id', filter=Q(added_to_cart=True)),
                purchases=Count('id', filter=Q(bought=True))
            )

            # 4. Suscripciones B2B y Atlas AI
            atlas_active = AtlasPlusPlan.objects.filter(valid_until__gt=now, tier=1).count()
            subscriptions_data = {
                'Comercios Premium': active_merchants,
                'Usuarios Atlas+': atlas_active,
                'Usuarios Freemium': total_users - active_merchants - atlas_active
            }

            # 5. Radar Comercial: Demanda Insatisfecha en Venezuela (Top 5)
            unmet_demand = UnmetDemandLog.objects.values('search_term') \
                .annotate(total=Count('id')).order_by('-total')[:5]
            unmet_labels = [item['search_term'].capitalize() for item in unmet_demand]
            unmet_values = [item['total'] for item in unmet_demand]

            # 6. Soporte y Reputación (Tickets por Tópico)
            tickets_topic = SupportTicket.objects.values('topic').annotate(total=Count('id'))
            topic_labels = {0: 'Órdenes', 1: 'Tiendas', 2: 'Cuenta', 3: 'Otro'}
            support_data = {topic_labels.get(item['topic'], 'Otro'): item['total'] for item in tickets_topic}

            metrics = {
                'kpis': {
                    'users': total_users,
                    'orders_month': total_orders_month,
                    'active_merchants': active_merchants,
                    'open_tickets': open_tickets,
                },
                'charts_json': json.dumps({
                    'orders_labels': list(orders_data.keys()),
                    'orders_values': list(orders_data.values()),
                    'funnel_labels': ['Vistas', 'Carritos', 'Compras'],
                    'funnel_values': [telemetry['views'], telemetry['carts'], telemetry['purchases']],
                    'subs_labels': list(subscriptions_data.keys()),
                    'subs_values': list(subscriptions_data.values()),
                    'unmet_labels': unmet_labels,
                    'unmet_values': unmet_values,
                    'support_labels': list(support_data.keys()),
                    'support_values': list(support_data.values()),
                })
            }
            # Guardar en Redis (Caché por 30 minutos)
            cache.set(cache_key, metrics, timeout=1800)

        context = extra_context or {}
        context.update(metrics)
        return super().index(request, context)

# Reemplaza el sitio por defecto
admin.site = CartMakerAdminSite()