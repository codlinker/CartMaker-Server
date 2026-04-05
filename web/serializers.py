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
        return data
    
class ClientLocationSerializer(serializers.ModelSerializer):
    latitude = serializers.FloatField(write_only=True)
    longitude = serializers.FloatField(write_only=True)

    class Meta:
        model = ClientLocation
        fields = ['id', 'name', 'latitude', 'longitude'] 
        read_only_fields = ['id']

    def create(self, validated_data):
        user = validated_data.get('user')
        if ClientLocation.objects.filter(user=user).count() >= 5:
            # Lanzamos la excepción. DRF la atrapará y devolverá un HTTP 400 a Flutter
            raise serializers.ValidationError(
                {"error": "Has alcanzado el límite máximo de 5 ubicaciones permitidas."}
            )
        lat = validated_data.pop('latitude')
        lon = validated_data.pop('longitude')
        validated_data['coordinates'] = Point(lon, lat, srid=4326)
        return super().create(validated_data)

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['latitude'] = instance.coordinates.y
        representation['longitude'] = instance.coordinates.x
        return representation