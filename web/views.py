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
from rest_framework import viewsets, mixins
from rest_framework.decorators import action
import secrets
from django.contrib.auth.hashers import check_password
from .cos import storage_manager
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from datetime import datetime
import requests
from django.db import transaction

####################################################
################## AUTENTICACION ###################
####################################################

class BiometricLoginView(APIView):
    """
    Endpoint para autenticación mediante vectores biométricos.
    """
    def post(self, request):
        vector = request.data.get('biometry')
        
        if not vector or not isinstance(vector, list) or len(vector) != 192:
            return Response(
                {"error": "Vector biométrico inválido o incompleto."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # 1. Definimos el umbral de seguridad
        THRESHOLD = 0.50

        # 2. Búsqueda vectorial ultra rápida con HNSW
        # Filtramos por usuarios verificados y que tengan vector
        closest_user = User.objects.filter(
            cedula_verified=True,
            biometric_vector__isnull=False,
            is_active=True
        ).annotate(
            distance=CosineDistance('biometric_vector', vector)
        ).order_by('distance').first()

        if (closest_user is None):
            return Response({
                'error':"Identidad biométrica no reconocida o no registrada."}, 
                status=status.HTTP_401_UNAUTHORIZED)

        # 3. Verificamos el veredicto del "Juez" (Distancia del Coseno)
        print("USUARIO OBTENIDO: ", closest_user)
        print("CLOSEST USER DISTANCE: ", closest_user.distance)
        if closest_user and closest_user.distance <= THRESHOLD:
            # ✅ ÉXITO: Generamos tokens manualmente
            refresh = RefreshToken.for_user(closest_user)
            
            # Construimos la respuesta con la misma metadata que tu CartMakerTokenSerializer
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'user_id': closest_user.id,
                'user_type': closest_user.user_type,
                'email': closest_user.email,
                'first_name': closest_user.first_name.strip(),
                'last_name': closest_user.last_name.strip(),
                'email_verified': closest_user.email_verified,
                'gender': closest_user.gender,
            }, status=status.HTTP_200_OK)

        # ❌ FALLO: No se reconoce el rostro o está fuera del umbral
        return Response(
            {"error": "Identidad biométrica no reconocida o no registrada."}, 
            status=status.HTTP_401_UNAUTHORIZED
        )

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
    
class GoogleRegistView(APIView):
    """
    API para el registro de usuarios a traves de Google OAuth.
    """
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'

    def post(self, request):
        token = request.data.get('token_id')
        try:
            idinfo = id_token.verify_oauth2_token(token, google_requests.Request(), settings.GOOGLE_OAUTH_CLIENT_ID)
            email = idinfo['email']
            if User.objects.filter(email=email).exists():
                return Response({'error':'Ya existe esta cuenta.'}, status=400)
            first_name = idinfo.get('given_name', '')
            last_name = idinfo.get('family_name', '')
            profile_pic = idinfo.get('picture', '')
            random_password = secrets.token_urlsafe(32)
            user = User.objects.create(
                email=email,
                first_name=first_name,
                last_name=last_name,
                profile_picture=profile_pic,
                email_verified=True,
                password=random_password,
                is_external_account=True
            )
            tokens = get_tokens_for_user(user) 
            return Response({
                "user_id": user.id,
                "access": tokens['access'],
                "refresh":tokens['refresh'],
                "email":user.email,
                "first_name":user.first_name,
                "last_name":user.last_name,
                "gender":user.gender,
                "user_type":user.user_type,
                "email_verified":True,
                "is_external_account":user.is_external_account
            }, status=201)
        except ValueError as e:
            print(e)
            return Response({"error": "Token inválido"}, status=400)

class GoogleLoginView(APIView):
    """
    API para autenticacion con Google OAuth.
    """
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'

    def post(self, request):
        token = request.data.get('token_id')
        try:
            idinfo = id_token.verify_oauth2_token(
                token, google_requests.Request(),
                settings.GOOGLE_OAUTH_CLIENT_ID)
            email = idinfo['email']
            try:
                user = User.objects.only('id', 'email', 'first_name', 'last_name', 'gender', 'user_type'
                                            ).get(email=email)
            except User.DoesNotExist:
                return Response({'error':"No existe esta cuenta."}, status=400)
            tokens = get_tokens_for_user(user) 
            return Response({
                "user_id": user.id,
                "access": tokens['access'],
                "refresh":tokens['refresh'],
                "email":user.email,
                "first_name":user.first_name,
                "last_name":user.last_name,
                "gender":user.gender,
                "user_type":user.user_type,
                "email_verified":True
            }, status=200)
        except ValueError as e:
            print(e)
            return Response({"error": "Token inválido"}, status=400)

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.none()
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

class VerifyPasswordAPI(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'navigation'
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Devuelve 200 si la contrasenia es correcta. 403 si no.
        """
        user = request.user
        password_input = request.data.get('password')
        if not password_input:
            return Response({'error':"Debe ingresar la contrasenia."}, status=400)
        if not check_password(password_input, user.password):
            return Response({'error':"Contrasenia incorrecta."}, status=403)
        return Response(status=200)

###################################################################
################### VERIFICACION BIOMETRICA #######################
###################################################################

class CheckIfCedulaExists(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    permission_classes = [IsAuthenticated]

    def get(self, request, cedula_number: str):
        details = {'error': '', 'data_retrieved': False}
        status_code = status.HTTP_200_OK

        # 1. Validación de duplicados
        if User.objects.filter(cedula_number=cedula_number).exists():
            return Response(
                {'error': f"Ya existe un usuario con la cédula {cedula_number}."}, 
                status=status.HTTP_403_FORBIDDEN
            )

        if settings.USE_CEDULAS_API:
            nacionalidad = cedula_number[0].upper()
            cedula = cedula_number[1:] # Asumiendo formato V123456
            
            try:
                cedula_api_response = requests.get(
                    f'https://api.cedula.com.ve/api/v1',
                    params={
                        'app_id': settings.CEDULAS_API_APP_ID,
                        'token': settings.CEDULAS_API_ACCESS_TOKEN,
                        'nacionalidad': nacionalidad,
                        'cedula': cedula
                    },
                    timeout=5
                )
                
                api_data = cedula_api_response.json()
                error = api_data.get('error', True)

                if not error:
                    print("API DATA DE LA CEDULA: ", api_data['data'])
                    # CASO A: Existe en CNE. Traemos nombre y fecha real.
                    details = api_data['data']
                    fecha_objeto = datetime.strptime(details['fecha_nac'], '%Y-%m-%d')
                    details['fecha_nac'] = fecha_objeto.strftime('%d/%m/%Y')
                    details['data_retrieved'] = True
                    return Response(details, status=status.HTTP_200_OK)
                
                else:
                    # CASO B:
                    # En lugar de 404, devolvemos un 200 pero avisamos que no hay data.
                    # El Flutter deberá permitirle al usuario escribir su nombre manualmente.
                    return Response({
                        'data_retrieved': False,
                        'message': 'Documento no está en CNE (posible menor de edad). Proceda con carga manual.'
                    }, status=status.HTTP_200_OK)

            except Exception as e:
                print(f"ERROR API CEDULA: {e}")
                # Si la API se cae, permitimos registro manual para no perder al usuario
                return Response({'data_retrieved': False}, status=status.HTTP_200_OK)

        return Response({'data_retrieved': False}, status=status_code)

class VerifyUser(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'navigation'
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = VerifyUserSerializer(data=request.data,
                                          context={"request":request.user})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user = request.user
        try:
            with transaction.atomic():
                file_obj = data['cedula_photo']
                extension = file_obj.name.split('.')[-1]
                file_name = f"cedula_{user.id}.{extension}"
                folder = "identity_verifications"
                relative_path = storage_manager.save_file(file_obj, folder, file_name)
                print("RUTA RELATIVA A LA CEDULA DEL USUARIO: ", relative_path)
                if relative_path:
                    user.cedula_document = relative_path
                else:
                    raise Exception("Error al guardar el archivo de la cedula en el storage.")
                file_obj = data['selfie_photo']
                extension = file_obj.name.split('.')[-1]
                file_name = f"selfie_{user.id}.{extension}"
                folder = "identity_verifications"
                relative_path = storage_manager.save_file(file_obj, folder, file_name)
                print("RUTA RELATIVA A LA SELFIE DEL USUARIO: ", relative_path)
                user.first_name = str(data['first_name']).capitalize()
                user.last_name = str(data['last_name']).capitalize()
                user.cedula_number = data['cedula_number']
                user.nacionality = UserNacionality.VENEZOLANO if str(data['nacionality']).upper() == "V" else UserNacionality.EXTRANJERO
                user.biometric_vector = data['biometry']
                user.birth_date = data['birth_date']
                user.cedula_verified = True
                user.save()
                return Response({
                    "message": "Identidad confirmada. Ahora eres un usuario verificado en CartMaker."
                }, status=status.HTTP_200_OK) 
        except Exception as e:
            print(f"Error al verificar al usuario: {e}")
            raise Exception("Hubo un problema al procesar tu verificación. Inténtalo de nuevo.")

######################################################
###################### ACTIONS #######################
######################################################

class GetCartMakerAccounts(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Devuelve todas las cuentas bancarias disponibles para CartMaker.
        """
        return Response({'data':[bank.get_json() for bank in CartMakerBankAccount.objects.filter(active=True)]}, status=status.HTTP_200_OK)


class GetMerchantPlans(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Devuelve todas los planes disponibles para comerciantes.
        """
        plans = [mp.get_json() for mp in MerchantPlan.objects.all().order_by('price')]
        dollar_bcv_tax = 0.0
        bs_price = 0.0
        try:
            response = requests.get('https://ve.dolarapi.com/v1/estado')
            response.raise_for_status()
            data = response.json()
            api_available = data.get('estado') == 'Disponible' if data.get('estado') else False
            if api_available:
                response = requests.get('https://ve.dolarapi.com/v1/dolares/oficial')
                response.raise_for_status()
                data = response.json()
                dollar_bcv_tax = data.get('promedio', 0.0)
        except Exception as e:
            print(f"Error obteniendo el precio del dolar bcv: {e}")
        for plan in plans:
            if dollar_bcv_tax > 0.0:
                bs_price = plan['price'] * dollar_bcv_tax
            plan['bs_price'] = bs_price
            plan['dollar_bcv_tax'] = dollar_bcv_tax
        return Response({'data':plans}, status=status.HTTP_200_OK)
    
class UploadSubscriptionPayment(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = UploadSubscriptionPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        bank_api_available = False 
        # TODO: Implementar chequeo de disponibilidad de api de bancos.
        subscription_type = data['subscription_type']
        subscription_id = data['subscription_id']
        if subscription_type == 1:
            # TODO: Subscripciones de Atlas Plus
            pass
        elif subscription_type == 2:
            try:
                merchant_plan = MerchantPlan.objects.get(id=subscription_id)
            except MerchantPlan.DoesNotExist:
                return Response({'error':'Plan de comerciante no encontrado.'}, status=status.HTTP_400_BAD_REQUEST)
            try:
                merchant_subscription = MerchantSubscription.objects.get(merchant=request.user)
                if merchant_subscription.valid_until < datetime.now():
                    return Response({'error':'La suscripcion aun esta activa.'}, status=status.HTTP_406_NOT_ACCEPTABLE)
            except MerchantSubscription.DoesNotExist:
                merchant_subscription = MerchantSubscription.objects.create(
                    merchant=request.user,
                    merchant_type = MerchantType.BUSINESS if merchant_plan.requires_business else MerchantType.ENTREPRENEUR,
                    plan = merchant_plan
                )
            if not bank_api_available:
                file_obj = data['payment_proof']
                extension = file_obj.name.split('.')[-1]
                file_name = f"payment_proof_{merchant_subscription.id}_{datetime.now().strftime('%d-%m-%Y_%H-%M-%S')}.{extension}"
                folder = f"subscriptions/merchant_plans/{merchant_plan.name}"
                relative_path = storage_manager.save_file(file_obj, folder, file_name)
                try:
                    payment = MerchantPlanPayment.objects.get(subscription=merchant_subscription)
                    payment.reference_number = data['reference_number']
                    payment.payment_proof_url = storage_manager.get_url(relative_path)
                    payment.amount=data['amount_sended']
                    payment.bcv_taxes_to_day=data['dollar_bcv_tax']
                except MerchantPlanPayment.DoesNotExist:
                    payment = MerchantPlanPayment(
                        subscription=merchant_subscription,
                        reference_number = data['reference_number'],
                        payment_proof_url = storage_manager.get_url(relative_path),
                        amount=data['amount_sended'],
                        bcv_taxes_to_day=data['dollar_bcv_tax'],
                    )
                payment.save()
                return Response(status=status.HTTP_201_CREATED)
            else:
                # TODO: Implementar caso para utilizar api de bancos para validar el pago.
                pass
            return Response(status=status.HTTP_200_OK)
        else:
            return Response({'error':'Tipo de subscripcion no valida.'}, status=status.HTTP_400_BAD_REQUEST)

####################################################
###################### CACHE #######################
####################################################

class UserCacheAPI(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'navigation'
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Devuelve todos los datos necesarios para la cache de usuario de la app.
        """
        user = request.user
        locations = [location.get_json() for location in ClientLocation.objects.filter(user=user)]
        contact_methods = [contact_method.get_json() for contact_method in ClientContactMethod.objects.filter(client=user).order_by('method_type')]
        cache = {
            "user_id":user.id,
            "email":user.email,
            "creation":user.creation.strftime('%d/%m/%Y, %H:%M:%S'),
            "first_name":user.first_name,
            "last_name":user.last_name,
            "birth_date":user.birth_date if user.birth_date else "",
            "email_verified":user.email_verified,
            "user_type":user.user_type,
            "profile_picture":user.get_profile_picture_url(),
            "cedula_document_url":user.cedula_document if user.cedula_document else "",
            "cedula_verified":user.cedula_verified,
            "cedula_number":user.cedula_number if user.cedula_number else "",
            "gender":user.gender,
            "locations":locations,
            "is_external_account":user.is_external_account,
            'contact_methods':contact_methods
        }
        print(f"Cache del usuario {user}: {cache}")
        return Response(cache, status=200)
    
class HomeCacheAPI(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'navigation'
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Devuelve todos los datos necesarios para la cache de la home screen de la app.
        """
        announcements = [announcement.get_json() for announcement in Announcement.objects.filter(active=True).order_by('-creation')]
        categories = [
            category.get_json() 
            for category in Category.objects.prefetch_related('subcategories').all()
        ]
        cache = {
            "announcements":announcements,
            "categories":categories
        }
        return Response(cache, status=200)

####################################################
#################### VIEW SETS #####################
####################################################

class ClientContactMethodViewSet(viewsets.ModelViewSet):
    serializer_class = ClientContactMethodSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ClientContactMethod.objects.filter(client=self.request.user)

    def perform_create(self, serializer):
        serializer.save(client=self.request.user)
        
class ClientLocationViewSet(viewsets.ModelViewSet):
    serializer_class = ClientLocationSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ClientLocation.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class UserViewSet(mixins.RetrieveModelMixin,
                  mixins.UpdateModelMixin,
                  viewsets.GenericViewSet):
    serializer_class = UserSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    permission_classes = [IsAuthenticated]
    parser_classes = (JSONParser, MultiPartParser, FormParser)

    def get_queryset(self):
        return User.objects.filter(id=self.request.user.id)

    def get_object(self):
        return self.request.user
    
    @action(detail=False, methods=['post'], url_path='upload-avatar')
    def upload_avatar(self, request):
        file_obj = request.FILES.get('photo')
        if not file_obj:
            return Response({"error": "No se envió ninguna imagen"}, status=400)
        user = request.user
        extension = file_obj.name.split('.')[-1]
        file_name = f"avatar_{user.id}_{datetime.now().strftime('%d-%m-%Y_%H-%M-%S')}.{extension}"
        folder = "profiles/avatars"
        relative_path = storage_manager.save_file(file_obj, folder, file_name)
        if relative_path:
            if user.profile_picture:
                storage_manager.delete_file(user.profile_picture)
            user.profile_picture = relative_path
            user.save()
            return Response({
                "message": "Foto actualizada",
                "url": storage_manager.get_url(relative_path)
            })
        return Response({"error": "Error al guardar el archivo"}, status=500)

####################################################
################### VISTAS WEB #####################
####################################################

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
