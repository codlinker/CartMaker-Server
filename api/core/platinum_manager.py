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
        thirty_days_ago = timezone.now() - timedelta(days=30)
        try:
            config = SystemConfig.objects.latest('creation')
            min_sales = config.platinum_min_sells_per_month_requirement
            min_rating = float(config.platinum_min_rating_promedy_requirement)
        except SystemConfig.DoesNotExist:
            min_sales = 100
            min_rating = 4.5

        sales_by_company = dict(
            InventoryItemTransaction.objects.filter(
                transaction_type=1,
                creation__gte=thirty_days_ago,
            )
            .values('item__store__company_id')
            .annotate(total_sold=Sum('units'))
            .values_list('item__store__company_id', 'total_sold')
        )

        ratings_by_company = dict(
            MerchantCalification.objects.filter(
                creation__gte=thirty_days_ago,
            )
            .values('merchant_id')
            .annotate(average=Avg('rating'))
            .values_list('merchant_id', 'average')
        )

        to_update = []
        for company in Company.objects.only('id', 'is_platinum').iterator(chunk_size=500):
            total_sold = abs(sales_by_company.get(company.id, 0) or 0)
            avg_rating = float(ratings_by_company.get(company.id, 0.0) or 0.0)
            should_be_platinum = (total_sold >= min_sales) and (avg_rating >= min_rating)
            if company.is_platinum != should_be_platinum:
                company.is_platinum = should_be_platinum
                to_update.append(company)

        if to_update:
            Company.objects.bulk_update(to_update, ['is_platinum'], batch_size=500)

    @staticmethod
    def evaluate_company(company: Company, config: SystemConfig = None) -> bool:
        thirty_days_ago = timezone.now() - timedelta(days=30)

        if config is None:
            try:
                config = SystemConfig.objects.latest('creation')
            except SystemConfig.DoesNotExist:
                config = None

        if config is not None:
            min_sales = config.platinum_min_sells_per_month_requirement
            min_rating = float(config.platinum_min_rating_promedy_requirement)
        else:
            min_sales = 100
            min_rating = 4.5

        sales_volume = abs(
            InventoryItemTransaction.objects.filter(
                item__store__company=company,
                transaction_type=1,
                creation__gte=thirty_days_ago,
            ).aggregate(total_sold=Sum('units'))['total_sold'] or 0
        )

        if sales_volume < min_sales:
            return PlatinumEvaluator._update_status(company, False)

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