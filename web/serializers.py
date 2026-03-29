from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    tokens = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'email', 'first_name', 'last_name', 'password', 'tokens')

    def create(self, validated_data):
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            username=validated_data['email'] # O el campo que uses como username
        )
        return user

    def get_tokens(self, user):
        refresh = RefreshToken.for_user(user)
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }

class CartMakerTokenSerializer(TokenObtainPairSerializer):
    """
    Serializer personalizado para incluir metadata del usuario en la respuesta del JWT.
    """
    @classmethod
    def get_token(cls, user):
        # Esto añade datos al PAYLOAD del token (el JSON encriptado)
        token = super().get_token(user)
        token['user_type'] = user.user_type
        return token

    def validate(self, attrs):
        # Esto añade datos a la RESPUESTA JSON que recibe Postman/Flutter
        data = super().validate(attrs)
        
        # 'self.user' es cargado automáticamente por el método validate original
        data['user_id'] = self.user.id
        data['user_type'] = self.user.user_type
        data['profile_picture'] = self.user.profile_picture
        data['email'] = self.user.email
        data['full_name'] = f"{self.user.first_name} {self.user.last_name}".strip()
        
        return data