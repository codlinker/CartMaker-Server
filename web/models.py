import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.contrib.gis.db import models as gis_models
from pgvector.django import HnswIndex, VectorField
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from .cos import storage_manager
from colorfield.fields import ColorField
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.html import mark_safe
from decimal import Decimal

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

class BankDocumentType(models.IntegerChoices):
    """
    ENUM para el tipo de documento del banco.
    """
    CEDULA = 0, _('CI'),
    RIF = 1, _('RIF')


class BankEnum(models.IntegerChoices):
    """
    ENUM del banco.
    """
    BANESCO = 0, _('Banesco')
    MERCANTIL = 1, _('Banco Mercantil')
    PROVINCIAL = 2, _('BBVA Provincial')
    VENEZUELA = 3, _('Banco de Venezuela')
    EXTERIOR = 4, _('Banco Exterior')
    BNC = 5, _('Banco Nacional de Crédito')
    BANPLUS = 6, _('Banplus')
    DIGITAL_DE_LOS_TRABAJADORES = 7, _('Banco Digital de los Trabajadores')
    SOFITASA = 8, _('Sofitasa')
    PLAZA = 9, _('Banco Plaza')
    BANCAMIGA = 10, _('Bancamiga')

BANK_IMAGES = {
    BankEnum.BANESCO:"img/bank_icons/banesco.png",
    BankEnum.MERCANTIL:"img/bank_icons/banco_mercantil.png",
    BankEnum.PROVINCIAL:"img/bank_icons/banco_provincial.png",
    BankEnum.VENEZUELA:"img/bank_icons/banco_de_venezuela.png",
    BankEnum.EXTERIOR:"img/bank_icons/banco_exterior.png",
    BankEnum.BNC:"img/bank_icons/bnc.png",
    BankEnum.BANPLUS:"img/bank_icons/banplus.png",
    BankEnum.DIGITAL_DE_LOS_TRABAJADORES:"img/bank_icons/banco_digital_de_los_trabajadores.png",
    BankEnum.SOFITASA:"img/bank_icons/banco_sofitasa.png",
    BankEnum.PLAZA:"img/bank_icons/banco_plaza.png",
    BankEnum.BANCAMIGA:"img/bank_icons/bancamiga.png"
}

class RejectionReason(models.IntegerChoices):
    """
    ENUM Motivos de rechazo del pago.
    """
    INVALID_REFERENCE = 1, _('Referencia inválida o no encontrada')
    INVALID_DATE = 2, _('Fecha de transferencia incorrecta')
    FAKE_PROOF = 3, _('Comprobante falso o ilegible')
    OTHER = 4, _('Otro motivo no especificado')
    NOT_ENOUGH_AMOUNT = 5, _('Monto incompleto')

class RejectionHelpText(models.IntegerChoices):
    """
    ENUM Textos de ayuda/instrucciones según el motivo de rechazo.
    """
    INVALID_REFERENCE = 1, _(
        'El número de referencia ingresado no coincide con nuestros registros bancarios. '
        'Por favor, verifique los dígitos y vuelva a intentarlo.'
    )
    INVALID_DATE = 2, _(
        'La fecha indicada en el formulario no coincide con la del comprobante. '
        'Por favor, seleccione la fecha exacta en la que realizó la operación.'
    )
    FAKE_PROOF = 3, _(
        'La imagen adjunta no es legible, está borrosa o no corresponde a un comprobante válido. '
        'Suba una captura de pantalla clara donde se vean todos los datos de la operación.'
    )
    OTHER = 4, _(
        'Su pago ha sido rechazado por un motivo no listado. '
        'Por favor, póngase en contacto con soporte técnico para más detalles.'
    )
    NOT_ENOUGH_AMOUNT = 5, _(
        'Su pago ha sido abonado a su cuenta. '
        'Por favor, realice el reporte de pago del monto restante para continuar con la activación de su suscripción.'
    )

class NotificationSection(models.IntegerChoices):
    """
    ENUM Tipo de notificacion.
    """
    HOME = 0, _('Home')
    ORDERS = 1, _('Ordenes')
    CART = 2, _('Carrito')
    SEARCH = 3, _('Buscador')
    ATLAS = 4, _('Atlas')
    SETTINGS = 5, _('Ajustes')
    HELP = 6, _('Ayuda')
    
class NotificationCategory(models.IntegerChoices):
    # Usamos un rango distinto o simplemente empezamos desde 0
    NEW_PAYMENT = 0, _('Nuevo pago recibido.')
    PAYMENT_APPROVED = 1, _('Pago aprobado.')
    PAYMENT_REJECTED = 2, _('Pago rechazado.')
    SUBSCRIPTION_EXPIRED = 3, _('Suscripción expirada.')

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

class UserWallet(models.Model):
    """
    Billetera digital del usuario. Se utiliza para almacenar montos a favor al
    pagar suscripciones en los casos en el que el usuario paga un monto inferior o superior.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wallet')
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    history = models.JSONField(default=list, blank=True)

    def get_json(self) -> dict:
        return {
            'balance': float(self.balance),
            'history': self.history
        }

    def regist_transaction(self, amount: float | Decimal, sub_type: str, description: str = "",
            transaction="add"):
        """
        Agrega un registro al historial de la billetera y actualiza el saldo.
        
        :param amount: El monto a agregar (positivo) o descontar (negativo).
        :param sub_type: Tipo de suscripción ('merchant' o 'atlas').
        :param description: Texto opcional para mostrarle al usuario (ej: "Abono por pago incompleto").
        """
        amount_decimal = Decimal(str(amount)).quantize(Decimal('0.00'))
        
        if transaction == 'add':
            self.balance += amount_decimal
        elif transaction == 'substract':
            if self.balance < amount_decimal:
                print("Error: Intento de dejar la cuenta en negativo")
                return self.balance
            self.balance -= amount_decimal

        transaction_record = {
            'timestamp': timezone.now().isoformat(),
            'subscription_type': sub_type,
            'amount': float(amount_decimal),
            'action': 'credit' if amount_decimal > 0 else 'debit',
            'description': description,
            'resulting_balance': float(self.balance)
        }
        if not isinstance(self.history, list):
            self.history = []
        self.history.append(transaction_record)
        self.save()

class DeviceToken(models.Model):
    """
    Token de Firebase asociado al dispositivo del usuario.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='fcm_tokens')
    token = models.CharField(max_length=255, unique=True)
    creation = models.DateTimeField(auto_now_add=True)
    platform = models.CharField(max_length=20, choices=[('android', 'Android'), ('ios', 'iOS')])

    def __str__(self):
        return f"Token de {self.user.username}"

class Notification(models.Model):
    """
    Modelo para gestionar las notificaciones persistentes en la interfaz de usuario (UI) de la App.

    Este modelo actúa como la 'Fuente de la Verdad' para el sistema de alertas del frontend,
    permitiendo sincronizar los contadores de notificaciones (badges) independientemente
    del ciclo de vida de Firebase Cloud Messaging (FCM).

    Atributos:
        user (ForeignKey): Referencia al usuario que recibe la notificación.
        section (int): Indica el módulo de la App (Home, Orders, etc.) donde se mostrará
            la alerta, basado en `NotificationSection`.
        category (int): Identifica el evento lógico específico (ej: pago aprobado) 
            basado en `NotificationCategory`.
        title (str): Título breve de la notificación para mostrar en la lista o push.
        body (str): Contenido detallado del mensaje.
        is_read (bool): Estado de lectura para el control de contadores en el NotificationProvider.
        metadata (json): Almacén flexible para IDs adicionales (como payment_id), 
            rutas de navegación o datos extras necesarios para la acción en Flutter.
        created_at (datetime): Fecha de creación para ordenamiento cronológico.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    section = models.IntegerField(choices=NotificationSection.choices)
    title = models.CharField(max_length=255)
    body = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    category = models.IntegerField(choices=NotificationCategory.choices)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.get_category_display()}] {self.title} - {self.user.username}"

    def get_json(self)->dict:
        return {
            "id":self.id,
            "section":self.section.__index__(),
            "title":self.title,
            "body":self.body,
            "is_read":self.is_read,
            "created_at":timezone.localtime(self.created_at).strftime("%d/%m/%Y, %H:%M:%S"),
            "category":self.category.__index__(),
            "metadata":self.metadata
        }

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

class Mall(models.Model):
    """
    """
    name = models.CharField(max_length=60)
    location = gis_models.PointField()
    
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

    def get_json(self)->dict:
        return {
            'id':self.id,
            'name':self.name,
            'creation':timezone.localtime(self.creation).strftime("%d/%m/%Y, %H:%M:%S"),
            'category':self.category.name
        }

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
    image = models.CharField(max_length=500, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def get_json(self)->dict:
        url = f"{settings.DOMAIN}/{self.image}" if not self.image.startswith('http') else self.image
        return {
            'id':self.id,
            'name':self.name,
            'creation':timezone.localtime(self.creation).strftime("%d/%m/%Y, %H:%M:%S"),
            'business_hours':self.business_hours,
            'image':url,
            'location':self.location.get_json()
        }

class StoreLocation(models.Model):
    """
    Ubicación geográfica de una sucursal.

    Attributes:
        store (OneToOne): Tienda asociada.
        mall (ForeignKey): Si no es null significa que la tienda esta dentro de un cc.
        coordinates (Point): Punto geográfico para mapas.
        name (str): Dirección legible.
        details (str): Referencias adicionales de la ubicación.
        creation (datetime): Fecha de registro de la ubicación.
    """
    store = models.OneToOneField(CompanyStore, on_delete=models.CASCADE, related_name='location')
    mall = models.ForeignKey(Mall, on_delete=models.SET_NULL, null=True, blank=True, related_name='stores')
    coordinates = gis_models.PointField()
    name = models.CharField(max_length=255)
    details = models.TextField(null=True, blank=True)
    creation = models.DateTimeField(auto_now_add=True)

    def get_json(self)->dict:
        return {
            'mall_id':self.mall.id if self.mall else None,
            'coordinates':self.coordinates,
            'name':self.name,
            'details':self.details,
            'creation':timezone.localtime(self.creation).strftime("%d/%m/%Y, %H:%M:%S")
        }

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
    Definición de paquetes de planes para comercios y su configuración visual en la App.

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
        operative_management_analytics (bool): Métricas operativas.
        company_branches (bool): Permite múltiples sucursales.
        company_employees (bool): Permite gestión de múltiples empleados.

        is_popular (bool): Flag para destacar el plan con un banner de 'POPULAR'.
        short_description_html (str): Resumen para la tarjeta principal (soporta <b>).
        large_description_html (str): Detalle extendido para la vista de beneficios.
        warning_description_html (str): Requisitos o notas críticas en color de alerta.
        requires_business (bool): Indica si requiere que el propietario sea una compania registrada.
        
        card_bg_color (str): Color Hexadecimal para el fondo de la tarjeta.
        label_bg_color (str): Color Hexadecimal para el fondo de la etiqueta de título.
        label_border_color (str): Color Hexadecimal para el borde de la etiqueta de título.
        label_text_color (str): Color Hexadecimal para el texto del título del plan.
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
    # Campos design
    is_popular = models.BooleanField(
        default=False, 
        help_text="Si está activo, mostrará el banner de 'POPULAR' y resaltará la tarjeta."
    )
    short_description_html = models.TextField(
        blank=True,
        help_text="Descripción corta del plan. Sale en la tarjeta."
    )
    large_description_html = models.TextField(
        blank=True,
        help_text="Descripción larga del plan. Sale en la pantalla de beneficios."
    )
    warning_description_html = models.TextField(
        blank=True,
        help_text="Corta descripcion de requisitos indispensables. (Se ven de color rojo en la pantalla de beneficios)"
    )
    requires_business = models.BooleanField(default=False)
    card_bg_color = ColorField(default='#E7E7E7', help_text="Color de fondo de la tarjeta")
    label_bg_color = ColorField(default='#B79DF0', help_text="Fondo de la etiqueta del nombre")
    label_border_color = ColorField(default='#6200EE', help_text="Borde de la etiqueta del nombre")
    label_text_color = ColorField(default='#FFFFFF', help_text="Color del texto de la etiqueta")

    def get_json(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'price': float(self.price),
            "bs_price":0.0, # Se llenan en las peticiones
            "dollar_bcv_tax":0.0, # Se llenan en las peticiones
            'benefits': {
                'inventory_capacity': {
                    "label": "Capacidad del inventario",
                    "description":"Límite de productos registrados en el inventario.",
                    "value": self.inventory_capacity
                },
                'products_registration_with_ia': {
                    "label": "Registro de productos con IA",
                    "description":"Permite escanear productos con IA para rellenar los campos correspondientes a los datos del producto automáticamente, así como también recibir sugerencias de precio.",
                    "value": self.products_registration_with_ia
                },
                'profile_histories': {
                    "label": "Historial de perfiles",
                    "description":"Desbloquea la función de subir historias en tu cuenta de comerciante, al igual que en Instagram. Mantén a los clientes al tanto de tus promociones y ofertas a través del contenido multimedia.",
                    "value": self.profile_histories
                },
                'gamification_system': {
                    "label": "Sistema de gamificación",
                    "description":"Incentiva las ventas brindándoles a tus clientes la posibilidad de obtener tokens por comprar en tu tienda y poder canjearlos por descuentos en tus productos.",
                    "value": self.gamification_system
                },
                'gamification_analytics': {
                    "label": "Analítica de gamificación",
                    "description":"Sección de datos sobre los resultados y rendimiento del sistema de gamificación.",
                    "value": self.gamification_analytics
                },
                'digital_performance_analytics': {
                    "label": "Analítica de rendimiento digital",
                    "description":"Sección de datos sobre visualizaciones de la tienda, conversión de ventas, efectividad de productos y membresía.",
                    "value": self.digital_performance_analytics
                },
                'clients_behavior_analytics': {
                    "label": "Analítica de comportamiento de clientes",
                    "description":"Sección de datos sobre retencion de clientes, rankings, mapas de calor sobre horas pico de compra.",
                    "value": self.clients_behavior_analytics
                },
                'operative_management_analytics': {
                    "label": "Analítica de gestión operativa",
                    "description":"Sección de datos sobre el estado del inventario en cada sucursal, gastos promedios por cliente y contabilidad.",
                    "value": self.operative_management_analytics
                },
                'company_branches': {
                    "label": "Sucursales de la empresa",
                    "description":"Permite la bifurcación de tu negocio en diferentes localizaciones. Podrás registrar cuantas sucursales desees y tendrás un inventario por cada una.",
                    "value": self.company_branches
                },
                'company_employees': {
                    "label": "Empleados de la empresa",
                    "description":"Permite el registro de biometría de terceros para autorizar su acceso a la cuenta y gestionar sus permisos para ejecutar acciones.",
                    "value": self.company_employees
                },
            },
            'ui_data':{
                'is_popular':self.is_popular,
                'short_description_html':self.short_description_html,
                'large_description_html':self.large_description_html,
                'warning_description_html':self.warning_description_html,
                'card_bg_color':self.card_bg_color,
                'label_bg_color':self.label_bg_color,
                'label_border_color':self.label_border_color,
                'label_text_color':self.label_text_color
            }
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
    merchant = models.OneToOneField(User, on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(MerchantPlan, on_delete=models.PROTECT)
    valid_until = models.DateTimeField(null=True, default=None)
    adquired_at = models.DateTimeField(auto_now_add=True)
    merchant_type = models.IntegerField(choices=MerchantType.choices)
    rif_number = models.CharField(max_length=50, null=True, blank=True)
    company_document_url = models.CharField(max_length=500, null=True, blank=True)

    def get_json(self)->dict:
        return {
            'id':self.id,
            'plan':self.plan.name,
            'valid_until':self.valid_until.strftime("%d/%m/%Y, %H:%M:%S") if self.valid_until else None,
            'adquired_at':self.adquired_at.strftime("%d/%m/%Y, %H:%M:%S"),
            'merchant_type':self.get_merchant_type_display(),
            'rif_number':self.rif_number,
        }

class MerchantPlanPayment(models.Model):
    """
    Registro de pagos de suscripción.
    """
    subscription = models.ForeignKey(MerchantSubscription, on_delete=models.CASCADE, related_name='payments')
    reference_number = models.CharField(max_length=100)
    payment_proof_url = models.CharField(max_length=500, null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    bcv_taxes_to_day = models.DecimalField(max_digits=10, decimal_places=4)
    status = models.IntegerField(choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    verified_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.IntegerField(choices=RejectionReason.choices, null=True, blank=True)
    rejection_help = models.IntegerField(choices=RejectionHelpText.choices, null=True, blank=True)
    creation = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.pk:
            original_instance = MerchantPlanPayment.objects.get(pk=self.pk)
            if original_instance.status != PaymentStatus.REJECTED and self.status == PaymentStatus.REJECTED:
                if self.rejection_reason is None:
                    raise ValidationError({
                        'rejection_reason': "Debes seleccionar una razón de rechazo."
                    })
        if self.status != PaymentStatus.REJECTED:
            self.rejection_reason = None
        super().clean()

    # 2. Método para renderizar la imagen en el Admin
    @property
    def payment_proof_preview(self):
        if self.payment_proof_url:
            return mark_safe(f'<img src="{self.payment_proof_url}" style="max-height: 400px; max-width: 300px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);" />')
        return "Sin comprobante"
    
    payment_proof_preview.fget.short_description = "Comprobante de Pago"

    def get_json(self) -> dict:
        
        return {
            'id': self.id,
            'subscription': self.subscription.id,
            'reference_number': self.reference_number,
            'payment_proof_url': self.payment_proof_url,
            'amount': float(self.amount),
            'bcv_taxes_to_day': float(self.bcv_taxes_to_day),
            'status': self.status,
            'verified_at': self.verified_at.strftime("%d/%m/%Y, %H:%M:%S") if self.verified_at else None,
            'rejection_reason': self.get_rejection_reason_display() if self.rejection_reason else "",
            'rejection_help': self.get_rejection_help_display() if self.rejection_help else "",
            'creation': self.creation.strftime("%d/%m/%Y, %H:%M:%S") if self.creation else None
        }


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
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='atlas_plan')
    valid_until = models.DateTimeField()

    def get_json(self) -> dict:
        return {
            'valid_until':self.valid_until.strftime("%d/%m/%Y, %H:%M:%S") if self.valid_until else None
        }

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
        rejection_reason (int): Solo se utiliza si el pago fue rechazado.
        rejection_help (int): Texto de ayuda para el usuario para saber que hacer en caso de pago rechazado.
    """
    plan = models.ForeignKey(AtlasPlusPlan, on_delete=models.CASCADE, related_name='payments')
    reference_number = models.CharField(max_length=100)
    payment_proof_url = models.CharField(max_length=500, null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    bcv_taxes_to_day = models.DecimalField(max_digits=10, decimal_places=4)
    status = models.IntegerField(choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    verified_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.IntegerField(choices=RejectionReason.choices, null=True, blank=True)
    rejection_help = models.IntegerField(choices=RejectionHelpText.choices, null=True, blank=True)
    creation = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.pk:
            original_instance = AtlasPlusPlanPayment.objects.get(pk=self.pk)
            if (original_instance.status != PaymentStatus.REJECTED and 
                self.status == PaymentStatus.REJECTED):
                if not self.rejection_reason or self.rejection_reason.strip() == "":
                    raise ValidationError({
                        'rejection_reason': "Debes especificar una razón de rechazo."
                    })
        super().clean()

    @property
    def payment_proof_preview(self):
        if self.payment_proof_url:
            return mark_safe(f'<img src="{self.payment_proof_url}" style="max-height: 400px; max-width: 300px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);" />')
        return "Sin comprobante"
    
    payment_proof_preview.fget.short_description = "Comprobante de Pago"

    def get_json(self)->dict:
        return {
            'id':self.id,
            'reference_number':self.reference_number,
            'payment_proof_url':self.payment_proof_url,
            'amount':float(self.amount),
            'bcv_taxes_to_day':float(self.bcv_taxes_to_day),
            'status':self.status,
            'verified_at':self.verified_at.strftime("%d/%m/%Y, %H:%M:%S") if self.verified_at else None,
            'rejection_reason':self.rejection_reason,
            'rejection_help': self.get_rejection_help_display() if self.rejection_help else "",
            'creation':self.creation.strftime("%d/%m/%Y, %H:%M:%S") if self.creation else None
        }

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

class CartMakerBankAccount(models.Model):
    """
    Bancos configurados en CartMaker para recibir pagos de suscripciones.
    """
    bank = models.IntegerField(blank=True, choices=BankEnum.choices)
    pago_movil_enabled = models.BooleanField(default=False)
    tlf = models.CharField(blank=True)
    document_number = models.CharField()
    document_type = models.IntegerField(choices=BankDocumentType.choices, default=BankDocumentType.CEDULA)
    account_number = models.CharField()
    active = models.BooleanField(default=True)
    beneficiary_name = models.CharField(default='CODLINKER C.A')

    @property
    def bank_img_url(self)->str:
        try:
            return f"{settings.DOMAIN}{settings.STATIC_URL}{BANK_IMAGES[self.bank]}"
        except Exception as e:
            print(f"Error al obtener la imagen del banco: {e}")
            return f"{settings.DOMAIN}{settings.STATIC_URL}img/no_image.jpg"
        
    def get_json(self)->dict:
        return {
            'id':self.id,
            'bank':self.get_bank_display(),
            'pago_movil_enabled':self.pago_movil_enabled,
            'tlf':self.tlf,
            'document_number':self.document_number,
            'document_type':self.get_document_type_display(),
            'account_number':self.account_number,
            'beneficiary_name':self.beneficiary_name,
            'bank_img_url':self.bank_img_url
        }

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