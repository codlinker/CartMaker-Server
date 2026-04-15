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

@admin.register(User)
class UserAdmin(ModelAdmin):
    list_display = ("email", "full_name", "user_type_label", "is_external_account", "cedula_verified_status", "is_active", "gender")
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

# --- MÓDULO 2 & 3: COMERCIO E INVENTARIO ---

@admin.register(Company)
class CompanyAdmin(ModelAdmin):
    list_display = ("name", "owner", "category", "creation")
    inlines = [StoreInline]

@admin.register(CompanyStore)
class CompanyStoreAdmin(ModelAdmin):
    list_display = ("name", "company", "creation")
    filter_horizontal = () 

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
    list_display = ("id", "client", "store", "status_pill", "withdrawal_type", "creation")
    list_filter = ("status", "withdrawal_type")
    readonly_fields = ("creation", "end_time")

    @display(description="Estado", label={
        OrderStatus.WAITING: "info",
        OrderStatus.COMPLETED: "success",
        OrderStatus.CANCELLED: "danger",
        OrderStatus.RESOLVED: "warning",
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

@admin.register(MerchantPlanPayment)
@admin.register(AtlasPlusPlanPayment)
class PaymentAdmin(ModelAdmin):
    list_display = ("reference_number", "amount", "status_label", "verified_at")
    list_filter = ("status", "payment_method")

    @display(description="Estado Pago", label=True)
    def status_label(self, obj):
        return obj.get_status_display()

@admin.register(AtlasPlusPlan)
class AtlasPlusPlanAdmin(ModelAdmin):
    list_display = ("user", "is_active", "valid_until")

@admin.register(AtlasThread)
class AtlasThreadAdmin(ModelAdmin):
    list_display = ("plan", "summary_short")
    def summary_short(self, obj):
        return obj.summary[:50] if obj.summary else "Sin resumen"

# --- MÓDULO 9: ANALÍTICAS (DINÁMICAS) ---

@admin.register(ProductViewLog)
class ProductViewLogAdmin(ModelAdmin):
    list_display = ("client", "inventory_item", "added_to_cart", "bought", "start_time")
    list_filter = ("added_to_cart", "bought")

@admin.register(StoreViewLog)
class StoreViewLogAdmin(ModelAdmin):
    list_display = ("client", "join_time", "exit_time", "location_watched")

# --- REGISTRO DE TODAS LAS TABLAS RESTANTES ---

# Modelos Geográficos
@admin.register(ClientLocation, StoreLocation)
class GeoAdmin(GISModelAdmin, ModelAdmin):
    gis_widget_kwargs = {
        'attrs': {
            'default_lon': -66.6115, 
            'default_lat': 10.4686,  
            'default_zoom': 14,      
        }
    }
    list_display = ("coordinates", "name")
    
    class Media:
        css = {
            'all': ('css/admin_map_fix.css',)
        }

@admin.register(Announcement)
class AnnouncementAdmin(ModelAdmin):
    list_display = ("active", "banner_img", "navigate_to", "creation")

# Modelos de Soporte y Configuración (Registro Simple con Estilo Unfold)
others = [
    CompanyCategory, Category, SubCategory, InventoryItemOffer, 
    InventoryItemTransaction, InventoryItemQuestion, OrderCancellationTopic, 
    TokenWalletTransaction, StoreCalification, ProductCalification, 
    MerchantCalification, SupportTicket, MerchantPlan, AtlasMessage, 
    SystemConfig, UserNavigationLog, ClientContactMethod, 
    StoreContactMethod
]

for m in others:
    admin.site.register(m, ModelAdmin)