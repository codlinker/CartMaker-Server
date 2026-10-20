from datetime import datetime, timedelta
import hashlib
import secrets
from typing import Optional
import uuid
from django.db import models, transaction
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.contrib.gis.db import models as gis_models
from pgvector.django import HnswIndex, VectorField
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from .cos import storage_manager
from colorfield.fields import ColorField
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.utils import timezone
from django.utils.html import mark_safe
from decimal import Decimal
from django.contrib.postgres.indexes import GinIndex
from django.db.models import UniqueConstraint, Q
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
import re

# FUNCIONES PARA JSON Fields por default

def get_default_work_hours():
    return {"start": "08:00 AM", "end": "06:30 PM"}

# Función para el default de los días (Lun a Vie)
def get_default_work_days():
    return [0, 1, 2, 3, 4]

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
    CREATION = 2, _("Creacion")

class OrderStatus(models.IntegerChoices):
    """
    ENUM Estado de la orden.
    """
    WAITING = 0, _('Esperando')
    DELIVERY_SENT = 1, _("Delivery en camino")
    REPORTED = 2, _('Reportada / En revisión')
    CANCELLED = 3, _('Cancelada')
    COMPLETED = 4, _('Completada')
    SOLVED = 5, _('Resuelta')

class StoreType(models.IntegerChoices):
    # Ubicaciones tradicionales
    IN_MALL = 0, _('En centro comercial')
    STREET = 1, _('Local a pie de calle')
    KIOSK = 2, _('Kiosco')
    OFFICE = 3, _('Oficina')
    # Formatos modernos
    ONLINE = 4, _('Tienda virtual')
    MOBILE = 5, _('Unidad móvil / Food Truck')
    BUHONERO = 6, _('Puesto buhonero')

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

class CancellationReason(models.IntegerChoices):
    """
    Razones predefinidas para la cancelación de pedidos.
    """
    BETTER_PRICE = 1, _('Encontré un mejor precio.')
    WRONG_PRODUCT = 2, _('Me equivoqué de producto.')
    DELIVERY_TOO_LONG = 3, _('El delivery tarda demasiado.')
    NO_LONGER_NEEDED = 4, _('Ya no lo necesito.')
    OTHER = 5, _('Otros motivos.')

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
    NOT_ENOUGH_AMOUNT = 5, _('Monto incompleto')
    OTHER = 4, _('Otro motivo no especificado')

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
    # Clientes
    HOME = 0, _('Home')
    ORDERS = 1, _('Ordenes Cliente')
    CART = 2, _('Carrito')
    SEARCH = 3, _('Buscador')
    ATLAS = 4, _('Atlas')
    SETTINGS = 5, _('Ajustes')
    HELP = 6, _('Ayuda')
    MERCHANT_SUBSCRIPTION = 12, _('Suscripción Negocio')
    MY_COMPANY = 13, _('Mi Negocio')
    MANAGE_STORAGE = 15, _('Inventario')
    MERCHANT_ORDERS = 28, _('Pedidos del Negocio')
    MERCHANT_QUESTIONS = 29, _('Preguntas al Vendedor')
    MERCHANT_ANALYTICS = 30, _('Analíticas')
    MERCHANT_GAMIFICATION = 31, _('Gamificación')
    MERCHANT_EMPLOYEES = 32, _('Empleados')

class NotificationCategory(models.IntegerChoices):
    # Existentes
    NEW_PAYMENT = 0, _('Nuevo pago recibido.')
    PAYMENT_APPROVED = 1, _('Pago aprobado.')
    PAYMENT_REJECTED = 2, _('Pago rechazado.')
    SUBSCRIPTION_EXPIRED = 3, _('Suscripción expirada.')
    NEW_QUESTION = 4, _('Nueva pregunta de cliente.')
    NEW_ORDER = 5, _('Nuevo pedido recibido.')
    NEW_ANSWER = 6, _('Nueva respuesta recibida.')
    LOW_INVENTORY = 7, _('Stock bajo de producto.')
    OUT_OF_STOCK = 8, _('Producto agotado.')
    ANALYTICS_REPORT = 9, _('Reporte de métricas listo.')
    GAMIFICATION_ALERT = 10, _('Alerta de tokens/gamificación.')
    ORDER_STATUS_CHANGED = 11, _('Actualización en orden.')
    NEW_CHAT_MESSAGE = 12, _('Nuevo Mensaje de Chat')
    # Sistema de trabajadores (Workforce)
    EMPLOYEE_INVITATION = 13, _('Invitación para trabajar en un comercio.')
    EMPLOYEE_UPDATE = 14, _('Actualización de trabajador.')
    # Delivery en tiempo real
    DELIVERY_ASSIGNMENT = 15, _('Asignación de Delivery')
    DELIVERY_STATUS = 16, _('Estado de Delivery')

class MessageOrigin(models.IntegerChoices):
    """
    ENUM Origen del mensaje de la conversacion con Atlas.
    """
    CLIENT = 0, _('Cliente')
    ATLAS = 1, _('Atlas')

class EmployeeRole(models.IntegerChoices):
    """
    ENUM Rol del trabajador dentro del comercio.
    """
    ASSISTANT = 0, _('Asistente')
    DELIVERY = 1, _('Repartidor')

class EmployeeStatus(models.IntegerChoices):
    """
    ENUM Estado laboral del trabajador. Convive con `Employee.is_active`
    (is_active == True únicamente cuando el estado es ACTIVE).
    """
    ACTIVE = 0, _('Activo')
    SUSPENDED = 1, _('Suspendido')
    REVOKED = 2, _('Revocado')

class VehicleType(models.IntegerChoices):
    """
    ENUM Tipo de vehículo del repartidor. Define el perfil de rutas (OSRM) y de velocidades.
    """
    MOTO = 0, _('Moto')
    BICI = 1, _('Bicicleta')
    CARRO = 2, _('Carro')
    PIE = 3, _('A pie')

class InvitationChannel(models.IntegerChoices):
    """
    ENUM Canal por el que se envía la invitación de trabajador.
    """
    EMAIL = 0, _('Correo electrónico')
    IN_APP = 1, _('Dentro de la app')
    QR_LINK = 2, _('Enlace o código QR')

class InvitationStatus(models.IntegerChoices):
    """
    ENUM Estado de la invitación de trabajador.
    """
    PENDING = 0, _('Pendiente')
    ACCEPTED = 1, _('Aceptada')
    DECLINED = 2, _('Rechazada')
    REVOKED = 3, _('Revocada')
    EXPIRED = 4, _('Expirada')

# Slugs estables del rol (se usan en los claims del JWT de trabajador y en las respuestas de la API)
EMPLOYEE_ROLE_SLUGS = {
    EmployeeRole.ASSISTANT: 'assistant',
    EmployeeRole.DELIVERY: 'delivery',
}

class DeliveryStatus(models.IntegerChoices):
    """
    ENUM Estado de una entrega a domicilio (DeliveryAssignment).
    """
    PENDING_RIDER = 0, _('Buscando repartidor')
    ASSIGNED = 1, _('Asignado (esperando aceptación)')
    ACCEPTED = 2, _('Aceptado (en camino a tienda)')
    AT_STORE = 3, _('En la tienda')
    PICKED_UP = 4, _('En camino al cliente')
    ARRIVING = 5, _('Llegando al destino')
    DELIVERED = 6, _('Entregado')
    FAILED = 7, _('Entrega fallida')
    CANCELLED = 8, _('Cancelado')

class FixSource(models.IntegerChoices):
    """
    ENUM Origen de una posición del repartidor.
    """
    GNSS_SOCKET = 0, _('GPS directo')
    OFFLINE_BUFFER = 1, _('Buffer offline')
    BLE_RELAY = 2, _('Retransmisión BLE')

# Estados en los que el repartidor tiene una entrega "viva" (restricción one_active_delivery_per_rider)
DELIVERY_ACTIVE_STATUSES = (
    DeliveryStatus.ASSIGNED,
    DeliveryStatus.ACCEPTED,
    DeliveryStatus.AT_STORE,
    DeliveryStatus.PICKED_UP,
    DeliveryStatus.ARRIVING,
)
DELIVERY_TERMINAL_STATUSES = (
    DeliveryStatus.DELIVERED,
    DeliveryStatus.FAILED,
    DeliveryStatus.CANCELLED,
)
DELIVERY_MAX_PIN_ATTEMPTS = 5

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
    biometric_vector = VectorField(dimensions=512, null=True, blank=True)
    biometric_consent_accepted_at = models.DateTimeField(null=True, blank=True)
    biometric_consent_version = models.CharField(max_length=32, null=True, blank=True)
    biometric_suppressed_at = models.DateTimeField(null=True, blank=True)
    gender = models.IntegerField(choices=UserGender.choices, default=UserGender.MALE)
    is_external_account = models.BooleanField(default=False)
    can_check_payments = models.BooleanField(default=False, help_text="Puede ingresar al panel de pagos")
    can_check_support = models.BooleanField(default=False, help_text="Puede ingresar al panel de soporte")
    preferred_categories = models.ManyToManyField(
        'Category',
        blank=True,
        related_name='interested_users',
        help_text="Categorías principales seleccionadas por el usuario en el onboarding."
    )

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

    def get_preferred_category_ids(self) -> list:
        """
        Retorna la lista ordenada de IDs de categorías principales preferidas por el usuario.
        """
        prefetched = getattr(self, '_prefetched_objects_cache', None)
        if prefetched and 'preferred_categories' in prefetched:
            return sorted(cat.id for cat in prefetched['preferred_categories'])
        return list(
            self.preferred_categories.order_by('id').values_list('id', flat=True)
        )

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
        
        :param amount: El monto a agregar (positivo) o descontar (positivo).
        :param sub_type: Tipo de suscripción ('merchant' o 'atlas').
        :param description: Texto opcional para mostrarle al usuario (ej: "Abono por pago incompleto").
        """
        amount_decimal = Decimal(str(amount)).quantize(Decimal('0.00'))
        if amount_decimal < Decimal('0.00'):
            raise ValidationError("El monto de la transacción no puede ser negativo.")

        if transaction == 'add':
            self.balance += amount_decimal
            action_label = 'credit'
        elif transaction in ('substract', 'subtract'):
            if self.balance < amount_decimal:
                raise ValidationError("Saldo insuficiente en la billetera para realizar esta operación.")
            self.balance -= amount_decimal
            action_label = 'debit'
        else:
            raise ValidationError(f"Tipo de transacción '{transaction}' no válido.")

        transaction_record = {
            'timestamp': timezone.now().isoformat(),
            'subscription_type': sub_type,
            'amount': float(amount_decimal),
            'action': action_label,
            'description': description,
            'resulting_balance': float(self.balance)
        }
        if not isinstance(self.history, list):
            self.history = []
        self.history.append(transaction_record)
        self.save()
        return self.balance

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
        indexes = [
            models.Index(fields=['user', 'is_read'], name='notif_user_unread_idx'),
            models.Index(fields=['user', '-created_at'], name='notif_user_created_idx'),
            models.Index(fields=['user', 'section', '-created_at'], name='notif_user_sec_created_idx'),
        ]

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
        description (str): Descripcion de la ubicacion.
        is_default (str): Indica si esta es la ubicacion seleccionada por el usuario como predeterminada.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='locations')
    coordinates = gis_models.PointField()
    name = models.CharField(max_length=255)
    description = models.CharField(max_length=600)
    is_default = models.BooleanField(default=False)

    class Meta:
        indexes = [
            # Esto crea el índice GIST sobre la columna de coordenadas
            models.Index(fields=['coordinates'], name='client_location_gis_idx', opclasses=['gist_geometry_ops_2d']),
        ]

    def get_json(self)->dict:
        return {
            'id':self.id,
            'latitude':self.coordinates.y,
            'longitude':self.coordinates.x,
            'name':self.name,
            'description':self.description,
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
    name = models.CharField(max_length=60)
    coordinates = gis_models.PointField()
    floors_quantity = models.IntegerField(default=1)
    img_url = models.CharField(default="static/img/no_image.jpg")

    class Meta:
        indexes = [
            # Esto crea el índice GIST sobre la columna de coordenadas
            models.Index(fields=['coordinates'], name='mall_location_gis_idx', opclasses=['gist_geometry_ops_2d']),
        ]

    def get_img_url(self) -> str:
        """
        Retorna la URL publica de la imagen del centro comercial.
        """
        return self.img_url if self.img_url.startswith('http')\
              else f"{settings.DOMAIN}/{self.img_url}"

    def get_json(self) -> dict:
        prefetched = getattr(self, '_prefetched_objects_cache', None)
        if prefetched and 'stores' in prefetched:
            store_ids = [s.id for s in prefetched['stores']]
        else:
            store_ids = list(self.stores.values_list('id', flat=True))
        return {
            'id': self.id,
            'name': self.name,
            'lat': self.coordinates.y,
            'lng': self.coordinates.x,
            # Solo devolvemos los IDs de las ubicaciones asociadas
            'store_location_ids': store_ids,
            'floors_quantity':self.floors_quantity,
            'img_url':self.get_img_url()
        }
    
class CompanyCategory(models.Model):
    """
    Categoría legal o comercial de una empresa.

    Attributes:
        name (str): Nombre de la categoría (ej: 'Farmacia', 'Supermercado').
    """
    name = models.CharField(max_length=255)

    def get_json(self)->dict:
        return {
            'id':self.id,
            'name':self.name
        }

class Company(models.Model):
    """
    Entidad legal que agrupa una o más tiendas.

    Attributes:
        id (uuid): Identificador único global de la compañía.
        name (str): Nombre comercial.
        owner (ForeignKey): Usuario dueño de la empresa.
        creation (datetime): Fecha de registro de la empresa.
        category (ForeignKey): Rubro al que pertenece.
        image (str): Imagen de perfil de la empresa.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    owner = models.OneToOneField(User, on_delete=models.CASCADE, related_name='company')
    creation = models.DateTimeField(auto_now_add=True)
    category = models.ForeignKey(CompanyCategory, on_delete=models.SET_NULL, null=True)
    image = models.CharField(null=True, blank=True)
    presentation_video_url = models.CharField(null=True, default=None)
    presentation_video_thumbnail = models.CharField(null=True, default=None)
    gamification_enabled = models.BooleanField(default=False)
    gamification_tokens_per_dollar = models.IntegerField(default=0)
    main_work_hours = models.JSONField(default=get_default_work_hours)
    main_work_days = models.JSONField(default=get_default_work_days)
    is_platinum = models.BooleanField(
        default=False, 
        db_index=True,
        help_text="Si es True, la empresa tiene +4.5 estrellas y alto volumen de ventas. Recibe boost en el motor de búsqueda."
    )
    merchant_type = models.IntegerField(
        choices=MerchantType.choices,
        default=MerchantType.ENTREPRENEUR,
        help_text="Emprendedor o empresa. Lo define el dueño al configurar la compañía."
    )
    rif_number = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        help_text="RIF normalizado SENIAT (ej. J-31234567-8)"
    )
    razon_social = models.CharField(
        max_length=180,
        null=True,
        blank=True,
        db_index=True,
        help_text="Denominación o Razón Social fiscal según SENIAT/SAREN"
    )
    mercantil_oficina = models.CharField(
        max_length=140,
        null=True,
        blank=True,
        help_text="Circunscripción / Oficina de Registro Mercantil (SAREN)"
    )
    mercantil_numero = models.CharField(
        max_length=40,
        null=True,
        blank=True,
        help_text="Número de Registro / Expediente Mercantil"
    )
    mercantil_tomo = models.CharField(
        max_length=40,
        null=True,
        blank=True,
        help_text="Tomo del Registro Mercantil (ej. 128-A)"
    )
    representante_cedula = models.CharField(
        max_length=25,
        null=True,
        blank=True,
        db_index=True,
        help_text="Cédula del Socio/Representante Legal tomada de request.user.cedula_number"
    )
    kyb_ocr_verified = models.BooleanField(default=False)
    kyb_confidence_score = models.PositiveSmallIntegerField(default=0)
    rif_document_url = models.URLField(max_length=500, null=True, blank=True)
    mercantil_document_url = models.URLField(max_length=500, null=True, blank=True)
    rif_image_sha256 = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True,
        db_index=True
    )
    mercantil_image_sha256 = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True,
        db_index=True
    )

    @property
    def kyb_status(self) -> int:
        """
        Estado KYB derivado dinámicamente:
        0 = Emprendedor (no requiere KYB mercantil)
        1 = Empresa en revisión manual
        2 = Empresa verificada por OCR (score >= 80)
        """
        if self.merchant_type != MerchantType.BUSINESS:
            return 0
        return 2 if (self.kyb_ocr_verified and (self.kyb_confidence_score or 0) >= 80) else 1

    def get_json(self)->dict:
        url = ""
        if self.image:
            url = storage_manager.get_url(self.image) 
        presentation_url = ""
        if self.presentation_video_url:
            presentation_url = storage_manager.get_url(self.presentation_video_url) 
        presentation_video_thumbnail = ""
        if self.presentation_video_thumbnail:
            presentation_video_thumbnail = storage_manager.get_url(self.presentation_video_thumbnail)
        rif_doc_url = (
            self.rif_document_url
            if (self.rif_document_url and str(self.rif_document_url).startswith(("http://", "https://")))
            else (storage_manager.get_url(self.rif_document_url) if self.rif_document_url else None)
        )
        mercantil_doc_url = (
            self.mercantil_document_url
            if (self.mercantil_document_url and str(self.mercantil_document_url).startswith(("http://", "https://")))
            else (storage_manager.get_url(self.mercantil_document_url) if self.mercantil_document_url else None)
        )
        prefetched = getattr(self, '_prefetched_objects_cache', None)
        if prefetched and 'payment_methods' in prefetched:
            pm_list = [pm.get_json() for pm in prefetched['payment_methods']]
        else:
            try:
                pm_list = [pm.get_json() for pm in self.payment_methods.all().order_by('-is_active', 'id')]
            except Exception:
                pm_list = []

        return {
            'id':self.id,
            'name':self.name,
            'creation':timezone.localtime(self.creation).strftime("%d/%m/%Y, %H:%M:%S"),
            'category':self.category.name if self.category else "",
            'merchant_type': self.merchant_type,
            'image':url,
            'presentation_video_url':presentation_url,
            "gamification_enabled":self.gamification_enabled,
            "gamification_tokens_per_dollar":self.gamification_tokens_per_dollar,
            "main_work_hours":self.main_work_hours,
            "main_work_days":self.main_work_days,
            "presentation_video_thumbnail":presentation_video_thumbnail,
            "is_platinum":self.is_platinum,
            'rif_number': self.rif_number,
            'razon_social': self.razon_social,
            'mercantil_oficina': self.mercantil_oficina,
            'mercantil_numero': self.mercantil_numero,
            'mercantil_tomo': self.mercantil_tomo,
            'representante_cedula': self.representante_cedula,
            'rif_document_url': rif_doc_url,
            'mercantil_document_url': mercantil_doc_url,
            'kyb_ocr_verified': self.kyb_ocr_verified,
            'kyb_confidence_score': self.kyb_confidence_score,
            'kyb_status': self.kyb_status,
            'payment_methods': pm_list,
        }
    
    def __str__(self):
        return self.name

class CompanyStore(models.Model):
    """
    Sucursal física o virtual de una compañía.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='stores')
    name = models.CharField(max_length=255)
    creation = models.DateTimeField(auto_now_add=True)
    store_img_url = models.CharField(default=None, null=True)
    work_hours = models.JSONField(default=get_default_work_hours)
    work_days = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    store_type = models.IntegerField(choices=StoreType.choices, default=StoreType.STREET)
    is_main_store = models.BooleanField(
        default=False,
        help_text="Indica si es la sucursal principal. Obligatorio si el plan no permite múltiples sucursales."
    )

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=['company'],
                condition=Q(is_main_store=True),
                name='unique_main_store_per_company'
            )
        ]

    # =========================================================================
    # DÍAS Y HORARIOS: la sucursal manda si los configuró; si no, la compañía.
    # =========================================================================
    @property
    def effective_work_days(self) -> list:
        """Días laborales de la sucursal, o los de la compañía si esta sucursal no los configuró."""
        has_valid_days = self.work_days and isinstance(self.work_days, list) and len(self.work_days) > 0
        days = self.work_days if has_valid_days else self.company.main_work_days
        return days if days else [0, 1, 2, 3, 4]

    @property
    def effective_work_hours(self) -> dict:
        """Horario de la sucursal, o el de la compañía si esta sucursal no lo configuró."""
        has_valid_hours = self.work_hours and isinstance(self.work_hours, dict) and 'start' in self.work_hours
        return self.work_hours if has_valid_hours else self.company.main_work_hours

    # =========================================================================
    # VALIDADORES EN TIEMPO REAL (No cambian, consumen las propiedades superiores)
    # =========================================================================
    @property
    def is_between_work_days(self) -> bool:
        now_local = timezone.localtime(timezone.now())
        return now_local.weekday() in self.effective_work_days

    @property
    def is_between_work_hours(self) -> bool:
        hours_to_use = self.effective_work_hours
        
        if not hours_to_use or 'start' not in hours_to_use or 'end' not in hours_to_use:
            return False 
            
        try:
            now_local = timezone.localtime(timezone.now())
            start_time = datetime.strptime(hours_to_use['start'].strip(), "%I:%M %p").time()
            end_time = datetime.strptime(hours_to_use['end'].strip(), "%I:%M %p").time()
            current_time = now_local.time()
            
            if start_time <= end_time:
                return start_time <= current_time <= end_time
            else:
                return current_time >= start_time or current_time <= end_time
        except (ValueError, TypeError, AttributeError):
            return False
        
    @property
    def is_currently_open(self) -> bool:
        """
        Calcula de forma unificada si la tienda está abierta.
        Al alimentarse de `effective_work_hours` y `effective_work_days`, 
        hereda automáticamente la lógica de suscripción programada arriba.
        """
        hours_to_use = self.effective_work_hours
        days_to_use = self.effective_work_days

        if not hours_to_use or 'start' not in hours_to_use or 'end' not in hours_to_use:
            return False

        try:
            now_local = timezone.localtime(timezone.now())
            current_time = now_local.time()
            current_weekday = now_local.weekday()

            start_time = datetime.strptime(hours_to_use['start'].strip(), "%I:%M %p").time()
            end_time = datetime.strptime(hours_to_use['end'].strip(), "%I:%M %p").time()

            # CASO A: Horario normal
            if start_time <= end_time:
                if current_weekday in days_to_use:
                    return start_time <= current_time <= end_time
                return False

            # CASO B: Horario nocturno / Cruzando la medianoche
            else:
                if current_weekday in days_to_use and current_time >= start_time:
                    return True
                
                yesterday_weekday = (current_weekday - 1) % 7
                if yesterday_weekday in days_to_use and current_time <= end_time:
                    return True

                return False

        except (ValueError, TypeError, AttributeError):
            return False

    def get_json(self) -> dict:
        url = ""
        if self.store_img_url:
            url = storage_manager.get_url(self.store_img_url)
            
        contact_methods_dict = {
            ContactMethodType(contact.method_type).name.lower(): contact.get_json()
            for contact in self.contact_methods.all()
        }
        
        return {
            'id': self.id,
            'name': self.name,
            'creation': timezone.localtime(self.creation).strftime("%d/%m/%Y, %H:%M:%S"),
            'store_img_url': url,
            'work_hours': self.effective_work_hours,
            'work_days': self.effective_work_days,
            'is_currently_open': self.is_currently_open,
            'location': self.location.get_json() if hasattr(self, 'location') else None,
            'contact_methods': contact_methods_dict,
            'is_active': self.is_active,
            "is_main_store": self.is_main_store
        }
    
    def __str__(self):
        return f"{self.name} ({self.company.name})"

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
    mall_floor = models.IntegerField(null=True, blank=True)
    coordinates = gis_models.PointField()
    name = models.CharField(max_length=255)
    details = models.TextField(null=True, blank=True)
    creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            # Esto crea el índice GIST sobre la columna de coordenadas
            models.Index(fields=['coordinates'], name='store_location_gis_idx', opclasses=['gist_geometry_ops_2d']),
        ]

    def get_json(self) -> dict:
        return {
            'id': self.id,
            'mall_id': self.mall_id,
            'mall_floor':self.mall_floor,
            'lat': self.coordinates.y,
            'lng': self.coordinates.x,
            'store_type': self.store.store_type,
            'name': self.name,
            'details': self.details,
            'creation': timezone.localtime(self.creation).strftime("%d/%m/%Y, %H:%M:%S")
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

    class Meta:
        # Aquí definimos la restricción de unicidad
        constraints = [
            models.UniqueConstraint(
                fields=['store', 'method_type'], 
                name='unique_contact_method_per_store'
            )
        ]

    def get_json(self) -> dict:
        return {
            'id': self.id,
            'method_type': self.get_method_type_display(),
            'value': self.value
        }


class MerchantPaymentMethodType(models.TextChoices):
    PAGO_MOVIL = 'pago_movil', _('Pago Móvil')
    TRANSFERENCIA = 'transferencia', _('Transferencia Bancaria')
    ZELLE = 'zelle', _('Zelle')
    BINANCE = 'binance', _('Binance Pay')
    EFECTIVO_USD = 'efectivo_usd', _('Efectivo (USD)')
    EFECTIVO_BS = 'efectivo_bs', _('Efectivo (Bs.)')
    PUNTO_VENTA = 'punto_venta', _('Punto de Venta')
    PAYPAL = 'paypal', _('PayPal')
    ZINLI = 'zinli', _('Zinli')
    WALLY = 'wally', _('Wally')
    OTRO = 'otro', _('Otro Método')


VENEZUELAN_BANKS_CATALOG = [
    {"code": "0102", "name": "Banco de Venezuela", "short_name": "BDV", "icon": "img/bank_icons/banco_de_venezuela.png"},
    {"code": "0134", "name": "Banesco", "short_name": "Banesco", "icon": "img/bank_icons/banesco.png"},
    {"code": "0105", "name": "Banco Mercantil", "short_name": "Mercantil", "icon": "img/bank_icons/banco_mercantil.png"},
    {"code": "0108", "name": "BBVA Provincial", "short_name": "Provincial", "icon": "img/bank_icons/banco_provincial.png"},
    {"code": "0191", "name": "Banco Nacional de Crédito (BNC)", "short_name": "BNC", "icon": "img/bank_icons/bnc.png"},
    {"code": "0172", "name": "Bancamiga", "short_name": "Bancamiga", "icon": "img/bank_icons/bancamiga.png"},
    {"code": "0114", "name": "Bancaribe", "short_name": "Bancaribe", "icon": ""},
    {"code": "0115", "name": "Banco Exterior", "short_name": "Exterior", "icon": "img/bank_icons/banco_exterior.png"},
    {"code": "0174", "name": "Banplus", "short_name": "Banplus", "icon": "img/bank_icons/banplus.png"},
    {"code": "0175", "name": "Banco Digital de los Trabajadores (BDT)", "short_name": "BDT", "icon": "img/bank_icons/banco_digital_de_los_trabajadores.png"},
    {"code": "0138", "name": "Banco Plaza", "short_name": "Plaza", "icon": "img/bank_icons/banco_plaza.png"},
    {"code": "0137", "name": "Banco Sofitasa", "short_name": "Sofitasa", "icon": "img/bank_icons/banco_sofitasa.png"},
    {"code": "0151", "name": "BFC Banco Fondo Común", "short_name": "BFC", "icon": ""},
    {"code": "0156", "name": "100% Banco", "short_name": "100% Banco", "icon": ""},
    {"code": "0163", "name": "Banco del Tesoro", "short_name": "Tesoro", "icon": ""},
    {"code": "0168", "name": "Bancrecer", "short_name": "Bancrecer", "icon": ""},
    {"code": "0169", "name": "R4 Banco Microfinanciero (Mi Banco)", "short_name": "R4 / Mi Banco", "icon": ""},
    {"code": "0171", "name": "Banco Activo", "short_name": "Activo", "icon": ""},
    {"code": "0177", "name": "BANFANB", "short_name": "BANFANB", "icon": ""},
    {"code": "0178", "name": "N58 Banco Digital", "short_name": "N58", "icon": ""},
]


class MerchantPaymentMethod(models.Model):
    """
    Métodos de cobro configurados por el comerciante para sus ventas y para envío
    en 1 toque dentro del chat de órdenes.
    """
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='payment_methods',
    )
    method_type = models.CharField(
        max_length=32,
        choices=MerchantPaymentMethodType.choices,
        default=MerchantPaymentMethodType.PAGO_MOVIL,
        db_index=True,
    )
    alias = models.CharField(
        max_length=120,
        blank=True,
        default='',
        help_text="Etiqueta opcional del método (ej. 'Pago Móvil Banesco Principal').",
    )
    bank_name = models.CharField(max_length=120, blank=True, default='')
    bank_code = models.CharField(max_length=10, blank=True, default='')
    phone = models.CharField(max_length=40, blank=True, default='')
    dni = models.CharField(
        max_length=40,
        blank=True,
        default='',
        help_text="Cédula o RIF asociado a la cuenta (ej. V-12345678 o J-31234567-8).",
    )
    document_type = models.CharField(max_length=10, blank=True, default='V')
    account_number = models.CharField(max_length=60, blank=True, default='')
    account_type = models.CharField(max_length=30, blank=True, default='')
    holder_name = models.CharField(max_length=150, blank=True, default='')
    email = models.CharField(max_length=150, blank=True, default='')
    wallet_id = models.CharField(max_length=120, blank=True, default='')
    currency = models.CharField(max_length=12, blank=True, default='Bs')
    notes = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_active', 'id']
        indexes = [
            models.Index(fields=['company', 'is_active'], name='mpm_company_active_idx'),
        ]

    def _sync_bank_metadata(self):
        code = (self.bank_code or '').strip()
        name = (self.bank_name or '').strip()
        if code and not name:
            for b in VENEZUELAN_BANKS_CATALOG:
                if b['code'] == code:
                    self.bank_name = b['name']
                    break
        elif name and not code:
            name_lower = name.lower()
            for b in VENEZUELAN_BANKS_CATALOG:
                if b['name'].lower() == name_lower or b['short_name'].lower() == name_lower or b['short_name'].lower() in name_lower:
                    self.bank_code = b['code']
                    break

    @staticmethod
    def clean_dni_parts(document_type: str = 'V', dni: str = '') -> tuple:
        """
        Retorna (doc_type, clean_dni_digits, dni_formatted) garantizando que jamás se duplique
        el prefijo (ej. evita 'V-V-30222103').
        """
        raw_dni = str(dni or '').strip()
        raw_doc_type = str(document_type or '').strip().upper()
        prefix_match = re.match(r'^([VEJGP])[-\s]*', raw_dni, flags=re.IGNORECASE)
        if prefix_match and not raw_doc_type:
            raw_doc_type = prefix_match.group(1).upper()
        clean_type = (raw_doc_type[:1] if raw_doc_type and raw_doc_type[0] in 'VEJGP' else 'V')
        clean_digits = re.sub(r'^([VEJGP][-\s]*)+', '', raw_dni, flags=re.IGNORECASE).strip()
        formatted = f"{clean_type}-{clean_digits}" if clean_digits else ""
        return clean_type, clean_digits, formatted

    def save(self, *args, **kwargs):
        self._sync_bank_metadata()
        if self.dni or self.document_type:
            clean_type, clean_digits, _ = self.clean_dni_parts(self.document_type, self.dni)
            self.document_type = clean_type
            self.dni = clean_digits
        if not self.currency:
            if self.method_type in (
                MerchantPaymentMethodType.ZELLE,
                MerchantPaymentMethodType.EFECTIVO_USD,
                MerchantPaymentMethodType.PAYPAL,
                MerchantPaymentMethodType.ZINLI,
                MerchantPaymentMethodType.WALLY,
            ):
                self.currency = 'USD'
            elif self.method_type == MerchantPaymentMethodType.BINANCE:
                self.currency = 'USDT'
            else:
                self.currency = 'Bs'
        super().save(*args, **kwargs)

    def get_copyable_fields(self) -> list:
        fields = []
        if self.bank_name or self.bank_code:
            bank_val = f"{self.bank_name} ({self.bank_code})".strip() if (self.bank_name and self.bank_code) else (self.bank_name or self.bank_code)
            fields.append({'key': 'bank', 'label': 'Banco', 'value': bank_val, 'copy_value': self.bank_code or self.bank_name})
        if self.phone:
            fields.append({'key': 'phone', 'label': 'Teléfono', 'value': self.phone, 'copy_value': self.phone})
        _, clean_digits, dni_formatted = self.clean_dni_parts(self.document_type, self.dni)
        if clean_digits:
            fields.append({'key': 'dni', 'label': 'C.I. / RIF', 'value': dni_formatted, 'copy_value': dni_formatted})
        if self.account_number:
            fields.append({'key': 'account_number', 'label': 'N° de Cuenta', 'value': self.account_number, 'copy_value': self.account_number})
        if self.holder_name:
            fields.append({'key': 'holder_name', 'label': 'Titular', 'value': self.holder_name, 'copy_value': self.holder_name})
        if self.email:
            fields.append({'key': 'email', 'label': 'Correo', 'value': self.email, 'copy_value': self.email})
        if self.wallet_id:
            fields.append({'key': 'wallet_id', 'label': 'ID / Pay ID', 'value': self.wallet_id, 'copy_value': self.wallet_id})
        return fields

    def format_chat_text(self) -> str:
        label = self.alias or self.get_method_type_display()
        lines = [f"💳 {label}"]
        for f in self.get_copyable_fields():
            lines.append(f"• {f['label']}: {f['value']}")
        if self.notes:
            lines.append(f"📌 Nota: {self.notes}")
        return "\n".join(lines)

    def get_json(self) -> dict:
        display_title = self.alias or self.get_method_type_display()
        clean_type, clean_digits, dni_formatted = self.clean_dni_parts(self.document_type, self.dni)
        return {
            'id': self.id,
            'company_id': str(self.company_id),
            'method_type': self.method_type,
            'type': self.method_type,
            'method_type_label': self.get_method_type_display(),
            'alias': display_title,
            'label': display_title,
            'title': display_title,
            'bank_name': self.bank_name,
            'bank_code': self.bank_code,
            'phone': self.phone,
            'phone_number': self.phone,
            'dni': clean_digits,
            'dni_formatted': dni_formatted,
            'identification': clean_digits,
            'document_number': clean_digits,
            'document_type': clean_type,
            'account_number': self.account_number,
            'account_type': self.account_type,
            'holder_name': self.holder_name,
            'beneficiary_name': self.holder_name,
            'email': self.email,
            'wallet_id': self.wallet_id,
            'pay_id': self.wallet_id,
            'currency': self.currency,
            'notes': self.notes,
            'instructions': self.notes,
            'is_active': self.is_active,
            'details': {
                'bank_name': self.bank_name,
                'bank_code': self.bank_code,
                'phone': self.phone,
                'phone_number': self.phone,
                'dni': clean_digits,
                'dni_formatted': dni_formatted,
                'identification': clean_digits,
                'document_type': clean_type,
                'document_number': clean_digits,
                'account_number': self.account_number,
                'account_type': self.account_type,
                'holder_name': self.holder_name,
                'email': self.email,
                'wallet_id': self.wallet_id,
                'notes': self.notes,
            },
            'copyable_fields': self.get_copyable_fields(),
            'formatted_text': self.format_chat_text(),
            'created_at': timezone.localtime(self.created_at).isoformat() if self.created_at else None,
            'updated_at': timezone.localtime(self.updated_at).isoformat() if self.updated_at else None,
        }


class Employee(models.Model):
    """
    Trabajador de un comercio (asistente o repartidor).

    Attributes:
        user (ForeignKey): Cuenta personal del trabajador.
        company (ForeignKey): Comercio que lo emplea.
        is_active (bool): Espejo de `status == ACTIVE` (se sincroniza en `save`).
        role (int): Rol dentro del comercio (`EmployeeRole`).
        status (int): Estado laboral (`EmployeeStatus`).
        vehicle_type (int): Vehículo del repartidor (`VehicleType`), opcional.
        display_alias (str): Nombre visible para el cliente.
        last_seen_at (datetime): Última actividad registrada en contexto de trabajador.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="employment_records")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="employees")
    is_active = models.BooleanField(default=True)
    hired_at = models.DateTimeField(auto_now_add=True)
    role = models.IntegerField(choices=EmployeeRole.choices, default=EmployeeRole.ASSISTANT)
    status = models.IntegerField(choices=EmployeeStatus.choices, default=EmployeeStatus.ACTIVE)
    vehicle_type = models.IntegerField(choices=VehicleType.choices, null=True, blank=True)
    display_alias = models.CharField(max_length=60, blank=True, default='')
    last_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('user', 'company') # Un usuario no puede ser empleado dos veces de la misma empresa
        indexes = [
            models.Index(fields=['company', 'role', 'status'], name='emp_company_role_status_idx'),
        ]

    def __str__(self):
        return f"{self.user} @ {self.company} ({self.get_role_display()})"

    def save(self, *args, **kwargs):
        # `is_active` siempre refleja el estado laboral para no romper el código que ya lo consulta
        self.is_active = (self.status == EmployeeStatus.ACTIVE)
        update_fields = kwargs.get('update_fields')
        if update_fields is not None and 'status' in update_fields and 'is_active' not in update_fields:
            kwargs['update_fields'] = list(update_fields) + ['is_active']
        super().save(*args, **kwargs)

    @property
    def role_slug(self) -> str:
        return EMPLOYEE_ROLE_SLUGS.get(self.role, 'assistant')

    def get_store_list(self) -> list:
        """
        Sucursales asignadas al trabajador (EmployeeStoreAssignment), como lista de dicts {id, name}.
        """
        prefetched = getattr(self, '_prefetched_objects_cache', None)
        if prefetched and 'employeestoreassignment_set' in prefetched:
            assignments = sorted(
                prefetched['employeestoreassignment_set'],
                key=lambda a: (a.store.name or '').lower()
            )
        else:
            assignments = self.employeestoreassignment_set.select_related('store').order_by('store__name')
        return [
            {'id': str(a.store_id), 'name': a.store.name}
            for a in assignments
        ]

    def get_json(self, include_company: bool = False) -> dict:
        user = self.user
        data = {
            'id': self.id,
            'user': {
                'id': str(user.id),
                'first_name': (user.first_name or '').strip(),
                'last_name': (user.last_name or '').strip(),
                'email': user.email,
                'profile_picture': user.get_profile_picture_url() if user.profile_picture else '',
                'cedula_verified': bool(user.cedula_verified),
            },
            'role': int(self.role),
            'role_slug': self.role_slug,
            'role_label': str(self.get_role_display()),
            'status': int(self.status),
            'status_label': str(self.get_status_display()),
            'is_active': self.is_active,
            'vehicle_type': int(self.vehicle_type) if self.vehicle_type is not None else None,
            'vehicle_type_label': str(self.get_vehicle_type_display()) if self.vehicle_type is not None else None,
            'display_alias': self.display_alias or '',
            'hired_at': timezone.localtime(self.hired_at).isoformat() if self.hired_at else None,
            'last_seen_at': timezone.localtime(self.last_seen_at).isoformat() if self.last_seen_at else None,
            'stores': self.get_store_list(),
        }
        if include_company:
            company = self.company
            data['company'] = {
                'id': str(company.id),
                'name': company.name,
                'image': storage_manager.get_url(company.image) if company.image else '',
            }
        return data

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


# Alfabeto sin caracteres ambiguos (sin 0/O, 1/I/L) para los códigos cortos escritos a mano
INVITATION_SHORT_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
INVITATION_SHORT_CODE_LENGTH = 8
INVITATION_DEFAULT_TTL_HOURS = 72


def default_invitation_expiry():
    """ Vencimiento por defecto de una invitación de trabajador (72 horas). """
    return timezone.now() + timedelta(hours=INVITATION_DEFAULT_TTL_HOURS)


class EmployeeInvitation(models.Model):
    """
    Invitación de un comercio para que un usuario de CartMaker trabaje como asistente o repartidor.

    El token en claro SOLO viaja en el enlace `https://www.cartmaker.app/join/<token>`;
    en la base de datos se guarda únicamente su hash SHA-256 (`token_hash`).
    `short_code` (8 caracteres) permite aceptar la invitación escribiéndola a mano.

    Attributes:
        company (ForeignKey): Comercio que invita.
        invited_by (ForeignKey): Usuario (dueño) que emitió la invitación.
        role (int): Rol ofrecido (`EmployeeRole`).
        allowed_stores (ManyToMany): Sucursales ofrecidas.
        channel (int): Canal de envío (`InvitationChannel`).
        target_email (str): Correo destinatario (opcional).
        target_user (ForeignKey): Usuario destinatario (opcional).
        token_hash (str): SHA-256 (hex) del token del enlace.
        short_code (str): Código corto de 8 caracteres.
        status (int): Estado (`InvitationStatus`).
        expires_at (datetime): Vencimiento (72 h por defecto).
        accepted_by (ForeignKey): Usuario que aceptó la invitación.
        accepted_at (datetime): Fecha de aceptación.
    """
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='employee_invitations')
    invited_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_employee_invitations')
    role = models.IntegerField(choices=EmployeeRole.choices, default=EmployeeRole.ASSISTANT)
    allowed_stores = models.ManyToManyField(CompanyStore, blank=True, related_name='employee_invitations')
    channel = models.IntegerField(choices=InvitationChannel.choices, default=InvitationChannel.QR_LINK)
    target_email = models.EmailField(null=True, blank=True)
    target_user = models.ForeignKey(
        User, on_delete=models.CASCADE, null=True, blank=True,
        related_name='received_employee_invitations'
    )
    token_hash = models.CharField(max_length=64, unique=True)
    short_code = models.CharField(max_length=INVITATION_SHORT_CODE_LENGTH, unique=True)
    status = models.IntegerField(choices=InvitationStatus.choices, default=InvitationStatus.PENDING)
    expires_at = models.DateTimeField(default=default_invitation_expiry)
    accepted_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='accepted_employee_invitations'
    )
    accepted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'status'], name='empinv_company_status_idx'),
            models.Index(fields=['target_user', 'status'], name='empinv_target_user_status_idx'),
            models.Index(fields=['target_email'], name='empinv_target_email_idx'),
        ]

    def __str__(self):
        return f"Invitación {self.short_code} · {self.company} ({self.get_status_display()})"

    @staticmethod
    def hash_token(raw_token: str) -> str:
        """ Retorna el SHA-256 (hex) del token en claro. """
        return hashlib.sha256(str(raw_token or '').encode('utf-8')).hexdigest()

    @staticmethod
    def normalize_short_code(raw_code: str) -> str:
        """ Normaliza el código corto escrito a mano (mayúsculas, sin espacios ni guiones). """
        return re.sub(r'[\s\-]', '', str(raw_code or '')).upper()

    @classmethod
    def generate_short_code(cls) -> str:
        """ Genera un código corto único con un alfabeto sin caracteres ambiguos. """
        for _attempt in range(12):
            code = ''.join(secrets.choice(INVITATION_SHORT_CODE_ALPHABET) for _i in range(INVITATION_SHORT_CODE_LENGTH))
            if not cls.objects.filter(short_code=code).exists():
                return code
        raise ValidationError("No se pudo generar un código de invitación único. Inténtalo de nuevo.")

    @classmethod
    def create_with_token(cls, *, company, invited_by, role, channel, target_email=None,
                          target_user=None, stores=None, ttl_hours: int = INVITATION_DEFAULT_TTL_HOURS):
        """
        Crea la invitación con un token nuevo (`secrets.token_urlsafe(32)`).

        Returns:
            tuple: (invitation, raw_token). El token en claro no se persiste.
        """
        raw_token = secrets.token_urlsafe(32)
        invitation = cls.objects.create(
            company=company,
            invited_by=invited_by,
            role=role,
            channel=channel,
            target_email=(target_email or '').strip().lower() or None,
            target_user=target_user,
            token_hash=cls.hash_token(raw_token),
            short_code=cls.generate_short_code(),
            expires_at=timezone.now() + timedelta(hours=ttl_hours),
        )
        if stores:
            invitation.allowed_stores.set(stores)
        return invitation, raw_token

    def is_expired(self) -> bool:
        return bool(self.expires_at and self.expires_at <= timezone.now())

    @property
    def effective_status(self) -> int:
        """ Estado real: una invitación PENDING vencida se reporta como EXPIRED. """
        if self.status == InvitationStatus.PENDING and self.is_expired():
            return InvitationStatus.EXPIRED
        return int(self.status)

    @property
    def role_slug(self) -> str:
        return EMPLOYEE_ROLE_SLUGS.get(self.role, 'assistant')

    def get_json(self, include_company: bool = True) -> dict:
        """ Representación pública de la invitación. Nunca incluye `token_hash`. """
        eff_status = self.effective_status
        target_user = self.target_user
        accepted_by = self.accepted_by
        invited_by = self.invited_by
        company = self.company
        company_img = storage_manager.get_url(company.image) if (company and company.image) else ''
        company_cat = company.category.name if (company and getattr(company, 'category_id', None) and company.category) else ''
        company_rif = (getattr(company, 'rif_number', '') or '').strip() if company else ''
        inviter_name = (
            f"{(invited_by.first_name or '').strip()} {(invited_by.last_name or '').strip()}".strip()
            or invited_by.email
        ) if invited_by else ''

        stores_payload = []
        # Usa el prefetch (`Prefetch('allowed_stores', queryset=...select_related('location'))`) si existe
        for store in self.allowed_stores.all():
            loc = getattr(store, 'location', None)
            addr = (loc.name or '').strip() if loc else ''
            stores_payload.append({
                'id': str(store.id),
                'name': store.name,
                'address': addr,
            })

        data = {
            'id': self.id,
            'company_id': str(company.id) if company else '',
            'company_name': company.name if company else '',
            'company_image': company_img,
            'company_rif': company_rif,
            'company_category': company_cat,
            'invited_by_name': inviter_name,
            'role': int(self.role),
            'role_id': int(self.role),
            'role_slug': self.role_slug,
            'role_label': str(self.get_role_display()),
            'channel': int(self.channel),
            'channel_label': str(self.get_channel_display()),
            'status': int(eff_status),
            'status_label': str(InvitationStatus(eff_status).label),
            'is_valid': eff_status == InvitationStatus.PENDING,
            'short_code': self.short_code,
            'target_email': self.target_email,
            'target_user': {
                'id': str(target_user.id),
                'first_name': (target_user.first_name or '').strip(),
                'last_name': (target_user.last_name or '').strip(),
                'email': target_user.email,
            } if target_user else None,
            'invited_by': {
                'id': str(invited_by.id),
                'first_name': (invited_by.first_name or '').strip(),
                'last_name': (invited_by.last_name or '').strip(),
                'full_name': inviter_name,
            } if invited_by else None,
            'accepted_by': {
                'id': str(accepted_by.id),
                'first_name': (accepted_by.first_name or '').strip(),
                'last_name': (accepted_by.last_name or '').strip(),
            } if accepted_by else None,
            'stores': stores_payload,
            'expires_at': timezone.localtime(self.expires_at).isoformat() if self.expires_at else None,
            'accepted_at': timezone.localtime(self.accepted_at).isoformat() if self.accepted_at else None,
            'created_at': timezone.localtime(self.created_at).isoformat() if self.created_at else None,
            'company': {
                'id': str(company.id),
                'name': company.name,
                'image': company_img,
                'rif': company_rif,
                'category': company_cat,
            } if company else None,
        }
        return data


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

    def get_product_schema(self) -> dict:
        from api.core.category_schemas import get_subcategory_schema
        return get_subcategory_schema(parent_category_name=self.name)

    def get_json(self) -> dict:
        subs = []
        for sub in self.subcategories.all():
            sub._state.fields_cache.setdefault('parent_category', self)
            subs.append({
                "id": sub.id,
                "name": sub.name,
                "img_url": sub.get_img_url(),
                "product_schema": sub.get_product_schema(),
            })
        return {
            "id": self.id,
            "name": self.name,
            "img_url": self.get_img_url(),
            "default_product_schema": self.get_product_schema(),
            "sub_categories": subs,
        }
    
    def get_img_url(self) -> str:
        """
        Retorna la URL pública de la imagen de la categoría principal.
        Sincroniza automáticamente con CATALOGO_ESTRUCTURA y agrega ?v=<mtime>
        para que cualquier cambio de imagen en disco invalide el caché de red en Flutter.
        """
        raw_path = (self.img_url or "").strip()
        if raw_path.startswith('http'):
            return raw_path

        clean_path = raw_path.lstrip('/')
        try:
            import os
            from api.core.category_schemas import CATALOGO_ESTRUCTURA
            cat_name_clean = (self.name or "").strip().lower()
            for cat_entry in CATALOGO_ESTRUCTURA:
                if cat_entry.get('categoria', '').strip().lower() == cat_name_clean:
                    official_img = (cat_entry.get('imagen') or '').strip().lstrip('/')
                    if official_img and official_img != clean_path:
                        clean_path = official_img
                        self.img_url = official_img
                        if self.pk:
                            Category.objects.filter(pk=self.pk).update(img_url=official_img)
                    break

            if not clean_path:
                return ""

            base_url = f"{settings.DOMAIN}/{clean_path}"
            local_file = os.path.join(settings.BASE_DIR, 'api', clean_path)
            if not os.path.exists(local_file):
                local_file = os.path.join(settings.BASE_DIR, clean_path)
            if os.path.exists(local_file):
                mtime = int(os.path.getmtime(local_file))
                return f"{base_url}?v={mtime}"
            return base_url
        except Exception:
            if not clean_path:
                return ""
            return f"{settings.DOMAIN}/{clean_path}"

class SubCategory(models.Model):
    """
    Sub-segmento de productos.

    Attributes:
        name (str): Nombre de la subcategoría.
        parent_category (ForeignKey): Categoría padre.
        schema_config (json): Configuración dinámica opcional de campos, unidades y variantes.
    """
    name = models.CharField(max_length=255)
    parent_category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='subcategories')
    img_url = models.CharField(help_text="Colocar ruta a traves del endpoint static del servidor. Ej: static/img/test.png", blank=True, null=True)
    schema_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Overrides opcionales del esquema dinámico de producto para esta subcategoría."
    )

    def get_product_schema(self) -> dict:
        from api.core.category_schemas import get_subcategory_schema
        parent_name = self.parent_category.name if self.parent_category_id else None
        return get_subcategory_schema(
            subcategory_name=self.name,
            parent_category_name=parent_name,
            custom_override=self.schema_config if isinstance(self.schema_config, dict) else None,
        )

    def get_json(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "parent_category": self.parent_category_id,
            "parent_category_name": self.parent_category.name if self.parent_category_id else "",
            "img_url": self.get_img_url(),
            "product_schema": self.get_product_schema(),
        }
    
    def get_img_url(self) -> str:
        """
        Retorna la URL publica de la imagen de la sub-categoria.
        Resuelve automáticamente la nueva estructura de subcarpetas por categoría padre
        (static/img/categories/sub_categories/<categoria>/<archivo>.jpg) y agrega ?v=<mtime>.
        """
        if not self.img_url:
            return ""
        raw_path = self.img_url.strip()
        if raw_path.startswith('http'):
            return raw_path

        clean_path = raw_path.lstrip('/')
        try:
            import os
            from api.core.category_schemas import CATALOGO_ESTRUCTURA
            sub_name_lower = (self.name or '').strip().lower()
            resolved_path = None
            for cat_entry in CATALOGO_ESTRUCTURA:
                for sub_entry in cat_entry.get('subcategorias', []):
                    if sub_entry.get('nombre', '').strip().lower() == sub_name_lower:
                        resolved_path = (sub_entry.get('imagen') or '').strip().lstrip('/')
                        break
                if resolved_path:
                    break

            if not resolved_path and clean_path.startswith('static/img/categories/sub_categories/') and clean_path.count('/') == 4:
                filename = clean_path.rsplit('/', 1)[-1].lower()
                for cat_entry in CATALOGO_ESTRUCTURA:
                    for sub_entry in cat_entry.get('subcategorias', []):
                        entry_img = (sub_entry.get('imagen') or '').strip().lstrip('/')
                        if entry_img.lower().endswith(f"/{filename}"):
                            resolved_path = entry_img
                            break
                    if resolved_path:
                        break

            if resolved_path and resolved_path != clean_path:
                clean_path = resolved_path
                self.img_url = resolved_path
                if self.pk:
                    SubCategory.objects.filter(pk=self.pk).update(img_url=resolved_path)

            base_url = f"{settings.DOMAIN}/{clean_path}"
            local_file = os.path.join(settings.BASE_DIR, 'api', clean_path)
            if not os.path.exists(local_file):
                local_file = os.path.join(settings.BASE_DIR, clean_path)
            if os.path.exists(local_file):
                mtime = int(os.path.getmtime(local_file))
                return f"{base_url}?v={mtime}"
            return base_url
        except Exception:
            return f"{settings.DOMAIN}/{clean_path}"
    
    def __str__(self) -> str:
        return f"{self.parent_category.name} - {self.name}"

class Product(models.Model):
    """
    Catálogo maestro de productos por compañía, con soporte dinámico según su categoría/subcategoría.

    Attributes:
        id (uuid): ID único del producto.
        name (str): Nombre descriptivo del artículo.
        price (Decimal): Precio base de referencia (por la unidad definida en `selling_unit`).
        creation (datetime): Fecha de registro.
        category (ForeignKey): Subcategoría asignada.
        description (str): Detalles técnicos o comerciales.
        discounts_by_tokens_active (bool): Habilita canje de tokens.
        discounts_data (json): Configuración de reglas de descuento.
        company (ForeignKey): Empresa propietaria del producto.
        images (json): Lista de URLs de imágenes del producto.
        selling_unit (str): Unidad de venta ('unit', 'kg', 'g', 'lb', 'l', 'ml', 'pack', 'box', 'portion', 'combo', 'pair', 'set', 'm', 'm2', 'gal').
        unit_label (str): Etiqueta corta de la unidad (ej. 'und', 'kg', 'g', 'porción', 'par').
        allow_fractional_quantity (bool): Permite pedir cantidades decimales (ej. 0.5 kg, 1.25 kg).
        min_order_quantity (Decimal): Cantidad mínima por orden.
        unit_step (Decimal): Incremento del selector de cantidad en el frontend.
        attributes (json): Diccionario de atributos específicos de la categoría (marca, modelo, talla, año, etc.).
        variants (json): Lista de variantes seleccionables (tallas/colores, presentaciones de peso, capacidades) con su precio/stock.
        modifier_groups (json): Grupos de extras/contornos/preparación estilo PedidosYa.
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
    selling_unit = models.CharField(
        max_length=32,
        default="unit",
        help_text="Unidad de venta: unit, kg, g, lb, l, ml, pack, box, portion, combo, pair, set, m, m2, gal."
    )
    unit_label = models.CharField(
        max_length=50,
        default="und",
        blank=True,
        help_text="Etiqueta corta visible de la unidad (ej. 'und', 'kg', 'g', 'porción', 'par')."
    )
    allow_fractional_quantity = models.BooleanField(
        default=False,
        help_text="Si es True, el comprador puede pedir fracciones (ej. 0.5 kg, 1.5 kg)."
    )
    min_order_quantity = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=1.000,
        help_text="Cantidad mínima por pedido en la unidad de venta."
    )
    unit_step = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=1.000,
        help_text="Incremento/paso del selector de cantidad en el frontend (ej. 0.25 para kg, 1 para unidad)."
    )
    attributes = models.JSONField(
        default=dict,
        blank=True,
        help_text="Atributos dinámicos según la categoría (ej. marca, modelo, almacenamiento, tela, año, kilometraje)."
    )
    variants = models.JSONField(
        default=list,
        blank=True,
        help_text="Variantes seleccionables (ej. tallas/colores, presentaciones de peso 250g/500g/1kg, tamaños)."
    )
    modifier_groups = models.JSONField(
        default=list,
        blank=True,
        help_text="Grupos de modificadores/extras estilo PedidosYa (ej. contornos, salsas, tipo de corte, maduración)."
    )

    class Meta:
        indexes = [
            GinIndex(
                name='product_name_gin_idx', 
                fields=['name'], 
                opclasses=['gin_trgm_ops']
            ),
            GinIndex(
                name='product_desc_gin_idx', 
                fields=['description'], 
                opclasses=['gin_trgm_ops']
            ),
        ]

    def __str__(self):
        return f"{self.name} - {self.company.name}"

    def get_json(self)->dict:
        from api.core.category_schemas import (
            SELLING_UNITS_CATALOG,
            get_subcategory_schema,
            normalize_modifier_groups,
            normalize_variants,
        )
        images = []
        for img_url in (self.images or []):
            images.append(storage_manager.get_url(img_url))
        category = self.category
        if category is None:
            category_data = {
                "id": None,
                "name": "General",
                "parent_category_id": None,
                "parent_category_name": "General",
            }
            schema = get_subcategory_schema()
        else:
            parent_cat = category.parent_category if category.parent_category_id else None
            category_data = {
                'id': self.category_id,
                'name': category.name,
                'parent_category_id': category.parent_category_id,
                'parent_category_name': parent_cat.name if parent_cat else "",
            }
            schema = category.get_product_schema()

        base_price = float(self.price)
        selling_unit_code = (self.selling_unit or schema.get("default_selling_unit") or "unit").strip().lower()
        unit_meta = SELLING_UNITS_CATALOG.get(selling_unit_code, SELLING_UNITS_CATALOG["unit"])
        unit_label_val = (self.unit_label or unit_meta["short_label"]).strip()

        normalized_variants = normalize_variants(self.variants, base_price=base_price)
        normalized_modifiers = normalize_modifier_groups(self.modifier_groups)
        attrs = self.attributes if isinstance(self.attributes, dict) else {}

        data = {
            "id": str(self.id),
            "name": self.name,
            "price": base_price,
            "creation": timezone.localtime(self.creation),
            "category": category_data,
            "category_archetype": schema.get("archetype", "general"),
            "description": self.description,
            "discounts_by_tokens_active": self.discounts_by_tokens_active if self.company.gamification_enabled else False,
            "discounts_data": self.discounts_data,
            "company_id": self.company_id,
            "images": images,
            "selling_unit": selling_unit_code,
            "unit_label": unit_label_val,
            "price_label": unit_meta.get("price_label", "Precio por unidad"),
            "allow_fractional_quantity": bool(self.allow_fractional_quantity),
            "min_order_quantity": float(self.min_order_quantity or 1.0),
            "unit_step": float(self.unit_step or 1.0),
            "attributes": attrs,
            "variants": normalized_variants,
            "modifier_groups": normalized_modifiers,
            "has_variants": len(normalized_variants) > 0,
            "has_modifier_groups": len(normalized_modifiers) > 0,
            "order_notes_enabled": bool(schema.get("order_notes_enabled", True)),
            "order_notes_placeholder": schema.get("order_notes_placeholder", ""),
        }
        return data


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
    store = models.ForeignKey(CompanyStore, on_delete=models.CASCADE, related_name='product_items')
    creation = models.DateTimeField(auto_now_add=True, db_index=True)
    sold_out_time = models.DateTimeField(null=True, blank=True)
    expiration_date = models.DateTimeField(null=True, blank=True)
    custom_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    paused = models.BooleanField(default=False)
    cached_popularity_score = models.FloatField(
        default=0.0, 
        db_index=True,
        help_text="Puntuación precalculada de interacciones (visitas, carritos, compras). Evita JOINs masivos. Usado por el motor de busqueda."
    )

    class Meta:
        indexes = [
            models.Index(fields=['store', 'paused', 'stock'], name='inv_store_paused_stock_idx'),
            models.Index(fields=['paused', 'stock'], name='inv_paused_stock_idx'),
        ]

    def _active_offer(self):
        try:
            offer = self.offer
        except Exception:
            return None
        if offer and offer.valid_until and offer.valid_until >= timezone.now():
            return offer
        return None

    def get_list_price(self) -> float:
        if self.custom_price is not None:
            return float(self.custom_price)
        return float(self.product.price)

    def get_effective_price(self) -> float:
        base = self.get_list_price()
        offer = self._active_offer()
        if not offer:
            return round(base, 2)
        pct = max(0, min(100, int(offer.percentage or 0)))
        return round(base * ((100 - pct) / 100.0), 2)

    def _distance_meters_value(self):
        for attr in ('real_distance_meters', 'distance_to_user'):
            distance = getattr(self, attr, None)
            if distance is None:
                continue
            try:
                meters = float(distance.m) if hasattr(distance, 'm') else float(distance)
                return round(meters, 1)
            except (TypeError, ValueError, AttributeError):
                continue
        return None

    def get_json(self) -> dict:
        offer = self._active_offer()
        list_price = self.get_list_price()
        effective_price = self.get_effective_price()
        if (
            'store' in self._state.fields_cache
            and 'company' in self.store._state.fields_cache
            and 'product' in self._state.fields_cache
            and self.product.company_id == self.store.company_id
        ):
            self.product._state.fields_cache.setdefault('company', self.store.company)

        dist_m = self._distance_meters_value()
        is_very_close = getattr(self, 'is_very_close', None)
        if is_very_close is None:
            is_very_close = (dist_m is not None and dist_m < 600.0)
        is_close = getattr(self, 'is_close', None)
        if is_close is None:
            is_close = (dist_m is not None and 600.0 <= dist_m <= 1200.0)

        return {
            "id": str(self.id),
            "product": self.product.get_json(),
            "stock": self.stock,
            "store_id": self.store_id,
            "store_name": self.store.name,
            "creation": timezone.localtime(self.creation) if self.creation else None,
            "company_name": self.store.company.name,
            "company_image": storage_manager.get_url(self.store.company.image),
            "sold_out_time": timezone.localtime(self.sold_out_time) if self.sold_out_time else None,
            "expiration_date": timezone.localtime(self.expiration_date) if self.expiration_date else None,
            "custom_price": float(self.custom_price) if self.custom_price is not None else None,
            "paused": self.paused,
            "offer": offer.get_json() if offer else None,
            "offer_percentage": int(offer.percentage) if offer else 0,
            "list_price": round(list_price, 2),
            "effective_price": effective_price,
            "avg_rating": round(float(getattr(self, 'avg_rating', 0.0)), 2),
            "rating_count": int(getattr(self, 'rating_count', 0)),
            "merchant_avg_rating": round(float(getattr(self, 'merchant_avg_rating', 0.0)), 2),
            "merchant_rating_count": int(getattr(self, 'merchant_rating_count', 0)),
            "is_platinum": bool(getattr(self.store.company, 'is_platinum', False)),
            "is_very_close": bool(is_very_close),
            "is_close": bool(is_close),
            "is_liked": bool(getattr(self, 'is_liked', False)),
            "likes_count": getattr(self, 'likes_count', 0),
            "work_hours": self.store.effective_work_hours,
            "work_days": self.store.effective_work_days,
            "is_open_now": self.store.is_currently_open,
            "distance_meters": dist_m,
        }
    
    def __str__(self):
        return self.product.name

class InventoryItemOffer(models.Model):
    """
    Promociones temporales aplicadas a ítems específicos.

    Attributes:
        product_item (OneToOne): Ítem en oferta.
        valid_until (datetime): Fecha de expiración de la oferta.
        percentage (int): Porcentaje de descuento aplicado.
    """
    product_item = models.OneToOneField(InventoryItem, on_delete=models.CASCADE, related_name='offer')
    valid_until = models.DateTimeField(db_index=True)
    percentage = models.IntegerField()

    def get_json(self) -> dict:
        return {
            "valid_until": timezone.localtime(self.valid_until),
            "percentage": self.percentage
        }

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
    cancellation_topic = models.IntegerField(choices=CancellationReason.choices, null=True, blank=True)
    withdrawal_type = models.IntegerField(choices=WithdrawalType.choices)
    client_location = models.ForeignKey(ClientLocation, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['client', '-creation'], name='order_client_creation_idx'),
            models.Index(fields=['store', 'status', '-creation'], name='order_store_status_idx'),
            models.Index(fields=['status', 'creation'], name='order_status_creation_idx'),
        ]

    def get_delivery_json(self, viewer_user=None) -> Optional[dict]:
        """
        Bloque `delivery` de la orden (solo para órdenes con delivery que tengan DeliveryAssignment).
        Si `viewer_user` es None o es el comprador, se usa la vista del cliente (incluye el PIN de entrega);
        para cualquier otro usuario (comerciante) se usa la vista del comercio (sin PIN).
        """
        try:
            if int(self.withdrawal_type) != WithdrawalType.DELIVERY:
                return None
        except (TypeError, ValueError):
            return None
        assignment = getattr(self, 'delivery_assignment', None)
        if assignment is None:
            return None
        is_client = viewer_user is None or getattr(viewer_user, 'id', None) == self.client_id
        return assignment.get_json(viewer_role='client' if is_client else 'merchant')


# ==========================================
# MÓDULO 4.1: DELIVERY EN TIEMPO REAL
# ==========================================

def default_trace_expiry():
    """ Las trazas GPS crudas se eliminan a los 30 días (Habeas Data, Art. 28). """
    return timezone.now() + timedelta(days=30)


def _geo_point_json(point) -> Optional[dict]:
    if point is None:
        return None
    return {'lat': float(point.y), 'lng': float(point.x)}


def _dt_iso(value) -> Optional[str]:
    return timezone.localtime(value).isoformat() if value else None


def _dt_ms(value) -> Optional[int]:
    return int(value.timestamp() * 1000) if value else None


def _haversine_between_points_m(p1, p2) -> float:
    """ Distancia (m) entre dos PointField (x=lng, y=lat). """
    import math
    if p1 is None or p2 is None:
        return 0.0
    lat1, lon1 = math.radians(p1.y), math.radians(p1.x)
    lat2, lon2 = math.radians(p2.y), math.radians(p2.x)
    a = math.sin((lat2 - lat1) / 2.0) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2.0) ** 2
    return 2.0 * 6371000.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))


class RiderShift(models.Model):
    """
    Turno de un repartidor en una sucursal. Mientras está abierto, el repartidor manda un latido
    de ubicación cada 60 s (la posición caliente vive en Redis `rider:{emp_id}:loc`, TTL 120 s).
    Fuera de turno no hay ningún rastreo.
    """
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='shifts')
    store = models.ForeignKey(CompanyStore, on_delete=models.CASCADE, related_name='rider_shifts')
    is_active = models.BooleanField(default=True, db_index=True)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    last_point = gis_models.PointField(srid=4326, null=True, blank=True)
    last_heartbeat_at = models.DateTimeField(null=True, blank=True)
    battery_level = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['store', 'is_active'], name='ridershift_store_active_idx'),
            models.Index(fields=['employee', 'is_active'], name='ridershift_emp_active_idx'),
        ]

    def __str__(self):
        return f"Turno de {self.employee_id} en {self.store_id} ({'abierto' if self.is_active else 'cerrado'})"

    def get_json(self) -> dict:
        store = self.store
        return {
            'id': self.id,
            'employee_id': self.employee_id,
            'store': {'id': str(store.id), 'name': store.name},
            'is_active': self.is_active,
            'started_at': _dt_iso(self.started_at),
            'ended_at': _dt_iso(self.ended_at),
            'last_heartbeat_at': _dt_iso(self.last_heartbeat_at),
            'battery_level': self.battery_level,
            'last_point': _geo_point_json(self.last_point),
        }


class DeliveryAssignment(models.Model):
    """
    Entrega a domicilio de una orden (1:1 con Order).

    `origin_point` y `dest_point` son COPIAS CONGELADAS de la tienda y del cliente
    (`client_location` usa SET_NULL y el cliente puede editarla).
    `route_cum_dist` / `route_cum_time` son el perfil de tiempos por tramo de la ruta planificada:
    la base matemática del protocolo de predicción (Dead Reckoning).
    `tracking_key` autentica paquetes BLE y entregas offline; `handoff_pin` solo lo ve el cliente.
    """
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='delivery_assignment')
    store = models.ForeignKey(CompanyStore, on_delete=models.CASCADE, related_name='delivery_assignments')
    rider = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name='deliveries')
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_deliveries')
    is_auto_assigned = models.BooleanField(default=True)
    status = models.IntegerField(choices=DeliveryStatus.choices, default=DeliveryStatus.PENDING_RIDER, db_index=True)

    origin_point = gis_models.PointField(srid=4326)
    dest_point = gis_models.PointField(srid=4326)
    dest_address_snapshot = models.TextField(blank=True, default='')

    route_geometry = gis_models.LineStringField(srid=4326, null=True, blank=True)
    route_polyline6 = models.TextField(blank=True, default='')
    route_cum_dist = models.JSONField(default=list, blank=True)
    route_cum_time = models.JSONField(default=list, blank=True)
    route_version = models.PositiveIntegerField(default=1)
    route_distance_m = models.FloatField(default=0.0)
    route_duration_s = models.FloatField(default=0.0)
    eta_at = models.DateTimeField(null=True, blank=True)

    tracking_key = models.CharField(max_length=64, default='')
    handoff_pin = models.CharField(max_length=4, default='')
    handoff_pin_hash = models.CharField(max_length=128, default='')
    pin_attempts = models.PositiveSmallIntegerField(default=0)

    declined_rider_ids = models.JSONField(default=list, blank=True)
    offer_expires_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.CharField(max_length=255, blank=True, default='')

    last_fix_point = gis_models.PointField(srid=4326, null=True, blank=True)
    last_fix_speed_mps = models.FloatField(null=True, blank=True)
    last_fix_heading = models.FloatField(null=True, blank=True)
    last_fix_accuracy_m = models.FloatField(null=True, blank=True)
    last_fix_at = models.DateTimeField(null=True, blank=True)
    last_fix_source = models.IntegerField(choices=FixSource.choices, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    assigned_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    at_store_at = models.DateTimeField(null=True, blank=True)
    picked_up_at = models.DateTimeField(null=True, blank=True)
    arriving_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=['rider'],
                condition=Q(status__in=[1, 2, 3, 4, 5]),
                name='one_active_delivery_per_rider',
            ),
        ]
        indexes = [
            models.Index(fields=['store', 'status'], name='dlv_store_status_idx'),
            models.Index(fields=['rider', 'status'], name='dlv_rider_status_idx'),
            models.Index(fields=['status', 'offer_expires_at'], name='dlv_status_offer_idx'),
        ]

    def __str__(self):
        return f"Delivery #{self.id} · Orden {self.order_id} ({self.get_status_display()})"

    @property
    def is_active(self) -> bool:
        return int(self.status) in DELIVERY_ACTIVE_STATUSES

    def get_rider_public_json(self, include_employee_id: bool = False) -> Optional[dict]:
        rider = self.rider
        if rider is None:
            return None
        user = rider.user
        alias = (rider.display_alias or '').strip()
        if not alias:
            last_initial = (user.last_name or '').strip()[:1]
            alias = f"{(user.first_name or '').strip()} {last_initial + '.' if last_initial else ''}".strip() or 'Repartidor'
        data = {
            'display_name': alias,
            'vehicle_type': int(rider.vehicle_type) if rider.vehicle_type is not None else None,
            'vehicle_type_label': str(rider.get_vehicle_type_display()) if rider.vehicle_type is not None else None,
            'profile_picture': user.get_profile_picture_url() if user.profile_picture else '',
        }
        if include_employee_id:
            data['employee_id'] = rider.id
        return data

    def get_json(self, viewer_role: str = 'client') -> dict:
        """
        Representación con privacidad estricta (Habeas Data, Art. 28):
        - client: incluye `handoff_pin`; ve al repartidor, su posición y la ruta SOLO en PICKED_UP / ARRIVING.
        - rider: NUNCA ve el PIN; ve la dirección exacta del cliente solo desde ACCEPTED
          (en ASSIGNED solo una zona aproximada ~1 km y una distancia estimada).
        - merchant: NUNCA ve el PIN ni `tracking_key`; ve la posición del repartidor desde ACCEPTED.
        `tracking_key` y `handoff_pin_hash` nunca se incluyen aquí (la clave va solo en el bootstrap del repartidor).
        """
        status_value = int(self.status)
        data = {
            'id': self.id,
            'order_id': self.order_id,
            'store_id': str(self.store_id),
            'store_name': self.store.name if self.store_id else '',
            'status': status_value,
            'status_label': str(DeliveryStatus(status_value).label),
            'is_active': status_value in DELIVERY_ACTIVE_STATUSES,
            'route_version': self.route_version,
            'eta_at': _dt_iso(self.eta_at),
            'eta_at_ms': _dt_ms(self.eta_at),
            'origin': _geo_point_json(self.origin_point),
            'failure_reason': self.failure_reason or '',
            'tracking_room': f"delivery_{self.id}",
            'timestamps': {
                'created_at': _dt_iso(self.created_at),
                'assigned_at': _dt_iso(self.assigned_at),
                'accepted_at': _dt_iso(self.accepted_at),
                'at_store_at': _dt_iso(self.at_store_at),
                'picked_up_at': _dt_iso(self.picked_up_at),
                'arriving_at': _dt_iso(self.arriving_at),
                'delivered_at': _dt_iso(self.delivered_at),
                'cancelled_at': _dt_iso(self.cancelled_at),
            },
        }

        in_transit = status_value in (DeliveryStatus.PICKED_UP, DeliveryStatus.ARRIVING)
        show_dest_exact = False
        show_route = False
        show_fix = False
        show_rider = False
        include_employee_id = False

        if viewer_role == 'rider':
            show_dest_exact = status_value in (
                DeliveryStatus.ACCEPTED, DeliveryStatus.AT_STORE, DeliveryStatus.PICKED_UP,
                DeliveryStatus.ARRIVING, DeliveryStatus.DELIVERED, DeliveryStatus.FAILED,
            )
            show_route = show_dest_exact
            show_fix = True
            show_rider = True
            include_employee_id = True
            data['is_auto_assigned'] = self.is_auto_assigned
            data['offer_expires_at'] = _dt_iso(self.offer_expires_at)
            data['offer_expires_at_ms'] = _dt_ms(self.offer_expires_at)
            data['pin_attempts_remaining'] = max(0, DELIVERY_MAX_PIN_ATTEMPTS - int(self.pin_attempts or 0))
        elif viewer_role == 'merchant':
            show_dest_exact = True
            show_route = status_value >= DeliveryStatus.ACCEPTED and status_value != DeliveryStatus.CANCELLED
            show_fix = status_value in (
                DeliveryStatus.ACCEPTED, DeliveryStatus.AT_STORE, DeliveryStatus.PICKED_UP, DeliveryStatus.ARRIVING,
            )
            show_rider = True
            include_employee_id = True
            data['is_auto_assigned'] = self.is_auto_assigned
            data['offer_expires_at'] = _dt_iso(self.offer_expires_at)
            data['offer_expires_at_ms'] = _dt_ms(self.offer_expires_at)
            data['declined_count'] = len(self.declined_rider_ids or [])
        else:
            # Cliente (comprador)
            show_dest_exact = True
            show_route = in_transit
            show_fix = in_transit
            show_rider = in_transit
            include_employee_id = in_transit
            data['handoff_pin'] = self.handoff_pin if status_value not in DELIVERY_TERMINAL_STATUSES else None
            data['has_rider'] = self.rider_id is not None and status_value in DELIVERY_ACTIVE_STATUSES

        if show_dest_exact:
            dest = _geo_point_json(self.dest_point)
            if dest is not None:
                dest['address'] = self.dest_address_snapshot or ''
            data['destination'] = dest
        elif viewer_role == 'rider' and self.dest_point is not None:
            data['destination_zone'] = {
                'lat': round(float(self.dest_point.y), 2),
                'lng': round(float(self.dest_point.x), 2),
                'approx_radius_m': 1000,
            }
            data['estimated_distance_m'] = round(
                _haversine_between_points_m(self.origin_point, self.dest_point) * 1.28
            )

        if show_route and self.route_polyline6:
            data['route'] = {
                'version': self.route_version,
                'polyline6': self.route_polyline6,
                'distance_m': self.route_distance_m,
                'duration_s': self.route_duration_s,
            }

        if show_fix and self.last_fix_point is not None:
            source_int = int(self.last_fix_source) if self.last_fix_source is not None else None
            try:
                source_lbl = str(FixSource(source_int).label) if source_int is not None else None
            except ValueError:
                source_lbl = None
            data['last_fix'] = {
                'lat': float(self.last_fix_point.y),
                'lng': float(self.last_fix_point.x),
                'speed_mps': self.last_fix_speed_mps,
                'heading': self.last_fix_heading,
                'accuracy_m': self.last_fix_accuracy_m,
                'at': _dt_iso(self.last_fix_at),
                'at_ms': _dt_ms(self.last_fix_at),
                'source': source_int,
                'source_label': source_lbl,
            }

        if show_rider:
            data['rider'] = self.get_rider_public_json(include_employee_id=include_employee_id)

        return data


class DeliveryTrace(models.Model):
    """
    Traza real de una entrega (una fila por entrega, se escribe al terminar o al subir el buffer offline).

    `compressed_points` = gzip(msgpack(lista de puntos)), cada punto como
    `[t_ms, lat_e7, lng_e7, v_cms, heading_cd, acc_dm, source]` (t_ms relativo a `assigned_at`).
    Se elimina a los 30 días (`expires_at`).
    """
    delivery = models.OneToOneField(DeliveryAssignment, on_delete=models.CASCADE, related_name='trace')
    compressed_points = models.BinaryField(null=True, blank=True)
    matched_polyline6 = models.TextField(blank=True, default='')
    point_count = models.PositiveIntegerField(default=0)
    max_gap_s = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=default_trace_expiry, db_index=True)

    def __str__(self):
        return f"Traza de delivery #{self.delivery_id} ({self.point_count} puntos)"

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

    def get_json(self)->dict:
        return {
            "id":self.id,
            "balance":self.balance,
            "creation":timezone.localtime(self.creation).strftime("%d/%m/%Y, %H:%M:%S")
        }

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

    class TicketTopic(models.IntegerChoices):
        ORDER_ISSUE = 0, 'Problema con una Orden'
        STORE_COMPLAINT = 1, 'Reclamo sobre Tienda'
        ACCOUNT_ISSUE = 2, 'Problema con mi Cuenta'
        OTHER = 3, 'Otro'
        PRIVACY_HABEAS_DATA = 4, 'Privacidad y Habeas Data'

    class CloseReason(models.IntegerChoices):
        SOLVED = 0, 'Resuelto con éxito'
        UNRESOLVED = 1, 'No se pudo resolver'
        SPAM = 2, 'Spam / Inválido'
        NO_RESPONSE = 3, 'El cliente no responde'

    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='support_tickets')
    agent = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tickets')
    order = models.ForeignKey(
        Order,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='support_tickets',
        help_text='Orden reportada por el usuario o comercio (si aplica).',
    )
    topic = models.IntegerField(choices=TicketTopic.choices, default=TicketTopic.OTHER)
    title = models.CharField(max_length=200)
    description = models.TextField()
    closed = models.BooleanField(default=False)
    close_reason = models.IntegerField(choices=CloseReason.choices, null=True, blank=True)
    resolution_note = models.TextField(
        blank=True,
        default='',
        help_text='Conclusión o dictamen detallado escrito por el agente de soporte al cerrar el ticket.',
    )
    muted_client = models.BooleanField(
        default=False,
        help_text='Si es True, el comprador está silenciado temporalmente en este ticket.',
    )
    muted_merchant = models.BooleanField(
        default=False,
        help_text='Si es True, el comerciante está silenciado temporalmente en este ticket.',
    )
    mute_reason = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text='Motivo opcional del silenciamiento temporal.',
    )
    creation = models.DateTimeField(auto_now_add=True)
    close_time = models.DateTimeField(null=True, blank=True)
    waiting_for_client_reply = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=['client', '-creation'], name='ticket_client_creation_idx'),
            models.Index(fields=['closed', '-creation'], name='ticket_closed_creation_idx'),
        ]

    def get_buyer_user(self):
        if self.order_id and self.order and self.order.client_id:
            return self.order.client
        return self.client

    def get_merchant_company(self):
        if self.order_id and self.order and self.order.store_id and self.order.store and self.order.store.company_id:
            return self.order.store.company
        return None

    def get_merchant_user(self):
        company = self.get_merchant_company()
        if company and company.owner_id:
            return company.owner
        return None

    def get_reporter_info(self) -> dict:
        reporter_user = self.client if self.client_id else None
        reporter_uid_str = str(self.client_id) if self.client_id else None
        order_obj = self.order if self.order_id else None
        company = self.get_merchant_company()

        if order_obj is not None:
            merchant_owner_id = company.owner_id if company else None
            if merchant_owner_id and self.client_id == merchant_owner_id and self.client_id != order_obj.client_id:
                role = 'merchant'
            elif self.client_id == order_obj.client_id:
                role = 'client'
            else:
                cart_data = order_obj.cart if isinstance(order_obj.cart, dict) else {}
                raw_role = str(cart_data.get('reported_by_role') or '').strip().lower()
                role = 'merchant' if raw_role == 'merchant' else 'client'

            if role == 'merchant':
                reporter_name = (
                    company.name
                    if company and company.name
                    else (f"{reporter_user.first_name} {reporter_user.last_name}".strip() if reporter_user else 'Comercio')
                )
            else:
                buyer_u = order_obj.client if order_obj.client_id else reporter_user
                reporter_name = f"{buyer_u.first_name} {buyer_u.last_name}".strip() if buyer_u else 'Comprador'
        else:
            role = 'client'
            reporter_name = f"{reporter_user.first_name} {reporter_user.last_name}".strip() if reporter_user else 'Cliente'

        return {
            'reported_by_role': role,
            'reported_by_user_id': reporter_uid_str,
            'reporter_id': reporter_uid_str,
            'reported_by_name': reporter_name,
        }

    def get_participant_role(self, user_id) -> str:
        if not user_id:
            return 'client'
        uid_str = str(user_id)
        if self.agent_id and uid_str == str(self.agent_id):
            return 'support'
        if self.order_id and self.order:
            company = self.get_merchant_company()
            if company and company.owner_id and uid_str == str(company.owner_id) and uid_str != str(self.order.client_id):
                return 'merchant'
            if self.order.client_id and uid_str == str(self.order.client_id):
                return 'client'
            if company and company.owner_id and uid_str == str(company.owner_id):
                return 'merchant'
        if self.client_id and uid_str == str(self.client_id):
            return 'client'
        return 'support'

    def is_user_participant(self, user_or_id) -> bool:
        if user_or_id is None:
            return False
        if hasattr(user_or_id, 'id'):
            if getattr(user_or_id, 'is_superuser', False) or getattr(user_or_id, 'is_staff', False):
                return True
            uid_str = str(user_or_id.id)
        else:
            uid_str = str(user_or_id)

        allowed = set()
        if self.client_id:
            allowed.add(str(self.client_id))
        if self.agent_id:
            allowed.add(str(self.agent_id))
        if self.order_id and self.order:
            if self.order.client_id:
                allowed.add(str(self.order.client_id))
            company = self.get_merchant_company()
            if company and company.owner_id:
                allowed.add(str(company.owner_id))
        return uid_str in allowed

    def get_all_participant_ids(self) -> list:
        ids = []
        for candidate in (
            self.client_id,
            self.agent_id,
            self.order.client_id if (self.order_id and self.order) else None,
            self.get_merchant_company().owner_id if self.get_merchant_company() else None,
        ):
            if candidate:
                s = str(candidate)
                if s not in ids:
                    ids.append(s)
        return ids

    def is_user_muted(self, user_id) -> bool:
        if not user_id:
            return False
        role = self.get_participant_role(user_id)
        if role == 'client':
            return bool(self.muted_client)
        if role == 'merchant':
            return bool(self.muted_merchant)
        return False

    def get_muted_user_ids(self) -> list:
        muted_ids = []
        buyer_user = self.get_buyer_user()
        merchant_user = self.get_merchant_user()
        if self.muted_client and buyer_user:
            s = str(buyer_user.id)
            if s not in muted_ids:
                muted_ids.append(s)
        if self.muted_merchant and merchant_user:
            s = str(merchant_user.id)
            if s not in muted_ids:
                muted_ids.append(s)
        return muted_ids

    def get_json(self, current_user=None) -> dict:
        time_str = timezone.localtime(self.creation).strftime("%d/%m/%Y %I:%M %p").lower()
        unread_client = getattr(self, 'unread_client_count', None)
        if unread_client is None:
            unread_client = self.messages.filter(status__lt=3).exclude(sender_id=self.client_id).count()
        unread_agent = getattr(self, 'unread_agent_count', None)
        if unread_agent is None:
            unread_agent = self.messages.filter(status__lt=3).exclude(sender_id=self.agent_id).count() if self.agent_id else self.messages.count()

        agent_obj = self.agent if self.agent_id else None
        agent_full_name = f"{agent_obj.first_name} {agent_obj.last_name}".strip() if agent_obj else None
        if not agent_full_name:
            agent_full_name = None

        order_obj = self.order if self.order_id else None
        buyer_user = self.get_buyer_user()
        merchant_user = self.get_merchant_user()
        company = self.get_merchant_company()
        reporter_info = self.get_reporter_info()

        order_summary = None
        if order_obj is not None:
            cart_data = order_obj.cart if isinstance(order_obj.cart, dict) else {}
            try:
                total_amount = round(float(cart_data.get('total', 0.0) or 0.0), 2)
            except (ValueError, TypeError):
                total_amount = 0.0
            store_name = None
            if order_obj.store_id and order_obj.store:
                store_name = (
                    company.name
                    if company
                    else order_obj.store.name
                )
            order_summary = {
                'id': str(order_obj.id),
                'order_id': str(order_obj.id),
                'status': order_obj.status,
                'status_label': order_obj.get_status_display(),
                'total_amount': f"{total_amount:.2f}",
                'store_name': store_name,
                'created_at': order_obj.creation.isoformat() if order_obj.creation else None,
            }

        status_str = 'CLOSED' if self.closed else ('IN_PROGRESS' if self.agent_id else 'OPEN')
        close_reason_label = self.get_close_reason_display() if self.close_reason is not None else None
        resolution_note_clean = (self.resolution_note or '').strip() or None
        closed_at_str = timezone.localtime(self.close_time).strftime("%d/%m/%Y %I:%M %p").lower() if self.close_time else None

        has_explicit_user = bool(current_user is not None and getattr(current_user, 'is_authenticated', False))
        is_current_muted = self.is_user_muted(current_user.id) if has_explicit_user else None

        client_display_name = f"{buyer_user.first_name} {buyer_user.last_name}".strip() if buyer_user else None
        merchant_display_name = (
            company.name
            if company and company.name
            else (f"{merchant_user.first_name} {merchant_user.last_name}".strip() if merchant_user else None)
        )

        payload = {
            'id': self.id,
            'status': status_str,
            'client_id': str(self.client_id) if self.client_id else None,
            'client_user_id': str(buyer_user.id) if buyer_user else (str(self.client_id) if self.client_id else None),
            'client_name': client_display_name,
            'merchant_user_id': str(merchant_user.id) if merchant_user else None,
            'merchant_name': merchant_display_name,
            'agent_id': str(self.agent_id) if self.agent_id else None,
            'assigned_to_id': str(self.agent_id) if self.agent_id else None,
            'agent_name': agent_full_name,
            'assigned_to_name': agent_full_name,
            # 💡 1. ENVIAMOS LA FOTO DE PERFIL DEL AGENTE
            'agent_image': agent_obj.get_profile_picture_url() if agent_obj and agent_obj.profile_picture else None,
            'topic': self.get_topic_display(), 
            'topic_id': self.topic,
            'title': self.title,
            'description': self.description,
            'order': str(self.order_id) if self.order_id else None,
            'order_id': str(self.order_id) if self.order_id else None,
            'order_summary': order_summary,
            'is_tripartite': bool(self.order_id is not None),
            **reporter_info,
            'muted_client': bool(self.muted_client),
            'muted_merchant': bool(self.muted_merchant),
            'mute_reason': (self.mute_reason or '').strip() or None,
            'muted_user_ids': self.get_muted_user_ids(),
            'closed': self.closed,
            'close_reason': close_reason_label,
            'close_reason_id': self.close_reason,
            'resolution_outcome': close_reason_label,
            'resolution_note': resolution_note_clean,
            'closed_at': closed_at_str,
            'creation': time_str,
            'waiting_for_client_reply': self.waiting_for_client_reply,
            # 💡 2. ENVIAMOS LOS BADGES
            'unread_client': unread_client,
            'unread_agent': unread_agent,
        }
        if has_explicit_user:
            payload['is_current_user_muted'] = bool(is_current_muted)
            payload['is_muted'] = bool(is_current_muted)
        return payload

class SupportMessage(models.Model):
    class MessageType(models.TextChoices):
        TEXT = 'text', 'Texto'
        IMAGE = 'image', 'Imagen'
        AUDIO = 'audio', 'Nota de Voz'
        SYSTEM = 'system', 'Sistema'

    class DeliveryStatus(models.IntegerChoices):
        PENDING = 0, 'Enviando'
        SENT = 1, 'Enviado al Servidor'
        DELIVERED = 2, 'Entregado al Dispositivo'
        READ = 3, 'Leído'

    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_support_messages')
    text = models.TextField(blank=True, null=True)
    message_type = models.CharField(max_length=10, choices=MessageType.choices, default=MessageType.TEXT)
    media_url = models.TextField(null=True, blank=True)
    status = models.IntegerField(choices=DeliveryStatus.choices, default=DeliveryStatus.SENT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['ticket', '-created_at'], name='supp_msg_ticket_created_idx'),
            models.Index(fields=['ticket', 'status'], name='supp_msg_ticket_status_idx'),
        ]

    def get_json(self, temp_id: str = None) -> dict:
        time_str = timezone.localtime(self.created_at).strftime("%d/%m/%Y %I:%M %p").lower()
        absolute_media_url = (storage_manager.get_url(self.media_url) or "") if self.media_url else ""
        resolved_status = self.status if self.status is not None else 1

        if self.message_type == self.MessageType.SYSTEM:
            sender_role = 'system'
        elif self.ticket_id and self.ticket:
            sender_role = self.ticket.get_participant_role(self.sender_id)
        else:
            sender_role = 'support' if (getattr(self.sender, 'is_superuser', False) or getattr(self.sender, 'is_staff', False)) else 'client'

        sender_full_name = f"{self.sender.first_name} {self.sender.last_name}".strip()
        if sender_role == 'merchant' and self.ticket_id and self.ticket:
            company = self.ticket.get_merchant_company()
            if company and company.name:
                sender_full_name = f"{company.name} ({sender_full_name})" if sender_full_name else company.name

        payload = {
            'id': self.id,
            'ticket_id': self.ticket_id,
            'sender_id': str(self.sender_id),
            'sender_name': sender_full_name,
            'sender_role': sender_role,
            'text': self.text,
            'message_type': self.message_type,
            'media_url': absolute_media_url,
            'status': resolved_status,
            'is_read': bool(resolved_status >= self.DeliveryStatus.READ),
            'is_support': (sender_role == 'support'),
            'created_at': time_str,
            'timestamp': self.created_at.isoformat() if self.created_at else None,
        }
        if temp_id:
            payload['temp_id'] = str(temp_id)
        return payload


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
                    "label": "Motor de Fidelidad",
                    "description":"Sección de datos sobre los resultados y rendimiento del sistema de gamificación y retención de clientes.",
                    "value": self.gamification_analytics
                },
                'digital_performance_analytics': {
                    "label": "Impacto y ROI",
                    "description":"Sección de datos sobre rentabilidad del plan, conversión de ventas y efectividad de productos.",
                    "value": self.digital_performance_analytics
                },
                'clients_behavior_analytics': {
                    "label": "Rendimiento Visual",
                    "description":"Sección de datos sobre el rendimiento de los videos, midiendo las interacciones de los clientes.",
                    "value": self.clients_behavior_analytics
                },
                'comercial_radar': {
                    "label": "Radar Comercial",
                    "description":"Mapa especializado en mostrar la demanda de productos en zonas del territorio nacional, identificando oportunidades de negocio.",
                    "value":True # TODOS LOS PLANES TIENEN ESTE BENEFICIO
                },
                'operative_management_analytics': {
                    "label": "Gestión Operativa",
                    "description":"Sección de datos sobre el rendimiento por sucursal, gastos promedios por cliente y contabilidad.",
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
    
    def get_benefits_json(self) -> dict:
        return {
        'inventory_capacity': {
            "value": self.inventory_capacity
        },
        'products_registration_with_ia': {
            "value": self.products_registration_with_ia
        },
        'profile_histories': {
            "value": self.profile_histories
        },
        'gamification_system': {
            "value": self.gamification_system
        },
        'gamification_analytics': {
            "value": self.gamification_analytics
        },
        'digital_performance_analytics': {
            "value": self.digital_performance_analytics
        },
        'clients_behavior_analytics': {
            "value": self.clients_behavior_analytics
        },
        'operative_management_analytics': {
            "value": self.operative_management_analytics
        },
        'company_branches': {
            "value": self.company_branches
        },
        'company_employees': {
            "value": self.company_employees
        },
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
    # Banderas para notificaciones de renovacion de subscripciones
    notified_5_days = models.BooleanField(default=False)
    notified_1_day = models.BooleanField(default=False)
    notified_hours = models.BooleanField(default=False)

    def get_json(self) -> dict:
        prorated_remanent_usd = 0.0
        now = timezone.now()
        
        # 💡 LÓGICA DE PRORRATEO: Calculamos el valor del tiempo no consumido
        if self.valid_until and self.valid_until > now:
            days_left = (self.valid_until - now).total_seconds() / 86400.0
            daily_rate = float(self.plan.price) / 30.0
            # Redondeamos a 2 decimales para formato de moneda
            prorated_remanent_usd = round(days_left * daily_rate, 2)

        return {
            'id': str(self.id),
            'plan': self.plan.name,
            'valid_until': self.valid_until.strftime("%d/%m/%Y, %H:%M:%S") if self.valid_until else None,
            'adquired_at': self.adquired_at.strftime("%d/%m/%Y, %H:%M:%S"),
            'merchant_type': self.get_merchant_type_display(),
            'rif_number': self.rif_number,
            'benefits': self.plan.get_benefits_json(),
            'business_required': self.plan.requires_business,
            'prorated_remanent_usd': prorated_remanent_usd
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
    target_plan = models.ForeignKey(MerchantPlan, on_delete=models.SET_NULL, null=True, blank=True)

    def clean(self):
        if self.pk:
            original_instance = MerchantPlanPayment.objects.get(pk=self.pk)
            
            # Si el pago está siendo rechazado...
            if (original_instance.status != PaymentStatus.REJECTED and 
                self.status == PaymentStatus.REJECTED):
                
                # 1. Validamos que haya seleccionado un motivo
                if self.rejection_reason is None:
                    raise ValidationError({
                        'rejection_reason': "Debes seleccionar una razón de rechazo."
                    })
                    
                # 💡 2. Aplicamos la misma lógica de auto-asignación aquí
                self.rejection_help = int(self.rejection_reason)

            # Si el pago NO está rechazado, limpiamos
            elif self.status != PaymentStatus.REJECTED:
                self.rejection_reason = None
                self.rejection_help = None

        super().clean()

    # 2. Método para renderizar la imagen en el Admin
    @property
    def payment_proof_preview(self):
        if self.payment_proof_url:
            return mark_safe(f'<img src="{storage_manager.get_url(self.payment_proof_url)}" style="max-height: 400px; max-width: 300px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);" />')
        return "Sin comprobante"
    
    payment_proof_preview.fget.short_description = "Comprobante de Pago"

    def get_json(self) -> dict:
        
        return {
            'id': self.id,
            'subscription': self.subscription_id,
            "plan_name": self.subscription.plan.name,
            'reference_number': self.reference_number,
            'payment_proof_url': storage_manager.get_url(self.payment_proof_url),
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

class AtlasSubscriptionTier(models.IntegerChoices):
    FREEMIUM = 0, 'Freemium'
    PREMIUM = 1, 'Premium'


def format_ve_amount(value, decimals: int = 2, symbol: str = "$", symbol_right: bool = True) -> str:
    """
    Formatea un monto numérico al estándar venezolano: punto para miles y coma para decimales.
    Ejemplo USD: 1.800,00$ | Ejemplo Bs: 76.500,00 Bs.
    """
    try:
        num = float(value or 0.0)
    except (TypeError, ValueError):
        num = 0.0
    formatted = f"{num:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if not symbol:
        return formatted
    return f"{formatted}{symbol}" if symbol_right else f"{symbol}{formatted}"


class AtlasPlusPlan(models.Model):
    """
    Gestión de estado, suscripción y presupuesto diario unificado (Comprador + Negocios)
    para el asistente inteligente Atlas.
    Todos los usuarios tienen este registro. El tier define sus límites diarios.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='atlas_plan')
    tier = models.IntegerField(choices=AtlasSubscriptionTier.choices, default=AtlasSubscriptionTier.FREEMIUM)
    valid_until = models.DateTimeField(null=True, blank=True)
    daily_usage_date = models.DateField(null=True, blank=True)
    daily_usage_count = models.IntegerField(default=0)

    def is_active_premium(self) -> bool:
        return bool(
            self.tier == AtlasSubscriptionTier.PREMIUM
            and self.valid_until
            and self.valid_until > timezone.now()
        )

    def get_contracted_daily_limit(self, default: int = 0) -> int:
        """
        Obtiene el cupo diario contratado por el usuario en su licencia activa (Derechos Adquiridos).
        Si la configuración global de SystemConfig baja en el futuro (ej. de 30 a 15 usos/día),
        el usuario conserva el cupo que pagó hasta que venza su periodo de suscripción (`valid_until`).
        """
        if not self.is_active_premium():
            return 0

        cache_key = f"cartmaker:atlas:contracted_limit:{self.user_id}"
        cached_limit = cache.get(cache_key)
        if cached_limit is not None:
            try:
                val = int(cached_limit)
                if val > 0:
                    return val
            except (TypeError, ValueError):
                pass

        now = timezone.now()
        try:
            active_invoices = list(
                AtlasPlusInvoice.objects.filter(
                    user_id=self.user_id,
                    period_end__gt=now,
                ).order_by('-issued_at', '-correlative_number')[:5]
            )
            if not active_invoices:
                latest_inv = (
                    AtlasPlusInvoice.objects.filter(user_id=self.user_id)
                    .order_by('-issued_at', '-correlative_number')
                    .first()
                )
                if latest_inv:
                    active_invoices = [latest_inv]

            if active_invoices:
                current_window_limits = [
                    inv.contracted_daily_limit
                    for inv in active_invoices
                    if (inv.period_start is None or inv.period_start <= now)
                ]
                resolved_limit = (
                    max(current_window_limits)
                    if current_window_limits
                    else max(inv.contracted_daily_limit for inv in active_invoices)
                )
                if resolved_limit > 0:
                    ttl = max(60, min(86400, int((self.valid_until - now).total_seconds()))) if self.valid_until else 3600
                    cache.set(cache_key, resolved_limit, timeout=ttl)
                    return resolved_limit
        except Exception:
            pass

        return default

    def get_effective_plus_daily_limit(self, config=None) -> int:
        """
        Calcula el límite diario efectivo para un suscriptor de Atlas Plus:
        Garantiza como mínimo el cupo que el usuario contrató al pagar su licencia activa,
        incluso si `SystemConfig.atlas_plus_daily_limit` se reduce posteriormente.
        """
        if config is None:
            try:
                config = SystemConfig.objects.latest('creation')
            except Exception:
                config = None

        config_plus_limit = int(getattr(config, 'atlas_plus_daily_limit', 30) or 30)
        if not self.is_active_premium():
            return config_plus_limit

        contracted = self.get_contracted_daily_limit(default=config_plus_limit)
        return max(contracted, config_plus_limit)

    def get_quota_status(self, config=None) -> dict:
        if config is None:
            try:
                config = SystemConfig.objects.latest('creation')
            except Exception:
                config = None

        config_plus_limit = int(getattr(config, 'atlas_plus_daily_limit', 30) or 30)
        free_limit = int(getattr(config, 'atlas_free_daily_limit', 7) or 7)
        price_usd = float(getattr(config, 'atlas_plus_price_usd', Decimal('3.99')) or 3.99)

        is_premium = self.is_active_premium()
        effective_plus_limit = self.get_effective_plus_daily_limit(config=config) if is_premium else config_plus_limit
        daily_limit = effective_plus_limit if is_premium else free_limit

        now_local = timezone.localtime(timezone.now())
        today_local = now_local.date()

        cache_key = f"cartmaker:atlas:daily_usage:{self.user_id}"
        cached_used = cache.get(cache_key)
        if cached_used is not None:
            try:
                used_today = max(0, int(cached_used))
            except (TypeError, ValueError):
                used_today = 0
        else:
            db_used = self.daily_usage_count if self.daily_usage_date == today_local else 0
            msg_used = AtlasMessage.objects.filter(
                conversation__plan=self,
                origin=1,
                creation__date=today_local,
            ).count()
            used_today = max(int(db_used or 0), int(msg_used or 0))
            tomorrow = (now_local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            timeout = max(1, int((tomorrow - now_local).total_seconds()))
            cache.set(cache_key, used_today, timeout=timeout)

        free_left = max(0, daily_limit - used_today)
        return {
            'tier': self.get_tier_display(),
            'is_premium': is_premium,
            'valid_until': self.valid_until.strftime("%d/%m/%Y, %H:%M:%S") if self.valid_until else None,
            'daily_limit': daily_limit,
            'contracted_daily_limit': effective_plus_limit if is_premium else None,
            'new_subscription_daily_limit': config_plus_limit,
            'used_today': used_today,
            'free_interactions_left': free_left,
            'requires_atlas_plus': (free_left <= 0 and not is_premium),
            'atlas_plus_price_usd': price_usd,
            'atlas_plus_price_formatted': format_ve_amount(price_usd, 2, "$", True),
        }

    def get_json(self) -> dict:
        return self.get_quota_status()


class AtlasPlusPlanPayment(models.Model):
    """
    Registro de pagos para Atlas Plus.

    Attributes:
        plan (ForeignKey): Plan al que abona.
        reference_number (str): Número de referencia bancaria.
        payment_proof_url (str): URL del comprobante.
        amount (Decimal): Monto en Bolívares (Bs.).
        bcv_taxes_to_day (Decimal): Tasa oficial de cambio BCV.
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
            
            # Si el pago está siendo rechazado...
            if (original_instance.status != PaymentStatus.REJECTED and 
                self.status == PaymentStatus.REJECTED):
                
                # 1. Validamos que haya seleccionado un motivo
                if self.rejection_reason is None:
                    raise ValidationError({
                        'rejection_reason': "Debes especificar una razón de rechazo."
                    })
                
                # 💡 2. Forzamos la asignación usando el atributo value o convirtiendo a int
                # Esto asegura que se guarde el ID numérico, no el objeto Choice
                self.rejection_help = int(self.rejection_reason)

            # Si el pago NO está rechazado (ej. Aprobado o Pendiente), limpiamos los campos
            elif self.status != PaymentStatus.REJECTED:
                self.rejection_reason = None
                self.rejection_help = None

        super().clean()

    # 2. Método para renderizar la imagen en el Admin
    @property
    def payment_proof_preview(self):
        if self.payment_proof_url:
            return mark_safe(f'<img src="{storage_manager.get_url(self.payment_proof_url)}" style="max-height: 400px; max-width: 300px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);" />')
        return "Sin comprobante"
    
    payment_proof_preview.fget.short_description = "Comprobante de Pago"

    def get_json(self) -> dict:
        try:
            invoice_obj = getattr(self, 'invoice', None)
        except Exception:
            invoice_obj = None
        if invoice_obj is None and self.status == PaymentStatus.APPROVED:
            try:
                invoice_obj = AtlasPlusInvoice.issue_for_payment(payment=self)
            except Exception:
                invoice_obj = None
        invoice_data = invoice_obj.get_json() if invoice_obj else None
        return {
            'id': self.id,
            'reference_number': self.reference_number,
            'payment_proof_url': storage_manager.get_url(self.payment_proof_url) if self.payment_proof_url else "",
            'amount': float(self.amount),
            'amount_bs_formatted': format_ve_amount(self.amount, 2, " Bs.", True),
            'bcv_taxes_to_day': float(self.bcv_taxes_to_day),
            'status': self.status,
            'verified_at': self.verified_at.strftime("%d/%m/%Y, %H:%M:%S") if self.verified_at else None,
            'rejection_reason': self.get_rejection_reason_display() if self.rejection_reason else "",
            'rejection_help': self.get_rejection_help_display() if self.rejection_help else "",
            'creation': self.creation.strftime("%d/%m/%Y, %H:%M:%S") if self.creation else None,
            'has_invoice': invoice_data is not None,
            'invoice_number': invoice_data.get('invoice_number') if invoice_data else None,
            'control_number': invoice_data.get('control_number') if invoice_data else None,
            'invoice_url': invoice_data.get('invoice_url') if invoice_data else None,
            'invoice': invoice_data,
        }


class BillingIssuerType(models.TextChoices):
    PERSONAL = 'PERSONAL', 'Persona Natural / Servicios Profesionales (Comprobante Digital · RIF V-)'
    COMPANY = 'COMPANY', 'Persona Jurídica / Empresa Registrada (Comprobante Digital · RIF J-)'
    PERSONAL_SENIAT_IMP = 'PERSONAL_SENIAT_IMP', 'Persona Natural — Facturación Homologada Imprenta Digital SENIAT'
    COMPANY_SENIAT_IMP = 'COMPANY_SENIAT_IMP', 'Persona Jurídica — Facturación Homologada Imprenta Digital SENIAT'


class BillingTaxRegime(models.TextChoices):
    EXENTO_NO_SUJETO = 'EXENTO_NO_SUJETO', 'Exento / No Sujeto (0% IVA)'
    CONTRIBUYENTE_ORDINARIO = 'CONTRIBUYENTE_ORDINARIO', 'Contribuyente Ordinario (16% IVA)'
    CONTRIBUYENTE_ESPECIAL = 'CONTRIBUYENTE_ESPECIAL', 'Contribuyente Especial SENIAT'


DEFAULT_COMPROBANTE_LEGAL_NOTE = (
    "Comprobante Digital de Pago y Recibo Administrativo de Suscripción emitido conforme al Código Civil y de Comercio "
    "de la República Bolivariana de Venezuela y la Ley sobre Mensajes de Datos y Firmas Electrónicas. "
    "Actividad de servicios profesionales / tecnológicos No Sujeta o Exenta de IVA (Alícuota 0%). "
    "Este comprobante acredita la recepción del pago y la activación del servicio digital, no constituye factura fiscal "
    "a los efectos de crédito fiscal de IVA (Providencias Administrativas SENIAT SNAT/2011/0071 y SNAT/2024/000102). "
    "Montos expresados en Bolívares (Bs.) como moneda de curso legal y su equivalencia referencial en Dólares (USD) "
    "según tasa oficial del Banco Central de Venezuela (BCV) vigente a la fecha de la operación (Art. 128 Ley del BCV)."
)

DEFAULT_SENIAT_FACTURA_LEGAL_NOTE = (
    "Documento emitido conforme a las Providencias Administrativas SENIAT SNAT/2011/0071 y SNAT/2024/000102. "
    "La condición de este contribuyente requiere la retención del 100% del impuesto causado, salvo que esté exento, "
    "no sujeto o demuestre ante el Agente de Retención del IVA que es un contribuyente exonerado (SENIAT). "
    "Montos expresados en Bolívares (Bs.) como moneda de curso legal y su equivalencia en Dólares (USD) "
    "según tasa oficial del Banco Central de Venezuela (BCV) vigente a la fecha de la operación (Art. 128 Ley del BCV)."
)

_PLACEHOLDER_ADDRESS_LABELS = {
    'mi primera dirección.',
    'mi primera direccion.',
    'mi primera dirección',
    'mi primera direccion',
    'mi dirección',
    'mi direccion',
    'casa',
    'oficina',
    'trabajo',
    'apartamento',
    'dirección principal',
    'direccion principal',
    'ubicación actual',
    'ubicacion actual',
}


class AtlasPlusInvoice(models.Model):
    """
    Comprobante / Factura Fiscal Digital inmutable emitido automáticamente al aprobarse
    un pago de suscripción de Atlas Plus (transferencia/Pago Móvil o billetera).
    Conserva una fotografía exacta de los datos fiscales del emisor (SystemConfig) y del
    adquiriente al momento de la emisión conforme a la normativa venezolana (SENIAT / BCV).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.OneToOneField(
        AtlasPlusPlanPayment,
        on_delete=models.CASCADE,
        related_name='invoice',
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='atlas_invoices',
    )
    correlative_number = models.PositiveIntegerField(unique=True, db_index=True)
    invoice_number = models.CharField(max_length=40, unique=True, db_index=True)
    control_number = models.CharField(max_length=40, unique=True, db_index=True)
    verification_code = models.CharField(max_length=64, unique=True, db_index=True)
    issued_at = models.DateTimeField(default=timezone.now, db_index=True)
    period_start = models.DateTimeField(null=True, blank=True)
    period_end = models.DateTimeField(null=True, blank=True)

    # Snapshot del Emisor (Persona Natural o Empresa según SystemConfig al momento de emitir)
    issuer_type = models.CharField(
        max_length=20,
        choices=BillingIssuerType.choices,
        default=BillingIssuerType.PERSONAL,
    )
    issuer_name = models.CharField(max_length=255)
    issuer_trade_name = models.CharField(max_length=255, default='CartMaker')
    issuer_rif = models.CharField(max_length=30)
    issuer_cedula = models.CharField(max_length=30, blank=True, default='')
    issuer_fiscal_address = models.TextField()
    issuer_seniat_region = models.CharField(max_length=255, blank=True, default='')
    issuer_rif_certificate = models.CharField(max_length=60, blank=True, default='')
    tax_regime = models.CharField(
        max_length=30,
        choices=BillingTaxRegime.choices,
        default=BillingTaxRegime.EXENTO_NO_SUJETO,
    )

    # Snapshot del Cliente / Adquiriente
    buyer_name = models.CharField(max_length=255)
    buyer_document = models.CharField(max_length=60, default='Consumidor Final')
    buyer_email = models.CharField(max_length=255, blank=True, default='')
    buyer_address = models.TextField(blank=True, default='República Bolivariana de Venezuela')
    buyer_is_company = models.BooleanField(default=False)

    # Desglose Financiero Bimonetario (Bs. Curso Legal + Equivalente USD BCV)
    payment_method = models.CharField(max_length=80, default='Pago Móvil / Transferencia Bancaria')
    payment_reference = models.CharField(max_length=100)
    concept_description = models.CharField(max_length=500)
    bcv_rate = models.DecimalField(max_digits=12, decimal_places=4)

    subtotal_usd = models.DecimalField(max_digits=12, decimal_places=2)
    subtotal_bs = models.DecimalField(max_digits=14, decimal_places=2)
    exempt_amount_usd = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    exempt_amount_bs = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    taxable_base_usd = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    taxable_base_bs = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    iva_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    iva_amount_usd = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    iva_amount_bs = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    total_usd = models.DecimalField(max_digits=12, decimal_places=2)
    total_bs = models.DecimalField(max_digits=14, decimal_places=2)

    amount_paid_bs = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    amount_paid_usd = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    wallet_surplus_usd = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    wallet_surplus_bs = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    legal_note = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-issued_at', '-correlative_number']
        indexes = [
            models.Index(fields=['user', '-issued_at'], name='atlas_inv_user_issued_idx'),
        ]

    @property
    def invoice_url(self) -> str:
        domain = getattr(settings, 'DOMAIN', 'https://www.cartmaker.app').rstrip('/')
        return f"{domain}/facturas/atlas/{self.id}/?token={self.verification_code}"

    @property
    def is_seniat_homologated(self) -> bool:
        return self.issuer_type in (
            BillingIssuerType.PERSONAL_SENIAT_IMP,
            BillingIssuerType.COMPANY_SENIAT_IMP,
        )

    @property
    def contracted_daily_limit(self) -> int:
        """
        Extrae el cupo diario contratado y congelado en el momento en que el usuario pagó esta licencia.
        Si es un comprobante previo sin marcador explícito (como A-00000001), lo auto-sanea a 30/día
        en la base de datos para garantizar que futuros cambios en SystemConfig no alteren su licencia.
        """
        raw = self.concept_description or ''
        match = re.search(r'\[Cupo:\s*(\d+)\s*/\s*d[ií]a\]', raw, flags=re.IGNORECASE)
        if match:
            try:
                val = int(match.group(1))
                if val > 0:
                    return val
            except (TypeError, ValueError):
                pass

        default_limit = 30
        if self.pk:
            base_text = re.sub(r'\s*\[Cupo:\s*\d+\s*/\s*d[ií]a\]', '', raw).strip()
            updated_desc = f"{base_text} [Cupo: {default_limit}/día]"[:500]
            self.concept_description = updated_desc
            AtlasPlusInvoice.objects.filter(pk=self.pk).update(concept_description=updated_desc)
        return default_limit

    @property
    def clean_concept_description(self) -> str:
        raw = self.concept_description or ''
        return re.sub(r'\s*\[Cupo:\s*\d+\s*/\s*d[ií]a\]', '', raw, flags=re.IGNORECASE).strip()

    @classmethod
    def _resolve_buyer_address(cls, user: User, company: Optional['Company'] = None) -> str:
        """
        Determina el domicilio fiscal o ubicación del adquiriente:
        1. Si es Persona Jurídica (Company), prioriza la dirección de su sede comercial (CompanyStore).
        2. Si no tiene tienda con dirección descriptiva, busca en ClientLocation ignorando etiquetas
           genéricas de marcador de posición (ej. 'Mi primera dirección.', 'Casa', 'Oficina').
        """
        if company is None:
            company = Company.objects.filter(owner=user).first()

        if company:
            stores = CompanyStore.objects.filter(company=company).select_related('location')
            for store in stores:
                loc = getattr(store, 'location', None)
                if not loc:
                    continue
                for candidate in (getattr(loc, 'description', None), getattr(loc, 'name', None)):
                    if candidate:
                        cleaned = candidate.strip()
                        if cleaned and cleaned.lower() not in _PLACEHOLDER_ADDRESS_LABELS:
                            return cleaned

        client_locs = ClientLocation.objects.filter(user=user)
        for loc in client_locs:
            desc = (getattr(loc, 'description', None) or '').strip()
            if desc and desc.lower() not in _PLACEHOLDER_ADDRESS_LABELS:
                return desc
            name = (getattr(loc, 'name', None) or '').strip()
            if name and name.lower() not in _PLACEHOLDER_ADDRESS_LABELS and len(name) > 12:
                return name

        return "República Bolivariana de Venezuela"

    @classmethod
    def issue_for_payment(
        cls,
        payment: 'AtlasPlusPlanPayment',
        config: Optional['SystemConfig'] = None,
        payment_method: Optional[str] = None,
        surplus_usd: Decimal = Decimal('0.00'),
        period_start=None,
        period_end=None,
    ) -> 'AtlasPlusInvoice':
        existing = cls.objects.filter(payment=payment).first()
        if existing:
            return existing

        with transaction.atomic():
            existing = cls.objects.select_for_update().filter(payment=payment).first()
            if existing:
                return existing

            if config is None:
                config = SystemConfig.objects.select_for_update().order_by('-creation').first()
            else:
                config = SystemConfig.objects.select_for_update().filter(pk=config.pk).first() or config

            if config is None:
                config = SystemConfig.objects.create()

            if config.atlas_plus_daily_limit == 20:
                config.atlas_plus_daily_limit = 30
                config.save(update_fields=['atlas_plus_daily_limit'])

            correlative = max(1, int(config.billing_next_correlative or 1))
            max_existing = cls.objects.aggregate(models.Max('correlative_number')).get('correlative_number__max') or 0
            if correlative <= max_existing:
                correlative = max_existing + 1

            config.billing_next_correlative = correlative + 1
            config.save(update_fields=['billing_next_correlative'])

            series = (config.billing_series_prefix or 'A').strip().upper()
            ctrl_prefix = (config.billing_control_prefix or '00').strip()
            invoice_number = f"{series}-{correlative:08d}" if series else f"{correlative:08d}"
            control_number = f"{ctrl_prefix}-{correlative:08d}" if ctrl_prefix else f"00-{correlative:08d}"
            verification_code = f"CMK-{timezone.localtime(timezone.now()).strftime('%Y%m%d')}-{secrets.token_hex(4).upper()}"

            user = payment.plan.user
            company = Company.objects.filter(owner=user).first()
            buyer_is_company = False
            company_rif = (getattr(company, 'rif_number', None) or '').strip() if company else ''
            company_legal_name = (
                (getattr(company, 'razon_social', None) or getattr(company, 'name', None) or '').strip()
                if company else ''
            )
            if company and company_rif and company_legal_name:
                buyer_name = company_legal_name.upper()
                if company_rif[0].upper() in ('J', 'G', 'V', 'E', 'C', 'P'):
                    buyer_document = company_rif.upper()
                else:
                    buyer_document = f"J-{company_rif.upper()}"
                buyer_is_company = True
            else:
                full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
                buyer_name = (full_name or user.email.split('@')[0]).upper()
                if user.cedula_number:
                    nat_prefix = 'E' if getattr(user, 'nacionality', 0) == UserNacionality.EXTRANJERO else 'V'
                    clean_ced = str(user.cedula_number).strip().upper()
                    if clean_ced and clean_ced[0] in ('V', 'E', 'J', 'G', 'P'):
                        buyer_document = clean_ced
                    else:
                        buyer_document = f"{nat_prefix}-{clean_ced}"
                else:
                    buyer_document = "V-00000000 (Consumidor Final)"

            buyer_address = cls._resolve_buyer_address(user=user, company=company)

            bcv_rate = Decimal(str(payment.bcv_taxes_to_day or '1.0000'))
            if bcv_rate <= Decimal('0'):
                bcv_rate = Decimal('1.0000')

            total_usd = Decimal(str(config.atlas_plus_price_usd or '3.99')).quantize(Decimal('0.01'))
            total_bs = (total_usd * bcv_rate).quantize(Decimal('0.01'))

            iva_pct = Decimal(str(config.billing_iva_percentage or '0.00')).quantize(Decimal('0.01'))
            if config.billing_tax_regime == BillingTaxRegime.EXENTO_NO_SUJETO or iva_pct <= Decimal('0'):
                iva_pct = Decimal('0.00')
                subtotal_usd = total_usd
                subtotal_bs = total_bs
                exempt_usd = total_usd
                exempt_bs = total_bs
                taxable_usd = Decimal('0.00')
                taxable_bs = Decimal('0.00')
                iva_usd = Decimal('0.00')
                iva_bs = Decimal('0.00')
            else:
                divisor = Decimal('1.00') + (iva_pct / Decimal('100.00'))
                taxable_usd = (total_usd / divisor).quantize(Decimal('0.01'))
                taxable_bs = (total_bs / divisor).quantize(Decimal('0.01'))
                iva_usd = (total_usd - taxable_usd).quantize(Decimal('0.01'))
                iva_bs = (total_bs - taxable_bs).quantize(Decimal('0.01'))
                subtotal_usd = taxable_usd
                subtotal_bs = taxable_bs
                exempt_usd = Decimal('0.00')
                exempt_bs = Decimal('0.00')

            raw_paid_bs = Decimal(str(payment.amount or '0.00')).quantize(Decimal('0.01'))
            if raw_paid_bs > Decimal('0.00'):
                amount_paid_bs = raw_paid_bs
                amount_paid_usd = (raw_paid_bs / bcv_rate).quantize(Decimal('0.01'))
                resolved_method = payment_method or 'Pago Móvil / Transferencia Bancaria'
            else:
                amount_paid_usd = total_usd
                amount_paid_bs = total_bs
                resolved_method = payment_method or 'Saldo en Billetera Digital CartMaker (UserWallet)'

            surplus_usd_clean = max(Decimal('0.00'), Decimal(str(surplus_usd or '0.00')).quantize(Decimal('0.01')))
            surplus_bs_clean = (surplus_usd_clean * bcv_rate).quantize(Decimal('0.01'))

            now = timezone.now()
            p_start = period_start or now
            p_end = period_end or (payment.plan.valid_until if payment.plan and payment.plan.valid_until else now + timedelta(days=30))

            config_limit = max(1, int(config.atlas_plus_daily_limit or 30))
            pending_limit = 0
            try:
                cached_pending = cache.get(f"cartmaker:atlas:pending_payment_limit:{payment.id}")
                if cached_pending is not None:
                    pending_limit = int(cached_pending)
            except Exception:
                pending_limit = 0
            contracted_limit = max(config_limit, pending_limit)
            base_concept = re.sub(
                r'\s*\[Cupo:\s*\d+\s*/\s*d[ií]a\]',
                '',
                (config.billing_service_concept or ''),
                flags=re.IGNORECASE,
            ).strip()
            concept_with_quota = f"{base_concept} [Cupo: {contracted_limit}/día]"[:500]

            is_homologated = config.billing_issuer_type in (
                BillingIssuerType.PERSONAL_SENIAT_IMP,
                BillingIssuerType.COMPANY_SENIAT_IMP,
            )
            raw_legal_note = (config.billing_legal_note or '').strip()
            if not is_homologated and (not raw_legal_note or 'Agente de Retención del IVA' in raw_legal_note):
                effective_legal_note = DEFAULT_COMPROBANTE_LEGAL_NOTE
            elif is_homologated and not raw_legal_note:
                effective_legal_note = DEFAULT_SENIAT_FACTURA_LEGAL_NOTE
            else:
                effective_legal_note = raw_legal_note

            created_invoice = cls.objects.create(
                payment=payment,
                user=user,
                correlative_number=correlative,
                invoice_number=invoice_number,
                control_number=control_number,
                verification_code=verification_code,
                issued_at=now,
                period_start=p_start,
                period_end=p_end,
                issuer_type=config.billing_issuer_type,
                issuer_name=config.billing_issuer_name,
                issuer_trade_name=config.billing_trade_name,
                issuer_rif=config.billing_issuer_rif,
                issuer_cedula=config.billing_issuer_cedula,
                issuer_fiscal_address=config.billing_fiscal_address,
                issuer_seniat_region=config.billing_seniat_region,
                issuer_rif_certificate=config.billing_rif_certificate_number,
                tax_regime=config.billing_tax_regime,
                buyer_name=buyer_name,
                buyer_document=buyer_document,
                buyer_email=user.email,
                buyer_address=buyer_address,
                buyer_is_company=buyer_is_company,
                payment_method=resolved_method,
                payment_reference=payment.reference_number,
                concept_description=concept_with_quota,
                bcv_rate=bcv_rate,
                subtotal_usd=subtotal_usd,
                subtotal_bs=subtotal_bs,
                exempt_amount_usd=exempt_usd,
                exempt_amount_bs=exempt_bs,
                taxable_base_usd=taxable_usd,
                taxable_base_bs=taxable_bs,
                iva_percentage=iva_pct,
                iva_amount_usd=iva_usd,
                iva_amount_bs=iva_bs,
                total_usd=total_usd,
                total_bs=total_bs,
                amount_paid_bs=amount_paid_bs,
                amount_paid_usd=amount_paid_usd,
                wallet_surplus_usd=surplus_usd_clean,
                wallet_surplus_bs=surplus_bs_clean,
                legal_note=effective_legal_note,
            )

            try:
                cache.delete(f"cartmaker:atlas:contracted_limit:{user.id}")
            except Exception:
                pass

            return created_invoice

    def get_json(self) -> dict:
        issued_local = timezone.localtime(self.issued_at) if self.issued_at else timezone.localtime(timezone.now())
        sys_cfg = SystemConfig.objects.only('id', 'atlas_plus_daily_limit').order_by('-creation').first()
        if sys_cfg and sys_cfg.atlas_plus_daily_limit == 20:
            sys_cfg.atlas_plus_daily_limit = 30
            sys_cfg.save(update_fields=['atlas_plus_daily_limit'])
        daily_limit = self.contracted_daily_limit
        clean_desc = self.clean_concept_description

        is_homologated = self.is_seniat_homologated
        if is_homologated:
            document_title = "FACTURA DIGITAL"
            document_number_label = "Factura N°"
            control_number_label = "N° de Control"
            grand_total_label = "TOTAL FACTURADO"
        else:
            document_title = "COMPROBANTE DIGITAL DE PAGO"
            document_number_label = "Comprobante N°"
            control_number_label = "Control Interno N°"
            grand_total_label = "TOTAL PAGADO"

        if self.issuer_type in (BillingIssuerType.COMPANY, BillingIssuerType.COMPANY_SENIAT_IMP):
            issuer_short_label = "Persona Jurídica · Servicios Tecnológicos (RIF J-)"
        else:
            issuer_short_label = "Persona Natural · Servicios Profesionales (RIF V-)"

        tax_regime_short = (
            "Exento / No Sujeto (0% IVA)"
            if self.tax_regime == BillingTaxRegime.EXENTO_NO_SUJETO or float(self.iva_percentage) <= 0.0
            else self.get_tax_regime_display()
        )

        # Auto-saneamiento de dirección si el registro previo guardó un marcador genérico ('Mi primera dirección.')
        resolved_buyer_address = (self.buyer_address or '').strip()
        if not resolved_buyer_address or resolved_buyer_address.lower() in _PLACEHOLDER_ADDRESS_LABELS:
            resolved_buyer_address = self._resolve_buyer_address(user=self.user)
            if resolved_buyer_address != self.buyer_address:
                self.buyer_address = resolved_buyer_address
                AtlasPlusInvoice.objects.filter(pk=self.pk).update(buyer_address=resolved_buyer_address)

        # Auto-saneamiento de nota legal según modo (Comprobante Digital vs Factura Homologada SENIAT)
        effective_legal_note = (self.legal_note or '').strip()
        if not is_homologated and (not effective_legal_note or 'Agente de Retención del IVA' in effective_legal_note):
            effective_legal_note = DEFAULT_COMPROBANTE_LEGAL_NOTE
        elif is_homologated and not effective_legal_note:
            effective_legal_note = DEFAULT_SENIAT_FACTURA_LEGAL_NOTE

        return {
            'id': str(self.id),
            'payment_id': self.payment_id,
            'correlative_number': self.correlative_number,
            'invoice_number': self.invoice_number,
            'control_number': self.control_number,
            'verification_code': self.verification_code,
            'is_seniat_homologated': is_homologated,
            'document_title': document_title,
            'document_number_label': document_number_label,
            'control_number_label': control_number_label,
            'grand_total_label': grand_total_label,
            'atlas_plus_daily_limit': daily_limit,
            'issued_at': issued_local.strftime("%d/%m/%Y %H:%M:%S"),
            'issued_date': issued_local.strftime("%d/%m/%Y"),
            'issued_time': issued_local.strftime("%I:%M:%S %p"),
            'period_start': timezone.localtime(self.period_start).strftime("%d/%m/%Y") if self.period_start else None,
            'period_end': timezone.localtime(self.period_end).strftime("%d/%m/%Y") if self.period_end else None,
            'issuer': {
                'issuer_type': self.issuer_type,
                'issuer_type_label': issuer_short_label,
                'name': self.issuer_name,
                'trade_name': self.issuer_trade_name,
                'rif': self.issuer_rif,
                'cedula': self.issuer_cedula,
                'fiscal_address': self.issuer_fiscal_address,
                'seniat_region': self.issuer_seniat_region,
                'rif_certificate_number': self.issuer_rif_certificate,
                'tax_regime': self.tax_regime,
                'tax_regime_label': tax_regime_short,
            },
            'buyer': {
                'name': self.buyer_name,
                'document': self.buyer_document,
                'email': self.buyer_email,
                'address': resolved_buyer_address,
                'is_company': self.buyer_is_company,
            },
            'payment_details': {
                'payment_method': self.payment_method,
                'reference_number': self.payment_reference,
                'bcv_rate': float(self.bcv_rate),
                'bcv_rate_formatted': format_ve_amount(self.bcv_rate, 4, " Bs./$", True),
            },
            'items': [
                {
                    'quantity': 1,
                    'unit': 'Mes (30 días)',
                    'description': clean_desc,
                    'unit_price_usd': float(self.subtotal_usd),
                    'unit_price_usd_formatted': format_ve_amount(self.subtotal_usd, 2, "$", True),
                    'unit_price_bs': float(self.subtotal_bs),
                    'unit_price_bs_formatted': format_ve_amount(self.subtotal_bs, 2, " Bs.", True),
                    'is_exempt': float(self.iva_percentage) <= 0.0,
                }
            ],
            'amounts': {
                'subtotal_usd': float(self.subtotal_usd),
                'subtotal_usd_formatted': format_ve_amount(self.subtotal_usd, 2, "$", True),
                'subtotal_bs': float(self.subtotal_bs),
                'subtotal_bs_formatted': format_ve_amount(self.subtotal_bs, 2, " Bs.", True),
                'exempt_amount_usd': float(self.exempt_amount_usd),
                'exempt_amount_usd_formatted': format_ve_amount(self.exempt_amount_usd, 2, "$", True),
                'exempt_amount_bs': float(self.exempt_amount_bs),
                'exempt_amount_bs_formatted': format_ve_amount(self.exempt_amount_bs, 2, " Bs.", True),
                'taxable_base_usd': float(self.taxable_base_usd),
                'taxable_base_usd_formatted': format_ve_amount(self.taxable_base_usd, 2, "$", True),
                'taxable_base_bs': float(self.taxable_base_bs),
                'taxable_base_bs_formatted': format_ve_amount(self.taxable_base_bs, 2, " Bs.", True),
                'iva_percentage': float(self.iva_percentage),
                'iva_amount_usd': float(self.iva_amount_usd),
                'iva_amount_usd_formatted': format_ve_amount(self.iva_amount_usd, 2, "$", True),
                'iva_amount_bs': float(self.iva_amount_bs),
                'iva_amount_bs_formatted': format_ve_amount(self.iva_amount_bs, 2, " Bs.", True),
                'total_usd': float(self.total_usd),
                'total_usd_formatted': format_ve_amount(self.total_usd, 2, "$", True),
                'total_bs': float(self.total_bs),
                'total_bs_formatted': format_ve_amount(self.total_bs, 2, " Bs.", True),
                'amount_paid_bs': float(self.amount_paid_bs),
                'amount_paid_bs_formatted': format_ve_amount(self.amount_paid_bs, 2, " Bs.", True),
                'amount_paid_usd': float(self.amount_paid_usd),
                'amount_paid_usd_formatted': format_ve_amount(self.amount_paid_usd, 2, "$", True),
                'wallet_surplus_usd': float(self.wallet_surplus_usd),
                'wallet_surplus_usd_formatted': format_ve_amount(self.wallet_surplus_usd, 2, "$", True),
                'wallet_surplus_bs': float(self.wallet_surplus_bs),
                'wallet_surplus_bs_formatted': format_ve_amount(self.wallet_surplus_bs, 2, " Bs.", True),
            },
            'legal_note': effective_legal_note,
            'invoice_url': self.invoice_url,
        }


class AtlasThread(models.Model):
    """
    Contexto de conversación persistente con la IA.

    Attributes:
        plan (ForeignKey): Suscripción asociada. Null si el hilo es de un invitado.
        guest_key (str): Token de invitado. Null en hilos de usuarios con cuenta.
        summary (str): Resumen generado por la IA sobre la conversación.
    """
    plan = models.ForeignKey(AtlasPlusPlan, on_delete=models.CASCADE, related_name='threads', null=True, blank=True)
    guest_key = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    summary = models.TextField(null=True, blank=True)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=['guest_key'],
                condition=Q(guest_key__isnull=False),
                name='unique_atlas_thread_guest_key',
            )
        ]

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
    product_ids = models.JSONField(default=list, blank=True)
    action_command = models.JSONField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['conversation', '-creation'], name='atlas_msg_conv_created_idx'),
        ]


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
    document_number = models.CharField(default='30222103')
    document_type = models.IntegerField(choices=BankDocumentType.choices, default=BankDocumentType.CEDULA)
    account_number = models.CharField()
    active = models.BooleanField(default=True)
    beneficiary_name = models.CharField(default='ATREYUS DE JESUS REYES ALVAREZ')

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
    Parámetros globales del ecosistema CartMaker y configuración dinámica de
    facturación fiscal (SENIAT Persona Natural V- o Persona Jurídica J-).
    """
    platinum_min_rating_promedy_requirement = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('4.5'))
    platinum_min_sells_per_month_requirement = models.IntegerField(default=100)
    creation = models.DateTimeField(auto_now_add=True)
    atlas_plus_price_usd = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('3.99'))
    atlas_plus_daily_limit = models.IntegerField(default=30)
    atlas_free_daily_limit = models.IntegerField(default=7)
    atlas_anonymous_daily_limit = models.IntegerField(default=3)

    # --- CONFIGURACIÓN DINÁMICA DE FACTURACIÓN FISCAL (SENIAT VENEZUELA) ---
    billing_issuer_type = models.CharField(
        max_length=20,
        choices=BillingIssuerType.choices,
        default=BillingIssuerType.PERSONAL,
        help_text="Define si las facturas de Atlas Plus se emiten a tu nombre personal (RIF V-) o a nombre de tu empresa registrada (RIF J-).",
    )
    billing_issuer_name = models.CharField(
        max_length=255,
        default='ATREYUS DE JESUS REYES ALVAREZ',
        help_text="Nombre completo (Persona Natural) o Razón Social (Empresa) tal como aparece en el RIF del SENIAT.",
    )
    billing_trade_name = models.CharField(
        max_length=255,
        default='CartMaker',
        help_text="Nombre comercial o marca mostrada en el encabezado de la factura.",
    )
    billing_issuer_rif = models.CharField(
        max_length=30,
        default='V-30222103-7',
        help_text="RIF fiscal activo ante el SENIAT (ej. V-30222103-7 o J-XXXXXXXX-X cuando registres la empresa).",
    )
    billing_issuer_cedula = models.CharField(
        max_length=30,
        default='V-30.222.103',
        blank=True,
        help_text="Cédula de Identidad del emisor o representante legal (ej. V-30.222.103).",
    )
    billing_fiscal_address = models.TextField(
        default='CTRA NACIONAL GUATIRE-GUARENAS CASA TOWN HOUSE NRO C-11 CONJUNTO RESIDENCIAL EL REFUGIO GUATIRE MIRANDA ZONA POSTAL 1221',
        help_text="Domicilio Fiscal exacto registrado en el comprobante RIF del SENIAT.",
    )
    billing_seniat_region = models.CharField(
        max_length=255,
        default='GERENCIA REGIONAL DE TRIBUTOS INTERNOS REGIÓN CAPITAL / SECTOR GUARENAS / GUATIRE',
        blank=True,
        help_text="Gerencia Regional de Tributos Internos del SENIAT.",
    )
    billing_rif_certificate_number = models.CharField(
        max_length=60,
        default='202401P0000063963955',
        blank=True,
        help_text="N° de Comprobante del Registro Único de Información Fiscal (SENIAT).",
    )
    billing_tax_regime = models.CharField(
        max_length=30,
        choices=BillingTaxRegime.choices,
        default=BillingTaxRegime.EXENTO_NO_SUJETO,
        help_text="Condición frente al IVA. Usa 'Exento / No Sujeto' como Persona Natural inicial, o 'Contribuyente Ordinario (16%)' al facturar con IVA.",
    )
    billing_iva_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Porcentaje de IVA aplicable (0.00 para Persona Natural Exento/No Sujeto; 16.00 para Contribuyente Ordinario).",
    )
    billing_series_prefix = models.CharField(
        max_length=20,
        default='A',
        blank=True,
        help_text="Prefijo de serie para la numeración de facturas digitales (ej. A -> A-00000001).",
    )
    billing_control_prefix = models.CharField(
        max_length=20,
        default='00',
        blank=True,
        help_text="Prefijo de Número de Control (ej. 00 -> 00-00000001).",
    )
    billing_next_correlative = models.PositiveIntegerField(
        default=1,
        help_text="Siguiente número correlativo de factura a emitir (se incrementa automáticamente con cada pago aprobado).",
    )
    billing_service_concept = models.CharField(
        max_length=500,
        default='Servicios de Programación, Procesamiento de Datos y Suscripción Mensual al Asistente de Inteligencia Artificial Atlas Plus (CartMaker)',
        help_text="Descripción del servicio tecnológico que aparece en el renglón principal de la factura.",
    )
    billing_legal_note = models.TextField(
        default=DEFAULT_COMPROBANTE_LEGAL_NOTE,
        blank=True,
    )

    def get_billing_issuer_json(self) -> dict:
        is_homologated = self.billing_issuer_type in (
            BillingIssuerType.PERSONAL_SENIAT_IMP,
            BillingIssuerType.COMPANY_SENIAT_IMP,
        )
        return {
            'issuer_type': self.billing_issuer_type,
            'issuer_type_label': self.get_billing_issuer_type_display(),
            'is_seniat_homologated': is_homologated,
            'document_title': 'FACTURA DIGITAL' if is_homologated else 'COMPROBANTE DIGITAL DE PAGO',
            'issuer_name': self.billing_issuer_name,
            'trade_name': self.billing_trade_name,
            'rif': self.billing_issuer_rif,
            'cedula': self.billing_issuer_cedula,
            'fiscal_address': self.billing_fiscal_address,
            'seniat_region': self.billing_seniat_region,
            'rif_certificate_number': self.billing_rif_certificate_number,
            'tax_regime': self.billing_tax_regime,
            'tax_regime_label': self.get_billing_tax_regime_display(),
            'iva_percentage': float(self.billing_iva_percentage),
            'series_prefix': self.billing_series_prefix,
            'control_prefix': self.billing_control_prefix,
            'service_concept': self.billing_service_concept,
        }


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
                                 Si la imagen esta en el servidor, solo especificar la ruta en la carpeta static, ej: img/banner_1_test.png")
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
    origin_source = models.CharField(
        max_length=20, 
        choices=[('organic', 'Orgánico'), ('atlas', 'Atlas IA')], 
        default='organic'
    )
    search_prompt = models.TextField(null=True, blank=True)
    ai_keywords = models.CharField(max_length=255, null=True, blank=True)
    atlas_message_id = models.IntegerField(null=True, blank=True)
    bought = models.BooleanField(default=False)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['client', 'inventory_item'], name='pvlog_client_item_idx'),
            models.Index(fields=['inventory_item', 'start_time'], name='pvlog_item_start_idx'),
            models.Index(fields=['client', 'start_time'], name='pvlog_client_start_idx'),
        ]

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
    store = models.ForeignKey(CompanyStore, on_delete=models.CASCADE, related_name='profile_views', null=True)
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

class UnmetDemandLog(models.Model):
    """
    Registro de búsquedas fallidas para detectar oportunidades de mercado por zona.
    """
    client = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    search_term = models.CharField(max_length=255, db_index=True)
    coordinates = gis_models.PointField()
    creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['coordinates'], name='unmet_demand_gis_idx', opclasses=['gist_geometry_ops_2d']),
        ]

# ==========================================
# MÓDULO 10: RED SOCIAL & POLIMORFISMO
# ==========================================

class UniversalLike(models.Model):
    """
    💡 SOLUCIÓN: Sistema unificado polimórfico de likes (Me Gusta).
    Soporta dar likes a Productos (InventoryItem) o Videos (CompanyVideoStory).
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='universal_likes')
    
    # Tubería genérica de Django
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=50) # Admite UUIDs (Videos) y enteros (Productos)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Evita que un usuario le de más de un like a la misma entidad exacta
        unique_together = ('user', 'content_type', 'object_id')
        indexes = [
            models.Index(fields=['content_type', 'object_id'], name='ulike_ct_obj_idx'),
            models.Index(fields=['user', 'content_type', 'creation'], name='ulike_user_ct_created_idx'),
        ]


class UniversalComment(models.Model):
    """
    💡 SOLUCIÓN: Sistema unificado polimórfico para Dudas / Mensajes de preventa.
    Permite interactuar tanto en fichas de productos como en videos corporativos.
    """
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='universal_comments')
    
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=50)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    question_text = models.TextField()
    question_creation = models.DateTimeField(auto_now_add=True)
    answer_text = models.TextField(null=True, blank=True)
    answer_creation = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['content_type', 'object_id'], name='ucomment_ct_obj_idx'),
            models.Index(fields=['client', 'question_creation'], name='ucomment_client_created_idx'),
        ]

    def get_json(self, target_obj=None):
        # Resolvemos dinámicamente la compañía dueña del recurso sin N+1 si target_obj fue pre-cargado
        resolved_target = target_obj if target_obj is not None else getattr(self, '_prefetched_target_obj', None)
        if resolved_target is None:
            resolved_target = self.content_object

        ct_model = self.content_type.model
        company = None
        if ct_model == 'inventoryitem' and resolved_target:
            company = resolved_target.store.company
        elif ct_model == 'companyvideostory' and resolved_target:
            company = resolved_target.company

        company_image_url = ""
        company_name = "Comercio"
        if company:
            company_name = company.name
            if company.image:
                company_image_url = storage_manager.get_url(company.image)

        # 💡 NUEVO: Resolvemos el nombre del ítem para que el comercio sepa a qué le están preguntando
        item_name = "Artículo no disponible"
        if ct_model == 'inventoryitem' and resolved_target:
            item_name = resolved_target.product.name
        elif ct_model == 'companyvideostory' and resolved_target:
            item_name = "Video Promocional"

        return {
            "id": self.id,
            "client_data": {
                "id": self.client_id,
                "name": f"{self.client.first_name} {self.client.last_name}",
                "profile_picture": self.client.get_profile_picture_url()
            },
            "seller_data": {
                "name": company_name,
                "profile_picture": company_image_url
            },
            "target_info": {
                "name": item_name,
                "type": ct_model,
                "target_id": self.object_id
            },
            "question_text": self.question_text,
            "question_creation": timezone.localtime(self.question_creation).strftime('%d/%m/%Y, %H:%M:%S'),
            "answer_text": self.answer_text,
            "answer_creation": timezone.localtime(self.answer_creation).strftime('%d/%m/%Y, %H:%M:%S') if self.answer_creation else None
        }


class CompanyVideoStory(models.Model):
    """
    Modelo unificado para la gestión de contenido en formato de video corto.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='video_stories')
    title = models.CharField(max_length=150, blank=True, default='')
    video_file = models.CharField(max_length=500, null=True, blank=True)
    duration_seconds = models.FloatField(default=0.0)
    thumbnail = models.CharField(max_length=500, null=True, blank=True)
    description = models.TextField(blank=True, null=True)
    associated_item = models.ForeignKey(
        InventoryItem, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='linked_stories'
    )
    creation = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(db_index=True)
    views_count = models.PositiveIntegerField(default=0)
    applied_filter_matrix = models.JSONField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    # 💡 ENLACES GENÉRICOS (Borra automáticamente en cascada likes y comentarios de este video al ser eliminado)
    likes = GenericRelation(UniversalLike, related_query_name='company_video_stories')
    comments = GenericRelation(UniversalComment, related_query_name='company_video_stories')

    class Meta:
        verbose_name = _("Video Historia de Compañía")
        verbose_name_plural = _("Video Historias de Compañía")
        ordering = ['-creation']

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(days=3)
        super().save(*args, **kwargs)

    @property
    def is_media_expired(self) -> bool:
        return timezone.now() > self.expires_at

    @property
    def is_media_available(self) -> bool:
        return bool(self.video_file) and not self.is_media_expired

    def clear_media_files(self):
        if self.video_file:
            storage_manager.delete_file(self.video_file)
            self.video_file = None
        if self.thumbnail:
            storage_manager.delete_file(self.thumbnail)
            self.thumbnail = None
        self.save(update_fields=['video_file', 'thumbnail'])

    def reactivate_story(self, new_video_path: str, new_thumbnail_path: str):
        self.video_file = new_video_path
        self.thumbnail = new_thumbnail_path
        self.expires_at = timezone.now() + timezone.timedelta(days=3)
        self.save(update_fields=['video_file', 'thumbnail', 'expires_at'])

    def get_json(self) -> dict:
        associated_json = self.associated_item.get_json() if self.associated_item else None
        return {
            'id': str(self.id),
            'company_id': str(self.company_id),
            'company_name': self.company.name,
            'company_image': storage_manager.get_url(self.company.image) if self.company.image else None,
            'video_url': storage_manager.get_url(self.video_file) if self.video_file else None,
            'thumbnail_url': storage_manager.get_url(self.thumbnail) if self.thumbnail else None,
            'title': self.title or self.description or '',
            'description': self.description,
            'duration': self.duration_seconds,
            'duration_seconds': self.duration_seconds,
            'metadata': self.metadata or {},
            'applied_filter_matrix': self.applied_filter_matrix,
            'associated_item': associated_json,
            'associated_item_id': str(self.associated_item_id) if self.associated_item_id else None,
            'tagged_products': [associated_json] if associated_json else [],
            'creation': self.creation.isoformat(),
            'updated_at': self.updated_at.isoformat() if self.updated_at else self.creation.isoformat(),
            'expires_at': self.expires_at.isoformat(),
            'is_media_available': self.is_media_available,
            'views_count': self.views_count,
        }

class VideoEngagementLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='video_engagement_records')
    video = models.ForeignKey(CompanyVideoStory, on_delete=models.CASCADE, related_name='engagement_logs')
    watch_time_seconds = models.FloatField(default=0.0)
    video_completed = models.BooleanField(default=False)
    interacted_with_product = models.BooleanField(default=False)
    added_to_cart_from_video = models.BooleanField(default=False)
    bought_from_video = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("Log de Engagement de Video")
        verbose_name_plural = _("Logs de Engagement de Video")
        indexes = [
            models.Index(fields=['client', 'video'], name='veng_client_video_idx'),
            models.Index(fields=['client', 'timestamp'], name='veng_client_ts_idx'),
        ]


# =========================================================================
# 🔐 MÓDULO DE SEGURIDAD PERIMETRAL: API KEYS ENCRIPTADAS (APP & CHAT)
# =========================================================================
import hashlib
import secrets
from django.core.cache import cache


class CartMakerApiKey(models.Model):
    """
    Credencial criptográfica para autorizar peticiones HTTP provenientes de la
    Aplicación Móvil (Flutter) y del Servidor de Chat hacia el backend de CartMaker.

    La llave en texto plano (formato `cmk_live_<prefijo>_<secreto>`) se genera una única
    vez al crearse en el panel administrativo y jamás se almacena en la base de datos;
    únicamente se guarda su prefijo identificador y su hash derivado con PBKDF2-HMAC-SHA256.
    """

    class Scope(models.TextChoices):
        ALL = 'all', _('API Principal + Servidor de Chat (Acceso Completo)')
        API_ONLY = 'api', _('Solo Servidor de la Aplicación (/api/)')
        CHAT_ONLY = 'chat', _('Solo Servidor de Chat (/chat/)')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=120,
        verbose_name=_("Nombre / Dispositivo o Servicio"),
        help_text=_("Ej: App Móvil Flutter (Producción), Servidor de Chat Node.js, etc.")
    )
    scope = models.CharField(
        max_length=16,
        choices=Scope.choices,
        default=Scope.ALL,
        db_index=True,
        verbose_name=_("Alcance de Autorización"),
        help_text=_("Define si esta API Key autoriza peticiones hacia /api/, hacia /chat/ o ambos.")
    )
    prefix = models.CharField(
        max_length=32,
        unique=True,
        editable=False,
        db_index=True,
        verbose_name=_("Prefijo Identificador")
    )
    hashed_key = models.CharField(
        max_length=256,
        editable=False,
        verbose_name=_("Hash Criptográfico (PBKDF2-HMAC-SHA256)")
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name=_("Key Activa"),
        help_text=_("Si se desmarca, cualquier petición con esta API Key será rechazada de inmediato.")
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Fecha de Expiración (Opcional)"),
        help_text=_("Déjalo en blanco para que la API Key no caduque automáticamente.")
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name='created_api_keys',
        verbose_name=_("Creada por")
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Fecha de Creación"))
    last_used_at = models.DateTimeField(null=True, blank=True, editable=False, verbose_name=_("Último Uso"))

    class Meta:
        verbose_name = _("CartMaker API Key")
        verbose_name_plural = _("CartMaker API Keys")
        ordering = ['-created_at']

    def __str__(self):
        status_str = "Activa" if self.is_active else "Revocada"
        return f"{self.name} ({self.prefix}••••) [{status_str}]"

    @classmethod
    def hash_raw_key(cls, raw_key: str) -> str:
        """
        Deriva un hash irreversible de 256 bits usando PBKDF2-HMAC-SHA256 (60,000 iteraciones)
        combinado con el SECRET_KEY del servidor como sal criptográfica.
        """
        salt = (getattr(settings, 'SECRET_KEY', '') or 'cartmaker-default-salt').encode('utf-8')
        derived = hashlib.pbkdf2_hmac(
            'sha256',
            raw_key.encode('utf-8'),
            salt,
            60000
        )
        return derived.hex()

    def generate_and_set_key(self) -> str:
        """
        Genera una API Key de alta entropía (>288 bits), asigna `prefix` y `hashed_key`
        al modelo, y retorna la llave en texto plano por única vez.
        """
        while True:
            prefix_hex = secrets.token_hex(6)  # 12 caracteres hexadecimales
            candidate_prefix = f"cmk_live_{prefix_hex}"
            if not CartMakerApiKey.objects.filter(prefix=candidate_prefix).exists():
                break

        secret_token = secrets.token_urlsafe(36)
        raw_key = f"{candidate_prefix}_{secret_token}"
        self.prefix = candidate_prefix
        self.hashed_key = self.hash_raw_key(raw_key)
        return raw_key

    def invalidate_cache(self):
        if self.prefix:
            try:
                cache.delete(f"cmk_record:{self.prefix}")
            except Exception:
                pass

    def save(self, *args, **kwargs):
        self.invalidate_cache()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.invalidate_cache()
        return super().delete(*args, **kwargs)

    @classmethod
    def _fast_cache_digest(cls, raw_key: str) -> str:
        """
        Digest rápido en una sola pasada SHA-256 con SECRET_KEY para validar en microsegundos
        llaves que ya superaron las 60,000 rondas PBKDF2 durante la ventana activa de caché (300s).
        """
        salt = (getattr(settings, 'SECRET_KEY', '') or 'cartmaker-default-salt')
        return hashlib.sha256(f"{salt}:fast:{raw_key}".encode('utf-8')).hexdigest()

    @classmethod
    def verify_key(cls, raw_key: str, required_scope: str = 'api') -> bool:
        """
        Verifica en tiempo constante (`secrets.compare_digest`) si una API Key recibida
        en los headers HTTP es auténtica, está activa, no ha expirado y tiene permiso
        para el alcance solicitado ('api' o 'chat').
        """
        if not raw_key or not isinstance(raw_key, str):
            return False

        raw_key = raw_key.strip()
        if not raw_key.startswith("cmk_live_"):
            return False

        parts = raw_key.split("_", 3)
        if len(parts) != 4:
            return False

        prefix = f"cmk_live_{parts[2]}"
        cache_key = f"cmk_record:{prefix}"

        record = None
        try:
            record = cache.get(cache_key)
        except Exception:
            record = None

        if record is None:
            key_obj = cls.objects.filter(prefix=prefix).only(
                'id', 'prefix', 'hashed_key', 'scope', 'is_active', 'expires_at'
            ).first()
            if not key_obj:
                try:
                    cache.set(cache_key, {'invalid': True}, timeout=60)
                except Exception:
                    pass
                return False
            record = {
                'id': str(key_obj.id),
                'hashed_key': key_obj.hashed_key,
                'scope': key_obj.scope,
                'is_active': key_obj.is_active,
                'expires_at_ts': key_obj.expires_at.timestamp() if key_obj.expires_at else None,
            }
            try:
                cache.set(cache_key, record, timeout=300)
            except Exception:
                pass

        if record.get('invalid') or not record.get('is_active'):
            return False

        expires_at_ts = record.get('expires_at_ts')
        if expires_at_ts and timezone.now().timestamp() > expires_at_ts:
            return False

        allowed_scopes = ('all', required_scope)
        if record.get('scope') not in allowed_scopes:
            return False

        fast_digest = cls._fast_cache_digest(raw_key)
        cached_fast_digest = record.get('fast_digest')
        if cached_fast_digest:
            if not secrets.compare_digest(fast_digest, cached_fast_digest):
                return False
        else:
            computed_hash = cls.hash_raw_key(raw_key)
            if not secrets.compare_digest(computed_hash, record.get('hashed_key', '')):
                return False
            record['fast_digest'] = fast_digest
            try:
                cache.set(cache_key, record, timeout=300)
            except Exception:
                pass

        # Actualización ligera (throttled cada 5 min) de last_used_at
        usage_throttle_key = f"cmk_used:{prefix}"
        try:
            if cache.get(usage_throttle_key) is None:
                cls.objects.filter(prefix=prefix).update(last_used_at=timezone.now())
                cache.set(usage_throttle_key, 1, timeout=300)
        except Exception:
            pass

        return True