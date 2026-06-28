from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum, Avg

from ..models import Company, InventoryItemTransaction, MerchantCalification, SystemConfig

class PlatinumEvaluator:
    """
    Motor de evaluación de calidad de comerciantes.
    Se encarga de otorgar o revocar el estado 'Platinum' basado en rendimiento histórico.
    """

    @staticmethod
    def evaluate_all_companies():
        companies = Company.objects.all()
        for company in companies:
            PlatinumEvaluator.evaluate_company(company)

    @staticmethod
    def evaluate_company(company: Company) -> bool:
        thirty_days_ago = timezone.now() - timedelta(days=30)

        # Obtenemos los parámetros dinámicos desde SystemConfig
        try:
            config = SystemConfig.objects.latest('creation')
            min_sales = config.platinum_min_sells_per_month_requirement
            min_rating = float(config.platinum_min_rating_promedy_requirement)
        except SystemConfig.DoesNotExist:
            min_sales = 100
            min_rating = 4.5

        # 1. Verificar volumen de ventas
        # Reemplaza '1' por tu TransactionType.SALE si es diferente
        sales_volume = InventoryItemTransaction.objects.filter(
            item__store__company=company,
            transaction_type=1, 
            creation__gte=thirty_days_ago
        ).aggregate(total_sold=Sum('units'))['total_sold'] or 0

        if sales_volume < min_sales:
            return PlatinumEvaluator._update_status(company, False)

        # 2. Verificar promedio de calificaciones
        avg_rating = MerchantCalification.objects.filter(
            merchant=company,
            creation__gte=thirty_days_ago
        ).aggregate(average=Avg('rating'))['average'] or 0.0

        if avg_rating >= min_rating:
            return PlatinumEvaluator._update_status(company, True)
        else:
            return PlatinumEvaluator._update_status(company, False)

    @staticmethod
    def _update_status(company: Company, is_platinum: bool) -> bool:
        if company.is_platinum != is_platinum:
            company.is_platinum = is_platinum
            company.save(update_fields=['is_platinum'])
        return is_platinum