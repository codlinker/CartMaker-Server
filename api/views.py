import csv
import hashlib
import io
import json
from django.core.exceptions import ObjectDoesNotExist
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
from .utils import parse_flexible_date
from asgiref.sync import sync_to_async, async_to_sync
from rest_framework.pagination import PageNumberPagination
from django.db.models.functions import Coalesce, Round
from django.db.models import Avg, Count, Sum, Q, Subquery, OuterRef, Prefetch, UUIDField
from django.contrib.gis.measure import D
import operator
from functools import reduce
from django.utils.dateparse import parse_datetime
from django.db.models.functions import Cast

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
        if request.user.is_superuser:
            return Response({
                'error':"No se permite acceso a cuentas administrativas."
            }, status=status.HTTP_406_NOT_ACCEPTABLE)
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
        
        if closest_user.is_superuser:
            return Response({
                'error':"No se permite acceso a cuentas administrativas."
            }, status=status.HTTP_406_NOT_ACCEPTABLE)

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
            
            # 💡 NUEVO: Atrapamos el parámetro de agotados
            out_of_stock = request.GET.get('out_of_stock') == 'true'

            # 💡 2. Filtramos el queryset de lotes si vienen los parámetros
            items_query = InventoryItem.objects.filter(store=store)
            
            if category_id:
                items_query = items_query.filter(product__category_id=category_id)
                
            # 💡 NUEVO: Aplicamos el filtro de stock en 0
            if out_of_stock:
                items_query = items_query.filter(stock=0)
                
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
    
class GetAtlasPlusPlanDetails(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Devuelve los datos de configuración, límites y costos en tiempo real 
        (USD y Bs BCV) para el plan Atlas Plus.
        """
        config = SystemConfig.objects.latest('creation')
        
        dollar_bcv_tax = 1.0
        bs_price = 0.0
        
        # Consumimos la tasa oficial en vivo al igual que con los comercios
        try:
            response = requests.get('https://ve.dolarapi.com/v1/estado')
            response.raise_for_status()
            data = response.json()
            api_available = data.get('estado') == 'Disponible' if data.get('estado') else False
            
            if api_available:
                response = requests.get('https://ve.dolarapi.com/v1/dolares/oficial')
                response.raise_for_status()
                data = response.json()
                dollar_bcv_tax = float(data.get('promedio', 1.0))
        except Exception as e:
            print(f"Error obteniendo el precio del dolar bcv para Atlas: {e}")

        price_usd = float(config.atlas_plus_price_usd)
        if dollar_bcv_tax > 0.0:
            bs_price = price_usd * dollar_bcv_tax

        payload = {
            'atlas_plus_price_usd': price_usd,
            'bs_price': bs_price,
            'dollar_bcv_tax': dollar_bcv_tax,
            'atlas_plus_daily_limit': config.atlas_plus_daily_limit,
            'atlas_free_daily_limit': config.atlas_free_daily_limit,
        }
        
        return Response({'data': payload}, status=status.HTTP_200_OK)
    
class UploadSubscriptionPayment(APIView):
    permission_classes = [IsAuthenticated]

    def _try_automatic_bank_validation(self, reference_number, amount_bs) -> bool:
        """
        [Capa Defensiva] Intenta conciliar el pago móvil/transferencia con la API del banco.
        Si la API del banco falla, cae, o no encuentra coincidencia exacta, devuelve False
        para que el flujo pase a validación manual por supervisores sin trancar la app.
        """
        try:
            # Ejemplo analítico de consumo de webhook/API bancaria
            # payload = {"ref": reference_number, "amount": float(amount_bs)}
            # r = requests.post("https://api.tu-banco.com/v1/verify", json=payload, timeout=4)
            # return r.json().get("matched") == True
            return False  # Simulamos falla/no disponible para forzar validación manual segura
        except Exception as e:
            print(f"⚠️ API Bancaria no disponible: {e}")
            return False

    def post(self, request):
        serializer = UploadSubscriptionPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        
        subscription_type = data['subscription_type']
        subscription_id = data['subscription_id'] # ID del MerchantPlan o del SystemConfig
        dollar_bcv_tax = Decimal(str(data['dollar_bcv_tax']))
        monto_enviado_bs = Decimal(str(data['amount_sended']))

        # Intentar conciliación bancaria automática primero
        bank_api_available = self._try_automatic_bank_validation(data['reference_number'], monto_enviado_bs)

        # =========================================================================
        # CASO 1: SUSCRIPCIONES ATLAS PLUS
        # =========================================================================
        if subscription_type == 1:
            atlas_plan, created = AtlasPlusPlan.objects.get_or_create(user=request.user)
            
            # Evitar duplicados en procesamiento pendiente
            if AtlasPlusPlanPayment.objects.filter(plan=atlas_plan, status=PaymentStatus.PENDING).exists():
                return Response({'error': "Ya tienes un pago pendiente por verificación para Atlas Plus."}, status=status.HTTP_406_NOT_ACCEPTABLE)

            file_obj = data['payment_proof']
            extension = file_obj.name.split('.')[-1]
            file_name = f"atlas_payment_{atlas_plan.id}_{timezone.now().strftime('%d-%m-%Y_%H-%M-%S')}.{extension}"
            relative_path = storage_manager.save_file(file_obj, "subscriptions/atlas_plus", file_name)

            payment = AtlasPlusPlanPayment.objects.create(
                plan=atlas_plan,
                reference_number=data['reference_number'],
                payment_proof_url=relative_path,
                amount=monto_enviado_bs,
                bcv_taxes_to_day=dollar_bcv_tax,
                status=PaymentStatus.APPROVED if bank_api_available else PaymentStatus.PENDING,
                verified_at=timezone.now() if bank_api_available else None
            )

            if bank_api_available:
                cache.delete(f"cartmaker:tenant:{request.user.id}:company")
                cache.delete(f"cartmaker:tenant:{request.user.id}:subscriptions")

            # Si la API del banco lo aprobó instantáneamente, se ejecutan las señales de activación de inmediato
            return Response({'payment_data': payment.get_json(), 'subscription_data': atlas_plan.get_json()}, status=status.HTTP_201_CREATED)

        # =========================================================================
        # CASO 2: SUSCRIPCIONES COMERCIANTE (Tu código existente integrado con la API del banco)
        # =========================================================================
        elif subscription_type == 2:
            try:
                merchant_plan = MerchantPlan.objects.get(id=subscription_id)
            except MerchantPlan.DoesNotExist:
                return Response({'error': 'Plan no encontrado.'}, status=status.HTTP_400_BAD_REQUEST)
                
            merchant_subscription, _ = MerchantSubscription.objects.get_or_create(
                merchant=request.user,
                defaults={
                    'merchant_type': MerchantType.BUSINESS if merchant_plan.requires_business else MerchantType.ENTREPRENEUR,
                    'plan': merchant_plan
                }
            )

            if MerchantPlanPayment.objects.filter(subscription=merchant_subscription, target_plan=merchant_plan, status=PaymentStatus.PENDING).exists():
                return Response({'error': "Ya tienes un pago pendiente por verificación por este plan."}, status=status.HTTP_406_NOT_ACCEPTABLE)

            file_obj = data['payment_proof']
            extension = file_obj.name.split('.')[-1]
            file_name = f"payment_proof_{merchant_subscription.id}_{timezone.now().strftime('%d-%m-%Y_%H-%M-%S')}.{extension}"
            relative_path = storage_manager.save_file(file_obj, f"subscriptions/merchant_plans/{merchant_plan.name}", file_name)

            payment = MerchantPlanPayment.objects.create(
                subscription=merchant_subscription,
                target_plan=merchant_plan,
                reference_number=data['reference_number'],
                payment_proof_url=relative_path,
                amount=monto_enviado_bs,
                bcv_taxes_to_day=dollar_bcv_tax,
                status=PaymentStatus.APPROVED if bank_api_available else PaymentStatus.PENDING,
                verified_at=timezone.now() if bank_api_available else None
            )
            return Response({'payment_data': payment.get_json(), 'subscription_data': merchant_subscription.get_json()}, status=status.HTTP_201_CREATED)


class FullPaySubscriptionWithWalletView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                print("REQUEST DATA: ", request.data)
                plan_id = request.data.get('plan_id')

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
                    return Response({'error':"No se pudo determinar la tasa del dolar."}, status=status.HTTP_423_LOCKED)
                
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

                plan_type = request.data.get('plan_type', 'merchant')
                wallet = UserWallet.objects.select_for_update().get(user=request.user)

                if plan_type == 'atlas':
                    config = SystemConfig.objects.latest('creation')
                    atlas_plan = AtlasPlusPlan.objects.select_for_update().get(user=request.user)
                    price_usd = config.atlas_plus_price_usd
                    
                    # Lógica de prorrateo para Atlas Plus si cambia/renueva antes de vencer
                    if atlas_plan.tier == AtlasSubscriptionTier.PREMIUM and atlas_plan.valid_until and atlas_plan.valid_until > timezone.now():
                        days_left = (atlas_plan.valid_until - timezone.now()).total_seconds() / 86400.0
                        daily_rate = float(price_usd) / 30.0
                        remanent_usd = Decimal(str(round(days_left * daily_rate, 2)))
                        if remanent_usd > 0:
                            wallet.regist_transaction(remanent_usd, 'atlas', "Reintegro por tiempo no consumido de Atlas Plus", 'add')

                    if wallet.balance < price_usd:
                        return Response({'success': False, 'message': 'Saldo insuficiente para Atlas Plus.'}, status=status.HTTP_400_BAD_REQUEST)

                    wallet.regist_transaction(price_usd, 'atlas', "Pago de suscripción Atlas Plus", 'substract')
                    
                    atlas_plan.tier = AtlasSubscriptionTier.PREMIUM
                    atlas_plan.valid_until = timezone.now() + relativedelta(months=1)
                    atlas_plan.save()
                    
                    # Creamos el registro físico del pago aprobado
                    atlas_payment = AtlasPlusPlanPayment.objects.create(
                        plan=atlas_plan,
                        reference_number=f"WALLET-ATLAS-{uuid.uuid4().hex[:6].upper()}",
                        amount=0,
                        bcv_taxes_to_day=dollar_bcv_tax,
                        status=PaymentStatus.APPROVED,
                        verified_at=timezone.now()
                    )

                    # Notificación local de interfaz
                    Notification.objects.create(
                        user=request.user,
                        section=NotificationSection.HOME,
                        title="¡Atlas Plus Activo!",
                        body="Tu billetera cubrió la activación. Disfruta de tus 75 interacciones diarias.",
                        category=NotificationCategory.PAYMENT_APPROVED,
                        metadata={'payment_id': str(atlas_payment.id)}
                    )
                    
                    return Response({
                        'success': True,
                        'message': '¡Atlas Plus activado usando tu saldo a favor!',
                        'data': {'new_balance': float(wallet.balance), 'valid_until': atlas_plan.valid_until.strftime("%d/%m/%Y, %H:%M:%S")}
                    }, status=status.HTTP_200_OK)

                # =======================================================
                # 💡 LÓGICA DE PRORRATEO (Split de saldos a favor)
                # =======================================================
                is_plan_change = merchant_subscription.plan.id != int(plan_id)
                current_plan_name = merchant_subscription.plan.name

                if is_plan_change and merchant_subscription.valid_until and merchant_subscription.valid_until > timezone.now():
                    days_left = (merchant_subscription.valid_until - timezone.now()).total_seconds() / 86400.0
                    daily_rate = float(merchant_subscription.plan.price) / 30.0
                    remanent_usd = Decimal(str(round(days_left * daily_rate, 2)))
                    
                    if remanent_usd > 0:
                        wallet.regist_transaction(
                            amount=remanent_usd,
                            sub_type='merchant',
                            description=f"Reintegro por tiempo no consumido del plan anterior ({current_plan_name})",
                            transaction='add'
                        )

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

                if is_plan_change:
                    merchant_subscription.plan = merchant_plan
                
                # 5. Activar la suscripción (Con Lógica de Acumulación)
                now = timezone.now()
                if merchant_subscription.valid_until and merchant_subscription.valid_until > now:
                    merchant_subscription.valid_until = merchant_subscription.valid_until + relativedelta(months=1)
                else:
                    merchant_subscription.valid_until = now + relativedelta(months=1)

                # Reseteamos las banderas para que el Cron Job vuelva a avisar en el futuro
                merchant_subscription.notified_5_days = False
                merchant_subscription.notified_1_day = False
                merchant_subscription.notified_hours = False
                
                merchant_subscription.save()

                cache.delete(f"cartmaker:tenant:{request.user.id}:company")
                cache.delete(f"cartmaker:tenant:{request.user.id}:subscriptions")

                # 6. Dejar un registro en el historial de pagos
                merchant_payment = MerchantPlanPayment.objects.create(
                    subscription=merchant_subscription,
                    target_plan=merchant_plan, # 💡 NUEVO: Dejamos el rastro del plan pagado
                    reference_number=f"WALLET-{uuid.uuid4().hex[:8].upper()}",
                    amount=0,
                    bcv_taxes_to_day=dollar_bcv_tax,
                    status=PaymentStatus.APPROVED,
                    verified_at=timezone.now()
                )

                # 7. Crear la notificacion
                if is_plan_change:
                    title = '¡Plan Actualizado!'
                    body = f'Has cambiado exitosamente al <b>{merchant_plan.name}</b>. El remanente de tu plan anterior fue reintegrado.'
                else:
                    title = '¡Pago Validado!'
                    body = f'Hemos aprobado el pago por la suscripción <b>{merchant_plan.name}</b>. Ya puedes registrar tus productos en CartMaker.'
                    
                Notification.objects.create(
                    user=request.user,
                    section=NotificationSection.HOME,
                    title=title,
                    body=body,
                    category=NotificationCategory.PAYMENT_APPROVED,
                    metadata={'payment_id':str(merchant_payment.id)}
                )

                # Mantengo tu cálculo de new_balance exacto (Aunque gracias al Prorrateo, la variable wallet.balance ya lo contempla)
                return Response({
                    'success': True,
                    'message': '¡Suscripción renovada exitosamente usando tu saldo a favor!',
                    'data': {
                        'new_balance': float(wallet.balance),
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
        cache_key = f"cartmaker:tenant:{request.user.id}:company"
        cached_data = cache.get(cache_key)

        if cached_data:
            if "error_status" in cached_data:
                return Response({'message': cached_data["message"]}, status=cached_data["error_status"])
            return Response(cached_data, status=status.HTTP_200_OK)
            
        try:
            company = Company.objects.get(owner=request.user).get_json()
        except Company.DoesNotExist:
            error_data = {"error_status": status.HTTP_404_NOT_FOUND, "message": "No ha configurado su tienda."}
            cache.set(cache_key, error_data, timeout=300)
            return Response({'message': error_data["message"]}, status=error_data["error_status"])
            
        if MerchantSubscription.objects.filter(merchant=request.user, valid_until__gt=timezone.now()).exists():
            stores = [company_store.get_json() for company_store in CompanyStore.objects.filter(company_id=company['id']).order_by('creation')]
            
            # ==========================================
            # 💡 NUEVO: EXTRAER IDs DE PREGUNTAS PENDIENTES
            # ==========================================
            item_ct = ContentType.objects.get(model='inventoryitem')
            video_ct = ContentType.objects.get(model='companyvideostory')

            items_pks = InventoryItem.objects.filter(store__company_id=company['id']).values_list('id', flat=True)
            videos_pks = CompanyVideoStory.objects.filter(company_id=company['id']).values_list('id', flat=True)

            pending_items = UniversalComment.objects.filter(content_type=item_ct).annotate(
                object_uuid=Cast('object_id', output_field=UUIDField())
            ).filter(object_uuid__in=items_pks).filter(Q(answer_text__isnull=True) | Q(answer_text__exact=''))

            pending_videos = UniversalComment.objects.filter(content_type=video_ct).annotate(
                object_uuid=Cast('object_id', output_field=UUIDField())
            ).filter(object_uuid__in=videos_pks).filter(Q(answer_text__isnull=True) | Q(answer_text__exact=''))

            pending_questions = list(pending_items.values_list('id', flat=True)) + list(pending_videos.values_list('id', flat=True))
            # ==========================================

            data = {'company': company, 'stores': stores, 'pending_questions': pending_questions}
            cache.set(cache_key, data, timeout=3600)
            return Response(data, status=status.HTTP_200_OK)
        else:
            error_data = {"error_status": status.HTTP_406_NOT_ACCEPTABLE, "message": "Suscripción expirada."}
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
        print("SUBSCRIPTIONS PAYMENTS ATLAS: ", subscriptions_payments['atlas'])
        data = {
            "merchant_subscription": merchant_subscription.get_json() if merchant_subscription else None,
            "atlas_subscription": atlas_subscription.get_json() if atlas_subscription else None,
            "subscriptions_payments": subscriptions_payments,
            "wallet": wallet_data,
            "pending_payment_notification_retry_id": pending_rejection_notif.id if pending_rejection_notif else None,
        }
        cache.set(cache_key, data, timeout=3600) # 1 hora
        return Response(data, status=status.HTTP_200_OK)
    
class SystemConfigCacheAPI(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'navigation'
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Caché de configuracion.
        """
        config = SystemConfig.objects.latest('creation')
        data = {
            'atlas_plus_price_usd': float(config.atlas_plus_price_usd),
            'atlas_plus_daily_limit': config.atlas_plus_daily_limit,
            'atlas_free_daily_limit': config.atlas_free_daily_limit,
            'platinum_min_rating_promedy_requirement': config.platinum_min_rating_promedy_requirement,
            'platinum_min_sells_per_month_requirement': config.platinum_min_sells_per_month_requirement
        }
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

class SupportTicketViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        tickets = SupportTicket.objects.filter(client=request.user).order_by('-creation')
        data = [ticket.get_json() for ticket in tickets]
        return Response({'data': data}, status=status.HTTP_200_OK)

    def create(self, request):
        if SupportTicket.objects.filter(client=request.user, closed=False).exists():
            return Response(
                {'error': 'Ya tienes un ticket de soporte en curso. Por favor, espera a que sea resuelto antes de abrir uno nuevo.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        topic_str = request.data.get('topic')
        title = request.data.get('title')
        description = request.data.get('description')

        if not topic_str or not title or not description:
            return Response({'error': 'Faltan campos obligatorios'}, status=status.HTTP_400_BAD_REQUEST)

        TOPIC_MAP = {
            'Problema con una Orden': SupportTicket.TicketTopic.ORDER_ISSUE,
            'Reclamo sobre Tienda': SupportTicket.TicketTopic.STORE_COMPLAINT,
            'Problema con mi Cuenta': SupportTicket.TicketTopic.ACCOUNT_ISSUE,
            'Otro': SupportTicket.TicketTopic.OTHER,
        }
        topic_int = TOPIC_MAP.get(topic_str, SupportTicket.TicketTopic.OTHER)

        # =================================================================
        # 🧠 ALGORITMO DE ASIGNACIÓN INTELIGENTE
        # =================================================================
        
        # 1. Preguntamos a Node.js qué IDs de usuarios tienen sockets abiertos
        online_users = []
        try:
            resp = requests.get(
                "http://127.0.0.1:3000/internal/online-users", 
                headers={'X-Microservice-Token': settings.SECRET_KEY}, # o env_manager.DJANGO_SECRET_KEY
                timeout=2
            )
            if resp.status_code == 200:
                online_users = resp.json().get('online_users', [])
        except Exception as e:
            print(f"Advertencia: No se pudo conectar a Node.js para ver agentes online: {e}")

        # 2. Buscamos a los SuperUsers. Filtramos primero a los que están online.
        all_agents = User.objects.filter(is_superuser=True)
        online_agents = all_agents.filter(id__in=online_users)

        # Si no hay nadie online, usamos a todos los agentes para que no quede huerfano
        agent_pool = online_agents if online_agents.exists() else all_agents

        # 3. Anotamos cuántos tickets ABIERTOS tiene asignados cada uno y sacamos al que tenga menos
        best_agent = agent_pool.annotate(
            active_tickets=Count('assigned_tickets', filter=Q(assigned_tickets__closed=False))
        ).order_by('active_tickets').first()

        # 4. Creamos el ticket ya asignado desde el nacimiento
        ticket = SupportTicket.objects.create(
            client=request.user,
            agent=best_agent,
            topic=topic_int,
            title=title,
            description=description
        )

        ticket_json = ticket.get_json()

        # 5. Si encontramos agente, disparamos las alertas en tiempo real mediante Node.js
        if best_agent:
            try:
                requests.post(
                    "http://127.0.0.1:3000/internal/emit-assignment",
                    json={
                        'ticket': ticket_json, 
                        'agent_id': str(best_agent.id),
                        'client_id': str(request.user.id) # 💡 NUEVO
                    },
                    headers={'X-Microservice-Token': settings.SECRET_KEY},
                    timeout=2
                )
            except Exception as e:
                pass

        return Response({'success': True, 'data': ticket_json}, status=status.HTTP_201_CREATED)

class AnalyticsViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'

    # =========================================================================
    # 1. IMPACTO FINANCIERO Y RETORNO DE INVERSIÓN (ROI)
    # =========================================================================
    @action(detail=False, methods=['get'])
    def roi_impact(self, request):
        company = Company.objects.filter(owner=request.user).first()
        if not company:
            return Response({'error': 'Compañía no encontrada.'}, status=status.HTTP_404_NOT_FOUND)

        time_horizon = timezone.now() - timedelta(days=30)

        # --- 1. EMBUDO BASE (Vistas analíticas agregadas) ---
        total_views = ProductViewLog.objects.filter(
            inventory_item__store__company=company,
            start_time__gte=time_horizon
        ).count()

        # --- 2. TRANSMUTACIÓN FINANCIERA DESDE DIARIO DE INVENTARIO ---
        # Buscamos exclusivamente los EGRESOS (OUTCOME) que representan las ventas en CartMaker
        sales_transactions = InventoryItemTransaction.objects.filter(
            item__store__company=company,
            transaction_type=TransactionType.OUTCOME,
            creation__gte=time_horizon
        ).select_related('item__product', 'item__store')

        total_revenue = 0.0
        total_items_sold = 0
        
        organic_sales_count = 0
        atlas_sales_count = 0
        video_sales_count = 0

        product_financials = {}

        for trans in sales_transactions:
            qty = abs(trans.units)
            total_items_sold += qty

            # Deducción del precio basada en la jerarquía del inventario (Custom vs Base)
            price = float(trans.item.custom_price if trans.item.custom_price else trans.item.product.price)
            subtotal = qty * price
            total_revenue += subtotal

            # --- ATRIBUCIÓN LOGÍSTICA-TELEMETRÍCA (Sin Tabla de Órdenes) ---
            # Correlacionamos el momento exacto del egreso con los logs de interacción del cliente
            is_attributed = False

            # A. Verificación de canal de Video Historias (Ventana de interacción de 2 horas previas)
            has_video_engagement = VideoEngagementLog.objects.filter(
                video__associated_item=trans.item,
                timestamp__lte=trans.creation,
                timestamp__gte=trans.creation - timedelta(hours=2)
            ).exists()

            if has_video_engagement:
                video_sales_count += qty
                is_attributed = True

            # B. Verificación de recomendación de Atlas IA (Ventana de influencia de 7 días previos)
            if not is_attributed:
                has_atlas_influence = ProductViewLog.objects.filter(
                    inventory_item=trans.item,
                    origin_source='atlas',
                    start_time__lte=trans.creation,
                    start_time__gte=trans.creation - timedelta(days=7)
                ).exists()

                if has_atlas_influence:
                    atlas_sales_count += qty
                    is_attributed = True

            # C. Fallback: Si no hay marcas telemétricas, la venta es puramente Orgánica
            if not is_attributed:
                organic_sales_count += qty

            # --- MASTRUZACIÓN DEL RANKING FINANCIERO ---
            pid = str(trans.item.product.id)
            if pid not in product_financials:
                product_financials[pid] = {
                    'id': pid,
                    'name': trans.item.product.name,
                    'image': storage_manager.get_url(trans.item.product.images[0]) if trans.item.product.images else None,
                    'units_sold': 0,
                    'revenue': 0.0
                }
            product_financials[pid]['units_sold'] += qty
            product_financials[pid]['revenue'] += subtotal

        # Tasa de conversión basada en flujos reales
        conversion_rate = round((total_items_sold / total_views * 100), 2) if total_views > 0 else 0.0
        top_products = sorted(product_financials.values(), key=lambda x: x['revenue'], reverse=True)[:5]

        # --- 3. CÁLCULO DE RENTABILIDAD SOBRE EL COSTO DEL PLAN ---
        plan_cost = 0.0
        try:
            sub = MerchantSubscription.objects.select_related('plan').get(merchant=request.user)
            plan_cost = float(sub.plan.price)
        except MerchantSubscription.DoesNotExist:
            pass

        net_profit = total_revenue - plan_cost
        roi_percentage = round((net_profit / plan_cost * 100), 1) if plan_cost > 0 else 0.0
        is_profitable = total_revenue >= plan_cost

        # --- 4. INSIGHTS CONTEXTUALES GENERADOS POR ATLAS ---
        insights = {'roi': None, 'origin': None, 'products': None}

        if is_profitable and plan_cost > 0:
            multiplier = round(total_revenue / plan_cost, 1)
            insights['roi'] = f"¡Excelente! Los ingresos deducidos este mes ya cubrieron tu plan {multiplier} veces. Tu negocio está en números verdes."
        elif plan_cost > 0 and total_revenue > 0:
            insights['roi'] = "Estás generando ingresos en inventario, pero aún no cubres el costo de tu suscripción. Intenta potenciar tus ofertas."

        if total_items_sold > 0:
            if atlas_sales_count >= organic_sales_count and atlas_sales_count >= video_sales_count:
                insights['origin'] = "Estoy conectando exitosamente tus productos con los clientes ideales mediante el chat. Mantén tus precios al día."
            elif video_sales_count >= organic_sales_count:
                insights['origin'] = "Tus Video Historias están liderando la conversión de existencias. Sigue explotando tu vitrina visual."
            else:
                insights['origin'] = "Tus clientes retiran stock principalmente por búsquedas orgánicas. Tienes buen posicionamiento local."

        if top_products:
            insights['products'] = f"'{top_products[0]['name']}' es el motor de tu negocio este mes. Vigila de cerca su inventario en tiempo real."

        return Response({
            'data': {
                'funnel': {
                    'views': total_views,
                    'sales': total_items_sold,
                    'conversion_rate': conversion_rate
                },
                'sales_distribution': {
                    'organic': organic_sales_count,
                    'atlas': atlas_sales_count,
                    'video': video_sales_count
                },
                'revenue_and_roi': {
                    'total_revenue_usd': round(total_revenue, 2),
                    'plan_cost_usd': plan_cost,
                    'roi_percentage': roi_percentage,
                    'is_profitable': is_profitable
                },
                'top_products': top_products,
                'insights': insights
            }
        }, status=status.HTTP_200_OK)

    # =========================================================================
    # 2. RENDIMIENTO DE CONTENIDO (Video Stories Metrics)
    # =========================================================================
    @action(detail=False, methods=['get'])
    def content_performance(self, request):
        company = Company.objects.filter(owner=request.user).first()
        if not company:
            return Response({'error': 'Compañía no encontrada.'}, status=status.HTTP_404_NOT_FOUND)

        time_horizon = timezone.now() - timedelta(days=30)
        logs = VideoEngagementLog.objects.filter(video__company=company, timestamp__gte=time_horizon)

        total_views = logs.count()
        completed_views = logs.filter(video_completed=True).count()
        abandoned_views = total_views - completed_views
        interacted = logs.filter(interacted_with_product=True).count()
        added_to_cart = logs.filter(added_to_cart_from_video=True).count()
        
        completion_rate = round((completed_views / total_views * 100), 1) if total_views > 0 else 0.0

        video_stats = {}
        total_video_revenue = 0.0
        total_watch_time_seconds_clean = 0.0

        company_videos = CompanyVideoStory.objects.filter(company=company)
        for v in company_videos:
            video_stats[str(v.id)] = {
                'id': str(v.id),
                'description': v.description or 'Video sin descripción',
                'thumbnail': storage_manager.get_url(v.thumbnail) if v.thumbnail else None,
                'duration_seconds': v.duration_seconds,
                'views': 0, 'completions': 0, 'watch_time_seconds': 0.0,
                'revenue': 0.0, 'units_sold': 0, 'interacted': 0
            }

        for log in logs:
            vid = str(log.video_id)
            if vid in video_stats:
                video_stats[vid]['views'] += 1
                
                real_duration = video_stats[vid]['duration_seconds']
                logged_time = log.watch_time_seconds
                
                if real_duration > 0 and logged_time > real_duration:
                    capped_time = real_duration
                else:
                    capped_time = logged_time
                    
                video_stats[vid]['watch_time_seconds'] += capped_time
                total_watch_time_seconds_clean += capped_time

                if log.video_completed: video_stats[vid]['completions'] += 1
                if log.interacted_with_product: video_stats[vid]['interacted'] += 1

        # --- AUDITORÍA DE FACTURACIÓN POR VIDEO USANDO DIARIO CONTABLE ---
        # Buscamos todos los egresos físicos vinculados a productos asociados a los videos
        for vid, stats in video_stats.items():
            video_obj = next((v for v in company_videos if str(v.id) == vid), None)
            if video_obj and video_obj.associated_item_id:
                # Rastreamos los egresos físicos que ocurrieron en la ventana temporal del video
                related_txs = InventoryItemTransaction.objects.filter(
                    item_id=video_obj.associated_item_id,
                    transaction_type=TransactionType.OUTCOME,
                    creation__gte=time_horizon
                )
                for tx in related_txs:
                    # Correlacionamos si existen logs de compra atribuidos por video
                    has_purchase_log = VideoEngagementLog.objects.filter(
                        video_id=vid,
                        bought_from_video=True,
                        timestamp__lte=tx.creation,
                        timestamp__gte=tx.creation - timedelta(hours=2)
                    ).exists()

                    if has_purchase_log:
                        units = abs(tx.units)
                        price = float(tx.item.custom_price if tx.item.custom_price else tx.item.product.price)
                        revenue_tx = units * price
                        
                        video_stats[vid]['units_sold'] += units
                        video_stats[vid]['revenue'] += revenue_tx
                        total_video_revenue += revenue_tx

        top_videos = sorted(
            [v for v in video_stats.values() if v['views'] > 0 or v['revenue'] > 0], 
            key=lambda x: (x['revenue'], x['views']), 
            reverse=True
        )[:5]

        # Generación de insights telemétricos
        insights = {'funnel': None, 'retention': None, 'top': None}
        if total_views > 0:
            click_rate = interacted / total_views
            if click_rate < 0.05:
                insights['funnel'] = "Tus videos captan atención, pero no derivan clics al producto. Ajusta tu llamado a la acción."
            elif (added_to_cart / interacted) >= 0.3:
                insights['funnel'] = "¡Conversión óptima desde el reproductor! El contenido multimedia es altamente persuasivo."
                
            if completion_rate < 20:
                insights['retention'] = "Los usuarios abandonan el clip rápido. Intenta condensar el mensaje clave en menos segundos."

        if top_videos and top_videos[0]['revenue'] > 0:
            top_desc = top_videos[0]['description']
            clean_desc = top_desc[:25] + "..." if len(top_desc) > 25 else top_desc
            insights['top'] = f"Tu video '{clean_desc}' lidera los ingresos de almacén. Replica su estilo visual."

        return Response({
            'data': {
                'global_metrics': {
                    'total_views': total_views,
                    'completed_views': completed_views,
                    'abandoned_views': abandoned_views,
                    'total_watch_time_minutes': round(total_watch_time_seconds_clean / 60, 1),
                    'completion_rate': completion_rate,
                    'total_video_revenue': round(total_video_revenue, 2),
                },
                'funnel': {
                    'views': total_views,
                    'interacted': interacted,
                    'added_to_cart': added_to_cart,
                },
                'top_videos': top_videos,
                'insights': insights
            }
        }, status=status.HTTP_200_OK)

    # =========================================================================
    # 3. MOTOR DE FIDELIZACIÓN (Gamificación y Retención Telemétrica)
    # =========================================================================
    @action(detail=False, methods=['get'])
    def loyalty_performance(self, request):
        company = Company.objects.filter(owner=request.user).first()
        if not company:
            return Response({'error': 'Compañía no encontrada.'}, status=status.HTTP_404_NOT_FOUND)

        time_horizon = timezone.now() - timedelta(days=30)
        
        # --- 1. AUDITORÍA DE TOKENS ---
        tokens_emitted = TokenWalletTransaction.objects.filter(
            token_wallet__company=company,
            transaction_type=TransactionType.INCOME,
            creation__gte=time_horizon
        ).aggregate(Sum('amount'))['amount__sum'] or 0

        tokens_redeemed = TokenWalletTransaction.objects.filter(
            token_wallet__company=company,
            transaction_type=TransactionType.OUTCOME,
            creation__gte=time_horizon
        ).aggregate(Sum('amount'))['amount__sum'] or 0

        # --- 2. RETENCIÓN MEDIANTE LOGS DE TRÁFICO COMPRADOR ---
        # Usamos los logs analíticos donde se marca 'bought=True' para identificar clientes recurrentes
        purchase_logs_30d = ProductViewLog.objects.filter(
            inventory_item__store__company=company,
            bought=True,
            start_time__gte=time_horizon
        ).values('client').annotate(purchase_count=Count('id'))

        all_time_purchases = ProductViewLog.objects.filter(
            inventory_item__store__company=company,
            bought=True
        ).values('client').annotate(total_purchases=Count('id'))
        
        history_map = {item['client']: item['total_purchases'] for item in all_time_purchases}
        
        new_customers = 0
        returning_customers = 0
        vip_data = {}

        for log in purchase_logs_30d:
            client_id = log['client']
            if history_map.get(client_id, 0) > 1:
                returning_customers += 1
            else:
                new_customers += 1

        # --- 3. EXTRACCIÓN VIP Y ANALÍTICA DE GAMIFICACIÓN ---
        # Buscamos transacciones contables del catálogo con reglas de gamificación activas
        gamified_items = InventoryItem.objects.filter(
            store__company=company,
            product__discounts_by_tokens_active=True
        ).select_related('product')

        gamified_products_stats = {}
        revenue_from_token_orders = 0.0

        for item in gamified_items:
            # Traemos todos los egresos reales de este producto gamificado
            item_sales = InventoryItemTransaction.objects.filter(
                item=item,
                transaction_type=TransactionType.OUTCOME,
                creation__gte=time_horizon
            )
            
            for tx in item_sales:
                qty = abs(tx.units)
                price = float(item.custom_price if item.custom_price else item.product.price)
                subtotal = qty * price
                
                # Si hubo tokens redimidos en la ventana de tiempo, asumimos impacto del programa
                if tokens_redeemed > 0:
                    revenue_from_token_orders += subtotal

                pid = str(item.product.id)
                if pid not in gamified_products_stats:
                    gamified_products_stats[pid] = {
                        'id': pid,
                        'name': item.product.name,
                        'image': storage_manager.get_url(item.product.images[0]) if item.product.images else None,
                        'units_sold': 0,
                        'revenue': 0.0,
                        'discount_investment': 0.0
                    }
                gamified_products_stats[pid]['units_sold'] += qty
                gamified_products_stats[pid]['revenue'] += subtotal

        # Construcción sintética del Top VIP basado en volumen analítico de compras
        top_vips_logs = ProductViewLog.objects.filter(
            inventory_item__store__company=company,
            bought=True,
            start_time__gte=time_horizon
        ).select_related('client').values(
            'client__id', 'client__first_name', 'client__last_name', 'client__profile_picture'
        ).annotate(total_purchases=Count('id'))[:5]

        top_vips = []
        for v in top_vips_logs:
            top_vips.append({
                'id': str(v['client__id']),
                'name': f"{v['client__first_name']} {v['client__last_name']}",
                'image': storage_manager.get_url(v['client__profile_picture']) if v['client__profile_picture'] else None,
                'orders': v['total_purchases'],
                'spent': 0.0  # Mantenemos firma del contrato de la API
            })

        top_gamified_products = sorted(gamified_products_stats.values(), key=lambda x: x['revenue'], reverse=True)[:10]

        # Insights contextuados
        insights = {'tokens': None, 'retention': None, 'general': None, 'products': None}
        if not company.gamification_enabled:
            insights['general'] = "No tienes la gamificación activada. Enciende los tokens para empezar a fidelizar clientes."
        else:
            if tokens_redeemed > 0:
                insights['tokens'] = "¡El sistema de fidelización funciona! Los clientes están retornando para liberar sus puntos."
            
            if returning_customers > new_customers:
                insights['retention'] = "¡Excelente retención telemétrica! Tienes una base de compradores altamente recurrentes."

        return Response({
            'data': {
                'gamification_enabled': company.gamification_enabled,
                'tokens': {
                    'emitted': tokens_emitted,
                    'redeemed': tokens_redeemed,
                    'revenue_from_token_orders': round(revenue_from_token_orders, 2)
                },
                'retention': {
                    'new_customers': new_customers,
                    'returning_customers': returning_customers
                },
                'top_vips': top_vips,
                'gamified_products': top_gamified_products,
                'insights': insights
            }
        }, status=status.HTTP_200_OK)

    # =========================================================================
    # 4. RADAR DE OPORTUNIDADES COMERCIALES (Geolocalización Analítica)
    # =========================================================================
    @action(detail=False, methods=['get'])
    def opportunities_radar(self, request):
        company = Company.objects.filter(owner=request.user).first()
        if not company:
            return Response({'error': 'Compañía no encontrada.'}, status=status.HTTP_404_NOT_FOUND)

        time_horizon = timezone.now() - timedelta(days=30)
        
        main_store = CompanyStore.objects.filter(company=company, is_main_store=True).select_related('location').first()
        if not main_store or not hasattr(main_store, 'location'):
            main_store = CompanyStore.objects.filter(company=company).select_related('location').first()
            
        if not main_store or not hasattr(main_store, 'location') or not main_store.location.coordinates:
            return Response({'error': 'Tu comercio no tiene una ubicación configurada para generar el radar.'}, status=status.HTTP_400_BAD_REQUEST)

        center_point = main_store.location.coordinates

        from django.contrib.gis.measure import D
        unmet_logs = UnmetDemandLog.objects.filter(
            creation__gte=time_horizon,
            coordinates__distance_lte=(center_point, D(km=15))
        )

        total_missed_searches = unmet_logs.count()
        top_terms = unmet_logs.values('search_term').annotate(count=Count('id')).order_by('-count')[:20]
        top_keywords = [{'term': item['search_term'].capitalize(), 'count': item['count']} for item in top_terms]

        features = []
        for log in unmet_logs:
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [log.coordinates.x, log.coordinates.y]
                },
                "properties": {
                    "weight": 1.0,
                    "term": log.search_term.capitalize() 
                }
            })
            
        heatmap_geojson = {
            "type": "FeatureCollection",
            "features": features
        }

        insights = {'radar': None, 'action': None}
        if total_missed_searches == 0:
            insights['radar'] = "Por ahora no detecto búsquedas fallidas relevantes cerca de tu ubicación."
        else:
            insights['radar'] = f"Detecté {total_missed_searches} clientes potenciales buscando productos sin stock en tu rango de entrega."
            if top_keywords:
                insights['action'] = f"La oportunidad de oro es '{top_keywords[0]['term']}'. Satisface esta demanda para dominar la zona."

        return Response({
            'data': {
                'center_lat': center_point.y,
                'center_lng': center_point.x,
                'total_missed_searches': total_missed_searches,
                'top_keywords': top_keywords,
                'heatmap_geojson': heatmap_geojson,
                'insights': insights
            }
        }, status=status.HTTP_200_OK)

    # =========================================================================
    # 5. GESTIÓN OPERATIVA DE SUCURSALES (Finanzas desde el Inventario)
    # =========================================================================
    @action(detail=False, methods=['get'])
    def operative_management(self, request):
        company = Company.objects.filter(owner=request.user).first()
        if not company:
            return Response({'error': 'Compañía no encontrada.'}, status=status.HTTP_404_NOT_FOUND)

        time_horizon = timezone.now() - timedelta(days=30)
        
        # Traemos todas las transacciones de venta (OUTCOME) del mes
        sales_txs = InventoryItemTransaction.objects.filter(
            item__store__company=company,
            transaction_type=TransactionType.OUTCOME,
            creation__gte=time_horizon
        ).select_related('item__store')

        total_revenue = 0.0
        # Consideramos cada transacción contable de venta como una entrada en caja
        total_sales_records = sales_txs.count()

        branches_data = {}
        stores = CompanyStore.objects.filter(company=company)
        
        for store in stores:
            total_items = InventoryItem.objects.filter(store=store).count()
            low_stock_items = InventoryItem.objects.filter(store=store, stock__lte=5).count()
            
            health_status = "Estable"
            if total_items > 0:
                low_pct = low_stock_items / total_items
                if low_pct > 0.5:
                    health_status = "Bajo"
                elif low_pct > 0.2:
                    health_status = "Medio"

            store_image = storage_manager.get_url(store.store_img_url) if store.store_img_url else ""
            
            branches_data[store.id] = {
                'id': str(store.id),
                'name': store.name,
                'orders': 0,
                'image': store_image,
                'revenue': 0.0,
                'inventory_health': health_status
            }

        # Procesamos los ingresos reales calculados desde el diario de stock
        for tx in sales_txs:
            qty = abs(tx.units)
            price = float(tx.item.custom_price if tx.item.custom_price else tx.item.product.price)
            subtotal = qty * price
            
            total_revenue += subtotal
            
            store_id = tx.item.store.id
            if store_id in branches_data:
                branches_data[store_id]['orders'] += 1
                branches_data[store_id]['revenue'] += subtotal

        average_ticket = round(total_revenue / total_sales_records, 2) if total_sales_records > 0 else 0.0
        sorted_branches = sorted(branches_data.values(), key=lambda x: x['revenue'], reverse=True)

        insights = {'accounting': None, 'branches': None}
        if total_sales_records > 0:
            if average_ticket > 20:
                insights['accounting'] = f"Tu ticket promedio de ${average_ticket} basado en flujo de stock es muy sólido."
            else:
                insights['accounting'] = f"Tu ticket promedio es de ${average_ticket}. Incentiva compras de mayor volumen."
                
            if len(sorted_branches) > 1 and sorted_branches[0]['revenue'] > 0:
                insights['branches'] = f"La sede '{sorted_branches[0]['name']}' lidera la facturación física."

        return Response({
            'data': {
                'accounting': {
                    'total_revenue': round(total_revenue, 2),
                    'total_orders': total_sales_records,
                    'average_ticket': average_ticket
                },
                'branches': sorted_branches,
                'insights': insights
            }
        }, status=status.HTTP_200_OK)

    # =========================================================================
    # 6. LIBRO MAYOR DETALLADO (Soporta VENTA, INGRESO STOCK y CREACION)
    # =========================================================================
    @action(detail=False, methods=['get'])
    def detailed_ledger(self, request):
        company = Company.objects.filter(owner=request.user).first()
        if not company:
            return Response({'error': 'Compañía no encontrada.'}, status=status.HTTP_404_NOT_FOUND)

        store_id = request.query_params.get('store_id', None)
        page = int(request.query_params.get('page', 1))
        is_export = request.query_params.get('export', 'false').lower() == 'true'
        limit = 10
        
        time_horizon = timezone.now() - timedelta(days=30)

        # Query limpia unificada: Traemos todo ordenado por fecha de creación decreciente
        queryset = InventoryItemTransaction.objects.filter(
            item__store__company=company,
            creation__gte=time_horizon
        ).select_related(
            'item__product', 
            'item__store'
        ).order_by('-creation')

        if store_id and store_id != 'all':
            queryset = queryset.filter(item__store_id=store_id)

        total_items = queryset.count()
        total_pages = (total_items + limit - 1) // limit if total_items > 0 else 1

        if not is_export:
            start_idx = (page - 1) * limit
            end_idx = start_idx + limit
            transactions = queryset[start_idx:end_idx]
        else:
            transactions = queryset

        ledger = []
        for trans in transactions:
            qty_val = abs(trans.units)
            
            # CASO A: Egresos (Ventas)
            if trans.transaction_type == TransactionType.OUTCOME:
                price = float(trans.item.custom_price if trans.item.custom_price else trans.item.product.price)
                gross = round(price * qty_val, 2)
                
                ledger.append({
                    'date': trans.creation,
                    'type': 'VENTA',
                    'store': trans.item.store.name,
                    'product': trans.item.product.name,
                    'qty': f"-{qty_val}",
                    'gross_amount': gross,
                    'discount_amount': 0.0,
                    'net_revenue': gross,
                    'origin': 'Venta Regular',
                    'client_or_reason': 'Cliente CartMaker',
                    'details': 'Procesado en caja / Checkout'
                })
                
            # CASO B: Ingresos por reposición de stock
            elif trans.transaction_type == TransactionType.INCOME:
                ledger.append({
                    'date': trans.creation,
                    'type': 'INGRESO STOCK',
                    'store': trans.item.store.name,
                    'product': trans.item.product.name,
                    'qty': f"+{qty_val}",
                    'gross_amount': 0.0,
                    'discount_amount': 0.0,
                    'net_revenue': 0.0,
                    'origin': 'Operativo',
                    'client_or_reason': 'Abastecimiento / Proveedor',
                    'details': 'Carga manual de inventario para reponer stock'
                })
                
            # 💡 CASO C: Registro del Lote Inicial de Creación del Producto
            elif trans.transaction_type == TransactionType.CREATION:
                ledger.append({
                    'date': trans.creation,
                    'type': 'CREACION LOTE',
                    'store': trans.item.store.name,
                    'product': trans.item.product.name,
                    'qty': f"+{qty_val}",
                    'gross_amount': 0.0,
                    'discount_amount': 0.0,
                    'net_revenue': 0.0,
                    'origin': 'Operativo',
                    'client_or_reason': 'Registro Inicial',
                    'details': 'Lote de inventario inicial creado en el sistema'
                })

        for entry in ledger:
            entry['date'] = timezone.localtime(entry['date']).strftime("%d/%m/%Y %I:%M %p")

        return Response({
            'data': {
                'ledger': ledger,
                'pagination': {
                    'current_page': page,
                    'total_pages': total_pages,
                    'has_next': page < total_pages,
                    'has_previous': page > 1,
                    'total_records': total_items
                }
            }
        }, status=status.HTTP_200_OK)

    # =========================================================================
    # 7. INVENTARIO VIVO DE SUCURSAL (Para Modal en Flutter)
    # =========================================================================
    @action(detail=False, methods=['get'])
    def branch_inventory(self, request):
        store_id = request.query_params.get('store_id')
        if not store_id:
            return Response({'error': 'ID de sucursal requerido.'}, status=status.HTTP_400_BAD_REQUEST)
            
        company = Company.objects.filter(owner=request.user).first()
        
        items = InventoryItem.objects.filter(
            store_id=store_id, 
            store__company=company,
            paused=False
        ).select_related('product')
        
        data = []
        for item in items:
            img_url = storage_manager.get_url(item.product.images[0]) if item.product.images else ""
            data.append({
                'id': str(item.id),
                'name': item.product.name,
                'stock': item.stock,
                'image': img_url
            })
            
        data.sort(key=lambda x: x['stock'])
        return Response({'data': data}, status=status.HTTP_200_OK)

class CompanyVideoStoryViewSet(viewsets.ModelViewSet):
    """
    Endpoints para gestionar los videos cortos de los comercios.
    """
    queryset = CompanyVideoStory.objects.all()
    serializer_class = CompanyVideoStorySerializer
    
    # 💡 MUY IMPORTANTE: Habilitamos a Django para recibir archivos pesados
    parser_classes = (MultiPartParser, FormParser)

    @action(detail=False, methods=['get'])
    def available_items(self, request):
        """
        Retorna todos los InventoryItems agrupados por sucursal.
        Indica si el ítem ya tiene un video vigente.
        """
        company = Company.objects.filter(owner=request.user).first()
        if not company:
            return Response({"error": "No tienes una compañía registrada."}, status=status.HTTP_403_FORBIDDEN)

        now = timezone.now()
        stores = company.stores.filter(is_active=True).prefetch_related(
            'product_items', 'product_items__product', 'product_items__linked_stories'
        )
        
        data = []
        for store in stores:
            items_data = []
            # Filtramos ítems con stock y que no estén pausados
            inventory_items = store.product_items.filter(paused=False, stock__gt=0)
            
            for item in inventory_items:
                # Verificamos si tiene un video vigente activo
                active_story = item.linked_stories.filter(expires_at__gt=now, video_file__isnull=False).first()
                
                img_url = ""
                if item.product.images and len(item.product.images) > 0:
                    img_url = storage_manager.get_url(item.product.images[0])

                items_data.append({
                    "id": str(item.id),
                    "product_name": item.product.name,
                    "image": img_url,
                    "active_video_expiration": timezone.localtime(active_story.expires_at).isoformat() if active_story else None
                })
            
            data.append({
                "store_id": str(store.id),
                "store_name": store.name,
                "items": items_data
            })
            
        return Response({"data": data}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def my_videos(self, request):
        company = Company.objects.filter(owner=request.user).first()
        if not company:
            return Response({"error": "No tienes una compañía registrada."}, status=status.HTTP_403_FORBIDDEN)

        # Traemos los videos ordenados por fecha de creación
        videos = self.queryset.filter(company=company).order_by('-creation')
        
        page_number = request.GET.get('page', 1)
        paginator = Paginator(videos, 10) # 10 videos por página
        page_obj = paginator.get_page(page_number)

        data = [video.get_json() for video in page_obj.object_list]
        
        return Response({
            "success": True,
            "data": {
                "videos": data,
                "pagination": {
                    "current_page": page_obj.number,
                    "total_pages": paginator.num_pages,
                    "has_next": page_obj.has_next(),
                    "total_items": paginator.count
                }
            }
        }, status=status.HTTP_200_OK)

    # 💡 2. OVERRIDE: Destrucción segura
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Validar que el dueño sea el que intenta borrar
        if instance.company.owner != request.user:
             return Response({"error": "No tienes permiso para eliminar este video."}, status=status.HTTP_403_FORBIDDEN)
        
        # Disparamos la limpieza física de AWS/Storage
        instance.clear_media_files()
        
        # Borramos de la BD (GenericRelation limpiará likes y comments en cascada)
        instance.delete()
        
        return Response({"success": True, "message": "Video eliminado correctamente."}, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        """
        Endpoint que recibe la petición desde Flutter (multipart/form-data).
        Maneja los archivos físicamente a través del COS (storage_manager).
        """
        try:
            # 1. Obtener la compañía del comerciante
            company = Company.objects.filter(owner=request.user).first()
            if not company:
                return Response({
                    "error": "No tienes una compañía registrada para subir videos."
                }, status=status.HTTP_403_FORBIDDEN)

            # 2. Extraer datos crudos del Request
            video_obj = request.FILES.get('video_file')
            thumb_obj = request.FILES.get('thumbnail')
            description = request.data.get('description', '')
            associated_item_id = request.data.get('associated_item_id')
            duration = float(request.data.get('duration_seconds', 0.0))

            filter_matrix_raw = request.data.get('applied_filter_matrix')
            filter_matrix = json.loads(filter_matrix_raw) if filter_matrix_raw else None

            if not video_obj or not thumb_obj:
                return Response({
                    "error": "Faltan los archivos físicos de video o miniatura."
                }, status=status.HTTP_400_BAD_REQUEST)

            # 3. Validar el producto vinculado (Si aplica)
            associated_item = None
            if associated_item_id and str(associated_item_id).strip():
                try:
                    associated_item = InventoryItem.objects.get(
                        id=associated_item_id, 
                        store__company=company
                    )
                except InventoryItem.DoesNotExist:
                    return Response({
                        "error": "El producto vinculado no existe o no te pertenece."
                    }, status=status.HTTP_400_BAD_REQUEST)

            # 4. Transacción Atómica y Guardado Físico
            with transaction.atomic():
                dtnow_str = timezone.localtime(timezone.now()).strftime('%d-%m-%Y_%H-%M-%S')
                
                # --- GUARDAR VIDEO ---
                v_ext = video_obj.name.split('.')[-1]
                v_name = f"story_video_{company.id}_{dtnow_str}.{v_ext}"
                v_folder = "stories/videos" 
                v_path = storage_manager.save_file(video_obj, v_folder, v_name)

                # --- GUARDAR MINIATURA ---
                t_ext = thumb_obj.name.split('.')[-1]
                t_name = f"story_thumb_{company.id}_{dtnow_str}.{t_ext}"
                t_folder = "stories/thumbnails"
                t_path = storage_manager.save_file(thumb_obj, t_folder, t_name)

                if not v_path or not t_path:
                    raise Exception("Fallo en el storage_manager al guardar los archivos.")

                # 5. Crear el registro en la Base de Datos
                expires_at = timezone.now() + timedelta(hours=72)

                print("FILTER MATRIX: ", filter_matrix)

                # 💡 Creamos la historia. Como "associated_item" es un ForeignKey, 
                # la BD permite que varios videos apunten al mismo producto sin chocar.
                story = CompanyVideoStory.objects.create(
                    company=company,
                    video_file=v_path,
                    thumbnail=t_path,
                    description=description,
                    associated_item=associated_item,
                    applied_filter_matrix=filter_matrix,
                    expires_at=expires_at,
                    duration_seconds=duration
                )

                # 💡 Lanzamos la tarea a Celery
                optimize_and_transcode_video_story.delay(story.id)

                # 💡 Destrucción táctica del caché estructural.
                # Al borrar esto, forzamos a los teléfonos a recalcular el Feed en la próxima petición,
                # inyectando tu nuevo video inmediatamente en la mezcla.
                try:
                    cache.delete_pattern("cartmaker:struct:*")
                except Exception as e:
                    print(f"Nota: No se pudo limpiar el caché por patrón: {e}")

            return Response({
                "success": True,
                "message": "Video publicado con éxito",
                "data": story.get_json()
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            print(f"Error al guardar la historia: {e}")
            return Response({
                "success": False,
                "error": f"Error interno: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class OrderViewSet(viewsets.ViewSet):
    """
    API para la gestión y consulta de órdenes de compra del usuario.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'

    # 💡 NUEVO ENDPOINT PARA RECUPERAR UNA ORDEN INDIVIDUAL
    def retrieve(self, request, pk=None):
        """
        GET /api/v1/orders/<id>/
        Permite recuperar una orden individual si eres el cliente O el comerciante dueño.
        """
        try:
            # Buscamos la orden garantizando que el usuario sea el cliente O el dueño de la compañía
            order = Order.objects.select_related(
                'store__company', 
                'store__location',
                'client_location'
            ).get(
                Q(id=pk) & (Q(client=request.user) | Q(store__company__owner=request.user))
            )
            
            # Formateamos la data exactamente igual que en tus otros métodos
            company = order.store.company
            store_image_url = storage_manager.get_url(company.image) if company.image else ""
            creation_str = timezone.localtime(order.creation).strftime("%d/%m/%Y %I:%M %p").lower() if order.creation else None
            
            store_lat = float(order.store.location.coordinates.y) if hasattr(order.store, 'location') and order.store.location and order.store.location.coordinates else None
            store_lng = float(order.store.location.coordinates.x) if hasattr(order.store, 'location') and order.store.location and order.store.location.coordinates else None
            store_address = "Dirección no registrada"
            if hasattr(order.store, 'location') and order.store.location:
                store_address = order.store.location.name
            store_email = company.owner.email if company and company.owner else "Sin correo"
            
            client_lat = float(order.client_location.coordinates.y) if order.client_location else None
            client_lng = float(order.client_location.coordinates.x) if order.client_location else None
            client_address = order.client_location.description if order.client_location else None

            is_merchant_mode = False
            if hasattr(request.user, 'company'):
                if request.user.company.id == order.store.company.id:
                    is_merchant_mode = True

            contact_methods_dict = {
                ContactMethodType(contact.method_type).name.lower(): contact.get_json()
                for contact in order.client.contact_methods.all()
            }

            store_contact_methods_dict = {
                str(ContactMethodType(contact.method_type).name).lower(): contact.get_json()
                for contact in order.store.contact_methods.all()
            }

            # Mandamos la estructura limpia que espera Flutter
            payload = {
                'id': order.id, 
                "is_merchant_mode":is_merchant_mode,
                'status': order.status,
                'withdrawal_type': order.withdrawal_type,
                'store_id': str(order.store.id),
                'store_name': company.name,
                'store_image': store_image_url,
                'store_lat': store_lat,
                'store_lng': store_lng,
                'store_contact_methods':store_contact_methods_dict,
                'store_address': store_address,
                'store_email': store_email,
                'cart': order.cart,
                'creation': creation_str,
                'client_lat': client_lat,
                'client_lng': client_lng,
                'client_address': client_address,
                "client_image": storage_manager.get_url(order.client.profile_picture) if order.client.profile_picture else None,
                'client_name': f"{order.client.first_name} {order.client.last_name}",
                'client_contact_methods':contact_methods_dict,
                'end_time': timezone.localtime(order.end_time).strftime("%d/%m/%Y %I:%M %p").lower() if order.end_time else creation_str,
                'client_cedula': order.client.cedula_number,
                'client_email': order.client.email,
            }
            
            return Response(payload, status=status.HTTP_200_OK)

        except Order.DoesNotExist:
            return Response(
                {"error": "La orden no existe o no tienes permisos para verla."}, 
                status=status.HTTP_404_NOT_FOUND
            )

    def list(self, request):
        # 💡 Optimizamos con select_related para traer la info de la tienda, la compañía y la ubicación de entrega de un solo golpe
        orders = Order.objects.select_related(
            'store__company', 
            'store__location',
            'client_location'
        ).prefetch_related(
            'store__contact_methods'
        ).filter(client=request.user).order_by('-creation')
        
        orders_data = []
        for order in orders:
            company = order.store.company
            
            # Obtenemos el logo de la empresa usando tu storage_manager
            store_image_url = ""
            if company.image:
                store_image_url = storage_manager.get_url(company.image)
                
            # Formateamos la fecha exacto como el Mockup: "17/01/2026 09:26 am"
            creation_str = timezone.localtime(order.creation).strftime("%d/%m/%Y %I:%M %p").lower() if order.creation else None
            
            # 💡 EXTRACCIÓN DE COORDENADAS DESDE EL ONE-TO-ONE FIELD Y POINTFIELD
            store_lat = None
            store_lng = None
            client_lat = None     # 💡 CORRECCIÓN: Inicializados en None para evitar UnboundLocalError
            client_lng = None     # 💡 CORRECCIÓN: Inicializados en None para evitar UnboundLocalError
            client_address = None
            store_address = "Dirección no registrada"
            store_email = "Sin correo"
            if hasattr(order.store, 'location') and order.store.location:
                location = order.store.location
                if location.coordinates:
                    store_lat = float(location.coordinates.y)  # Eje Y = Latitud
                    store_lng = float(location.coordinates.x)  # Eje X = Longitud
                store_address = order.store.location.name
                store_email = company.owner.email if company and company.owner else "Sin correo"
            
            if order.client_location:
                client_lat = float(order.client_location.coordinates.y)
                client_lng = float(order.client_location.coordinates.x)
                client_address = order.client_location.description

            # 💡 EXTRACCIÓN DE MÉTODOS DE CONTACTO (Tienda -> Cliente)
            contact_methods_dict = {
                ContactMethodType(contact.method_type).name.lower(): contact.get_json()
                for contact in order.client.contact_methods.all()
            }

            store_contact_methods_dict = {
                str(ContactMethodType(contact.method_type).name).lower(): contact.get_json()
                for contact in order.store.contact_methods.all()
            }

            orders_data.append({
                'id': order.id, 
                'status': order.status,
                'withdrawal_type': order.withdrawal_type,
                'store_id': str(order.store.id),
                'store_name': company.name,
                'store_image': store_image_url,
                'store_contact_methods': store_contact_methods_dict,
                'store_lat': store_lat,
                'store_lng': store_lng,
                'store_address': store_address,
                'store_email': store_email,
                'cart': order.cart,
                'creation': creation_str,
                'client_lat': client_lat,
                'client_lng': client_lng,
                'client_address': client_address,
                'client_contact_methods': contact_methods_dict,
                'end_time': timezone.localtime(order.end_time).strftime("%d/%m/%Y %I:%M %p").lower() if order.end_time else creation_str,
                'client_cedula': order.client.cedula_number,
                'client_email': order.client.email,
            })

        return Response({'data': orders_data}, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def merchant_orders(self, request):
        """ Retorna las órdenes pertenecientes a las tiendas del comerciante autenticado """
        orders = Order.objects.select_related(
            'store__company', 
            'store__location', 
            'client',
            'client_location'
        ).prefetch_related(
            'client__contact_methods'
        ).filter(
            store__company__owner=request.user
        ).order_by('-creation')
        
        orders_data = []
        for order in orders:
            creation_str = timezone.localtime(order.creation).strftime("%d/%m/%Y %I:%M %p").lower() if order.creation else None
            
            # Extraemos la imagen de perfil usando tu método del modelo User
            client_image_url = order.client.get_profile_picture_url() if order.client.profile_picture else ""

            # EXTRACCIÓN DE MÉTODOS DE CONTACTO (Cliente -> Tienda)
            contact_methods_dict = {
                str(ContactMethodType(contact.method_type).name).lower(): contact.get_json()
                for contact in order.client.contact_methods.all()
            }

            # =========================================================================
            # 💡 RESOLUCIÓN DE DATA LOGÍSTICA COMPLETA PARA EL COMERCIANTE
            # =========================================================================
            company = order.store.company
            
            # Imagen corporativa de la Company
            store_image_url = ""
            if company.image:
                store_image_url = storage_manager.get_url(company.image)

            # Coordenadas geográficas de la sucursal emisora
            store_lat = None
            store_lng = None
            if hasattr(order.store, 'location') and order.store.location and order.store.location.coordinates:
                store_lat = float(order.store.location.coordinates.y)
                store_lng = float(order.store.location.coordinates.x)

            # Coordenadas geográficas fijas del destino del cliente
            client_lat = None
            client_lng = None
            client_address = None
            if order.client_location:
                client_lat = float(order.client_location.coordinates.y)
                client_lng = float(order.client_location.coordinates.x)
                client_address = order.client_location.description

            orders_data.append({
                'id': order.id,
                'status': order.status,
                'withdrawal_type': order.withdrawal_type,
                'client_name': f"{order.client.first_name} {order.client.last_name}",
                'client_image': client_image_url,
                'client_contact_methods': contact_methods_dict,
                'store_name': order.store.name,
                
                # Datos estructurados inyectados para MerchantRouteMap
                'store_image': store_image_url,
                'store_lat': store_lat,
                'store_lng': store_lng,
                'client_lat': client_lat,
                'client_lng': client_lng,
                'client_address': client_address,
                
                'cart': order.cart,
                'creation': creation_str,
            })
        return Response({'data': orders_data}, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['post'])
    def merchant_ship_order(self, request):
        """ Permite al comerciante marcar un delivery como enviado (Status 1) """
        order_id = request.data.get('order_id')
        try:
            order = Order.objects.select_related('store__company').get(id=order_id, store__company__owner=request.user)
            print("WITDRAWAL TYPE: ", order.withdrawal_type)
            if order.withdrawal_type != WithdrawalType.DELIVERY: # DELIVERY
                return Response({"error": "Esta orden no requiere despacho a domicilio."}, status=status.HTTP_400_BAD_REQUEST)
                
            if order.status != OrderStatus.WAITING: # WAITING
                return Response({"error": "La orden ya ha cambiado de estado."}, status=status.HTTP_400_BAD_REQUEST)

            order.status = OrderStatus.DELIVERY_SENT # ENVIADO / EN CAMINO
            order.save()
            
            # 💡 SOLUCIÓN CASO BORDE 1: Marcamos como leídas las notificaciones previas de esta orden
            Notification.objects.filter(metadata__order_id=str(order.id), is_read=False).update(is_read=True)
            
            # Notificar al cliente que su motorizado va en camino
            NotificationManager.notify_order_status_change(
                user_id=order.client.id,
                order_id=order.id,
                title="¡Tu orden va en camino!",
                body=f"El repartidor de {order.store.company.name} ha salido con tus productos.",
                is_merchant=False,
                new_status=OrderStatus.DELIVERY_SENT # 💡 AÑADIDO
            )
            return Response({"success": True, "message": "Orden marcada como enviada."}, status=status.HTTP_200_OK)
        except Order.DoesNotExist:
            return Response({"error": "La orden no existe o no eres el dueño del comercio."}, status=status.HTTP_404_NOT_FOUND)

    # =========================================================================
    # 💡 OBTENER TÓPICOS DIRECTO DEL CÓDIGO (Sin tocar la BD)
    # =========================================================================
    @action(detail=False, methods=['get'])
    def cancellation_topics(self, request):
        try:
            # Transformamos el Enum de Django en una lista de diccionarios para Flutter
            topics = [{'id': choice[0], 'name': str(choice[1])} for choice in CancellationReason.choices]
            return Response({'data': topics}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"Error obteniendo tópicos: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # =========================================================================
    # 💡 CANCELAR ORDEN (Con reintegro de Stock Físico y Digital)
    # =========================================================================
    @action(detail=False, methods=['post'])
    def cancel_order(self, request):
        order_id = request.data.get('order_id')
        topic_id = request.data.get('cancellation_topic_id') 

        if not order_id or not topic_id:
            return Response({"error": "Se requiere order_id y cancellation_topic_id."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            topic_id = int(topic_id)
            if topic_id not in dict(CancellationReason.choices):
                raise ValueError
        except (TypeError, ValueError):
            return Response({"error": "El motivo de cancelación seleccionado no es válido."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                order = Order.objects.select_for_update().get(id=order_id, client=request.user)

                if order.status != OrderStatus.WAITING: 
                    return Response({"error": "Solo puedes cancelar órdenes pendientes."}, status=status.HTTP_400_BAD_REQUEST)

                # =============================================================
                # 1. REINTEGRO DE STOCK FÍSICO
                # =============================================================
                cart_items = order.cart.get('items', [])
                for item in cart_items:
                    inv_item_id = item.get('inventory_item_id')
                    qty = int(item.get('quantity', 0))
                    if inv_item_id and qty > 0:
                        try:
                            inv_item = InventoryItem.objects.select_for_update().get(id=inv_item_id)
                            inv_item.stock += qty
                            inv_item.save()
                        except InventoryItem.DoesNotExist:
                            pass 

                # =============================================================
                # 💡 2. REINTEGRO DE TOKENS (Gamificación)
                # =============================================================
                # Buscamos si a esta orden se le cobraron tokens (OUTCOME)
                spent_transactions = TokenWalletTransaction.objects.filter(
                    order=order, 
                    transaction_type=TransactionType.OUTCOME
                )
                
                total_tokens_to_refund = sum(t.amount for t in spent_transactions)

                if total_tokens_to_refund > 0:
                    try:
                        # Bloqueamos la billetera para evitar race conditions
                        wallet = TokenWallet.objects.select_for_update().get(
                            user=order.client, 
                            company=order.store.company
                        )
                        wallet.balance += total_tokens_to_refund
                        wallet.save(update_fields=['balance'])
                        
                        # Dejamos un recibo del reembolso
                        TokenWalletTransaction.objects.create(
                            token_wallet=wallet,
                            amount=total_tokens_to_refund,
                            transaction_type=TransactionType.INCOME, # O TransactionType.REFUND si lo tienes
                            order=order
                        )
                    except TokenWallet.DoesNotExist:
                        pass # Fallback de seguridad por si le borraron la billetera manualmente

                # =============================================================
                # 3. ACTUALIZACIÓN DE ESTADO Y NOTIFICACIONES
                # =============================================================
                order.status = OrderStatus.CANCELLED
                order.cancellation_topic = topic_id 
                order.end_time = timezone.now()
                order.save()

                Notification.objects.filter(metadata__order_id=str(order.id), is_read=False).update(is_read=True)
                NotificationManager.notify_order_status_change(
                    user_id=order.store.company.owner.id,
                    order_id=order.id,
                    title="Orden Cancelada",
                    body=f"El cliente ha cancelado la orden N° {order.id}.",
                    is_merchant=True,
                    new_status=OrderStatus.CANCELLED 
                )

            return Response({"success": True, "message": "Orden cancelada exitosamente y stock/tokens devueltos."}, status=status.HTTP_200_OK)
        except Order.DoesNotExist:
            return Response({"error": "La orden no existe."}, status=status.HTTP_404_NOT_FOUND)

    # =========================================================================
    # 💡 MARCAR ORDEN COMO RECIBIDA Y CALIFICAR (TODO EN 1)
    # =========================================================================
    @action(detail=False, methods=['post'])
    def complete_order(self, request):
        """ Endpoint unificado de finalización con lógica de cross-notification """
        order_id = request.data.get('order_id')
        merchant_rating = request.data.get('merchant_rating', 0)
        product_ratings = request.data.get('product_ratings', [])

        try:
            with transaction.atomic():
                # Buscamos si quien ejecuta es el cliente o el comerciante
                order = Order.objects.select_related('store__company').get(id=order_id)
                is_client = order.client == request.user
                is_merchant = order.store.company.owner == request.user

                if not is_client and not is_merchant:
                    return Response({"error": "No tienes permisos sobre esta orden."}, status=status.HTTP_403_FORBIDDEN)

                if order.status == OrderStatus.COMPLETED: # COMPLETED
                    return Response({"error": "Esta orden ya se encuentra completada."}, status=status.HTTP_400_BAD_REQUEST)

                with transaction.atomic():
                    order.status = OrderStatus.COMPLETED # COMPLETED
                    order.end_time = timezone.now()
                    order.save()

                    cart_items = order.cart.get('items', [])
                    for item in cart_items:
                        inv_item_id = item.get('inventory_item_id')
                        qty = int(item.get('quantity', 0))
                        
                        # 💡 EXTRAEMOS LA ETIQUETA DEL VIDEO DEL SNAPSHOT DE LA ORDEN
                        source_video_id = item.get('source_video_id')
                        
                        if inv_item_id and qty > 0:
                            try:
                                inv_item = InventoryItem.objects.get(id=inv_item_id)
                                InventoryItemTransaction.objects.create(
                                    item=inv_item,
                                    units=qty,
                                    transaction_type=TransactionType.OUTCOME
                                )
                            except InventoryItem.DoesNotExist:
                                pass # Si el producto ya no existe, ignoramos

                        # =========================================================
                        # 💡 REGISTRO DE COMPRA DE VIDEO (Atribución Real en Checkout)
                        # =========================================================
                        if source_video_id:
                            try:
                                # ⚠️ MUY IMPORTANTE: Usamos order.client, NO request.user, 
                                # porque el que completa la orden podría ser el comerciante.
                                log = VideoEngagementLog.objects.filter(
                                    client=order.client,
                                    video_id=source_video_id
                                ).order_by('-timestamp').first()

                                if log:
                                    log.bought_from_video = True
                                    log.save(update_fields=['bought_from_video'])
                                else:
                                    # Fallback de seguridad
                                    VideoEngagementLog.objects.create(
                                        client=order.client,
                                        video_id=source_video_id,
                                        bought_from_video=True
                                    )
                                print(f"✅ ATRIBUCIÓN DE COMPRA REGISTRADA PARA EL VIDEO: {source_video_id}")
                            except Exception as e:
                                print(f"❌ Error actualizando atribución de video: {e}")
                    

                    Notification.objects.filter(metadata__order_id=str(order.id), is_read=False).update(is_read=True)

                    # El cliente califica (Solo si la petición viene del cliente real)
                    if is_client:
                        if merchant_rating and float(merchant_rating) > 0:
                            MerchantCalification.objects.create(merchant=order.store.company, client=request.user, rating=float(merchant_rating))
                        for pr in product_ratings:
                            rating_val = pr.get('rating', 0)
                            product_id = pr.get('product_id')
                            if product_id and float(rating_val) > 0:
                                ProductCalification.objects.create(product_id=product_id, client=request.user, rating=float(rating_val))

                if is_client:
                    NotificationManager.notify_order_status_change(
                        user_id=order.store.company.owner.id,
                        order_id=order.id,
                        title="Cliente confirmó entrega",
                        body=f"El cliente de la orden N° {order.id} la ha marcado como completada.",
                        is_merchant=True,
                        new_status=OrderStatus.COMPLETED # 💡 AÑADIDO
                    )
                elif is_merchant:
                    NotificationManager.notify_order_status_change(
                        user_id=order.client.id,
                        order_id=order.id,
                        title="Tu orden fue completada",
                        body=f"{order.store.company.name} ha marcado tu pedido como completado exitosamente.",
                        is_merchant=False,
                        new_status=OrderStatus.COMPLETED # 💡 AÑADIDO
                    )

                tokens_earned = 0.0
                company = order.store.company

                if company.gamification_enabled and company.gamification_tokens_per_dollar > 0:
                    order_total = float(order.cart.get('total', 0.0))
                    tokens_earned = int(order_total * company.gamification_tokens_per_dollar)
                    
                    if tokens_earned > 0:
                        wallet, _ = TokenWallet.objects.get_or_create(user=order.client, company=company)
                        wallet.balance += tokens_earned
                        wallet.save(update_fields=['balance'])
                        
                        TokenWalletTransaction.objects.create(
                            token_wallet=wallet, amount=tokens_earned,
                            transaction_type=TransactionType.INCOME, order=order
                        )

                return Response({
                    "success": True, 
                    "tokens_earned": round(float(tokens_earned), 2) , # 👈 Ahora sí enviamos el número real
                    "message": "Orden completada con éxito."
                }, status=status.HTTP_200_OK)
            return Response({'error':"Error interno en el servidor."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Order.DoesNotExist:
            return Response({"error": "La orden no existe."}, status=status.HTTP_404_NOT_FOUND)


class CartViewSet(viewsets.ViewSet):
    """
    API ultra-optimizada para la gestión del carrito de compras.
    Utiliza MGET y Split Caching para resolver carritos masivos en milisegundos.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'

    @action(detail=False, methods=['post'])
    def details(self, request):
        item_ids = request.data.get('item_ids', [])

        print("ITEM IDS: ", item_ids)
        
        if not item_ids or not isinstance(item_ids, list):
            return Response({'data': []}, status=status.HTTP_200_OK)

        # =========================================================================
        # 1. CACHÉ ESTRUCTURAL (Fotos, Nombres, Empresa)
        # =========================================================================
        struct_keys = {f"cartmaker:struct:item:{uid}": uid for uid in item_ids}
        cached_structs = cache.get_many(struct_keys.keys())

        missing_ids = [uid for key, uid in struct_keys.items() if key not in cached_structs]
        struct_data_map = {uid: cached_structs[f"cartmaker:struct:item:{uid}"] for uid in item_ids if f"cartmaker:struct:item:{uid}" in cached_structs}

        # RESOLUCIÓN DE CACHE MISS (Solo va a BD por los productos que no están en RAM)
        if missing_ids:
            qs = InventoryItem.objects.select_related(
                'product', 'offer', 'store__company__owner__subscription__plan'
            ).filter(id__in=missing_ids)
            
            new_structs_to_cache = {}
            for item in qs:
                item_json = item.get_json()
                
                # 💡 Inyección Táctica: Ponemos los datos de la empresa a mano 
                # para que el frontend de Flutter no tenga que escarbar en el JSON
                company = item.store.company
                print(f"IMAGEN DE LAA COMPNY {company}: {company.image}")
                item_json['company_info'] = {
                    'id': str(company.id),
                    'name': company.name,
                    'image': storage_manager.get_url(company.image) if company.image else None
                }

                struct_data_map[str(item.id)] = item_json
                new_structs_to_cache[f"cartmaker:struct:item:{item.id}"] = item_json
            
            if new_structs_to_cache:
                cache.set_many(new_structs_to_cache, timeout=86400) # Estructura cacheada por 24h

        # =========================================================================
        # 2. STITCHING VOLÁTIL EN TIEMPO REAL (Stock y Precios Exactos)
        # =========================================================================
        volatile_keys = {f"cartmaker:volatile:item:{uid}": uid for uid in item_ids}
        cached_volatiles = cache.get_many(volatile_keys.keys())

        final_data = []
        for uid in item_ids:
            item_data = struct_data_map.get(uid)
            if not item_data:
                continue # El ítem fue eliminado físicamente de la BD

            v_key = f"cartmaker:volatile:item:{uid}"
            state = cached_volatiles.get(v_key)

            if not state:
                state = {
                    "stock": int(item_data.get("stock", 0)),
                    "paused": bool(item_data.get("paused", False)),
                    "custom_price": item_data.get("custom_price")
                }
                cache.set(v_key, state, timeout=86400)
            
            # Fusión en RAM
            item_data["stock"] = state["stock"]
            item_data["paused"] = state["paused"]
            item_data["custom_price"] = state["custom_price"]

            final_data.append(item_data)

        return Response({'data': final_data}, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['post'])
    def create_order(self, request):
        if request.user.cedula_verified == False:
            return Response({
                "error": "No puedes comprar sin antes verificar tu identidad."
            }, status=status.HTTP_406_NOT_ACCEPTABLE)
        store_id = request.data.get('store_id')
        items_data = request.data.get('items', [])  # Ej: [{'id': 'uid', 'quantity': 2}]
        withdrawal_type = request.data.get('withdrawal_type', 0)
        location_id = request.data.get('delivery_location_id')

        print("REQUEST DATA EN CREATE ORDER: ", request.data)

        if not store_id or not items_data:
            return Response({
                "error": "El carrito está vacío o faltan datos para procesar tu orden."
            }, status=status.HTTP_400_BAD_REQUEST)

        # =========================================================================
        # 1. VALIDACIONES PRELIMINARES (Ahorran recursos)
        # =========================================================================
        try:
            store = CompanyStore.objects.select_related(
                'company', 'company__owner__subscription'
            ).get(id=store_id)
            if hasattr(request.user, 'company'):
                if store.company.id == request.user.company.id:
                    return Response({
                        "error": "No puedes comprar tus mismos productos."
                    }, status=status.HTTP_406_NOT_ACCEPTABLE)
        except CompanyStore.DoesNotExist:
            return Response({
                "error": "La tienda en la que intentas comprar ya no se encuentra disponible en la plataforma."
            }, status=status.HTTP_404_NOT_FOUND)

        if not store.is_active:
            return Response({
                "error": f"Lo sentimos, {store.name} se encuentra inactiva en este momento. Por favor, intenta más tarde."
            }, status=status.HTTP_403_FORBIDDEN)

        if not store.is_currently_open:
            return Response({
                "error": "La tienda se encuentra fuera de horario laboral.",
                "work_hours": store.effective_work_hours,
                "work_days": store.effective_work_days
            }, status=status.HTTP_403_FORBIDDEN)

        try:
            sub = store.company.owner.subscription
            if not sub.valid_until or sub.valid_until < timezone.now():
                return Response({
                    "error": f"El comercio {store.company.name} no se encuentra habilitado para recibir pedidos en este momento."
                }, status=status.HTTP_403_FORBIDDEN)
        except ObjectDoesNotExist:
            return Response({
                "error": f"El comercio {store.company.name} no puede procesar compras temporalmente."
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Validar que el usuario NO tenga órdenes activas en esta misma tienda
        # (Asumiendo que status 0 = WAITING. Si agregas luego status 1=PREPARANDO, pon status__in=[0, 1])
        has_active_order = Order.objects.filter(
            client=request.user, 
            store_id=store_id, 
            status=OrderStatus.WAITING
        ).exists()

        if has_active_order:
            return Response({
                "error": "ORDEN_DUPLICADA",
                "message": f"Ya tienes un pedido en curso en {store.company.name}. Por favor espera a que finalice o cancélalo si deseas modificar tu compra."
            }, status=status.HTTP_409_CONFLICT)

        item_ids = [item['id'] for item in items_data]
        item_qty_map = {item['id']: int(item['quantity']) for item in items_data}
        item_discount_map = {item.get('id'): item.get('selected_discount') for item in items_data if item.get('selected_discount')}
        # Calculamos cuántos tokens en total le va a costar esta orden al usuario
        total_tokens_needed = 0
        for item_id, discount in item_discount_map.items():
            total_tokens_needed += int(discount.get('tokens', 0))
        # 💡 Buscamos la ubicación de forma segura
        client_location = None
        try:
            client_location = ClientLocation.objects.get(id=location_id, user=request.user)
        except ClientLocation.DoesNotExist:
            return Response({"error": "La dirección seleccionada no es válida."}, status=status.HTTP_404_NOT_FOUND)

        # =========================================================================
        # 2. BLOQUEO ATÓMICO Y HARD RESERVATION
        # =========================================================================
        try:
            with transaction.atomic():
                inventory_items = InventoryItem.objects.select_for_update().filter(id__in=item_ids)

                # 💡 BLOQUEO ATÓMICO 1: Validamos que el cliente SÍ tenga los tokens en esta compañía
                token_wallet = None
                if total_tokens_needed > 0:
                    try:
                        token_wallet = TokenWallet.objects.select_for_update().get(user=request.user, company=store.company)
                        if token_wallet.balance < total_tokens_needed:
                            return Response({
                                "error": "TOKENS_INSUFICIENTES",
                                "message": f"Necesitas {total_tokens_needed} tokens, pero tu saldo actual es de {token_wallet.balance} T."
                            }, status=status.HTTP_409_CONFLICT)
                    except TokenWallet.DoesNotExist:
                        return Response({
                            "error": "SIN_BILLETERA",
                            "message": "No tienes tokens registrados con este comercio."
                        }, status=status.HTTP_409_CONFLICT)
                    
                # 💡 CASO 1: Un producto fue borrado de la BD por el comerciante
                if inventory_items.count() != len(item_ids):
                    found_ids = set(str(item.id) for item in inventory_items)
                    missing_ids = set(item_ids) - found_ids
                    # Retornamos el primer ID faltante para que Flutter lo limpie
                    return Response({
                        "error": "PRODUCTO_ELIMINADO",
                        "product_id": list(missing_ids)[0],
                        "message": "Uno de los productos en tu carrito fue retirado del catálogo por el vendedor. Hemos actualizado tu carrito."
                    }, status=status.HTTP_404_NOT_FOUND)

                cart_snapshot = []
                total_price = 0.0

                for item in inventory_items:
                    requested_qty = item_qty_map[str(item.id)]
                    
                    # 💡 CASO 2: El producto fue pausado
                    if item.paused:
                        return Response({
                            "error": "PRODUCTO_PAUSADO",
                            "product_id": str(item.id),
                            "message": f"El vendedor acaba de pausar la venta de '{item.product.name}'. Por favor, retíralo de tu carrito para continuar."
                        }, status=status.HTTP_409_CONFLICT)
                    
                    # 💡 CASO 3: Stock agotado totalmente o parcialmente
                    if item.stock < requested_qty:
                        if item.stock == 0:
                            msg = f"¡Ups! Alguien más acaba de comprar la última unidad de '{item.product.name}'. Lo hemos retirado de tu carrito."
                        else:
                            # =========================================================
                            # ✨ MENSAJE ULTRA-DESCRIPTIVO (Lo que pediste)
                            # =========================================================
                            msg = f"Hemos ajustado tu pedido de '{item.product.name}' de {requested_qty} a {item.stock} unidades, que es el stock disponible actualmente."
                            
                        return Response({
                            "error": "STOCK_INSUFICIENTE",
                            "product_id": str(item.id),
                            "available_stock": item.stock,
                            "message": msg
                        }, status=status.HTTP_409_CONFLICT)
                    
                    # Todo en orden: Descontamos
                    item.stock -= requested_qty
                    if item.stock <= 0:
                        item.sold_out_time = timezone.now()
                        if item.stock < 0:
                            # Corregir en caso de error
                            item.stock = 0
                    item.save()

                    # Precio base de la BD
                    base_unit_price = float(item.custom_price) if item.custom_price else float(item.product.price)
                    
                    # 💡 1. APLICAMOS OFERTA ESTÁNDAR (Afecta a TODAS las unidades)
                    standard_offer_pct = None
                    if hasattr(item, 'offer') and item.offer and item.offer.valid_until >= timezone.now():
                        standard_offer_pct = int(item.offer.percentage)
                        base_unit_price = base_unit_price - (base_unit_price * (standard_offer_pct / 100.0))

                    # 💡 2. REGLA DE NEGOCIO: EXCLUSIVIDAD MUTUA
                    applied_token_discount = item_discount_map.get(str(item.id))
                    
                    # Si el producto tiene oferta de tienda Y el usuario intentó usar tokens: ¡Rechazamos!
                    if standard_offer_pct and applied_token_discount:
                        return Response({
                            "error": "OFERTAS_NO_ACUMULABLES",
                            "message": f"El producto '{item.product.name}' ya tiene una oferta de la tienda, por lo que no es acumulable con descuentos por tokens."
                        }, status=status.HTTP_409_CONFLICT)

                    # El subtotal arranca asumiendo que todas valen el base_unit_price (ya rebajado si había oferta estándar)
                    subtotal = base_unit_price * requested_qty

                    # 💡 3. APLICAMOS DESCUENTO POR TOKENS (Afecta solo a 1 UNIDAD)
                    if applied_token_discount:
                        pct = float(applied_token_discount.get('percentage', 0))
                        ahorro = base_unit_price * (pct / 100.0)
                        subtotal -= ahorro 

                    img_url = storage_manager.get_url(item.product.images[0]) if item.product.images else ""

                    original_item_req = next((req_item for req_item in items_data if str(req_item['id']) == str(item.id)), {})
                    source_video_id = original_item_req.get('source_video_id')
                    is_from_atlas = original_item_req.get('isFromAtlas', False)

                    img_url = storage_manager.get_url(item.product.images[0]) if item.product.images else ""

                    cart_snapshot.append({
                        "product_id": str(item.product.id),
                        "inventory_item_id": str(item.id),
                        "name": item.product.name,
                        "quantity": requested_qty,
                        "unit_price": base_unit_price, 
                        "subtotal": subtotal,
                        "product_image": img_url,
                        "standard_offer_applied": standard_offer_pct,
                        "token_discount_applied": applied_token_discount,
                        "source_video_id": source_video_id,
                        "is_from_atlas": is_from_atlas
                    })
                    total_price += subtotal

                # 3. Creamos la orden oficial
                order = Order.objects.create(
                    store=store,
                    client=request.user,
                    client_location=client_location,
                    cart={"items": cart_snapshot, "total": total_price},
                    status=OrderStatus.WAITING, 
                    withdrawal_type=withdrawal_type
                )

                # 💡 COBRAMOS LOS TOKENS AL FINALIZAR LA ORDEN
                if token_wallet and total_tokens_needed > 0:
                    token_wallet.balance -= total_tokens_needed
                    token_wallet.save(update_fields=['balance'])
                    
                    TokenWalletTransaction.objects.create(
                        token_wallet=token_wallet,
                        amount=total_tokens_needed,
                        transaction_type=TransactionType.OUTCOME,
                        order=order
                    )
                
                # Invalidamos caché volátil
                for item in inventory_items:
                    cache.delete(f"cartmaker:volatile:item:{item.id}")

            # Obtenemos el ID del dueño de la empresa (Comerciante)
            merchant_id = store.company.owner.id
            total_price = order.cart.get('total', 0.0)
            
            # Lanzamos la alerta al panel administrativo
            firebase_admin.NotificationManager.notify_order_created(
                merchant_id=merchant_id,
                order_id=order.id,
                store_name=store.name,
                total=total_price
            )

            return Response({
                "success": True, 
                "order_id": str(order.id), 
                "message": "¡Orden creada exitosamente!"
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({"error": "Ocurrió un error inesperado al procesar tu compra. Por favor, intenta de nuevo."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
        Registra el Dwell Time e interacciones. Envía los datos a un Buffer en Redis.
        """
        data = request.data
        item_id = data.get('item_id')
        start_time_raw = data.get('start_time')

        if not item_id or not start_time_raw:
            return Response({'error': 'item_id y start_time son obligatorios.'}, status=status.HTTP_400_BAD_REQUEST)

        # Preparamos el payload añadiendo el ID del usuario
        payload = {
            'client_id': str(request.user.id),
            'item_id': str(item_id),
            'added_to_cart': data.get('added_to_cart', False),
            'bought': data.get('bought', False),
            'start_time': start_time_raw,
            'end_time': data.get('end_time')
        }

        try:
            # Empujamos a la lista de Redis
            redis_conn = cache.client.get_client()
            redis_conn.rpush("telemetry:product_views", json.dumps(payload))
            return Response(status=status.HTTP_202_ACCEPTED) # 202 significa "Aceptado para procesamiento"
            
        except Exception as e:
            print(f"Error al encolar analítica en Redis: {e}")
            return Response({'error': 'Error interno'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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

        payload = {
            'client_id': str(request.user.id),
            'store_id': str(store_id),
            'join_time': join_time_raw,
            'exit_time': data.get('exit_time'),
            'location_watched': data.get('location_watched', False),
            'presentation_video_watched': data.get('presentation_video_watched', False),
            'stories_watched': data.get('stories_watched', False),
            'products_watched': data.get('products_watched', False),
            'tryed_to_contact': data.get('tryed_to_contact', False)
        }

        try:
            redis_conn = cache.client.get_client()
            redis_conn.rpush("telemetry:store_views", json.dumps(payload))
            return Response(status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            print(f"Error al encolar analítica de store_view: {e}")
            return Response({'error': 'Error interno'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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

        payload = {
            'client_id': str(request.user.id),
            'navigation_record': navigation_record,
            'login_time': login_time_raw,
            'logout_time': data.get('logout_time')
        }

        try:
            redis_conn = cache.client.get_client()
            redis_conn.rpush("telemetry:navigation_logs", json.dumps(payload))
            return Response(status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            print(f"Error al encolar analítica de navigation: {e}")
            return Response({'error': 'Error interno'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def video_engagement(self, request):
        """
        Registra interacciones de video y acumula el tiempo de visualización.
        """
        data = request.data
        video_id = data.get('video_id')
        
        if not video_id:
            return Response({'error': 'video_id es obligatorio.'}, status=status.HTTP_400_BAD_REQUEST)

        # Blindaje de parseo booleano desde Flutter
        def parse_bool(val):
            return str(val).lower() == 'true' if isinstance(val, str) else bool(val)

        payload = {
            'client_id': str(request.user.id),
            'video_id': str(video_id),
            'watch_time_seconds': float(data.get('watch_time_seconds', 0.0)),
            'video_completed': parse_bool(data.get('video_completed', False)),
            'interacted_with_product': parse_bool(data.get('interacted_with_product', False)),
            'added_to_cart_from_video': parse_bool(data.get('added_to_cart_from_video', False)),
            'bought_from_video': parse_bool(data.get('bought_from_video', False))
        }

        try:
            redis_conn = cache.client.get_client()
            redis_conn.rpush("telemetry:video_engagement", json.dumps(payload))
            return Response({'success': True}, status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            print(f"Error al encolar analítica de video_engagement: {e}")
            return Response({'error': 'Error interno'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
            # 1. Determinar qué tienda consultar (PRIORIDAD AL STORE_ID)
            # 💡 Agregamos "!= 'null'" por si el frontend manda la palabra string por error en la URL
            if store_id and store_id != 'null': 
                store = CompanyStore.objects.select_related('company', 'company__category').filter(
                    Q(company__owner__subscription__plan__company_branches=True) |
                    Q(company__owner__subscription__plan__company_branches=False, is_main_store=True),
                    id=store_id,
                    is_active=True
                ).first()

                # Parche: Si no la encontró, verificamos si por error Flutter mandó el ID de la compañía aquí
                if not store:
                    store = CompanyStore.objects.select_related('company', 'company__category').filter(
                        company_id=store_id,
                        is_main_store=True,
                        is_active=True
                    ).first()

                if not store:
                    return Response({'error': 'La tienda solicitada no existe, fue eliminada o está inactiva.'}, status=status.HTTP_404_NOT_FOUND)
                company = store.company
                
            elif company_id and company_id != 'null':
                # Solo entramos aquí si Flutter explícitamente NO mandó un store_id
                store = CompanyStore.objects.select_related('company', 'company__category').filter(
                    Q(company__owner__subscription__plan__company_branches=True) |
                    Q(company__owner__subscription__plan__company_branches=False, is_main_store=True),
                    company_id=company_id, 
                    is_active=True
                ).order_by('-is_main_store', 'creation').first() # 💡 Priorizamos mostrar la Main Store
                
                if not store:
                    return Response({'error': 'La compañía no tiene tiendas activas bajo su plan actual.'}, status=status.HTTP_404_NOT_FOUND)
                company = store.company
                
            else:
                return Response({'error': 'Faltan parámetros válidos.'}, status=status.HTTP_400_BAD_REQUEST)
            
            # =======================================================
            # 2. CÁLCULO DE MÉTRICAS GLOBALES DE LA COMPAÑÍA
            # =======================================================
            
            # A) Promedio de calificación
            rating_aggr = MerchantCalification.objects.filter(merchant=company).aggregate(Avg('rating'))
            avg_rating = round(rating_aggr['rating__avg'] or 0.0, 2)
            
            # B) Total de ventas de TODAS las sucursales
            sales_aggr = InventoryItemTransaction.objects.filter(
                item__store__company=company,
                transaction_type=1  # OUTCOME
            ).aggregate(Sum('units'))
            total_sales = sales_aggr['units__sum'] or 0
            formatted_sales = f"{total_sales // 1000}k" if total_sales >= 1000 else str(total_sales)

            # C) Categorías disponibles para esta compañía
            available_categories = SubCategory.objects.filter(
                product__inventory_items__store__company=company,
                product__inventory_items__paused=False
            ).distinct().values('id', 'name')

            merchant_subscription = MerchantSubscription.objects.get(merchant=company.owner)

            # 💡 NUEVO: D) Obtenemos todas las sucursales activas permitidas para el Selector
            available_stores_qs = CompanyStore.objects.select_related('location').filter(
                company=company,
                is_active=True
            ).order_by('-is_main_store', 'creation')

            # Si el plan NO permite sucursales, solo mandamos la principal para evitar "hackeos"
            if not merchant_subscription.plan.company_branches:
                available_stores_qs = available_stores_qs.filter(is_main_store=True)

            available_stores = [s.get_json() for s in available_stores_qs]

            # =======================================================
            # 3. CONSTRUCCIÓN DE LA RESPUESTA
            # =======================================================
            company_metadata = company.get_json()
            company_metadata['avg_rating'] = avg_rating
            company_metadata['total_sales'] = formatted_sales
            company_metadata['total_sales_raw'] = total_sales
            company_metadata['merchant_type'] = merchant_subscription.get_merchant_type_display()
            
            store_metadata = store.get_json()

            token_wallet = company.issued_wallets.filter(user=request.user).first()

            return Response({
                'store_metadata': store_metadata,
                'company_metadata': company_metadata,
                'token_wallet': token_wallet.get_json() if token_wallet else None,
                'available_categories': list(available_categories),
                'available_stores': available_stores # 👈 LA LISTA DE SUCURSALES
            }, status=status.HTTP_200_OK)

        except CompanyStore.DoesNotExist:
            return Response({'error': 'La tienda solicitada no existe o fue eliminada.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': f'Error interno: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GamificationViewSet(viewsets.ViewSet):
    """
    API dedicada al motor de gamificación del comerciante.
    Maneja la activación global y por producto.
    """
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def status(self, request):
        """ Obtiene el estado actual de la empresa y la lista de sus productos. """
        company = Company.objects.filter(owner=request.user).first()
        if not company:
            return Response({'error': 'No se encontró la empresa del comerciante.'}, status=status.HTTP_404_NOT_FOUND)

        # Traemos los productos de esta empresa
        products = Product.objects.filter(company=company).order_by('-creation')
        
        products_data = []
        for p in products:
            image_url = ""
            if p.images and len(p.images) > 0:
                image_url = storage_manager.get_url(p.images[0])
                
            products_data.append({
                'id': str(p.id),
                'name': p.name,
                'image': image_url,
                'discounts_by_tokens_active': p.discounts_by_tokens_active
            })

        return Response({
            'gamification_enabled': company.gamification_enabled,
            'gamification_tokens_per_dollar': company.gamification_tokens_per_dollar,
            'products': products_data
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['patch'])
    def update_company_settings(self, request):
        """ Actualiza los settings globales de la empresa. """
        company = Company.objects.filter(owner=request.user).first()
        if not company:
            return Response({'error': 'Compañía no encontrada.'}, status=status.HTTP_404_NOT_FOUND)

        enabled = request.data.get('gamification_enabled')
        tokens = request.data.get('gamification_tokens_per_dollar')

        update_fields = []
        if enabled is not None:
            company.gamification_enabled = bool(enabled)
            update_fields.append('gamification_enabled')
            
        if tokens is not None:
            try:
                company.gamification_tokens_per_dollar = int(tokens)
                update_fields.append('gamification_tokens_per_dollar')
            except ValueError:
                return Response({'error': 'El valor de tokens debe ser numérico.'}, status=status.HTTP_400_BAD_REQUEST)

        if update_fields:
            company.save(update_fields=update_fields)

        return Response({'success': True, 'message': 'Configuración actualizada.'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['patch'])
    def toggle_product(self, request):
        """ Activa o desactiva la gamificación para un producto individual. """
        product_id = request.data.get('product_id')
        active = request.data.get('active')

        if product_id is None or active is None:
            return Response({'error': 'Faltan parámetros.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Aseguramos que el producto le pertenezca a la empresa del usuario
            product = Product.objects.get(id=product_id, company__owner=request.user)
            product.discounts_by_tokens_active = bool(active)
            product.save(update_fields=['discounts_by_tokens_active'])
            return Response({'success': True}, status=status.HTTP_200_OK)
        except Product.DoesNotExist:
            return Response({'error': 'Producto no encontrado o no tienes permisos.'}, status=status.HTTP_404_NOT_FOUND)

class UniversalConversationPagination(PageNumberPagination):
    page_size = 15
    page_size_query_param = 'page_size'
    max_page_size = 30

class UniversalConversationViewSet(viewsets.ViewSet):
    """
    API unificada para comentarios y preguntas en Productos y Videos.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'navigation'

    @action(detail=False, methods=['get'])
    def merchant_items_summary(self, request):
        """
        Retorna la TOTALIDAD de los productos y videos del comerciante,
        calculando sus preguntas pendientes para servir como panel histórico.
        """
        user = request.user
        item_ct = ContentType.objects.get(model='inventoryitem')
        video_ct = ContentType.objects.get(model='companyvideostory')

        # ==========================================
        # 1. OBTENER TODO EL INVENTARIO Y SUS ALERTAS
        # ==========================================
        db_items = InventoryItem.objects.select_related('product', 'store__company').filter(
            store__company__owner=user
        )
        items_ids_strs = [str(item.id) for item in db_items]

        products_summary = UniversalComment.objects.filter(
            content_type=item_ct,
            object_id__in=items_ids_strs
        ).values('object_id').annotate(
            pending=Count('id', filter=Q(answer_text__isnull=True) | Q(answer_text__exact=''))
        )
        products_dict = {item['object_id']: item['pending'] for item in products_summary}

        # ==========================================
        # 2. OBTENER TODAS LAS VIDEO HISTORIAS Y SUS ALERTAS
        # ==========================================
        db_videos = CompanyVideoStory.objects.filter(company__owner=user)
        videos_ids_strs = [str(vid.id) for vid in db_videos]

        videos_summary = UniversalComment.objects.filter(
            content_type=video_ct,
            object_id__in=videos_ids_strs
        ).values('object_id').annotate(
            pending=Count('id', filter=Q(answer_text__isnull=True) | Q(answer_text__exact=''))
        )
        videos_dict = {video['object_id']: video['pending'] for video in videos_summary}

        # ==========================================
        # 3. COMPILACIÓN DE DATA COMPLETA
        # ==========================================
        data = []

        # Mapeamos absolutamente todos los productos
        for item in db_items:
            item_id_str = str(item.id)
            product_json = item.product.get_json()
            images = product_json.get('images', [])
            
            data.append({
                "id": item_id_str,
                "name": product_json.get('name', 'Producto sin nombre'),
                "image": images[0] if images else '',
                "type": "product",
                "pending_questions_count": products_dict.get(item_id_str, 0),
                "creation": item.creation # 💡 Inyectamos la fecha nativa para ordenar
            })

        # Mapeamos absolutamente todos los videos
        for vid in db_videos:
            vid_id_str = str(vid.id)
            vid_json = vid.get_json()
            
            raw_desc = vid_json.get('description') or ''
            clean_desc = raw_desc.strip() if raw_desc else "Video Historia sin descripción"
            
            data.append({
                "id": vid_id_str,
                "name": clean_desc if len(clean_desc) <= 40 else clean_desc[:40] + "...",
                "image": vid_json.get('thumbnail_url') or '', 
                "type": "video",
                "pending_questions_count": videos_dict.get(vid_id_str, 0),
                "creation": vid.creation # 💡 Inyectamos la fecha nativa para ordenar
            })

        # 📊 ORDENAMIENTO DOBLE CRÍTICO:
        # 1. Primero por cantidad de dudas pendientes (Mayor a menor)
        # 2. Segundo por fecha de creación (Más nuevo/reciente a más viejo)
        data.sort(key=lambda x: (x['pending_questions_count'], x['creation']), reverse=True)

        # 🧼 LIMPIEZA PRE-JSON: Eliminamos el objeto 'datetime' para que Django no explote
        # al serializar la respuesta hacia Flutter, ya que el móvil no necesita este campo.
        for item in data:
            item.pop('creation', None)

        return Response({'data': data}, status=200)

    @action(detail=False, methods=['get'])
    def list_comments(self, request):
        target_type = request.query_params.get('target_type')
        target_id = request.query_params.get('target_id')

        if not target_type or not target_id:
            return Response({'error': 'Faltan parámetros: target_type o target_id'}, status=status.HTTP_400_BAD_REQUEST)

        # Mapeo de tipos hacia los modelos nativos
        model_map = {
            'product': 'inventoryitem',
            'video': 'companyvideostory'
        }
        
        content_model = model_map.get(target_type)
        if not content_model:
            return Response({'error': 'Tipo de contenido no soportado.'}, status=status.HTTP_400_BAD_REQUEST)

        content_type_obj = ContentType.objects.get(model=content_model)
        
        # Filtramos por el tipo y el ID (Usamos select_related genérico si es necesario)
        comments = UniversalComment.objects.filter(
            content_type=content_type_obj,
            object_id=target_id
        ).select_related('client').order_by('-question_creation')

        paginator = UniversalConversationPagination()
        paginated_qs = paginator.paginate_queryset(comments, request)

        data = [q.get_json() for q in paginated_qs]
        return paginator.get_paginated_response(data)

    @action(detail=False, methods=['post'])
    def add_comment(self, request):
        target_type = request.data.get('target_type')
        target_id = request.data.get('target_id')
        question_text = request.data.get('question_text')

        if not target_type or not target_id or not question_text:
            return Response({'error': 'Faltan parámetros.'}, status=status.HTTP_400_BAD_REQUEST)

        clean_text = question_text.strip()
        if not clean_text:
            return Response({'error': 'El comentario no puede estar vacío.'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            try:
                if target_type == 'product':
                    target_obj = InventoryItem.objects.select_related('store__company__owner', 'product').get(id=target_id, paused=False)
                    owner_id = target_obj.store.company.owner.id
                    item_name = target_obj.product.name
                elif target_type == 'video':
                    target_obj = CompanyVideoStory.objects.select_related('company__owner').get(id=target_id)
                    owner_id = target_obj.company.owner.id
                    item_name = "tu Video Historia"
                else:
                    raise ValueError("Tipo inválido")
            except (InventoryItem.DoesNotExist, CompanyVideoStory.DoesNotExist, ValueError):
                return Response({'error': 'El contenido no existe o fue retirado.'}, status=status.HTTP_404_NOT_FOUND)

            content_type_obj = ContentType.objects.get_for_model(target_obj)
            
            comment = UniversalComment.objects.create(
                client=request.user,
                content_type=content_type_obj,
                object_id=target_id,
                question_text=clean_text
            )

            # Notificamos al dueño
            firebase_admin.NotificationManager.notify_new_question(
                merchant_user_id=owner_id,
                item_name=item_name,
                item_id=target_id,
                question_id=comment.id 
            )
            return Response({'message': 'Comentario enviado con éxito.', 'data': comment.get_json()}, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'])
    def answer_comment(self, request):
        question_id = request.data.get('question_id')
        answer_text = request.data.get('answer_text')

        if not question_id or not answer_text:
            return Response({'error': 'Faltan parámetros.'}, status=status.HTTP_400_BAD_REQUEST)

        clean_text = answer_text.strip()
        if not clean_text:
            return Response({'error': 'La respuesta no puede estar vacía.'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            try:
                comment = UniversalComment.objects.get(id=question_id)
            except UniversalComment.DoesNotExist:
                return Response({'error': 'La pregunta no existe.'}, status=status.HTTP_404_NOT_FOUND)

            # Extraemos dinámicamente al dueño para verificar permisos
            owner = None
            company_name = ""
            item_name = ""
            
            if comment.content_type.model == 'inventoryitem':
                owner = comment.content_object.store.company.owner
                company_name = comment.content_object.store.company.name
                item_name = comment.content_object.product.name
            elif comment.content_type.model == 'companyvideostory':
                owner = comment.content_object.company.owner
                company_name = comment.content_object.company.name
                item_name = "tu Video"

            if owner != request.user:
                return Response({'error': 'No tienes permisos para responder.'}, status=status.HTTP_403_FORBIDDEN)

            if comment.answer_text is not None:
                return Response({'error': 'Esta pregunta ya fue respondida.'}, status=status.HTTP_400_BAD_REQUEST)

            comment.answer_text = clean_text
            comment.answer_creation = timezone.now()
            comment.save()

            # En UniversalConversationViewSet.answer_comment, al llamar a notify_new_answer:
            item_type = 'product' if comment.content_type.model == 'inventoryitem' else 'video'
            
            firebase_admin.NotificationManager.notify_new_answer(
                user_id=comment.client.id,
                company_name=company_name,
                item_name=item_name,
                item_id=comment.object_id,
                target_type=item_type
            )

            return Response({'success': True, 'message': 'Respuesta enviada.', 'data': comment.get_json()}, status=status.HTTP_200_OK)
        
    @action(detail=False, methods=['get'], url_path='single-feed-post')
    def single_feed_post(self, request):
        """
        Recupera un solo elemento (Producto o Video) y lo empaqueta con el
        formato exacto del Home Feed para inyecciones dinámicas en Flutter
        cuando el usuario entra desde una notificación push.
        """
        target_id = request.query_params.get('target_id')
        target_type = request.query_params.get('target_type')

        if not target_id or not target_type:
            return Response({'error': 'Faltan parámetros target_id o target_type.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if target_type == 'product':
                # 💡 Buscamos el ítem asegurándonos de que no esté pausado
                item = InventoryItem.objects.select_related('product', 'store__company').get(id=target_id, paused=False)
                
                # 💡 Empaquetamos igual que tu Feed
                data = item.get_json()
                data['feed_type'] = 'product' 
                
                return Response({'data': data}, status=status.HTTP_200_OK)

            elif target_type == 'video':
                video = CompanyVideoStory.objects.select_related('company', 'associated_item').get(id=target_id)
                
                # 💡 Verificamos que el video no haya expirado
                if not video.is_media_available:
                    return Response({'error': 'El video expiró o fue eliminado.'}, status=status.HTTP_404_NOT_FOUND)

                data = video.get_json()
                data['feed_type'] = 'video'
                
                return Response({'data': data}, status=status.HTTP_200_OK)

            else:
                return Response({'error': 'Tipo de contenido no soportado.'}, status=status.HTTP_400_BAD_REQUEST)

        except InventoryItem.DoesNotExist:
            return Response({'error': 'El producto no existe o fue retirado.'}, status=status.HTTP_404_NOT_FOUND)
        except CompanyVideoStory.DoesNotExist:
            return Response({'error': 'El video no existe o fue retirado.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
class ProductSearchEngineViewSet(viewsets.ViewSet):
    """
    API integral para la distribución algorítmica de productos hacia la App.
    Interactúa con el ProductSearchEngine para retornar Feeds dinámicos cacheados
    respetando exactamente las firmas de respuesta requeridas por Flutter.
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

    def _get_pagination_params(self, request):
        """Extrae de forma segura los parámetros de paginación con fallbacks."""
        try:
            page = int(request.query_params.get('page', 1))
            page_size = int(request.query_params.get('page_size', 20))
        except ValueError:
            page, page_size = 1, 20
        return page, page_size

    def _paginate_and_respond(self, data_list: list, request) -> Response:
        """
        [OBSOLETO PARA FEEDS PRINCIPALES - Mantenido por retrocompatibilidad]
        Paginación O(1) en RAM que imita la estructura CursorPagination de DRF.
        """
        page, page_size = self._get_pagination_params(request)

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

    def _respond_pre_sliced_data(self, data_list: list, request, page: int, page_size: int) -> Response:
        """
        Paginador optimizado para feeds.
        Asume que la lista ya fue rebanada nativamente en SQL (Limit/Offset).
        """
        has_next = len(data_list) == page_size
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
            'results': data_list
        }, status=status.HTTP_200_OK)

    # ------------------------------------------------------------------------
    # ENDPOINTS
    # ------------------------------------------------------------------------
    @action(detail=False, methods=['get'])
    def category(self, request):
        sub_category_id = request.query_params.get('sub_category_id')
        lat, lng = self._get_coordinates(request)
        sort_by, price_order = self._get_sorting_params(request)
        page, page_size = self._get_pagination_params(request)

        if not sub_category_id or lat is None or lng is None:
            return Response({'error': 'Faltan parámetros'}, status=status.HTTP_400_BAD_REQUEST)

        engine = ProductSearchEngine(lat, lng, user=request.user)
        data_list = engine.get_category_feed(
            sub_category_id=sub_category_id, page=page, page_size=page_size, 
            sort_by=sort_by, price_order=price_order
        )

        return self._respond_pre_sliced_data(data_list, request, page, page_size)

    @action(detail=False, methods=['get'])
    def store(self, request):
        store_id = request.query_params.get('store_id')
        company_id = request.query_params.get('company_id')
        category_id = request.query_params.get('category_id')
        lat, lng = self._get_coordinates(request)
        _, price_order = self._get_sorting_params(request)
        page, page_size = self._get_pagination_params(request)

        if (not store_id and not company_id) or lat is None or lng is None:
            return Response(
                {'error': 'Faltan parámetros obligatorios: store_id o company_id, lat, lng'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        engine = ProductSearchEngine(lat, lng, user=request.user)
        data_list = engine.get_store_feed(
            page=page, page_size=page_size,
            store_id=store_id, 
            company_id=company_id,
            category_id=category_id,
            price_order=price_order
        )
        
        return self._respond_pre_sliced_data(data_list, request, page, page_size)

    @action(detail=False, methods=['get'])
    def offers(self, request):
        lat, lng = self._get_coordinates(request)
        sort_by, price_order = self._get_sorting_params(request)
        page, page_size = self._get_pagination_params(request)
        is_home_widget = request.query_params.get('home_widget', 'false').lower() == 'true'

        if lat is None or lng is None:
            return Response({'error': 'Faltan parámetros obligatorios: lat, lng'}, status=status.HTTP_400_BAD_REQUEST)

        engine = ProductSearchEngine(lat, lng, user=request.user)
        data_list = engine.get_offers_feed(page=page, page_size=page_size, sort_by=sort_by, price_order=price_order)

        if is_home_widget:
            top_10 = data_list[:10]
            return Response({'results': top_10}, status=status.HTTP_200_OK)
            
        return self._respond_pre_sliced_data(data_list, request, page, page_size)

    @action(detail=False, methods=['get'])
    def stores_with_tokens(self, request):
        lat, lng = self._get_coordinates(request)
        page, page_size = self._get_pagination_params(request)
        is_home_widget = request.query_params.get('home_widget', 'false').lower() == 'true'

        if lat is None or lng is None:
            return Response({'error': 'Faltan parámetros obligatorios: lat, lng'}, status=status.HTTP_400_BAD_REQUEST)

        engine = ProductSearchEngine(lat, lng, user=request.user)
        data_list = engine.get_stores_with_tokens_feed(page=page, page_size=page_size)

        if is_home_widget:
            top_10 = data_list[:10]
            # Mantenemos consistencia con la respuesta de 'favorites'
            return Response({'data': {'results': top_10}}, status=status.HTTP_200_OK)
            
        return self._respond_pre_sliced_data(data_list, request, page, page_size)

    @action(detail=False, methods=['get'])
    def text_search(self, request):
        search_query = request.query_params.get('q', '')
        lat, lng = self._get_coordinates(request)
        sort_by, price_order = self._get_sorting_params(request)
        page, page_size = self._get_pagination_params(request)
        
        try:
            max_distance = float(request.query_params.get('max_distance', 10000))
        except ValueError:
            max_distance = 10000

        if not search_query or lat is None or lng is None:
            return Response({'error': 'Faltan parámetros obligatorios: q, lat, lng'}, status=status.HTTP_400_BAD_REQUEST)

        engine = ProductSearchEngine(lat, lng, user=request.user)
        data_list = engine.get_text_search_feed(
            search_query=search_query, page=page, page_size=page_size,
            sort_by=sort_by, price_order=price_order,
            max_distance_meters=max_distance
        )

        if len(data_list) == 0 and search_query:
            payload = {
                'client_id': str(request.user.id) if request.user.is_authenticated else None,
                'search_term': search_query,
                'lat': lat,
                'lng': lng,
                'timestamp': timezone.now().isoformat()
            }
            try:
                redis_conn = cache.client.get_client()
                redis_conn.rpush("telemetry:unmet_demand", json.dumps(payload))
            except Exception as e:
                print(f"Error registrando demanda insatisfecha: {e}")

        return self._respond_pre_sliced_data(data_list, request, page, page_size)

    @action(detail=False, methods=['get'])
    def home_feed(self, request):
        lat, lng = self._get_coordinates(request)
        # 💡 Capturamos la semilla enviada por Flutter
        seed = request.query_params.get('seed', 'default_seed')
        
        if lat is None or lng is None:
            return Response({'error': 'Faltan coordenadas'}, status=status.HTTP_400_BAD_REQUEST)

        page, page_size = self._get_pagination_params(request)

        # 🕵️ ESPÍA 1: ¿Flutter nos está mandando una semilla distinta cada vez?
        print(f"\n=======================================================")
        print(f"🚀 [ENDPOINT HOME] Request -> Page: {page} | Semilla recibida: {seed}")
        print(f"=======================================================")

        # 💡 Le pasamos la semilla al motor
        engine = ProductSearchEngine(lat, lng, user=request.user, seed=seed)
        data_list = engine.get_home_feed(page=page, page_size=page_size)
        
        return self._respond_pre_sliced_data(data_list, request, page, page_size)
        
    @action(detail=False, methods=['get'])
    def favorites(self, request):
        lat, lng = self._get_coordinates(request)
        sort_by, price_order = self._get_sorting_params(request)
        page, page_size = self._get_pagination_params(request)
        is_home_widget = request.query_params.get('home_widget', 'false').lower() == 'true'

        if lat is None or lng is None:
            return Response({'error': 'Faltan parámetros obligatorios: lat, lng'}, status=status.HTTP_400_BAD_REQUEST)

        engine = ProductSearchEngine(lat, lng, user=request.user)
        data_list = engine.get_favorites_feed(page=page, page_size=page_size, sort_by=sort_by, price_order=price_order)

        if is_home_widget:
            top_10 = data_list[:10]
            return Response({'data': {'results': top_10}}, status=status.HTTP_200_OK)
    
        return self._respond_pre_sliced_data(data_list, request, page, page_size)

    # ------------------------------------------------------------------------
    # MÉTODOS SIN PAGINACIÓN (Item Details y Toggle Like)
    # ------------------------------------------------------------------------
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
            data['is_owner'] = item.product.company.id == request.user.company.id \
                if (request.user.is_authenticated and hasattr(request.user, 'company')) else False
            
            
            user_tokens = 0
            if request.user.is_authenticated:
                try:
                    from api.models import TokenWallet
                    wallet = TokenWallet.objects.only('balance').get(
                        user=request.user, 
                        company=item.store.company
                    )
                    user_tokens = wallet.balance
                except TokenWallet.DoesNotExist:
                    user_tokens = 0
            
            data['user_wallet_balance'] = user_tokens
            
            return Response({'success': True, 'data': data}, status=status.HTTP_200_OK)
            
        except InventoryItem.DoesNotExist:
            return Response({'error': 'El producto no existe o fue retirado.'}, status=status.HTTP_404_NOT_FOUND)

    # ------------------------------------------------------------------------
    # MÉTODOS SIN PAGINACIÓN (Item Details y Toggle Universal Like)
    # ------------------------------------------------------------------------
    @action(detail=False, methods=['post'])
    def toggle_like(self, request):
        target_type = request.data.get('target_type')
        target_id = request.data.get('target_id')

        if not target_type or not target_id:
            return Response({'error': 'Faltan parámetros: target_type, target_id'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if target_type == 'product':
                target_obj = InventoryItem.objects.get(id=target_id, paused=False)
            elif target_type == 'video':
                target_obj = CompanyVideoStory.objects.get(id=target_id)
            else:
                return Response({'error': 'Tipo no soportado.'}, status=status.HTTP_400_BAD_REQUEST)
        except (InventoryItem.DoesNotExist, CompanyVideoStory.DoesNotExist):
            return Response({'error': 'El contenido no existe.'}, status=status.HTTP_404_NOT_FOUND)

        content_type_obj = ContentType.objects.get_for_model(target_obj)

        like, created = UniversalLike.objects.get_or_create(
            user=request.user,
            content_type=content_type_obj,
            object_id=target_id
        )

        if not created:
            like.delete()
            # Contamos cuántos likes quedaron tras eliminar
            total_likes = UniversalLike.objects.filter(content_type=content_type_obj, object_id=target_id).count()
            return Response({'success': True, 'is_liked': False, 'total_likes': total_likes}, status=status.HTTP_200_OK)
        
        total_likes = UniversalLike.objects.filter(content_type=content_type_obj, object_id=target_id).count()
        return Response({'success': True, 'is_liked': True, 'total_likes': total_likes}, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def mark_video_as_viewed(self, request, pk=None):
        try:
            video = CompanyVideoStory.objects.get(pk=pk)
            # 💡 get_or_create usando VideoEngagementLog
            # Esto registra que el usuario ha interactuado con el video
            VideoEngagementLog.objects.get_or_create(
                client=request.user, 
                video=video
            )
            return Response({'status': 'viewed'}, status=status.HTTP_200_OK)
        except CompanyVideoStory.DoesNotExist:
            return Response({'error': 'Historia no encontrada'}, status=status.HTTP_404_NOT_FOUND)

class AtlasViewSet(viewsets.ViewSet):
    """
    API integral para todas las interacciones con Atlas (IA de CartMaker).
    """
    permission_classes = [IsAuthenticated]

    # 💡 LÍMITE DIARIO CONFIGURABLE
    DAILY_FREE_LIMIT = 15

    def _get_user_plan(self, user):
        try:
            return user.atlas_plan
        except AtlasPlusPlan.DoesNotExist:
            return None

    def _create_thread(self, plan):
        return AtlasThread.objects.create(plan=plan)

    # =========================================================================
    # LÓGICA DE CUOTA CON CACHE-ASIDE (PostgreSQL como fuente de verdad)
    # =========================================================================
    def _get_daily_limit(self, user) -> int:
        """Devuelve el límite de interacciones según el Tier del usuario."""
        config = SystemConfig.objects.latest('creation')
        try:
            plan = user.atlas_plan
            # Si es Premium y el plan no ha vencido
            if plan.tier == AtlasSubscriptionTier.PREMIUM and plan.valid_until and plan.valid_until >= timezone.now():
                return config.atlas_plus_daily_limit
        except AtlasPlusPlan.DoesNotExist:
            pass
        return config.atlas_free_daily_limit

    def _get_used_today(self, user) -> int:
        """Obtiene el consumo desde Redis, o lo reconstruye desde BD si se reinició el servidor."""
        cache_key = f"cartmaker:atlas:daily_usage:{user.id}"
        used = cache.get(cache_key)
        
        if used is None:
            # 💡 CACHE MISS: Redis se reinició o es el primer mensaje del día.
            # Vamos a la base de datos a buscar la verdad absoluta.
            now_local = timezone.localtime(timezone.now())
            
            try:
                plan = user.atlas_plan
                used = AtlasMessage.objects.filter(
                    conversation__plan=plan,
                    origin=1, # Contamos solo los mensajes enviados por el usuario
                    creation__date=now_local.date()
                ).count()
            except Exception:
                used = 0
                
            # Calculamos los segundos exactos que faltan para la medianoche local
            tomorrow = (now_local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            timeout = int((tomorrow - now_local).total_seconds())
            
            # Repoblamos Redis
            cache.set(cache_key, used, timeout=timeout)
            
        return used

    def _get_free_interactions_left(self, user) -> int:
        limit = self._get_daily_limit(user)
        used = self._get_used_today(user)
        return max(0, limit - used)

    def _consume_free_interaction(self, user) -> bool:
        limit = self._get_daily_limit(user)
        used = self._get_used_today(user)
        
        if used >= limit:
            return False 
            
        cache_key = f"cartmaker:atlas:daily_usage:{user.id}"
        
        if used == 0:
            now_local = timezone.localtime(timezone.now())
            tomorrow = (now_local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            timeout = int((tomorrow - now_local).total_seconds())
            cache.set(cache_key, 1, timeout=timeout)
        else:
            cache.incr(cache_key)
            
        return True

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
            if filename.endswith('.xlsx') or filename.endswith('.xls'):
                wb = openpyxl.load_workbook(io.BytesIO(excel_file.read()), data_only=True)
                sheet = wb.active
                headers = [str(cell.value) if cell.value is not None else f"Col_{idx}" for idx, cell in enumerate(sheet[1])]
                
                for row in sheet.iter_rows(min_row=2, values_only=True):
                    if any(cell is not None for cell in row):
                        row_dict = {headers[idx]: str(val) if val is not None else "" for idx, val in enumerate(row) if idx < len(headers)}
                        raw_rows.append(row_dict)
            else:
                decoded_file = excel_file.read().decode('utf-8-sig').splitlines()
                reader = csv.DictReader(decoded_file)
                for row in reader:
                    raw_rows.append(dict(row))

            raw_rows = raw_rows[:50] 

        except Exception as e:
            print(f"[PARSING ERROR]: {e}")
            return Response({'error': 'Error al procesar la estructura del archivo.'}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        atlas_manager = atlas.AtlasManager()
        resultado = async_to_sync(atlas_manager.analyze_processed_json_products_async)(raw_rows)
        
        if "error" in resultado and not resultado.get("products"):
            return Response(resultado, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
            
        return Response(resultado, status=status.HTTP_200_OK)

    # ------------------------------------------------------------------------
    # ENDPOINT: GET /api/v1/atlas/current_thread/
    # ------------------------------------------------------------------------
    @action(detail=False, methods=['get'])
    def current_thread(self, request):
        plan = request.user.atlas_plan 
        is_premium = plan.tier == AtlasSubscriptionTier.PREMIUM and plan.valid_until and plan.valid_until >= timezone.now()
        free_left = self._get_free_interactions_left(request.user)
        
        latest_thread = AtlasThread.objects.filter(plan=plan).order_by('-id').first()
        
        if not latest_thread:
            # 1. Creamos el hilo nuevo
            latest_thread = AtlasThread.objects.create(plan=plan)
            
            # Extraemos el nombre del usuario (o usamos un genérico si no lo ha configurado)
            nombre_usuario = request.user.first_name if request.user.first_name else "mi pana"
            
            # 💡 2. BANCO DE SALUDOS INICIALES DINÁMICOS (Anti-bot)
            saludos_templates = [
                f"¡Epa, {nombre_usuario}! Qué fino tenerte por aquí. Soy Atlas. Dime qué andas buscando hoy y te lo consigo en las tiendas de tu zona en un dos por tres.",
                f"¡Hola, {nombre_usuario}! Por aquí Atlas. Vengo a resolverte la vida con las compras. ¿Qué te hace falta hoy para buscártelo de una?",
                f"¡Qué más, {nombre_usuario}! Te saluda Atlas. Estoy activo para cuadrarte las mejores ofertas y productos cerca de ti. ¿Por dónde empezamos?",
                f"¡Epa, {nombre_usuario}! ¿Cómo va todo? Soy Atlas, tu contacto directo con los comercios de la zona. Cuéntame, ¿qué tienes en mente comprar hoy?",
                f"¡Hola, {nombre_usuario}! Aquí Atlas reportándose. Estoy listo para rastrear el inventario de la zona y conseguirte exactamente lo que necesitas. ¿Qué buscas hoy?",
                f"¡Qué bueno verte por acá, {nombre_usuario}! Soy Atlas. Si estás buscando algo específico o solo quieres ver qué hay de bueno en las tiendas hoy, avísame y nos movemos."
            ]
            
            # Selección aleatoria
            mensaje_bienvenida = random.choice(saludos_templates)
            
            # Lo guardamos como si fuera una respuesta generada por la IA (origin=2)
            AtlasMessage.objects.create(
                conversation=latest_thread,
                origin=2, # 2 es tu constante ORIGIN_AI en AtlasManager
                text=mensaje_bienvenida,
                product_ids=[]
            )
            
        # 💡 FEATURE: PAGINACIÓN (Por defecto carga 15 mensajes)
        try:
            offset = int(request.query_params.get('offset', 0))
        except ValueError:
            offset = 0
        limit = 15

        # Obtenemos de más nuevo a más viejo para aplicar el slice exacto
        messages_qs = AtlasMessage.objects.filter(conversation=latest_thread).order_by('-creation')[offset:offset+limit]
        
        # Invertimos la lista de nuevo para entregar en orden cronológico (Viejo -> Nuevo)
        messages_list = list(messages_qs)[::-1]

        # 💡 FEATURE: HIDRATACIÓN DE PRODUCTOS EN TIEMPO REAL
        all_product_ids = set()
        for m in messages_list:
            if getattr(m, 'product_ids', None):
                all_product_ids.update(m.product_ids)

        items_dict = {}
        if all_product_ids:
            # Traemos la info viva para respetar el stock actual y pausas
            fresh_items = InventoryItem.objects.filter(id__in=all_product_ids).select_related('product', 'store__company')
            for item in fresh_items:
                items_dict[str(item.id)] = item.get_json()

        messages_data = []
        for m in messages_list:
            msg_type = 'text'
            msg_products = []
            
            p_ids = getattr(m, 'product_ids', [])
            if p_ids:
                msg_type = 'products'
                for pid in p_ids:
                    if pid in items_dict:
                        msg_products.append(items_dict[pid])
                    else:
                        # Fallback: El item fue borrado o no existe
                        msg_products.append({"id": pid, "paused": True, "stock": 0})

            # 💡 Aseguramos la integridad del JSON
            cmd = getattr(m, 'action_command', None)
            if isinstance(cmd, str):
                try:
                    cmd = json.loads(cmd)
                except:
                    cmd = None

            messages_data.append({
                "id": m.id,
                "origin": m.origin, 
                "text": m.text,
                "type": msg_type,
                "products": msg_products if msg_products else None,
                "creation": m.creation.isoformat(),
                "action_command": cmd # 💡 Usamos la variable limpia
            })

        return Response({
            'thread_id': latest_thread.id,
            'free_interactions_left': free_left,
            'is_premium': is_premium,
            'messages': messages_data
        }, status=status.HTTP_200_OK)

    # ------------------------------------------------------------------------
    # ENDPOINT: POST /api/v1/atlas/{id}/message/
    # ------------------------------------------------------------------------
    @action(detail=True, methods=['post'])
    def message(self, request, pk=None):
        text = request.data.get('text')
        # 💡 EXTRAEMOS LA FOTO EN BASE64 DESDE EL JSON (Si existe)
        image_base64 = request.data.get('image_base64')
        
        if not text:
            return Response({'error': 'El texto del mensaje es obligatorio.'}, status=status.HTTP_400_BAD_REQUEST)
            
        plan = request.user.atlas_plan
        is_premium = plan.tier == AtlasSubscriptionTier.PREMIUM and plan.valid_until and plan.valid_until >= timezone.now()
        
        # 💡 FIX: Consumimos la interacción para TODOS. 
        # La función _consume_free_interaction ya sabe si el límite es 15 o 75.
        if not self._consume_free_interaction(request.user):
            mensaje_error = 'Has agotado tus interacciones de Atlas Plus por hoy.' if is_premium else 'Has agotado tus interacciones gratuitas por hoy.'
            return Response({
                'error': mensaje_error,
                'free_interactions_left': 0
            }, status=status.HTTP_403_FORBIDDEN)
        
        lat = float(request.data.get('lat', 0.0))
        lng = float(request.data.get('lng', 0.0))
        user_locations = request.data.get('locations', [])
        
        atlas_manager = atlas.AtlasManager(
            user_lat=lat, 
            user_lng=lng, 
            user_locations=user_locations, 
            user=request.user, 
            seed=str(pk)
        )

        # 💡 PASAMOS LA FOTO AL MOTOR DE ATLAS
        resultado = async_to_sync(atlas_manager.send_chat_message_async)(thread_id=pk, user_text=text, image_base64=image_base64)
        
        if not resultado.get('success'):
            if not is_premium:
                try: cache.decr(f"cartmaker:atlas:daily_usage:{request.user.id}")
                except: pass
            return Response({'error': resultado.get('error')}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        free_left = self._get_free_interactions_left(request.user)
            
        # 💡 Nos aseguramos de imprimir para debuguear si está saliendo bien
        print(f"📦 [VIEWS] Comando enviado al Frontend: {resultado.get('action_command')}")
            
        return Response({
            'response': resultado['response'],
            'message_id': resultado['message_id'],
            'free_interactions_left': free_left,
            'injected_products': resultado.get('injected_products'),
            'action_command': resultado.get('action_command') # <-- Esto es crucial
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

                store = CompanyStore.objects.select_related('company').get(id=store_id, company__owner=request.user)
                product = Product.objects.select_related('company').get(id=product_id, company__owner=request.user)

                # Procesamos la fecha de caducidad usando nuestra función flexible
                exp_datetime = None
                if expiration_date_raw:
                    parsed_date = parse_flexible_date(expiration_date_raw)
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
                InventoryItemTransaction.objects.create(
                    item=item,
                    units=int(stock),
                    transaction_type=TransactionType.CREATION
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
        
    @action(detail=True, methods=['post'])
    def restock(self, request, pk=None):
        item = self.get_object()
        units_raw = request.data.get('units')

        try:
            units = int(units_raw)
            if units <= 0:
                return Response({'error': {'error': 'La cantidad a reponer debe ser mayor a cero.'}}, status=status.HTTP_400_BAD_REQUEST)
        except (ValueError, TypeError):
            return Response({'error': {'error': 'Cantidad inválida.'}}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                # 1. Actualizamos el stock
                item.stock += units
                
                # NO SE LIMPIA EL SOLD OUT TIME PORQUE AYUDA A SABER LA ULTIMA VEZ QUE SE AGOTO...
                # # 2. Si estaba agotado y ahora tiene stock, limpiamos el 'sold_out_time'
                # if item.stock > 0 and item.sold_out_time is not None:
                #     item.sold_out_time = None
                item.creation = timezone.now()
                item.save()

                # 3. Registramos el movimiento en el historial
                # 💡 IMPORTANTE: Reemplaza el '1' por el valor que corresponda a "Entrada/Reposición"
                # en tu clase TransactionType (ej. TransactionType.REPOSICION)
                from .models import InventoryItemTransaction # Ajusta la ruta si es necesario
                InventoryItemTransaction.objects.create(
                    item=item,
                    units=units,
                    transaction_type=1 
                )

            item.refresh_from_db()
            return Response({'success': True, 'data': item.get_json()}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'success': False, 'error': {'error': str(e)}}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'navigation'
    
    # Fundamental para recibir tanto el JSON de datos como las imágenes físicas
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    def get_queryset(self):
        # Aseguramos que el usuario solo pueda interactuar con los productos de su compañía
        return Product.objects.select_related('company').filter(company__owner=self.request.user).order_by('-creation')
    
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

    @action(detail=False, methods=['post'])
    def bulk_delete(self, request):
        """
        Recibe una lista de IDs y elimina los productos masivamente.
        """
        product_ids = request.data.get('product_ids', [])
        if not product_ids or not isinstance(product_ids, list):
            return Response({'error': 'Se requiere una lista de IDs de productos válidos.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                # Filtramos para asegurar que pertenezcan al usuario dueño de la compañía
                products_to_delete = Product.objects.select_related('company').filter(id__in=product_ids, company__owner=request.user)
                
                # Borramos las imágenes del storage iterando la consulta evaluada
                for product in products_to_delete:
                    for img in product.images:
                        try:
                            storage_manager.delete_file(img)
                        except Exception as e:
                            print(f"Error borrando imagen en bulk_delete: {e}")
                
                # Eliminación masiva a nivel de BD
                deleted_count, _ = products_to_delete.delete()

            return Response({'success': True, 'deleted_count': deleted_count}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class NotificationViewSet(viewsets.GenericViewSet, mixins.ListModelMixin):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # IMPORTANTE: Ordenamos para que las más nuevas salgan primero
        return Notification.objects.filter(user=self.request.user).order_by('-created_at')

    @action(detail=False, methods=['post'], url_path="mark-section-as-read")
    def mark_section_as_read(self, request):
        section = request.data.get('section')
        if section is None:
            return Response({"detail": "Falta la sección."}, status=status.HTTP_400_BAD_REQUEST)
            
        # 💡 Bulk update: Actualiza todas las no leídas de esta sección a True
        updated_count = self.get_queryset().filter(section=section, is_read=False).update(is_read=True)
        
        return Response({"updated_count": updated_count, "detail": "Sección marcada como leída."}, status=status.HTTP_200_OK)

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