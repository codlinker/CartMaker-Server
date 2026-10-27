"""
Verificación funcional del versionado del modelo facial (fp32 -> int8) en el backend biométrico.
Uso (BD LOCAL únicamente):  python manage.py shell < scripts/verify_biometric_versions.py
Todo corre dentro de una transacción que SIEMPRE se revierte, con almacenamiento forzado a disco temporal
(nunca sube a S3) y la tarea Celery `update_rolling_template.delay` mockeada (se invoca `.run` directo).

Cubre: login/KYC sin embedding_model_version (igual que antes), con versión válida, versión inválida (400),
1:1 con versión distinta (409 REENROLL), 1:N que NO cruza versiones, duplicados KYC que no cruzan versiones,
rolling template con versión distinta (no mezcla), supresión biométrica (resetea versión) y UserCacheAPI.
"""
import io
import math
import random
import tempfile
import uuid
from unittest import mock

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection, transaction
from django.test.utils import override_settings
from PIL import Image
from rest_framework.test import APIClient

from api import utils as U
from api.cos import storage_manager
from api.models import CartMakerApiKey, User
from api.tasks import update_rolling_template

assert settings.DEBUG, 'Abortado: solo debe correrse con DEBUG=1 (entorno local)'
assert connection.settings_dict['HOST'] in ('127.0.0.1', 'localhost', ''), 'Abortado: la BD no es local'

if 'testserver' not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS.append('testserver')
storage_manager.storage_type = 'local'
settings.MEDIA_ROOT = tempfile.mkdtemp(prefix='cm_verify_bio_')

# Los throttles (429) son ajenos a lo que se verifica aquí
from rest_framework.throttling import ScopedRateThrottle  # noqa: E402
ScopedRateThrottle.allow_request = lambda self, request, view: True

FP32 = 'mobilefacenet-fp32-v1'
INT8 = 'mobilefacenet-int8-v1'
DIM = U.BIOMETRIC_VECTOR_DIMENSIONS
RESULTS = []


def check(name, cond, extra=''):
    RESULTS.append((name, bool(cond), extra))
    print(('PASS ' if cond else 'FAIL ') + name + (f'  -> {extra}' if extra and not cond else ''))


class Rollback(Exception):
    pass


# ---------------------------------------------------------------- utilidades de vectores
def unit(vec):
    n = math.sqrt(sum(x * x for x in vec))
    return [x / n for x in vec]


def rand_vec(seed):
    rng = random.Random(f'{seed}-{uuid.uuid4().hex}')
    return unit([rng.gauss(0, 1) for _ in range(DIM)])


def near(vec, s, seed=0):
    """Vector a distancia coseno ≈ 1 - 1/sqrt(1+s²) de `vec` (ruido gaussiano de norma ≈ s; s=0.5 → ≈0.106)."""
    rng = random.Random(f'near-{seed}-{uuid.uuid4().hex}')
    return unit([x + rng.gauss(0, 1) * s / math.sqrt(DIM) for x in vec])


def cos_dist(a, b):
    return 1.0 - sum(x * y for x, y in zip(a, b))


def mk_user(tag, vec=None, version=FP32, verified=True):
    u = User.objects.create_user(
        email=f"verif_bio_{tag}_{uuid.uuid4().hex[:6]}@example.com", password='Pw12345!x',
        first_name='V', last_name=tag,
    )
    if vec is not None:
        u.biometric_vector = vec
        u.biometric_model_version = version
    if verified:
        u.cedula_verified = True
        u.cedula_number = f"V{random.randint(10_000_000, 99_999_999)}"
    u.save()
    return u


def png():
    buf = io.BytesIO()
    Image.new('RGB', (64, 64), (200, 30, 30)).save(buf, format='PNG')
    return buf.getvalue()


def kyc_payload(vec, version='__omit__', **extra):
    body = {
        'first_name': 'Prueba', 'last_name': 'Biometrica',
        'cedula_number': f"V{random.randint(10_000_000, 99_999_999)}",
        'birth_date': '01/01/1990', 'nacionality': 'V',
        'cedula_photo': SimpleUploadedFile('c.png', png(), content_type='image/png'),
        'selfie_photo': SimpleUploadedFile('s.png', png(), content_type='image/png'),
        'biometry': [str(x) for x in vec],  # multipart: lista de strings
    }
    if version != '__omit__':
        body['embedding_model_version'] = version
    body.update(extra)
    return body


def client(user=None):
    c = APIClient(HTTP_X_API_KEY=RAW_KEY)
    if user is not None:
        c.force_authenticate(user)
    return c


def login(vec, version='__omit__', **extra):
    body = {'biometry': vec}
    if version != '__omit__':
        body['embedding_model_version'] = version
    body.update(extra)
    return client().post('/api/v1/biometric-login', body, format='json')


def kyc(user, vec, version='__omit__'):
    return client(user).post('/api/v1/verify-user', kyc_payload(vec, version), format='multipart')


try:
    with transaction.atomic():
        key_obj = CartMakerApiKey(name='verify-bio-tmp', scope='all')
        RAW_KEY = key_obj.generate_and_set_key()
        key_obj.save()

        # ------------------------------------------------------------------
        print('\n=== 1. HELPERS (api/utils.py) ===')
        check('constante default', U.BIOMETRIC_MODEL_CURRENT_DEFAULT == FP32)
        check('permitidas por defecto', U.BIOMETRIC_ALLOWED_MODEL_VERSIONS == {FP32, INT8}, str(U.BIOMETRIC_ALLOWED_MODEL_VERSIONS))
        check('normalize(None) => default', U.normalize_embedding_model_version(None) == FP32)
        check('normalize("") / espacios => default', U.normalize_embedding_model_version('') == FP32
              and U.normalize_embedding_model_version('   ') == FP32)
        check('normalize strip+minúsculas', U.normalize_embedding_model_version('  MobileFaceNet-INT8-V1 ') == INT8)
        for bad in ('foo', 'mobilefacenet-int4-v1', 'x' * 33, 'x' * 200):
            try:
                U.normalize_embedding_model_version(bad)
                check(f'normalize({bad[:20]!r}) lanza ValueError', False, 'no lanzó')
            except ValueError as e:
                check(f'normalize({bad[:20]!r}) lanza ValueError con mensaje', len(str(e)) > 10, str(e))
        legacy = {
            'perfect': U.BIOMETRIC_LOGIN_THRESHOLD_PERFECT, 'acceptable_1n': U.BIOMETRIC_LOGIN_THRESHOLD_ACCEPTABLE,
            'one_to_one': U.BIOMETRIC_LOGIN_THRESHOLD_1TO1, 'kyc_duplicate': U.BIOMETRIC_KYC_DUPLICATE_THRESHOLD,
            'min_margin': U.BIOMETRIC_LOGIN_MIN_MARGIN,
        }
        check('constantes antiguas intactas',
              (U.BIOMETRIC_LOGIN_THRESHOLD_PERFECT, U.BIOMETRIC_LOGIN_THRESHOLD_ACCEPTABLE, U.BIOMETRIC_LOGIN_THRESHOLD_1TO1,
               U.BIOMETRIC_KYC_DUPLICATE_THRESHOLD, U.BIOMETRIC_LOGIN_MIN_MARGIN) == (0.18, 0.26, 0.30, 0.30, 0.08))
        check('umbrales fp32 == actuales', U.get_biometric_thresholds(FP32) == legacy)
        check('umbrales int8 == actuales (iniciales)', U.get_biometric_thresholds(INT8) == legacy)
        check('get_biometric_thresholds devuelve copia', U.get_biometric_thresholds(FP32) is not U.get_biometric_thresholds(FP32))
        with override_settings(BIOMETRIC_THRESHOLD_OVERRIDES={INT8: {'acceptable_1n': 0.27, 'min_margin': 'x', 'bogus': 1}}):
            t = U._build_thresholds_by_model()
            check('overrides por settings (válidos aplican, inválidos se ignoran)',
                  t[INT8]['acceptable_1n'] == 0.27 and t[INT8]['min_margin'] == 0.08 and t[FP32]['acceptable_1n'] == 0.26 and 'bogus' not in t[INT8])
        with override_settings(BIOMETRIC_THRESHOLD_OVERRIDES='{"%s": {"kyc_duplicate": 0.33}}' % INT8):
            check('overrides como string JSON', U._build_thresholds_by_model()[INT8]['kyc_duplicate'] == 0.33)
        with override_settings(BIOMETRIC_ALLOWED_MODEL_VERSIONS=['mobilefacenet-int8-v1']):
            check('allowed por settings', U._load_allowed_model_versions() == frozenset({INT8}))

        # ------------------------------------------------------------------
        print('\n=== 2. LOGIN BIOMÉTRICO ===')
        v1 = rand_vec('u1')
        u1 = mk_user('fp32', v1, FP32)
        v2 = rand_vec('u2')
        u2 = mk_user('int8', v2, INT8)
        calls = []

        class FakeTask:
            @staticmethod
            def delay(*a, **k):
                calls.append(a)

        with mock.patch('api.views.auth_views.update_rolling_template', FakeTask):
            r = login(near(v1, 0.5))
            check('1:N sin embedding_model_version => 200 (apps viejas)', r.status_code == 200 and r.data.get('user_id') == u1.id, f'{r.status_code} {r.data}')
            check('  rolling template recibe versión fp32 por defecto', calls and calls[-1][2] == FP32 and calls[-1][0] == u1.id, str(calls))
            r = login(near(v1, 0.3), FP32)
            check('1:N con fp32 explícito => 200', r.status_code == 200 and r.data.get('user_id') == u1.id, f'{r.status_code}')
            r = login(near(v1, 0.3), '  MobileFaceNet-FP32-V1 ')
            check('1:N con versión en mayúsculas/espacios => 200 (normalizada)', r.status_code == 200, f'{r.status_code}')
            r = login(near(v2, 0.5), INT8)
            check('1:N int8 con usuario int8 => 200', r.status_code == 200 and r.data.get('user_id') == u2.id, f'{r.status_code} {r.data}')
            check('  rolling template recibe int8', calls[-1][2] == INT8, str(calls[-1][2:]))

            r = login(near(v1, 0.3), 'foo')
            check('versión inválida => 400 BIOMETRIC_MODEL_UNSUPPORTED',
                  r.status_code == 400 and r.data.get('code') == 'BIOMETRIC_MODEL_UNSUPPORTED' and r.data.get('error'), f'{r.status_code} {r.data}')
            r = login(near(v1, 0.3), 'x' * 40)
            check('versión > 32 chars => 400 BIOMETRIC_MODEL_UNSUPPORTED', r.status_code == 400 and r.data.get('code') == 'BIOMETRIC_MODEL_UNSUPPORTED')
            r = login([0.1] * 5, 'foo')
            check('versión inválida tiene prioridad sobre vector inválido', r.status_code == 400 and r.data.get('code') == 'BIOMETRIC_MODEL_UNSUPPORTED')
            r = login([0.1] * 5)
            check('vector inválido sin versión => 400 sin code (igual que antes)', r.status_code == 400 and 'code' not in r.data)

            print('\n=== 3. LOGIN 1:1 CON VERSIÓN DISTINTA (409) ===')
            r = login(near(v2, 0.3), FP32, user_id=u2.id)
            check('1:1 user_id: usuario int8, request fp32 => 409', r.status_code == 409, f'{r.status_code} {r.data}')
            d = r.data
            check('  payload 409 completo', d.get('code') == 'BIOMETRIC_REENROLL_REQUIRED' and d.get('reenroll_required') is True
                  and d.get('registered_model_version') == INT8 and d.get('requested_model_version') == FP32 and d.get('error'), str(d))
            check('  409 sin tokens ni datos sensibles', not ({'access', 'refresh', 'email', 'user_id'} & set(d.keys())), str(d.keys()))
            r = login(near(v2, 0.3), email=u2.email.upper())
            check('1:1 email: usuario int8, request sin versión (fp32) => 409', r.status_code == 409 and r.data.get('code') == 'BIOMETRIC_REENROLL_REQUIRED', f'{r.status_code}')
            r = login(near(v1, 0.3), INT8, user_id=u1.id)
            check('1:1: usuario fp32, request int8 => 409 (registered fp32 / requested int8)',
                  r.status_code == 409 and r.data.get('registered_model_version') == FP32 and r.data.get('requested_model_version') == INT8)
            r = login(near(v1, 0.3), user_id=u1.id)
            check('1:1 misma versión (sin campo) => 200', r.status_code == 200 and r.data.get('user_id') == u1.id, f'{r.status_code}')
            r = login(near(v2, 0.3), INT8, email=u2.email)
            check('1:1 misma versión int8 => 200', r.status_code == 200 and r.data.get('user_id') == u2.id, f'{r.status_code}')
            r = login(rand_vec('otro'), FP32, user_id=u1.id)
            check('1:1 misma versión pero cara distinta => 401 (no 409)', r.status_code == 401, f'{r.status_code}')

            print('\n=== 4. 1:N NO CRUZA VERSIONES ===')
            x = rand_vec('x')
            ux = mk_user('x-fp32', x, FP32)
            r = login(near(x, 0.25), INT8)
            check('vector de usuario fp32 buscado con versión int8 => 401 (no hay vecinos int8)', r.status_code == 401, f'{r.status_code} {r.data}')
            r = login(near(x, 0.25), FP32)
            check('el mismo vector con fp32 => 200', r.status_code == 200 and r.data.get('user_id') == ux.id, f'{r.status_code}')
            # Dos usuarios casi idénticos en versiones distintas: no deben generar "ambigüedad" entre sí
            y = rand_vec('y')
            uy_fp = mk_user('y-fp32', y, FP32)
            uy_i8 = mk_user('y-int8', near(y, 0.05), INT8)
            r = login(near(y, 0.15), FP32)
            check('vecino casi idéntico de OTRA versión no causa rechazo por ambigüedad', r.status_code == 200 and r.data.get('user_id') == uy_fp.id, f'{r.status_code} {r.data}')
            r = login(near(y, 0.15), INT8)
            check('  y a la inversa (int8) tampoco', r.status_code == 200 and r.data.get('user_id') == uy_i8.id, f'{r.status_code} {r.data}')
            # Control: dos fp32 casi idénticos SÍ son ambiguos (margen de Lowe sigue vigente)
            z = rand_vec('z')
            mk_user('z1', near(z, 0.05), FP32)
            mk_user('z2', near(z, 0.05), FP32)
            r = login(near(z, 0.15), FP32)
            check('control: dos usuarios de la MISMA versión muy cercanos => 401 ambiguo', r.status_code == 401, f'{r.status_code}')

        # ------------------------------------------------------------------
        print('\n=== 5. KYC / VerifyUser ===')
        dup_fp = rand_vec('kyc-fp')
        mk_user('kyc-owner-fp', dup_fp, FP32)
        dup_i8 = rand_vec('kyc-i8')
        mk_user('kyc-owner-i8', dup_i8, INT8)

        n = mk_user('n1', verified=False)
        fresh = rand_vec('fresh1')
        r = kyc(n, fresh)
        n.refresh_from_db()
        check('KYC sin embedding_model_version => 200 y guarda fp32 (igual que antes)',
              r.status_code == 200 and n.cedula_verified and n.biometric_model_version == FP32 and n.biometric_vector is not None, f'{r.status_code} {r.data}')

        n = mk_user('n2', verified=False)
        r = kyc(n, near(dup_fp, 0.1))
        n.refresh_from_db()
        check('KYC duplicado fp32 sin versión => 400 (igual que antes)',
              r.status_code == 400 and 'biometry' in r.data and not n.cedula_verified, f'{r.status_code} {r.data}')

        n = mk_user('n3', verified=False)
        r = kyc(n, near(dup_fp, 0.1), FP32)
        check('KYC duplicado fp32 con versión fp32 explícita => 400', r.status_code == 400 and 'biometry' in r.data, f'{r.status_code} {r.data}')

        n = mk_user('n4', verified=False)
        r = kyc(n, near(dup_fp, 0.1), INT8)
        n.refresh_from_db()
        check('KYC duplicado de usuario fp32 pero con versión int8 NO cruza versiones => 200 (limitación documentada)',
              r.status_code == 200 and n.biometric_model_version == INT8 and n.cedula_verified, f'{r.status_code} {r.data}')

        n = mk_user('n5', verified=False)
        r = kyc(n, near(dup_i8, 0.1), INT8)
        check('KYC duplicado de usuario int8 con versión int8 => 400', r.status_code == 400 and 'biometry' in r.data, f'{r.status_code} {r.data}')

        n = mk_user('n6', verified=False)
        r = kyc(n, near(dup_i8, 0.1), FP32)
        n.refresh_from_db()
        check('KYC duplicado de usuario int8 con versión fp32 NO cruza => 200', r.status_code == 200 and n.biometric_model_version == FP32, f'{r.status_code} {r.data}')

        n = mk_user('n7', verified=False)
        r = kyc(n, rand_vec('fresh7'), 'mobilefacenet-int8-v1 ')
        n.refresh_from_db()
        check('KYC con versión int8 (con espacio) => 200 y guarda int8', r.status_code == 200 and n.biometric_model_version == INT8, f'{r.status_code} {r.data}')

        n = mk_user('n8', verified=False)
        r = kyc(n, rand_vec('fresh8'), 'foo-v9')
        n.refresh_from_db()
        check('KYC con versión inválida => 400 BIOMETRIC_MODEL_UNSUPPORTED y no verifica',
              r.status_code == 400 and r.data.get('code') == 'BIOMETRIC_MODEL_UNSUPPORTED' and not n.cedula_verified, f'{r.status_code} {r.data}')

        n = mk_user('n9', verified=False)
        r = kyc(n, rand_vec('fresh9'), '')
        n.refresh_from_db()
        check('KYC con versión vacía => fp32', r.status_code == 200 and n.biometric_model_version == FP32, f'{r.status_code} {r.data}')

        # Serializador directo (otros llamadores): versión inválida => error de validación
        from api.serializers import VerifyUserSerializer
        n = mk_user('n10', verified=False)
        s = VerifyUserSerializer(data=kyc_payload(rand_vec('fresh10'), 'zzz'), context={'request': n})
        check('VerifyUserSerializer rechaza versión inválida', not s.is_valid() and 'embedding_model_version' in s.errors, str(s.errors))

        # ------------------------------------------------------------------
        print('\n=== 6. ROLLING TEMPLATE ===')
        base = rand_vec('roll')
        ur = mk_user('roll', base, FP32)
        sample = near(base, 0.5)
        dd = cos_dist(base, sample)
        check('precondición: muestra a distancia ∈ [0.06, 0.18]', 0.06 <= dd <= 0.18, f'{dd:.4f}')

        def stored(u):
            return list(User.objects.get(pk=u.pk).biometric_vector)

        before = stored(ur)
        update_rolling_template.run(ur.id, sample, INT8)
        check('versión distinta (int8 vs fp32) => NO mezcla', stored(ur) == before)
        update_rolling_template.run(ur.id, sample, 'foo')
        check('versión inválida => NO mezcla', stored(ur) == before)
        update_rolling_template.run(ur.id, sample, FP32)
        after = stored(ur)
        check('misma versión => mezcla (vector cambia, sigue unitario)',
              after != before and abs(math.sqrt(sum(a * a for a in after)) - 1.0) < 1e-5)
        ur2 = mk_user('roll2', base, FP32)
        update_rolling_template.run(ur2.id, sample)
        check('llamada retrocompatible (2 args) => mezcla con default fp32', stored(ur2) != list(base) and stored(ur2) != [])
        ur3 = mk_user('roll3', base, INT8)
        b3 = stored(ur3)
        update_rolling_template.run(ur3.id, sample)  # default fp32 vs usuario int8
        check('llamada retrocompatible a usuario int8 => NO mezcla', stored(ur3) == b3)
        update_rolling_template.run(ur3.id, sample, INT8)
        check('usuario int8 con versión int8 => mezcla', stored(ur3) != b3)
        far_sample = near(base, 1.5)
        b4 = stored(ur3)
        update_rolling_template.run(ur3.id, far_sample, INT8)
        check('misma versión pero distancia > perfect => NO mezcla (defensa en profundidad intacta)', stored(ur3) == b4)

        # ------------------------------------------------------------------
        print('\n=== 7. PERFIL (UserCacheAPI) y SUPRESIÓN ===')
        from django.core.cache import cache
        cache.delete(f"cartmaker:tenant:{u2.id}:profile")
        r = client(u2).get('/api/v1/cache/user')
        check('UserCacheAPI expone biometric_model_version (int8)', r.status_code == 200 and r.data.get('biometric_model_version') == INT8, f'{r.status_code} {r.data.get("biometric_model_version") if hasattr(r, "data") else ""}')
        nov = mk_user('novec', verified=False)
        cache.delete(f"cartmaker:tenant:{nov.id}:profile")
        r = client(nov).get('/api/v1/cache/user')
        check('UserCacheAPI: sin vector => biometric_model_version null', r.status_code == 200 and r.data.get('biometric_model_version') is None, str(r.data.get('biometric_model_version')))
        cache.set(f"cartmaker:tenant:{nov.id}:profile", {'preferred_category_ids': []}, 60)
        r = client(nov).get('/api/v1/cache/user')
        check('UserCacheAPI: caché antigua sin la clave se regenera', r.status_code == 200 and 'biometric_model_version' in r.data)

        r = client(u2).post('/api/v1/user/suppress-biometrics', {'confirm_suppression': True}, format='json')
        u2.refresh_from_db()
        check('suppress-biometrics => vector None y versión reseteada a fp32',
              r.status_code == 200 and u2.biometric_vector is None and u2.biometric_model_version == FP32 and not u2.cedula_verified, f'{r.status_code} {r.data}')

        raise Rollback()
except Rollback:
    print('\n(transacción revertida: BD sin cambios)')

print('\n=== RESUMEN ===')
fails = [r for r in RESULTS if not r[1]]
print(f'{len(RESULTS) - len(fails)}/{len(RESULTS)} OK')
for n_, _, e in fails:
    print('  FAIL:', n_, e)
