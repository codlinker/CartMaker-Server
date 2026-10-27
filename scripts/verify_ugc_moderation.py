"""
Verificación funcional de moderación UGC / bloqueo / +18.
Uso (BD LOCAL únicamente):  python manage.py shell < scripts/verify_ugc_moderation.py
Todo corre dentro de una transacción que SIEMPRE se revierte, con almacenamiento forzado a disco temporal
(nunca sube a S3) y con los proveedores externos de visión/IA mockeados.
"""
import io
import tempfile
import uuid
from unittest import mock

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection, transaction
from PIL import Image
from rest_framework.test import APIClient

from api.core import content_moderation as cm
from api.cos import storage_manager
from api.models import (
    CartMakerApiKey, Company, CompanyStore, CompanyVideoStory, ContentReport, InventoryItem, Product, User, UserBlock,
)

assert settings.DEBUG, 'Abortado: solo debe correrse con DEBUG=1 (entorno local)'
assert connection.settings_dict['HOST'] in ('127.0.0.1', 'localhost', ''), 'Abortado: la BD no es local'

if 'testserver' not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS.append('testserver')
storage_manager.storage_type = 'local'
settings.MEDIA_ROOT = tempfile.mkdtemp(prefix='cm_verify_')

RESULTS = []

# Los throttles (429) son ajenos a lo que se verifica aquí
from rest_framework.throttling import ScopedRateThrottle  # noqa: E402
ScopedRateThrottle.allow_request = lambda self, request, view: True


def check(name, cond, extra=''):
    RESULTS.append((name, bool(cond), extra))
    print(('PASS ' if cond else 'FAIL ') + name + (f'  -> {extra}' if extra and not cond else ''))


class Rollback(Exception):
    pass


def mk_user(tag):
    return User.objects.create_user(
        email=f"verif_{tag}_{uuid.uuid4().hex[:6]}@example.com", password='Pw12345!x',
        first_name='V', last_name=tag,
    )


def png_bytes():
    buf = io.BytesIO()
    Image.new('RGB', (64, 64), (200, 30, 30)).save(buf, format='PNG')
    return buf.getvalue()


def client(user=None):
    c = APIClient(HTTP_X_API_KEY=RAW_KEY)
    if user is not None:
        c.force_authenticate(user)
    return c


def vision(allowed, cat='SAFE'):
    return (
        mock.patch.object(cm, '_check_with_aws_rekognition', return_value=None),
        mock.patch.object(cm, '_check_with_openrouter_vision', return_value=(allowed, cat, 'mock')),
        mock.patch.object(cm, '_check_with_openai_moderation', return_value=None),
        mock.patch.object(cm, 'cache'),
    )


try:
    with transaction.atomic():
        key_obj = CartMakerApiKey(name='verify-tmp', scope='all')
        RAW_KEY = key_obj.generate_and_set_key()
        key_obj.save()

        # ------------------------------------------------------------------
        print('\n=== 1. FILTRO DE TEXTO ===')
        bad = {
            'pene': 'NUDITY_OR_SEXUAL', 'Vagina': 'NUDITY_OR_SEXUAL', 'p0rn0': 'NUDITY_OR_SEXUAL',
            'XXX': 'NUDITY_OR_SEXUAL', 'Consolador de silicona': 'ADULT_TOYS',
            'vibrador sexual': 'ADULT_TOYS', 'cigarrillos Marlboro': 'TOBACCO_OR_VAPE',
            'Vaper desechable': 'TOBACCO_OR_VAPE', 'nicotina': 'TOBACCO_OR_VAPE', 'hookah': 'TOBACCO_OR_VAPE',
            'Marihuana': 'DRUGS_OR_NARCOTICS', 'cocaína': 'DRUGS_OR_NARCOTICS', 'fentanilo': 'DRUGS_OR_NARCOTICS',
            'arma de fuego': 'WEAPONS_OR_VIOLENCE', 'municiones': 'WEAPONS_OR_VIOLENCE',
        }
        for txt, cat in bad.items():
            try:
                cm.moderate_text(txt)
                check(f'bloquea "{txt}"', False, 'no lanzó error')
            except cm.ContentModerationError as e:
                check(f'bloquea "{txt}" ({e.category})', e.category == cat, f'esperaba {cat}, obtuvo {e.category}')
        for txt in ['Empanada de pollo', 'Pantalón Slim Fit', 'Pipa de agua para plomería',
                    'Disfraz de pirata con espada de juguete', 'Cámara fotográfica Canon', 'Pistola de silicón caliente',
                    'Pistola de pintura', 'Cartera de cuero', 'Hamburguesa XXL', 'Camisa talla XXL',
                    'Cable HDMI 3 metros', 'Taza de café']:
            try:
                cm.moderate_text(txt)
                check(f'permite "{txt}"', True)
            except cm.ContentModerationError as e:
                check(f'permite "{txt}"', False, f'falso positivo {e.category}')
        print('   -- falsos positivos conocidos/aceptados por política (informativo):')
        for txt in ['Parche de nicotina', 'Perfume con notas de tabaco', 'Chicle de nicotina', 'Munición de airsoft']:
            try:
                cm.moderate_text(txt); print(f'      permite "{txt}"')
            except cm.ContentModerationError as e:
                print(f'      BLOQUEA "{txt}" ({e.category})')
        try:
            cm.moderate_text_fields({'a': 'ok', 'b': {'x': ['tabaco']}})
            check('moderate_text_fields detecta en JSON anidado', False)
        except cm.ContentModerationError:
            check('moderate_text_fields detecta en JSON anidado', True)

        # ------------------------------------------------------------------
        print('\n=== 2. MODERACIÓN DE IMAGEN (proveedores mockeados) ===')
        p = vision(False, 'ADULT_TOYS')
        with p[0], p[1], p[2], p[3] as mcache:
            mcache.get.return_value = None
            try:
                cm.moderate_image_bytes(b'abc-fake', folder_path='product_pictures/x', file_name='a.jpg')
                check('imagen prohibida es bloqueada', False)
            except cm.ContentModerationError as e:
                check('imagen prohibida es bloqueada', e.category == 'ADULT_TOYS')
            for folder in ('identity_verifications', 'identity_verifications/', 'companies/kyb/rif',
                           'companies/kyb/mercantil', 'subscriptions/atlas_plus'):
                try:
                    cm.moderate_image_bytes(b'abc-fake', folder_path=folder, file_name='a.jpg')
                    check(f'carpeta privada "{folder}" exenta (no sale a IA externa)', True)
                except cm.ContentModerationError:
                    check(f'carpeta privada "{folder}" exenta (no sale a IA externa)', False)
            for folder in ('chat_media', 'support_media'):
                try:
                    cm.moderate_image_bytes(b'abc-fake', folder_path=folder, file_name='a.jpg')
                    print(f'   INFO: "{folder}" NO está exenta: sus imágenes salen a Gemini/OpenRouter')
                except cm.ContentModerationError:
                    print(f'   INFO: "{folder}" NO está exenta: sus imágenes salen a Gemini/OpenRouter')
        with mock.patch.object(cm, '_check_with_aws_rekognition', return_value=None), \
             mock.patch.object(cm, '_check_with_openrouter_vision', return_value=None), \
             mock.patch.object(cm, '_check_with_openai_moderation', return_value=None):
            try:
                cm.moderate_image_bytes(b'abc-fake2', folder_path='product_pictures/x', file_name='a.jpg')
                check('fail-open si ningún proveedor responde', True)
            except Exception:
                check('fail-open si ningún proveedor responde', False)

        # ------------------------------------------------------------------
        print('\n=== 3. REGISTRO +18 / TÉRMINOS ===')
        c = client()
        with mock.patch('api.serializers.send_email_otp'):
            def reg(fmt='json', **kw):
                body = {'email': f"reg_{uuid.uuid4().hex[:8]}@example.com", 'password': 'Pw12345!x',
                        'first_name': 'A', 'last_name': 'B', 'gender': 0}
                body.update(kw)
                return c.post('/api/v1/register', body, format=fmt)

            r = reg()
            check('registro sin campos nuevos (retrocompat) = 201', r.status_code == 201, r.content[:200])
            r = reg(is_adult=False)
            check('is_adult=false = 400', r.status_code == 400, f'{r.status_code} {r.content[:200]}')
            check('  código UNDERAGE_RESTRICTED', b'UNDERAGE_RESTRICTED' in r.content, r.content[:300])
            _j = r.json()
            check('  formato plano {success,code,error,detail} (no listas)', _j.get('success') is False and _j.get('code') == 'UNDERAGE_RESTRICTED' and isinstance(_j.get('error'), str) and _j.get('detail'), _j)
            r = reg(accepted_terms=False)
            check('accepted_terms=false = 400', r.status_code == 400, f'{r.status_code} {r.content[:200]}')
            check('  código TERMS_NOT_ACCEPTED', b'TERMS_NOT_ACCEPTED' in r.content, r.content[:300])
            r = reg(birth_date='2015-05-05')
            check('birth_date menor de 18 = 400', r.status_code == 400, f'{r.status_code} {r.content[:200]}')
            r = reg(birth_date='1990-05-05', is_adult=True, accepted_terms=True)
            check('mayor de edad + términos = 201', r.status_code == 201, f'{r.status_code} {r.content[:200]}')
            if r.status_code == 201:
                u = User.objects.get(email=r.json().get('email') or User.objects.order_by('-creation').first().email)
                check('  birth_date guardada en el usuario', str(u.birth_date) == '1990-05-05', u.birth_date)
            r = reg(fmt='multipart', is_adult='false')
            check('is_adult="false" en multipart = 400', r.status_code == 400, f'{r.status_code} {r.content[:200]}')
            r = reg(birth_date='05/05/1990')
            check('birth_date formato DD/MM/YYYY = 201', r.status_code == 201, f'{r.status_code} {r.content[:200]}')
        r = c.post('/api/v1/google/regist', {'token_id': 'x', 'is_adult': False}, format='json')
        check('google/regist is_adult=false = 400 UNDERAGE', r.status_code == 400 and b'UNDERAGE' in r.content, r.content[:200])
        r = c.post('/api/v1/google/regist', {'token_id': 'x', 'accepted_terms': False}, format='json')
        check('google/regist accepted_terms=false = 400 TERMS', r.status_code == 400 and b'TERMS_NOT_ACCEPTED' in r.content, r.content[:200])

        # ------------------------------------------------------------------
        print('\n=== 4. FIXTURES (comercio, sucursal, producto, inventario) ===')
        owner = mk_user('owner')
        company = Company.objects.create(owner=owner, name=f'Verif Co {uuid.uuid4().hex[:5]}')
        store = CompanyStore.objects.create(company=company, name='Sucursal V', work_hours='08:00-17:00',
                                            work_days=[0, 1, 2, 3, 4], store_type=0)
        product = Product.objects.create(company=company, name='Producto verif', price=5, description='ok')
        item = InventoryItem.objects.create(product=product, store=store, stock=10)
        print('   fixtures creados')

        reporters = [mk_user(f'r{i}') for i in range(3)]
        cl = client(reporters[0])

        payload = {
            'target_type': 'product', 'target_id': str(item.id), 'target_title': product.name,
            'reason_code': 'sexual_or_nudity', 'reason_label': 'Contenido sexual o desnudez',
            'details': 'prueba', 'company_id': str(company.id), 'company_name': company.name,
            'block_merchant': True,
        }
        r = cl.post('/api/v1/ugc/report/', payload, format='json')
        check('POST /ugc/report/ payload Flutter = 201', r.status_code == 201, f'{r.status_code} {r.content[:300]}')
        if r.status_code == 201:
            rep = ContentReport.objects.filter(reporter=reporters[0], target_id=str(item.id)).first()
            check('  reason mapeado a NUDITY_OR_SEXUAL', rep and rep.reason == 'NUDITY_OR_SEXUAL', rep and rep.reason)
            check('  UserBlock creado (block_merchant)', UserBlock.objects.filter(blocker=reporters[0], blocked_company=company).exists())
        r = cl.post('/api/v1/ugc/report', payload, format='json')
        check('reporte duplicado sin slash final = 200 (idempotente)', r.status_code == 200, f'{r.status_code} {r.content[:200]}')
        check('  sigue habiendo 1 sola fila', ContentReport.objects.filter(reporter=reporters[0], target_id=str(item.id)).count() == 1)

        r = cl.post('/api/v1/ugc/report/', {'target_type': 'story', 'reason_code': 'x'}, format='json')
        check('sin target_id = 400', r.status_code == 400, f'{r.status_code}')
        for body in (
            {'target_type': 'product', 'target_id': 'no-es-uuid', 'reason_code': 'scam_or_fake'},
            {'target_type': 'product', 'target_id': 'no-es-uuid', 'reason_code': 'scam_or_fake', 'block_merchant': True},
            {'target_type': 'comment', 'target_id': '999999', 'reason_code': 'harassment_or_hate', 'block_merchant': True},
            {'target_type': 'story', 'target_id': 'zzz', 'reason_code': 'illegal_or_weapons', 'block_merchant': True},
            {'target_type': 'video', 'target_id': str(uuid.uuid4()), 'reason_code': 'tobacco_or_vapes'},
        ):
            sp = transaction.savepoint()
            r = cl.post('/api/v1/ugc/report/', body, format='json')
            check(f'payload raro {body["target_type"]}/{str(body["target_id"])[:8]} no revienta (<500)', r.status_code < 500, f'{r.status_code} {r.content[:200]}')
            try:
                transaction.savepoint_rollback(sp)
            except Exception:
                pass
        r = APIClient(HTTP_X_API_KEY=RAW_KEY).post('/api/v1/ugc/report/', payload, format='json')
        check('sin JWT = 401', r.status_code in (401, 403), f'{r.status_code}')
        r = APIClient().post('/api/v1/ugc/report/', payload, format='json')
        check('sin API key = 401 (gatekeeper)', r.status_code == 401, f'{r.status_code}')

        # Cuarentena automática con 3 reportes graves distintos
        for u in reporters[1:]:
            client(u).post('/api/v1/ugc/report/', {**payload, 'block_merchant': False, 'reason_code': 'tobacco_or_vapes'}, format='json')
        item.refresh_from_db()
        check('3 reportes graves distintos => item pausado (cuarentena)', item.paused is True)
        check('  reportes pasan a QUARANTINED', ContentReport.objects.filter(target_id=str(item.id), status='QUARANTINED').exists())

        # Bloqueo directo
        r = client(owner).post('/api/v1/ugc/block/', {'company_id': str(company.id)}, format='json')
        check('dueño no puede bloquear su propio comercio = 400', r.status_code == 400, f'{r.status_code} {r.content[:200]}')
        c3 = client(reporters[1])
        r = c3.post('/api/v1/ugc/block/', {'company_id': str(company.id), 'reason': 'x'}, format='json')
        check('POST /ugc/block/ = 201', r.status_code == 201, f'{r.status_code} {r.content[:200]}')
        r = c3.get('/api/v1/ugc/blocked/')
        check('GET /ugc/blocked/ lista el comercio', r.status_code == 200 and str(company.id) in r.json().get('blocked_company_ids', []), r.content[:200])
        r = c3.post('/api/v1/ugc/block/', {'target_type': 'user', 'user_id': str(reporters[1].id)}, format='json')
        check('no puedes bloquearte a ti mismo = 400', r.status_code == 400, f'{r.status_code}')
        r = c3.post('/api/v1/ugc/block/', {'target_type': 'user', 'user_id': str(owner.id)}, format='json')
        check('bloquear usuario = 201', r.status_code == 201, f'{r.status_code} {r.content[:200]}')
        r = c3.post('/api/v1/ugc/unblock/', {'target_id': str(company.id)}, format='json')
        check('POST /ugc/unblock/ = 200', r.status_code == 200 and r.json().get('unblocked') is True, r.content[:200])
        r = c3.delete('/api/v1/ugc/block/', {'target_id': str(owner.id)}, format='json')
        check('DELETE /ugc/block/ = 200', r.status_code == 200, f'{r.status_code} {r.content[:200]}')
        r = c3.post('/api/v1/ugc/block/', {}, format='json')
        check('block sin id = 400', r.status_code == 400, f'{r.status_code}')
        r = c3.post('/api/v1/ugc/block/', {'company_id': str(uuid.uuid4())}, format='json')
        check('block de comercio inexistente = 404', r.status_code == 404, f'{r.status_code}')
        r = c3.post('/api/v1/ugc/block/', {'company_id': 'basura'}, format='json')
        check('block con id basura no revienta (<500)', r.status_code < 500, f'{r.status_code} {r.content[:200]}')
        r = c3.post('/api/v1/ugc/block/', {'company_id': str(company.id)}, format='json')
        UserBlock.invalidate_user_cache(reporters[1].id)
        check('bloqueados vía modelo devuelve el comercio', str(company.id) in UserBlock.get_blocked_company_ids(reporters[1].id))

        # ------------------------------------------------------------------
        print('\n=== 5. COMENTARIOS / Q&A ===')
        item.paused = False
        item.save(update_fields=['paused'])
        buyer = client(mk_user('buyer'))
        with mock.patch('api.views.social_and_stories_views.firebase_admin.NotificationManager.notify_new_question'):
            r = buyer.post('/api/v1/universal-conversation/add_comment/', {'target_type': 'product', 'target_id': str(item.id),
                                                                           'question_text': 'Venden cigarrillos aquí?'}, format='json')
            check('comentario con "cigarrillos" = 400 PROHIBITED_CONTENT', r.status_code == 400 and b'PROHIBITED_CONTENT' in r.content, f'{r.status_code} {r.content[:200]}')
            r = buyer.post('/api/v1/universal-conversation/add_comment/', {'target_type': 'product', 'target_id': str(item.id),
                                                                           'question_text': 'Tienen en talla M?'}, format='json')
            check('comentario normal = 201', r.status_code == 201, f'{r.status_code} {r.content[:200]}')
            qid = (r.json().get('data') or {}).get('id') if r.status_code == 201 else None
        if qid:
            with mock.patch('api.views.social_and_stories_views.firebase_admin.NotificationManager.notify_new_answer'):
                r = client(owner).post('/api/v1/universal-conversation/answer_comment/', {'question_id': qid, 'answer_text': 'Vendemos vapers también'}, format='json')
                check('respuesta con "vapers" = 400 PROHIBITED_CONTENT', r.status_code == 400 and b'PROHIBITED_CONTENT' in r.content, f'{r.status_code} {r.content[:200]}')
                r = client(owner).post('/api/v1/universal-conversation/answer_comment/', {'question_id': qid, 'answer_text': 'Sí, hay talla M'}, format='json')
                check('respuesta normal = 200', r.status_code == 200, f'{r.status_code} {r.content[:200]}')

        # ------------------------------------------------------------------
        print('\n=== 6. VIDEO STORY ===')
        oc = client(owner)
        with mock.patch('api.views.social_and_stories_views.optimize_and_transcode_video_story'):
            vid = SimpleUploadedFile('v.mp4', b'\x00' * 2048, content_type='video/mp4')
            th = SimpleUploadedFile('t.png', png_bytes(), content_type='image/png')
            r = oc.post('/api/v1/story-video/', {'title': 'Vendo vapers baratos', 'description': 'x', 'duration_seconds': 10,
                                                 'video_file': vid, 'thumbnail': th}, format='multipart')
            check('video con título "vapers" = 400 PROHIBITED_CONTENT (no 500)', r.status_code == 400 and b'PROHIBITED_CONTENT' in r.content, f'{r.status_code} {r.content[:250]}')

            p = vision(False, 'NUDITY_OR_SEXUAL')
            with p[0], p[1], p[2], p[3] as mcache:
                mcache.get.return_value = None
                vid = SimpleUploadedFile('v.mp4', b'\x00' * 2048, content_type='video/mp4')
                th = SimpleUploadedFile('t.png', png_bytes(), content_type='image/png')
                before = CompanyVideoStory.objects.count()
                r = oc.post('/api/v1/story-video/', {'title': 'Pizza', 'description': 'rica', 'duration_seconds': 10,
                                                     'video_file': vid, 'thumbnail': th}, format='multipart')
                check('video con miniatura prohibida = 400 y no se crea', r.status_code == 400 and CompanyVideoStory.objects.count() == before, f'{r.status_code} {r.content[:250]}')
            p = vision(True)
            with p[0], p[1], p[2], p[3] as mcache:
                mcache.get.return_value = None
                vid = SimpleUploadedFile('v.mp4', b'\x00' * 2048, content_type='video/mp4')
                th = SimpleUploadedFile('t.png', png_bytes(), content_type='image/png')
                r = oc.post('/api/v1/story-video/', {'title': 'Pizza', 'description': 'rica', 'duration_seconds': 10,
                                                     'video_file': vid, 'thumbnail': th}, format='multipart')
                check('video normal = 201', r.status_code == 201, f'{r.status_code} {r.content[:250]}')
                sid = (r.json().get('data') or {}).get('id') if r.status_code == 201 else None
            if sid:
                r = oc.patch(f'/api/v1/story-video/{sid}/', {'title': 'cigarrillos'}, format='multipart')
                check('editar video con título "cigarrillos" = 400', r.status_code == 400 and b'PROHIBITED_CONTENT' in r.content, f'{r.status_code} {r.content[:250]}')
                r = oc.patch(f'/api/v1/story-video/{sid}/', {'title': 'Pizza grande'}, format='multipart')
                check('editar video título normal = 200', r.status_code == 200, f'{r.status_code} {r.content[:250]}')
                # video de un comercio bloqueado no aparece en list para el que bloqueó
                blk = client(reporters[2])
                blk.post('/api/v1/ugc/block/', {'company_id': str(company.id)}, format='json')
                r = blk.get('/api/v1/story-video/')
                body = r.json()
                rows = body.get('results', body) if isinstance(body, dict) else body
                check('video de comercio bloqueado NO aparece en story-video list', r.status_code == 200 and all(str(x.get('id')) != str(sid) for x in rows), f'{r.status_code} {str(rows)[:200]}')

        # ------------------------------------------------------------------
        print('\n=== 7. AVATAR y PRODUCTO con imagen/texto prohibido ===')
        p = vision(False, 'NUDITY_OR_SEXUAL')
        with p[0], p[1], p[2], p[3] as mcache:
            mcache.get.return_value = None
            old_pic = owner.profile_picture
            f = SimpleUploadedFile('a.png', png_bytes(), content_type='image/png')
            r = oc.post('/api/v1/user/upload-avatar/', {'photo': f}, format='multipart')
            owner.refresh_from_db()
            check('avatar prohibido = 400 PROHIBITED_CONTENT', r.status_code == 400 and b'PROHIBITED_CONTENT' in r.content, f'{r.status_code} {r.content[:250]}')
            check('  foto anterior intacta', owner.profile_picture == old_pic)
        r = oc.patch(f'/api/v1/products/{product.id}/', {'name': 'Consolador XL'}, format='multipart')
        check('PATCH producto con nombre "Consolador" = 400 PROHIBITED_CONTENT', r.status_code == 400 and b'PROHIBITED_CONTENT' in r.content, f'{r.status_code} {r.content[:250]}')
        r = oc.patch(f'/api/v1/products/{product.id}/', {'name': 'Zapato rojo'}, format='multipart')
        check('PATCH producto nombre normal no revienta (<500)', r.status_code < 500, f'{r.status_code} {r.content[:250]}')

        # ------------------------------------------------------------------
        print('\n=== 8. PÁGINAS PÚBLICAS (Google Play) ===')
        anon = APIClient()
        for path in ('/privacidad/', '/privacy/', '/eliminar-cuenta/', '/delete-account/'):
            r = anon.get(path)
            check(f'GET {path} público = 200', r.status_code == 200, r.status_code)
        r = anon.get('/privacidad/')
        check('  /privacidad/ incluye sección UGC +18', b'moderacion-ugc' in r.content)

        # ------------------------------------------------------------------
        print('\n=== 9. FALSOS POSITIVOS DE TEXTO (lista de excepciones) ===')
        for txt in ['Parche de nicotina 21mg', 'Chicle de nicotina', 'Perfume con notas de tabaco',
                    'Café con aroma a tabaco', 'Pistola de agua', 'Pistola de silicón', 'Munición de airsoft']:
            try:
                cm.moderate_text(txt)
                check(f'permite "{txt}"', True)
            except cm.ContentModerationError as e:
                check(f'permite "{txt}"', False, e.category)
        for txt in ['Cigarrillos aroma a tabaco', 'Vendo nicotina', 'tabaco de fumar', 'Vaper sabor a tabaco',
                    'pistola calibre 9mm', 'Consolador']:
            try:
                cm.moderate_text(txt)
                check(f'sigue bloqueando "{txt}"', False)
            except cm.ContentModerationError:
                check(f'sigue bloqueando "{txt}"', True)

        # ------------------------------------------------------------------
        print('\n=== 10. CHAT: moderación del texto ===')
        from chat.views import ChatWebhookViewSet
        from chat.models import ChatMessage
        from types import SimpleNamespace
        from rest_framework.test import APIRequestFactory
        from api.models import Order
        fake_company = SimpleNamespace(owner_id='owner-1')
        fake_order = SimpleNamespace(id=1, client_id='cli-1', store=SimpleNamespace(company=fake_company), status=0)
        qs_mock = mock.MagicMock()
        qs_mock.get.return_value = fake_order
        webhook = ChatWebhookViewSet.as_view({'post': 'process_message'}, permission_classes=[])
        factory = APIRequestFactory()
        with mock.patch.object(Order.objects, 'select_related', return_value=qs_mock):
            req = factory.post('/chat/webhook/process_message/', {'order_id': 1, 'sender_id': 'cli-1', 'text': 'Véndeme cigarrillos y vapers', 'message_type': 'text'}, format='json')
            resp = webhook(req)
            check('chat: texto prohibido = 400 PROHIBITED_CONTENT con "error"', resp.status_code == 400 and resp.data.get('code') == 'PROHIBITED_CONTENT' and resp.data.get('error'), f'{resp.status_code} {resp.data}')
            fake_msg = mock.MagicMock()
            fake_msg.get_json.return_value = {'id': 1}
            with mock.patch.object(ChatMessage.objects, 'create', return_value=fake_msg), \
                 mock.patch('chat.views.NotificationManager.notify_new_chat_message'):
                req = factory.post('/chat/webhook/process_message/', {'order_id': 1, 'sender_id': 'cli-1', 'text': 'Hola, ¿a qué hora cierran?', 'message_type': 'text', 'recipient_connected': True}, format='json')
                resp = webhook(req)
                check('chat: texto normal = 200', resp.status_code == 200, f'{resp.status_code} {resp.data}')

        # ------------------------------------------------------------------
        print('\n=== 11. PRE-MODERACIÓN CONCURRENTE ===')
        import time
        calls = []

        def slow_ok(_b):
            time.sleep(0.6); calls.append(1)
            return (True, 'SAFE', 'mock')

        def png_n(n):
            buf = io.BytesIO()
            Image.new('RGB', (80, 80), (n * 30 % 255, 10 * n % 255, 99)).save(buf, format='PNG')
            return buf.getvalue()

        files = [SimpleUploadedFile(f'f{i}.png', png_n(i + 1), content_type='image/png') for i in range(5)]
        with mock.patch.object(cm, '_check_with_aws_rekognition', return_value=None), \
             mock.patch.object(cm, '_check_with_openrouter_vision', side_effect=slow_ok), \
             mock.patch.object(cm, '_check_with_openai_moderation', return_value=None), \
             mock.patch.object(cm, 'cache') as mc:
            mc.get.return_value = None
            t0 = time.time()
            cm.premoderate_uploaded_images(files)
            elapsed = time.time() - t0
        check(f'5 imágenes x 0.6s en paralelo tardan <2.0s (real {elapsed:.2f}s)', elapsed < 2.0 and len(calls) == 5, f'{elapsed:.2f}s calls={len(calls)}')
        check('  los archivos quedan reutilizables (seek(0))', files[0].read(4) == png_n(1)[:4])

        verdicts = iter([(True, 'SAFE', 'm'), (False, 'ADULT_TOYS', 'm'), (True, 'SAFE', 'm')])
        files = [SimpleUploadedFile(f'g{i}.png', png_n(i + 7), content_type='image/png') for i in range(3)]
        with mock.patch.object(cm, '_check_with_aws_rekognition', return_value=None), \
             mock.patch.object(cm, '_check_with_openrouter_vision', side_effect=lambda b: next(verdicts)), \
             mock.patch.object(cm, '_check_with_openai_moderation', return_value=None), \
             mock.patch.object(cm, 'cache') as mc:
            mc.get.return_value = None
            try:
                cm.premoderate_uploaded_images(files)
                check('una imagen prohibida entre varias => ContentModerationError', False)
            except cm.ContentModerationError as e:
                check('una imagen prohibida entre varias => ContentModerationError', e.category == 'ADULT_TOYS')

        # ------------------------------------------------------------------
        print('\n=== 12. LIMPIEZA DE ARCHIVOS HUÉRFANOS ===')
        from api.cos import begin_request_file_tracking, end_request_file_tracking
        import os as _os
        p = vision(True)
        with p[0], p[1], p[2], p[3] as mc:
            mc.get.return_value = None
            tok = begin_request_file_tracking()
            try:
                f1 = SimpleUploadedFile('o1.png', png_n(3), content_type='image/png')
                f2 = SimpleUploadedFile('o2.png', png_n(4), content_type='image/png')
                path1 = storage_manager.save_file(f1, 'product_pictures/verif', 'o1.png')
                path2 = storage_manager.save_file(f2, 'product_pictures/verif', 'o2.png')
                exist_before = all(_os.path.isfile(_os.path.join(settings.MEDIA_ROOT, x)) for x in (path1, path2))
                resp = cm.ContentModerationError(category='ADULT_TOYS').to_response()
                exist_after = any(_os.path.isfile(_os.path.join(settings.MEDIA_ROOT, x)) for x in (path1, path2))
            finally:
                end_request_file_tracking(tok)
        check('al rechazar, los archivos subidos antes en la misma petición se borran', exist_before and not exist_after and resp.status_code == 400, f'{exist_before} {exist_after}')
        f3 = SimpleUploadedFile('o3.png', png_n(5), content_type='image/png')
        with p[0], p[1], p[2], p[3] as mc:
            mc.get.return_value = None
            path3 = storage_manager.save_file(f3, 'product_pictures/verif', 'o3.png')
        cm.ContentModerationError(category='ADULT_TOYS').to_response()
        check('sin rastreo activo NO se borra nada (seguridad)', _os.path.isfile(_os.path.join(settings.MEDIA_ROOT, path3)))

        # Rollback real vía API: nuevo producto con foto prohibida detectada tarde (cache.get=None) no deja huérfanos
        # (cubierto por la prueba unitaria anterior; el middleware se verifica a continuación)
        from django.test import RequestFactory
        from cartmaker_admin.request_files_middleware import RequestFileTrackingMiddleware
        seen = {}

        def _view(request):
            from api.cos import _REQUEST_SAVED_FILES
            seen['active'] = _REQUEST_SAVED_FILES.get() is not None
            return None
        RequestFileTrackingMiddleware(_view)(RequestFactory().get('/'))
        from api.cos import _REQUEST_SAVED_FILES
        check('middleware activa el rastreo durante la petición y lo libera al final', seen.get('active') is True and _REQUEST_SAVED_FILES.get() is None)

        # ------------------------------------------------------------------
        print('\n=== 13. RE-VERIFICACIÓN DIFERIDA (fail-open controlado) ===')
        from api import tasks as T
        sched = []
        with mock.patch.object(cm, 'moderation_providers_configured', return_value=True), \
             mock.patch.object(T.recheck_unverified_image, 'apply_async', side_effect=lambda **kw: sched.append(kw)), \
             mock.patch.object(cm, '_check_with_aws_rekognition', return_value=None), \
             mock.patch.object(cm, '_check_with_openrouter_vision', return_value=None), \
             mock.patch.object(cm, '_check_with_openai_moderation', return_value=None), \
             mock.patch.object(cm, 'cache') as mc:
            mc.get.return_value = None
            cm.moderate_image_bytes(b'xx-unverified', folder_path='product_pictures/z', file_name='z.jpg')
        check('sin veredicto => se agenda re-verificación con la ruta final', len(sched) == 1 and sched[0]['args'] == ['product_pictures/z/z.jpg'], sched)
        sched.clear()
        with mock.patch.object(cm, 'moderation_providers_configured', return_value=False), \
             mock.patch.object(T.recheck_unverified_image, 'apply_async', side_effect=lambda **kw: sched.append(kw)), \
             mock.patch.object(cm, '_check_with_aws_rekognition', return_value=None), \
             mock.patch.object(cm, '_check_with_openrouter_vision', return_value=None), \
             mock.patch.object(cm, '_check_with_openai_moderation', return_value=None), \
             mock.patch.object(cm, 'cache') as mc:
            mc.get.return_value = None
            cm.moderate_image_bytes(b'xx-unverified2', folder_path='product_pictures/z', file_name='z2.jpg')
        check('sin proveedores configurados NO se agenda (evita reintentos inútiles)', len(sched) == 0)

        # La tarea: imagen luego detectada como prohibida => se borra, se purga de producto y se registra
        owner_x = mk_user('own2')
        co_x = Company.objects.create(owner=owner_x, name=f'Recheck Co {uuid.uuid4().hex[:5]}')
        pr_x = Product.objects.create(company=co_x, name='PX', price=2, description='d')
        f4 = SimpleUploadedFile('bad.png', png_n(6), content_type='image/png')
        p = vision(True)
        with p[0], p[1], p[2], p[3] as mc:
            mc.get.return_value = None
            bad_path = storage_manager.save_file(f4, f'product_pictures/{pr_x.id}', 'bad.png')
        pr_x.images = [bad_path, 'product_pictures/otra/ok.jpg']
        pr_x.save(update_fields=['images'])
        with mock.patch.object(cm, '_check_with_aws_rekognition', return_value=None), \
             mock.patch.object(cm, '_check_with_openrouter_vision', return_value=(False, 'NUDITY_OR_SEXUAL', 'm')), \
             mock.patch.object(cm, '_check_with_openai_moderation', return_value=None):
            T.recheck_unverified_image.run(bad_path)
        pr_x.refresh_from_db()
        check('re-verificación: archivo prohibido borrado del storage', not _os.path.isfile(_os.path.join(settings.MEDIA_ROOT, bad_path)))
        check('  referencia purgada del producto (la otra foto se conserva)', pr_x.images == ['product_pictures/otra/ok.jpg'], pr_x.images)
        check('  reporte del sistema registrado (sin denunciante)', ContentReport.objects.filter(reporter__isnull=True, target_type='image', target_id=bad_path).exists())

        # ------------------------------------------------------------------
        print('\n=== 14. MODERACIÓN DE VIDEO (frames con ffmpeg shim) ===')
        import shutil, stat
        shim_dir = tempfile.mkdtemp(prefix='cm_shim_')
        sample_jpg = _os.path.join(shim_dir, 'sample.jpg')
        Image.new('RGB', (64, 64), (10, 200, 10)).save(sample_jpg, format='JPEG')
        with open(_os.path.join(shim_dir, 'ffprobe'), 'w') as fh:
            fh.write('#!/bin/sh\necho 12.0\n')
        with open(_os.path.join(shim_dir, 'ffmpeg'), 'w') as fh:
            fh.write(f'#!/bin/sh\nfor last; do :; done\ncp {sample_jpg} "$last"\n')
        for n in ('ffprobe', 'ffmpeg'):
            _os.chmod(_os.path.join(shim_dir, n), 0o755)
        old_path = _os.environ['PATH']
        _os.environ['PATH'] = shim_dir + _os.pathsep + old_path
        try:
            frames = cm.extract_video_frames('/tmp/no-importa.mp4')
            check('extract_video_frames devuelve 3 fotogramas (comando bien formado)', len(frames) == 3, len(frames))
        finally:
            _os.environ['PATH'] = old_path
        from django.utils import timezone as _tz
        from datetime import timedelta as _td
        _os.environ['PATH'] = shim_dir + _os.pathsep + old_path
        try:
            vpath = storage_manager.save_file(SimpleUploadedFile('vid.mp4', b'\x00' * 4096, content_type='video/mp4'), 'stories/videos', 'vid_verif.mp4')
            tpath = storage_manager.save_file(SimpleUploadedFile('th.png', png_n(9), content_type='image/png'), 'stories/thumbnails', 'th_verif.png')
            st_x = CompanyVideoStory.objects.create(company=co_x, title='t', description='d', video_file=vpath, thumbnail=tpath,
                                                    expires_at=_tz.now() + _td(hours=5), duration_seconds=5)
            p = vision(True)
            with p[0], p[1], p[2], p[3] as mc:
                mc.get.return_value = None
                ok = T._moderate_story_video_or_takedown(st_x)
            st_x.refresh_from_db()
            check('video limpio => se conserva', ok is True and st_x.video_file == vpath)

            p = vision(False, 'WEAPONS_OR_VIOLENCE')
            with p[0], p[1], p[2], p[3] as mc:
                mc.get.return_value = None
                ok = T._moderate_story_video_or_takedown(st_x)
            st_x.refresh_from_db()
            check('video con fotogramas prohibidos => dado de baja', ok is False and st_x.video_file is None and st_x.expires_at <= _tz.now(), f'{ok} {st_x.video_file}')
            check('  archivo físico eliminado', not _os.path.isfile(_os.path.join(settings.MEDIA_ROOT, vpath)))
            check('  reporte del sistema registrado', ContentReport.objects.filter(reporter__isnull=True, target_type='video', target_id=str(st_x.id)).exists())

            # Video de presentación del comercio
            vpath2 = storage_manager.save_file(SimpleUploadedFile('pv.mp4', b'\x00' * 4096, content_type='video/mp4'), 'company_presentation_videos', 'pv_verif.mp4')
            co_x.presentation_video_url = vpath2
            co_x.save(update_fields=['presentation_video_url'])
            p = vision(False, 'NUDITY_OR_SEXUAL')
            with p[0], p[1], p[2], p[3] as mc:
                mc.get.return_value = None
                T.moderate_company_presentation_video.run(co_x.id)
            co_x.refresh_from_db()
            check('video de presentación prohibido => eliminado del perfil', co_x.presentation_video_url is None and not _os.path.isfile(_os.path.join(settings.MEDIA_ROOT, vpath2)))
        finally:
            _os.environ['PATH'] = old_path
        raise Rollback()
except Rollback:
    print('\n(transacción revertida: BD sin cambios)')

print('\n=== RESUMEN ===')
fails = [r for r in RESULTS if not r[1]]
print(f'{len(RESULTS) - len(fails)}/{len(RESULTS)} OK')
for n, _, e in fails:
    print('  FAIL:', n, e)
