import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.contrib.gis.db import models as gis_models
from pgvector.django import HnswIndex, VectorField
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from .cos import storage_manager

# ==========================================
# ENUMS (Para validación automática en DRF)
# ==========================================

class UserGender(models.IntegerChoices):
    """
    ENUM Genero del usuario.
    """
    MALE = 0, _('Masculino'),
    FEMALE = 1, _('Femenino'),
    NO_BINARY = 2, _("No Binario")

class UserType(models.IntegerChoices):
    """
    ENUM Tipo de usuario.
    """
    CLIENT = 0, _('Cliente')
    MERCHANT = 1, _('Vendedor')
    ADMIN = 2, _('Administrador')

class UserNacionality(models.IntegerChoices):
    """
    ENUM Nacionalidad del usuario.
    """
    VENEZOLANO = 0, _('Venezolano')
    EXTRANJERO = 1, _('Extranjero')

class ContactMethodType(models.IntegerChoices):
    """
    ENUM Tipo de metodo de contacto.
    """
    INSTAGRAM = 0, _('Instagram')
    WHATSAPP = 1, _('Whatsapp')
    PHONE = 2, _('Llamada')

class TransactionType(models.IntegerChoices):
    """
    ENUM Tipo de transaccion.
    """
    INCOME = 0, _('Ingreso')
    OUTCOME = 1, _('Egreso')

class OrderStatus(models.IntegerChoices):
    """
    ENUM Estado de la orden.
    """
    WAITING = 0, _('Esperando')
    CANCELLED = 3, _('Cancelada')
    COMPLETED = 4, _('Completada')
    RESOLVED = 5, _('Resuelta')

class WithdrawalType(models.IntegerChoices):
    """
    ENUM Tipo de retiro de la orden.
    """
    PICKUP = 0, _('En tienda')
    DELIVERY = 1, _('Delivery')

class MerchantType(models.IntegerChoices):
    """
    ENUM Tipo de comerciante.
    """
    ENTREPRENEUR = 0, _('Emprendedor')
    BUSINESS = 1, _('Empresa')

class PaymentStatus(models.IntegerChoices):
    """
    ENUM Estado del pago.
    """
    PENDING = 0, _('Pendiente')
    APPROVED = 1, _('Aprobada')
    REJECTED = 2, _('Rechazada')

class PaymentMethod(models.IntegerChoices):
    """
    ENUM Metodo de pago.
    """
    TRANSFER = 0, _('Transferencia')
    MOBILE_PAYMENT = 1, _('Pago Móvil')

class MessageOrigin(models.IntegerChoices):
    """
    ENUM Origen del mensaje de la conversacion con Atlas.
    """
    CLIENT = 0, _('Cliente')
    ATLAS = 1, _('Atlas')

# ==========================================
# MÓDULO 1: USUARIOS Y CLIENTES
# ==========================================

class UserManager(BaseUserManager):
    use_in_migrations = True

    def get_by_natural_key(self, email):
        return self.get(email=email)

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('El email es obligatorio')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('user_type', UserType.ADMIN)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser debe tener is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser debe tener is_superuser=True.')

        return self.create_user(email, password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
    """
    Modelo personalizado de usuario para la plataforma.

    Attributes:
        id (int): ID único del usuario (autoincremental por defecto).
        first_name (str): Nombre del usuario.
        last_name (str): Apellido del usuario.
        email (str): Correo electrónico único.
        nacionality (int): Nacionalidad del usuario.
        password (str): Hash de la clave de acceso.
        birth_date (datetime): Fecha de nacimiento.
        email_verified (bool): Indica si el correo fue validado.
        creation (datetime): Fecha y hora de registro.
        user_type (int): Rol del usuario (Cliente, Comerciante, etc.).
        profile_picture (str): URL de la imagen de perfil.
        cedula_document (str): URL del documento de identidad subido.
        cedula_verified (bool): Estado de verificación legal de la identidad.
        cedula_number (str): Número de identificación legal (Cédula/DNI).
        biometric_vector (vector): Vector de 512 dimensiones para reconocimiento facial.
        gender (int): Genero del usuario.
        is_external_account (bool): Indica si es una cuenta de Google o Apple.
    """
    username = None
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    email = models.EmailField(unique=True)
    nacionality = models.IntegerField(default=None, null=True, blank=True, choices=UserNacionality)
    email_verified = models.BooleanField(default=False)
    creation = models.DateTimeField(auto_now_add=True)
    user_type = models.IntegerField(choices=UserType.choices, default=UserType.CLIENT)
    profile_picture = models.CharField(max_length=500, default="")
    cedula_document = models.CharField(max_length=500, null=True, blank=True)
    cedula_verified = models.BooleanField(default=False)
    cedula_number = models.CharField(max_length=50, null=True, blank=True)
    biometric_vector = VectorField(dimensions=192, null=True, blank=True)
    gender = models.IntegerField(choices=UserGender.choices, default=UserGender.MALE)
    is_external_account = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'password']

    class Meta:
        # Aquí sumamos, no restamos.
        indexes = [
            HnswIndex(
                name='user_biometric_hsnw_idx',
                fields=['biometric_vector'],
                m=16,
                ef_construction=64,
                opclasses=['vector_cosine_ops']
            ),
        ]
    
    def __str__(self)-> str:
        return f"{self.first_name} {self.last_name} ({self.email})"

    def get_profile_picture_url(self) -> str:
        """
        Retorna la URL publica de la foto de perfil del usuario.
        """
        return self.profile_picture if self.profile_picture.startswith('http')\
              else storage_manager.get_url(self.profile_picture)

class ClientLocation(models.Model):
    """
    Direcciones guardadas por los clientes.

    Attributes:
        user (ForeignKey): Referencia al usuario dueño de la ubicación.
        coordinates (Point): Coordenadas espaciales (Lat, Lon).
        name (str): Etiqueta de la ubicación (ej: 'Casa', 'Trabajo').
        is_default (str): Indica si esta es la ubicacion seleccionada por el usuario como predeterminada.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='locations')
    coordinates = gis_models.PointField()
    name = models.CharField(max_length=255)
    is_default = models.BooleanField(default=False)

    def get_json(self)->dict:
        return {
            'id':self.id,
            'latitude':self.coordinates.y,
            'longitude':self.coordinates.x,
            'name':self.name,
            'is_default':self.is_default
        }

class ClientContactMethod(models.Model):
    """
    Métodos de contacto adicionales para el cliente (Teléfono, RRSS).

    Attributes:
        client (ForeignKey): Usuario asociado.
        method_type (int): Tipo de contacto (WhatsApp, Telegram, etc.).
        value (str): El dato de contacto (número o username).
    """
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='contact_methods')
    method_type = models.IntegerField(choices=ContactMethodType.choices)
    value = models.CharField(max_length=255)

    def get_json(self)->dict:
        return {
            "id":self.id,
            'method_type':self.method_type,
            'value':self.value
        }


# ==========================================
# MÓDULO 2: COMPAÑÍA Y TIENDAS
# ==========================================

class CompanyCategory(models.Model):
    """
    Categoría legal o comercial de una empresa.

    Attributes:
        name (str): Nombre de la categoría (ej: 'Farmacia', 'Supermercado').
    """
    name = models.CharField(max_length=255)

class Company(models.Model):
    """
    Entidad legal que agrupa una o más tiendas.

    Attributes:
        id (uuid): Identificador único global de la compañía.
        name (str): Nombre comercial.
        owner (ForeignKey): Usuario dueño de la empresa.
        creation (datetime): Fecha de registro de la empresa.
        category (ForeignKey): Rubro al que pertenece.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='companies')
    creation = models.DateTimeField(auto_now_add=True)
    category = models.ForeignKey(CompanyCategory, on_delete=models.SET_NULL, null=True)

class CompanyStore(models.Model):
    """
    Sucursal física o virtual de una compañía.

    Attributes:
        id (uuid): ID único de la tienda.
        company (ForeignKey): Compañía a la que pertenece.
        name (str): Nombre de la sucursal.
        creation (datetime): Fecha de apertura en la plataforma.
        business_hours (json): Horarios de atención por día.
        image (str): URL de la imagen de fachada o logo de la tienda.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='stores')
    name = models.CharField(max_length=255)
    creation = models.DateTimeField(auto_now_add=True)
    business_hours = models.JSONField(default=dict)
    image = models.URLField(max_length=500, null=True, blank=True)

class StoreLocation(models.Model):
    """
    Ubicación geográfica de una sucursal.

    Attributes:
        store (OneToOne): Tienda asociada.
        coordinates (Point): Punto geográfico para mapas.
        name (str): Dirección legible.
        details (str): Referencias adicionales de la ubicación.
        creation (datetime): Fecha de registro de la ubicación.
    """
    store = models.OneToOneField(CompanyStore, on_delete=models.CASCADE, related_name='location')
    coordinates = gis_models.PointField()
    name = models.CharField(max_length=255)
    details = models.TextField(null=True, blank=True)
    creation = models.DateTimeField(auto_now_add=True)

class StoreContactMethod(models.Model):
    """
    Canales de comunicación directa de una tienda.

    Attributes:
        store (ForeignKey): Sucursal asociada.
        method_type (int): Tipo de canal (Teléfono fijo, WhatsApp).
        value (str): Dato del contacto.
    """
    store = models.ForeignKey(CompanyStore, on_delete=models.CASCADE, related_name='contact_methods')
    method_type = models.IntegerField(choices=ContactMethodType.choices)
    value = models.CharField(max_length=255)

class Employee(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="employment_records")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="employees")
    is_active = models.BooleanField(default=True)
    hired_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'company') # Un usuario no puede ser empleado dos veces de la misma empresa

class EmployeePermission(models.Model):
    employee = models.OneToOneField(Employee, on_delete=models.CASCADE, related_name="permissions")
    allowed_stores = models.ManyToManyField(
        'CompanyStore', 
        blank=True,
        related_name="assigned_employees"
    )
    can_edit_inventory = models.BooleanField(default=False)
    can_view_sales = models.BooleanField(default=False)
    can_manage_orders = models.BooleanField(default=True)

class EmployeeStoreAssignment(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    store = models.ForeignKey(CompanyStore, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('employee', 'store')


# ==========================================
# MÓDULO 3: PRODUCTOS E INVENTARIO
# ==========================================

class Category(models.Model):
    """
    Categoría principal de productos.

    Attributes:
        name (str): Nombre del sector (ej: 'Alimentos', 'Electrónica').
    """
    name = models.CharField(max_length=255)
    img_url = models.CharField(help_text="Colocar ruta a traves del endpoint static del servidor. Ej: static/img/test.png", blank=True, null=True)

    def get_json(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "img_url": f"{settings.DOMAIN}/{self.img_url}",
            "sub_categories": [{
                "id": sub.id,
                "name": sub.name,
                "img_url": self.get_img_url()
            } for sub in self.subcategories.all()] 
        }
    
    def get_img_url(self) -> str:
        """
        Retorna la URL publica de la imagen de la categoria.
        """
        return self.img_url if self.img_url.startswith('http')\
              else storage_manager.get_url(self.img_url)

class SubCategory(models.Model):
    """
    Sub-segmento de productos.

    Attributes:
        name (str): Nombre de la subcategoría.
        parent_category (ForeignKey): Categoría padre.
    """
    name = models.CharField(max_length=255)
    parent_category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='subcategories')
    img_url = models.CharField(help_text="Colocar ruta a traves del endpoint static del servidor. Ej: static/img/test.png", blank=True, null=True)

    def get_json(self) -> dict:
        return {
            "id":self.id,
            "name":self.name,
            "parent_category":self.parent_category.id,
            "img_url":self.get_img_url()
        }
    
    def get_img_url(self) -> str:
        """
        Retorna la URL publica de la imagen de la sub-categoria.
        """
        return self.img_url if self.img_url.startswith('http')\
              else storage_manager.get_url(self.img_url)

class Product(models.Model):
    """
    Catálogo maestro de productos por compañía.

    Attributes:
        id (uuid): ID único del producto.
        name (str): Nombre descriptivo del artículo.
        price (Decimal): Precio base de referencia.
        creation (datetime): Fecha de registro.
        category (ForeignKey): Subcategoría asignada.
        description (str): Detalles técnicos o comerciales.
        discounts_by_tokens_active (bool): Habilita canje de tokens.
        discounts_data (json): Configuración de reglas de descuento.
        company (ForeignKey): Empresa propietaria del producto.
        images (json): Lista de URLs de imágenes del producto.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    creation = models.DateTimeField(auto_now_add=True)
    category = models.ForeignKey(SubCategory, on_delete=models.SET_NULL, null=True)
    description = models.TextField()
    discounts_by_tokens_active = models.BooleanField(default=False)
    discounts_data = models.JSONField(default=dict, blank=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='products')
    images = models.JSONField(default=list)
    # Ejemplo de 'images':
    # [
    #     {
    #         "image_url": "https://...",
    #         "idx": 0,
    #         "apply_transparency": true,
    #         "transparency_color": "#00FF00"
    #     },
    #     {
    #         "image_url": "https://...",
    #         "idx": 1,
    #         "apply_transparency": false,
    #         "transparency_color": null
    #     }
    # ]

class InventoryItem(models.Model):
    """
    Existencias reales de un producto en inventario.

    Attributes:
        id (uuid): ID único del lote/ítem.
        product (ForeignKey): Producto del catálogo.
        stock (int): Unidades disponibles.
        creation (datetime): Fecha de ingreso a inventario.
        sold_out_time (datetime): Momento en que se agotó el stock.
        expiration_date (datetime): Fecha de vencimiento (si aplica).
        custom_price (Decimal): Precio específico para este lote.
        paused (bool): Indica si el ítem está oculto para la venta.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='inventory_items')
    stock = models.IntegerField(default=0)
    creation = models.DateTimeField(auto_now_add=True)
    sold_out_time = models.DateTimeField(null=True, blank=True)
    expiration_date = models.DateTimeField(null=True, blank=True)
    custom_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    paused = models.BooleanField(default=False)

class InventoryItemOffer(models.Model):
    """
    Promociones temporales aplicadas a ítems específicos.

    Attributes:
        product_item (OneToOne): Ítem en oferta.
        valid_until (datetime): Fecha de expiración de la oferta.
        percentage (int): Porcentaje de descuento aplicado.
    """
    product_item = models.OneToOneField(InventoryItem, on_delete=models.CASCADE, related_name='offer')
    valid_until = models.DateTimeField()
    percentage = models.IntegerField()

class InventoryItemTransaction(models.Model):
    """
    Historial de movimientos de stock (Entradas/Salidas).

    Attributes:
        item (ForeignKey): Ítem afectado.
        units (int): Cantidad de unidades movidas.
        transaction_type (int): Tipo (Venta, Reposición, Ajuste).
        creation (datetime): Fecha del movimiento.
    """
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='transactions')
    units = models.IntegerField()
    transaction_type = models.IntegerField(choices=TransactionType.choices)
    creation = models.DateTimeField(auto_now_add=True)

class InventoryItemQuestion(models.Model):
    """
    Interacción de preventa entre cliente y comercio.

    Attributes:
        client (ForeignKey): Usuario que pregunta.
        item (ForeignKey): Ítem consultado.
        question_text (str): Contenido de la pregunta.
        question_creation (datetime): Fecha de la pregunta.
        answer_text (str): Respuesta del comercio.
        answer_creation (datetime): Fecha de la respuesta.
    """
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='questions_asked')
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    question_creation = models.DateTimeField(auto_now_add=True)
    answer_text = models.TextField(null=True, blank=True)
    answer_creation = models.DateTimeField(null=True, blank=True)


# ==========================================
# MÓDULO 4: VENTAS Y FIDELIZACIÓN
# ==========================================

class OrderCancellationTopic(models.Model):
    """
    Razones predefinidas para la cancelación de pedidos.

    Attributes:
        name (str): Motivo (ej: 'Falta de stock', 'Cliente no retiró').
    """
    name = models.CharField(max_length=255)

class Order(models.Model):
    """
    Registro de transacciones de compra.

    Attributes:
        store (ForeignKey): Tienda donde se realizó el pedido.
        client (ForeignKey): Usuario que realizó la compra.
        cart (json): Snapshot de los productos comprados y sus precios.
        creation (datetime): Fecha de creación del pedido.
        end_time (datetime): Fecha de finalización o entrega.
        status (int): Estado actual (Pendiente, Pagado, Entregado).
        cancellation_topic (ForeignKey): Razón en caso de ser cancelada.
        withdrawal_type (int): Método de entrega (Delivery, Pickup).
    """
    store = models.ForeignKey(CompanyStore, on_delete=models.CASCADE, related_name='orders')
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    cart = models.JSONField()
    creation = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    status = models.IntegerField(choices=OrderStatus.choices, default=OrderStatus.WAITING)
    cancellation_topic = models.ForeignKey(OrderCancellationTopic, on_delete=models.SET_NULL, null=True, blank=True)
    withdrawal_type = models.IntegerField(choices=WithdrawalType.choices)

class TokenWallet(models.Model):
    """
    Billetera de puntos de fidelidad por compañía.

    Attributes:
        id (uuid): ID de la billetera.
        user (ForeignKey): Cliente dueño de los tokens.
        company (ForeignKey): Empresa que emitió los tokens.
        balance (int): Cantidad de tokens disponibles.
        creation (datetime): Fecha de apertura de la billetera.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='token_wallets')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='issued_wallets')
    balance = models.IntegerField(default=0)
    creation = models.DateTimeField(auto_now_add=True)

class TokenWalletTransaction(models.Model):
    """
    Movimientos de tokens (Ganados/Gastados).

    Attributes:
        token_wallet (ForeignKey): Billetera afectada.
        amount (int): Cantidad de tokens transaccionados.
        creation (datetime): Fecha de la transacción.
        transaction_type (int): Tipo (Compra, Recompensa, Ajuste).
        order (ForeignKey): Pedido asociado a la transacción (opcional).
    """
    token_wallet = models.ForeignKey(TokenWallet, on_delete=models.CASCADE, related_name='transactions')
    amount = models.IntegerField()
    creation = models.DateTimeField(auto_now_add=True)
    transaction_type = models.IntegerField(choices=TransactionType.choices)
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True)


# ==========================================
# MÓDULO 5: CALIFICACIONES Y SOPORTE
# ==========================================

class StoreCalification(models.Model):
    """
    Reseñas de clientes sobre sucursales.

    Attributes:
        store (ForeignKey): Tienda calificada.
        client (ForeignKey): Usuario que califica.
        creation (datetime): Fecha de la reseña.
        rating (int): Puntaje otorgado (1-5).
    """
    store = models.ForeignKey(CompanyStore, on_delete=models.CASCADE, related_name='califications')
    client = models.ForeignKey(User, on_delete=models.CASCADE)
    creation = models.DateTimeField(auto_now_add=True)
    rating = models.IntegerField()

class ProductCalification(models.Model):
    """
    Valoración individual de productos.

    Attributes:
        product (ForeignKey): Producto calificado.
        client (ForeignKey): Usuario que califica.
        creation (datetime): Fecha de la valoración.
        rating (float): Puntaje del producto.
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='califications')
    client = models.ForeignKey(User, on_delete=models.CASCADE)
    creation = models.DateTimeField(auto_now_add=True)
    rating = models.FloatField()

class MerchantCalification(models.Model):
    """
    Reputación general del comerciante/compañía.

    Attributes:
        merchant (ForeignKey): Compañía calificada.
        client (ForeignKey): Usuario que califica.
        creation (datetime): Fecha de la calificación.
        rating (float): Puntaje reputacional.
    """
    merchant = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='califications')
    client = models.ForeignKey(User, on_delete=models.CASCADE)
    creation = models.DateTimeField(auto_now_add=True)
    rating = models.FloatField()

class SupportTicket(models.Model):
    """
    Gestión de incidencias y soporte técnico.

    Attributes:
        client (ForeignKey): Usuario que reporta el problema.
        agent (ForeignKey): Usuario del staff que atiende el ticket.
        closed (bool): Estado de resolución.
        conversation (json): Historial de mensajes del ticket.
        creation (datetime): Apertura del ticket.
        close_time (datetime): Cierre del ticket.
        waiting_for_client_reply (bool): Indica flujo de atención.
    """
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='support_tickets')
    agent = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='assigned_tickets')
    closed = models.BooleanField(default=False)
    conversation = models.JSONField(default=list)
    creation = models.DateTimeField(auto_now_add=True)
    close_time = models.DateTimeField(null=True, blank=True)
    waiting_for_client_reply = models.BooleanField(default=False)


# ==========================================
# MÓDULO 6: SUSCRIPCIONES Y PLANES
# ==========================================

class MerchantPlan(models.Model):
    """
    Definición de paquetes de servicios para comercios.

    Attributes:
        name (str): Nombre comercial del plan.
        price (Decimal): Costo mensual del plan.
        inventory_capacity (int): Límite de ítems permitidos.
        products_registration_with_ia (bool): Acceso a carga por IA.
        profile_histories (bool): Acceso a historias en perfil.
        gamification_system (bool): Acceso a sistema de tokens.
        gamification_analytics (bool): Métricas de fidelización.
        digital_performance_analytics (bool): Métricas de rendimiento.
        clients_behavior_analytics (bool): Métricas de comportamiento.
        operative_managment_analytics (bool): Métricas operativas.
        company_branches (bool): Permite múltiples sucursales.
    """
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    inventory_capacity = models.IntegerField()
    products_registration_with_ia = models.BooleanField(default=False)
    profile_histories = models.BooleanField(default=False)
    gamification_system = models.BooleanField(default=False)
    gamification_analytics = models.BooleanField(default=False)
    digital_performance_analytics = models.BooleanField(default=False)
    clients_behavior_analytics = models.BooleanField(default=False)
    operative_management_analytics = models.BooleanField(default=False)
    company_branches = models.BooleanField(default=False)
    company_employees = models.BooleanField(default=False)

    def get_json(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'price': float(self.price),
            'inventory_capacity': self.inventory_capacity,
            'products_registration_with_ia': self.products_registration_with_ia,
            'profile_histories': self.profile_histories,
            'gamification_system': self.gamification_system,
            'gamification_analytics': self.gamification_analytics,
            'digital_performance_analytics': self.digital_performance_analytics,
            'clients_behavior_analytics': self.clients_behavior_analytics,
            'operative_management_analytics': self.operative_management_analytics,
            'company_branches': self.company_branches,
            'company_employees': self.company_employees,
        }

class MerchantSubscription(models.Model):
    """
    Contrato activo entre un comercio y la plataforma.

    Attributes:
        id (uuid): ID único de suscripción.
        merchant (ForeignKey): Usuario dueño del comercio.
        plan (ForeignKey): Plan contratado.
        valid_until (datetime): Fecha de vencimiento del servicio.
        merchant_type (int): Clasificación (Personal, Empresa).
        rif_number (str): Identificación fiscal.
        company_document_url (str): URL del registro mercantil.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subscriptions')
    plan = models.ForeignKey(MerchantPlan, on_delete=models.PROTECT)
    valid_until = models.DateTimeField()
    merchant_type = models.IntegerField(choices=MerchantType.choices)
    rif_number = models.CharField(max_length=50, null=True, blank=True)
    company_document_url = models.URLField(max_length=500, null=True, blank=True)

class MerchantPlanPayment(models.Model):
    """
    Registro de pagos de suscripción.

    Attributes:
        subscription (ForeignKey): Suscripción a la que abona.
        reference_number (str): Número de confirmación bancaria.
        payment_proof_url (str): URL del comprobante capturado.
        amount (Decimal): Monto pagado.
        bcv_taxes_to_day (Decimal): Tasa de cambio oficial del día.
        status (int): Estado del pago (Pendiente, Verificado, Rechazado).
        verified_at (datetime): Fecha de validación por staff.
        payment_method (int): Método usado (Pago Móvil, Transferencia).
    """
    subscription = models.ForeignKey(MerchantSubscription, on_delete=models.CASCADE, related_name='payments')
    reference_number = models.CharField(max_length=100)
    payment_proof_url = models.URLField(max_length=500, null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    bcv_taxes_to_day = models.DecimalField(max_digits=10, decimal_places=4)
    status = models.IntegerField(choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    verified_at = models.DateTimeField(null=True, blank=True)
    payment_method = models.IntegerField(choices=PaymentMethod.choices)


# ==========================================
# MÓDULO 7: ATLAS AI
# ==========================================

class AtlasPlusPlan(models.Model):
    """
    Suscripción premium para el asistente inteligente Atlas.

    Attributes:
        id (uuid): ID único del plan.
        user (ForeignKey): Usuario beneficiario.
        is_active (bool): Estado del servicio premium.
        valid_until (datetime): Fecha de vencimiento.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='atlas_plans')
    is_active = models.BooleanField(default=True)
    valid_until = models.DateTimeField()

class AtlasPlusPlanPayment(models.Model):
    """
    Registro de pagos para Atlas Plus.

    Attributes:
        plan (ForeignKey): Plan al que abona.
        reference_number (str): Número de referencia bancaria.
        payment_proof_url (str): URL del comprobante.
        amount (Decimal): Monto en divisas.
        bcv_taxes_to_day (Decimal): Tasa oficial de cambio.
        status (int): Estado de verificación.
        verified_at (datetime): Fecha de aprobación.
        payment_method (int): Canal de pago.
    """
    plan = models.ForeignKey(AtlasPlusPlan, on_delete=models.CASCADE, related_name='payments')
    reference_number = models.CharField(max_length=100)
    payment_proof_url = models.URLField(max_length=500, null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    bcv_taxes_to_day = models.DecimalField(max_digits=10, decimal_places=4)
    status = models.IntegerField(choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    verified_at = models.DateTimeField(null=True, blank=True)
    payment_method = models.IntegerField(choices=PaymentMethod.choices)

class AtlasThread(models.Model):
    """
    Contexto de conversación persistente con la IA.

    Attributes:
        plan (ForeignKey): Suscripción asociada.
        summary (str): Resumen generado por la IA sobre la conversación.
    """
    plan = models.ForeignKey(AtlasPlusPlan, on_delete=models.CASCADE, related_name='threads')
    summary = models.TextField(null=True, blank=True)

class AtlasMessage(models.Model):
    """
    Mensajes individuales dentro de un hilo de Atlas.

    Attributes:
        conversation (ForeignKey): Hilo al que pertenece.
        origin (int): Quién envió el mensaje (Usuario o IA).
        creation (datetime): Fecha y hora del mensaje.
        text (str): Contenido del mensaje.
    """
    conversation = models.ForeignKey(AtlasThread, on_delete=models.CASCADE, related_name='messages')
    origin = models.IntegerField(choices=MessageOrigin.choices)
    creation = models.DateTimeField(auto_now_add=True)
    text = models.TextField()


# ==========================================
# MÓDULO 8: CONFIGURACIÓN Y ANUNCIOS
# ==========================================

class SystemConfig(models.Model):
    """
    Parámetros globales del ecosistema CartMaker.

    Attributes:
        platinum_min_rating_promedy_requirement (int): Rating mínimo para ser tienda Platinum.
        creation (datetime): Fecha de última actualización de config.
    """
    platinum_min_rating_promedy_requirement = models.IntegerField()
    creation = models.DateTimeField(auto_now_add=True)

class Announcement(models.Model):
    """
    Banners publicitarios e informativos de la App.

    Attributes:
        banner_img (str): URL de la imagen del banner.
        navigate_to (str): Ruta interna de la app para el clic.
        active (bool): Visibilidad del anuncio.
        creation (datetime): Fecha de lanzamiento.
    """
    banner_img = models.CharField(max_length=500, help_text="La imagen debe ser de 1920px x 1080px. Los primeros 180px de arriba estaran tapados por el AppBar del home. \
                                 Si la imagen esta en el servidor, solo especificar la ruta en la carpeta static, ej: static/img/banner_1_test.png")
    navigate_to = models.CharField(max_length=255)
    active = models.BooleanField(default=True)
    creation = models.DateTimeField(auto_now_add=True)

    def get_json(self) -> dict:
        url = f"{settings.DOMAIN}/{self.banner_img}" if not self.banner_img.startswith('http') else self.banner_img
        return {
            "banner_img_url":url,
            "navigate_to":self.navigate_to,
            "creation":self.creation.strftime('%d/%m/%Y, %H:%M:%S')
        }


# ==========================================
# MÓDULO 9: ANALÍTICAS
# ==========================================

class ProductViewLog(models.Model):
    """
    Registro de interacciones con productos para análisis de conversión.

    Attributes:
        client (ForeignKey): Usuario que visualizó.
        inventory_item (ForeignKey): Ítem visualizado.
        added_to_cart (bool): Si la vista terminó en adición al carrito.
        bought (bool): Si la vista terminó en compra efectiva.
        start_time (datetime): Inicio de la visualización.
        end_time (datetime): Fin de la visualización (cálculo de retención).
    """
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='product_views')
    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='views')
    added_to_cart = models.BooleanField(default=False)
    bought = models.BooleanField(default=False)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)

class StoreViewLog(models.Model):
    """
    Registro de tráfico en el perfil de una tienda.

    Attributes:
        client (ForeignKey): Usuario visitante.
        join_time (datetime): Hora de entrada al perfil.
        exit_time (datetime): Hora de salida.
        location_watched (bool): Si consultó el mapa de la tienda.
        presentation_video_watched (bool): Si reprodujo el video de intro.
        stories_watched (bool): Si visualizó historias de la tienda.
        products_watched (bool): Si exploró la lista de productos.
        tryed_to_contact (bool): Si pulsó botones de contacto.
    """
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='store_views')
    join_time = models.DateTimeField()
    exit_time = models.DateTimeField(null=True, blank=True)
    location_watched = models.BooleanField(default=False)
    presentation_video_watched = models.BooleanField(default=False)
    stories_watched = models.BooleanField(default=False)
    products_watched = models.BooleanField(default=False)
    tryed_to_contact = models.BooleanField(default=False)

class UserNavigationLog(models.Model):
    """
    Seguimiento de flujo de navegación del usuario en la plataforma.

    Attributes:
        user (ForeignKey): Usuario navegando.
        navigation_record (json): Mapa de pantallas visitadas.
        login_time (datetime): Inicio de sesión.
        logout_time (datetime): Cierre de sesión.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='navigation_logs')
    navigation_record = models.JSONField(default=dict)
    login_time = models.DateTimeField()
    logout_time = models.DateTimeField(null=True, blank=True)