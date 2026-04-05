from rest_framework.views import APIView
from rest_framework.renderers import TemplateHTMLRenderer
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import *
from .models import *
from rest_framework.permissions import *
from .utils import *
from rest_framework import generics, status
from rest_framework.throttling import ScopedRateThrottle
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from django.conf import settings
from rest_framework.permissions import IsAuthenticated
from rest_framework import viewsets

class CartMakerTokenView(TokenObtainPairView):
    """
    Vista personalizada para el login que devuelve datos extendidos del perfil.
    """
    serializer_class = CartMakerTokenSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'

class GoogleClientId(APIView):
    """
    API para obtener el Google Client Id.
    """
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'

    def get(self, request):
        return Response({"google_client_id":settings.GOOGLE_OAUTH_CLIENT_ID}, status=200)

class GoogleLoginView(APIView):
    """
    API para autenticacion con Google OAuth.
    """
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'

    def post(self, request):
        token = request.data.get('idToken')
        
        try:
            # 1. Validar el token con Google
            idinfo = id_token.verify_oauth2_token(token, google_requests.Request(), settings.GOOGLE_OAUTH_CLIENT_ID)

            print('ID INFO DEL USUARIO OBTENIDA DE GOOGLE: ', idinfo)

            # 2. Extraer información del usuario
            email = idinfo['email']
            first_name = idinfo.get('given_name', '')
            last_name = idinfo.get('family_name', '')
            profile_pic = idinfo.get('picture', '')

            # # 3. Lógica de "Get or Create" en tu modelo User
            # user, created = User.objects.get_or_create(
            #     email=email,
            #     defaults={
            #         'first_name': first_name,
            #         'last_name': last_name,
            #         'profile_picture': profile_pic,
            #         'email_verified': True, # Google ya lo verificó
            #         'password': User.objects.make_random_password() # Password dummy
            #     }
            # )

            # 4. Generar TU token (SimpleJWT u otro)
            # tokens = get_tokens_for_user(user) 
            
            # return Response({
            #     "user_id": user.id,
            #     "created": created,
            #     # "access": tokens['access']
            # })
            return Response({"error":"Solo probando"}, status=500)

        except ValueError:
            return Response({"error": "Token inválido"}, status=400)

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.none() # Vacio porque solo se necesita especificar el modelo
    serializer_class = RegisterSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'

    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)
    
class VerifyEmailView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Verifica el correo del usuario validando el código OTP.
        
        Params:
            code (str): Código ingresado por el usuario.
        """
        user = request.user 
        if user.email_verified:
            return Response(
                {"error": "El usuario ya verificó el correo."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        submitted_code = request.data.get('code')
        saved_code = get_email_otp(user.email)
        if saved_code is None:
            return Response(
                {"error": "El código ha expirado. Solicite uno nuevo."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        if saved_code == submitted_code:
            cache.delete(f"otp_verification_{user.email}")
            user.email_verified = True
            user.save(update_fields=['email_verified'])
            return Response(
                {"message": "Correo verificado exitosamente."}, 
                status=status.HTTP_200_OK
            )
        else:
            return Response(
                {"error": "Código inválido."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

class ResendEmailView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Reenvía el código de verificación al correo del usuario autenticado.
        """
        user = request.user
        if user.email_verified:
            return Response(
                {"error": "El usuario ya verificó el correo."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            send_email_otp(user.email)
            return Response(
                {"message": "Código reenviado exitosamente."},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {'error': f"Ha ocurrido un error al enviar el código: {e}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
class ClientLocationViewSet(viewsets.ModelViewSet):
    serializer_class = ClientLocationSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    permission_classes = [IsAuthenticated] # Exige que el usuario envíe un token válido

    def get_queryset(self):
        # Magia de privacidad: Sobrescribimos la consulta base.
        # Cuando el usuario haga GET /locations/, solo verá las suyas.
        return ClientLocation.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        # Magia de creación: Cuando Flutter haga POST para guardar "Casa",
        # no necesitamos que envíe su ID de usuario. Django lo saca 
        # automáticamente del token de seguridad y lo inyecta aquí.
        serializer.save(user=self.request.user)

class Home(APIView):
    """
    Home principal
    """
    permission_classes = [IsAuthenticated]
    renderer_classes = [TemplateHTMLRenderer]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'navigation'

    def get(self, request):
        return Response({}, template_name='index.html')
