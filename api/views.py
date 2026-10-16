import csv
import hashlib
import io
import json
import re
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
import random
import secrets
from django.contrib.auth.hashers import check_password
from .cos import storage_manager
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from datetime import datetime, timedelta
import requests
from django.db import transaction
from .core import *
from django.core.cache import cache
from django.utils import timezone
from .tasks import *
from django.contrib.gis.geos import Polygon, Point
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .utils import parse_flexible_date, validate_venezuelan_rif_modulo11
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
    permission_classes = [IsAuthenticated]
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
    Endpoint para autenticación mediante vectores biométricos de 512 dimensiones.
    Soporta:
    - Modo 1:1 (si el cliente envía 'user_id' o 'email' vinculado al dispositivo).
    - Modo 1:N con blindaje matemático: Normalización L2 en S^511, umbral estricto (<= 0.26)
      y prueba de margen contra el 2.do vecino más cercano (Lowe's Margin >= 0.08).
    """
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'

    def post(self, request):
        raw_vector = request.data.get('biometry')
        is_valid_vec, vector, vec_error = normalize_biometric_vector(
            raw_vector, expected_dim=BIOMETRIC_VECTOR_DIMENSIONS
        )
        if not is_valid_vec:
            return Response(
                {"error": vec_error or "Vector biométrico inválido o incompleto."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        target_user_id = request.data.get('user_id')
        target_email = (request.data.get('email') or '').strip()

        base_qs = User.objects.filter(
            cedula_verified=True,
            biometric_vector__isnull=False,
            is_active=True,
        ).annotate(
            distance=CosineDistance('biometric_vector', vector)
        )

        # Modo 1:1 (si el cliente indica la cuenta esperada) vs Modo 1:N global
        is_one_to_one = bool(target_user_id or target_email)
        if target_user_id:
            base_qs = base_qs.filter(id=target_user_id)
        elif target_email:
            base_qs = base_qs.filter(email__iexact=target_email)

        top_matches = list(base_qs.order_by('distance')[:2])
        if not top_matches:
            return Response(
                {'error': "Identidad biométrica no reconocida o no registrada."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        closest_user = top_matches[0]
        if closest_user.is_superuser:
            return Response(
                {'error': "No se permite acceso biométrico a cuentas administrativas."},
                status=status.HTTP_406_NOT_ACCEPTABLE,
            )

        effective_threshold = (
            BIOMETRIC_LOGIN_THRESHOLD_1TO1
            if is_one_to_one
            else BIOMETRIC_LOGIN_THRESHOLD_ACCEPTABLE
        )

        print("USUARIO OBTENIDO (512-D): ", closest_user)
        print("CLOSEST USER DISTANCE: ", closest_user.distance)

        if closest_user.distance is None or closest_user.distance > effective_threshold:
            return Response(
                {"error": "Identidad no verificada. Por favor, asegúrese de tener buena iluminación o no usar accesorios."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # En búsqueda global 1:N, exigimos margen claro respecto al 2.do usuario más parecido
        if not is_one_to_one and len(top_matches) > 1:
            second_user = top_matches[1]
            if second_user.distance is not None:
                margin = second_user.distance - closest_user.distance
                if margin < BIOMETRIC_LOGIN_MIN_MARGIN:
                    print(
                        f"🚨 LOGIN BIOMÉTRICO RECHAZADO POR AMBIGÜEDAD: "
                        f"Top1={closest_user.distance:.4f}, Top2={second_user.distance:.4f}, Margen={margin:.4f}"
                    )
                    return Response(
                        {"error": "Coincidencia biométrica ambigua. Por seguridad, inicie sesión con su correo y contraseña."},
                        status=status.HTTP_401_UNAUTHORIZED,
                    )

        # Solo adaptamos el rolling template cuando la coincidencia es de altísima confianza (<= 0.18),
        # evitando contaminar el vector con capturas dudosas o de terceros.
        if 0.06 <= closest_user.distance <= BIOMETRIC_LOGIN_THRESHOLD_PERFECT:
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
            'preferred_category_ids': closest_user.get_preferred_category_ids(),
        }, status=status.HTTP_200_OK)

class CartMakerTokenView(TokenObtainPairView):
    """
    Vista personalizada para el login que devuelve datos extendidos del perfil.
    """
    permission_classes = [AllowAny]
    serializer_class = CartMakerTokenSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'

class GoogleClientId(APIView):
    """
    API para obtener el Google Client Id.
    """
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'

    def get(self, request):
        return Response({"google_client_id":settings.GOOGLE_OAUTH_CLIENT_ID}, status=200)
    
class GoogleRegistView(APIView):
    """
    API para el registro de usuarios a traves de Google OAuth.
    """
    permission_classes = [AllowAny]
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
            user = User.objects.create_user(
                email=email,
                password=random_password,
                first_name=first_name,
                last_name=last_name,
                profile_picture=profile_pic,
                email_verified=True,
                is_external_account=True
            )
            raw_cat_ids = request.data.get('category_ids') or request.data.get('preferred_category_ids')
            if isinstance(raw_cat_ids, list) and raw_cat_ids:
                valid_cats = Category.objects.filter(id__in=[int(cid) for cid in raw_cat_ids if str(cid).isdigit()])
                user.preferred_categories.set(valid_cats)
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
                "is_external_account":user.is_external_account,
                "preferred_category_ids": user.get_preferred_category_ids(),
            }, status=201)
        except ValueError as e:
            print(e)
            return Response({"error": "Token inválido"}, status=400)

class GoogleLoginView(APIView):
    """
    API para autenticacion con Google OAuth.
    """
    permission_classes = [AllowAny]
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
                "email_verified":True,
                "preferred_category_ids": user.get_preferred_category_ids(),
            }, status=200)
        except ValueError as e:
            print(e)
            return Response({"error": "Token inválido"}, status=400)

class RegisterView(generics.CreateAPIView):
    permission_classes = [AllowAny]
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
        if getattr(request.user, 'cedula_verified', False):
            return Response(
                {"error": "Tu identidad ya se encuentra verificada en CartMaker."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = VerifyUserSerializer(
            data=request.data,
            context={"request": request.user},
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user = request.user
        try:
            file_obj = data['cedula_photo']
            extension = file_obj.name.split('.')[-1]
            file_name = f"cedula_{user.id}.{extension}"
            folder = "identity_verifications"
            cedula_rel_path = storage_manager.save_file(file_obj, folder, file_name)
            if not cedula_rel_path:
                return Response(
                    {"error": "Error al guardar el archivo de la cédula en el servidor."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            selfie_obj = data['selfie_photo']
            selfie_ext = selfie_obj.name.split('.')[-1]
            selfie_name = f"selfie_{user.id}.{selfie_ext}"
            selfie_rel_path = storage_manager.save_file(selfie_obj, folder, selfie_name)
            if not selfie_rel_path:
                return Response(
                    {"error": "Error al guardar la selfie de verificación en el servidor."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            with transaction.atomic():
                locked_user = User.objects.select_for_update().get(pk=user.pk)
                if locked_user.cedula_verified:
                    return Response(
                        {"error": "Tu identidad ya se encuentra verificada en CartMaker."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if User.objects.exclude(pk=locked_user.pk).filter(
                    cedula_number__iexact=data['cedula_number'], is_active=True
                ).exists():
                    return Response(
                        {"error": f"Ya existe un usuario registrado con la cédula {data['cedula_number']}."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                locked_user.cedula_document = cedula_rel_path
                locked_user.first_name = str(data['first_name']).capitalize()
                locked_user.last_name = str(data['last_name']).capitalize()
                locked_user.cedula_number = data['cedula_number']
                locked_user.nacionality = (
                    UserNacionality.VENEZOLANO
                    if str(data['nacionality']).upper() == "V"
                    else UserNacionality.EXTRANJERO
                )
                locked_user.biometric_vector = data['biometry']
                locked_user.birth_date = data['birth_date']
                locked_user.cedula_verified = True
                locked_user.save()
                return Response(
                    {"message": "Identidad confirmada. Ahora eres un usuario verificado en CartMaker."},
                    status=status.HTTP_200_OK,
                )
        except Exception as e:
            print(f"Error al verificar al usuario: {e}")
            return Response(
                {"error": "Hubo un problema al procesar tu verificación. Inténtalo de nuevo."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

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
            products_query = company.products.select_related(
                'category', 'category__parent_category', 'company'
            ).all()
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
            store = CompanyStore.objects.select_related('company').get(id=store_id)
            if store.company.owner_id != request.user.id:
                return Response({'error': 'No tiene permisos para esta sucursal.'}, status=status.HTTP_406_NOT_ACCEPTABLE)

            # 1. Categorías únicas del inventario de esta sucursal
            store_categories = SubCategory.objects.filter(
                product__inventory_items__store=store
            ).distinct().values('id', 'name')

            category_id = request.GET.get('category_id')
            page = request.GET.get('page', 1)
            out_of_stock = request.GET.get('out_of_stock') == 'true'

            # 2. QuerySet base optimizado con select_related
            items_query = InventoryItem.objects.filter(store=store).select_related(
                'product',
                'product__category',
                'product__category__parent_category',
                'product__company',
                'offer',
                'store',
                'store__company',
            )
            
            if category_id:
                items_query = items_query.filter(product__category_id=category_id)
                
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

            # =========================================================
            # 💡 CART-6: CÁLCULO DE NÚMEROS Y MÉTRICAS POR LOTE
            # =========================================================
            current_items_list = list(current_items)
            item_ids = [item.id for item in current_items_list]
            item_ids_str = [str(uid) for uid in item_ids]

            # A. Visualizaciones
            views_qs = ProductViewLog.objects.filter(
                inventory_item_id__in=item_ids
            ).values('inventory_item_id').annotate(total_views=Count('id'))
            views_map = {v['inventory_item_id']: v['total_views'] for v in views_qs}

            # B. Ventas y unidades egresadas
            sales_qs = InventoryItemTransaction.objects.filter(
                item_id__in=item_ids,
                transaction_type=TransactionType.OUTCOME
            ).values('item_id').annotate(
                units_sold=Sum('units'),
                sales_count=Count('id')
            )
            sales_map = {
                s['item_id']: {
                    'units_sold': abs(s['units_sold'] or 0),
                    'sales_count': s['sales_count'] or 0
                } for s in sales_qs
            }

            # C. Likes / Favoritos polimórficos
            item_ct = ContentType.objects.get_for_model(InventoryItem)
            likes_qs = UniversalLike.objects.filter(
                content_type=item_ct,
                object_id__in=item_ids_str
            ).values('object_id').annotate(total_likes=Count('id'))
            likes_map = {l['object_id']: l['total_likes'] for l in likes_qs}

            # D. Preguntas / Comentarios polimórficos
            comments_qs = UniversalComment.objects.filter(
                content_type=item_ct,
                object_id__in=item_ids_str
            ).values('object_id').annotate(total_comments=Count('id'))
            comments_map = {c['object_id']: c['total_comments'] for c in comments_qs}

            items = []
            for item in current_items_list:
                item_json = item.get_json()
                item_id = item.id
                item_str = str(item_id)
                
                views_count = views_map.get(item_id, 0)
                sold_info = sales_map.get(item_id, {'units_sold': 0, 'sales_count': 0})
                units_sold = sold_info['units_sold']
                sales_count = sold_info['sales_count']
                likes_count = likes_map.get(item_str, 0)
                questions_count = comments_map.get(item_str, 0)
                
                unit_price = float(item.custom_price if item.custom_price else item.product.price)
                revenue = round(units_sold * unit_price, 2)
                
                metrics = {
                    'views_count': views_count,
                    'units_sold': units_sold,
                    'sales_count': sales_count,
                    'revenue': revenue,
                    'likes_count': likes_count,
                    'questions_count': questions_count,
                }
                
                item_json['metrics'] = metrics
                item_json['views_count'] = views_count
                item_json['units_sold'] = units_sold
                item_json['revenue'] = revenue
                item_json['likes_count'] = likes_count
                item_json['questions_count'] = questions_count
                
                items.append(item_json)

            return Response({
                'items': items,
                'store_categories': list(store_categories),
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


def _get_cached_bcv_rate(default: float = 0.0, raise_on_failure: bool = False) -> float:
    """
    Obtiene la tasa oficial del BCV desde caché en Redis (TTL 1h) o desde dolarapi.com con timeout estricto.
    """
    cache_key = "cartmaker:global:bcv_rate"
    fallback_key = "cartmaker:global:bcv_rate_fallback"
    cached_rate = cache.get(cache_key)
    if cached_rate is not None:
        return float(cached_rate)

    try:
        response = requests.get('https://ve.dolarapi.com/v1/estado', timeout=4)
        response.raise_for_status()
        data = response.json()
        api_available = data.get('estado') == 'Disponible' if data.get('estado') else False
        if api_available:
            response = requests.get('https://ve.dolarapi.com/v1/dolares/oficial', timeout=4)
            response.raise_for_status()
            data = response.json()
            rate = float(data.get('promedio', default) or default)
            if rate > 0:
                cache.set(cache_key, rate, timeout=3600)
                cache.set(fallback_key, rate, timeout=86400 * 7)
                return rate
    except Exception as e:
        print(f"Error obteniendo el precio del dolar bcv: {e}")
        fallback_rate = cache.get(fallback_key)
        if fallback_rate is not None:
            return float(fallback_rate)
        if raise_on_failure:
            raise

    fallback_rate = cache.get(fallback_key)
    if fallback_rate is not None:
        return float(fallback_rate)
    return float(default)


class GetMerchantPlans(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Devuelve todas los planes disponibles para comerciantes.
        """
        plans = [mp.get_json() for mp in MerchantPlan.objects.all().order_by('price')]
        dollar_bcv_tax = _get_cached_bcv_rate(default=0.0)
        bs_price = 0.0
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
        
        dollar_bcv_tax = _get_cached_bcv_rate(default=1.0)
        bs_price = 0.0

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

        elif subscription_type == 2:
            return Response(
                {'error': 'Vender en CartMaker ya no requiere un plan de pago. Configura tu compañía para empezar.'},
                status=status.HTTP_406_NOT_ACCEPTABLE,
            )


class FullPaySubscriptionWithWalletView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            plan_type = request.data.get('plan_type', 'merchant')
            if plan_type != 'atlas':
                return Response({
                    'success': False,
                    'message': 'Vender en CartMaker ya no requiere un plan de pago. Configura tu compañía para empezar.'
                }, status=status.HTTP_406_NOT_ACCEPTABLE)

            # Obtenemos la tasa BCV FUERA de la transacción atómica para no retener bloqueos de fila durante llamadas de red
            try:
                dollar_bcv_tax = _get_cached_bcv_rate(default=1.0, raise_on_failure=True)
            except Exception as e:
                print(f"Error obteniendo el precio del dolar bcv: {e}")
                return Response({'error': "No se pudo determinar la tasa del dolar."}, status=status.HTTP_423_LOCKED)

            with transaction.atomic():
                wallet = UserWallet.objects.select_for_update().get(user=request.user)

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

                atlas_payment = AtlasPlusPlanPayment.objects.create(
                    plan=atlas_plan,
                    reference_number=f"WALLET-ATLAS-{uuid.uuid4().hex[:6].upper()}",
                    amount=0,
                    bcv_taxes_to_day=dollar_bcv_tax,
                    status=PaymentStatus.APPROVED,
                    verified_at=timezone.now()
                )

                Notification.objects.create(
                    user=request.user,
                    section=NotificationSection.HOME,
                    title="¡Atlas Plus Activo!",
                    body="Tu billetera cubrió la activación. Disfruta de tus 75 interacciones diarias.",
                    category=NotificationCategory.PAYMENT_APPROVED,
                    metadata={'payment_id': str(atlas_payment.id)}
                )

                user_id = request.user.id
                transaction.on_commit(lambda: cache.delete(f"cartmaker:tenant:{user_id}:subscriptions"))

                return Response({
                    'success': True,
                    'message': '¡Atlas Plus activado usando tu saldo a favor!',
                    'data': {'new_balance': float(wallet.balance), 'valid_until': atlas_plan.valid_until.strftime("%d/%m/%Y, %H:%M:%S")}
                }, status=status.HTTP_200_OK)

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
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    serializer_class = CreateCompanySerializer

    @staticmethod
    def _compute_file_sha256(file_obj) -> str:
        file_obj.seek(0)
        hasher = hashlib.sha256()
        if hasattr(file_obj, "chunks"):
            for chunk in file_obj.chunks():
                hasher.update(chunk)
        else:
            hasher.update(file_obj.read())
        file_obj.seek(0)
        return hasher.hexdigest()

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            print("ERRORES DE SERIALIZER:", serializer.errors)
            return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        user = request.user
        if user.user_type == UserType.MERCHANT or Company.objects.filter(owner=user).exists():
            return Response({"error": "Este usuario ya posee una compañia."}, status=status.HTTP_400_BAD_REQUEST)
        company_name = serializer.validated_data["name"].strip()
        comercial_entity_type = serializer.validated_data["comercial_entity_type"]
        store_type = serializer.validated_data["store_type"]
        selected_mall_id = serializer.validated_data.get("selected_mall_id")
        selected_mall_floor = serializer.validated_data.get("selected_mall_floor")
        company_category_id = serializer.validated_data["company_category"]
        lat = serializer.validated_data.get("lat")
        lng = serializer.validated_data.get("lng")
        address = serializer.validated_data.get("address")
        # --- DATOS KYB (SI ES EMPRESA: comercial_entity_type == 1) ---
        rif_number = (serializer.validated_data.get("rif_number") or "").strip()
        razon_social = (serializer.validated_data.get("razon_social") or "").strip()
        mercantil_oficina = (serializer.validated_data.get("mercantil_oficina") or "").strip()
        mercantil_numero = (serializer.validated_data.get("mercantil_numero") or "").strip()
        mercantil_tomo = (serializer.validated_data.get("mercantil_tomo") or "").strip()
        client_rep_cedula = (serializer.validated_data.get("representante_cedula") or "").strip()
        kyb_ocr_verified = serializer.validated_data.get("kyb_ocr_verified", False)
        kyb_confidence_score = serializer.validated_data.get("kyb_confidence_score", 0)
        rif_file = serializer.validated_data.get("rif_document")
        mercantil_file = serializer.validated_data.get("mercantil_document")
        if Company.objects.filter(name__iexact=company_name).exists():
            return Response({'error': 'El nombre de la compañia no esta disponible.'}, status=status.HTTP_400_BAD_REQUEST)
        locked_representante_cedula = None
        rif_sha256 = None
        mercantil_sha256 = None
        # =====================================================================
        # VALIDACIÓN ESTRICTA KYB (CAMINO 1) SI ES EMPRESA CONSTITUIDA (1)
        # =====================================================================
        if comercial_entity_type == MerchantType.BUSINESS:
            # 1. Exigir que la cuenta de CartMaker tenga su Cédula verificada biométricamente
            if not getattr(user, "cedula_verified", False) or not getattr(user, "cedula_number", None):
                return Response(
                    {'error': 'Debes verificar tu Cédula de Identidad biométricamente antes de registrar una Empresa Constituida.'},
                    status=status.HTTP_403_FORBIDDEN
                )
            # 2. Bloquear la Cédula del representante directamente a la del titular autenticado en BD
            user_digits = re.sub(r"[^0-9]", "", str(user.cedula_number))
            if client_rep_cedula:
                client_digits = re.sub(r"[^0-9]", "", client_rep_cedula)
                if client_digits and client_digits != user_digits:
                    return Response(
                        {'error': 'Alerta Antifraude: La Cédula del representante no coincide con la Cédula verificada de tu cuenta.'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            raw_nac = getattr(user, "nacionality", UserNacionality.VENEZOLANO)
            if isinstance(raw_nac, str):
                nac_prefix = raw_nac.strip().upper()
            else:
                nac_prefix = "E" if raw_nac == UserNacionality.EXTRANJERO else "V"
            if nac_prefix not in ("V", "E"):
                nac_prefix = "V"
            locked_representante_cedula = f"{nac_prefix}-{user_digits}"
            # 3. Validar campos obligatorios y documentos físicos escaneados
            if not rif_number or not razon_social or not mercantil_oficina or not mercantil_numero or not mercantil_tomo:
                return Response(
                    {'error': 'Debe consignar todos los datos mercantiles (RIF, Razón Social, Oficina, Número y Tomo).'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if not rif_file or not mercantil_file:
                return Response(
                    {'error': 'Debe adjuntar las capturas escaneadas del Comprobante RIF y del Registro Mercantil.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            # 4. Validar Checksum Módulo 11 del RIF en el servidor (protección contra Postman/scripts)
            is_valid_rif, normalized_rif, rif_error = validate_venezuelan_rif_modulo11(rif_number)
            if not is_valid_rif:
                return Response({'error': rif_error}, status=status.HTTP_400_BAD_REQUEST)
            rif_number = normalized_rif
            # 5. Calcular y validar hashes SHA-256 de las imágenes de RIF y Registro Mercantil
            rif_sha256 = self._compute_file_sha256(rif_file)
            mercantil_sha256 = self._compute_file_sha256(mercantil_file)
            if rif_sha256 == mercantil_sha256:
                return Response(
                    {'error': 'Las imágenes del Comprobante RIF y del Registro Mercantil no pueden ser el mismo archivo.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if Company.objects.filter(Q(rif_image_sha256=rif_sha256) | Q(mercantil_image_sha256=rif_sha256)).exists():
                return Response(
                    {'error': 'La imagen del Comprobante RIF ya fue utilizada en otro registro.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if Company.objects.filter(Q(mercantil_image_sha256=mercantil_sha256) | Q(rif_image_sha256=mercantil_sha256)).exists():
                return Response(
                    {'error': 'La imagen del Registro Mercantil ya fue utilizada en otro registro.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            # 6. Validar que no exista otra empresa con el mismo RIF, Razón Social o Asiento Mercantil
            if Company.objects.filter(rif_number__iexact=rif_number).exists():
                return Response(
                    {'error': f'El RIF {rif_number} ya se encuentra registrado en otra empresa.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if Company.objects.filter(razon_social__iexact=razon_social).exists():
                return Response(
                    {'error': f'La Razón Social "{razon_social}" ya se encuentra registrada en otra empresa.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if Company.objects.filter(
                mercantil_oficina__iexact=mercantil_oficina,
                mercantil_numero__iexact=mercantil_numero,
                mercantil_tomo__iexact=mercantil_tomo,
            ).exists():
                return Response(
                    {'error': f'El asiento mercantil (Nro. {mercantil_numero}, Tomo {mercantil_tomo}) ya fue registrado por otra empresa.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        try:
            company_category = CompanyCategory.objects.get(id=company_category_id)
        except CompanyCategory.DoesNotExist:
            return Response({"error": "La categoria especificada no existe."}, status=status.HTTP_400_BAD_REQUEST)
        if store_type == StoreType.IN_MALL:
            if selected_mall_id is None or selected_mall_floor is None:
                return Response({'error': 'Debes especificar el centro comercial y el piso.'}, status=status.HTTP_400_BAD_REQUEST)
            try:
                mall = Mall.objects.get(id=selected_mall_id)
                location = mall.coordinates
                if not address:
                    address = mall.name
            except Mall.DoesNotExist:
                return Response({'error': 'El centro comercial seleccionado no existe.'}, status=status.HTTP_404_NOT_FOUND)
        else:
            if lat is None or lng is None or address is None:
                return Response({'error': 'Debes especificar las coordenadas y la dirección.'}, status=status.HTTP_400_BAD_REQUEST)
            location = Point(float(lng), float(lat), srid=4326)
            mall = None
        # Subida de documentos KYB a Cloud Object Storage (si aplica)
        rif_doc_url = None
        mercantil_doc_url = None
        if comercial_entity_type == MerchantType.BUSINESS:
            dtnow_str = timezone.localtime(timezone.now()).strftime('%d-%m-%Y_%H-%M-%S')
            rif_ext = rif_file.name.rsplit('.', 1)[-1].lower() if '.' in getattr(rif_file, 'name', '') else 'jpg'
            mercantil_ext = mercantil_file.name.rsplit('.', 1)[-1].lower() if '.' in getattr(mercantil_file, 'name', '') else 'jpg'
            rif_filename = f"rif_{user.id}_{dtnow_str}.{rif_ext}"
            mercantil_filename = f"mercantil_{user.id}_{dtnow_str}.{mercantil_ext}"
            rif_rel_path = storage_manager.save_file(rif_file, "companies/kyb/rif", rif_filename)
            mercantil_rel_path = storage_manager.save_file(mercantil_file, "companies/kyb/mercantil", mercantil_filename)
            if not rif_rel_path or not mercantil_rel_path:
                return Response(
                    {'error': 'Error al almacenar los documentos mercantiles en el servidor. Intente nuevamente.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            rif_doc_url = storage_manager.get_url(rif_rel_path)
            mercantil_doc_url = storage_manager.get_url(mercantil_rel_path)
        with transaction.atomic():
            company = Company.objects.create(
                owner=user,
                name=company_name,
                merchant_type=comercial_entity_type,
                category=company_category,
                rif_number=rif_number if comercial_entity_type == MerchantType.BUSINESS else None,
                razon_social=razon_social if comercial_entity_type == MerchantType.BUSINESS else None,
                mercantil_oficina=mercantil_oficina if comercial_entity_type == MerchantType.BUSINESS else None,
                mercantil_numero=mercantil_numero if comercial_entity_type == MerchantType.BUSINESS else None,
                mercantil_tomo=mercantil_tomo if comercial_entity_type == MerchantType.BUSINESS else None,
                # Siempre guardamos la Cédula bloqueada del titular autenticado (nunca un string libre)
                representante_cedula=locked_representante_cedula if comercial_entity_type == MerchantType.BUSINESS else None,
                rif_document_url=rif_doc_url,
                mercantil_document_url=mercantil_doc_url,
                rif_image_sha256=rif_sha256 if comercial_entity_type == MerchantType.BUSINESS else None,
                mercantil_image_sha256=mercantil_sha256 if comercial_entity_type == MerchantType.BUSINESS else None,
                kyb_ocr_verified=kyb_ocr_verified if comercial_entity_type == MerchantType.BUSINESS else False,
                kyb_confidence_score=kyb_confidence_score if comercial_entity_type == MerchantType.BUSINESS else 0,
            )
            main_store = CompanyStore.objects.create(
                company=company,
                name="Sucursal Principal",
                store_type=store_type,
                is_main_store=True,
                is_active=True,
            )
            StoreLocation.objects.create(
                store=main_store,
                mall=mall if store_type == StoreType.IN_MALL else None,
                mall_floor=selected_mall_floor if store_type == StoreType.IN_MALL else None,
                coordinates=location,
                name=address or company_name,
            )
            user.user_type = UserType.MERCHANT
            user.save(update_fields=['user_type'])
        return Response(
            {
                "message": "Compañía creada exitosamente.",
                "company": company.get_json(),
                "store": main_store.get_json(),
            },
            status=status.HTTP_201_CREATED,
        )

class CheckCompanyNameAvailableAPI(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    permission_classes = [IsAuthenticated]

    def get(self, request, name:str):
        return Response(status=status.HTTP_202_ACCEPTED) if Company.objects.only('name').filter(name=name).exists()\
            == False else Response(status=status.HTTP_406_NOT_ACCEPTABLE)

class UpdateCompanyAPI(APIView):
    """
    Actualiza la compañía y la sucursal principal. Vender no depende de un plan.
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
            return Response({'error': 'No se encontro la compania.'}, status=status.HTTP_404_NOT_FOUND)
        if company.owner_id != request.user.id:
            return Response({'error': 'No tienes permisos para modificar esta compañía.'}, status=status.HTTP_403_FORBIDDEN)
        main_store = company.stores.filter(is_main_store=True).first()
        if main_store == None:
            first = company.stores.all().order_by('-creation').first()
            if first == None:
                return Response({'error': 'No hay una tienda configurada'}, status=status.HTTP_409_CONFLICT)
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
    queryset = CompanyStore.objects.select_related('company').all()
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return CompanyStore.objects.select_related('company').filter(company__owner=self.request.user)

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

class CheckCompanyKybAvailableAPI(APIView):
    """
    Verifica en tiempo real (Etapa 2.5):
    1. Que el usuario autenticado tenga KYC biométrico verificado (Camino 1 Estricto).
    2. Que el RIF sea válido en Módulo 11 (SENIAT).
    3. Que ni el RIF, ni la Razón Social, ni el asiento mercantil (Oficina + Número + Tomo)
       estén ya registrados por otra empresa en CartMaker.
    """
    permission_classes = [IsAuthenticated]
    def post(self, request):
        user = request.user
        # 1. CAMINO 1 (ESTRICTO): Exigir KYC biométrico activo en la cuenta del titular
        if not getattr(user, "cedula_verified", False) or not getattr(user, "cedula_number", None):
            return Response(
                {
                    "available": False,
                    "error": "Tu cuenta personal debe tener la Cédula verificada biométricamente antes de registrar una Empresa Constituida."
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        rif_raw = (request.data.get("rif_number") or "").strip()
        razon_social = (request.data.get("razon_social") or "").strip()
        mercantil_oficina = (request.data.get("mercantil_oficina") or "").strip()
        mercantil_numero = (request.data.get("mercantil_numero") or "").strip()
        mercantil_tomo = (request.data.get("mercantil_tomo") or "").strip()
        # 2. Validar que si el cliente envía representante_cedula, coincida con request.user.cedula_number
        client_rep_cedula = (request.data.get("representante_cedula") or "").strip()
        user_digits = re.sub(r"[^0-9]", "", str(user.cedula_number))
        client_digits = re.sub(r"[^0-9]", "", client_rep_cedula)
        if client_digits and user_digits != client_digits:
            return Response(
                {
                    "available": False,
                    "error": "Alerta Antifraude: La Cédula del representante no coincide con la Cédula verificada del titular de la cuenta."
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        # 3. Validar Módulo 11 del RIF
        is_valid_rif, normalized_rif, rif_error = validate_venezuelan_rif_modulo11(rif_raw)
        if not is_valid_rif:
            return Response(
                {"available": False, "error": rif_error},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # 4. Verificar duplicidad de RIF
        if Company.objects.filter(rif_number__iexact=normalized_rif).exists():
            return Response(
                {
                    "available": False,
                    "error": f"El RIF {normalized_rif} ya se encuentra registrado por otra empresa en CartMaker."
                },
                status=status.HTTP_409_CONFLICT,
            )
        # 5. Verificar duplicidad de Razón Social
        if razon_social and Company.objects.filter(razon_social__iexact=razon_social).exists():
            return Response(
                {
                    "available": False,
                    "error": f"La Razón Social '{razon_social}' ya se encuentra registrada en CartMaker."
                },
                status=status.HTTP_409_CONFLICT,
            )
        # 6. Verificar duplicidad de Asiento en Registro Mercantil (Oficina + Número + Tomo)
        if mercantil_oficina and mercantil_numero and mercantil_tomo:
            asiento_duplicado = Company.objects.filter(
                mercantil_oficina__iexact=mercantil_oficina,
                mercantil_numero__iexact=mercantil_numero,
                mercantil_tomo__iexact=mercantil_tomo,
            ).exists()
            if asiento_duplicado:
                return Response(
                    {
                        "available": False,
                        "error": f"El asiento mercantil (Nro. {mercantil_numero}, Tomo {mercantil_tomo}) ya fue registrado por otra empresa."
                    },
                    status=status.HTTP_409_CONFLICT,
                )
        # 7. Verificar duplicidad de hashes SHA-256 de imágenes si el cliente los envía
        rif_sha256 = (request.data.get("rif_image_sha256") or "").strip().lower()
        mercantil_sha256 = (request.data.get("mercantil_image_sha256") or "").strip().lower()
        if rif_sha256 and mercantil_sha256 and rif_sha256 == mercantil_sha256:
            return Response(
                {
                    "available": False,
                    "error": "Las imágenes del Comprobante RIF y del Registro Mercantil no pueden ser el mismo archivo."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if rif_sha256 and Company.objects.filter(
            Q(rif_image_sha256__iexact=rif_sha256) | Q(mercantil_image_sha256__iexact=rif_sha256)
        ).exists():
            return Response(
                {
                    "available": False,
                    "error": "La imagen del Comprobante RIF ya fue utilizada en otro registro en CartMaker."
                },
                status=status.HTTP_409_CONFLICT,
            )
        if mercantil_sha256 and Company.objects.filter(
            Q(mercantil_image_sha256__iexact=mercantil_sha256) | Q(rif_image_sha256__iexact=mercantil_sha256)
        ).exists():
            return Response(
                {
                    "available": False,
                    "error": "La imagen del Registro Mercantil ya fue utilizada en otro registro en CartMaker."
                },
                status=status.HTTP_409_CONFLICT,
            )
        return Response(
            {
                "available": True,
                "normalized_rif": normalized_rif,
                "locked_representante_cedula": user_digits,
            },
            status=status.HTTP_200_OK,
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
                return Response({'error': 'Usted no es propietario de esta compania.'}, status=status.HTTP_406_NOT_ACCEPTABLE)
        except StoreContactMethod.DoesNotExist:
            return Response({'error': 'No existe ese metodo de contacto.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            contact_method.delete()
        except Exception as e:
            print(f"Error al eliminar el metodo de contacto: {e}")
            return Response({'error': f"{e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
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

    def get_permissions(self):
        if self.action in ('get_locations', 'store_products'):
            return [AllowAny()]
        return [IsAuthenticated()]

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
        if cached_features is None:
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
            if structural_data is None:
                # Recuperamos el QuerySet base con todas sus relaciones cargadas
                queryset = InventoryItem.objects.select_related(
                    'product',
                    'product__category',
                    'product__category__parent_category',
                    'product__company',
                    'offer',
                    'store',
                    'store__company',
                ).filter(
                    store_id=store_id,
                    paused=False,
                    stock__gt=0
                )
                
                prod_avg_sq = Subquery(
                    ProductCalification.objects.filter(product_id=OuterRef('product_id'))
                    .values('product_id')
                    .annotate(v=Avg('rating'))
                    .values('v')[:1],
                    output_field=FloatField()
                )
                prod_cnt_sq = Subquery(
                    ProductCalification.objects.filter(product_id=OuterRef('product_id'))
                    .values('product_id')
                    .annotate(c=Count('id'))
                    .values('c')[:1],
                    output_field=IntegerField()
                )
                queryset = queryset.annotate(
                    avg_rating=Round(Coalesce(prod_avg_sq, Value(0.0, output_field=FloatField())), 1),
                    rating_count=Coalesce(prod_cnt_sq, Value(0, output_field=IntegerField()))
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
    permission_classes = [AllowAny]

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
                store__is_active=True,
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
    permission_classes = [AllowAny]

    def get(self, request):
        cache_key = "cartmaker:global:malls"
        cached_data = cache.get(cache_key)

        if cached_data is not None:
            return Response(cached_data, status=status.HTTP_200_OK)

        # Cache Miss
        malls = Mall.objects.prefetch_related('stores').all()
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

        if cached_data is not None:
            if cached_data.get("message") == "Suscripción expirada.":
                cache.delete(cache_key)
            elif "error_status" in cached_data:
                return Response({'message': cached_data["message"]}, status=cached_data["error_status"])
            else:
                return Response(cached_data, status=status.HTTP_200_OK)
            
        try:
            company_obj = Company.objects.select_related('category').get(owner=request.user)
            company = company_obj.get_json()
        except Company.DoesNotExist:
            error_data = {"error_status": status.HTTP_404_NOT_FOUND, "message": "No ha configurado su tienda."}
            cache.set(cache_key, error_data, timeout=300)
            return Response({'message': error_data["message"]}, status=error_data["error_status"])

        stores_qs = CompanyStore.objects.filter(
            company_id=company['id']
        ).select_related(
            'location', 'location__mall', 'company'
        ).prefetch_related(
            'contact_methods'
        ).order_by('creation')
        stores = [company_store.get_json() for company_store in stores_qs]

        item_ct = ContentType.objects.get_for_model(InventoryItem)
        video_ct = ContentType.objects.get_for_model(CompanyVideoStory)

        items_pks = InventoryItem.objects.filter(store__company_id=company['id']).values_list('id', flat=True)
        videos_pks = CompanyVideoStory.objects.filter(company_id=company['id']).values_list('id', flat=True)

        pending_items = UniversalComment.objects.filter(content_type=item_ct).annotate(
            object_uuid=Cast('object_id', output_field=UUIDField())
        ).filter(object_uuid__in=items_pks).filter(Q(answer_text__isnull=True) | Q(answer_text__exact=''))

        pending_videos = UniversalComment.objects.filter(content_type=video_ct).annotate(
            object_uuid=Cast('object_id', output_field=UUIDField())
        ).filter(object_uuid__in=videos_pks).filter(Q(answer_text__isnull=True) | Q(answer_text__exact=''))

        pending_questions = list(pending_items.values_list('id', flat=True)) + list(pending_videos.values_list('id', flat=True))

        data = {'company': company, 'stores': stores, 'pending_questions': pending_questions}
        cache.set(cache_key, data, timeout=3600)
        return Response(data, status=status.HTTP_200_OK)

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

        if cached_data is not None:
            return Response(cached_data, status=status.HTTP_200_OK)

        # Cache Miss
        user = User.objects.select_related(
            'subscription__plan',
            'atlas_plan',
            'wallet',
        ).prefetch_related(
            'subscription__payments__subscription__plan',
            'atlas_plan__payments',
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
            'atlas_anonymous_daily_limit': config.atlas_anonymous_daily_limit,
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

        if cached_data and "preferred_category_ids" in cached_data:
            return Response(cached_data, status=status.HTTP_200_OK)

        # Cache Miss
        user = User.objects.prefetch_related(
            'locations', 'contact_methods', 'preferred_categories'
        ).get(id=request.user.id)
        locations = [location.get_json() for location in user.locations.all()]
        contact_methods = [contact_method.get_json() for contact_method in user.contact_methods.all().order_by('method_type')]
        preferred_category_ids = sorted(cat.id for cat in user.preferred_categories.all())

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
            "preferred_category_ids": preferred_category_ids,
        }
        
        cache.set(cache_key, data, timeout=86400) # 24 horas (Cambia rara vez)
        return Response(data, status=status.HTTP_200_OK)
    
class HomeCacheAPI(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'navigation'
    permission_classes = [AllowAny]

    def get(self, request):
        cache_key = "cartmaker:global:home"
        cached_data = cache.get(cache_key)

        if cached_data is not None:
            return Response(cached_data, status=status.HTTP_200_OK)

        # Cache Miss
        announcements = [announcement.get_json() for announcement in Announcement.objects.filter(active=True).order_by('-creation')]
        
        # 👈 AQUÍ: aseguramos la iteración limpia usando el modelo Category
        company_categories = [cat.get_json() for cat in CompanyCategory.objects.all()]
        
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
    permission_classes = [AllowAny]

    def get(self, request):
        """
        Caché Global: UI del Buscador + Esquemas Dinámicos de Producto por Categoría/Subcategoría.
        """
        cache_key = "cartmaker:global:search"
        cached_data = cache.get(cache_key)

        if (
            cached_data
            and isinstance(cached_data.get("categories"), list)
            and (not cached_data["categories"] or "default_product_schema" in cached_data["categories"][0])
        ):
            return Response(cached_data, status=status.HTTP_200_OK)

        # Cache Miss
        categories = [category.get_json() for category in Category.objects.prefetch_related('subcategories').order_by('id')]
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


class CategoriesListAPI(APIView):
    """
    Endpoint público (protegido por X-Api-Key en el Gatekeeper) para listar
    las categorías principales del catálogo durante el Onboarding, buscador o registro de productos.
    GET /api/v1/categories/?page_size=50
    """
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'navigation'
    permission_classes = [AllowAny]

    def get(self, request):
        cache_key = "cartmaker:global:categories"
        categories = cache.get(cache_key)

        if (
            categories is None
            or not isinstance(categories, list)
            or (categories and "default_product_schema" not in categories[0])
        ):
            categories = [
                category.get_json()
                for category in Category.objects.prefetch_related('subcategories').order_by('id')
            ]
            cache.set(cache_key, categories, timeout=86400)

        try:
            page = max(1, int(request.query_params.get('page', 1)))
        except (TypeError, ValueError):
            page = 1

        try:
            page_size = max(1, min(100, int(request.query_params.get('page_size', 50))))
        except (TypeError, ValueError):
            page_size = 50

        start = (page - 1) * page_size
        end = start + page_size
        sliced = categories[start:end]

        return Response(
            {
                "count": len(categories),
                "next": None,
                "previous": None,
                "results": sliced,
                "categories": sliced,
                "data": sliced,
            },
            status=status.HTTP_200_OK,
        )


class CategoryProductSchemaAPI(APIView):
    """
    Devuelve el esquema dinámico de creación/visualización de producto para una
    subcategoría o categoría específica (o el catálogo completo de unidades y esquemas).
    GET /api/v1/categories/product-schema/?subcategory_id=X
    GET /api/v1/categories/product-schema/?category_id=Y
    GET /api/v1/categories/product-schema/?subcategory_name=Frescos
    """
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'navigation'
    permission_classes = [AllowAny]

    def get(self, request):
        from api.core.category_schemas import SELLING_UNITS_CATALOG, get_subcategory_schema

        subcategory_id = request.query_params.get('subcategory_id') or request.query_params.get('sub_category_id')
        category_id = request.query_params.get('category_id')
        subcategory_name = request.query_params.get('subcategory_name')
        category_name = request.query_params.get('category_name')

        if subcategory_id:
            try:
                sub = SubCategory.objects.select_related('parent_category').get(id=int(subcategory_id))
                return Response({
                    "subcategory_id": sub.id,
                    "subcategory_name": sub.name,
                    "category_id": sub.parent_category_id,
                    "category_name": sub.parent_category.name if sub.parent_category_id else "",
                    "product_schema": sub.get_product_schema(),
                }, status=status.HTTP_200_OK)
            except (SubCategory.DoesNotExist, ValueError, TypeError):
                return Response({"error": "Subcategoría no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        if category_id:
            try:
                cat = Category.objects.prefetch_related('subcategories').get(id=int(category_id))
                return Response({
                    "category_id": cat.id,
                    "category_name": cat.name,
                    "default_product_schema": cat.get_product_schema(),
                    "sub_categories": [
                        {
                            "id": s.id,
                            "name": s.name,
                            "product_schema": s.get_product_schema(),
                        }
                        for s in cat.subcategories.all()
                    ],
                }, status=status.HTTP_200_OK)
            except (Category.DoesNotExist, ValueError, TypeError):
                return Response({"error": "Categoría no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        if subcategory_name or category_name:
            schema = get_subcategory_schema(
                subcategory_name=subcategory_name,
                parent_category_name=category_name,
            )
            return Response({
                "subcategory_name": subcategory_name,
                "category_name": category_name,
                "product_schema": schema,
            }, status=status.HTTP_200_OK)

        categories = [
            category.get_json()
            for category in Category.objects.prefetch_related('subcategories').order_by('id')
        ]
        return Response({
            "selling_units_catalog": list(SELLING_UNITS_CATALOG.values()),
            "categories": categories,
        }, status=status.HTTP_200_OK)


def _extract_and_validate_category_ids(data: dict):
    """
    Extrae y sanea la lista de IDs de categorías enviadas en el body
    ('category_ids' o 'preferred_category_ids' o 'categories').
    Retorna (is_valid: bool, clean_ids: list[int], error_msg: str | None).
    """
    raw_ids = None
    if isinstance(data, dict):
        for key in ('category_ids', 'preferred_category_ids', 'categories'):
            if key in data:
                raw_ids = data.get(key)
                break

    if raw_ids is None or not isinstance(raw_ids, (list, tuple)):
        return False, [], "Se requiere el campo 'category_ids' como una lista de IDs enteros."

    clean_ids = []
    seen = set()
    for item in raw_ids:
        try:
            cid = int(item)
            if cid > 0 and cid not in seen:
                seen.add(cid)
                clean_ids.append(cid)
        except (TypeError, ValueError):
            return False, [], f"ID de categoría inválido: {item!r}."

    return True, clean_ids, None


class UserPreferencesAPI(APIView):
    """
    Endpoint para consultar y guardar las preferencias de categorías del usuario
    seleccionadas durante el Onboarding o desde Ajustes.
    Rutas: GET / POST /api/v1/users/preferences/ (y /api/v1/user/preferences/)
    """
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    permission_classes = [IsAuthenticated]

    def get(self, request):
        preferred_ids = request.user.get_preferred_category_ids()
        return Response(
            {"preferred_category_ids": preferred_ids},
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        is_valid, clean_ids, error_msg = _extract_and_validate_category_ids(request.data)
        if not is_valid:
            return Response({"error": error_msg}, status=status.HTTP_400_BAD_REQUEST)

        valid_categories = list(Category.objects.filter(id__in=clean_ids).order_by('id'))
        valid_ids = [cat.id for cat in valid_categories]

        with transaction.atomic():
            request.user.preferred_categories.set(valid_categories)
            user_id = request.user.id
            transaction.on_commit(
                lambda: cache.delete(f"cartmaker:tenant:{user_id}:profile")
            )

        return Response(
            {"preferred_category_ids": valid_ids},
            status=status.HTTP_200_OK,
        )

    def put(self, request):
        return self.post(request)

    def patch(self, request):
        return self.post(request)

####################################################
#################### VIEW SETS #####################
####################################################

class SupportTicketViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        tickets = SupportTicket.objects.filter(
            client=request.user
        ).select_related('agent').annotate(
            unread_client_count=Count(
                'messages',
                filter=Q(messages__status__lt=3) & ~Q(messages__sender_id=F('client_id'))
            ),
            unread_agent_count=Case(
                When(
                    agent__isnull=False,
                    then=Count(
                        'messages',
                        filter=Q(messages__status__lt=3) & ~Q(messages__sender_id=F('agent_id'))
                    )
                ),
                default=Count('messages'),
                output_field=IntegerField()
            )
        ).order_by('-creation')
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
                f"{settings.INTERNAL_WEBSOCKETS_URL}internal/online-users", 
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
                    f"{settings.INTERNAL_WEBSOCKETS_URL}internal/emit-assignment",
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

        # Pre-cargamos en lote los timestamps de engagement de video y de Atlas IA para eliminar N+1 queries
        video_engagement_rows = VideoEngagementLog.objects.filter(
            video__company=company,
            video__associated_item__isnull=False,
            timestamp__gte=time_horizon - timedelta(hours=2)
        ).values_list('video__associated_item_id', 'timestamp')
        video_ts_by_item = {}
        for item_id_val, ts_val in video_engagement_rows:
            video_ts_by_item.setdefault(item_id_val, []).append(ts_val)

        atlas_view_rows = ProductViewLog.objects.filter(
            inventory_item__store__company=company,
            origin_source='atlas',
            start_time__gte=time_horizon - timedelta(days=7)
        ).values_list('inventory_item_id', 'start_time')
        atlas_ts_by_item = {}
        for item_id_val, ts_val in atlas_view_rows:
            atlas_ts_by_item.setdefault(item_id_val, []).append(ts_val)

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
            tx_time = trans.creation
            window_video_start = tx_time - timedelta(hours=2)

            # A. Verificación de canal de Video Historias (Ventana de interacción de 2 horas previas)
            has_video_engagement = any(
                window_video_start <= ts <= tx_time
                for ts in video_ts_by_item.get(trans.item_id, ())
            )

            if has_video_engagement:
                video_sales_count += qty
                is_attributed = True

            # B. Verificación de recomendación de Atlas IA (Ventana de influencia de 7 días previos)
            if not is_attributed:
                window_atlas_start = tx_time - timedelta(days=7)
                has_atlas_influence = any(
                    window_atlas_start <= ts <= tx_time
                    for ts in atlas_ts_by_item.get(trans.item_id, ())
                )

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

        # Vender ya no tiene costo de plan. Las claves del JSON se conservan.
        plan_cost = 0.0
        roi_percentage = 0.0
        is_profitable = total_revenue >= plan_cost

        insights = {'roi': None, 'origin': None, 'products': None}

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
        logs = list(VideoEngagementLog.objects.filter(video__company=company, timestamp__gte=time_horizon))

        total_views = len(logs)
        completed_views = sum(1 for l in logs if l.video_completed)
        abandoned_views = total_views - completed_views
        interacted = sum(1 for l in logs if l.interacted_with_product)
        added_to_cart = sum(1 for l in logs if l.added_to_cart_from_video)
        
        completion_rate = round((completed_views / total_views * 100), 1) if total_views > 0 else 0.0

        video_stats = {}
        total_video_revenue = 0.0
        total_watch_time_seconds_clean = 0.0

        company_videos = list(CompanyVideoStory.objects.filter(company=company))
        for v in company_videos:
            video_stats[str(v.id)] = {
                'id': str(v.id),
                'description': v.description or 'Video sin descripción',
                'thumbnail': storage_manager.get_url(v.thumbnail) if v.thumbnail else None,
                'duration_seconds': v.duration_seconds,
                'views': 0, 'completions': 0, 'watch_time_seconds': 0.0,
                'revenue': 0.0, 'units_sold': 0, 'interacted': 0
            }

        purchase_ts_by_video = {}
        for log in logs:
            vid = str(log.video_id)
            if log.bought_from_video:
                purchase_ts_by_video.setdefault(vid, []).append(log.timestamp)
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

        # --- AUDITORÍA DE FACTURACIÓN POR VIDEO USANDO DIARIO CONTABLE (SIN N+1) ---
        associated_item_ids = {v.associated_item_id for v in company_videos if v.associated_item_id}
        txs_by_item = {}
        if associated_item_ids:
            all_related_txs = InventoryItemTransaction.objects.filter(
                item_id__in=associated_item_ids,
                transaction_type=TransactionType.OUTCOME,
                creation__gte=time_horizon
            ).select_related('item__product')
            for tx in all_related_txs:
                txs_by_item.setdefault(tx.item_id, []).append(tx)

        for v in company_videos:
            vid = str(v.id)
            if v.associated_item_id and v.associated_item_id in txs_by_item:
                vid_purchase_ts = purchase_ts_by_video.get(vid, ())
                if not vid_purchase_ts:
                    continue
                for tx in txs_by_item[v.associated_item_id]:
                    window_start = tx.creation - timedelta(hours=2)
                    has_purchase_log = any(window_start <= ts <= tx.creation for ts in vid_purchase_ts)
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

        # --- 3. EXTRACCIÓN VIP Y ANALÍTICA DE GAMIFICACIÓN (EN LOTE, SIN N+1) ---
        gamified_sales_txs = InventoryItemTransaction.objects.filter(
            item__store__company=company,
            item__product__discounts_by_tokens_active=True,
            transaction_type=TransactionType.OUTCOME,
            creation__gte=time_horizon
        ).select_related('item__product')

        gamified_products_stats = {}
        revenue_from_token_orders = 0.0

        for tx in gamified_sales_txs:
            item = tx.item
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
        
        # Traemos todas las transacciones de venta (OUTCOME) del mes con item__product pre-cargado
        sales_txs = list(InventoryItemTransaction.objects.filter(
            item__store__company=company,
            transaction_type=TransactionType.OUTCOME,
            creation__gte=time_horizon
        ).select_related('item__store', 'item__product'))

        total_revenue = 0.0
        # Consideramos cada transacción contable de venta como una entrada en caja
        total_sales_records = len(sales_txs)

        branches_data = {}
        stores = CompanyStore.objects.filter(company=company).annotate(
            total_items_count=Count('product_items'),
            low_stock_items_count=Count('product_items', filter=Q(product_items__stock__lte=5))
        )
        
        for store in stores:
            total_items = store.total_items_count
            low_stock_items = store.low_stock_items_count
            
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
            
            store_id = tx.item.store_id
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
    permission_classes = [IsAuthenticated]
    
    # 💡 MUY IMPORTANTE: Habilitamos a Django para recibir archivos pesados
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.company.owner != request.user:
            return Response({"error": "No tienes permiso para modificar este video."}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.company.owner != request.user:
            return Response({"error": "No tienes permiso para modificar este video."}, status=status.HTTP_403_FORBIDDEN)
        return super().partial_update(request, *args, **kwargs)

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
        active_stories_prefetch = Prefetch(
            'linked_stories',
            queryset=CompanyVideoStory.objects.filter(expires_at__gt=now, video_file__isnull=False),
            to_attr='active_linked_stories'
        )
        active_items_prefetch = Prefetch(
            'product_items',
            queryset=InventoryItem.objects.filter(paused=False, stock__gt=0).select_related('product').prefetch_related(active_stories_prefetch),
            to_attr='active_product_items'
        )
        stores = company.stores.filter(is_active=True).prefetch_related(active_items_prefetch)
        
        data = []
        for store in stores:
            items_data = []
            inventory_items = getattr(store, 'active_product_items', [])
            
            for item in inventory_items:
                active_stories = getattr(item, 'active_linked_stories', [])
                active_story = active_stories[0] if active_stories else None
                
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

        videos = self.queryset.filter(company=company).select_related(
            'company',
            'associated_item',
            'associated_item__product',
            'associated_item__product__category',
            'associated_item__product__category__parent_category',
            'associated_item__product__company',
            'associated_item__offer',
            'associated_item__store',
            'associated_item__store__company',
        ).order_by('-creation')
        
        page_number = request.GET.get('page', 1)
        paginator = Paginator(videos, 10)
        page_obj = paginator.get_page(page_number)

        current_videos = list(page_obj.object_list)
        video_ids = [v.id for v in current_videos]
        video_ids_str = [str(vid) for vid in video_ids]

        # 1. Telemetría de engagement
        logs_data = VideoEngagementLog.objects.filter(
            video_id__in=video_ids
        ).values('video_id').annotate(
            total_views=Count('id'),
            completed_views=Count('id', filter=Q(video_completed=True)),
            product_clicks=Count('id', filter=Q(interacted_with_product=True)),
            added_to_cart_count=Count('id', filter=Q(added_to_cart_from_video=True)),
            sales_count=Count('id', filter=Q(bought_from_video=True)),
            total_watch_time=Sum('watch_time_seconds')
        )
        logs_map = {l['video_id']: l for l in logs_data}

        # 2. Likes polimórficos
        video_ct = ContentType.objects.get_for_model(CompanyVideoStory)
        likes_data = UniversalLike.objects.filter(
            content_type=video_ct,
            object_id__in=video_ids_str
        ).values('object_id').annotate(total_likes=Count('id'))
        likes_map = {l['object_id']: l['total_likes'] for l in likes_data}

        # 3. Preguntas/Comentarios polimórficos
        comments_data = UniversalComment.objects.filter(
            content_type=video_ct,
            object_id__in=video_ids_str
        ).values('object_id').annotate(total_comments=Count('id'))
        comments_map = {c['object_id']: c['total_comments'] for c in comments_data}

        data = []
        for video in current_videos:
            v_json = video.get_json()
            vid = video.id
            vid_str = str(vid)
            
            v_log = logs_map.get(vid, {})
            log_views = v_log.get('total_views', 0)
            total_views = max(video.views_count, log_views)
            
            likes_count = likes_map.get(vid_str, 0)
            comments_count = comments_map.get(vid_str, 0)
            product_clicks = v_log.get('product_clicks', 0)
            sales_count = v_log.get('sales_count', 0)
            added_to_cart_count = v_log.get('added_to_cart_count', 0)
            completed_views = v_log.get('completed_views', 0)
            watch_time = round(float(v_log.get('total_watch_time') or 0.0), 1)

            # Facturación estimada atribuida
            revenue = 0.0
            if video.associated_item and sales_count > 0:
                item_price = float(video.associated_item.custom_price if video.associated_item.custom_price else video.associated_item.product.price)
                revenue = round(sales_count * item_price, 2)

            metrics = {
                'views_count': total_views,
                'likes_count': likes_count,
                'comments_count': comments_count,
                'product_clicks': product_clicks,
                'sales_count': sales_count,
                'added_to_cart_count': added_to_cart_count,
                'completed_views': completed_views,
                'watch_time_seconds': watch_time,
                'revenue': revenue,
            }

            v_json['metrics'] = metrics
            v_json['views_count'] = total_views
            v_json['likes_count'] = likes_count
            v_json['comments_count'] = comments_count
            v_json['sales_count'] = sales_count
            v_json['product_clicks'] = product_clicks
            v_json['revenue'] = revenue

            data.append(v_json)

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
                'client',
                'store__company',
                'store__company__owner',
                'store__location',
                'client_location'
            ).prefetch_related(
                'client__contact_methods',
                'store__contact_methods'
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

            is_merchant_mode = (company.owner_id == request.user.id)

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
                'store_id': str(order.store_id),
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
            'client',
            'store__company',
            'store__company__owner',
            'store__location',
            'client_location'
        ).prefetch_related(
            'store__contact_methods',
            'client__contact_methods'
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
                    raw_qty = float(item.get('quantity', 0) or 0)
                    stock_units = int(item.get('stock_units_deducted') or (max(1, math.ceil(raw_qty)) if raw_qty > 0 else 0))
                    if inv_item_id and stock_units > 0:
                        try:
                            inv_item = InventoryItem.objects.select_for_update().select_related('product').get(id=inv_item_id)
                            inv_item.stock += stock_units
                            inv_item.save()

                            # Si se descontó stock de una variante específica, lo reintegramos también
                            sel_var = item.get('selected_variant')
                            if isinstance(sel_var, dict) and sel_var.get('id') and isinstance(inv_item.product.variants, list):
                                updated_vars = False
                                for v in inv_item.product.variants:
                                    if isinstance(v, dict) and str(v.get('id')) == str(sel_var.get('id')) and v.get('stock') is not None:
                                        try:
                                            v['stock'] = int(v['stock']) + stock_units
                                            v['is_available'] = v['stock'] > 0
                                            updated_vars = True
                                        except (ValueError, TypeError):
                                            pass
                                if updated_vars:
                                    inv_item.product.save(update_fields=['variants'])
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
                # Bloqueamos únicamente la fila de la orden (of=('self',)) para evitar bloqueos innecesarios en tablas relacionadas
                order = Order.objects.select_for_update(of=('self',)).select_related('store__company').get(id=order_id)
                is_client = order.client == request.user
                is_merchant = order.store.company.owner == request.user

                if not is_client and not is_merchant:
                    return Response({"error": "No tienes permisos sobre esta orden."}, status=status.HTTP_403_FORBIDDEN)

                if order.status == OrderStatus.COMPLETED:
                    return Response({"error": "Esta orden ya se encuentra completada."}, status=status.HTTP_400_BAD_REQUEST)

                if order.status in (OrderStatus.CANCELLED, OrderStatus.SOLVED):
                    return Response({"error": "No se puede completar una orden cancelada o cerrada."}, status=status.HTTP_400_BAD_REQUEST)

                order.status = OrderStatus.COMPLETED
                order.end_time = timezone.now()
                order.save()

                cart_items = order.cart.get('items', [])
                for item in cart_items:
                    inv_item_id = item.get('inventory_item_id')
                    raw_qty = float(item.get('quantity', 0) or 0)
                    qty = int(item.get('stock_units_deducted') or (max(1, math.ceil(raw_qty)) if raw_qty > 0 else 0))
                    
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

                # El cliente califica (Solo si la petición viene del cliente real y validando rango [1.0, 5.0])
                if is_client:
                    try:
                        m_rating_val = float(merchant_rating or 0)
                    except (ValueError, TypeError):
                        m_rating_val = 0.0
                    if m_rating_val > 0:
                        clamped_m_rating = min(5.0, max(1.0, m_rating_val))
                        MerchantCalification.objects.create(
                            merchant=order.store.company,
                            client=request.user,
                            rating=clamped_m_rating
                        )
                    valid_product_ids = {str(item.get('product_id')) for item in cart_items if item.get('product_id')}
                    if isinstance(product_ratings, list):
                        for pr in product_ratings:
                            if not isinstance(pr, dict):
                                continue
                            product_id = pr.get('product_id')
                            try:
                                rating_val = float(pr.get('rating', 0) or 0)
                            except (ValueError, TypeError):
                                rating_val = 0.0
                            if product_id and str(product_id) in valid_product_ids and rating_val > 0:
                                clamped_p_rating = min(5.0, max(1.0, rating_val))
                                ProductCalification.objects.create(
                                    product_id=product_id,
                                    client=request.user,
                                    rating=clamped_p_rating
                                )

                tokens_earned = 0.0
                company = order.store.company

                if company.gamification_enabled and company.gamification_tokens_per_dollar > 0:
                    order_total = max(0.0, float(order.cart.get('total', 0.0)))
                    tokens_earned = int(order_total * company.gamification_tokens_per_dollar)
                    
                    if tokens_earned > 0:
                        wallet, _ = TokenWallet.objects.select_for_update().get_or_create(
                            user=order.client,
                            company=company
                        )
                        wallet.balance += tokens_earned
                        wallet.save(update_fields=['balance'])
                        
                        TokenWalletTransaction.objects.create(
                            token_wallet=wallet, amount=tokens_earned,
                            transaction_type=TransactionType.INCOME, order=order
                        )

                owner_id = order.store.company.owner.id
                client_id = order.client.id
                company_name = order.store.company.name
                oid = order.id

                if is_client:
                    transaction.on_commit(lambda: NotificationManager.notify_order_status_change(
                        user_id=owner_id,
                        order_id=oid,
                        title="Cliente confirmó entrega",
                        body=f"El cliente de la orden N° {oid} la ha marcado como completada.",
                        is_merchant=True,
                        new_status=OrderStatus.COMPLETED
                    ))
                elif is_merchant:
                    transaction.on_commit(lambda: NotificationManager.notify_order_status_change(
                        user_id=client_id,
                        order_id=oid,
                        title="Tu orden fue completada",
                        body=f"{company_name} ha marcado tu pedido como completado exitosamente.",
                        is_merchant=False,
                        new_status=OrderStatus.COMPLETED
                    ))

                return Response({
                    "success": True, 
                    "tokens_earned": round(float(tokens_earned), 2),
                    "message": "Orden completada con éxito."
                }, status=status.HTTP_200_OK)
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
                'product', 'product__category__parent_category', 'offer', 'store__company'
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
        from api.core.category_schemas import resolve_cart_item_dynamic_pricing

        if request.user.cedula_verified == False:
            return Response({
                "error": "No puedes comprar sin antes verificar tu identidad."
            }, status=status.HTTP_406_NOT_ACCEPTABLE)
        store_id = request.data.get('store_id')
        items_data = request.data.get('items', [])  # Ej: [{'id': 'uid', 'quantity': 2, 'selected_variant': ..., 'selected_modifiers': [...]}]
        withdrawal_type = request.data.get('withdrawal_type', 0)
        location_id = request.data.get('delivery_location_id')

        if not store_id or not items_data or not isinstance(items_data, list):
            return Response({
                "error": "El carrito está vacío o faltan datos para procesar tu orden."
            }, status=status.HTTP_400_BAD_REQUEST)

        # Validamos estructura y cantidades estrictamente positivas (> 0), soportando enteros y decimales (ej. 0.5 kg)
        item_qty_map = {}
        item_discount_map = {}
        items_lines_by_id = {}
        for item_entry in items_data:
            if not isinstance(item_entry, dict) or not item_entry.get('id'):
                return Response({"error": "Formato de productos inválido."}, status=status.HTTP_400_BAD_REQUEST)
            try:
                qty_val = float(item_entry.get('quantity', 0))
            except (ValueError, TypeError):
                qty_val = 0.0
            if qty_val <= 0 or math.isnan(qty_val) or math.isinf(qty_val):
                return Response({
                    "error": "La cantidad de cada producto debe ser mayor a cero."
                }, status=status.HTTP_400_BAD_REQUEST)
            entry_id = str(item_entry['id'])
            item_qty_map[entry_id] = round(item_qty_map.get(entry_id, 0.0) + qty_val, 3)
            items_lines_by_id.setdefault(entry_id, []).append(item_entry)
            if item_entry.get('selected_discount'):
                item_discount_map[entry_id] = item_entry.get('selected_discount')

        item_ids = list(item_qty_map.keys())

        # =========================================================================
        # 1. VALIDACIONES PRELIMINARES (Ahorran recursos)
        # =========================================================================
        try:
            store = CompanyStore.objects.select_related(
                'company'
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

        # Validar que el usuario NO tenga órdenes activas en esta misma tienda
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

        # 💡 Buscamos la ubicación de forma segura
        client_location = None
        if location_id is not None:
            try:
                client_location = ClientLocation.objects.get(id=location_id, user=request.user)
            except (ClientLocation.DoesNotExist, ValueError, TypeError):
                return Response({"error": "La dirección seleccionada no es válida."}, status=status.HTTP_404_NOT_FOUND)
        elif withdrawal_type == WithdrawalType.DELIVERY:
            return Response({"error": "Debes seleccionar una dirección de entrega para pedidos con delivery."}, status=status.HTTP_400_BAD_REQUEST)

        # =========================================================================
        # 2. BLOQUEO ATÓMICO Y HARD RESERVATION
        # =========================================================================
        try:
            with transaction.atomic():
                # Filtramos explícitamente por store=store y usamos of=('self',) porque 'offer' es un OneToOne inverso (LEFT OUTER JOIN en PostgreSQL)
                inventory_items = list(
                    InventoryItem.objects.select_for_update(of=('self',))
                    .select_related('product', 'product__category', 'offer')
                    .filter(id__in=item_ids, store=store)
                )

                # 💡 CASO 1: Un producto fue borrado de la BD o no pertenece a la tienda
                if len(inventory_items) != len(item_ids):
                    found_ids = set(str(item.id) for item in inventory_items)
                    missing_ids = set(item_ids) - found_ids
                    return Response({
                        "error": "PRODUCTO_ELIMINADO",
                        "product_id": list(missing_ids)[0],
                        "message": "Uno de los productos en tu carrito fue retirado del catálogo por el vendedor. Hemos actualizado tu carrito."
                    }, status=status.HTTP_404_NOT_FOUND)

                # Validamos en servidor los descuentos por tokens contra item.product.discounts_data real en BD
                validated_discount_map = {}
                total_tokens_needed = 0
                for item in inventory_items:
                    item_id_str = str(item.id)
                    req_discount = item_discount_map.get(item_id_str)
                    if not req_discount:
                        continue
                    if not isinstance(req_discount, dict):
                        return Response({"error": "Formato de descuento inválido."}, status=status.HTTP_400_BAD_REQUEST)
                    if not store.company.gamification_enabled or not item.product.discounts_by_tokens_active:
                        return Response({
                            "error": "DESCUENTO_NO_DISPONIBLE",
                            "message": f"Los descuentos por tokens no están habilitados para '{item.product.name}'."
                        }, status=status.HTTP_409_CONFLICT)
                    try:
                        req_tokens = int(req_discount.get('tokens', 0))
                        req_pct = float(req_discount.get('percentage', 0))
                    except (ValueError, TypeError):
                        return Response({"error": "Valores de descuento inválidos."}, status=status.HTTP_400_BAD_REQUEST)

                    matched_tier = None
                    for tier in (item.product.discounts_data or []):
                        if not isinstance(tier, dict):
                            continue
                        try:
                            tier_tokens = int(tier.get('tokens', -1))
                            tier_pct = float(tier.get('percentage', -1))
                        except (ValueError, TypeError):
                            continue
                        if tier_tokens == req_tokens and abs(tier_pct - req_pct) < 0.01 and tier_tokens > 0 and 0 < tier_pct <= 100:
                            matched_tier = {'tokens': tier_tokens, 'percentage': tier_pct}
                            break

                    if not matched_tier:
                        return Response({
                            "error": "DESCUENTO_INVALIDO",
                            "message": f"El descuento por tokens seleccionado para '{item.product.name}' ya no es válido."
                        }, status=status.HTTP_409_CONFLICT)

                    validated_discount_map[item_id_str] = matched_tier
                    total_tokens_needed += matched_tier['tokens']

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

                cart_snapshot = []
                total_price = 0.0

                for item in inventory_items:
                    item_id_str = str(item.id)
                    requested_qty_total = item_qty_map[item_id_str]
                    stock_units_to_deduct = max(1, int(math.ceil(requested_qty_total)))
                    
                    # 💡 CASO 2: El producto fue pausado
                    if item.paused:
                        return Response({
                            "error": "PRODUCTO_PAUSADO",
                            "product_id": item_id_str,
                            "message": f"El vendedor acaba de pausar la venta de '{item.product.name}'. Por favor, retíralo de tu carrito para continuar."
                        }, status=status.HTTP_409_CONFLICT)
                    
                    # 💡 CASO 3: Stock agotado totalmente o parcialmente
                    if item.stock < stock_units_to_deduct:
                        if item.stock == 0:
                            msg = f"¡Ups! Alguien más acaba de comprar la última unidad de '{item.product.name}'. Lo hemos retirado de tu carrito."
                        else:
                            msg = f"Hemos ajustado tu pedido de '{item.product.name}' de {requested_qty_total:g} a {item.stock} {item.product.unit_label or 'unidades'}, que es el stock disponible actualmente."
                            
                        return Response({
                            "error": "STOCK_INSUFICIENTE",
                            "product_id": item_id_str,
                            "available_stock": item.stock,
                            "message": msg
                        }, status=status.HTTP_409_CONFLICT)
                    
                    # Todo en orden: Descontamos del inventario de la sucursal
                    item.stock -= stock_units_to_deduct
                    if item.stock <= 0:
                        item.sold_out_time = timezone.now()
                        if item.stock < 0:
                            item.stock = 0
                    item.save()

                    # Oferta estándar activa sobre el lote
                    standard_offer_pct = None
                    if hasattr(item, 'offer') and item.offer and item.offer.valid_until >= timezone.now():
                        standard_offer_pct = int(item.offer.percentage)

                    applied_token_discount = validated_discount_map.get(item_id_str)
                    if standard_offer_pct and applied_token_discount:
                        return Response({
                            "error": "OFERTAS_NO_ACUMULABLES",
                            "message": f"El producto '{item.product.name}' ya tiene una oferta de la tienda, por lo que no es acumulable con descuentos por tokens."
                        }, status=status.HTTP_409_CONFLICT)

                    img_url = storage_manager.get_url(item.product.images[0]) if item.product.images else ""
                    token_discount_already_applied_for_item = False
                    product_variants_modified = False

                    for req_line in items_lines_by_id.get(item_id_str, []):
                        line_qty_float = float(req_line.get('quantity', 1))
                        line_qty = int(line_qty_float) if line_qty_float.is_integer() else round(line_qty_float, 3)
                        line_stock_units = max(1, int(math.ceil(line_qty_float)))

                        # Cálculo dinámico de precio (variantes + modificadores/extras)
                        dynamic_unit_price, selection_meta = resolve_cart_item_dynamic_pricing(item.product, req_line)

                        # Si el InventoryItem tiene custom_price y la variante no definió precio absoluto propio,
                        # usamos custom_price como base + deltas de variante y modificadores
                        sel_var = selection_meta.get("selected_variant")
                        if item.custom_price is not None:
                            var_delta = float(sel_var.get("price_delta", 0.0)) if sel_var else 0.0
                            mod_delta = float(selection_meta.get("modifiers_total_delta", 0.0))
                            line_base_unit_price = max(0.0, float(item.custom_price) + var_delta + mod_delta)
                        else:
                            line_base_unit_price = dynamic_unit_price

                        # Validar y descontar stock específico de la variante (si el comerciante definió stock por variante)
                        if sel_var and isinstance(item.product.variants, list):
                            for raw_v in item.product.variants:
                                if isinstance(raw_v, dict) and str(raw_v.get('id')) == str(sel_var.get('id')):
                                    if raw_v.get('stock') is not None:
                                        try:
                                            v_stock = int(raw_v['stock'])
                                        except (ValueError, TypeError):
                                            v_stock = None
                                        if v_stock is not None:
                                            if v_stock < line_stock_units:
                                                return Response({
                                                    "error": "STOCK_VARIANTE_INSUFICIENTE",
                                                    "product_id": item_id_str,
                                                    "variant_id": sel_var.get("id"),
                                                    "available_stock": v_stock,
                                                    "message": f"La variante '{sel_var.get('name')}' de '{item.product.name}' solo tiene {v_stock} disponible(s)."
                                                }, status=status.HTTP_409_CONFLICT)
                                            raw_v['stock'] = max(0, v_stock - line_stock_units)
                                            raw_v['is_available'] = raw_v['stock'] > 0
                                            product_variants_modified = True
                                    break

                        if standard_offer_pct:
                            line_base_unit_price = round(
                                line_base_unit_price - (line_base_unit_price * (standard_offer_pct / 100.0)),
                                2,
                            )

                        subtotal = round(line_base_unit_price * line_qty_float, 2)

                        line_token_discount = None
                        if applied_token_discount and not token_discount_already_applied_for_item:
                            pct = float(applied_token_discount['percentage'])
                            ahorro = line_base_unit_price * (pct / 100.0)
                            subtotal = round(max(0.0, subtotal - ahorro), 2)
                            line_token_discount = applied_token_discount
                            token_discount_already_applied_for_item = True

                        source_video_id = req_line.get('source_video_id')
                        is_from_atlas = req_line.get('isFromAtlas', False)

                        # Construir título descriptivo si tiene variante (mantiene 'name' limpio y agrega 'display_name')
                        display_name = item.product.name
                        if sel_var and sel_var.get("name"):
                            display_name = f"{item.product.name} ({sel_var['name']})"

                        cart_snapshot.append({
                            "product_id": str(item.product.id),
                            "inventory_item_id": item_id_str,
                            "name": item.product.name,
                            "display_name": display_name,
                            "quantity": line_qty,
                            "stock_units_deducted": line_stock_units,
                            "selling_unit": selection_meta["selling_unit"],
                            "unit_label": selection_meta["unit_label"],
                            "unit_price": round(line_base_unit_price, 2),
                            "subtotal": subtotal,
                            "product_image": img_url,
                            "selected_variant": sel_var,
                            "selected_modifiers": selection_meta["selected_modifiers"],
                            "selected_options": selection_meta["selected_options"],
                            "customer_notes": selection_meta["customer_notes"],
                            "standard_offer_applied": standard_offer_pct,
                            "token_discount_applied": line_token_discount,
                            "source_video_id": source_video_id,
                            "is_from_atlas": is_from_atlas
                        })
                        total_price = round(total_price + subtotal, 2)

                    if product_variants_modified:
                        item.product.save(update_fields=['variants'])

                # 3. Creamos la orden oficial
                order = Order.objects.create(
                    store=store,
                    client=request.user,
                    client_location=client_location,
                    cart={"items": cart_snapshot, "total": round(total_price, 2)},
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
                
                # Invalidamos caché volátil y notificamos tras commit exitoso
                volatile_keys_to_del = [f"cartmaker:volatile:item:{item.id}" for item in inventory_items]
                struct_keys_to_del = [f"cartmaker:struct:item:{item.id}" for item in inventory_items]
                merchant_id = store.company.owner_id
                final_order_id = order.id
                final_store_name = store.name
                final_total = order.cart.get('total', 0.0)

                def _post_order_commit():
                    cache.delete_many(volatile_keys_to_del + struct_keys_to_del)
                    firebase_admin.NotificationManager.notify_order_created(
                        merchant_id=merchant_id,
                        order_id=final_order_id,
                        store_name=final_store_name,
                        total=final_total
                    )

                transaction.on_commit(_post_order_commit)

            return Response({
                "success": True, 
                "order_id": str(order.id), 
                "message": "¡Orden creada exitosamente!"
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.exception(f"Error en create_order: {e}")
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

        # Preparamos el payload añadiendo el ID del usuario y metadatos de atribución (Atlas IA / Orgánico)
        payload = {
            'client_id': str(request.user.id),
            'item_id': str(item_id),
            'added_to_cart': data.get('added_to_cart', False),
            'bought': data.get('bought', False),
            'start_time': start_time_raw,
            'end_time': data.get('end_time'),
            'origin_source': data.get('origin_source', 'organic'),
            'search_prompt': data.get('search_prompt'),
            'ai_keywords': data.get('ai_keywords'),
            'atlas_message_id': data.get('atlas_message_id'),
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

    def get_permissions(self):
        if self.action == 'profile':
            return [AllowAny()]
        return [IsAuthenticated()]

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
            base_store_qs = CompanyStore.objects.select_related(
                'company', 'company__category', 'location', 'location__mall'
            ).prefetch_related('contact_methods')

            if store_id and store_id != 'null': 
                store = base_store_qs.filter(
                    id=store_id,
                    is_active=True
                ).first()

                # Parche: Si no la encontró, verificamos si por error Flutter mandó el ID de la compañía aquí
                if not store:
                    store = base_store_qs.filter(
                        company_id=store_id,
                        is_main_store=True,
                        is_active=True
                    ).first()

                if not store:
                    return Response({'error': 'La tienda solicitada no existe, fue eliminada o está inactiva.'}, status=status.HTTP_404_NOT_FOUND)
                company = store.company
                
            elif company_id and company_id != 'null':
                # Solo entramos aquí si Flutter explícitamente NO mandó un store_id
                store = base_store_qs.filter(
                    company_id=company_id, 
                    is_active=True
                ).order_by('-is_main_store', 'creation').first()
                
                if not store:
                    return Response({'error': 'La compañía no tiene tiendas activas.'}, status=status.HTTP_404_NOT_FOUND)
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

            available_stores_qs = CompanyStore.objects.select_related(
                'company', 'location', 'location__mall'
            ).prefetch_related('contact_methods').filter(
                company=company,
                is_active=True
            ).order_by('-is_main_store', 'creation')

            available_stores = [s.get_json() for s in available_stores_qs]

            # =======================================================
            # 3. CONSTRUCCIÓN DE LA RESPUESTA
            # =======================================================
            company_metadata = company.get_json()
            company_metadata['avg_rating'] = avg_rating
            company_metadata['total_sales'] = formatted_sales
            company_metadata['total_sales_raw'] = total_sales
            company_metadata['merchant_type'] = company.get_merchant_type_display()
            
            store_metadata = store.get_json()

            if request.user.is_authenticated:
                token_wallet = company.issued_wallets.filter(user=request.user).first()
            else:
                token_wallet = None

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
            logger.exception(f"Error en ClientCompanyViewSet.profile: {e}")
            return Response({'error': 'Error interno al cargar el perfil del comercio.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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

    def get_permissions(self):
        if self.action in ('list_comments', 'single_feed_post'):
            return [AllowAny()]
        return [IsAuthenticated()]

    @action(detail=False, methods=['get'])
    def merchant_items_summary(self, request):
        """
        Retorna la TOTALIDAD de los productos y videos del comerciante,
        calculando sus preguntas pendientes para servir como panel histórico.
        """
        user = request.user
        item_ct = ContentType.objects.get_for_model(InventoryItem)
        video_ct = ContentType.objects.get_for_model(CompanyVideoStory)

        # ==========================================
        # 1. OBTENER TODO EL INVENTARIO Y SUS ALERTAS
        # ==========================================
        db_items = list(InventoryItem.objects.select_related('product').filter(
            store__company__owner=user
        ))
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
        db_videos = list(CompanyVideoStory.objects.filter(company__owner=user))
        videos_ids_strs = [str(vid.id) for vid in db_videos]

        videos_summary = UniversalComment.objects.filter(
            content_type=video_ct,
            object_id__in=videos_ids_strs
        ).values('object_id').annotate(
            pending=Count('id', filter=Q(answer_text__isnull=True) | Q(answer_text__exact=''))
        )
        videos_dict = {video['object_id']: video['pending'] for video in videos_summary}

        # ==========================================
        # 3. COMPILACIÓN DE DATA COMPLETA (SIN LLAMAR A get_json() COMPLETO)
        # ==========================================
        data = []

        # Mapeamos absolutamente todos los productos
        for item in db_items:
            item_id_str = str(item.id)
            prod = item.product
            first_img = storage_manager.get_url(prod.images[0]) if prod.images else ''
            
            data.append({
                "id": item_id_str,
                "name": prod.name or 'Producto sin nombre',
                "image": first_img,
                "type": "product",
                "pending_questions_count": products_dict.get(item_id_str, 0),
                "creation": item.creation # 💡 Inyectamos la fecha nativa para ordenar
            })

        # Mapeamos absolutamente todos los videos
        for vid in db_videos:
            vid_id_str = str(vid.id)
            raw_desc = vid.description or ''
            clean_desc = raw_desc.strip() if raw_desc else "Video Historia sin descripción"
            thumb_url = storage_manager.get_url(vid.thumbnail) if vid.thumbnail else ''
            
            data.append({
                "id": vid_id_str,
                "name": clean_desc if len(clean_desc) <= 40 else clean_desc[:40] + "...",
                "image": thumb_url, 
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

        content_type_obj = ContentType.objects.get_for_model(
            InventoryItem if content_model == 'inventoryitem' else CompanyVideoStory
        )
        
        # Pre-resolvemos el objeto padre una sola vez con sus relaciones para evitar 60-80 N+1 GenericForeignKey queries
        target_obj = None
        if content_model == 'inventoryitem':
            target_obj = InventoryItem.objects.select_related('store__company', 'product').filter(id=target_id).first()
        else:
            target_obj = CompanyVideoStory.objects.select_related('company').filter(id=target_id).first()

        # Filtramos por el tipo y el ID
        comments = UniversalComment.objects.filter(
            content_type=content_type_obj,
            object_id=target_id
        ).select_related('client', 'content_type').order_by('-question_creation')

        paginator = UniversalConversationPagination()
        paginated_qs = paginator.paginate_queryset(comments, request)

        data = [q.get_json(target_obj=target_obj) for q in paginated_qs]
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
            logger.exception(f"Error en single_feed_post: {e}")
            return Response({'error': 'Error interno al consultar el contenido.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
class ProductSearchEngineViewSet(viewsets.ViewSet):
    """
    API integral para la distribución algorítmica de productos hacia la App.
    Interactúa con el ProductSearchEngine para retornar Feeds dinámicos cacheados
    respetando exactamente las firmas de respuesta requeridas por Flutter.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'navigation'

    def get_permissions(self):
        public_reads = (
            'category', 'store', 'offers', 'text_search', 'home_feed', 'item_details',
        )
        if self.action in public_reads:
            return [AllowAny()]
        return [IsAuthenticated()]
    
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
        """Extrae de forma segura los parámetros de paginación con límites defensivos contra DoS."""
        try:
            page = max(1, int(request.query_params.get('page', 1)))
            page_size = max(1, min(50, int(request.query_params.get('page_size', 20))))
        except (ValueError, TypeError):
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

        effective_page_size = min(page_size, 10) if is_home_widget else page_size
        engine = ProductSearchEngine(lat, lng, user=request.user)
        data_list = engine.get_offers_feed(page=page, page_size=effective_page_size, sort_by=sort_by, price_order=price_order)

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

        effective_page_size = min(page_size, 10) if is_home_widget else page_size
        engine = ProductSearchEngine(lat, lng, user=request.user)
        data_list = engine.get_stores_with_tokens_feed(page=page, page_size=effective_page_size)

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

        effective_page_size = min(page_size, 10) if is_home_widget else page_size
        engine = ProductSearchEngine(lat, lng, user=request.user)
        data_list = engine.get_favorites_feed(page=page, page_size=effective_page_size, sort_by=sort_by, price_order=price_order)

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
                'product',
                'product__category',
                'product__category__parent_category',
                'product__company',
                'offer',
                'store',
                'store__company',
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

        try:
            cache.delete(f"cartmaker:affinity_profile:v1:{request.user.id}")
            if hasattr(cache, 'delete_pattern'):
                cache.delete_pattern(f"cartmaker:struct:favs:{request.user.id}:*")
        except Exception:
            pass

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
    GUEST_HEADER = 'HTTP_X_CARTMAKER_GUEST'

    def get_permissions(self):
        if self.action in ('guest_session', 'current_thread', 'message', 'stage_radar', 'stage_radar_dash'):
            return [AllowAny()]
        return [IsAuthenticated()]

    # 💡 LÍMITE DIARIO CONFIGURABLE
    DAILY_FREE_LIMIT = 15

    def _client_ip(self, request) -> str:
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
        if forwarded:
            return forwarded.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR') or 'unknown'

    def _seconds_until_midnight(self) -> int:
        now_local = timezone.localtime(timezone.now())
        tomorrow = (now_local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return max(1, int((tomorrow - now_local).total_seconds()))

    def _anonymous_daily_limit(self) -> int:
        try:
            return SystemConfig.objects.latest('creation').atlas_anonymous_daily_limit
        except SystemConfig.DoesNotExist:
            return 5

    def _guest_token_from_request(self, request) -> str:
        return (request.META.get(self.GUEST_HEADER) or '').strip()

    def _known_guest(self, token: str) -> bool:
        if not token:
            return False
        return cache.get(f"cartmaker:atlas:guest-known:{token}") is not None

    def _remember_guest(self, token: str) -> None:
        cache.set(f"cartmaker:atlas:guest-known:{token}", 1, timeout=60 * 60 * 24 * 30)

    def _anon_used(self, token: str, ip: str) -> int:
        used_token = cache.get(f"cartmaker:atlas:anon:{token}") or 0
        used_ip = cache.get(f"cartmaker:atlas:anon-ip:{ip}") or 0
        return max(int(used_token), int(used_ip))

    def _anon_remaining(self, token: str, ip: str) -> int:
        return max(0, self._anonymous_daily_limit() - self._anon_used(token, ip))

    def _consume_anon(self, token: str, ip: str) -> bool:
        if self._anon_remaining(token, ip) <= 0:
            return False
        timeout = self._seconds_until_midnight()
        for key in (f"cartmaker:atlas:anon:{token}", f"cartmaker:atlas:anon-ip:{ip}"):
            if cache.get(key) is None:
                cache.set(key, 1, timeout=timeout)
            else:
                try:
                    cache.incr(key)
                except ValueError:
                    cache.set(key, 1, timeout=timeout)
        return True

    def _refund_anon(self, token: str, ip: str) -> None:
        for key in (f"cartmaker:atlas:anon:{token}", f"cartmaker:atlas:anon-ip:{ip}"):
            try:
                current = cache.get(key)
                if current and int(current) > 0:
                    cache.decr(key)
            except Exception:
                pass

    def _login_required_payload(self, daily_limit: int) -> dict:
        return {
            'error': 'Inicia sesión para seguir hablando con Atlas.',
            'free_interactions_left': 0,
            'login_required': True,
            'daily_limit': daily_limit,
            'is_premium': False,
        }

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
        try:
            config = SystemConfig.objects.latest('creation')
            plus_limit = config.atlas_plus_daily_limit
            free_limit = config.atlas_free_daily_limit
        except SystemConfig.DoesNotExist:
            plus_limit = 75
            free_limit = self.DAILY_FREE_LIMIT
        try:
            plan = user.atlas_plan
            # Si es Premium y el plan no ha vencido
            if plan.tier == AtlasSubscriptionTier.PREMIUM and plan.valid_until and plan.valid_until >= timezone.now():
                return plus_limit
        except AtlasPlusPlan.DoesNotExist:
            pass
        return free_limit

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
    # ENDPOINT: POST /api/v1/atlas/guest-session/
    # ------------------------------------------------------------------------
    @action(detail=False, methods=['post'], url_path='guest-session')
    def guest_session(self, request):
        if request.user.is_authenticated:
            free_left = self._get_free_interactions_left(request.user)
            plan = self._get_user_plan(request.user)
            is_premium = bool(
                plan and plan.tier == AtlasSubscriptionTier.PREMIUM
                and plan.valid_until and plan.valid_until >= timezone.now()
            )
            return Response({
                'guest_token': None,
                'free_interactions_left': free_left,
                'daily_limit': self._get_daily_limit(request.user),
                'is_premium': is_premium,
                'login_required': False,
            }, status=status.HTTP_200_OK)

        daily_limit = self._anonymous_daily_limit()
        ip = self._client_ip(request)
        token = self._guest_token_from_request(request)
        if not self._known_guest(token):
            if (cache.get(f"cartmaker:atlas:anon-ip:{ip}") or 0) >= daily_limit:
                return Response(self._login_required_payload(daily_limit), status=status.HTTP_403_FORBIDDEN)
            token = secrets.token_urlsafe(32)
            self._remember_guest(token)
        else:
            self._remember_guest(token)

        remaining = self._anon_remaining(token, ip)
        return Response({
            'guest_token': token,
            'free_interactions_left': remaining,
            'daily_limit': daily_limit,
            'is_premium': False,
            'login_required': remaining <= 0,
        }, status=status.HTTP_200_OK)

    # ------------------------------------------------------------------------
    # ENDPOINT: GET /api/v1/atlas/current_thread/
    # ------------------------------------------------------------------------
    @action(detail=False, methods=['get'])
    def current_thread(self, request):
        if request.user.is_authenticated:
            plan = request.user.atlas_plan
            is_premium = plan.tier == AtlasSubscriptionTier.PREMIUM and plan.valid_until and plan.valid_until >= timezone.now()
            free_left = self._get_free_interactions_left(request.user)
            latest_thread = AtlasThread.objects.filter(plan=plan).order_by('-id').first()
            nombre_usuario = request.user.first_name.strip() if request.user.first_name else ""
        else:
            token = self._guest_token_from_request(request)
            if not self._known_guest(token):
                return Response(
                    self._login_required_payload(self._anonymous_daily_limit()),
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            is_premium = False
            free_left = self._anon_remaining(token, self._client_ip(request))
            latest_thread = AtlasThread.objects.filter(guest_key=token).order_by('-id').first()
            nombre_usuario = ""

        starter_quick_actions = [
            {"id": "qa_open_now", "label": "🟢 Abiertos ahora", "prompt": "Muéstrame tiendas y productos abiertos ahorita cerca de mi ubicación", "action_type": "STAGE_RADAR", "radar_params": {"intent": "FEED", "enfoque": "OPEN_NOW"}},
            {"id": "qa_flash_offers", "label": "⚡ Ofertas Flash", "prompt": "¿Qué ofertas y descuentos hay cerca de mí hoy?", "action_type": "STAGE_RADAR", "radar_params": {"intent": "FEED", "enfoque": "FLASH_OFFERS"}},
            {"id": "qa_tokens", "label": "🪙 Canjear Tokens", "prompt": "¿En qué productos puedo canjear o ganar tokens hoy?", "action_type": "STAGE_RADAR", "radar_params": {"intent": "FEED", "enfoque": "TOKEN_REWARDS"}},
            {"id": "qa_smart_bundle", "label": "🛒 Armar compra inteligente", "prompt": "Ayúdame a armar una lista de mercado al mejor precio en mi zona", "action_type": "SEND_PROMPT"},
        ]

        if not latest_thread:
            if request.user.is_authenticated:
                latest_thread = AtlasThread.objects.create(plan=request.user.atlas_plan)
            else:
                latest_thread = AtlasThread.objects.create(guest_key=token, plan=None)
            
            saludo_nombre = f", {nombre_usuario}" if nombre_usuario else ""
            # 💡 2. BANCO DE SALUDOS INICIALES DINÁMICOS (Naturales, sin muletillas prohibidas)
            saludos_templates = [
                f"¡Epa{saludo_nombre}! Qué bueno tenerte por aquí. Soy Atlas. Dime qué andas buscando hoy y rastreo el inventario de tu zona al instante.",
                f"¡Hola{saludo_nombre}! Por aquí Atlas. Estoy listo para conseguirte el mejor precio, armar tu mercado o mostrarte qué tiendas están abiertas ahorita.",
                f"¡Qué más{saludo_nombre}! Te saluda Atlas. Dime qué producto necesitas o toca uno de los accesos rápidos para explorar el radar de tu zona.",
                f"¡Hola{saludo_nombre}! Aquí Atlas reportándose. Cuéntame qué tienes en mente comprar hoy y te ubico las mejores opciones cerca de ti.",
            ]
            
            mensaje_bienvenida = random.choice(saludos_templates)
            welcome_experience = {
                "version": "2.0",
                "ui_mode": "CONVERSATIONAL",
                "cinematic_directive": {
                    "animation_type": "IDLE_PULSE",
                    "mood_theme": "DEFAULT",
                    "auto_expand_map": False,
                    "show_radar_pulse": False,
                    "sound_haptic_cue": "SOFT_POP",
                    "camera_keyframes": [],
                    "target_bounding_box": None,
                    "route_polyline_points": [],
                },
                "stores_map": [],
                "comparison_highlights": None,
                "smart_bundle": None,
                "video_reels": [],
                "token_opportunities": {
                    "items_with_redeemable_discount": 0,
                    "max_immediate_savings_usd": 0.0,
                    "best_item_id": None,
                },
                "zone_transition": None,
                "quick_actions": starter_quick_actions,
            }
            
            AtlasMessage.objects.create(
                conversation=latest_thread,
                origin=2,
                text=mensaje_bienvenida,
                product_ids=[],
                action_command={"action": "NONE", "atlas_experience": welcome_experience}
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
            fresh_items = InventoryItem.objects.filter(id__in=all_product_ids).select_related(
                'product',
                'product__category',
                'store__company',
                'store__location',
                'store__location__mall',
            )
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
                    if str(pid) in items_dict:
                        msg_products.append(items_dict[str(pid)])
                    else:
                        msg_products.append({"id": pid, "paused": True, "stock": 0})

            cmd = getattr(m, 'action_command', None)
            if isinstance(cmd, str):
                try:
                    cmd = json.loads(cmd)
                except Exception:
                    cmd = None

            msg_experience = cmd.get("atlas_experience") if isinstance(cmd, dict) else None

            messages_data.append({
                "id": m.id,
                "origin": m.origin, 
                "text": m.text,
                "type": msg_type,
                "products": msg_products if msg_products else None,
                "creation": m.creation.isoformat(),
                "action_command": cmd,
                "atlas_experience": msg_experience,
            })

        if request.user.is_authenticated:
            daily_limit = self._get_daily_limit(request.user)
            login_required = False
        else:
            daily_limit = self._anonymous_daily_limit()
            login_required = free_left <= 0

        return Response({
            'thread_id': latest_thread.id,
            'free_interactions_left': free_left,
            'is_premium': is_premium,
            'daily_limit': daily_limit,
            'login_required': login_required,
            'initial_quick_actions': starter_quick_actions,
            'messages': messages_data
        }, status=status.HTTP_200_OK)

    # ------------------------------------------------------------------------
    # ENDPOINT: POST /api/v1/atlas/{id}/message/
    # ------------------------------------------------------------------------
    @action(detail=True, methods=['post'])
    def message(self, request, pk=None):
        text = request.data.get('text')
        image_base64 = request.data.get('image_base64')
        
        if not text:
            return Response({'error': 'El texto del mensaje es obligatorio.'}, status=status.HTTP_400_BAD_REQUEST)

        guest_token = None
        guest_ip = None
        if request.user.is_authenticated:
            try:
                thread = AtlasThread.objects.get(pk=pk, plan=request.user.atlas_plan)
            except AtlasThread.DoesNotExist:
                return Response({'error': 'El hilo no existe.'}, status=status.HTTP_404_NOT_FOUND)
            plan = request.user.atlas_plan
            is_premium = plan.tier == AtlasSubscriptionTier.PREMIUM and plan.valid_until and plan.valid_until >= timezone.now()
            if not self._consume_free_interaction(request.user):
                mensaje_error = 'Has agotado tus interacciones de Atlas Plus por hoy.' if is_premium else 'Has agotado tus interacciones gratuitas por hoy.'
                return Response({
                    'error': mensaje_error,
                    'free_interactions_left': 0,
                    'login_required': False,
                }, status=status.HTTP_403_FORBIDDEN)
            atlas_user = request.user
        else:
            guest_token = self._guest_token_from_request(request)
            if not self._known_guest(guest_token):
                return Response(
                    self._login_required_payload(self._anonymous_daily_limit()),
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            try:
                thread = AtlasThread.objects.get(pk=pk, guest_key=guest_token)
            except AtlasThread.DoesNotExist:
                return Response({'error': 'El hilo no existe.'}, status=status.HTTP_404_NOT_FOUND)
            guest_ip = self._client_ip(request)
            is_premium = False
            if not self._consume_anon(guest_token, guest_ip):
                return Response(
                    self._login_required_payload(self._anonymous_daily_limit()),
                    status=status.HTTP_403_FORBIDDEN,
                )
            atlas_user = None

        lat = float(request.data.get('lat', 0.0) or 0.0)
        lng = float(request.data.get('lng', 0.0) or 0.0)
        user_locations = request.data.get('locations', []) or []

        atlas_manager = atlas.AtlasManager(
            user_lat=lat,
            user_lng=lng,
            user_locations=user_locations,
            user=atlas_user,
            seed=str(thread.id)
        )

        resultado = async_to_sync(atlas_manager.send_chat_message_async)(thread_id=thread.id, user_text=text, image_base64=image_base64)
        
        if not resultado.get('success'):
            if guest_token:
                self._refund_anon(guest_token, guest_ip)
            else:
                try:
                    cache_key = f"cartmaker:atlas:daily_usage:{request.user.id}"
                    current = cache.get(cache_key)
                    if current and int(current) > 0:
                        cache.decr(cache_key)
                except Exception:
                    pass
            return Response({'error': resultado.get('error')}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 💡 ZERO-RESULTS QUOTA SHIELD: Si el usuario buscó un producto y no había stock en ninguna zona,
        # no le penalizamos su cuota diaria.
        quota_refunded = False
        if resultado.get('zero_results_refund_eligible'):
            quota_refunded = True
            if guest_token:
                self._refund_anon(guest_token, guest_ip)
            else:
                try:
                    cache_key = f"cartmaker:atlas:daily_usage:{request.user.id}"
                    current = cache.get(cache_key)
                    if current and int(current) > 0:
                        cache.decr(cache_key)
                except Exception:
                    pass

        if guest_token:
            free_left = self._anon_remaining(guest_token, guest_ip)
            daily_limit = self._anonymous_daily_limit()
            login_required = free_left <= 0
        else:
            free_left = self._get_free_interactions_left(request.user)
            daily_limit = self._get_daily_limit(request.user)
            login_required = False
            
        print(f"📦 [VIEWS] Comando enviado al Frontend: {resultado.get('action_command')}")
            
        return Response({
            'response': resultado['response'],
            'message_id': resultado['message_id'],
            'free_interactions_left': free_left,
            'daily_limit': daily_limit,
            'login_required': login_required,
            'quota_refunded': quota_refunded,
            'injected_products': resultado.get('injected_products'),
            'action_command': resultado.get('action_command'),
            'atlas_experience': resultado.get('atlas_experience'),
        }, status=status.HTTP_200_OK)

    # ------------------------------------------------------------------------
    # ENDPOINT 0-TOKENS (<50ms): GET/POST /api/v1/atlas/stage_radar/
    # Permite al Frontend disparar escaneos de radar, filtros rápidos, cambios
    # de cámara en el mapa o armar combos SIN gastar tokens de Gemini ni cuota.
    # ------------------------------------------------------------------------
    def _handle_stage_radar(self, request):
        data = request.data if request.method == 'POST' else request.query_params
        try:
            lat = float(data.get('lat', 0.0) or 0.0)
            lng = float(data.get('lng', 0.0) or 0.0)
        except (TypeError, ValueError):
            lat, lng = 0.0, 0.0

        user_locations = data.get('locations', []) if isinstance(data.get('locations'), list) else []
        atlas_user = request.user if request.user.is_authenticated else None
        seed = str(data.get('seed') or (atlas_user.id if atlas_user else 'stage-radar'))

        intent = str(data.get('intent', 'FEED') or 'FEED').upper()
        query = str(data.get('query', '') or '').strip()

        def _to_bool(val, default=False):
            if val is None:
                return default
            if isinstance(val, bool):
                return val
            return str(val).strip().lower() in ('1', 'true', 'yes', 'si', 'sí')

        def _to_float(val):
            try:
                return float(val) if val is not None and val != '' else None
            except (TypeError, ValueError):
                return None

        atlas_manager = atlas.AtlasManager(
            user_lat=lat,
            user_lng=lng,
            user_locations=user_locations,
            user=atlas_user,
            seed=seed,
        )

        injected_products = []
        smart_bundle = None
        zone_transition = None
        applied_filters = {}
        tools_used = []

        mode_raw = str(data.get('mode') or 'best').lower()
        mode_map = {
            'cheapest': 'cheap',
            'cheap': 'cheap',
            'nearest': 'nearby',
            'nearby': 'nearby',
            'fastest': 'nearby',
            'balanced': 'best',
            'best': 'best',
            'discounts': 'cheap',
        }
        mapped_mode = mode_map.get(mode_raw, 'best')

        if intent == 'SHOPPING_LIST':
            raw_items = data.get('items') or []
            if isinstance(raw_items, str):
                raw_items = [x.strip() for x in raw_items.split(',') if x.strip()]
            title = str(data.get('title') or 'Compra Inteligente Atlas')
            budget_max_usd = _to_float(data.get('budget_max_usd'))
            plan = atlas_manager._execute_shopping_list({
                'items': raw_items,
                'titulo_plan': title,
                'presupuesto_max_usd': budget_max_usd,
                'mode': mapped_mode,
            })
            smart_bundle = plan
            injected_products = list(plan.get('injected', []))
            tools_used.append('armar_lista_o_receta')
        elif intent == 'SEARCH' or query:
            search_args = {
                'query': query,
                'mode': mapped_mode,
                'categoria': data.get('category') or data.get('categoria'),
                'comercio_o_centro_comercial': data.get('company') or data.get('tienda_o_empresa'),
                'solo_abiertos_ahora': _to_bool(data.get('only_open_now') or data.get('solo_abiertos_ahora'), False),
                'solo_ofertas': _to_bool(data.get('only_offers') or data.get('solo_ofertas') or (mode_raw == 'discounts'), False),
                'solo_con_descuento_tokens': _to_bool(data.get('only_token_discounts') or data.get('solo_descuento_tokens'), False),
                'precio_min_usd': _to_float(data.get('min_price') or data.get('precio_min')),
                'precio_max_usd': _to_float(data.get('max_price') or data.get('precio_max')),
                'unidad_venta': data.get('selling_unit') or data.get('unidad_venta'),
                'atributo_o_variante': data.get('variant_or_attribute') or data.get('atributo_o_variante'),
                'solo_en_centro_comercial': _to_bool(data.get('mall_only') or data.get('solo_centro_comercial'), False),
            }
            db_res = atlas_manager._execute_search(search_args)
            if db_res.get('applied_filters'):
                applied_filters.update(db_res['applied_filters'])
            if query:
                applied_filters['query'] = query
            if db_res.get('type') == 'results':
                injected_products = list(db_res.get('data', []))
                zone_transition = db_res.get('zone_transition')
            tools_used.append('buscar_productos_inventario')
        else:
            enfoque = str(data.get('enfoque') or data.get('focus') or 'parati').lower()
            if enfoque in ('open_now', 'abiertos_cerca'):
                applied_filters['only_open_now'] = True
            elif enfoque in ('flash_offers', 'ofertas'):
                applied_filters['only_offers'] = True
            elif enfoque in ('token_rewards', 'mis_tokens'):
                applied_filters['only_token_discounts'] = True
            injected_products = atlas_manager._execute_personalized_feed({
                'enfoque': enfoque,
                'categoria': data.get('category') or data.get('categoria'),
            })
            tools_used.append('explorar_feed_personalizado')

        atlas_experience = atlas_manager._build_atlas_experience(
            user_text=query or intent,
            injected_products=injected_products,
            smart_bundle=smart_bundle,
            zone_transition=zone_transition,
            tools_used=tools_used,
            applied_filters=applied_filters,
        )
        action_command = {
            "action": atlas_experience["ui_mode"],
            "ui_mode": atlas_experience["ui_mode"],
            "cinematic_directive": atlas_experience["cinematic_directive"],
            "quick_actions": atlas_experience["quick_actions"],
            "atlas_experience": atlas_experience,
        }

        return Response({
            'success': True,
            'zero_token_engine': True,
            'injected_products': injected_products,
            'action_command': action_command,
            'atlas_experience': atlas_experience,
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get', 'post'], url_path='stage_radar')
    def stage_radar(self, request):
        return self._handle_stage_radar(request)

    @action(detail=False, methods=['get', 'post'], url_path='stage-radar')
    def stage_radar_dash(self, request):
        return self._handle_stage_radar(request)

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
            parsed_date = parse_flexible_date(valid_until_raw)
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
                locked_item = InventoryItem.objects.select_for_update().get(pk=item.pk)
                # 1. Actualizamos el stock de forma atómica
                locked_item.stock += units
                locked_item.creation = timezone.now()
                locked_item.save()

                # 2. Registramos el movimiento en el historial como INGRESO DE STOCK (TransactionType.INCOME = 0)
                InventoryItemTransaction.objects.create(
                    item=locked_item,
                    units=units,
                    transaction_type=TransactionType.INCOME
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
        return Product.objects.select_related('company', 'category__parent_category').filter(company__owner=self.request.user).order_by('-creation')

    @action(detail=False, methods=['get'], url_path='schema', permission_classes=[AllowAny])
    def schema(self, request):
        """
        Devuelve el esquema dinámico de creación de producto para la subcategoría o categoría solicitada.
        GET /api/v1/products/schema/?subcategory_id=X
        """
        return CategoryProductSchemaAPI().get(request)
    
    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """
        Recibe un lote de productos y los guarda todos de golpe usando bulk_create.
        Soporta campos dinámicos por categoría (selling_unit, attributes, variants, modifier_groups).
        """
        from api.core.category_schemas import validate_and_normalize_product_dynamic_data

        company_id = request.data.get('company_id')
        try:
            company = Company.objects.get(id=company_id, owner=request.user)
        except Company.DoesNotExist:
            return Response({'error': 'Compañía no encontrada'}, status=status.HTTP_404_NOT_FOUND)

        raw_products = request.data.get('products_data')
        if not raw_products:
            return Response({'error': 'Faltan los datos de los productos.'}, status=status.HTTP_400_BAD_REQUEST)

        if isinstance(raw_products, list):
            products_list = raw_products
        else:
            try:
                products_list = json.loads(raw_products)
            except json.JSONDecodeError:
                return Response({'error': 'El formato de products_data es inválido.'}, status=status.HTTP_400_BAD_REQUEST)

        created_products_json = []
        dtnow_str = timezone.localtime(timezone.now()).strftime('%d-%m-%Y_%H-%M-%S')

        try:
            with transaction.atomic():
                # 1. Pre-cargar subcategorías involucradas en un solo viaje a la BD
                category_ids = {prod_data['category_id'] for prod_data in products_list if prod_data.get('category_id')}
                categories_map = {
                    cat.id: cat
                    for cat in SubCategory.objects.select_related('parent_category').filter(id__in=category_ids)
                }

                # 2. Preparar las instancias en memoria
                product_instances = []
                
                for prod_data in products_list:
                    cat_id = prod_data.get('category_id')
                    category = categories_map.get(int(cat_id)) if str(cat_id).isdigit() else categories_map.get(cat_id)
                    if not category:
                        raise SubCategory.DoesNotExist(f"Subcategoría {cat_id} no encontrada.")

                    discounts_data = prod_data.get('discounts_data', [])
                    if isinstance(discounts_data, str) and discounts_data.strip():
                        try:
                            discounts_data = json.loads(discounts_data)
                        except Exception:
                            discounts_data = []

                    dynamic_data = validate_and_normalize_product_dynamic_data(
                        prod_data,
                        subcategory_name=category.name,
                        category_name=category.parent_category.name if category.parent_category_id else None,
                        base_price=float(prod_data.get('price', 0.0) or 0.0),
                    )

                    # Instanciamos sin guardar en BD todavía
                    product = Product(
                        company=company,
                        name=prod_data['name'],
                        price=prod_data['price'],
                        description=prod_data['description'],
                        category=category,
                        discounts_by_tokens_active=prod_data.get('discounts_by_tokens_active', False),
                        discounts_data=discounts_data,
                        images=[],
                        selling_unit=dynamic_data['selling_unit'],
                        unit_label=dynamic_data['unit_label'],
                        allow_fractional_quantity=dynamic_data['allow_fractional_quantity'],
                        min_order_quantity=dynamic_data['min_order_quantity'],
                        unit_step=dynamic_data['unit_step'],
                        attributes=dynamic_data['attributes'],
                        variants=dynamic_data['variants'],
                        modifier_groups=dynamic_data['modifier_groups'],
                    )
                    product_instances.append(product)

                # 3. BULK CREATE REAL (Un solo viaje a la BD)
                created_products = Product.objects.bulk_create(product_instances)

                # 4. Manejo de imágenes (Requiere los IDs que acabamos de generar)
                for prod_index, product in enumerate(created_products):
                    prod_data = products_list[prod_index]
                    image_order = prod_data.get('image_order', [])
                    if isinstance(image_order, str) and image_order.strip():
                        try:
                            image_order = json.loads(image_order)
                        except Exception:
                            image_order = []
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

                    product.images = final_images

                # 5. BULK UPDATE de imágenes en un solo viaje a la BD
                if created_products:
                    Product.objects.bulk_update(created_products, ['images'])

                for product in created_products:
                    created_products_json.append(product.get_json())

            return Response({'success': True, 'data': created_products_json}, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def create(self, request, *args, **kwargs):
        from api.core.category_schemas import validate_and_normalize_product_dynamic_data

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

                category = SubCategory.objects.select_related('parent_category').get(id=d['category_id'])
                raw_discounts = request.data.get('discounts_data')
                if isinstance(raw_discounts, str) and raw_discounts.strip():
                    discounts_data = json.loads(raw_discounts)
                elif isinstance(raw_discounts, (list, dict)):
                    discounts_data = raw_discounts
                else:
                    discounts_data = []

                dynamic_input = {}
                for dyn_key in (
                    'selling_unit', 'unit_label', 'allow_fractional_quantity',
                    'min_order_quantity', 'unit_step', 'attributes', 'variants', 'modifier_groups'
                ):
                    if dyn_key in d:
                        dynamic_input[dyn_key] = d[dyn_key]
                    elif dyn_key in request.data:
                        dynamic_input[dyn_key] = request.data.get(dyn_key)

                dynamic_data = validate_and_normalize_product_dynamic_data(
                    dynamic_input,
                    subcategory_name=category.name,
                    category_name=category.parent_category.name if category.parent_category_id else None,
                    base_price=float(d.get('price', 0.0) or 0.0),
                )

                product = Product.objects.create(
                    company=company,
                    name=d['name'],
                    price=d['price'],
                    description=d['description'],
                    category=category,
                    discounts_by_tokens_active=d.get('discounts_by_tokens_active', False),
                    discounts_data=discounts_data,
                    images=[], # Lo llenamos en el siguiente paso
                    selling_unit=dynamic_data['selling_unit'],
                    unit_label=dynamic_data['unit_label'],
                    allow_fractional_quantity=dynamic_data['allow_fractional_quantity'],
                    min_order_quantity=dynamic_data['min_order_quantity'],
                    unit_step=dynamic_data['unit_step'],
                    attributes=dynamic_data['attributes'],
                    variants=dynamic_data['variants'],
                    modifier_groups=dynamic_data['modifier_groups'],
                )

                # ===============================
                # MANEJO DE IMÁGENES (Array de Strings)
                # ===============================
                raw_image_order = request.data.get('image_order', '[]')
                image_order = json.loads(raw_image_order) if isinstance(raw_image_order, str) else (raw_image_order or [])
                
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
        from api.core.category_schemas import validate_and_normalize_product_dynamic_data

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
                    product.category = SubCategory.objects.select_related('parent_category').get(id=d['category_id'])

                raw_discounts = request.data.get('discounts_data')
                if raw_discounts is not None:
                    product.discounts_data = json.loads(raw_discounts) if isinstance(raw_discounts, str) else raw_discounts

                dynamic_input = {}
                for dyn_key in (
                    'selling_unit', 'unit_label', 'allow_fractional_quantity',
                    'min_order_quantity', 'unit_step', 'attributes', 'variants', 'modifier_groups'
                ):
                    if dyn_key in request.data:
                        dynamic_input[dyn_key] = d[dyn_key] if dyn_key in d else request.data.get(dyn_key)

                cat_obj = product.category
                dynamic_data = validate_and_normalize_product_dynamic_data(
                    dynamic_input,
                    subcategory_name=cat_obj.name if cat_obj else None,
                    category_name=cat_obj.parent_category.name if (cat_obj and cat_obj.parent_category_id) else None,
                    base_price=float(product.price or 0.0),
                    existing_product=product,
                )

                product.selling_unit = dynamic_data['selling_unit']
                product.unit_label = dynamic_data['unit_label']
                product.allow_fractional_quantity = dynamic_data['allow_fractional_quantity']
                product.min_order_quantity = dynamic_data['min_order_quantity']
                product.unit_step = dynamic_data['unit_step']
                product.attributes = dynamic_data['attributes']
                product.variants = dynamic_data['variants']
                product.modifier_groups = dynamic_data['modifier_groups']

                # ===============================
                # MANEJO DE IMÁGENES CORREGIDO
                # ===============================
                if 'image_order' in request.data:
                    raw_image_order = request.data.get('image_order', '[]')
                    image_order_from_frontend = json.loads(raw_image_order) if isinstance(raw_image_order, str) else (raw_image_order or [])
                    
                    processed_image_order = []

                    # 1. TRADUCIR URLs ABSOLUTAS A RELATIVAS
                    for item in image_order_from_frontend:
                        if item.startswith('new_image_'):
                            processed_image_order.append(item)
                        else:
                            found = False
                            for old_relative_url in product.images:
                                if old_relative_url in item:
                                    processed_image_order.append(old_relative_url)
                                    found = True
                                    break
                            
                            if not found:
                                clean_path = item.split('/media/')[-1] if '/media/' in item else item
                                processed_image_order.append(clean_path)
                    
                    # 2. BORRAR IMÁGENES DESCARTADAS
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
                                raise Exception("Error guardando nueva imagen.")
                        else:
                            final_images.append(item)

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
        raw_name = getattr(file_obj, 'name', '') or ''
        extension = raw_name.rsplit('.', 1)[-1].lower() if '.' in raw_name else ''
        if extension not in {'jpg', 'jpeg', 'png', 'webp', 'heic'}:
            return Response(
                {"error": "Formato de imagen no permitido. Usa JPG, PNG, WEBP o HEIC."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if file_obj.size > MAX_IMAGE_SIZE_MB * 1024 * 1024:
            return Response(
                {"error": f"La imagen no puede pesar más de {MAX_IMAGE_SIZE_MB}MB."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = request.user
        file_name = f"avatar_{user.id}_{timezone.localtime(timezone.now()).strftime('%d-%m-%Y_%H-%M-%S')}.{extension}"
        folder = "profiles/avatars"
        relative_path = storage_manager.save_file(file_obj, folder, file_name)
        if relative_path:
            if user.profile_picture:
                storage_manager.delete_file(user.profile_picture)
            user.profile_picture = relative_path
            user.save(update_fields=['profile_picture'])
            cache.delete(f"cartmaker:tenant:{user.id}:profile")
            return Response({
                "message": "Foto actualizada",
                "url": storage_manager.get_url(relative_path)
            })
        return Response({"error": "Error al guardar el archivo"}, status=500)

    @action(detail=False, methods=['get', 'post', 'put', 'patch'], url_path='preferences')
    def preferences(self, request):
        if request.method == 'GET':
            return Response(
                {"preferred_category_ids": request.user.get_preferred_category_ids()},
                status=status.HTTP_200_OK,
            )
        is_valid, clean_ids, error_msg = _extract_and_validate_category_ids(request.data)
        if not is_valid:
            return Response({"error": error_msg}, status=status.HTTP_400_BAD_REQUEST)

        valid_categories = list(Category.objects.filter(id__in=clean_ids).order_by('id'))
        valid_ids = [cat.id for cat in valid_categories]

        with transaction.atomic():
            request.user.preferred_categories.set(valid_categories)
            user_id = request.user.id
            transaction.on_commit(
                lambda: (
                    cache.delete(f"cartmaker:tenant:{user_id}:profile"),
                    cache.delete(f"cartmaker:affinity_profile:v1:{user_id}"),
                )
            )

        return Response(
            {"preferred_category_ids": valid_ids},
            status=status.HTTP_200_OK,
        )