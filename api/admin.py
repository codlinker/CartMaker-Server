from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline, StackedInline
from unfold.decorators import display
from django.contrib.gis.admin import GISModelAdmin
from .models import *

# --- CONFIGURACIÓN DE INLINES PARA RELACIONES ---

class StoreInline(TabularInline):
    model = CompanyStore
    extra = 0

class InventoryItemInline(StackedInline): # Stacked para ver mejor los detalles de stock
    model = InventoryItem
    extra = 0

class OrderTransactionInline(TabularInline):
    model = TokenWalletTransaction
    extra = 0

# --- MÓDULO 1: USUARIOS ---

@admin.register(Notification)
class NotificationAdmin(ModelAdmin):
    list_display = ('id', 'user', 'section', 'category', 'is_read', 'created_at')

@admin.register(User)
class UserAdmin(ModelAdmin):
    list_display = ('id', "email", "full_name", "user_type_label", "is_external_account", "cedula_verified_status", "is_active", "gender")
    list_filter = ("user_type", "cedula_verified", "is_active", "gender")
    search_fields = ("email", "first_name", "last_name", "is_external_account")
    
    @display(description="Tipo Usuario", label=True)
    def user_type_label(self, obj):
        return obj.get_user_type_display()

    @display(description="Identidad verificada", boolean=True)
    def cedula_verified_status(self, obj):
        return obj.cedula_verified

    @display(description="Nombres")
    def full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"
    
@admin.register(UserWallet)
class UserWalletAdmin(ModelAdmin):
    list_display = ('id', 'user','balance')

# --- MÓDULO 2 & 3: COMERCIO E INVENTARIO ---

@admin.register(Company)
class CompanyAdmin(ModelAdmin):
    list_display = ("name", "owner", "category", "main_work_hours", "creation")
    inlines = [StoreInline]

@admin.register(CompanyStore)
class CompanyStoreAdmin(ModelAdmin):
    list_display = ("id", "name", 'is_main_store', "company", "creation")
    list_filter = ('company',)

@admin.register(Product)
class ProductAdmin(ModelAdmin):
    list_display = ("name", "company", "price", "category", "token_enabled")
    list_filter = ("company", "category", "discounts_by_tokens_active")
    inlines = [InventoryItemInline]

    @display(description="Usa Tokens", boolean=True)
    def token_enabled(self, obj):
        return obj.discounts_by_tokens_active

@admin.register(InventoryItem)
class InventoryItemAdmin(ModelAdmin):
    list_display = ("product", "stock", "custom_price", "paused", "expiration_date")
    list_editable = ("stock", "paused")
    list_filter = ("paused", "product__company")

@admin.register(Employee)
class EmployeeAdmin(ModelAdmin):
    list_display = ("user", "company", "is_active", "hired_at")
    list_filter = ("company", "is_active")

@admin.register(EmployeePermission)
class EmployeePermissionAdmin(ModelAdmin):
    list_display = ("employee", "can_edit_inventory", "can_view_sales", "can_manage_orders")
    list_filter = ("can_edit_inventory", "can_view_sales", "can_manage_orders")

@admin.register(EmployeeStoreAssignment)
class EmployeeStoreAssignmentAdmin(ModelAdmin):
    list_display = ("employee", "store")
    list_filter = ("store",)

# --- MÓDULO 4: VENTAS Y FIDELIZACIÓN ---

@admin.register(Order)
class OrderAdmin(ModelAdmin):
    list_display = ("id", "client", "store", 'client_location', "status_pill", "withdrawal_type", "creation")
    list_filter = ("status", "withdrawal_type")
    readonly_fields = ("creation", "end_time")

    @display(description="Estado", label={
        OrderStatus.WAITING: "info",
        OrderStatus.COMPLETED: "success",
        OrderStatus.CANCELLED: "danger",
        OrderStatus.SOLVED: "warning",
    })
    def status_pill(self, obj):
        return obj.get_status_display()

@admin.register(TokenWallet)
class TokenWalletAdmin(ModelAdmin):
    list_display = ("user", "company", "balance")
    search_fields = ("user__email", "company__name")

# --- MÓDULO 6 & 7: SUSCRIPCIONES Y ATLAS AI ---

@admin.register(MerchantSubscription)
class MerchantSubscriptionAdmin(ModelAdmin):
    list_display = ("merchant", "plan", "valid_until", "merchant_type")
    list_filter = ("plan", "merchant_type")

@admin.register(MerchantPlanPayment, AtlasPlusPlanPayment)
class PaymentAdmin(ModelAdmin):
    list_display = ("reference_number", "amount", "status", 'bcv_taxes_to_day', 'creation')
    
    # Lo dejamos en readonly para que el admin pueda leer qué texto se le envió al usuario, pero no editarlo
    readonly_fields = ('reference_number', 'amount', 'bcv_taxes_to_day', "verified_at", 'payment_proof_preview', 'creation', 'rejection_help')
    
    list_filter = ("status", "rejection_reason")
    
    fieldsets = (
        ('Detalles del Pago', {
            'fields': ('reference_number', 'amount', 'bcv_taxes_to_day', 'creation', 'payment_proof_preview')
        }),
        ('Estado de Verificación', {
            # 💡 Está rejection_reason (editable) y rejection_help (readonly visual)
            'fields': ('status', 'rejection_reason', 'rejection_help')
        }),
    )

    class Media:
        js = ('js/admin/subscriptions_payment.js',)

    def formfield_for_choice_field(self, db_field, request, **kwargs):
        if db_field.name == 'rejection_reason':
            kwargs['choices'] = [
                choice for choice in RejectionReason.choices
            ]
            kwargs['choices'].insert(0, ('', '---------'))
            
        return super().formfield_for_choice_field(db_field, request, **kwargs)

@admin.register(AtlasPlusPlan)
class AtlasPlusPlanAdmin(ModelAdmin):
    list_display = ("user", "valid_until")

@admin.register(AtlasThread)
class AtlasThreadAdmin(ModelAdmin):
    list_display = ("plan", "summary_short")
    def summary_short(self, obj):
        return obj.summary[:50] if obj.summary else "Sin resumen"

# --- MODELOS GEOGRÁFICOS ---
@admin.register(ClientLocation)
class GeoAdmin(GISModelAdmin, ModelAdmin):
    gis_widget_kwargs = {
        'attrs': {
            'default_lon': -66.6115, 
            'default_lat': 10.4686,  
            'default_zoom': 14,      
        }
    }
    list_display = ("user", "coordinates", "name")
    
    class Media:
        css = {
            'all': ('css/admin_map_fix.css',)
        }

@admin.register(StoreLocation)
class GeoAdmin(GISModelAdmin, ModelAdmin):
    gis_widget_kwargs = {
        'attrs': {
            'default_lon': -66.6115, 
            'default_lat': 10.4686,  
            'default_zoom': 14,      
        }
    }
    list_display = ("store", "coordinates", "name")
    
    class Media:
        css = {
            'all': ('css/admin_map_fix.css',)
        }

@admin.register(Mall)
class MallAdmin(GISModelAdmin, ModelAdmin):
    gis_widget_kwargs = {
        'attrs': {
            'default_lon': -66.6115, 
            'default_lat': 10.4686,  
            'default_zoom': 14,      
        }
    }

    list_display = ("name", 'floors_quantity', "coordinates", 'img_url')
    search_fields = ('name',)
    
    class Media:
        css = {
            'all': ('css/admin_map_fix.css',)
        }

@admin.register(Announcement)
class AnnouncementAdmin(ModelAdmin):
    list_display = ("active", "banner_img", "navigate_to", "creation")

@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    list_display = ("id", "name", "img_url")

@admin.register(SubCategory)
class SubCategory(ModelAdmin):
    list_display = ("id", "name", "img_url", "parent_category")

@admin.register(MerchantPlan)
class MerchantPlanAdmin(ModelAdmin):
    list_display = ('name', 'price', 'inventory_capacity', 'products_registration_with_ia',
    'profile_histories', 'gamification_system', 'gamification_analytics', 'digital_performance_analytics',
    'clients_behavior_analytics', 'company_branches', 'company_employees')

@admin.register(CartMakerBankAccount)
class CartMakerBankAccountAdmin(ModelAdmin):
    list_display = ('bank', 'pago_movil_enabled', 'tlf', 'document_number', 'document_type', 'beneficiary_name')

@admin.register(DeviceToken)
class DeviceTokenAdmin(ModelAdmin):
    list_display = ('user', 'token', 'creation', 'platform')

@admin.register(CompanyCategory)
class CompanyCategoryAdmin(ModelAdmin):
    list_display = ('id', 'name')

@admin.register(StoreContactMethod)
class StoreContactMethodAdmin(ModelAdmin):
    list_display = ('id', 'store', 'method_type','value')

# =========================================================================
# 💡 MÓDULO 9: ANALÍTICAS (Optimizadas para Unfold)
# =========================================================================

@admin.register(ProductViewLog)
class ProductViewLogAdmin(ModelAdmin):
    list_display = ("client", "inventory_item", "origin_source", "duration_seconds", "added_to_cart_icon", "bought_icon", "start_time")
    list_filter = ("added_to_cart", "bought", "start_time")
    search_fields = ("client__email", "client__first_name", "inventory_item__product__name")
    readonly_fields = ("start_time", "end_time")
    date_hierarchy = "start_time"

    @display(description="Duración (Segs)")
    def duration_seconds(self, obj):
        if obj.end_time and obj.start_time:
            return (obj.end_time - obj.start_time).seconds
        return "-"

    @display(description="Carrito", boolean=True)
    def added_to_cart_icon(self, obj):
        return obj.added_to_cart

    @display(description="Comprado", boolean=True)
    def bought_icon(self, obj):
        return obj.bought


@admin.register(StoreViewLog)
class StoreViewLogAdmin(ModelAdmin):
    # 💡 Añadimos "store" a las columnas visibles
    list_display = ("client", "store", "join_time", "duration_seconds", "engagement_summary")
    list_filter = ("location_watched", "presentation_video_watched", "stories_watched", "products_watched", "store__company")
    search_fields = ("client__email", "store__name", "store__company__name")
    date_hierarchy = "join_time"

    @display(description="Duración (Segs)")
    def duration_seconds(self, obj):
        if obj.exit_time and obj.join_time:
            return (obj.exit_time - obj.join_time).seconds
        return "-"

    @display(description="Acciones Tomadas")
    def engagement_summary(self, obj):
        actions = []
        if obj.location_watched: actions.append("📍 Mapa")
        if obj.presentation_video_watched: actions.append("🎬 Intro")
        if obj.stories_watched: actions.append("📱 Historias")
        if obj.products_watched: actions.append("🛍️ Productos")
        if obj.tryed_to_contact: actions.append("💬 Contacto")
        return " | ".join(actions) if actions else "Solo visita"


@admin.register(UserNavigationLog)
class UserNavigationLogAdmin(ModelAdmin):
    list_display = ("user", "login_time", "logout_time", "screens_visited_count")
    list_filter = ("login_time",)
    search_fields = ("user__email",)
    date_hierarchy = "login_time"

    @display(description="Pantallas Visitadas")
    def screens_visited_count(self, obj):
        if obj.navigation_record and isinstance(obj.navigation_record, dict):
            return len(obj.navigation_record.keys())
        return 0


# =========================================================================
# 💡 MÓDULO 10: RED SOCIAL & ENGAGEMENT (Optimizados para Unfold)
# =========================================================================

@admin.register(CompanyVideoStory)
class CompanyVideoStoryAdmin(ModelAdmin):
    list_display = ("id", "company", "duration_seconds", "associated_item_link", "views_count", "is_active", "creation")
    list_filter = ("company", "creation")
    search_fields = ("company__name", "description")
    readonly_fields = ("creation", "views_count")
    date_hierarchy = "creation"
    
    fieldsets = (
        ('Contexto del Video', {
            'fields': ('company', 'associated_item', 'description')
        }),
        ('Multimedia', {
            'fields': ('video_file', 'thumbnail', 'duration_seconds')
        }),
        ('Métricas y Ciclo de Vida', {
            'fields': ('views_count', 'creation', 'expires_at')
        }),
    )

    @display(description="Producto Enlazado")
    def associated_item_link(self, obj):
        return obj.associated_item.product.name if obj.associated_item else "Ninguno"

    @display(description="Estado", boolean=True)
    def is_active(self, obj):
        return obj.is_media_available


@admin.register(UniversalLike)
class UniversalLikeAdmin(ModelAdmin):
    list_display = ("user", "content_type", "content_object_display", "creation")
    list_filter = ("content_type", "creation")
    search_fields = ("user__email", "object_id")
    readonly_fields = ("creation",)
    date_hierarchy = "creation"

    @display(description="Elemento que recibió el Like")
    def content_object_display(self, obj):
        return str(obj.content_object) if obj.content_object else f"ID: {obj.object_id} (Huérfano)"


@admin.register(UniversalComment)
class UniversalCommentAdmin(ModelAdmin):
    list_display = ("client", "content_type", "short_question", "has_answer", "question_creation")
    list_filter = ("content_type", "question_creation", "answer_creation")
    search_fields = ("client__email", "question_text", "answer_text")
    readonly_fields = ("question_creation", "answer_creation")
    
    fieldsets = (
        ('Referencias', {
            'fields': ('client', 'content_type', 'object_id')
        }),
        ('Interacción del Cliente', {
            'fields': ('question_text', 'question_creation')
        }),
        ('Respuesta del Comercio', {
            'fields': ('answer_text', 'answer_creation')
        }),
    )

    @display(description="Duda del Cliente")
    def short_question(self, obj):
        return obj.question_text[:40] + "..." if len(obj.question_text) > 40 else obj.question_text

    @display(description="¿Respondida?", boolean=True)
    def has_answer(self, obj):
        return bool(obj.answer_text)


@admin.register(VideoEngagementLog)
class VideoEngagementLogAdmin(ModelAdmin):
    list_display = ("client", "video_company", "watch_time_seconds", "engagement_score", "timestamp")
    list_filter = ("video_completed", "interacted_with_product", "added_to_cart_from_video", "bought_from_video", "timestamp")
    search_fields = ("client__email", "video__company__name")
    date_hierarchy = "timestamp"

    @display(description="Empresa del Video")
    def video_company(self, obj):
        return obj.video.company.name if obj.video else "Desconocida"

    @display(description="Nivel de Interacción")
    def engagement_score(self, obj):
        score = 0
        if obj.video_completed: score += 1
        if obj.interacted_with_product: score += 1
        if obj.added_to_cart_from_video: score += 1
        if obj.bought_from_video: score += 1
        
        badges = ["👀 Visto", "🎯 Completado", "🛒 Carrito", "🛍️ Compra!"]
        return badges[score - 1] if score > 0 else "Ignorado"
    
@admin.register(UnmetDemandLog)
class UnmetDemandLogAdmin(ModelAdmin):
    list_display = ('client', 'search_term', 'coordinates', 'creation')

others = [
    InventoryItemOffer, 
    InventoryItemTransaction, OrderCancellationTopic, 
    TokenWalletTransaction, ProductCalification, 
    MerchantCalification, SupportTicket, AtlasMessage, 
    SystemConfig, ClientContactMethod
]

for m in others:
    admin.site.register(m, ModelAdmin)