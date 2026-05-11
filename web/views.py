from dateutil.relativedelta import relativedelta
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
from .firebase_admin import NotificationManager
from django.utils import timezone
from .tasks import *
from django.contrib.gis.geos import Polygon, Point

####################################################
################## AUTENTICACION ###################
####################################################

class RegistDeviceView(APIView):
    serializer_class = RegistDeviceSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'

    def delete(self, request):
        token = request.data.get('fcm_token')
        DeviceToken.objects.filter(token=token, user=request.user).delete()
        return Response({"message": "Token eliminado"}, status=status.HTTP_204_NO_CONTENT)

    def post(self, request):
        fcm_token = request.data.get('fcm_token')
        platform = request.data.get('platform', 'android')
        device, created = DeviceToken.objects.update_or_create(
            token=fcm_token,
            defaults={
                'user': request.user, 
                'platform': platform
            }
        )
        return Response({"message": "Dispositivo registrado"}, status=status.HTTP_200_OK)

class BiometricLoginView(APIView):
    """
    Endpoint para autenticación mediante vectores biométricos.
    """
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'

    def post(self, request):
        vector = request.data.get('biometry')
        
        if not vector or not isinstance(vector, list) or len(vector) != 192:
            return Response(
                {"error": "Vector biométrico inválido o incompleto."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        THRESHOLD_PERFECT = 0.35
        THRESHOLD_ACCEPTABLE = 0.45
        closest_user = User.objects.filter(
            cedula_verified=True,
            biometric_vector__isnull=False,
            is_active=True
        ).annotate(
            distance=CosineDistance('biometric_vector', vector)
        ).order_by('distance').first()

        if closest_user is None:
            return Response({
                'error':"Identidad biométrica no reconocida o no registrada."}, 
                status=status.HTTP_401_UNAUTHORIZED)

        print("USUARIO OBTENIDO: ", closest_user)
        print("CLOSEST USER DISTANCE: ", closest_user.distance)
        if closest_user.distance <= THRESHOLD_ACCEPTABLE:
            if closest_user.distance > THRESHOLD_PERFECT:
                update_rolling_template.delay(closest_user.id, vector)
            refresh = RefreshToken.for_user(closest_user)
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
        return Response(
            {"error": "Identidad no verificada. Por favor, asegúrese de tener buena iluminación o no usar accesorios."}, 
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
            if User.objects.filter(email=email, is_active=True).exists():
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
                                            ).get(email=email, is_active=True)
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
        if User.objects.filter(cedula_number=cedula_number, is_active=True).exists():
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
                return Response({'error':'Plan no encontrado.'}, status=status.HTTP_400_BAD_REQUEST)
            try:
                merchant_subscription = MerchantSubscription.objects.only('id', 'merchant').get(merchant=request.user)
                if merchant_subscription.valid_until and merchant_subscription.valid_until < timezone.now():
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
                file_name = f"payment_proof_{merchant_subscription.id}_{timezone.localtime(timezone.now()).strftime('%d-%m-%Y_%H-%M-%S')}.{extension}"
                folder = f"subscriptions/merchant_plans/{merchant_plan.name}"
                relative_path = storage_manager.save_file(file_obj, folder, file_name)
                if MerchantPlanPayment.objects.filter(
                    subscription=merchant_subscription,
                    verified_at__isnull=True,
                    status=PaymentStatus.PENDING
                    ).exists():
                    return Response({'error':"Ya tienes un pago pendiente por verificacion por este plan."}, status=status.HTTP_406_NOT_ACCEPTABLE)
                payment = MerchantPlanPayment.objects.create(
                    subscription=merchant_subscription,
                    reference_number = data['reference_number'],
                    payment_proof_url = relative_path,
                    amount=data['amount_sended'],
                    bcv_taxes_to_day=data['dollar_bcv_tax'],
                )
                return Response({'payment_data':payment.get_json(), 'subscription_data':merchant_subscription.get_json()}, status=status.HTTP_201_CREATED)
            else:
                # TODO: Implementar caso para utilizar api de bancos para validar el pago.
                pass
            return Response(status=status.HTTP_200_OK)
        else:
            return Response({'error':'Tipo de subscripcion no valida.'}, status=status.HTTP_400_BAD_REQUEST)
        
class FullPaySubscriptionWithWalletView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                print("REQUEST DATA: ", request.data)
                # 1. Obtener el plan y crear la subscripcion u obtenerla si ya existe
                merchant_plan = MerchantPlan.objects.only('price', 'name').get(id=request.data.get('plan_id'))
                try:
                    merchant_subscription = MerchantSubscription.objects.select_related('plan').get(
                        merchant=request.user
                    )
                except MerchantSubscription.DoesNotExist:
                    merchant_subscription = MerchantSubscription(
                        merchant=request.user,
                        merchant_type=MerchantType.BUSINESS if merchant_plan.requires_business else MerchantType.ENTREPRENEUR,
                        plan=merchant_plan
                    )

                plan_price_usd = Decimal(str(merchant_plan.price))

                # 2. Obtener la billetera del usuario
                wallet = UserWallet.objects.select_for_update().get(user=request.user)

                # 3. Validar si tiene saldo suficiente
                if wallet.balance < plan_price_usd:
                    return Response({
                        'success': False,
                        'message': 'Saldo insuficiente en la billetera.'
                    }, status=status.HTTP_400_BAD_REQUEST)

                # 4. Descontar el dinero de la billetera
                wallet.regist_transaction(
                    amount=plan_price_usd,
                    sub_type='merchant',
                    description=f"Pago de suscripción con saldo: {merchant_plan.name}",
                    transaction='substract'
                )

                # 5. Activar la suscripción
                merchant_subscription.valid_until = timezone.now() + relativedelta(months=1)
                merchant_subscription.save()

                dollar_bcv_tax = 1.0
                try:
                    response = requests.get('https://ve.dolarapi.com/v1/estado')
                    response.raise_for_status()
                    data = response.json()
                    api_available = data.get('estado') == 'Disponible' if data.get('estado') else False
                    if api_available:
                        response = requests.get('https://ve.dolarapi.com/v1/dolares/oficial')
                        response.raise_for_status()
                        data = response.json()
                        dollar_bcv_tax = data.get('promedio', 1.0)
                except Exception as e:
                    print(f"Error obteniendo el precio del dolar bcv: {e}")

                # 6. Dejar un registro en el historial de pagos
                # Lo creamos directamente como APROBADO
                merchant_payment = MerchantPlanPayment.objects.create(
                    subscription=merchant_subscription,
                    reference_number=f"WALLET-{uuid.uuid4().hex[:8].upper()}",
                    amount=0,
                    bcv_taxes_to_day=dollar_bcv_tax,
                    status=PaymentStatus.APPROVED,
                    verified_at=timezone.now()
                )

                title = '¡Pago Validado!'
                
                # 7. Crear la notificacion
                body = f'Hemos aprobado el pago por la suscripción <b>{merchant_plan.name}</b>. Ya puedes registrar tus productos en CartMaker.'
                    
                Notification.objects.create(
                    user=request.user,
                    section=NotificationSection.HOME,
                    title=title,
                    body=body,
                    category=NotificationCategory.PAYMENT_APPROVED,
                    metadata={'payment_id':str(merchant_payment.id)}
                )

                return Response({
                    'success': True,
                    'message': '¡Suscripción renovada exitosamente usando tu saldo a favor!',
                    'data': {
                        'new_balance': float(wallet.balance - plan_price_usd),
                        'valid_until': merchant_subscription.valid_until.strftime("%d/%m/%Y, %H:%M:%S")
                    }
                }, status=status.HTTP_200_OK)

        except MerchantPlan.DoesNotExist:
            return Response({
                'success': False, 
                'message': 'Suscripción no encontrada.'
            }, status=status.HTTP_404_NOT_FOUND)
            
        except UserWallet.DoesNotExist:
            return Response({
                'success': False, 
                'message': 'No se encontró la billetera del usuario.'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            print("ERROR INTERNO EN EL SERVIDOR: ", e)
            return Response({
                'success': False, 
                'message': f'Ocurrió un error al procesar el pago: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CreateCompanyAPI(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data
        name = request.data.get('name')
        comercial_entity_type = request.data.get('comercial_entity_type')
        store_type = request.data.get('store_type')
        selected_mall_id = request.data.get('selected_mall_id')
        selected_mall_floor = request.data.get('selected_mall_floor')
        company_category = request.data.get('company_category')
        lat = request.data.get('lat')
        lng = request.data.get('lng')
        address = request.data.get('address')
        print("DATA: ", data)
        try:
            store_type = StoreType(store_type)
        except ValueError:
            return Response({'error':"Tipo de tienda no reconocido."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            merchant_type = MerchantType(comercial_entity_type)
        except ValueError:
            return Response({'error':"Tipo de entidad comercial no reconocido."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            company_category = CompanyCategory.objects.get(id=int(company_category))
        except CompanyCategory.DoesNotExist:
            return Response({'error':"No existe la categoria de la tienda."}, status=status.HTTP_400_BAD_REQUEST)
        if Company.objects.only('name').filter(name=name).exists():
            return Response({'error':"Ya existe una tienda con ese nombre."}, status=status.HTTP_406_NOT_ACCEPTABLE)
        try:
            merchant_subscription = MerchantSubscription.objects.only('plan', 'merchant_type').select_related('plan').get(merchant=request.user)
        except MerchantSubscription.DoesNotExist:
            return Response({'error':"Usted no esta asociado a una suscripcion de comerciante.."}, status=status.HTTP_406_NOT_ACCEPTABLE)
        if selected_mall_id != None:
            # Flujo para tienda en centro comercial
            try:
                mall = Mall.objects.get(id=int(selected_mall_id))
            except Mall.DoesNotExist:
                return Response({'error':"No encontramos ese centro comercial."}, status=status.HTTP_400_BAD_REQUEST)
            if selected_mall_floor > mall.floors_quantity:
                return Response({'error':"El centro comercial no tiene esa cantidad de pisos."}, status=status.HTTP_400_BAD_REQUEST)
            try:
                with transaction.atomic():
                    if not merchant_subscription.plan.requires_business and merchant_subscription.merchant_type != merchant_type:
                        merchant_subscription.merchant_type = merchant_type
                        merchant_subscription.save()
                    company = Company.objects.create(
                        name=name,
                        owner=request.user,
                        category=company_category
                    )
                    company_store = CompanyStore.objects.create(
                        company=company,
                        name=name, # Por defecto la primera sucursal tiene el nombre de la empresa
                        store_type=store_type
                    )
                    StoreLocation.objects.create(
                        store=company_store,
                        mall=mall,
                        coordinates=mall.coordinates,
                        name=address
                    )
                    request.user.user_type = UserType.MERCHANT
                    request.user.save()
            except Exception as e:
                return Response({'error':f"{e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            # Flujo para tienda de otro tipo
            try:
                with transaction.atomic():
                    if not merchant_subscription.plan.requires_business and merchant_subscription.merchant_type != merchant_type:
                        merchant_subscription.merchant_type = merchant_type
                        merchant_subscription.save()
                    company = Company.objects.create(
                        name=name,
                        owner=request.user,
                        category=company_category
                    )
                    company_store = CompanyStore.objects.create(
                        company=company,
                        name=name, # Por defecto la primera sucursal tiene el nombre de la empresa
                        store_type=store_type
                    )
                    StoreLocation.objects.create(
                        store=company_store,
                        coordinates=Point(lat, lng),
                        name=address
                    )
                    request.user.user_type = UserType.MERCHANT
                    request.user.save()
            except Exception as e:
                print("Error: ", e)
                return Response({'error':f"{e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({"data":"Compañía registrada exitosamente."}, status=status.HTTP_201_CREATED)

class CheckCompanyNameAvailableAPI(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    permission_classes = [IsAuthenticated]

    def get(self, request, name:str):
        return Response(status=status.HTTP_202_ACCEPTED) if Company.objects.only('name').filter(name=name).exists()\
            == False else Response(status=status.HTTP_406_NOT_ACCEPTABLE)

class UpdateCompanyAPI(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = UpdateCompanySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            company = Company.objects.get(id=data['company_id'])
        except Company.DoesNotExist:
            return Response({'No se encontro la compania.'}, status=status.HTTP_404_NOT_FOUND)
        
        first_store = company.stores.all().order_by('-creation').first()
        if first_store == None:
            return Response({'No hay una tienda configurada'}, status=status.HTTP_409_CONFLICT)
        
        profile_img = data.get('profile_img')
        main_store_img = data.get('main_store_img')
        presentation_video = data.get('presentation_video')
        presentation_video_thumbnail = data.get('presentation_video_thumbnail')
        category_id = data.get('category_id')
        name = data.get('name')
        gamification_enabled = data.get('gamification_enabled')
        gamification_tokens_per_dollar = data.get('gamification_tokens_per_dollar')
        work_hours = data.get('work_hours')
        whatsapp_number = data.get('whatsapp_number')
        instagram_handle = data.get('instagram_handle')
        phone_number = data.get('phone_number')
        
        # Extracción de campos de ubicación
        store_type = data.get('store_type')
        is_mall = data.get('is_mall')
        lat = data.get('lat')
        lng = data.get('lng')
        address = data.get('address')
        selected_mall_id = data.get('selected_mall_id')
        selected_mall_floor = data.get('selected_mall_floor')
        print("DATA QUE LLEGA DEL REQUEST: ", data)
        company_has_changed = False
        store_has_changed = False

        with transaction.atomic():
            dtnow_str = timezone.localtime(timezone.now()).strftime('%d-%m-%Y_%H-%M-%S')
            
            # ===============================
            # 1. MANEJO DE ARCHIVOS (MULTIMEDIA)
            # ===============================
            if profile_img:
                # NUEVO: Limpiamos la imagen de perfil anterior
                if company.image:
                    try:
                        storage_manager.delete_file(company.image)
                    except Exception as e:
                        print(f"Error borrando img vieja: {e}")

                extension = profile_img.name.split('.')[-1]
                file_name = f"{company.id}_{dtnow_str}.{extension}"
                folder = "company_profile_pictures"
                relative_path = storage_manager.save_file(profile_img, folder, file_name)
                
                if relative_path:
                    company.image = relative_path
                    company_has_changed = True
                else:
                    raise Exception("Error al guardar la imagen de perfil en el storage.")
            
            if main_store_img:
                # NUEVO: Limpiamos la foto de tienda anterior
                if first_store.store_img_url:
                    try:
                        storage_manager.delete_file(first_store.store_img_url)
                    except Exception as e:
                        print(f"Error borrando img de tienda vieja: {e}")

                extension = main_store_img.name.split('.')[-1]
                file_name = f"{dtnow_str}.{extension}"
                folder = f"store_pictures/{first_store.id}"
                relative_path = storage_manager.save_file(main_store_img, folder, file_name)
                
                if relative_path:
                    first_store.store_img_url = relative_path
                    store_has_changed = True
                else:
                    raise Exception("Error al guardar la imagen de la tienda en el storage.")
            
            if presentation_video:
                # NUEVO: ¡Aquí matamos el video viejo!
                if company.presentation_video_url:
                    try:
                        storage_manager.delete_file(company.presentation_video_url)
                    except Exception as e:
                        # Hacemos un print/log pero NO detenemos la ejecución si falla
                        # (es mejor dejar un archivo huérfano que bloquearle la app al usuario)
                        print(f"Atención: No se pudo borrar el video anterior en {company.presentation_video_url}. Error: {e}")

                extension = presentation_video.name.split('.')[-1]
                file_name = f"{company.id}_video_{dtnow_str}.{extension}"
                folder = "company_presentation_videos"
                relative_path = storage_manager.save_file(presentation_video, folder, file_name)
                
                if relative_path:
                    company.presentation_video_url = relative_path
                    company_has_changed = True
                else:
                    raise Exception("Error al guardar el video en el storage.")
            
            if presentation_video_thumbnail:
                # NUEVO: Limpiamos la miniatura vieja
                if company.presentation_video_thumbnail:
                    try:
                        storage_manager.delete_file(company.presentation_video_thumbnail)
                    except Exception as e:
                        print(f"Error borrando thumbnail viejo: {e}")

                extension = presentation_video_thumbnail.name.split('.')[-1]
                file_name = f"{company.id}_thumbnail_{dtnow_str}.{extension}"
                folder = "company_presentation_videos"
                relative_path = storage_manager.save_file(presentation_video_thumbnail, folder, file_name)
                
                if relative_path:
                    company.presentation_video_thumbnail = relative_path
                    company_has_changed = True
                else:
                    raise Exception("Error al guardar el thumbnail del video en el storage.")

            
            # =========================
            # 2. ACTUALIZACIÓN DE DATOS (Empresa)
            # =========================
            if name:
                company.name = name
                company_has_changed = True
            
            if category_id:
                company.category_id = category_id
                company_has_changed = True
                
            if gamification_enabled is not None:
                company.gamification_enabled = gamification_enabled
                company_has_changed = True
                
            if gamification_tokens_per_dollar is not None:
                company.gamification_tokens_per_dollar = gamification_tokens_per_dollar
                company_has_changed = True

            if work_hours:
                company.main_work_hours = work_hours 
                company_has_changed = True
                
            # Métodos de contacto
            contact_data = [
                (whatsapp_number, ContactMethodType.WHATSAPP),
                (instagram_handle, ContactMethodType.INSTAGRAM),
                (phone_number, ContactMethodType.PHONE),
            ]
            for value, method_type in contact_data:
                if value is not None:
                    StoreContactMethod.objects.update_or_create(
                        store=first_store,
                        method_type=method_type,
                        defaults={'value': value}
                    )

            # =========================
            # 3. ACTUALIZACIÓN DE UBICACIÓN
            # =========================
            if store_type is not None:
                first_store.store_type = store_type
                store_has_changed = True

            if is_mall is not None:
                location, _ = StoreLocation.objects.get_or_create(store=first_store)
                
                if is_mall:
                    try:
                        mall = Mall.objects.get(id=selected_mall_id)
                        location.mall = mall
                        location.coordinates = mall.coordinates
                        location.name = address  # Nombre del C.C.
                        
                        # NUEVO: Guardamos el piso en su campo dedicado
                        if selected_mall_floor is not None:
                            location.mall_floor = selected_mall_floor
                        
                        location.save()
                    except Mall.DoesNotExist:
                        return Response({'error': "El centro comercial seleccionado no existe."}, status=status.HTTP_400_BAD_REQUEST)
                else:
                    # Si ya no está en un mall, limpiamos los campos
                    location.mall = None
                    location.mall_floor = None 
                    location.details = None
                    if lat is not None and lng is not None:
                        location.coordinates = Point(x=lng, y=lat)
                    if address:
                        location.name = address
                    location.save()

            # ===============================
            # 4. GUARDADO FINAL
            # ===============================
            if company_has_changed:
                company.save()
            
            if store_has_changed:
                first_store.save()
                
        return Response({'message': 'Compañía actualizada exitosamente'}, status=status.HTTP_200_OK)
    
class CreateStoreAPI(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CreateStoreSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False, 
                'error': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
            
        d = serializer.validated_data
        
        try:
            with transaction.atomic():
                # 1. Verificar propiedad de la compañía
                try:
                    company = Company.objects.get(id=d['company_id'], owner=request.user)
                except Company.DoesNotExist:
                    return Response({
                        'success': False, 
                        'error': "La compañía no existe o no tienes permisos."
                    }, status=status.HTTP_404_NOT_FOUND)

                # 2. Crear instancia de Sucursal (primero sin imagen para obtener el ID)
                store = CompanyStore.objects.create(
                    company=company,
                    name=d['name'],
                    work_hours=d['work_hours'],
                    store_type=d['store_type'],
                    is_active=True
                )

                # 3. Manejo de Imagen de la Sucursal (Storage)
                store_img = d.get('store_img')
                if store_img:
                    dtnow_str = timezone.localtime(timezone.now()).strftime('%d-%m-%Y_%H-%M-%S')
                    extension = store_img.name.split('.')[-1]
                    # Usamos el ID de la nueva sucursal para la carpeta
                    file_name = f"store_{store.id}_{dtnow_str}.{extension}"
                    folder = f"store_pictures/{store.id}"
                    
                    relative_path = storage_manager.save_file(store_img, folder, file_name)
                    
                    if relative_path:
                        store.store_img_url = relative_path
                        store.save()
                    else:
                        raise Exception("Error al guardar la imagen de la sucursal en el storage.")

                # 4. Crear Ubicación (StoreLocation)
                is_mall = d['is_mall']
                location = StoreLocation(store=store)
                
                if is_mall:
                    selected_mall_id = d.get('selected_mall_id')
                    try:
                        mall = Mall.objects.get(id=selected_mall_id)
                        location.mall = mall
                        location.coordinates = mall.coordinates
                        location.name = d['address'] # Usualmente el nombre del local o C.C.
                        location.mall_floor = d.get('selected_mall_floor')
                    except Mall.DoesNotExist:
                        raise Exception("El centro comercial seleccionado no existe.")
                else:
                    # Ubicación de calle
                    location.coordinates = Point(x=d['lng'], y=d['lat'])
                    location.name = d['address']
                
                location.save()

                # 5. Crear Métodos de Contacto Iniciales
                # Mapeo de campos del serializer a tipos de contacto
                contacts_to_create = [
                    (d.get('whatsapp_number'), ContactMethodType.WHATSAPP),
                    (d.get('instagram_handle'), ContactMethodType.INSTAGRAM),
                    (d.get('phone_number'), ContactMethodType.PHONE),
                ]

                for value, method_type in contacts_to_create:
                    if value: # Solo si el valor no es None o vacío
                        StoreContactMethod.objects.create(
                            store=store,
                            method_type=method_type,
                            value=value
                        )

                # 6. Respuesta Exitosa
                return Response({
                    'success': True, 
                    'message': 'Sucursal creada exitosamente.',
                    'data': store.get_json() 
                }, status=status.HTTP_201_CREATED)

        except Exception as e:
            # Si algo falla, el transaction.atomic() hará rollback de todo
            return Response({
                'success': False, 
                'error': f"Error interno: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
class UpdateStoreAPI(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    permission_classes = [IsAuthenticated]

    def delete(self, request, store_id=None):
        try:
            store = CompanyStore.objects.prefetch_related('company__owner').only('id', 'company').get(id=store_id)
            if request.user.id != store.company.owner_id:
                return Response({"Usted no tiene permisos para eliminar esta tienda."}, status=status.HTTP_406_NOT_ACCEPTABLE)
            store.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except CompanyStore.DoesNotExist:
            return Response({"La tienda que tratas de eliminar no existe."}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request, store_id=None):
        serializer = UpdateStoreSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        
        try:
            # Obtenemos la tienda directamente por su ID
            store = CompanyStore.objects.get(id=data['store_id'])
        except CompanyStore.DoesNotExist:
            return Response({'error': 'No se encontró la sucursal.'}, status=status.HTTP_404_NOT_FOUND)

        if store.company.owner != request.user:
            return Response({'error': 'No tienes permisos para editar esta sucursal.'}, status=status.HTTP_403_FORBIDDEN)
        
        store_img = data.get('store_img')
        name = data.get('name')
        is_active = data.get('is_active')
        work_hours = data.get('work_hours')
        
        whatsapp_number = data.get('whatsapp_number')
        instagram_handle = data.get('instagram_handle')
        phone_number = data.get('phone_number')
        
        # Extracción de campos de ubicación
        store_type = data.get('store_type')
        is_mall = data.get('is_mall')
        lat = data.get('lat')
        lng = data.get('lng')
        address = data.get('address')
        selected_mall_id = data.get('selected_mall_id')
        selected_mall_floor = data.get('selected_mall_floor')
        
        store_has_changed = False

        with transaction.atomic():
            dtnow_str = timezone.localtime(timezone.now()).strftime('%d-%m-%Y_%H-%M-%S')
            
            # ===============================
            # 1. MANEJO DE ARCHIVOS (FOTO SUCURSAL)
            # ===============================
            if store_img:
                # Limpiamos la foto de tienda anterior
                if store.store_img_url:
                    try:
                        storage_manager.delete_file(store.store_img_url)
                    except Exception as e:
                        print(f"Error borrando img de tienda vieja: {e}")

                extension = store_img.name.split('.')[-1]
                file_name = f"{dtnow_str}.{extension}"
                folder = f"store_pictures/{store.id}"
                relative_path = storage_manager.save_file(store_img, folder, file_name)
                
                if relative_path:
                    store.store_img_url = relative_path
                    store_has_changed = True
                else:
                    raise Exception("Error al guardar la imagen de la tienda en el storage.")
            
            # =========================
            # 2. ACTUALIZACIÓN DE DATOS
            # =========================
            if name:
                store.name = name
                store_has_changed = True
                
            if is_active is not None:
                store.is_active = is_active
                store_has_changed = True

            if work_hours:
                store.work_hours = work_hours
                store_has_changed = True
                
            # Métodos de contacto (específicos de esta tienda)
            contact_data = [
                (whatsapp_number, ContactMethodType.WHATSAPP),
                (instagram_handle, ContactMethodType.INSTAGRAM),
                (phone_number, ContactMethodType.PHONE),
            ]
            for value, method_type in contact_data:
                if value is not None: # Si mandan "" se actualizará a vacío, respetando tu frontend
                    StoreContactMethod.objects.update_or_create(
                        store=store,
                        method_type=method_type,
                        defaults={'value': value}
                    )

            # =========================
            # 3. ACTUALIZACIÓN DE UBICACIÓN
            # =========================
            if store_type is not None:
                store.store_type = store_type
                store_has_changed = True

            if is_mall is not None:
                location, _ = StoreLocation.objects.get_or_create(store=store)
                
                if is_mall:
                    try:
                        mall = Mall.objects.get(id=selected_mall_id)
                        location.mall = mall
                        location.coordinates = mall.coordinates
                        location.name = address  # Nombre del C.C.
                        
                        if selected_mall_floor is not None:
                            location.mall_floor = selected_mall_floor
                        
                        location.save()
                    except Mall.DoesNotExist:
                        return Response({'error': "El centro comercial seleccionado no existe."}, status=status.HTTP_400_BAD_REQUEST)
                else:
                    # Si ya no está en un mall, limpiamos los campos del CC
                    location.mall = None
                    location.mall_floor = None 
                    location.details = None
                    if lat is not None and lng is not None:
                        location.coordinates = Point(x=lng, y=lat)
                    if address:
                        location.name = address
                    location.save()

            # ===============================
            # 4. GUARDADO FINAL
            # ===============================
            if store_has_changed:
                store.save()
                
        return Response({'message': 'Sucursal actualizada exitosamente'}, status=status.HTTP_200_OK)

class DeleteStoreContactMethodAPI(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    permission_classes = [IsAuthenticated]

    def delete(self, request, method_id:int):
        try:
            contact_method = StoreContactMethod.objects.prefetch_related('store__company__owner').get(id=method_id)
            if not request.user.id == contact_method.store.company.owner.id:
                return Response({'Usted no es propietario de esta compania.'}, status=status.HTTP_406_NOT_ACCEPTABLE)
        except StoreContactMethod.DoesNotExist:
            return Response({'No existe ese metodo de contacto.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            contact_method.delete()
        except Exception as e:
            print(f"Error al eliminar el metodo de contacto: {e}")
            return Response({f"{e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({'text':"Exito"}, status=status.HTTP_204_NO_CONTENT)


#########################################################
#################### MANEJO DE MAPAS ####################
#########################################################

class GetStoresLocations(APIView):
    """
    Endpoint optimizado para cargar tiendas basadas en el área visible del mapa.
    """
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            # Obtención de parámetros del BBOX
            bbox_coords = (
                float(request.query_params.get('min_lng')),
                float(request.query_params.get('min_lat')),
                float(request.query_params.get('max_lng')),
                float(request.query_params.get('max_lat'))
            )
            bbox = Polygon.from_bbox(bbox_coords)
            bbox.srid = 4326
            stores = StoreLocation.objects.filter(
                coordinates__coveredby=bbox
            ).values(
                'id', 
                'coordinates', 
                'name', 
                'mall_id', 
                'store__store_type'
            )[:500] # MAXIMO 500 TIENDAS A LA VISTA EN EL MAPA
            features = [{
                "id": s['id'],
                "lat": s['coordinates'].y,
                "lng": s['coordinates'].x,
                "mall_id": s['mall_id'],
                "name": s['name'],
                "type": s['store__store_type']
            } for s in stores]
            return Response({'data': features}, status=status.HTTP_200_OK)
        except (ValueError, TypeError, AttributeError):
            return Response({'error': 'Parámetros inválidos'}, status=status.HTTP_400_BAD_REQUEST)

####################################################
###################### CACHE #######################
####################################################

class GetMallsCache(APIView):
    """
    Devuelve todos los centros comerciales registrados para mapeo local.
    """
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    permission_classes = [IsAuthenticated]

    def get(selmalls_dataf, request):
        malls = Mall.objects.all()
        malls_data = [m.get_json() for m in malls]
        data = {
            'malls':malls_data
        }
        return Response(data, status=status.HTTP_200_OK)

class CompanyCacheAPI(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'navigation'
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Devuelve los datos de la compania creada pot el usuario.
        """
        if MerchantSubscription.objects.filter(merchant=request.user, valid_until__gt=timezone.now()).exists():
            try:
                company = Company.objects.get(owner=request.user).get_json()
                stores = [company_store.get_json() for company_store in CompanyStore.objects.filter(company_id=company['id']).order_by('creation')]
                return Response({
                    'company':company,
                    'stores':stores
                }, status=status.HTTP_200_OK)
            except Company.DoesNotExist:
                return Response({'message':"No ha configurado su tienda."}, status=status.HTTP_404_NOT_FOUND)
        else:
            return Response({'message':"La suscripcion del comerciante expiro o no ha sido adquirida."}, status=status.HTTP_406_NOT_ACCEPTABLE)

class SubscriptionsCacheAPI(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'navigation'
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Devuelve todos los datos necesarios para la cache de de las subscripciones del usuario en la app.
        """
        user = User.objects.select_related(
            'subscription__plan',
            'atlas_plan',
        ).prefetch_related(
            'subscription__payments',
            'atlas_plan__payments',
            'wallet'
        ).get(id=request.user.id)
        merchant_subscription = user.subscription if hasattr(user, 'subscription') else None
        atlas_subscription = user.atlas_plan if hasattr(user, 'atlas_plan') else None
        subscriptions_payments = {
            'atlas':[],
            'merchant':[]
        }
        wallet_data = user.wallet.get_json()
        if atlas_subscription:
            subscriptions_payments['atlas'] = [atlas_payment.get_json() for atlas_payment in atlas_subscription.payments.all()]
        if merchant_subscription:
            subscriptions_payments['merchant'] = [merchant_payment.get_json() for merchant_payment in merchant_subscription.payments.all()]
        cache = {
            "merchant_subscription":merchant_subscription.get_json() if merchant_subscription else None,
            "atlas_subscription":atlas_subscription.get_json() if atlas_subscription else None,
            "subscriptions_payments":subscriptions_payments,
            "wallet":wallet_data
        }
        return Response(cache, status=200)



class UserCacheAPI(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'navigation'
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Devuelve todos los datos necesarios para la cache de usuario en la app.
        """
        user = User.objects.prefetch_related('locations', 'contact_methods').get(id=request.user.id)

        locations = [location.get_json() for location in user.locations.all()]
        contact_methods = [contact_method.get_json() for contact_method in user.contact_methods.all().order_by('method_type')]

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
            'contact_methods':contact_methods,
        }
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
        company_categories = [
            category.get_json() for category in CompanyCategory.objects.all()
        ]
        company_section_images = {
            "administrar_inventario": storage_manager.get_url('static/img/company_section_buttons/administrar_inventario.jpg', True),
            "administrar_suscripcion": storage_manager.get_url('static/img/company_section_buttons/administrar_suscripcion.jpg', True),
            "analiticas": storage_manager.get_url('static/img/company_section_buttons/analiticas.jpg', True),
            "empleados": storage_manager.get_url('static/img/company_section_buttons/empleados.jpg', True),
            "gamificacion": storage_manager.get_url('static/img/company_section_buttons/gamificacion.jpg', True),
            "mi_tienda": storage_manager.get_url('static/img/company_section_buttons/mi_tienda.jpg', True),
            "pedidos": storage_manager.get_url('static/img/company_section_buttons/pedidos.jpg', True),
            "preguntas_de_clientes": storage_manager.get_url('static/img/company_section_buttons/preguntas_de_clientes.jpg', True),
        }
        search_stores_at_zone = {
            # TODO: Implementar funcionalidad para obtener el mensaje de Atlas
            "atlas_message":"Detecto varias ofertas de ortalizas en el Kiosco de DonAmigo.",
            "image_background":storage_manager.get_url('static/img/tiendas_en_la_zona_background.jpg', True)
        }
        cache = {
            "announcements":announcements,
            "categories":categories,
            'company_categories':company_categories,
            'company_section_images':company_section_images,
            'search_stores_at_zone':search_stores_at_zone
        }
        return Response(cache, status=200)

####################################################
#################### VIEW SETS #####################
####################################################

class NotificationViewSet(viewsets.GenericViewSet, mixins.ListModelMixin):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # IMPORTANTE: Ordenamos para que las más nuevas salgan primero
        return Notification.objects.filter(user=self.request.user).order_by('-created_at')

    # -------------------------------------------------------------------------
    # ENDPOINT 1: Obtener TODAS las notificaciones agrupadas por sección (KISS)
    # -------------------------------------------------------------------------
    @action(detail=False, methods=['get'], url_path="all-grouped")
    def all_grouped(self, request):
        """
        Devuelve todas las notificaciones del usuario en un diccionario:
        { "0": [{...}, {...}], "1": [{...}] }
        Ideal para llenar el Provider en una sola petición al inicio.
        """
        notifications = self.get_queryset()
        
        grouped_data = {}
        for notif in notifications:
            sec_str = str(notif.section)
            if sec_str not in grouped_data:
                grouped_data[sec_str] = []
            
            # Usamos el get_json() que ya tienes implementado
            grouped_data[sec_str].append(notif.get_json())
            
        return Response(grouped_data, status=status.HTTP_200_OK)

    # -------------------------------------------------------------------------
    # ENDPOINT 2: Marcar UNA notificación como leída (Eliminar)
    # -------------------------------------------------------------------------
    @action(detail=True, methods=['post'], url_path="mark-as-read")
    def mark_as_read(self, request, pk=None):
        notification = self.get_object()
        notification.delete()
        return Response({"detail": "Notificación leida."}, status=status.HTTP_200_OK)

    # -------------------------------------------------------------------------
    # ENDPOINT 3: Limpiar TODA una sección
    # -------------------------------------------------------------------------
    @action(detail=False, methods=['post'], url_path="clear-section")
    def clear_section(self, request):
        section = request.data.get('section')
        if section is None:
            return Response({"detail": "Falta la sección."}, status=status.HTTP_400_BAD_REQUEST)
            
        deleted_count, _ = self.get_queryset().filter(section=section).delete()
        return Response({"deleted_count": deleted_count}, status=status.HTTP_200_OK)

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
        return User.objects.filter(id=self.request.user.id, is_active=True)

    def get_object(self):
        return self.request.user
    
    @action(detail=False, methods=['post'], url_path='upload-avatar')
    def upload_avatar(self, request):
        file_obj = request.FILES.get('photo')
        if not file_obj:
            return Response({"error": "No se envió ninguna imagen"}, status=400)
        user = request.user
        extension = file_obj.name.split('.')[-1]
        file_name = f"avatar_{user.id}_{timezone.localtime(timezone.now()).strftime('%d-%m-%Y_%H-%M-%S')}.{extension}"
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

################################################################
################### ENDPOINTS PARA TESTING #####################
################################################################

class SendNotificationToUser(APIView):
    """
    Prueba de envio de notificacion a traves de Firebase.
    """
    def post(self, request):
        NotificationManager._send_multicast(
            User.objects.get(id=request.data.get('user_id')),
            request.data.get('title'),
            request.data.get('message'),
            request.data.get('payload')
        )
        return Response(status=status.HTTP_200_OK)