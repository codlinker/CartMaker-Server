import math
from .utils import *
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from .models import *
from api.core import *
from django.contrib.gis.geos import Point
from pgvector.django import CosineDistance
from django.db import transaction

User = get_user_model()

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    tokens = serializers.SerializerMethodField()
    category_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        allow_empty=True,
    )

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'password', 'tokens', 'gender', "id", 'category_ids')

    def create(self, validated_data):
        raw_category_ids = validated_data.pop('category_ids', None)
        with transaction.atomic():
            user = User.objects.create_user(
                email=validated_data['email'],
                password=validated_data['password'],
                first_name=validated_data.get('first_name', ''),
                last_name=validated_data.get('last_name', ''),
                gender=validated_data['gender']
            )
            if raw_category_ids is not None:
                valid_cats = Category.objects.filter(id__in=raw_category_ids)
                user.preferred_categories.set(valid_cats)
            send_email_otp(validated_data['email'])
        return user

    def get_tokens(self, user):
        refresh = RefreshToken.for_user(user)
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['user_id'] = representation.pop('id')
        representation['user_type'] = instance.user_type 
        representation['gender'] = instance.gender
        representation['email_verified'] = instance.email_verified
        representation['preferred_category_ids'] = instance.get_preferred_category_ids()
        return representation

class CartMakerTokenSerializer(TokenObtainPairSerializer):
    """
    Serializer personalizado para incluir metadata del usuario en la respuesta del JWT.
    """
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data['user_id'] = self.user.id
        data['user_type'] = self.user.user_type
        data['email'] = self.user.email
        data['first_name'] = f"{self.user.first_name}".strip()
        data['last_name'] = f"{self.user.last_name}".strip()
        data['email_verified'] = self.user.email_verified
        data['gender'] = self.user.gender
        data['preferred_category_ids'] = self.user.get_preferred_category_ids()
        return data
    
class ClientLocationSerializer(serializers.ModelSerializer):
    latitude = serializers.FloatField(write_only=True)
    longitude = serializers.FloatField(write_only=True)

    class Meta:
        model = ClientLocation
        fields = ['id', 'name', 'latitude', 'longitude', "description", "is_default"] 
        read_only_fields = ['id']

    def create(self, validated_data):
        user = validated_data.get('user')
        client_locations_qs = ClientLocation.objects.only('id', 'user', 'is_default').filter(user=user)
        locations_count = client_locations_qs.count()
        if locations_count >= 5:
            raise serializers.ValidationError(
                {"error": "Has alcanzado el límite máximo de 5 ubicaciones permitidas."}
            )
        elif locations_count == 0:
            validated_data['is_default'] = True
        default_location = None
        if client_locations_qs.filter(is_default=True).exists():
            default_location = client_locations_qs.get(is_default=True)
        if validated_data['is_default'] and default_location != None:
            default_location.is_default = False
            default_location.save()
        lat = validated_data.pop('latitude')
        lon = validated_data.pop('longitude')
        validated_data['coordinates'] = Point(lon, lat, srid=4326)
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        lat = validated_data.pop('latitude', None)
        lon = validated_data.pop('longitude', None)
        if lat is not None and lon is not None:
            validated_data['coordinates'] = Point(lon, lat, srid=4326)
        return super().update(instance, validated_data)

    def to_representation(self, instance):
        return instance.get_json()
    
class ClientContactMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientContactMethod
        fields = [
            'id',
            'client',
            'method_type',
            'value'
        ]
        read_only_fields = [
            'client'
        ]

    def create(self, validated_data):
        if ClientContactMethod.objects.filter(client=validated_data['client']).count() >= 5:
            raise serializers.ValidationError("Máximo 5 métodos de contacto permitidos."
            )
        if validated_data['method_type'] in [1, 2]:
            if len(validated_data['value']) != 11:
                raise serializers.ValidationError("Debes ingresar un número telefónico válido. No uses el +58."
                )
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        method_type = validated_data.get('method_type', instance.method_type)
        value = validated_data.get('value', instance.value)
        if method_type in [1, 2]:
            if len(value) != 11:
                raise serializers.ValidationError("Debes ingresar un número telefónico válido. No uses el +58."
                )
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()
        return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation.pop('client')
        return representation
    
class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        # Incluimos los campos que Flutter necesitará leer
        fields = [
            'id', 
            'section', 
            'category', 
            'title', 
            'body', 
            'metadata',
            'created_at'
        ]
    
class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'birth_date', 
            'gender', 'profile_picture', 'user_type', 'cedula_number', 
            'cedula_document', 'cedula_verified', 'email_verified', 
            'is_external_account', 'creation', 'password',
            'biometric_consent_accepted_at', 'biometric_consent_version', 'biometric_suppressed_at',
        ]
        read_only_fields = [
            'id', 'email', 'user_type', 'cedula_verified', 
            'email_verified', 'is_external_account', 'creation',
            'biometric_consent_accepted_at', 'biometric_consent_version', 'biometric_suppressed_at',
        ]

    def validate_first_name(self, value):
        return value.strip().title()

    def validate_last_name(self, value):
        return value.strip().title()

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password is not None:
            instance.set_password(password)
        instance.save()
        return instance
    
class ProductImageSerializer(serializers.Serializer):
    image_url = serializers.URLField()
    idx = serializers.IntegerField()
    apply_transparency = serializers.BooleanField(default=False)
    transparency_color = serializers.CharField(max_length=7, required=False, allow_null=True)

MAX_IMAGE_SIZE_MB = 10
MAX_VIDEO_SIZE_MB = 40

def validate_image_size(file):
    if file.size > MAX_IMAGE_SIZE_MB * 1024 * 1024:
        raise serializers.ValidationError(f"La imagen no puede pesar más de {MAX_IMAGE_SIZE_MB}MB.")
    return file

def validate_video_size(file):
    if file.size > MAX_VIDEO_SIZE_MB * 1024 * 1024:
        raise serializers.ValidationError(f"El video no puede pesar más de {MAX_VIDEO_SIZE_MB}MB.")
    return file

class VerifyUserSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150, required=True)
    last_name = serializers.CharField(max_length=150, required=True)
    cedula_number = serializers.CharField(max_length=20, required=True)
    birth_date = serializers.DateField(format="%d/%m/%Y", input_formats=['%d/%m/%Y'], required=True)
    cedula_photo = serializers.ImageField(required=True, validators=[validate_image_size])
    selfie_photo = serializers.ImageField(required=True, validators=[validate_image_size])
    nacionality = serializers.CharField(max_length=1, required=True)
    biometry = serializers.ListField(
        child=serializers.FloatField(),
        min_length=BIOMETRIC_VECTOR_DIMENSIONS,
        max_length=BIOMETRIC_VECTOR_DIMENSIONS,
        required=True
    )
    biometric_consent_accepted = serializers.CharField(max_length=16, required=False, allow_blank=True, allow_null=True)
    biometric_consent_version = serializers.CharField(max_length=32, required=False, allow_blank=True, allow_null=True)

    def _get_current_user(self):
        req_ctx = self.context.get('request')
        return req_ctx.user if hasattr(req_ctx, 'user') else req_ctx

    def validate_cedula_number(self, value):
        cleaned = str(value).strip().upper()
        current_user = self._get_current_user()
        qs = User.objects.filter(cedula_number__iexact=cleaned, is_active=True)
        if current_user and getattr(current_user, 'id', None):
            qs = qs.exclude(id=current_user.id)
        if qs.exists():
            raise serializers.ValidationError(
                f"Ya existe un usuario registrado con la cédula {cleaned}."
            )
        return cleaned

    def validate_biometry(self, value):
        """
        Validación matemática y detección de identidad duplicada (1:N) en 512 dimensiones
        usando normalización L2 sobre la hiperesfera unitaria S^511, índice HNSW y Distancia Coseno.
        """
        is_valid_vec, normalized_vector, vec_error = normalize_biometric_vector(
            value, expected_dim=BIOMETRIC_VECTOR_DIMENSIONS
        )
        if not is_valid_vec:
            raise serializers.ValidationError(vec_error)

        try:
            current_user = self._get_current_user()
            qs = User.objects.filter(
                cedula_verified=True,
                biometric_vector__isnull=False,
                is_active=True,
            )
            if current_user and getattr(current_user, 'id', None):
                qs = qs.exclude(id=current_user.id)

            closest_match = qs.annotate(
                distance=CosineDistance('biometric_vector', normalized_vector)
            ).order_by('distance').first()

            if closest_match and closest_match.distance is not None and closest_match.distance < BIOMETRIC_KYC_DUPLICATE_THRESHOLD:
                print(
                    f"🚨 ALERTA DE SEGURIDAD BIOMÉTRICA (512-D): Intento de multicuenta bloqueado. "
                    f"Distancia Coseno: {closest_match.distance:.4f} (< {BIOMETRIC_KYC_DUPLICATE_THRESHOLD}) "
                    f"contra C.I: {closest_match.cedula_number}"
                )
                raise serializers.ValidationError(
                    "Esta identidad biométrica ya está vinculada a otra cuenta verificada en CartMaker."
                )
        except serializers.ValidationError:
            raise
        except Exception as e:
            print(f"Error al validar la biometria: {e}")
            raise serializers.ValidationError(
                'Error interno al validar la biometría. Por favor, inténtelo de nuevo.'
            )
        return normalized_vector

class UploadSubscriptionPaymentSerializer(serializers.Serializer):
    reference_number = serializers.CharField(required=True)
    payment_date = serializers.DateField(format="%d/%m/%Y", input_formats=['%d/%m/%Y'], required=True)
    amount_sended = serializers.FloatField(required=True)
    subscription_type = serializers.IntegerField(required=True)
    subscription_id = serializers.IntegerField(required=True)
    payment_proof = serializers.ImageField(required=True, validators=[validate_image_size])
    dollar_bcv_tax = serializers.FloatField(required=True)

class RegistDeviceSerializer(serializers.Serializer):
    fcm_token = serializers.CharField(required=True)
    platform = serializers.CharField(required=True)

class UpdateCompanySerializer(serializers.Serializer):
    company_id = serializers.CharField(required=True)
    name = serializers.CharField(required=False)
    profile_img = serializers.ImageField(required=False, validators=[validate_image_size])
    main_store_img = serializers.ImageField(required=False, validators=[validate_image_size])
    presentation_video_thumbnail = serializers.FileField(required=False, validators=[validate_image_size])
    presentation_video = serializers.FileField(required=False, validators=[validate_video_size])
    
    gamification_enabled = serializers.BooleanField(required=False, allow_null=True)
    gamification_tokens_per_dollar = serializers.IntegerField(required=False)
    category_id = serializers.IntegerField(required=False)
    work_hours = serializers.JSONField(required=False)
    work_days = serializers.CharField(required=False)
    whatsapp_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    instagram_handle = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    phone_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    store_type = serializers.IntegerField(required=False, allow_null=True)
    is_mall = serializers.BooleanField(required=False, allow_null=True)
    lat = serializers.FloatField(required=False, allow_null=True)
    lng = serializers.FloatField(required=False, allow_null=True)
    address = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    selected_mall_id = serializers.IntegerField(required=False, allow_null=True)
    selected_mall_floor = serializers.IntegerField(required=False, allow_null=True)

class UpdateStoreSerializer(serializers.Serializer):
    store_id = serializers.CharField(required=True) # ID de la sucursal
    name = serializers.CharField(required=False)
    is_active = serializers.BooleanField(required=False, allow_null=True)
    store_img = serializers.ImageField(required=False, validators=[validate_image_size])
    
    work_hours = serializers.JSONField(required=False)
    work_days = serializers.CharField(required=False)
    whatsapp_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    instagram_handle = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    phone_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    # Campos de Ubicación
    store_type = serializers.IntegerField(required=False, allow_null=True)
    is_mall = serializers.BooleanField(required=False, allow_null=True)
    lat = serializers.FloatField(required=False, allow_null=True)
    lng = serializers.FloatField(required=False, allow_null=True)
    address = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    selected_mall_id = serializers.IntegerField(required=False, allow_null=True)
    selected_mall_floor = serializers.IntegerField(required=False, allow_null=True)

class CreateCompanySerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    comercial_entity_type = serializers.IntegerField(required=False, allow_null=True)
    merchant_type = serializers.IntegerField(required=False, allow_null=True)
    store_type = serializers.IntegerField()
    company_category = serializers.IntegerField()
    selected_mall_id = serializers.IntegerField(required=False, allow_null=True)
    selected_mall_floor = serializers.IntegerField(required=False, allow_null=True)
    lat = serializers.FloatField(required=False, allow_null=True)
    lng = serializers.FloatField(required=False, allow_null=True)
    address = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    # --- CAMPOS KYB OPCIONALES (Requeridos cuando comercial_entity_type == 1) ---
    rif_number = serializers.CharField(max_length=20, required=False, allow_null=True, allow_blank=True)
    razon_social = serializers.CharField(max_length=180, required=False, allow_null=True, allow_blank=True)
    mercantil_oficina = serializers.CharField(max_length=150, required=False, allow_null=True, allow_blank=True)
    mercantil_numero = serializers.CharField(max_length=50, required=False, allow_null=True, allow_blank=True)
    mercantil_tomo = serializers.CharField(max_length=50, required=False, allow_null=True, allow_blank=True)
    representante_cedula = serializers.CharField(max_length=25, required=False, allow_null=True, allow_blank=True)
    kyb_ocr_verified = serializers.BooleanField(required=False, default=False)
    kyb_confidence_score = serializers.IntegerField(required=False, default=0)
    rif_document = serializers.ImageField(required=False, allow_null=True, validators=[validate_image_size])
    mercantil_document = serializers.ImageField(required=False, allow_null=True, validators=[validate_image_size])
    rif_image_sha256 = serializers.CharField(max_length=64, required=False, allow_null=True, allow_blank=True)
    mercantil_image_sha256 = serializers.CharField(max_length=64, required=False, allow_null=True, allow_blank=True)

    def validate(self, attrs):
        entity_type = attrs.get("comercial_entity_type")
        if entity_type is None:
            entity_type = attrs.get("merchant_type")
        if entity_type is None:
            raise serializers.ValidationError({"comercial_entity_type": "Este campo es requerido."})
        attrs["comercial_entity_type"] = entity_type
        return attrs

class CreateStoreSerializer(serializers.Serializer):
    company_id = serializers.UUIDField(required=True)
    name = serializers.CharField(required=True, max_length=255)
    store_img = serializers.ImageField(required=False, validators=[validate_image_size])
    work_hours = serializers.JSONField(required=True)
    work_days = serializers.CharField(required=False)
    
    # Ubicación (Obligatorios)
    store_type = serializers.IntegerField(required=True)
    is_mall = serializers.BooleanField(required=True)
    lat = serializers.FloatField(required=True)
    lng = serializers.FloatField(required=True)
    address = serializers.CharField(required=True)
    
    # Mall (Opcionales dependiendo de is_mall)
    selected_mall_id = serializers.IntegerField(required=False, allow_null=True)
    selected_mall_floor = serializers.IntegerField(required=False, allow_null=True)
    
    # Contactos iniciales (Opcionales)
    whatsapp_number = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    instagram_handle = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    phone_number = serializers.CharField(required=False, allow_null=True, allow_blank=True)

class FlexibleJSONField(serializers.Field):
    """
    Acepta tanto objetos nativos (dict/list) en peticiones JSON como strings codificados
    en JSON cuando se envían mediante MultipartFormData desde Flutter.
    """
    def __init__(self, default_factory=dict, **kwargs):
        self.default_factory = default_factory
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        if data is None or data == "":
            return self.default_factory()
        if isinstance(data, (dict, list)):
            return data
        if isinstance(data, str):
            raw = data.strip()
            if not raw:
                return self.default_factory()
            try:
                return json.loads(raw)
            except Exception as exc:
                raise serializers.ValidationError(f"Formato JSON inválido: {exc}")
        return self.default_factory()

    def to_representation(self, value):
        return value


class ProductSerializer(serializers.ModelSerializer):
    category_id = serializers.IntegerField(write_only=True)
    # DRF convertirá los "true"/"false" de MultipartFormData a booleanos automáticamente
    discounts_by_tokens_active = serializers.BooleanField(default=False, required=False)
    selling_unit = serializers.CharField(max_length=32, required=False, allow_blank=True)
    unit_label = serializers.CharField(max_length=50, required=False, allow_blank=True)
    allow_fractional_quantity = serializers.BooleanField(required=False)
    min_order_quantity = serializers.DecimalField(max_digits=10, decimal_places=3, required=False)
    unit_step = serializers.DecimalField(max_digits=10, decimal_places=3, required=False)
    attributes = FlexibleJSONField(default_factory=dict, required=False)
    variants = FlexibleJSONField(default_factory=list, required=False)
    modifier_groups = FlexibleJSONField(default_factory=list, required=False)

    class Meta:
        model = Product
        fields = [
            'id', 
            'name', 
            'price', 
            'description', 
            'category_id', 
            'discounts_by_tokens_active',
            'selling_unit',
            'unit_label',
            'allow_fractional_quantity',
            'min_order_quantity',
            'unit_step',
            'attributes',
            'variants',
            'modifier_groups',
        ]

    def to_representation(self, instance):
        # Delegamos la serialización de salida al método del modelo
        return instance.get_json()

class CompanyVideoStorySerializer(serializers.ModelSerializer):
    """
    Serializer robusto para crear Historias de Video desde Flutter.
    """
    # 💡 Declaramos explícitamente los campos de archivo
    video_file = serializers.FileField(required=True, validators=[validate_video_size])
    thumbnail = serializers.ImageField(required=True, validators=[validate_image_size])
    
    # 💡 Los campos de texto siguen siendo opcionales y tolerantes
    associated_item_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    description = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    class Meta:
        model = CompanyVideoStory
        fields = [
            'id', 'video_file', 'thumbnail', 'description', 
            'associated_item_id', 'creation', 'expires_at', 'views_count'
        ]
        read_only_fields = ['id', 'creation', 'expires_at', 'views_count']

    def create(self, validated_data):
        item_id = validated_data.pop('associated_item_id', None)
        
        user = self.context['request'].user
        company = Company.objects.filter(owner=user).first()
        
        if not company:
            raise serializers.ValidationError({"company": "No tienes una empresa registrada para subir videos."})
            
        validated_data['company'] = company
        
        if item_id and str(item_id).strip():
            try:
                item = InventoryItem.objects.get(id=item_id, store__company=company)
                validated_data['associated_item'] = item
            except InventoryItem.DoesNotExist:
                raise serializers.ValidationError({"associated_item_id": "El producto seleccionado no existe o no te pertenece."})
        else:
            validated_data['associated_item'] = None

        return super().create(validated_data)