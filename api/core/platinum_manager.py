from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum, Avg

from ..models import Company, InventoryItemTransaction, MerchantCalification

class PlatinumEvaluator:
    """
    Motor de evaluación de calidad de comerciantes.
    Se encarga de otorgar o revocar el estado 'Platinum' basado en rendimiento histórico.
    """

    @staticmethod
    def evaluate_all_companies():
        """
        Evalúa a todas las compañías activas. Ideal para ejecutarse en un CronJob diario.
        """
        companies = Company.objects.all()
        for company in companies:
            PlatinumEvaluator.evaluate_company(company)

    @staticmethod
    def evaluate_company(company: Company) -> bool:
        """
        Evalúa si una compañía cumple con los requisitos Platinum:
        1. Al menos 100 unidades vendidas en los últimos 30 días.
        2. Calificación promedio mayor o igual a 4.5 en los últimos 30 días.
        
        Retorna True si es Platinum, False en caso contrario.
        """
        thirty_days_ago = timezone.now() - timedelta(days=30)

        # 1. Verificar volumen de ventas (asumiendo que tienes un enum para Ventas)
        # Reemplaza 'TransactionType.SALE' por el valor real de tu Enum
        sales_volume = InventoryItemTransaction.objects.filter(
            item__store__company=company,
            transaction_type=1, # 1 = Venta (Ajusta esto a tu modelo)
            creation__gte=thirty_days_ago
        ).aggregate(total_sold=Sum('units'))['total_sold'] or 0

        if sales_volume < 100:
            return PlatinumEvaluator._update_status(company, False)

        # 2. Verificar promedio de calificaciones en el mismo periodo
        avg_rating = MerchantCalification.objects.filter(
            merchant=company,
            creation__gte=thirty_days_ago
        ).aggregate(average=Avg('rating'))['average'] or 0.0

        if avg_rating >= 4.5:
            return PlatinumEvaluator._update_status(company, True)
        else:
            return PlatinumEvaluator._update_status(company, False)

    @staticmethod
    def _update_status(company: Company, is_platinum: bool) -> bool:
        """Actualiza la BD solo si el estado cambió, para ahorrar queries de escritura."""
        if company.is_platinum != is_platinum:
            company.is_platinum = is_platinum
            company.save(update_fields=['is_platinum'])
        return is_platinum