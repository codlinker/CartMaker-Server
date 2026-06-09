import csv
import hashlib
import io
import json

from dateutil.relativedelta import relativedelta
from rest_framework import parsers
from rest_framework.views import APIView
from rest_framework.renderers import TemplateHTMLRenderer
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import *
from .models import *
from rest_framework.permissions import *
from .core import atlas, firebase_admin
import mimetypes
from rest_framework.pagination import CursorPagination
from .core.product_search_engine import ProductSearchEngine
from rest_framework import generics, status
from rest_framework.throttling import ScopedRateThrottle
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from django.conf import settings
from rest_framework.permissions import IsAuthenticated
import openpyxl
from rest_framework import viewsets, mixins
from rest_framework.decorators import action
import secrets
from django.contrib.auth.hashers import check_password
from .cos import storage_manager
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from datetime import datetime
import requests
from django.db import transaction
from .core import *
from django.utils import timezone
from .tasks import *
from django.contrib.gis.geos import Polygon, Point
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .utils import _parse_flexible_date
from asgiref.sync import sync_to_async, async_to_sync
from rest_framework.pagination import PageNumberPagination
from django.db.models.functions import Coalesce, Round
from django.db.models import Avg, Count, Sum, Q, Subquery, OuterRef, Prefetch
from django.contrib.gis.measure import D
import operator
from functools import reduce
from django.utils.dateparse import parse_datetime

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

class CompanyMainBranchViewSet(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Devuelve todas las sucursales de la compañía del usuario.
        Incluye la foto de la sucursal y la lista de productos únicos 
        publicados en ella, con el conteo de sus lotes (InventoryItems) activos.
        """
        print("LLEGO:")
        user = request.user
        
        # 1. Optimizamos la consulta con Prefetch
        # Buscamos solo los InventoryItems activos (paused=False, stock>0)
        # y traemos el Product asociado de una vez para evitar consultas N+1
        active_inventory_prefetch = Prefetch(
            'product_items',
            queryset=InventoryItem.objects.filter(
                paused=False, 
                stock__gt=0
            ).select_related('product'),
            to_attr='active_items'
        )

        # 2. Obtenemos las tiendas que le pertenecen a la compañía de este usuario
        stores = CompanyStore.objects.filter(
            company__owner=user
        ).prefetch_related(active_inventory_prefetch)

        data = []

        # 3. Procesamos y agrupamos los datos
        for store in stores:
            product_map = {}
            
            # Iteramos sobre los ítems de inventario activos que ya trajimos a memoria
            for item in store.active_items:
                prod_id = str(item.product.id)
                
                if prod_id not in product_map:
                    # Extraemos la primera imagen del array de imágenes del producto (si existe)
                    prod_img = None
                    if item.product.images and len(item.product.images) > 0:
                        prod_img = storage_manager.get_url(item.product.images[0])
                        
                    # Inicializamos la estructura del Producto
                    product_map[prod_id] = {
                        "id": prod_id,
                        "name": item.product.name,
                        "image": prod_img,
                        "active_inventory_count": 0
                    }
                
                # Sumamos 1 al contador de items (lotes) activos para este producto
                product_map[prod_id]["active_inventory_count"] += 1

            # Formateamos la foto de la sucursal
            store_image = None
            if store.store_img_url:
                store_image = storage_manager.get_url(store.store_img_url)

            # Agregamos la sucursal a la respuesta
            data.append({
                "id": str(store.id),
                "name": store.name,
                "image": store_image,
                "is_main_store": store.is_main_store,
                "products": list(product_map.values()) # Convertimos el dict agrupado a lista
            })

        return Response({'data': data}, status=status.HTTP_200_OK)

    def post(self, request):
        """
        Recibe el id de una sucursal y la establece como la principal (is_main_store=True),
        apagando el flag en todas las demás sucursales de la misma compañía.
        """
        store_id = request.data.get('store_id')
        
        if not store_id:
            return Response({'error': 'El parámetro store_id es requerido.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Buscamos la tienda y validamos estrictamente que la compañía dueña de 
            # esta tienda le pertenezca al usuario que hace la petición
            store = CompanyStore.objects.select_related('company').get(
                id=store_id, 
                company__owner=request.user
            )
            company = store.company

            # Transacción atómica para evitar inconsistencias si algo falla en el medio
            with transaction.atomic():
                # Apagamos todas las sucursales de esta compañía
                CompanyStore.objects.filter(company=company).update(is_main_store=False)
                
                # Encendemos solo la seleccionada
                store.is_main_store = True
                store.save(update_fields=['is_main_store'])

            return Response({
                'success': True, 
                'message': f'La sucursal "{store.name}" ha sido establecida como la principal.'
            }, status=status.HTTP_200_OK)

        except CompanyStore.DoesNotExist:
            return Response({
                'error': 'La sucursal no existe o no tienes permisos para modificarla.'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'error': f'Error interno: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GetCompanyProducts(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    permission_classes = [IsAuthenticated]

    def get(self, request, company_id=None):
        """
        Devuelve el catálogo maestro de productos paginado + las categorías de la empresa.
        """
        try:
            company = Company.objects.get(id=company_id)
            if company.owner.id != request.user.id:
                return Response({'error': 'Usted no es el propietario de la compania.'}, status=status.HTTP_406_NOT_ACCEPTABLE)
            
            # Categorías globales de la empresa (siempre se devuelven todas)
            company_categories = SubCategory.objects.filter(
                product__company=company
            ).distinct().values('id', 'name')
            
            # 💡 NUEVO: Recibimos el parámetro del frontend
            category_id = request.GET.get('category_id')
            page = request.GET.get('page', 1)
            
            # 💡 NUEVO: Filtramos el queryset si viene el category_id
            products_query = company.products.all()
            if category_id:
                products_query = products_query.filter(category_id=category_id)
                
            products_query = products_query.order_by('-creation')
            
            paginator = Paginator(products_query, 10)
            
            try:
                current_products = paginator.page(page)
            except PageNotAnInteger:
                current_products = paginator.page(1)
            except EmptyPage:
                current_products = []

            products = [product.get_json() for product in current_products]
            
            return Response({
                'products': products,
                'company_categories': list(company_categories),
                'pagination': {
                    'has_next': current_products.has_next() if current_products else False,
                    'current_page': int(page),
                    'total_pages': paginator.num_pages
                }
            }, status=status.HTTP_200_OK)
        except Company.DoesNotExist:
            return Response({'error': 'No existe la compania especificada.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': f'Error interno: {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GetCompanySubCategories(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    permission_classes = [IsAuthenticated]

    def get(self, request, company_id=None):
        """
        Devuelve todas las subcategorías únicas que tienen productos registrados en la compañía.
        """
        try:
            company = Company.objects.get(id=company_id)
            if company.owner.id != request.user.id:
                return Response({'error': 'No autorizado.'}, status=status.HTTP_406_NOT_ACCEPTABLE)
            
            # ORM Mágico: Filtra las subcategorías cruzándolas con los productos de esta empresa
            company_categories = SubCategory.objects.filter(
                product__company=company
            ).distinct().values('id', 'name')
            
            return Response({'categories': list(company_categories)}, status=status.HTTP_200_OK)

        except Company.DoesNotExist:
            return Response({'error': 'Compañía no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': f'Error interno: {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GetStoreInventoryItems(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    permission_classes = [IsAuthenticated]

    def get(self, request, store_id=None):
        try:
            store = CompanyStore.objects.get(id=store_id)
            if store.company.owner.id != request.user.id:
                return Response({'error': 'No tiene permisos para esta sucursal.'}, status=status.HTTP_406_NOT_ACCEPTABLE)

            # 💡 1. ORM MÁGICO: Categorías únicas del inventario de ESTA sucursal
            store_categories = SubCategory.objects.filter(
                product__inventory_items__store=store
            ).distinct().values('id', 'name')

            category_id = request.GET.get('category_id')
            page = request.GET.get('page', 1)
            
            # 💡 2. Filtramos el queryset de lotes si viene el parámetro
            items_query = InventoryItem.objects.filter(store=store)
            if category_id:
                items_query = items_query.filter(product__category_id=category_id)
                
            items_query = items_query.order_by('-creation')
            
            paginator = Paginator(items_query, 10)
            
            try:
                current_items = paginator.page(page)
            except PageNotAnInteger:
                current_items = paginator.page(1)
            except EmptyPage:
                current_items = []

            items = [item.get_json() for item in current_items]

            return Response({
                'items': items,
                'store_categories': list(store_categories), # 👈 3. Lo devolvemos
                'pagination': {
                    'has_next': current_items.has_next() if current_items else False,
                    'current_page': int(page),
                    'total_pages': paginator.num_pages
                }
            }, status=status.HTTP_200_OK)

        except CompanyStore.DoesNotExist:
            return Response({'error': 'No existe la sucursal especificada.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': f'Error interno: {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
        print(data)
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
                merchant_subscription = MerchantSubscription.objects.only('id', 'merchant', 'valid_until').get(merchant=request.user)
                print("MERCHANT SUBSCRIPTION VALID UNTIL: ", merchant_subscription.valid_until)
                print("NOW: ", timezone.now())
                if merchant_subscription.valid_until and merchant_subscription.valid_until > timezone.now():
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
                if merchant_plan.id != merchant_subscription.plan.id:
                    merchant_subscription.plan = merchant_plan
                    merchant_subscription.save()
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
                plan_id = request.data.get('plan_id')
                # 1. Obtener el plan y crear la subscripcion u obtenerla si ya existe
                merchant_plan = MerchantPlan.objects.only('price', 'name').get(id=plan_id)
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

                if merchant_subscription.plan.id != int(plan_id):
                    merchant_subscription.plan = merchant_plan
                    merchant_subscription.save()

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
                        store_type=store_type,
                        is_main_store=True
                    )
                    StoreLocation.objects.create(
                        store=company_store,
                        mall=mall,
                        mall_floor=selected_mall_floor,
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
                        name=name, 
                        store_type=store_type,
                        is_main_store=True 
                    )
                    StoreLocation.objects.create(
                        store=company_store,
                        coordinates=Point(x=lng, y=lat),
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
    """
    Este endpoint solo se utiliza en los casos en los que la compania no tiene plan que permita sucursales.
    """
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
        main_store = company.stores.filter(is_main_store=True).first()
        if main_store == None:
            first = company.stores.all().order_by('-creation').first()
            if first == None:
                return Response({'No hay una tienda configurada'}, status=status.HTTP_409_CONFLICT)
            first.is_main_store = True
            first.save()
            main_store = first
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
        work_days = data.get('work_days')
        
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
                if main_store.store_img_url:
                    try:
                        storage_manager.delete_file(main_store.store_img_url)
                    except Exception as e:
                        print(f"Error borrando img de tienda vieja: {e}")

                extension = main_store_img.name.split('.')[-1]
                file_name = f"{dtnow_str}.{extension}"
                folder = f"store_pictures/{main_store.id}"
                relative_path = storage_manager.save_file(main_store_img, folder, file_name)
                
                if relative_path:
                    main_store.store_img_url = relative_path
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

            if work_hours:
                company.main_work_hours = work_hours 
                company_has_changed = True
                
            # <-- 2. Agrega este bloque para work_days
            if work_days is not None: 
                # Si llega como string (por el FormData de Flutter), lo convertimos
                if isinstance(work_days, str):
                    import json
                    try:
                        company.main_work_days = json.loads(work_days)
                    except json.JSONDecodeError:
                        pass
                else:
                    company.main_work_days = work_days
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
                        store=main_store,
                        method_type=method_type,
                        defaults={'value': value}
                    )

            # =========================
            # 3. ACTUALIZACIÓN DE UBICACIÓN
            # =========================
            if store_type is not None:
                main_store.store_type = store_type
                store_has_changed = True

            if is_mall is not None:
                location, _ = StoreLocation.objects.get_or_create(store=main_store)
                
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
                main_store.save()
                
        return Response({'message': 'Compañía actualizada exitosamente'}, status=status.HTTP_200_OK)
    
class CompanyStoreViewSet(viewsets.ModelViewSet):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=['post'])
    def set_main_store(self, request, pk=None):
        """
        Setea la tienda actual como la principal y desmarca cualquier otra 
        tienda de la misma compañía.
        """
        store = self.get_object()
        company = store.company

        # 1. Validar que el usuario que hace la petición es el dueño real de la compañía
        if company.owner != request.user:
            return Response(
                {'error': 'No tienes permisos para modificar las sucursales de esta compañía.'}, 
                status=status.HTTP_403_FORBIDDEN
            )

        # 2. Transacción segura para hacer el "switch"
        try:
            with transaction.atomic():
                # A. Apagamos el flag en todas las tiendas de esta compañía
                CompanyStore.objects.filter(company=company).update(is_main_store=False)
                
                # B. Encendemos el flag SOLO en la tienda solicitada
                store.is_main_store = True
                store.save(update_fields=['is_main_store'])

            return Response({
                'success': True, 
                'message': f'La sucursal "{store.name}" ha sido establecida como la principal.'
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {'error': f'Error interno al actualizar: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
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
                
                work_days_raw = d.get('work_days')
                parsed_work_days = [0, 1, 2, 3, 4] # Valor por defecto si no envían nada
                
                if work_days_raw is not None:
                    if isinstance(work_days_raw, str):
                        import json
                        try:
                            parsed_work_days = json.loads(work_days_raw)
                        except json.JSONDecodeError:
                            pass
                    else:
                        parsed_work_days = work_days_raw

                # 2. Crear instancia de Sucursal (primero sin imagen para obtener el ID)
                store = CompanyStore.objects.create(
                    company=company,
                    name=d['name'],
                    work_hours=d['work_hours'],
                    work_days=parsed_work_days,
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
            store = CompanyStore.objects.prefetch_related('company__owner').only('id', 'company', 'is_main_store').get(id=store_id)
            
            if request.user.id != store.company.owner_id:
                return Response({"error": "Usted no tiene permisos para eliminar esta tienda."}, status=status.HTTP_406_NOT_ACCEPTABLE)
            
            is_main = store.is_main_store
            company = store.company
            
            with transaction.atomic():
                store.delete()
                if is_main:
                    oldest_remaining = CompanyStore.objects.filter(company=company).order_by('creation').first()
                    if oldest_remaining:
                        oldest_remaining.is_main_store = True
                        oldest_remaining.save(update_fields=['is_main_store'])
                        
            return Response(status=status.HTTP_204_NO_CONTENT)
            
        except CompanyStore.DoesNotExist:
            return Response({"error": "La tienda que tratas de eliminar no existe."}, status=status.HTTP_404_NOT_FOUND)

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
        work_days = data.get('work_days')
        
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

            if work_days is not None:
                if isinstance(work_days, str):
                    import json
                    try:
                        store.work_days = json.loads(work_days)
                    except json.JSONDecodeError:
                        pass
                else:
                    store.work_days = work_days
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

from pprint import pprint

class CartMakerMapViewSet(viewsets.ViewSet):
    """
    API exclusiva para el motor de renderizado del mapa principal de CartMaker.
    Utiliza Grid Snapping (Alineación de Cuadrícula) y filtrado In-Memory 
    para absorber el tráfico masivo de map panning sin golpear a PostGIS.
    """
    permission_classes = [IsAuthenticated]

    def _snap_to_grid(self, val: float, step: float = 0.04) -> float:
        """
        Redondea una coordenada a una cuadrícula virtual determinista.
        Un step de 0.04 grados equivale aproximadamente a bloques de 4.5 km.
        """
        return math.floor(val / step) * step

    @action(detail=False, methods=['get'])
    def get_locations(self, request):
        try:
            min_lng = float(request.query_params.get('min_lng'))
            min_lat = float(request.query_params.get('min_lat'))
            max_lng = float(request.query_params.get('max_lng'))
            max_lat = float(request.query_params.get('max_lat'))
        except (TypeError, ValueError):
            return Response({'error': 'Parámetros de coordenadas inválidos'}, status=status.HTTP_400_BAD_REQUEST)

        # Captura de Filtros
        filters_dict = {
            'c_cat': request.query_params.get('company_category_id'),
            'plat': request.query_params.get('is_platinum') == 'true',
            'p_cat': request.query_params.get('category_id'),
            'p_sub': request.query_params.get('subcategory_id'),
            'min_p': request.query_params.get('min_price'),
            'max_p': request.query_params.get('max_price'),
            'q': request.query_params.get('search', '').strip().lower()
        }
        
        has_filters = any(v for v in filters_dict.values() if v is not False and v != '')
        # Hasheamos los filtros de forma determinista para la llave de Redis
        filters_hash = hashlib.md5(json.dumps(filters_dict, sort_keys=True).encode()).hexdigest()

        # =========================================================================
        # 1. GENERACIÓN DE LLAVE DETERMINISTA (GRID SNAPPING)
        # =========================================================================
        if has_filters:
            # Si hay filtros, tu lógica original usaba un radio de 200km desde el centro.
            # Hacemos snapping del centroide para estabilizar el caché de la búsqueda.
            centroid_lng = self._snap_to_grid((min_lng + max_lng) / 2, step=0.1)
            centroid_lat = self._snap_to_grid((min_lat + max_lat) / 2, step=0.1)
            cache_key = f"map:radius:{centroid_lng:.2f}:{centroid_lat:.2f}:{filters_hash}"
        else:
            # Panning libre: Expandimos el BBox del usuario al bloque estático más cercano
            grid_min_lng = self._snap_to_grid(min_lng)
            grid_min_lat = self._snap_to_grid(min_lat)
            grid_max_lng = self._snap_to_grid(max_lng) + 0.04
            grid_max_lat = self._snap_to_grid(max_lat) + 0.04
            cache_key = f"map:grid:{grid_min_lng:.2f}:{grid_min_lat:.2f}:{grid_max_lng:.2f}:{grid_max_lat:.2f}:{filters_hash}"

        # Intentamos recuperar el bloque gigante de la RAM
        cached_features = cache.get(cache_key)

        # =========================================================================
        # 2. CACHE MISS: CONSULTA PESADA A POSTGIS
        # =========================================================================
        if not cached_features:
            bbox = Polygon.from_bbox((min_lng, min_lat, max_lng, max_lat))
            bbox.srid = 4326

            if has_filters:
                # Usamos el centroide real para la consulta (PostGIS es rápido en esto)
                queryset = StoreLocation.objects.select_related('store', 'mall').filter(
                    coordinates__distance_lte=(bbox.centroid, D(km=200)),
                    store__is_active=True
                )
            else:
                # Usamos la cuadrícula GIGANTE redondeada para almacenar datos de sobra
                grid_bbox = Polygon.from_bbox((grid_min_lng, grid_min_lat, grid_max_lng, grid_max_lat))
                grid_bbox.srid = 4326
                queryset = StoreLocation.objects.select_related('store', 'mall').filter(
                    coordinates__coveredby=grid_bbox,
                    store__is_active=True
                )

            # --- APLICACIÓN DE FILTROS ORIGINALES ---
            if filters_dict['c_cat']:
                queryset = queryset.filter(store__company__category_id=filters_dict['c_cat'])
            if filters_dict['plat']:
                queryset = queryset.filter(store__company__is_platinum=True)

            if filters_dict['p_cat'] or filters_dict['p_sub'] or filters_dict['min_p'] or filters_dict['max_p']:
                inventory_query = Q(store__product_items__paused=False, store__product_items__stock__gt=0)
                if filters_dict['p_sub']:
                    inventory_query &= Q(store__product_items__product__category_id=filters_dict['p_sub'])
                elif filters_dict['p_cat']:
                    inventory_query &= Q(store__product_items__product__category__parent_category_id=filters_dict['p_cat'])

                if filters_dict['min_p']:
                    min_val = float(filters_dict['min_p'])
                    inventory_query &= (
                        Q(store__product_items__custom_price__isnull=False, store__product_items__custom_price__gte=min_val) |
                        Q(store__product_items__custom_price__isnull=True, store__product_items__product__price__gte=min_val)
                    )
                if filters_dict['max_p']:
                    max_val = float(filters_dict['max_p'])
                    inventory_query &= (
                        Q(store__product_items__custom_price__isnull=False, store__product_items__custom_price__lte=max_val) |
                        Q(store__product_items__custom_price__isnull=True, store__product_items__product__price__lte=max_val)
                    )
                queryset = queryset.filter(inventory_query).distinct()

            if filters_dict['q']:
                search_terms = filters_dict['q'].split()
                word_queries = []
                for term in search_terms:
                    term_filter = (
                        Q(store__name__icontains=term) |
                        Q(store__company__name__icontains=term) |
                        Q(store__company__category__name__icontains=term) |
                        Q(store__product_items__product__name__icontains=term, store__product_items__paused=False, store__product_items__stock__gt=0) |
                        Q(store__product_items__product__category__name__icontains=term, store__product_items__paused=False, store__product_items__stock__gt=0) |
                        Q(store__product_items__product__category__parent_category__name__icontains=term, store__product_items__paused=False, store__product_items__stock__gt=0)
                    )
                    word_queries.append(term_filter)
                global_search_filter = reduce(operator.and_, word_queries)
                queryset = queryset.filter(global_search_filter).distinct()

            now = timezone.now()
            queryset = queryset.filter(
                Q(store__company__owner__subscription__valid_until__gte=now) |
                Q(store__company__owner__subscription__valid_until__isnull=True),
                Q(store__company__owner__subscription__plan__company_branches=True) |
                Q(store__company__owner__subscription__plan__company_branches=False, store__is_main_store=True)
            )

            locations = queryset.values(
                'store_id', 'coordinates', 'mall_id', 'mall_floor',
                'store__store_type', 'store__name', 'store__company__name', 
                'store__company__image', 'store__company__category__name', 
                'store__company__is_platinum', 'store__work_hours',
                'store__work_days', 'store__company__main_work_hours',
                'store__company__main_work_days'
            )[:600]

            cached_features = []
            for loc in locations:
                type_int = loc['store__store_type']
                type_name = StoreType(type_int).name if type_int is not None else "STREET"
                raw_image = loc['store__company__image']
                image_url = storage_manager.get_url(raw_image) if raw_image else "https://via.placeholder.com/150"

                work_hours = loc['store__work_hours'] or loc['store__company__main_work_hours']
                work_days = loc['store__work_days'] or loc['store__company__main_work_days'] or [0, 1, 2, 3, 4]

                cached_features.append({
                    "store_id": str(loc['store_id']),
                    "lat": loc['coordinates'].y,
                    "lng": loc['coordinates'].x,
                    "mall_id": loc['mall_id'],
                    "floor": loc['mall_floor'] or 1,
                    "store_type": type_name,
                    "company_name": loc['store__company__name'],
                    "branch_name": loc['store__name'],
                    "category": loc['store__company__category__name'] or "General",
                    "profile_pic": image_url,
                    "is_platinum": loc['store__company__is_platinum'],
                    "work_hours": work_hours, 
                    "work_days": work_days 
                })

            # Guardamos el bloque en Redis por 15 minutos
            cache.set(cache_key, cached_features, timeout=900)

        # =========================================================================
        # 3. MAP REDUCE IN-MEMORY (CACHE HIT)
        # =========================================================================
        # En memoria, recortamos matemáticamente los bordes del bloque gigante 
        # para enviar a Flutter ÚNICAMENTE lo que cabe en su pantalla milimétrica.
        exact_features = [
            f for f in cached_features 
            if min_lng <= f['lng'] <= max_lng and min_lat <= f['lat'] <= max_lat
        ]

        return Response({'data': exact_features}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def store_products(self, request):
        """
        Retorna el catálogo activo de una tienda específica filtrado por subcategoría y rango de precios,
        preservando estrictamente la estructura de datos extendida original mediante Split Caching.
        """
        try:
            store_id = request.query_params.get('store_id')
            if not store_id:
                return Response({'error': 'store_id es requerido'}, status=status.HTTP_400_BAD_REQUEST)

            subcategory_id = request.query_params.get('subcategory_id') or 'all'
            min_price = request.query_params.get('min_price') or 'none'
            max_price = request.query_params.get('max_price') or 'none'

            # 1. Definir llave única estructural para esta combinación exacta de filtros en la sucursal
            struct_cache_key = f"cartmaker:struct:map_products:{store_id}:{subcategory_id}:{min_price}:{max_price}"
            structural_data = cache.get(struct_cache_key)

            # =========================================================================
            # CACHE MISS ESTRUCTURAL: CONSULTA OPTIMIZADA A POSTGRESQL
            # =========================================================================
            if not structural_data:
                # Recuperamos tu QuerySet base original con todas sus relaciones cargadas
                queryset = InventoryItem.objects.select_related(
                    'product', 'product__category', 'offer', 'store', 'store__company'
                ).filter(
                    store_id=store_id,
                    paused=False,
                    stock__gt=0
                )
                
                # Regla de protección ortodoxa de planes
                queryset = queryset.filter(
                    Q(store__company__owner__subscription__plan__company_branches=True) |
                    Q(
                        store__company__owner__subscription__plan__company_branches=False,
                        store__is_main_store=True
                    )
                ).annotate(
                    avg_rating=Round(Coalesce(Avg('product__califications__rating'), 0.0), 1),
                    rating_count=Count('product__califications')
                )

                # Aplicar filtro por SubCategoría si viene en los parámetros
                if request.query_params.get('subcategory_id'):
                    queryset = queryset.filter(product__category_id=request.query_params.get('subcategory_id'))

                # Aplicar filtro de rango de precios original evaluando el costo real
                if request.query_params.get('min_price') or request.query_params.get('max_price'):
                    queryset = queryset.annotate(
                        actual_price=Coalesce('custom_price', 'product__price')
                    )
                    if request.query_params.get('min_price'):
                        queryset = queryset.filter(actual_price__gte=float(request.query_params.get('min_price')))
                    if request.query_params.get('max_price'):
                        queryset = queryset.filter(actual_price__lte=float(request.query_params.get('max_price')))

                # Evaluamos los primeros 50 ítems del catálogo de la tienda
                items = queryset[:50]
                
                # CRÍTICO: Mantenemos el método get_json() original del modelo con todos sus campos extendidos
                structural_data = [item.get_json() for item in items]
                
                # Almacenamos el esqueleto en RAM por 10 minutos
                cache.set(struct_cache_key, structural_data, timeout=600)

            # =========================================================================
            # REAL-TIME STITCHING: FUSIÓN DE VOLATILIDAD DIRECTA EN LA VISTA
            # =========================================================================
            if not structural_data:
                return Response({'data': []}, status=status.HTTP_200_OK)

            # Extraemos los IDs de los ítems del caché estructural
            item_ids = [item["id"] for item in structural_data]
            
            # Ejecutamos un MGET nativo por tubería mapeando las llaves volátiles generadas en signals.py
            volatile_keys_map = {f"cartmaker:volatile:item:{uid}": uid for uid in item_ids}
            cached_states = cache.get_many(volatile_keys_map.keys())

            final_realtime_data = []
            
            for item_data in structural_data:
                item_id = item_data["id"]
                v_key = f"cartmaker:volatile:item:{item_id}"
                state = cached_states.get(v_key)

                # Fallback atómico si la llave volátil expiró en Redis
                if not state:
                    state = {
                        "stock": int(item_data.get("stock", 0)),
                        "paused": bool(item_data.get("paused", False)),
                        "custom_price": item_data.get("custom_price")
                    }
                    cache.set(v_key, state, timeout=86400)

                # Validación de consistencia en vivo: si se agotó el stock o se pausó, se descarta al vuelo
                if state["paused"] or state["stock"] <= 0:
                    continue

                # Sincronizamos las propiedades mutables sobre el diccionario extendido original
                item_data["stock"] = state["stock"]
                item_data["paused"] = state["paused"]
                item_data["custom_price"] = state["custom_price"]
                
                final_realtime_data.append(item_data)

            # Retornamos la firma de respuesta idéntica a la original {'data': [...]}
            return Response({'data': final_realtime_data}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'error': f'Error interno: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GetStoresLocations(APIView):
    """
    Endpoint optimizado para cargar tiendas basadas en el área visible del mapa.
    """
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
            now = timezone.now()
            
            # Filtro combinado directo
            stores = StoreLocation.objects.filter(
                Q(store__company__owner__subscription__valid_until__gte=now) |
                Q(store__company__owner__subscription__valid_until__isnull=True),
                # 💡 REGLA ORTODOXA
                Q(store__company__owner__subscription__plan__company_branches=True) |
                Q(store__company__owner__subscription__plan__company_branches=False, store__is_main_store=True),
                coordinates__coveredby=bbox,
            ).values(
                'id', 
                'coordinates', 
                'name', 
                'mall_id', 
                'store__store_type'
            )[:500] 

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
    Caché Global: Se invalida solo si se agrega o edita un Mall.
    """
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cache_key = "cartmaker:global:malls"
        cached_data = cache.get(cache_key)

        if cached_data:
            return Response(cached_data, status=status.HTTP_200_OK)

        # Cache Miss
        malls = Mall.objects.all()
        malls_data = [m.get_json() for m in malls]
        data = {'malls': malls_data}
        
        cache.set(cache_key, data, timeout=86400) # 24 horas
        return Response(data, status=status.HTTP_200_OK)

class CompanyCacheAPI(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'navigation'
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Caché por Usuario: Datos de la compañía del comerciante.
        """
        cache_key = f"cartmaker:tenant:{request.user.id}:company"
        cached_data = cache.get(cache_key)

        if cached_data:
            # Si el caché guardó un error explícito (ej. sin suscripción), lo respetamos
            if "error_status" in cached_data:
                return Response({'message': cached_data["message"]}, status=cached_data["error_status"])
            return Response(cached_data, status=status.HTTP_200_OK)

        # Cache Miss
        if MerchantSubscription.objects.filter(merchant=request.user, valid_until__gt=timezone.now()).exists():
            try:
                company = Company.objects.get(owner=request.user).get_json()
                stores = [company_store.get_json() for company_store in CompanyStore.objects.filter(company_id=company['id']).order_by('creation')]
                
                data = {'company': company, 'stores': stores}
                cache.set(cache_key, data, timeout=3600) # 1 hora
                return Response(data, status=status.HTTP_200_OK)
            except Company.DoesNotExist:
                error_data = {"error_status": status.HTTP_404_NOT_FOUND, "message": "No ha configurado su tienda."}
                cache.set(cache_key, error_data, timeout=300) # Caché corto para errores
                return Response({'message': error_data["message"]}, status=error_data["error_status"])
        else:
            error_data = {"error_status": status.HTTP_406_NOT_ACCEPTABLE, "message": "La suscripcion del comerciante expiro o no ha sido adquirida."}
            cache.set(cache_key, error_data, timeout=300)
            return Response({'message': error_data["message"]}, status=error_data["error_status"])

class SubscriptionsCacheAPI(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'navigation'
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Caché por Usuario: Suscripciones, Wallet y Notificaciones.
        Altamente dinámico: Se invalida por señales al pagar o recibir saldo.
        """
        cache_key = f"cartmaker:tenant:{request.user.id}:subscriptions"
        cached_data = cache.get(cache_key)

        if cached_data:
            return Response(cached_data, status=status.HTTP_200_OK)

        # Cache Miss
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
        
        subscriptions_payments = {'atlas': [], 'merchant': []}
        
        pending_rejection_notif = Notification.objects.filter(
            user=request.user,
            category=NotificationCategory.PAYMENT_REJECTED,
            is_read=False
        ).first()

        wallet_data = user.wallet.get_json()

        if atlas_subscription:
            subscriptions_payments['atlas'] = [atlas_payment.get_json() for atlas_payment in atlas_subscription.payments.all()]
        if merchant_subscription:
            subscriptions_payments['merchant'] = [merchant_payment.get_json() for merchant_payment in merchant_subscription.payments.all()]
        
        data = {
            "merchant_subscription": merchant_subscription.get_json() if merchant_subscription else None,
            "atlas_subscription": atlas_subscription.get_json() if atlas_subscription else None,
            "subscriptions_payments": subscriptions_payments,
            "wallet": wallet_data,
            "pending_payment_notification_retry_id": pending_rejection_notif.id if pending_rejection_notif else None
        }
        
        cache.set(cache_key, data, timeout=3600) # 1 hora
        return Response(data, status=status.HTTP_200_OK)

class UserCacheAPI(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'navigation'
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Caché por Usuario: Perfil base.
        """
        cache_key = f"cartmaker:tenant:{request.user.id}:profile"
        cached_data = cache.get(cache_key)

        if cached_data:
            return Response(cached_data, status=status.HTTP_200_OK)

        # Cache Miss
        user = User.objects.prefetch_related('locations', 'contact_methods').get(id=request.user.id)
        locations = [location.get_json() for location in user.locations.all()]
        contact_methods = [contact_method.get_json() for contact_method in user.contact_methods.all().order_by('method_type')]

        data = {
            "user_id": user.id,
            "email": user.email,
            "creation": user.creation.strftime('%d/%m/%Y, %H:%M:%S'),
            "first_name": user.first_name,
            "last_name": user.last_name,
            "birth_date": user.birth_date if user.birth_date else "",
            "email_verified": user.email_verified,
            "user_type": user.user_type,
            "profile_picture": user.get_profile_picture_url(),
            "cedula_document_url": user.cedula_document if user.cedula_document else "",
            "cedula_verified": user.cedula_verified,
            "cedula_number": user.cedula_number if user.cedula_number else "",
            "gender": user.gender,
            "locations": locations,
            "is_external_account": user.is_external_account,
            'contact_methods': contact_methods,
        }
        
        cache.set(cache_key, data, timeout=86400) # 24 horas (Cambia rara vez)
        return Response(data, status=status.HTTP_200_OK)
    
class HomeCacheAPI(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'navigation'
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Caché Global: Anuncios y UI del Home.
        """
        cache_key = "cartmaker:global:home"
        cached_data = cache.get(cache_key)

        if cached_data:
            return Response(cached_data, status=status.HTTP_200_OK)

        # Cache Miss
        announcements = [announcement.get_json() for announcement in Announcement.objects.filter(active=True).order_by('-creation')]
        company_categories = [category.get_json() for category in CompanyCategory.objects.all()]
        
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
        
        data = {
            "announcements": announcements,
            'company_categories': company_categories,
            'company_section_images': company_section_images,
        }
        
        cache.set(cache_key, data, timeout=86400) # 24h
        return Response(data, status=status.HTTP_200_OK)

class SearchCacheAPI(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'navigation'
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Caché Global: UI del Buscador.
        """
        cache_key = "cartmaker:global:search"
        cached_data = cache.get(cache_key)

        if cached_data:
            return Response(cached_data, status=status.HTTP_200_OK)

        # Cache Miss
        categories = [category.get_json() for category in Category.objects.prefetch_related('subcategories').all()]
        search_stores_at_zone = {
            "atlas_message": "Detecto varias ofertas de hortalizas en el Kiosco de DonAmigo.",
            "image_background": storage_manager.get_url('static/img/tiendas_en_la_zona_background.jpg', True)
        }
        
        data = {
            "categories": categories,
            'search_stores_at_zone': search_stores_at_zone
        }
        
        cache.set(cache_key, data, timeout=86400) # 24h
        return Response(data, status=status.HTTP_200_OK)

####################################################
#################### VIEW SETS #####################
####################################################

class InteractionLogViewSet(viewsets.ViewSet):
    """
    API dedicada a registrar silenciosamente la telemetría del usuario en la App.
    Alimenta los modelos de Machine Learning y el Algoritmo de Recomendación.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'

    # ==========================================
    # HELPER: Procesador de Fechas
    # ==========================================
    def _parse_aware_datetime(self, datetime_raw):
        """
        Toma un string ISO, lo convierte a objeto datetime y se asegura
        de que sea 'aware' (consciente de la zona horaria del servidor)
        para evitar RuntimeWarnings de Django.
        """
        if not datetime_raw:
            return None
        
        parsed = parse_datetime(str(datetime_raw))
        if parsed and timezone.is_naive(parsed):
            return timezone.make_aware(parsed)
        return parsed

    # ==========================================
    # ENDPOINTS
    # ==========================================
    @action(detail=False, methods=['post'])
    def product_view(self, request):
        """
        Registra el Dwell Time (tiempo en pantalla) e interacciones con un producto.
        """
        data = request.data
        item_id = data.get('item_id')
        start_time_raw = data.get('start_time')

        if not item_id or not start_time_raw:
            return Response({'error': 'item_id y start_time son obligatorios.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            item = InventoryItem.objects.only('id').get(id=item_id)
            
            # Usamos el helper para sanitizar las fechas
            start_time = self._parse_aware_datetime(start_time_raw)
            end_time = self._parse_aware_datetime(data.get('end_time'))

            ProductViewLog.objects.create(
                client=request.user,
                inventory_item=item,
                added_to_cart=data.get('added_to_cart', False),
                bought=data.get('bought', False),
                start_time=start_time,
                end_time=end_time
            )
            return Response(status=status.HTTP_201_CREATED)
        except InventoryItem.DoesNotExist:
            return Response({'error': 'El producto no existe.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def store_view(self, request):
        """
        Registra el comportamiento del usuario dentro del perfil de una tienda.
        """
        data = request.data
        store_id = data.get('store_id')
        join_time_raw = data.get('join_time')

        if not store_id or not join_time_raw:
            return Response({'error': 'store_id y join_time son obligatorios.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            store = CompanyStore.objects.only('id').get(id=store_id)
            
            # Usamos el helper para sanitizar las fechas
            join_time = self._parse_aware_datetime(join_time_raw)
            exit_time = self._parse_aware_datetime(data.get('exit_time'))

            StoreViewLog.objects.create(
                client=request.user,
                join_time=join_time,
                exit_time=exit_time,
                location_watched=data.get('location_watched', False),
                presentation_video_watched=data.get('presentation_video_watched', False),
                stories_watched=data.get('stories_watched', False),
                products_watched=data.get('products_watched', False),
                tryed_to_contact=data.get('tryed_to_contact', False)
            )
            return Response(status=status.HTTP_201_CREATED)
        except CompanyStore.DoesNotExist:
            return Response({'error': 'La tienda no existe.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def navigation(self, request):
        """
        Registra el mapa de pantallas que el usuario visitó durante su sesión.
        """
        data = request.data
        navigation_record = data.get('navigation_record', {})
        login_time_raw = data.get('login_time')

        if not login_time_raw:
            return Response({'error': 'login_time es obligatorio.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Usamos el helper para sanitizar las fechas
            login_time = self._parse_aware_datetime(login_time_raw)
            logout_time = self._parse_aware_datetime(data.get('logout_time'))

            UserNavigationLog.objects.create(
                user=request.user,
                navigation_record=navigation_record,
                login_time=login_time,
                logout_time=logout_time
            )
            return Response(status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ============================================================================
# 1. MÓDULO DE PERFILES DE EMPRESA
# ============================================================================
class ClientCompanyViewSet(viewsets.ViewSet):
    """
    API dedicada a la obtención de perfiles públicos de tiendas y compañías
    desde la perspectiva del cliente final.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'navigation'

    @action(detail=False, methods=['get'])
    def profile(self, request):
        """
        Retorna la metadata pública de la tienda y su compañía (estadísticas, horarios, info).
        QueryParam: store_id o company_id
        """
        store_id = request.query_params.get('store_id')
        company_id = request.query_params.get('company_id')

        if not store_id and not company_id:
            return Response(
                {'error': 'Debe proveer store_id o company_id'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # 1. Determinar qué tienda consultar
            if company_id:
                store = CompanyStore.objects.select_related('company', 'company__category').filter(
                    Q(company__owner__subscription__plan__company_branches=True) |
                    Q(company__owner__subscription__plan__company_branches=False, is_main_store=True),
                    company_id=company_id, 
                    is_active=True
                ).order_by('-is_main_store', 'creation').first() # 💡 Priorizamos mostrar la Main Store
                
                if not store:
                    return Response({'error': 'La compañía no tiene tiendas activas o visibles bajo su plan actual.'}, status=status.HTTP_404_NOT_FOUND)
                company = store.company
            else:
                # Si piden una store_id directa, también debemos validar que sea legal mostrarla
                store = CompanyStore.objects.select_related('company', 'company__category').filter(
                    Q(company__owner__subscription__plan__company_branches=True) |
                    Q(company__owner__subscription__plan__company_branches=False, is_main_store=True),
                    id=store_id,
                    is_active=True
                ).first()

                if not store:
                    return Response({'error': 'La tienda solicitada no existe, fue eliminada o está inactiva por límite de plan.'}, status=status.HTTP_404_NOT_FOUND)
                company = store.company
            
            # =======================================================
            # 2. CÁLCULO DE MÉTRICAS GLOBALES DE LA COMPAÑÍA
            # =======================================================
            
            # A) Promedio de calificación
            rating_aggr = MerchantCalification.objects.filter(merchant=company).aggregate(Avg('rating'))
            avg_rating = round(rating_aggr['rating__avg'] or 0.0, 2)
            
            # B) Total de ventas de TODAS las sucursales
            # Asumiendo que 1 = Venta (Reemplaza con tu TransactionType.SALE)
            sales_aggr = InventoryItemTransaction.objects.filter(
                item__store__company=company,
                transaction_type=1 
            ).aggregate(Sum('units'))
            total_sales = sales_aggr['units__sum'] or 0
            formatted_sales = f"{total_sales // 1000}k" if total_sales >= 1000 else str(total_sales)

            # C) Categorías disponibles para esta compañía (Solo las que tienen productos activos en inventario)
            available_categories = SubCategory.objects.filter(
                product__inventory_items__store__company=company,
                product__inventory_items__paused=False
            ).distinct().values('id', 'name')

            merchant_subscription = MerchantSubscription.objects.get(merchant=company.owner)

            # =======================================================
            # 3. CONSTRUCCIÓN DE LA RESPUESTA
            # =======================================================
            company_metadata = company.get_json()
            company_metadata['avg_rating'] = avg_rating
            company_metadata['total_sales'] = formatted_sales
            company_metadata['total_sales_raw'] = total_sales
            company_metadata['merchant_type'] = merchant_subscription.get_merchant_type_display()
            
            store_metadata = store.get_json()

            return Response({
                'store_metadata': store_metadata,
                'company_metadata': company_metadata,
                'available_categories': list(available_categories)
            }, status=status.HTTP_200_OK)

        except CompanyStore.DoesNotExist:
            return Response({'error': 'La tienda solicitada no existe o fue eliminada.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': f'Error interno: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================================================
# 2. MÓDULO DE CONVERSACIONES Y PREGUNTAS
# ============================================================================
class ProductConversationPagination(PageNumberPagination):
    """
    Configuración de paginación para las preguntas y respuestas.
    Trae 15 por página por defecto para que el modal cargue rápido en la App.
    """
    page_size = 15
    page_size_query_param = 'page_size'
    max_page_size = 30


class ProductConversationViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'navigation'

    # ------------------------------------------------------------------------
    # ENDPOINT: GET /api/v1/product-conversation/item_questions/
    # ------------------------------------------------------------------------
    @action(detail=False, methods=['get'])
    def item_questions(self, request):
        """
        Retorna la lista de preguntas y respuestas de un lote de forma paginada.
        """
        item_id = request.query_params.get('item_id')

        if not item_id:
            return Response(
                {'error': 'Falta el parámetro obligatorio: item_id'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Query optimizado con select_related para evitar el N+1 al traer el cliente
        questions = InventoryItemQuestion.objects.filter(
            item_id=item_id
        ).select_related(
            'client', 
            'item__store__company' # 👈 Esto trae toda la info de la empresa en un solo viaje
        ).order_by('-question_creation')

        paginator = ProductConversationPagination()
        paginated_qs = paginator.paginate_queryset(questions, request)

        # Mapeamos usando tu get_json() maestro
        data = [q.get_json() for q in paginated_qs]

        return paginator.get_paginated_response(data)

    # ------------------------------------------------------------------------
    # ENDPOINT: POST /api/v1/product-conversation/ask_question/
    # ------------------------------------------------------------------------
    @action(detail=False, methods=['post'])
    def ask_question(self, request):
        """
        Crea una pregunta y devuelve el objeto formateado con get_json().
        """
        item_id = request.data.get('item_id')
        question_text = request.data.get('question_text')

        if not item_id or not question_text:
            return Response(
                {'error': 'Faltan parámetros obligatorios.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        clean_text = question_text.strip()
        if not clean_text:
            return Response(
                {'error': 'La pregunta no puede estar vacía.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        with transaction.atomic():
            try:
                item = InventoryItem.objects.prefetch_related('store__company__owner', 'product').get(id=item_id, paused=False)
            except InventoryItem.DoesNotExist:
                return Response(
                    {'error': 'El producto no existe o fue retirado.'}, 
                    status=status.HTTP_404_NOT_FOUND
                )

            question = InventoryItemQuestion.objects.create(
                client=request.user,
                item=item,
                question_text=clean_text
            )

            firebase_admin.NotificationManager.notify_new_question(
                merchant_user_id=item.store.company.owner.id,
                item_name=item.product.name,
                item_id=item.id
            )
            return Response({
                'message': 'Pregunta enviada con éxito.',
                'data': question.get_json() # 💡 Devolvemos exactamente la misma estructura
            }, status=status.HTTP_201_CREATED)
        return Response({
            'error':"No se pudo crear la pregunta."
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # ------------------------------------------------------------------------
    # ENDPOINT: POST /api/v1/product-conversation/answer_question/
    # ------------------------------------------------------------------------
    @action(detail=False, methods=['post'])
    def answer_question(self, request):
        """
        Permite al dueño del comercio responder una pregunta.
        """
        question_id = request.data.get('question_id')
        answer_text = request.data.get('answer_text')

        if not question_id or not answer_text:
            return Response(
                {'error': 'Faltan parámetros obligatorios.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        clean_text = answer_text.strip()
        if not clean_text:
            return Response(
                {'error': 'La respuesta no puede estar vacía.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        with transaction.atomic():
            try:
                # Traemos la pregunta con sus relaciones para verificar permisos eficientemente
                question = InventoryItemQuestion.objects.select_related(
                    'item__store__company__owner'
                ).get(id=question_id)
            except InventoryItemQuestion.DoesNotExist:
                return Response(
                    {'error': 'La pregunta no existe.'}, 
                    status=status.HTTP_404_NOT_FOUND
                )

            # 🔒 VERIFICACIÓN DE SEGURIDAD: ¿El usuario que dispara el endpoint es el dueño de la empresa?
            if question.item.store.company.owner != request.user:
                return Response(
                    {'error': 'No tienes permisos para responder en nombre de este comercio.'}, 
                    status=status.HTTP_403_FORBIDDEN
                )

            # 🔒 Evitar re-escribir respuestas si ya se respondió (opcional, pero buena práctica)
            if question.answer_text is not None:
                return Response(
                    {'error': 'Esta pregunta ya fue respondida.'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            question.answer_text = clean_text
            question.answer_creation = timezone.now()
            question.save()
            firebase_admin.NotificationManager.notify_new_answer(
                user_id=question.client.id,
                company_name=question.item.store.company.name,
                item_name=question.item.product.name,
                item_id=question.item.id
            )

            return Response({
                'success': True,
                'message': 'Respuesta enviada con éxito.',
                'data': question.get_json()
            }, status=status.HTTP_200_OK)
        return Response({
            'error':"No se pudo crear la respuesta."
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
class ProductSearchEngineViewSet(viewsets.ViewSet):
    """
    API integral para la distribución algorítmica de productos hacia la App.
    Interactúa con el ProductSearchEngine para retornar Feeds dinámicos cacheados
    respetando exactamente las firmas de respuesta originales requeridas por Flutter.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'navigation'
    
    # ------------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------------
    def _get_coordinates(self, request):
        try:
            lat = float(request.query_params.get('lat'))
            lng = float(request.query_params.get('lng'))
            return lat, lng
        except (TypeError, ValueError):
            return None, None

    def _get_sorting_params(self, request):
        sort_by = request.query_params.get('sort_by', 'relevance')
        price_order = request.query_params.get('price_order')
        return sort_by, price_order

    def _paginate_and_respond(self, data_list: list, request) -> Response:
        """
        Paginación O(1) en RAM que imita con precisión milimétrica la estructura 
        de CursorPagination de DRF (next, previous, results) para mantener la 
        compatibilidad con el controlador de scrolls infinitos en Flutter.
        """
        try:
            page = int(request.query_params.get('page', 1))
            page_size = int(request.query_params.get('page_size', 20))
        except ValueError:
            page = 1
            page_size = 20

        start = (page - 1) * page_size
        end = start + page_size
        
        paginated_data = data_list[start:end]
        has_next = end < len(data_list)
        has_previous = page > 1

        url = request.build_absolute_uri()
        import urllib.parse as urlparse
        
        def replace_page_param(base_url, page_num):
            url_parts = list(urlparse.urlparse(base_url))
            query = dict(urlparse.parse_qsl(url_parts[4]))
            query['page'] = page_num
            url_parts[4] = urlparse.urlencode(query)
            return urlparse.urlunparse(url_parts)

        next_url = replace_page_param(url, page + 1) if has_next else None
        prev_url = replace_page_param(url, page - 1) if has_previous else None

        return Response({
            'next': next_url,
            'previous': prev_url,
            'results': paginated_data
        }, status=status.HTTP_200_OK)

    # ------------------------------------------------------------------------
    # ENDPOINTS
    # ------------------------------------------------------------------------
    @action(detail=False, methods=['get'])
    def category(self, request):
        sub_category_id = request.query_params.get('sub_category_id')
        lat, lng = self._get_coordinates(request)
        sort_by, price_order = self._get_sorting_params(request)

        if not sub_category_id or lat is None or lng is None:
            return Response(
                {'error': 'Faltan parámetros obligatorios: sub_category_id, lat, lng'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        engine = ProductSearchEngine(lat, lng, user=request.user)
        data_list = engine.get_category_feed(
            sub_category_id=sub_category_id, 
            sort_by=sort_by, 
            price_order=price_order
        )

        return self._paginate_and_respond(data_list, request)

    @action(detail=False, methods=['get'])
    def store(self, request):
        store_id = request.query_params.get('store_id')
        company_id = request.query_params.get('company_id')
        category_id = request.query_params.get('category_id')
        lat, lng = self._get_coordinates(request)
        _, price_order = self._get_sorting_params(request)

        if (not store_id and not company_id) or lat is None or lng is None:
            return Response(
                {'error': 'Faltan parámetros obligatorios: store_id o company_id, lat, lng'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        engine = ProductSearchEngine(lat, lng, user=request.user)
        data_list = engine.get_store_feed(
            store_id=store_id, 
            company_id=company_id,
            category_id=category_id,
            price_order=price_order
        )
        
        return self._paginate_and_respond(data_list, request)

    @action(detail=False, methods=['get'])
    def offers(self, request):
        lat, lng = self._get_coordinates(request)
        sort_by, price_order = self._get_sorting_params(request)
        is_home_widget = request.query_params.get('home_widget', 'false').lower() == 'true'

        if lat is None or lng is None:
            return Response({'error': 'Faltan parámetros obligatorios: lat, lng'}, status=status.HTTP_400_BAD_REQUEST)

        engine = ProductSearchEngine(lat, lng, user=request.user)
        data_list = engine.get_offers_feed(sort_by=sort_by, price_order=price_order)

        # RESTRICCION DE FIRMA: Conserva el formato plano original para el widget horizontal
        if is_home_widget:
            top_10 = data_list[:10]
            return Response({'results': top_10}, status=status.HTTP_200_OK)
            
        return self._paginate_and_respond(data_list, request)
        
    @action(detail=False, methods=['get'])
    def item_details(self, request):
        item_id = request.query_params.get('item_id')

        if not item_id:
            return Response({'error': 'Falta el parámetro obligatorio: item_id'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            item = InventoryItem.objects.select_related(
                'product', 'store__company'
            ).prefetch_related('product__califications').annotate(
                avg_rating=Round(Coalesce(Avg('product__califications__rating'), 0.0), 1),
                rating_count=Count('product__califications')
            ).get(id=item_id, paused=False)
            
            data = item.get_json()
            return Response({'success': True, 'data': data}, status=status.HTTP_200_OK)
            
        except InventoryItem.DoesNotExist:
            return Response({'error': 'El producto no existe o fue retirado.'}, status=status.HTTP_404_NOT_FOUND)
            
    @action(detail=False, methods=['get'])
    def text_search(self, request):
        search_query = request.query_params.get('q', '')
        lat, lng = self._get_coordinates(request)
        sort_by, price_order = self._get_sorting_params(request)
        
        try:
            max_distance = float(request.query_params.get('max_distance', 10000))
        except ValueError:
            max_distance = 10000

        if not search_query or lat is None or lng is None:
            return Response({'error': 'Faltan parámetros obligatorios: q, lat, lng'}, status=status.HTTP_400_BAD_REQUEST)

        engine = ProductSearchEngine(lat, lng, user=request.user)
        data_list = engine.get_text_search_feed(
            search_query=search_query,
            sort_by=sort_by,
            price_order=price_order,
            max_distance_meters=max_distance
        )

        return self._paginate_and_respond(data_list, request)
    
    @action(detail=False, methods=['get'])
    def home_feed(self, request):
        lat, lng = self._get_coordinates(request)
        
        if lat is None or lng is None:
            return Response({'error': 'Faltan coordenadas'}, status=status.HTTP_400_BAD_REQUEST)

        engine = ProductSearchEngine(lat, lng, user=request.user)
        data_list = engine.get_home_feed()
        
        return self._paginate_and_respond(data_list, request)
        
    @action(detail=False, methods=['get'])
    def favorites(self, request):
        lat, lng = self._get_coordinates(request)
        sort_by, price_order = self._get_sorting_params(request)
        is_home_widget = request.query_params.get('home_widget', 'false').lower() == 'true'

        if lat is None or lng is None:
            return Response({'error': 'Faltan parámetros obligatorios: lat, lng'}, status=status.HTTP_400_BAD_REQUEST)

        engine = ProductSearchEngine(lat, lng, user=request.user)
        data_list = engine.get_favorites_feed(sort_by=sort_by, price_order=price_order)

        # RESTRICCION DE FIRMA: Conserva el envoltorio exacto original {'data': {'results': [...]}}
        if is_home_widget:
            top_10 = data_list[:10]
            return Response({'data': {'results': top_10}}, status=status.HTTP_200_OK)
            
        return self._paginate_and_respond(data_list, request)

    @action(detail=False, methods=['post'])
    def toggle_like(self, request):
        item_id = request.data.get('item_id')

        if not item_id:
            return Response({'error': 'Falta el parámetro obligatorio: item_id'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            item = InventoryItem.objects.get(id=item_id, paused=False)
        except InventoryItem.DoesNotExist:
            return Response({'error': 'El producto no existe o está inactivo.'}, status=status.HTTP_404_NOT_FOUND)

        like, created = ProductLike.objects.get_or_create(
            user=request.user,
            product=item
        )

        if not created:
            like.delete()
            return Response({'success': True, 'is_liked': False}, status=status.HTTP_200_OK)
        
        return Response({'success': True, 'is_liked': True}, status=status.HTTP_200_OK)

class AtlasViewSet(viewsets.ViewSet):
    """
    API integral para todas las interacciones con Atlas (IA de CartMaker).
    """
    permission_classes = [IsAuthenticated]

    # Al ser una vista síncrona de DRF, el ORM se usa de forma normal y limpia
    def _get_user_plan(self, user):
        try:
            return user.atlas_plan
        except AtlasPlusPlan.DoesNotExist:
            return None

    def _create_thread(self, plan):
        return AtlasThread.objects.create(plan=plan)

    # ------------------------------------------------------------------------
    # ENDPOINT: POST /api/atlas/scan_image/
    # ------------------------------------------------------------------------
    @action(detail=False, methods=['post'])
    def scan_image(self, request):
        image_file = request.FILES.get('image')
        if not image_file:
            return Response(
                {'error': 'No se proporcionó ninguna imagen. Asegúrate de enviarla como multipart/form-data con la clave "image".'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        image_bytes = image_file.read()
        mime_type = image_file.content_type
        
        atlas_manager = atlas.AtlasManager()
        
        # LA MAGIA: Ejecutamos el método asíncrono de Atlas dentro de nuestra vista síncrona.
        # Uvicorn mantendrá esto en un hilo secundario sin bloquear la app.
        resultado = async_to_sync(atlas_manager.analyze_image_for_products_async)(image_bytes, mime_type)
        
        if "error" in resultado and not resultado.get("products"):
            return Response(resultado, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
            
        return Response(resultado, status=status.HTTP_200_OK)
    
    # ------------------------------------------------------------------------
    # ENDPOINT: POST /api/v1/atlas/scan_image_multiple/
    # ------------------------------------------------------------------------
    @action(detail=False, methods=['post'])
    def scan_image_multiple(self, request):
        image_file = request.FILES.get('image')
        if not image_file:
            return Response(
                {'error': 'No se proporcionó ninguna imagen para el escaneo masivo.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        image_bytes = image_file.read()
        mime_type = image_file.content_type
        
        atlas_manager = atlas.AtlasManager()
        
        # Ejecutamos la versión plural
        resultado = async_to_sync(atlas_manager.analyze_image_for_multiple_products_async)(image_bytes, mime_type)
        
        if "error" in resultado and not resultado.get("products"):
            return Response(resultado, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
            
        return Response(resultado, status=status.HTTP_200_OK)

    # ------------------------------------------------------------------------
    # ENDPOINT: POST /api/v1/atlas/scan_excel_multiple/
    # ------------------------------------------------------------------------
    @action(detail=False, methods=['post'])
    def scan_excel_multiple(self, request):
        excel_file = request.FILES.get('file')
        if not excel_file:
            return Response({'error': 'No se proporcionó ningún archivo.'}, status=status.HTTP_400_BAD_REQUEST)
        
        filename = excel_file.name.lower()
        raw_rows = []

        try:
            # 1. Extraemos las celdas limpias usando Python a la velocidad de la luz
            if filename.endswith('.xlsx') or filename.endswith('.xls'):
                wb = openpyxl.load_workbook(io.BytesIO(excel_file.read()), data_only=True)
                sheet = wb.active
                headers = [str(cell.value) if cell.value is not None else f"Col_{idx}" for idx, cell in enumerate(sheet[1])]
                
                for row in sheet.iter_rows(min_row=2, values_only=True):
                    if any(cell is not None for cell in row):
                        row_dict = {headers[idx]: str(val) if val is not None else "" for idx, val in enumerate(row) if idx < len(headers)}
                        raw_rows.append(row_dict)
            else:
                # Flujo CSV estándar
                decoded_file = excel_file.read().decode('utf-8-sig').splitlines()
                reader = csv.DictReader(decoded_file)
                for row in reader:
                    raw_rows.append(dict(row))

            # 4. Control de seguridad: Si el archivo es ridículamente enorme, limitamos el lote inicial
            raw_rows = raw_rows[:50] 

        except Exception as e:
            print(f"[PARSING ERROR]: {e}")
            return Response({'error': 'Error al procesar la estructura del archivo.'}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        # 5. Ejecutamos Atlas pasándole el JSON nativo de Python
        atlas_manager = atlas.AtlasManager()
        resultado = async_to_sync(atlas_manager.analyze_processed_json_products_async)(raw_rows)
        
        if "error" in resultado and not resultado.get("products"):
            return Response(resultado, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
            
        return Response(resultado, status=status.HTTP_200_OK)

    # ------------------------------------------------------------------------
    # ENDPOINT: POST /api/atlas/thread/
    # ------------------------------------------------------------------------
    @action(detail=False, methods=['post'])
    def thread(self, request):
        plan = self._get_user_plan(request.user)
        if not plan:
            return Response({'error': 'Debes tener una suscripción activa a Atlas Plus.'}, status=status.HTTP_403_FORBIDDEN)
            
        new_thread = self._create_thread(plan)
        return Response({'thread_id': new_thread.id}, status=status.HTTP_201_CREATED)

    # ------------------------------------------------------------------------
    # ENDPOINT: POST /api/atlas/{id}/message/
    # ------------------------------------------------------------------------
    @action(detail=True, methods=['post'])
    def message(self, request, pk=None):
        text = request.data.get('text')
        if not text:
            return Response({'error': 'El texto del mensaje es obligatorio.'}, status=status.HTTP_400_BAD_REQUEST)
            
        plan = self._get_user_plan(request.user)
        if not plan:
            return Response({'error': 'Debes tener una suscripción activa a Atlas Plus.'}, status=status.HTTP_403_FORBIDDEN)
            
        atlas_manager = atlas.AtlasManager()
        
        # Llamamos al chat asíncrono con async_to_sync
        resultado = async_to_sync(atlas_manager.send_chat_message_async)(thread_id=pk, user_text=text)
        
        if not resultado.get('success'):
            return Response({'error': resultado.get('error')}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        return Response({
            'response': resultado['response'],
            'message_id': resultado['message_id']
        }, status=status.HTTP_200_OK)

class InventoryItemViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'

    def get_queryset(self):
        return InventoryItem.objects.filter(store__company__owner=self.request.user).order_by('-creation')

    def create(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                store_id = request.data.get('store_id')
                product_id = request.data.get('product_id')
                stock = request.data.get('stock', 0)
                expiration_date_raw = request.data.get('expiration_date')
                custom_price = request.data.get('custom_price')

                store = CompanyStore.objects.get(id=store_id, company__owner=request.user)
                product = Product.objects.get(id=product_id, company__owner=request.user)

                # Procesamos la fecha de caducidad usando nuestra función flexible
                exp_datetime = None
                if expiration_date_raw:
                    parsed_date = _parse_flexible_date(expiration_date_raw)
                    if parsed_date:
                        # Lo hacemos consciente de la zona horaria y lo seteamos al final del día
                        exp_datetime = timezone.make_aware(datetime.combine(parsed_date.date(), datetime.max.time()))

                item = InventoryItem.objects.create(
                    store=store,
                    product=product,
                    stock=int(stock),
                    expiration_date=exp_datetime,
                    custom_price=custom_price if custom_price else None
                )

                return Response({'success': True, 'data': item.get_json()}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def apply_offer(self, request, pk=None):
        item = self.get_object()
        percentage = request.data.get('percentage')
        valid_until_raw = request.data.get('valid_until')

        try:
            # Procesamos la fecha de la oferta
            parsed_date = _parse_flexible_date(valid_until_raw)
            if not parsed_date:
                return Response({'error': 'La fecha de validez es obligatoria'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Seteamos la expiración a las 23:59:59 de ese día con su Timezone
            valid_datetime = timezone.make_aware(datetime.combine(parsed_date.date(), datetime.max.time()))

            InventoryItemOffer.objects.update_or_create(
                product_item=item,
                defaults={'percentage': int(percentage), 'valid_until': valid_datetime}
            )
            
            item.refresh_from_db()
            return Response({'success': True, 'data': item.get_json()}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'navigation'
    
    # Fundamental para recibir tanto el JSON de datos como las imágenes físicas
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    def get_queryset(self):
        # Aseguramos que el usuario solo pueda interactuar con los productos de su compañía
        return Product.objects.filter(company__owner=self.request.user).order_by('-creation')
    
    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """
        Recibe un lote de productos y los guarda todos de golpe usando bulk_create.
        """
        company_id = request.data.get('company_id')
        try:
            company = Company.objects.get(id=company_id, owner=request.user)
        except Company.DoesNotExist:
            return Response({'error': 'Compañía no encontrada'}, status=status.HTTP_404_NOT_FOUND)

        raw_products = request.data.get('products_data')
        if not raw_products:
            return Response({'error': 'Faltan los datos de los productos.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            products_list = json.loads(raw_products)
        except json.JSONDecodeError:
            return Response({'error': 'El formato de products_data es inválido.'}, status=status.HTTP_400_BAD_REQUEST)

        created_products_json = []
        dtnow_str = timezone.localtime(timezone.now()).strftime('%d-%m-%Y_%H-%M-%S')

        try:
            with transaction.atomic():
                # 1. Preparar las instancias en memoria
                product_instances = []
                
                for prod_data in products_list:
                    category = SubCategory.objects.get(id=prod_data['category_id'])
                    discounts_data = prod_data.get('discounts_data', [])

                    # Instanciamos sin guardar en BD todavía
                    product = Product(
                        company=company,
                        name=prod_data['name'],
                        price=prod_data['price'],
                        description=prod_data['description'],
                        category=category,
                        discounts_by_tokens_active=prod_data.get('discounts_by_tokens_active', False),
                        discounts_data=discounts_data,
                        images=[]
                    )
                    product_instances.append(product)

                # 2. BULK CREATE REAL (Un solo viaje a la BD)
                # OJO: bulk_create en Postgres sí retorna los IDs generados si pasas los objetos.
                created_products = Product.objects.bulk_create(product_instances)

                # 3. Manejo de imágenes (Requiere los IDs que acabamos de generar)
                for prod_index, product in enumerate(created_products):
                    prod_data = products_list[prod_index]
                    image_order = prod_data.get('image_order', [])
                    final_images = []

                    for img_index, item in enumerate(image_order):
                        if item.startswith('new_image_') and item in request.FILES:
                            file = request.FILES[item]
                            extension = file.name.split('.')[-1]
                            file_name = f"prod_{product.id}_{img_index}_{dtnow_str}.{extension}"
                            folder = f"product_pictures/{product.id}"
                            
                            relative_path = storage_manager.save_file(file, folder, file_name)
                            if relative_path:
                                final_images.append(relative_path)
                            else:
                                raise Exception(f"Error guardando la imagen {file.name}.")
                        else:
                            final_images.append(item)

                    # 4. Actualizamos el array de imágenes (Bulk Update opcional, pero aquí update normal está bien)
                    product.images = final_images
                    product.save(update_fields=['images'])
                    
                    created_products_json.append(product.get_json())

            return Response({'success': True, 'data': created_products_json}, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response({'success': False, 'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
            
        d = serializer.validated_data
        
        try:
            with transaction.atomic():
                company_id = request.data.get('company_id')
                try:
                    company = Company.objects.get(id=company_id, owner=request.user)
                except Company.DoesNotExist:
                    return Response({'error': 'Compañía no encontrada'}, status=status.HTTP_404_NOT_FOUND)

                category = SubCategory.objects.get(id=d['category_id'])
                raw_discounts = request.data.get('discounts_data')
                discounts_data = json.loads(raw_discounts) if raw_discounts else []

                product = Product.objects.create(
                    company=company,
                    name=d['name'],
                    price=d['price'],
                    description=d['description'],
                    category=category,
                    discounts_by_tokens_active=d.get('discounts_by_tokens_active', False),
                    discounts_data=discounts_data,
                    images=[] # Lo llenamos en el siguiente paso
                )

                # ===============================
                # MANEJO DE IMÁGENES (Array de Strings)
                # ===============================
                raw_image_order = request.data.get('image_order', '[]')
                image_order = json.loads(raw_image_order)
                
                final_images = []
                dtnow_str = timezone.localtime(timezone.now()).strftime('%d-%m-%Y_%H-%M-%S')
                
                for index, item in enumerate(image_order):
                    # Si el string dice "new_image_X", buscamos el archivo y lo subimos
                    if item.startswith('new_image_') and item in request.FILES:
                        file = request.FILES[item]
                        extension = file.name.split('.')[-1]
                        file_name = f"prod_{product.id}_{index}_{dtnow_str}.{extension}"
                        folder = f"product_pictures/{product.id}"
                        
                        relative_path = storage_manager.save_file(file, folder, file_name)
                        if relative_path:
                            final_images.append(relative_path)
                        else:
                            raise Exception(f"Error guardando la imagen {file.name}.")
                    else:
                        # Si no es un archivo nuevo, asumimos que es una URL existente
                        final_images.append(item)
                product.images = final_images
                product.save()

                return Response({'success': True, 'data': product.get_json()}, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def update(self, request, *args, **kwargs):
        product = self.get_object()
        serializer = self.get_serializer(product, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response({'success': False, 'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
            
        d = serializer.validated_data

        try:
            with transaction.atomic():
                product.name = d.get('name', product.name)
                product.price = d.get('price', product.price)
                product.description = d.get('description', product.description)
                product.discounts_by_tokens_active = d.get('discounts_by_tokens_active', product.discounts_by_tokens_active)
                
                if 'category_id' in d:
                    product.category_id = d['category_id']

                raw_discounts = request.data.get('discounts_data')
                if raw_discounts is not None:
                    product.discounts_data = json.loads(raw_discounts)

                # ===============================
                # MANEJO DE IMÁGENES CORREGIDO
                # ===============================
                raw_image_order = request.data.get('image_order', '[]')
                image_order_from_frontend = json.loads(raw_image_order)
                
                processed_image_order = []

                # 1. TRADUCIR URLs ABSOLUTAS A RELATIVAS
                for item in image_order_from_frontend:
                    if item.startswith('new_image_'):
                        processed_image_order.append(item)
                    else:
                        # El item es una URL con 'http://...'. Buscamos a qué ruta relativa de la BD pertenece.
                        found = False
                        for old_relative_url in product.images:
                            if old_relative_url in item: # Magia aquí: buscamos "product_pictures/..." dentro de "http://..."
                                processed_image_order.append(old_relative_url)
                                found = True
                                break
                        
                        if not found:
                            # Fallback de seguridad por si la URL llega extraña
                            clean_path = item.split('/media/')[-1] if '/media/' in item else item
                            processed_image_order.append(clean_path)
                
                # 2. BORRAR IMÁGENES DESCARTADAS (Ahora sí comparamos manzanas con manzanas)
                for old_url in product.images:
                    if old_url not in processed_image_order:
                        try:
                            storage_manager.delete_file(old_url)
                        except Exception as e:
                            print(f"Error borrando img descartada: {e}")

                final_images = []
                dtnow_str = timezone.localtime(timezone.now()).strftime('%d-%m-%Y_%H-%M-%S')

                # 3. CONSTRUIR NUEVO ARRAY (Subiendo nuevas y manteniendo las viejas)
                for index, item in enumerate(processed_image_order):
                    if item.startswith('new_image_') and item in request.FILES:
                        file = request.FILES[item]
                        extension = file.name.split('.')[-1]
                        file_name = f"prod_{product.id}_{index}_{dtnow_str}.{extension}"
                        folder = f"product_pictures/{product.id}"
                        
                        relative_path = storage_manager.save_file(file, folder, file_name)
                        if relative_path:
                            final_images.append(relative_path)
                        else:
                            raise Exception(f"Error guardando nueva imagen.")
                    else:
                        # Si no es nueva, ya es una ruta relativa limpia gracias al paso 1
                        final_images.append(item)

                # Guardamos las rutas limpias en la base de datos
                product.images = final_images
                product.save()

            return Response({'success': True, 'data': product.get_json()}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def destroy(self, request, *args, **kwargs):
        product = self.get_object()
        try:
            # Primero borramos las imágenes del storage
            for img in product.images:
                try:
                    storage_manager.delete_file(img)
                except Exception as e:
                    print(f"Error borrando imagen al eliminar producto: {e}")
            
            # Luego eliminamos el registro de la DB
            product.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
    # ENDPOINT 2: Marcar UNA notificación como leída (Conservar en historial)
    # -------------------------------------------------------------------------
    @action(detail=True, methods=['post'], url_path="mark-as-read")
    def mark_as_read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save(update_fields=['is_read'])
        return Response({"detail": "Notificación marcada como leída.", "id": notification.id}, status=status.HTTP_200_OK)

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
    
    # -------------------------------------------------------------------------
    # ENDPOINT 4: Eliminar UNA notificación permanentemente
    # -------------------------------------------------------------------------
    @action(detail=True, methods=['delete'], url_path="delete")
    def delete_notification(self, request, pk=None):
        notification = self.get_object()
        notification.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

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

    @action(detail=True, methods=['patch'], url_path='select-location')
    def select_location(self, request, pk=None):
        try:
            location = self.get_object()
            ClientLocation.objects.filter(
                user=request.user, 
                is_default=True
            ).exclude(pk=location.pk).update(is_default=False)
            location.is_default = True
            location.save()
            serializer = self.get_serializer(location)
            return Response({
                "message": "Ubicación activada correctamente.",
                "data": serializer.data
            }, status=200)
        except Exception as e:
            return Response({"error": f"Error al seleccionar la ubicación: {e}"}, status=500)

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
        firebase_admin.NotificationManager._send_multicast(
            User.objects.get(id=request.data.get('user_id')),
            request.data.get('title'),
            request.data.get('message'),
            request.data.get('payload')
        )
        return Response(status=status.HTTP_200_OK)