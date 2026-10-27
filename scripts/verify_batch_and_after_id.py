"""
Verificación funcional de:
  - Backfill incremental `?after_id=` en GET chat/messages/history/ y GET chat/support/history/
  - POST /api/v1/logs/batch/ (y que los endpoints individuales de logs sigan respondiendo igual)
Uso (BD LOCAL únicamente):  python manage.py shell < scripts/verify_batch_and_after_id.py
Todo corre dentro de una transacción que SIEMPRE se revierte; Redis se mockea (no se encola nada real).
"""
import json
import uuid
from datetime import timedelta, timezone as dt_tz
from unittest import mock

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone
from rest_framework.test import APIClient

from api.models import (
    CartMakerApiKey, Company, CompanyStore, Order, SupportMessage, SupportTicket, User,
)
from chat.models import ChatMessage

assert settings.DEBUG, 'Abortado: solo debe correrse con DEBUG=1 (entorno local)'
assert connection.settings_dict['HOST'] in ('127.0.0.1', 'localhost', ''), 'Abortado: la BD no es local'

if 'testserver' not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS.append('testserver')

RESULTS = []

# Los throttles (429) se verifican aparte (sección 5); aquí se desactivan para no interferir.
from rest_framework.throttling import ScopedRateThrottle  # noqa: E402
_orig_allow_request = ScopedRateThrottle.allow_request
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


def client(user=None):
    c = APIClient(HTTP_X_API_KEY=RAW_KEY)
    if user is not None:
        c.force_authenticate(user)
    return c


def post_json(c, url, body):
    return c.post(url, data=json.dumps(body), content_type='application/json')


def ids(resp):
    return [m['id'] for m in resp.data['data']]


class FakeRedis:
    def __init__(self):
        self.calls = []

    def rpush(self, key, value):
        self.calls.append((key, json.loads(value)))


try:
    with transaction.atomic():
        key_obj = CartMakerApiKey(name='verify-tmp', scope='all')
        RAW_KEY = key_obj.generate_and_set_key()
        key_obj.save()

        # ------------------------------------------------------------------
        print('\n=== FIXTURES ===')
        owner = mk_user('owner')
        buyer = mk_user('buyer')
        stranger = mk_user('stranger')
        company = Company.objects.create(owner=owner, name=f'Verif Co {uuid.uuid4().hex[:5]}')
        store = CompanyStore.objects.create(company=company, name='Sucursal V', work_hours='08:00-17:00',
                                            work_days=[0, 1, 2, 3, 4], store_type=0)
        order = Order.objects.create(store=store, client=buyer, cart=[], withdrawal_type=0)
        chat_msgs = [ChatMessage.objects.create(order=order, sender=buyer if i % 2 == 0 else owner, text=f'm{i}')
                     for i in range(7)]
        ticket = SupportTicket.objects.create(client=buyer, title='T verif', description='d')
        sup_msgs = [SupportMessage.objects.create(ticket=ticket, sender=buyer, text=f's{i}') for i in range(7)]
        print('   fixtures creados')

        # ------------------------------------------------------------------
        print('\n=== 1. after_id EN chat/messages/history/ ===')
        cb = client(buyer)
        url = '/chat/messages/history/'
        base = f'{url}?order_id={order.id}'
        ids_all = [m.id for m in chat_msgs]

        r = cb.get(base)
        check('sin after_id: 200 y forma clásica (next_offset presente, sin has_more)',
              r.status_code == 200 and 'next_offset' in r.data and 'has_more' not in r.data and 'next_after_id' not in r.data,
              str(r.data.keys()))
        check('sin after_id: cronológico asc', ids(r) == ids_all, str(ids(r)))
        r = cb.get(f'{base}&limit=3')
        check('sin after_id con limit=3: últimos 3 + next_offset=3', ids(r) == ids_all[-3:] and r.data['next_offset'] == 3)

        r = cb.get(f'{base}&after_id=0')
        check('after_id=0: todos, asc', r.status_code == 200 and ids(r) == ids_all, str(ids(r)))
        check('  has_more False, next_after_id = último, next_offset None',
              r.data['has_more'] is False and r.data['next_after_id'] == ids_all[-1] and r.data['next_offset'] is None, str(r.data))
        r = cb.get(f'{base}&after_id={ids_all[2]}')
        check('after_id=id[2]: solo id > after_id', ids(r) == ids_all[3:], str(ids(r)))
        r = cb.get(f'{base}&after_id={ids_all[2]}&limit=2')
        check('after_id con limit=2: 2 mensajes, has_more True, next_after_id = último devuelto',
              ids(r) == ids_all[3:5] and r.data['has_more'] is True and r.data['next_after_id'] == ids_all[4], str(r.data))
        r = cb.get(f'{base}&after_id={ids_all[4]}&limit=2')
        check('  siguiente página: has_more False (justo 2 restantes)',
              ids(r) == ids_all[5:7] and r.data['has_more'] is False and r.data['next_after_id'] == ids_all[6])
        r = cb.get(f'{base}&after_id={ids_all[-1]}')
        check('sin nuevos: data [], has_more False, next_after_id = after_id recibido',
              r.data['data'] == [] and r.data['has_more'] is False and r.data['next_after_id'] == ids_all[-1])
        r = cb.get(f'{base}&after_id=0&limit=9999')
        check('limit > 200 se acota (no falla)', r.status_code == 200 and len(r.data['data']) == 7)
        # límite default 100 / máx 200 con más datos
        extra = ChatMessage.objects.bulk_create([ChatMessage(order=order, sender=buyer, text=f'x{i}') for i in range(210)])
        r = cb.get(f'{base}&after_id=0')
        check('default limit=100 con 217 mensajes: 100 + has_more', len(r.data['data']) == 100 and r.data['has_more'] is True)
        r = cb.get(f'{base}&after_id=0&limit=500')
        check('limit=500 -> tope 200', len(r.data['data']) == 200 and r.data['has_more'] is True)
        ChatMessage.objects.filter(order=order, text__startswith='x').delete()

        for bad in ('abc', '-1', '1.5', '1e3'):
            r = cb.get(f'{base}&after_id={bad}')
            check(f'after_id inválido "{bad}" -> 400 con error', r.status_code == 400 and 'error' in r.data, str(r.data))
        r = client(stranger).get(f'{base}&after_id=0')
        check('permisos: usuario ajeno -> 403 también con after_id', r.status_code == 403)
        r = client(owner).get(f'{base}&after_id=0')
        check('permisos: dueño de la tienda accede con after_id', r.status_code == 200 and len(r.data['data']) == 7)
        r = cb.get(f'{url}?after_id=0')
        check('sin order_id -> 400', r.status_code == 400)
        r = cb.get(f'{url}?order_id=99999999&after_id=0')
        check('orden inexistente -> 404', r.status_code == 404)

        # ------------------------------------------------------------------
        print('\n=== 2. after_id EN chat/support/history/ ===')
        surl = '/chat/support/history/'
        sbase = f'{surl}?ticket_id={ticket.id}'
        sids = [m.id for m in sup_msgs]
        r = cb.get(sbase)
        check('sin after_id: forma clásica con ticket', r.status_code == 200 and 'ticket' in r.data and 'has_more' not in r.data and ids(r) == sids)
        r = cb.get(f'{sbase}&after_id=0&limit=3')
        check('after_id=0&limit=3: 3 primeros asc, has_more True, ticket presente, next_offset None',
              ids(r) == sids[:3] and r.data['has_more'] is True and r.data['next_after_id'] == sids[2]
              and 'ticket' in r.data and r.data['next_offset'] is None, str(r.data.keys()))
        r = cb.get(f'{sbase}&after_id={sids[2]}')
        check('after_id=id[2]: solo id > after_id', ids(r) == sids[3:] and r.data['has_more'] is False)
        r = cb.get(f'{sbase}&after_id={sids[-1]}')
        check('sin nuevos: [] y next_after_id = after_id', r.data['data'] == [] and r.data['next_after_id'] == sids[-1] and 'ticket' in r.data)
        for bad in ('abc', '-5'):
            r = cb.get(f'{sbase}&after_id={bad}')
            check(f'after_id inválido "{bad}" -> 400 con error', r.status_code == 400 and 'error' in r.data)
        r = client(stranger).get(f'{sbase}&after_id=0')
        check('permisos: ajeno -> 403 con after_id', r.status_code == 403)
        r = cb.get(f'{surl}?ticket_id=99999999&after_id=0')
        check('ticket inexistente -> 404', r.status_code == 404)

        # ------------------------------------------------------------------
        print('\n=== 3. ENDPOINTS INDIVIDUALES DE LOGS (sin cambios de comportamiento) ===')
        import api.views.support_and_analytics_views as V
        fake = FakeRedis()
        fake_cache = mock.MagicMock()
        fake_cache.client.get_client.return_value = fake
        now_iso = timezone.now().isoformat()
        with mock.patch.object(V, 'cache', fake_cache):
            c = client(buyer)
            r = post_json(c, '/api/v1/logs/product_view/', {'item_id': 5, 'start_time': now_iso, 'bought': True})
            check('product_view ok -> 202 sin cuerpo', r.status_code == 202 and not r.content, f'{r.status_code} {r.content}')
            r = post_json(c, '/api/v1/logs/product_view/', {'item_id': 5})
            check('product_view sin start_time -> 400', r.status_code == 400 and r.data == {'error': 'item_id y start_time son obligatorios.'})
            r = post_json(c, '/api/v1/logs/store_view/', {'store_id': 3, 'join_time': now_iso})
            check('store_view ok -> 202', r.status_code == 202 and not r.content)
            r = post_json(c, '/api/v1/logs/store_view/', {'store_id': 3})
            check('store_view sin join_time -> 400', r.status_code == 400 and r.data == {'error': 'store_id y join_time son obligatorios.'})
            r = post_json(c, '/api/v1/logs/navigation/', {'login_time': now_iso, 'navigation_record': {'a': 1}})
            check('navigation ok -> 202', r.status_code == 202 and not r.content)
            r = post_json(c, '/api/v1/logs/navigation/', {})
            check('navigation sin login_time -> 400', r.status_code == 400 and r.data == {'error': 'login_time es obligatorio.'})
            r = post_json(c, '/api/v1/logs/video_engagement/', {'video_id': 9, 'watch_time_seconds': 3, 'video_completed': 'true'})
            check('video_engagement ok -> 202 {success}', r.status_code == 202 and r.data == {'success': True})
            r = post_json(c, '/api/v1/logs/video_engagement/', {})
            check('video_engagement sin video_id -> 400', r.status_code == 400 and r.data == {'error': 'video_id es obligatorio.'})
            r = client().post('/api/v1/logs/product_view/', data='{}', content_type='application/json')
            check('sin autenticación -> 401/403', r.status_code in (401, 403))
            keys = [k for k, _ in fake.calls]
            check('encolado en las 4 listas esperadas', keys == ['telemetry:product_views', 'telemetry:store_views',
                  'telemetry:navigation_logs', 'telemetry:video_engagement'], str(keys))
            indiv_payloads = {k: p for k, p in fake.calls}
            check('payload individual product_view', indiv_payloads['telemetry:product_views'] == {
                'client_id': str(buyer.id), 'item_id': '5', 'added_to_cart': False, 'bought': True, 'start_time': now_iso,
                'end_time': None, 'origin_source': 'organic', 'search_prompt': None, 'ai_keywords': None, 'atlas_message_id': None})

        # Redis caído -> 500 en individual (comportamiento previo)
        boom = mock.MagicMock()
        boom.client.get_client.side_effect = RuntimeError('redis down')
        with mock.patch.object(V, 'cache', boom):
            r = post_json(client(buyer), '/api/v1/logs/store_view/', {'store_id': 3, 'join_time': now_iso})
            check('Redis caído: individual -> 500 {error: Error interno}', r.status_code == 500 and r.data == {'error': 'Error interno'})

        # ------------------------------------------------------------------
        print('\n=== 4. POST /api/v1/logs/batch/ ===')
        burl = '/api/v1/logs/batch/'
        recent_ms = int((timezone.now() - timedelta(hours=1)).timestamp() * 1000)
        recent_iso = (timezone.now() - timedelta(hours=2)).isoformat()
        events = [
            {'type': 'product_view', 'payload': {'item_id': 5, 'start_time': now_iso, 'bought': True}},       # 0 ok
            {'type': 'video_engagement', 'payload': {'video_id': 9, 'watch_time_seconds': 3}},                 # 1 ok
            {'type': 'store_view', 'payload': {'store_id': 3, 'join_time': now_iso}},                          # 2 ok
            {'type': 'navigation', 'payload': {'login_time': now_iso, 'navigation_record': {'a': 1}}},         # 3 ok
            {'type': 'product_view', 'payload': {'item_id': 5}},                                               # 4 error (falta start_time)
            {'type': 'inexistente', 'payload': {}},                                                            # 5 error tipo
            {'type': 'video_engagement', 'payload': {'video_id': 9, 'watch_time_seconds': 'abc'}},             # 6 error float
            {'type': 'store_view'},                                                                            # 7 error sin payload
            'no-soy-objeto',                                                                                   # 8 error
            {'type': 'store_view', 'payload': {'store_id': 4}, 'ts': recent_ms},                               # 9 ok (ts epoch ms rellena join_time)
            {'type': 'navigation', 'payload': {}, 'ts': recent_iso},                                           # 10 ok (ts ISO rellena login_time)
            {'type': 'navigation', 'payload': {}, 'ts': (timezone.now() + timedelta(hours=5)).isoformat()},    # 11 error (ts futuro ignorado)
            {'type': 'navigation', 'payload': {}, 'ts': (timezone.now() - timedelta(days=8)).isoformat()},     # 12 error (ts > 7 días ignorado)
            {'type': 'product_view', 'payload': {'item_id': 7, 'start_time': now_iso}, 'ts': 'basura'},        # 13 ok (ts inválido ignorado)
            {'type': 'store_view', 'payload': {'store_id': 6, 'join_time': 'EXPLICITO'}, 'ts': recent_ms},     # 14 ok (el campo explícito gana)
        ]
        fake = FakeRedis()
        fake_cache = mock.MagicMock()
        fake_cache.client.get_client.return_value = fake
        with mock.patch.object(V, 'cache', fake_cache):
            r = post_json(client(buyer), burl, {'events': events})
            check('batch mixto -> 200', r.status_code == 200, f'{r.status_code} {getattr(r, "data", r.content)}')
            d = r.data
            st = [x['status'] for x in d['results']]
            exp = ['ok'] * 4 + ['error'] * 5 + ['ok', 'ok', 'error', 'error', 'ok', 'ok']
            check('estados por índice correctos', st == exp, str(st))
            check('success/accepted/rejected', d['success'] is True and d['accepted'] == 8 and d['rejected'] == 7, f"{d['accepted']}/{d['rejected']}")
            check('results trae index y type en cada elemento', [x['index'] for x in d['results']] == list(range(len(events)))
                  and d['results'][0]['type'] == 'product_view' and d['results'][5]['type'] == 'inexistente')
            check('errores traen mensaje', all(x.get('error') for x in d['results'] if x['status'] == 'error'))
            check('ok no trae error', all('error' not in x for x in d['results'] if x['status'] == 'ok'))
            check('tipo desconocido -> error en ese índice', d['results'][5]['status'] == 'error')
            keys = [k for k, _ in fake.calls]
            check('solo se encolaron los 8 válidos', len(keys) == 8, str(len(keys)))
            by_idx = fake.calls
            check('payload batch product_view idéntico al individual',
                  by_idx[0][1] == {'client_id': str(buyer.id), 'item_id': '5', 'added_to_cart': False, 'bought': True,
                                   'start_time': now_iso, 'end_time': None, 'origin_source': 'organic', 'search_prompt': None,
                                   'ai_keywords': None, 'atlas_message_id': None})
            check('ts epoch ms rellena join_time', by_idx[4][0] == 'telemetry:store_views' and by_idx[4][1]['join_time'].startswith(
                  (timezone.now() - timedelta(hours=1)).astimezone(dt_tz.utc).strftime('%Y-%m-%dT%H')), str(by_idx[4]))
            check('ts ISO rellena login_time', by_idx[5][0] == 'telemetry:navigation_logs' and by_idx[5][1]['login_time'], str(by_idx[5]))
            check('ts inválido ignorado (usa start_time del payload)', by_idx[6][1]['start_time'] == now_iso)
            check('campo explícito tiene prioridad sobre ts', by_idx[7][1]['join_time'] == 'EXPLICITO')

            # lista directa
            fake.calls.clear()
            r = post_json(client(buyer), burl, [events[0], events[1]])
            check('lista JSON directa -> 200 con 2 aceptados', r.status_code == 200 and r.data['accepted'] == 2 and r.data['rejected'] == 0, str(r.data))
            # exactamente 100
            fake.calls.clear()
            r = post_json(client(buyer), burl, {'events': [events[0]] * 100})
            check('100 eventos -> 200', r.status_code == 200 and r.data['accepted'] == 100 and len(fake.calls) == 100)
            # 101
            fake.calls.clear()
            r = post_json(client(buyer), burl, {'events': [events[0]] * 101})
            check('101 eventos -> 400 con error y sin encolar', r.status_code == 400 and 'error' in r.data and not fake.calls, str(r.data))
            r = post_json(client(buyer), burl, [events[0]] * 101)
            check('lista directa de 101 -> 400', r.status_code == 400)
            # vacío / forma inválida
            r = post_json(client(buyer), burl, {'events': []})
            check('events vacío -> 200 con 0 aceptados', r.status_code == 200 and r.data['accepted'] == 0 and r.data['results'] == [])
            for bad_body in ({'foo': 1}, {'events': 'x'}, 'texto', 5):
                r = post_json(client(buyer), burl, bad_body)
                check(f'cuerpo inválido {bad_body!r} -> 400', r.status_code == 400 and 'error' in r.data, f'{r.status_code}')
            # permisos
            r = client().post(burl, data='{"events": []}', content_type='application/json')
            check('batch sin autenticación -> 401/403', r.status_code in (401, 403))

        with mock.patch.object(V, 'cache', boom):
            r = post_json(client(buyer), burl, {'events': [events[0], events[2]]})
            check('Redis caído: batch 200 con ambos en error (no explota)',
                  r.status_code == 200 and r.data['accepted'] == 0 and r.data['rejected'] == 2
                  and all(x['error'] == 'Error interno' for x in r.data['results']), str(getattr(r, 'data', r.content)))

        # ------------------------------------------------------------------
        print('\n=== 5. THROTTLE DEL BATCH ===')
        ScopedRateThrottle.allow_request = _orig_allow_request
        th = V.LogsBatchThrottle()
        check('scope batch con tasa por defecto razonable (>= 30/min si no hay config)',
              th.get_rate() == settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'].get('logs_batch', '30/minute'))
        check('scope de endpoints individuales sigue en actions',
              V.InteractionLogViewSet.throttle_scope == 'actions' and V.InteractionLogViewSet.batch.kwargs['throttle_scope'] == 'logs_batch')
        ScopedRateThrottle.allow_request = lambda self, request, view: True

        raise Rollback()
except Rollback:
    print('\n(transacción revertida: BD sin cambios)')

print('\n=== RESUMEN ===')
fails = [r for r in RESULTS if not r[1]]
print(f'{len(RESULTS) - len(fails)}/{len(RESULTS)} OK')
for n, _, e in fails:
    print('  FAIL:', n, e)
