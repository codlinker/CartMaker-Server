"""
Verificación funcional del paquete de rendimiento del backend (informe del frontend):
variantes de imagen + Cache-Control, órdenes (ETag/304, updated_after, paginación, señales), gzip/ETag en cache/*,
push/socket de órdenes, preguntas y denuncias UGC, y video ligero de feed + miniatura garantizada.

Uso (BD LOCAL únicamente):  python manage.py shell < scripts/verify_perf_backend.py
Todo corre dentro de una transacción que SIEMPRE se revierte, con almacenamiento en disco temporal (nunca S3),
Celery/FCM/Node/ffmpeg simulados.
"""
import io
import os
import stat
import sys
import tempfile
import types
import uuid
from datetime import timezone as dt_tz
from unittest import mock
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cartmaker_admin.settings")
import django
from django.apps import apps as django_apps
if not django_apps.ready:
    django.setup()

from django.conf import settings
from django.core.cache.backends.locmem import LocMemCache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection, transaction
from django.db.models.signals import post_save
from django.test import TestCase
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from api import cos as cos_module
from api.core import image_variants as iv
from api.core.firebase_admin import NotificationManager
from api.cos import storage_manager
from api.models import (
    CartMakerApiKey, Company, CompanyStore, CompanyVideoStory, ContentReport, DeliveryAssignment, Notification,
    NotificationCategory, Order, OrderStatus, Product, SupportTicket, User, WithdrawalType,
)

assert settings.DEBUG, 'Abortado: solo debe correrse con DEBUG=1 (entorno local)'
assert connection.settings_dict['HOST'] in ('127.0.0.1', 'localhost', ''), 'Abortado: la BD no es local'

if 'testserver' not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS.append('testserver')
storage_manager.storage_type = 'local'
settings.MEDIA_ROOT = tempfile.mkdtemp(prefix='cm_perf_')
settings.DISABLE_IMAGE_MODERATION = True

from rest_framework.throttling import ScopedRateThrottle  # noqa: E402
ScopedRateThrottle.allow_request = lambda self, request, view: True

# Registro de variantes aislado (no toca Redis DB 3 real) y Celery simulado
_REGISTRY = LocMemCache('perf-verify', {})
cos_module._variants_registry = lambda: _REGISTRY

RESULTS = []


def check(name, cond, extra=''):
    RESULTS.append((name, bool(cond), extra))
    print(('PASS ' if cond else 'FAIL ') + name + (f'  -> {extra}' if extra and not cond else ''))


class Rollback(Exception):
    pass


def mk_user(tag):
    return User.objects.create_user(
        email=f"perf_{tag}_{uuid.uuid4().hex[:6]}@example.com", password='Pw12345!x',
        first_name='P', last_name=tag,
    )


def jpeg_bytes(w, h, color=(180, 60, 60)):
    buf = io.BytesIO()
    img = Image.new('RGB', (w, h), color)
    for x in range(0, w, 7):  # algo de textura para que no sea un bloque plano
        for y in range(0, h, 11):
            img.putpixel((x, y), (x % 255, y % 255, (x + y) % 255))
    img.save(buf, format='JPEG', quality=85)
    return buf.getvalue()


def abs_media(path):
    return os.path.join(settings.MEDIA_ROOT, path)


try:
    with transaction.atomic():
        key_obj = CartMakerApiKey(name='verify-perf', scope='all')
        RAW_KEY = key_obj.generate_and_set_key()
        key_obj.save()

        def client(user=None):
            c = APIClient(HTTP_X_API_KEY=RAW_KEY)
            if user is not None:
                c.force_authenticate(user)
            return c

        # ------------------------------------------------------------------
        print('\n=== 1. VARIANTES DE IMAGEN (thumb 320 / medium 800, WebP q80) ===')
        scheduled = []
        probes = []
        with mock.patch.object(iv.generate_image_variants_task, 'apply_async', side_effect=lambda *a, **k: scheduled.append((a, k))), \
                mock.patch.object(iv.ensure_image_variants_task, 'apply_async', side_effect=lambda *a, **k: probes.append((a, k))):
            big = SimpleUploadedFile('foto.jpg', jpeg_bytes(1440, 1080), content_type='image/jpeg')
            path = storage_manager.save_file(big, 'product_pictures/99', f'prod_99_0_{uuid.uuid4().hex[:6]}.jpg')
            check('save_file devuelve ruta', bool(path), path)
            check('save_file encola generate_image_variants_task', len(scheduled) == 1 and scheduled[0][1].get('args') == [path], scheduled)

            before = storage_manager.get_image_variants(path)
            check('sin variantes: thumb/medium caen al original (URL siempre válida)',
                  before['thumb_url'] == before['url'] == before['medium_url'] and before['url'])
            check('sin variantes: se agenda sondeo perezoso (1 sola vez)', len(probes) == 1)
            storage_manager.get_image_variants(path)
            check('sondeo perezoso limitado por ventana (no se repite)', len(probes) == 1, len(probes))

            check('is_image_variant_eligible(product_pictures/..jpg)', cos_module.is_image_variant_eligible(path))
            check('NO elegible: carpeta privada chat_media', not cos_module.is_image_variant_eligible('chat_media/a.jpg'))
            check('NO elegible: kyc identity_verifications', not cos_module.is_image_variant_eligible('identity_verifications/cedula_1.jpg'))
            check('NO elegible: video mp4', not cos_module.is_image_variant_eligible('stories/thumbnails/x.mp4'))
            check('NO elegible: una variante', not cos_module.is_image_variant_eligible('product_pictures/1/a__thumb.webp'))

            result = iv.generate_image_variants(path)
            check("generate_image_variants = 'generated'", result == 'generated', result)
            thumb_path = cos_module.image_variant_key(path, 'thumb')
            medium_path = cos_module.image_variant_key(path, 'medium')
            check('archivos thumb y medium existen', os.path.isfile(abs_media(thumb_path)) and os.path.isfile(abs_media(medium_path)))
            with Image.open(abs_media(thumb_path)) as t_img:
                check('thumb es WebP con lado mayor 320', t_img.format == 'WEBP' and max(t_img.size) == 320, (t_img.format, t_img.size))
            with Image.open(abs_media(medium_path)) as m_img:
                check('medium es WebP con lado mayor 800', m_img.format == 'WEBP' and max(m_img.size) == 800, (m_img.format, m_img.size))
            check('thumb mucho más liviano que el original', os.path.getsize(abs_media(thumb_path)) < os.path.getsize(abs_media(path)))
            check("segunda llamada = 'exists' (idempotente)", iv.generate_image_variants(path) == 'exists')

            after = storage_manager.get_image_variants(path)
            check('con variantes: thumb_url/medium_url apuntan a .webp',
                  after['thumb_url'].endswith('__thumb.webp') and after['medium_url'].endswith('__medium.webp'), after)
            check('con variantes: url sigue siendo el original', after['url'].endswith(os.path.basename(path)))

            small = SimpleUploadedFile('s.png', (lambda b: (Image.new('RGB', (200, 100), (10, 200, 10)).save(b, 'PNG'), b.getvalue())[1])(io.BytesIO()),
                                       content_type='image/png')
            spath = storage_manager.save_file(small, 'profiles/avatars', f'avatar_1_{uuid.uuid4().hex[:6]}.png')
            iv.generate_image_variants(spath)
            with Image.open(abs_media(cos_module.image_variant_key(spath, 'medium'))) as s_img:
                check('imágenes pequeñas no se amplían', s_img.size == (200, 100), s_img.size)

            check("original inexistente = 'missing'", iv.generate_image_variants('product_pictures/0/no_existe.jpg') == 'missing')
            check("ruta no elegible = 'skipped'", iv.generate_image_variants('chat_media/x.jpg') == 'skipped')

            # JSON de producto / usuario
            owner = mk_user('owner')
            buyer = mk_user('buyer')
            company = Company.objects.create(owner=owner, name=f'Perf Co {uuid.uuid4().hex[:5]}', image=spath)
            store = CompanyStore.objects.create(company=company, name='Sucursal P', work_hours='08:00-17:00',
                                                work_days=[0, 1, 2, 3, 4], store_type=0, store_img_url=path)
            product = Product.objects.create(company=company, name='Producto perf', price=5, description='ok', images=[path])
            pj = product.get_json()
            check('Product.get_json: images sigue siendo lista de URLs (retrocompatible)',
                  isinstance(pj['images'], list) and isinstance(pj['images'][0], str) and pj['images'][0].endswith(os.path.basename(path)), pj['images'])
            check('Product.get_json: image_variants[{url,thumb_url,medium_url}]',
                  pj['image_variants'] and set(pj['image_variants'][0]) == {'url', 'thumb_url', 'medium_url'}
                  and pj['image_variants'][0]['thumb_url'].endswith('__thumb.webp'), pj.get('image_variants'))
            cj = company.get_json()
            check('Company.get_json: image_thumb_url + image_medium_url', cj['image_thumb_url'].endswith('__thumb.webp') and cj['image_medium_url'].endswith('__medium.webp'), cj.get('image_thumb_url'))
            sj = store.get_json()
            check('CompanyStore.get_json: store_img_thumb_url', sj['store_img_thumb_url'].endswith('__thumb.webp'), sj.get('store_img_thumb_url'))
            buyer.profile_picture = spath
            check('User.get_profile_picture_thumb_url', buyer.get_profile_picture_thumb_url().endswith('__thumb.webp'))
            buyer.profile_picture = ''
            check('User sin foto => thumb vacío', buyer.get_profile_picture_thumb_url() == '')

            # Borrado conjunto
            storage_manager.delete_file(path)
            check('delete_file borra también thumb y medium (sin huérfanos)',
                  not os.path.exists(abs_media(path)) and not os.path.exists(abs_media(thumb_path)) and not os.path.exists(abs_media(medium_path)))
            check('delete_file limpia la marca de variantes', not storage_manager.variants_ready(path))

        # Cache-Control inmutable en S3 (solo objetos públicos)
        fake_s3 = mock.MagicMock()
        old_type, old_pub, old_priv, old_client = (storage_manager.storage_type, storage_manager.public_bucket_name,
                                                    storage_manager.private_bucket_name, getattr(storage_manager, 's3_client', None))
        storage_manager.storage_type, storage_manager.public_bucket_name, storage_manager.private_bucket_name = 'aws', 'pub-bkt', 'priv-bkt'
        storage_manager.s3_client = fake_s3
        try:
            with mock.patch.object(storage_manager, '_schedule_image_variants'):
                storage_manager.save_file(SimpleUploadedFile('a.jpg', jpeg_bytes(300, 200), content_type='image/jpeg'), 'product_pictures/5', 'prod_5_0_x.jpg')
                pub_args = fake_s3.upload_fileobj.call_args_list[-1].kwargs['ExtraArgs']
                check('S3 público: Cache-Control public, max-age=31536000, immutable',
                      pub_args.get('CacheControl') == 'public, max-age=31536000, immutable', pub_args)
                storage_manager.save_file(SimpleUploadedFile('c.jpg', jpeg_bytes(300, 200), content_type='image/jpeg'), 'chat_media', 'chat_1_x.jpg')
                priv_args = fake_s3.upload_fileobj.call_args_list[-1].kwargs['ExtraArgs']
                check('S3 privado: SIN Cache-Control público (cifrado SSE)', 'CacheControl' not in priv_args and priv_args.get('ServerSideEncryption') == 'AES256', priv_args)
            fake_s3.head_object.return_value = {'ContentType': 'image/jpeg', 'Metadata': {}}
            check("ensure_immutable_cache_control => 'updated'", storage_manager.ensure_immutable_cache_control('product_pictures/5/prod_5_0_x.jpg') == 'updated')
            copy_kwargs = fake_s3.copy_object.call_args.kwargs
            check('  copy_object REPLACE con CacheControl inmutable', copy_kwargs.get('MetadataDirective') == 'REPLACE' and copy_kwargs.get('CacheControl') == 'public, max-age=31536000, immutable', copy_kwargs)
            fake_s3.head_object.return_value = {'ContentType': 'image/jpeg', 'CacheControl': 'public, max-age=31536000, immutable'}
            check("ensure_immutable_cache_control => 'ok' si ya lo tiene", storage_manager.ensure_immutable_cache_control('product_pictures/5/prod_5_0_x.jpg') == 'ok')
            check("privados => 'skipped'", storage_manager.ensure_immutable_cache_control('chat_media/x.jpg') == 'skipped')
        finally:
            storage_manager.storage_type, storage_manager.public_bucket_name, storage_manager.private_bucket_name = old_type, old_pub, old_priv
            if old_client is not None:
                storage_manager.s3_client = old_client

        # ------------------------------------------------------------------
        print('\n=== 2. ÓRDENES: ETag/304, updated_after, paginación, señales ===')
        orders = []
        for i in range(5):
            orders.append(Order.objects.create(store=store, client=buyer, cart={'items': [], 'total': 5.0 + i},
                                               withdrawal_type=WithdrawalType.PICKUP))
        check('Order.updated_at se asigna al crear', all(o.updated_at for o in orders))

        c_buyer = client(buyer)
        r1 = c_buyer.get('/api/v1/orders/')
        check('GET orders/ = 200 con data (formato actual)', r1.status_code == 200 and len(r1.json()['data']) == 5, f'{r1.status_code}')
        body1 = r1.json()
        check('  incluye server_time y NO trae campos de paginación', 'server_time' in body1 and 'results' not in body1 and 'next' not in body1)
        check('  cada orden trae updated_at y store_image_thumb_url', all('updated_at' in o and 'store_image_thumb_url' in o for o in body1['data']))
        etag = r1.headers.get('ETag')
        check('  responde con ETag y Cache-Control private,no-cache', bool(etag) and 'private' in r1.headers.get('Cache-Control', '') and 'no-cache' in r1.headers.get('Cache-Control', ''), r1.headers.get('Cache-Control'))
        r304 = c_buyer.get('/api/v1/orders/', HTTP_IF_NONE_MATCH=etag)
        check('If-None-Match igual => 304 sin cuerpo', r304.status_code == 304 and not r304.content, f'{r304.status_code}')
        r304w = c_buyer.get('/api/v1/orders/', HTTP_IF_NONE_MATCH='W/' + etag)
        check('If-None-Match débil (W/) también => 304', r304w.status_code == 304)
        o0 = orders[0]
        # El resto de órdenes quedan "antiguas" para poder probar la consulta incremental con precisión
        Order.objects.exclude(pk=o0.pk).update(updated_at=timezone.now() - timezone.timedelta(hours=1))
        o0.status = OrderStatus.CANCELLED
        o0.save(update_fields=['status'])
        o0.refresh_from_db()
        check('save(update_fields=["status"]) actualiza updated_at', o0.updated_at > orders[1].updated_at)
        r_changed = c_buyer.get('/api/v1/orders/', HTTP_IF_NONE_MATCH=etag)
        check('tras cambiar una orden el ETag cambia => 200', r_changed.status_code == 200 and r_changed.headers.get('ETag') != etag)

        since = quote((o0.updated_at - timezone.timedelta(seconds=1)).isoformat(), safe='')
        r_inc = c_buyer.get(f'/api/v1/orders/?updated_after={since}')
        inc = r_inc.json()
        check('updated_after => solo la orden modificada', r_inc.status_code == 200 and [o['id'] for o in inc['data']] == [o0.id] and inc.get('incremental') is True,
              [o['id'] for o in inc.get('data', [])])
        future = quote((timezone.now() + timezone.timedelta(hours=1)).isoformat(), safe='')
        check('updated_after en el futuro => lista vacía', c_buyer.get(f'/api/v1/orders/?updated_after={future}').json()['data'] == [])
        z = (o0.updated_at - timezone.timedelta(seconds=1)).astimezone(dt_tz.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        check('updated_after con sufijo Z', c_buyer.get(f'/api/v1/orders/?updated_after={z}').status_code == 200)
        raw_plus = (o0.updated_at - timezone.timedelta(seconds=1)).astimezone(dt_tz.utc).strftime('%Y-%m-%dT%H:%M:%S+00:00')
        check('updated_after con "+00:00" sin escapar (llega como espacio)', len(c_buyer.get(f'/api/v1/orders/?updated_after={raw_plus}').json()['data']) == 1)
        epoch_ms = int((o0.updated_at - timezone.timedelta(seconds=1)).timestamp() * 1000)
        check('updated_after epoch en milisegundos', len(c_buyer.get(f'/api/v1/orders/?updated_after={epoch_ms}').json()['data']) == 1)
        r_bad = c_buyer.get('/api/v1/orders/?updated_after=ayer')
        check('updated_after inválido => 400 invalid_updated_after', r_bad.status_code == 400 and r_bad.json().get('code') == 'invalid_updated_after')

        p1 = c_buyer.get('/api/v1/orders/?page=1&page_size=2').json()
        check('paginación p1: 2 ítems, count=5, next_page=2, results==data',
              len(p1['data']) == 2 and p1['count'] == 5 and p1['next_page'] == 2 and p1['results'] == p1['data'] and p1['previous'] is None, {k: p1.get(k) for k in ('count', 'next_page', 'page')})
        check('  next es URL absoluta con page=2', isinstance(p1['next'], str) and 'page=2' in p1['next'] and p1['next'].startswith('http'), p1.get('next'))
        p3 = c_buyer.get('/api/v1/orders/?page=3&page_size=2').json()
        check('paginación p3: 1 ítem, has_next=False, next=null', len(p3['data']) == 1 and p3['has_next'] is False and p3['next'] is None and p3['total_pages'] == 3)
        seen_ids = set()
        for pg in (1, 2, 3):
            seen_ids |= {o['id'] for o in c_buyer.get(f'/api/v1/orders/?page={pg}&page_size=2').json()['data']}
        check('las 3 páginas cubren las 5 órdenes sin repetir', len(seen_ids) == 5)
        check('page_size se limita a 100', c_buyer.get('/api/v1/orders/?page=1&page_size=1000').json()['page_size'] == 100)
        check('page inválido => 400', c_buyer.get('/api/v1/orders/?page=abc').status_code == 400)

        c_owner = client(owner)
        m1 = c_owner.get('/api/v1/orders/merchant_orders/')
        check('GET merchant_orders/ = 200 con data (formato actual)', m1.status_code == 200 and len(m1.json()['data']) == 5, f'{m1.status_code} {m1.content[:200]}')
        m_etag = m1.headers.get('ETag')
        check('  merchant: 304 con If-None-Match', c_owner.get('/api/v1/orders/merchant_orders/', HTTP_IF_NONE_MATCH=m_etag).status_code == 304)
        check('  merchant: items con client_image_thumb_url', all('client_image_thumb_url' in o for o in m1.json()['data']))
        mp = c_owner.get('/api/v1/orders/merchant_orders/?page=1&page_size=3').json()
        check('  merchant: paginación (3 de 5, next_page=2)', len(mp['data']) == 3 and mp['count'] == 5 and mp['next_page'] == 2)
        mi = c_owner.get(f'/api/v1/orders/merchant_orders/?updated_after={since}').json()
        check('  merchant: updated_after incremental', [o['id'] for o in mi['data']] == [o0.id])
        check('  comprador y comercio tienen ETags distintos', etag != m_etag)

        # Señales: entrega y ticket tocan la orden
        past = timezone.now() - timezone.timedelta(days=1)
        Order.objects.filter(pk=orders[1].pk).update(updated_at=past)
        post_save.send(sender=DeliveryAssignment, instance=types.SimpleNamespace(order_id=orders[1].pk), created=False,
                       update_fields=frozenset({'last_fix_at', 'last_fix_point'}))
        orders[1].refresh_from_db()
        check('telemetría del repartidor (last_fix_*) NO toca la orden', orders[1].updated_at == past)
        post_save.send(sender=DeliveryAssignment, instance=types.SimpleNamespace(order_id=orders[1].pk), created=False,
                       update_fields=frozenset({'rider', 'status'}))
        orders[1].refresh_from_db()
        check('asignar/reasignar repartidor o cambiar estado toca la orden', orders[1].updated_at > past)
        Order.objects.filter(pk=orders[1].pk).update(updated_at=past)
        post_save.send(sender=SupportTicket, instance=types.SimpleNamespace(order_id=orders[1].pk), created=True)
        orders[1].refresh_from_db()
        check('ticket de soporte (reporte) toca la orden', orders[1].updated_at > past)

        # ------------------------------------------------------------------
        print('\n=== 3. GZIP + ETag/304 + Cache-Control en cache/* ===')
        c_anon = client()
        sc = c_anon.get('/api/v1/cache/system-config', HTTP_ACCEPT_ENCODING='gzip')
        check('cache/system-config = 200', sc.status_code == 200, sc.status_code)
        check('  gzip activado (Content-Encoding: gzip)', sc.headers.get('Content-Encoding') == 'gzip', sc.headers.get('Content-Encoding'))
        sc_etag = sc.headers.get('ETag')
        check('  trae ETag', bool(sc_etag))
        check('  Cache-Control private + max-age=120', 'private' in sc.headers.get('Cache-Control', '') and 'max-age=120' in sc.headers.get('Cache-Control', ''), sc.headers.get('Cache-Control'))
        sc304 = c_anon.get('/api/v1/cache/system-config', HTTP_ACCEPT_ENCODING='gzip', HTTP_IF_NONE_MATCH=sc_etag)
        check('  If-None-Match => 304', sc304.status_code == 304, sc304.status_code)
        mp_ = c_anon.get('/api/v1/cache/maps', HTTP_ACCEPT_ENCODING='gzip')
        check('cache/maps = 200 + ETag + max-age=300', mp_.status_code == 200 and bool(mp_.headers.get('ETag')) and 'max-age=300' in mp_.headers.get('Cache-Control', ''), f'{mp_.status_code} {mp_.headers.get("Cache-Control")}')
        check('cache/maps If-None-Match => 304', c_anon.get('/api/v1/cache/maps', HTTP_IF_NONE_MATCH=mp_.headers.get('ETag')).status_code == 304)
        plain = c_anon.get('/api/v1/cache/system-config')
        check('sin Accept-Encoding: respuesta sin comprimir', plain.headers.get('Content-Encoding') != 'gzip')

        from api.views.maps_and_cache_views import _swap_images_for_thumbnails
        sample = {'sections': [{'images': ['o1', 'o2'], 'image_variants': [{'url': 'o1', 'thumb_url': 't1'}, {'url': 'o2', 'thumb_url': None}],
                                'product': {'images': ['o1'], 'image_variants': [{'url': 'o1', 'thumb_url': 't1'}]}}]}
        _swap_images_for_thumbnails(sample['sections'])
        check('?img=thumb: images -> thumb_url (con fallback al original)', sample['sections'][0]['images'] == ['t1', 'o2'] and sample['sections'][0]['product']['images'] == ['t1'], sample)
        hc = c_anon.get('/api/v1/cache/home?lat=10.48&lng=-66.90&compact=1&img=thumb', HTTP_ACCEPT_ENCODING='gzip')
        check('cache/home?compact=1&img=thumb = 200', hc.status_code == 200, f'{hc.status_code} {hc.content[:200]}')
        if hc.status_code == 200:
            import gzip, json
            hc_body = json.loads(gzip.decompress(hc.content)) if hc.headers.get('Content-Encoding') == 'gzip' else hc.json()
            check('  compact: sin espejos en la raíz ni departments duplicado', 'selected_for_you' not in hc_body and 'departments' not in hc_body and 'departments' not in hc_body.get('sections', {}))
            check('  compact: conserva sections y categories', 'sections' in hc_body and 'categories' in hc_body)
            hc_full = c_anon.get('/api/v1/cache/home?lat=10.48&lng=-66.90')
            check('  sin compact: forma original intacta (espejos + departments)', 'selected_for_you' in hc_full.json() and 'departments' in hc_full.json())

        # ------------------------------------------------------------------
        print('\n=== 4. SOCKET + PUSH: órdenes nuevas, estados, preguntas y denuncias UGC ===')
        sent_pushes = []
        posted = []
        with mock.patch.object(NotificationManager, '_send_multicast', side_effect=lambda **kw: sent_pushes.append(kw)), \
                mock.patch('api.core.firebase_admin.requests.post', side_effect=lambda url, **kw: posted.append((url, kw.get('json')))):
            NotificationManager.notify_order_created(owner.id, orders[2].id, 'Sucursal P', 12.5)
            check('orden nueva: push FCM al comerciante con type=new_order + order_id + notification_id',
                  len(sent_pushes) == 1 and sent_pushes[0]['data_payload']['type'] == 'new_order'
                  and sent_pushes[0]['data_payload']['order_id'] == str(orders[2].id) and 'notification_id' in sent_pushes[0]['data_payload'], sent_pushes)
            check('orden nueva: se emite order_updated por socket (reason=order_created) al dueño',
                  len(posted) == 1 and posted[0][0].endswith('internal/emit-order-status') and posted[0][1]['reason'] == 'order_created'
                  and posted[0][1]['recipient_ids'] == [str(owner.id)] and posted[0][1]['is_merchant_receiver'] is True and posted[0][1]['status'] == int(orders[2].status), posted)
            check('  Notification NEW_ORDER persistida para el dueño', Notification.objects.filter(user=owner, category=NotificationCategory.NEW_ORDER, metadata__order_id=str(orders[2].id)).exists())
            check('  _merchant_staff_user_ids sin asistentes => []', NotificationManager._merchant_staff_user_ids(orders[2].id, [owner.id]) == [])

            posted.clear(); sent_pushes.clear()
            NotificationManager.notify_order_status_change(user_id=buyer.id, order_id=orders[2].id, title='t', body='b', is_merchant=False, new_status=OrderStatus.CANCELLED)
            check('cambio de estado: socket reason=cancelled a comprador', posted and posted[0][1]['reason'] == 'cancelled' and posted[0][1]['recipient_ids'] == [str(buyer.id)] and posted[0][1]['status'] == 3, posted)
            check('cambio de estado: push con type=order_status_changed y order_id', sent_pushes and sent_pushes[0]['data_payload']['type'] == 'order_status_changed' and sent_pushes[0]['data_payload']['order_id'] == str(orders[2].id))
            posted.clear()
            NotificationManager.notify_order_status_change(user_id=owner.id, order_id=orders[3].id, title='t', body='b', is_merchant=True)
            check('recordatorio (new_status=-1): el socket resuelve el estado real de la orden', posted and posted[0][1]['status'] == int(orders[3].status), posted and posted[0][1])
            posted.clear()
            NotificationManager.notify_order_status_change(user_id=buyer.id, order_id=orders[3].id, title='t', body='b', is_merchant=False,
                                                           new_status=OrderStatus.REPORTED, reported_by_role='merchant', reporter_id=owner.id, support_ticket_id=77)
            check('reporte: socket reason=reported con support_ticket_id', posted and posted[0][1]['reason'] == 'reported' and posted[0][1]['support_ticket_id'] == 77, posted)

            sent_pushes.clear()
            NotificationManager.notify_new_question(owner.id, 'Zapato', 'item-abc', 41)
            qd = sent_pushes[0]['data_payload'] if sent_pushes else {}
            check('pregunta nueva: type=new_question + question_id + item_id + notification_id', qd.get('type') == 'new_question' and qd.get('question_id') == '41' and qd.get('item_id') == 'item-abc' and 'notification_id' in qd, qd)
            sent_pushes.clear()
            NotificationManager.notify_new_answer(buyer.id, 'Perf Co', 'Zapato', 'item-abc', 'item')
            ad = sent_pushes[0]['data_payload'] if sent_pushes else {}
            check('respuesta: type conserva generic_refresh y suma event/item_id/target_type', ad.get('type') == 'generic_refresh' and ad.get('event') == 'new_answer' and ad.get('item_id') == 'item-abc' and ad.get('target_type') == 'item', ad)

            sent_pushes.clear()
            reporter = mk_user('reporter')
            report = ContentReport.objects.create(reporter=reporter, target_type='product', target_id=str(product.id), reason='OTHER')
            with TestCase.captureOnCommitCallbacks(execute=True):
                report.status = ContentReport.ReportStatus.REMOVED
                report.save()
            ugc = [p for p in sent_pushes if p['data_payload'].get('type') == 'ugc_report_resolved']
            check('denuncia REMOVED: push al denunciante con type=ugc_report_resolved, report_id, outcome=removed',
                  len(ugc) == 1 and ugc[0]['data_payload']['outcome'] == 'removed' and ugc[0]['data_payload']['report_id'] == str(report.id)
                  and ugc[0]['data_payload']['target_id'] == str(product.id), ugc)
            check('  Notification UGC_REPORT_RESOLVED persistida', Notification.objects.filter(user=reporter, category=NotificationCategory.UGC_REPORT_RESOLVED).count() == 1)
            report.refresh_from_db()
            check('  resolved_at sellado automáticamente', report.resolved_at is not None)
            with TestCase.captureOnCommitCallbacks(execute=True):
                report.description = 'editado'
                report.save()
            check('  re-guardar una denuncia ya resuelta NO duplica el aviso', len([p for p in sent_pushes if p['data_payload'].get('type') == 'ugc_report_resolved']) == 1)
            report2 = ContentReport.objects.create(reporter=reporter, target_type='video', target_id='abc', reason='OTHER')
            with TestCase.captureOnCommitCallbacks(execute=True):
                report2.status = ContentReport.ReportStatus.DISMISSED
                report2.save()
            check('denuncia DISMISSED: outcome=dismissed', any(p['data_payload'].get('outcome') == 'dismissed' for p in sent_pushes))
            report3 = ContentReport.objects.create(reporter=None, target_type='image', target_id='x.jpg', reason='NUDITY_OR_SEXUAL', status=ContentReport.ReportStatus.QUARANTINED)
            n_before = len(sent_pushes)
            with TestCase.captureOnCommitCallbacks(execute=True):
                report3.status = ContentReport.ReportStatus.REMOVED
                report3.save()
            check('reporte automático del sistema (sin denunciante): no notifica a nadie', len(sent_pushes) == n_before)

        # ------------------------------------------------------------------
        print('\n=== 5. VIDEO: miniatura garantizada + video ligero de feed (ffmpeg simulado) ===')
        import api.tasks as T
        shim_dir = tempfile.mkdtemp(prefix='cm_ffshim_')
        log_file = os.path.join(shim_dir, 'calls.log')
        shim = os.path.join(shim_dir, 'ffmpeg')
        import sys as _sys
        with open(shim, 'w') as fh:
            fh.write('#!/bin/bash\n'
                     f'echo "$@" >> {log_file}\n'
                     'for last; do :; done\n'
                     f'case "$last" in *.jpg) {_sys.executable} - "$last" <<EOF\n'
                     'import sys\n'
                     'from PIL import Image\n'
                     'Image.new("RGB", (90, 160), (30, 90, 200)).save(sys.argv[1], "JPEG")\n'
                     'EOF\n;; *) echo fake-mp4-bytes > "$last";; esac\n'
                     'exit 0\n')
        os.chmod(shim, os.stat(shim).st_mode | stat.S_IEXEC)
        old_path = os.environ['PATH']
        os.environ['PATH'] = shim_dir + os.pathsep + old_path
        try:
            with mock.patch.object(iv.generate_image_variants_task, 'apply_async'):
                vpath = storage_manager.save_file(SimpleUploadedFile('v.mp4', b'\x00' * 2048, content_type='video/mp4'), 'stories/videos', 'story_video_1_x.mp4')
                story = CompanyVideoStory.objects.create(company=company, title='t', video_file=vpath, thumbnail=None, duration_seconds=5,
                                                         expires_at=timezone.now() + timezone.timedelta(hours=72))
                T._ensure_story_thumbnail_and_feed_video(story)
                story.refresh_from_db()
                check('sin miniatura: se extrae un fotograma y se guarda como thumbnail', bool(story.thumbnail) and os.path.isfile(abs_media(story.thumbnail)), story.thumbnail)
                check('se genera feed_video_file en stories/videos/feed_*.mp4', bool(story.feed_video_file) and story.feed_video_file.startswith('stories/videos/feed_') and os.path.isfile(abs_media(story.feed_video_file)), story.feed_video_file)
                calls = open(log_file).read()
                check('ffmpeg de feed: H.264 main, <=2.5 Mbps, faststart, AAC 96k, escala a 720 de lado corto',
                      all(flag in calls for flag in ('libx264', '+faststart', '2500k', 'aac', '96k', 'min(720,iw)', 'yuv420p')), calls[-600:])
                sj = story.get_json()
                check('get_json: video_url_feed apunta al feed y video_url al original',
                      '/feed_' in sj['video_url_feed'] and sj['video_url'].endswith(os.path.basename(vpath)), (sj['video_url_feed'], sj['video_url']))
                check('get_json: thumbnail_thumb_url / thumbnail_medium_url presentes', 'thumbnail_thumb_url' in sj and 'thumbnail_medium_url' in sj and sj['thumbnail_url'])
                old_feed = story.feed_video_file
                story.feed_video_file = None
                story.save(update_fields=['feed_video_file'])
                sj2 = story.get_json()
                check('sin feed todavía: video_url_feed cae al original (retrocompatible)', sj2['video_url_feed'] == sj2['video_url'])
                story.feed_video_file = old_feed
                story.save(update_fields=['feed_video_file'])
                feed_abs = abs_media(old_feed)
                story.clear_media_files()
                check('clear_media_files borra video, feed y miniatura', not os.path.exists(feed_abs) and story.feed_video_file is None and story.video_file is None and story.thumbnail is None)
        finally:
            os.environ['PATH'] = old_path

        # ------------------------------------------------------------------
        print('\n=== 5b. VIDEO REAL: imageio-ffmpeg (extracción de fotogramas, duración y transcodificación real) ===')
        import subprocess
        from api.core.content_moderation import get_ffmpeg_binary, get_video_duration_seconds, extract_video_frames
        real_ff = get_ffmpeg_binary()
        check('get_ffmpeg_binary resuelve un ejecutable real (sistema o imageio-ffmpeg)', os.path.isfile(real_ff), real_ff)
        with tempfile.TemporaryDirectory() as real_tmp:
            real_vid = os.path.join(real_tmp, 'real_sample.mp4')
            subprocess.run(
                [real_ff, '-y', '-f', 'lavfi', '-i', 'testsrc=duration=2:size=1080x1920:rate=15',
                 '-f', 'lavfi', '-i', 'sine=frequency=440:duration=2',
                 '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p',
                 '-c:a', 'aac', '-b:a', '96k', real_vid],
                check=True, capture_output=True, timeout=60,
            )
            dur = get_video_duration_seconds(real_vid)
            check('get_video_duration_seconds lee duración real (~2.0 s)', 1.8 <= dur <= 2.3, dur)
            frames = extract_video_frames(real_vid, count=3)
            check('extract_video_frames extrae 3 fotogramas JPEG reales', len(frames) == 3 and all(len(f) > 500 for f in frames), [len(f) for f in frames])
            with open(real_vid, 'rb') as fh:
                real_vid_bytes = fh.read()
            with mock.patch.object(iv.generate_image_variants_task, 'apply_async'):
                vpath_real = storage_manager.save_file(SimpleUploadedFile('real.mp4', real_vid_bytes, content_type='video/mp4'), 'stories/videos', 'story_video_real.mp4')
                story_real = CompanyVideoStory.objects.create(company=company, title='real', video_file=vpath_real, thumbnail=None, duration_seconds=2,
                                                              expires_at=timezone.now() + timezone.timedelta(hours=72))
                T._ensure_story_thumbnail_and_feed_video(story_real)
                story_real.refresh_from_db()
                check('transcodificación real 1080x1920 -> 720x1280 + miniatura JPEG con imageio-ffmpeg',
                      bool(story_real.thumbnail) and bool(story_real.feed_video_file) and os.path.isfile(abs_media(story_real.feed_video_file)),
                      (story_real.thumbnail, story_real.feed_video_file))
                story_real.clear_media_files()

        raise Rollback()
except Rollback:
    print('\n(transacción revertida: BD sin cambios)')

print('\n=== RESUMEN ===')
fails = [r for r in RESULTS if not r[1]]
print(f'{len(RESULTS) - len(fails)}/{len(RESULTS)} OK')
for n, _, e in fails:
    print('  FAIL:', n, e)
