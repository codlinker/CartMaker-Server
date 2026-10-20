"""Authentication, OAuth2, Biometric 512-D Login, Device Registration, and KYC Verification views."""
from .base import *
from .base import _get_cached_bcv_rate, _extract_and_validate_category_ids

####################################################
################## AUTENTICACION ###################
####################################################

class RegistDeviceView(APIView):
    serializer_class = RegistDeviceSerializer
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'

    def delete(self, request):
        token = (
            request.data.get('fcm_token')
            or request.data.get('registration_id')
            or request.query_params.get('fcm_token')
            or request.query_params.get('registration_id')
        )
        if token and str(token).strip():
            # Eliminamos el token físico sin importar la cuenta previa para impedir cruce de pushes en el mismo teléfono
            DeviceToken.objects.filter(token=str(token).strip()).delete()
        else:
            # Si el logout no envía el token en el body/query, desvinculamos los tokens activos de esta cuenta
            DeviceToken.objects.filter(user=request.user).delete()
        return Response({"message": "Token eliminado"}, status=status.HTTP_204_NO_CONTENT)

    def post(self, request):
        raw_token = request.data.get('fcm_token') or request.data.get('registration_id')
        fcm_token = str(raw_token).strip() if raw_token else ''
        platform = request.data.get('platform', 'android')
        if not fcm_token:
            return Response({'error': 'El fcm_token es obligatorio.'}, status=status.HTTP_400_BAD_REQUEST)
        if request.user.is_superuser:
            return Response({
                'error':"No se permite acceso a cuentas administrativas."
            }, status=status.HTTP_406_NOT_ACCEPTABLE)
        with transaction.atomic():
            # Unicidad de fcm_token activo: eliminamos cualquier vínculo previo con otra cuenta en este mismo dispositivo
            DeviceToken.objects.filter(token=fcm_token).exclude(user=request.user).delete()
            device, created = DeviceToken.objects.update_or_create(
                token=fcm_token,
                defaults={
                    'user': request.user, 
                    'platform': platform
                }
            )
        return Response({"message": "Dispositivo registrado", "user_id": str(request.user.id)}, status=status.HTTP_200_OK)

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
    throttle_scope = 'auth'
    permission_classes = [IsAuthenticated]

    def get(self, request, cedula_number: str):
        details = {'error': '', 'data_retrieved': False}
        status_code = status.HTTP_200_OK

        if getattr(request.user, 'cedula_verified', False):
            return Response(
                {'error': 'Tu cuenta ya posee una Cédula verificada biométricamente.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # 1. Validación de duplicados
        if User.objects.filter(cedula_number=cedula_number, is_active=True).exists():
            return Response(
                {'error': f"Ya existe un usuario con la cédula {cedula_number}."}, 
                status=status.HTTP_403_FORBIDDEN
            )

        if settings.USE_CEDULAS_API:
            cache_key = f"cm:cne_cedula:{cedula_number.upper()}"
            cached_cne = cache.get(cache_key)
            if cached_cne is not None:
                return Response(cached_cne, status=status.HTTP_200_OK)

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
                    details = dict(api_data['data'])
                    fecha_objeto = datetime.strptime(details['fecha_nac'], '%Y-%m-%d')
                    details['fecha_nac'] = fecha_objeto.strftime('%d/%m/%Y')
                    details['data_retrieved'] = True
                    cache.set(cache_key, details, timeout=86400)
                    return Response(details, status=status.HTTP_200_OK)
                
                else:
                    # CASO B:
                    # En lugar de 404, devolvemos un 200 pero avisamos que no hay data.
                    # El Flutter deberá permitirle al usuario escribir su nombre manualmente.
                    fallback_payload = {
                        'data_retrieved': False,
                        'message': 'Documento no está en CNE (posible menor de edad). Proceda con carga manual.'
                    }
                    cache.set(cache_key, fallback_payload, timeout=3600)
                    return Response(fallback_payload, status=status.HTTP_200_OK)

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

                consent_raw = str(
                    request.data.get("biometric_consent_accepted")
                    or data.get("biometric_consent_accepted")
                    or ""
                ).strip().lower()
                if consent_raw in ("true", "1", "yes"):
                    locked_user.biometric_consent_accepted_at = timezone.now()
                    locked_user.biometric_consent_version = (
                        str(
                            request.data.get("biometric_consent_version")
                            or data.get("biometric_consent_version")
                            or "VE-2026.1"
                        ).strip()[:32]
                        or "VE-2026.1"
                    )
                locked_user.biometric_suppressed_at = None
                locked_user.save()
                return Response(
                    {
                        "message": "Identidad confirmada. Ahora eres un usuario verificado en CartMaker.",
                        "biometric_consent_accepted_at": (
                            locked_user.biometric_consent_accepted_at.isoformat()
                            if locked_user.biometric_consent_accepted_at
                            else None
                        ),
                        "biometric_consent_version": locked_user.biometric_consent_version,
                    },
                    status=status.HTTP_200_OK,
                )
        except Exception as e:
            print(f"Error al verificar al usuario: {e}")
            return Response(
                {"error": "Hubo un problema al procesar tu verificación. Inténtalo de nuevo."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

