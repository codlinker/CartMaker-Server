from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from .models import *
from web.utils import *
from django.contrib.gis.geos import Point

User = get_user_model()

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    tokens = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'password', 'tokens', 'gender', "id")

    def create(self, validated_data):
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            gender=validated_data['gender']
        )
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
        representation['email_otp_code'] = get_email_otp(instance.email)
        representation['email_verified'] = instance.email_verified
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
        return data
    
class ClientLocationSerializer(serializers.ModelSerializer):
    latitude = serializers.FloatField(write_only=True)
    longitude = serializers.FloatField(write_only=True)

    class Meta:
        model = ClientLocation
        fields = ['id', 'name', 'latitude', 'longitude', "is_default"] 
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

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['latitude'] = instance.coordinates.y
        representation['longitude'] = instance.coordinates.x
        return representation
    
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
        if validated_data['method_type'] in [1, 2]:
            if len(validated_data['value']) != 11:
                raise serializers.ValidationError("Debes ingresar un número telefónico válido. No uses el +58."
                )
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation.pop('client')
        return representation
    
class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'birth_date', 
            'gender', 'profile_picture', 'user_type', 'cedula_number', 
            'cedula_document', 'cedula_verified', 'email_verified', 
            'is_external_account', 'creation', 'password' 
        ]
        read_only_fields = [
            'id', 'email', 'user_type', 'cedula_verified', 
            'email_verified', 'is_external_account', 'creation'
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

class ProductSerializer(serializers.ModelSerializer):
    # Esto te permite validar la estructura del JSON al recibir datos
    images = ProductImageSerializer(many=True)

    class Meta:
        model = Product
        fields = '__all__'