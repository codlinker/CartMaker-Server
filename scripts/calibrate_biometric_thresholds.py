#!/usr/bin/env python
"""
Calibración de umbrales biométricos (distancia coseno) para CartMaker.

Contexto: el backend compara embeddings faciales de 512-D con distancia coseno (1 - cos θ) y usa los umbrales
de `api/utils.py` (BIOMETRIC_THRESHOLDS_BY_MODEL: perfect / acceptable_1n / one_to_one / kyc_duplicate /
min_margin). Al migrar de 'mobilefacenet-fp32-v1' a 'mobilefacenet-int8-v1' la cuantización desplaza las
distribuciones de distancia, así que los umbrales deben recalibrarse por versión. Este script ayuda a hacerlo.

Entrada (CSV o JSONL, una fila por par etiquetado):
  - embedding_a, embedding_b : lista JSON de 512 floats, o ruta a un .npy / .json (relativa al archivo de
                               entrada o absoluta) que contenga esa lista.
  - same_person              : 1/0 (también true/false). 1 = par genuino, 0 = par impostor.
  - model_version (opcional) : p. ej. 'mobilefacenet-int8-v1'. Si existe se calculan métricas por versión
                               (o solo de una versión con --model-version).

Salida: tabla FAR/FRR para umbrales 0.05..0.60 (configurable), EER, y recomendaciones:
  - umbral 1:1 (one_to_one)    : mayor umbral con FAR <= 0.1 %
  - umbral 1:N (acceptable_1n) : mayor umbral con FAR <= 0.01 %
  - min_margin sugerido        : heurística = ancho de la cola baja de la distribución impostora
                                 (percentil 5 - percentil 0.1 de las distancias impostoras). Es una cota
                                 orientativa para el margen de Lowe en 1:N (distancia top-2 - top-1).
  - comparación contra los umbrales actuales (FAR/FRR a cada umbral vigente).
Con --json se emite además/en su lugar un JSON estructurado (--json-only para solo JSON).

Modo --self-test: genera pares sintéticos (gaussianas sobre S^511) y valida el cálculo; no usa datos reales.

!!! IMPORTANTE !!!  Este script NO sustituye validar con un set REAL de pares de personas distintas y
reales (varias sesiones, iluminación, dispositivos, edades, tonos de piel, accesorios...). Los resultados
solo son tan buenos como los pares de entrada. Con N pares impostores el FAR mínimo medible es 1/N: para
certificar FAR = 0.01 % hacen falta >= 100 000 pares impostores (el script avisa cuando no alcanza).
Los resultados sobre datos sintéticos solo prueban que la matemática del script es correcta.

Uso:
  python scripts/calibrate_biometric_thresholds.py pairs.csv
  python scripts/calibrate_biometric_thresholds.py pairs.jsonl --model-version mobilefacenet-int8-v1 --json
  python scripts/calibrate_biometric_thresholds.py --self-test
"""
import argparse
import csv
import json
import math
import os
import sys
import tempfile

import numpy as np

# Umbrales vigentes (api/utils.py). Se pueden sobrescribir por CLI si se calibró otra versión.
CURRENT_THRESHOLDS = {
    'perfect': 0.18,
    'acceptable_1n': 0.26,
    'one_to_one': 0.30,
    'kyc_duplicate': 0.30,
    'min_margin': 0.08,
}
FAR_TARGET_1TO1 = 0.001      # 0.1 %
FAR_TARGET_1TON = 0.0001     # 0.01 %
MARGIN_PCT_HIGH = 5.0        # percentil alto de la cola impostora
MARGIN_PCT_LOW = 0.1         # percentil bajo de la cola impostora
EXPECTED_DIM = 512


# ---------------------------------------------------------------------------
# Matemática
# ---------------------------------------------------------------------------
def cosine_distances(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Distancia coseno fila a fila: 1 - <a,b> / (||a|| ||b||). a, b: (n, d)."""
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    na = np.linalg.norm(a, axis=1)
    nb = np.linalg.norm(b, axis=1)
    if np.any(na < 1e-9) or np.any(nb < 1e-9):
        raise ValueError('Se encontró un embedding con norma ~0.')
    cos = np.einsum('ij,ij->i', a, b) / (na * nb)
    return 1.0 - np.clip(cos, -1.0, 1.0)


def far_frr(genuine: np.ndarray, impostor: np.ndarray, thresholds: np.ndarray):
    """FAR(t) = P(d_impostor <= t), FRR(t) = P(d_genuine > t). Se acepta cuando d <= t."""
    g = np.sort(genuine)
    i = np.sort(impostor)
    far = np.searchsorted(i, thresholds, side='right') / len(i)
    frr = 1.0 - np.searchsorted(g, thresholds, side='right') / len(g)
    return far, frr


def compute_eer(genuine: np.ndarray, impostor: np.ndarray):
    """EER exacto sobre todas las distancias observadas. Devuelve (eer, umbral)."""
    cand = np.unique(np.concatenate([genuine, impostor]))
    far, frr = far_frr(genuine, impostor, cand)
    idx = int(np.argmin(np.abs(far - frr)))
    return float((far[idx] + frr[idx]) / 2.0), float(cand[idx])


def max_threshold_for_far(impostor: np.ndarray, far_target: float, lo: float, hi: float):
    """
    Mayor umbral t en [lo, hi] (redondeado hacia abajo a 3 decimales) tal que FAR(t) <= far_target.
    Devuelve None si ni siquiera `lo` cumple el objetivo.
    """
    imp = np.sort(impostor)
    n = len(imp)
    allowed = int(math.floor(far_target * n + 1e-9))  # impostores que pueden aceptarse
    if allowed >= n:
        t = hi
    else:
        t = float(np.nextafter(imp[allowed], -np.inf))  # justo debajo del primer impostor no tolerado
    t = min(t, hi)
    t = math.floor(t * 1000.0) / 1000.0
    if t < lo:
        return None
    return t


def analyze(genuine, impostor, lo, hi, step, current):
    genuine = np.asarray(genuine, dtype=np.float64)
    impostor = np.asarray(impostor, dtype=np.float64)
    if len(genuine) == 0 or len(impostor) == 0:
        raise ValueError('Se necesitan pares genuinos (same_person=1) e impostores (same_person=0).')

    n_steps = int(round((hi - lo) / step))
    grid = np.round(lo + step * np.arange(n_steps + 1), 6)
    far, frr = far_frr(genuine, impostor, grid)
    eer, eer_thr = compute_eer(genuine, impostor)

    t_1to1 = max_threshold_for_far(impostor, FAR_TARGET_1TO1, lo, hi)
    t_1ton = max_threshold_for_far(impostor, FAR_TARGET_1TON, lo, hi)
    p_hi = float(np.percentile(impostor, MARGIN_PCT_HIGH))
    p_lo = float(np.percentile(impostor, MARGIN_PCT_LOW))
    margin = max(0.0, p_hi - p_lo)

    def at(t):
        if t is None:
            return None
        f, r = far_frr(genuine, impostor, np.array([t]))
        return {'threshold': round(float(t), 4), 'far': float(f[0]), 'frr': float(r[0])}

    cur = {}
    for key in ('perfect', 'acceptable_1n', 'one_to_one', 'kyc_duplicate'):
        cur[key] = at(current[key])
    cur['min_margin'] = {'value': current['min_margin']}

    n_imp = len(impostor)
    warnings = []
    if 1.0 / n_imp > FAR_TARGET_1TON:
        warnings.append(
            f'Resolución insuficiente: con {n_imp} pares impostores el FAR mínimo medible es {100.0 / n_imp:.4f} % '
            f'(para validar FAR=0.01 % hacen falta >= {int(1 / FAR_TARGET_1TON)} pares impostores). '
            'El umbral 1:N recomendado es optimista.'
        )
    elif 1.0 / n_imp > FAR_TARGET_1TO1:
        warnings.append(
            f'Resolución insuficiente para FAR=0.1 %: solo {n_imp} pares impostores (se necesitan >= {int(1 / FAR_TARGET_1TO1)}).'
        )
    if len(genuine) < 1000:
        warnings.append(f'Pocos pares genuinos ({len(genuine)}): el FRR tiene mucha varianza (recomendado >= 1000).')
    warnings.append('Validar siempre con un set real de pares de personas; este análisis no lo sustituye.')

    return {
        'n_genuine': int(len(genuine)),
        'n_impostor': int(n_imp),
        'genuine_distance': {
            'mean': float(genuine.mean()), 'p50': float(np.percentile(genuine, 50)),
            'p95': float(np.percentile(genuine, 95)), 'p99': float(np.percentile(genuine, 99)),
            'max': float(genuine.max()),
        },
        'impostor_distance': {
            'mean': float(impostor.mean()), 'p0.1': p_lo, 'p1': float(np.percentile(impostor, 1)),
            'p5': p_hi, 'min': float(impostor.min()),
        },
        'eer': eer,
        'eer_threshold': eer_thr,
        'table': [
            {'threshold': float(t), 'far': float(a), 'frr': float(b)} for t, a, b in zip(grid, far, frr)
        ],
        'recommended': {
            'one_to_one': at(t_1to1),
            'acceptable_1n': at(t_1ton),
            'kyc_duplicate_hint': at(max(t_1to1, t_1ton) if (t_1to1 is not None and t_1ton is not None) else None),
            'min_margin': round(margin, 4),
            'min_margin_method': f'p{MARGIN_PCT_HIGH:g} - p{MARGIN_PCT_LOW:g} de distancias impostoras (heurística)',
        },
        'current': cur,
        'warnings': warnings,
    }


# ---------------------------------------------------------------------------
# Carga de datos
# ---------------------------------------------------------------------------
def _parse_label(value) -> int:
    s = str(value).strip().lower()
    if s in ('1', 'true', 'yes', 'si', 'sí', 'same', '1.0'):
        return 1
    if s in ('0', 'false', 'no', 'diff', 'different', '0.0'):
        return 0
    raise ValueError(f'same_person inválido: {value!r}')


def _load_embedding(cell, base_dir: str, cache: dict) -> np.ndarray:
    if isinstance(cell, (list, tuple)):
        arr = np.asarray(cell, dtype=np.float64)
    elif isinstance(cell, np.ndarray):
        arr = cell.astype(np.float64)
    else:
        text = str(cell).strip()
        if text.startswith('['):
            arr = np.asarray(json.loads(text), dtype=np.float64)
        else:
            path = text if os.path.isabs(text) else os.path.join(base_dir, text)
            if path in cache:
                arr = cache[path]
            else:
                if path.lower().endswith('.npy'):
                    arr = np.load(path).astype(np.float64)
                elif path.lower().endswith('.json'):
                    with open(path, encoding='utf-8') as fh:
                        arr = np.asarray(json.load(fh), dtype=np.float64)
                else:
                    raise ValueError(f'Formato de embedding no soportado: {text[:60]!r} (use lista JSON, .npy o .json)')
                cache[path] = arr
    arr = np.asarray(arr, dtype=np.float64).reshape(-1)
    if arr.shape[0] != EXPECTED_DIM:
        raise ValueError(f'Embedding de {arr.shape[0]} dimensiones (se esperaban {EXPECTED_DIM}).')
    return arr


def _iter_rows(path: str):
    if path.lower().endswith(('.jsonl', '.ndjson')):
        with open(path, encoding='utf-8') as fh:
            for line in fh:
                line = line.strip()
                if line:
                    yield json.loads(line)
    else:
        csv.field_size_limit(sys.maxsize)
        with open(path, newline='', encoding='utf-8') as fh:
            for row in csv.DictReader(fh):
                yield row


def load_pairs(path: str):
    """Devuelve {model_version: (distancias_genuinas, distancias_impostoras)}."""
    base_dir = os.path.dirname(os.path.abspath(path))
    cache: dict = {}
    rows_a, rows_b, labels, versions = [], [], [], []
    for n, row in enumerate(_iter_rows(path), start=1):
        try:
            rows_a.append(_load_embedding(row['embedding_a'], base_dir, cache))
            rows_b.append(_load_embedding(row['embedding_b'], base_dir, cache))
            labels.append(_parse_label(row['same_person']))
            versions.append((row.get('model_version') or '').strip().lower() or 'default')
        except (KeyError, ValueError, OSError) as exc:
            raise SystemExit(f'Fila {n}: {exc}')
    if not rows_a:
        raise SystemExit('El archivo no contiene pares.')
    dist = cosine_distances(np.vstack(rows_a), np.vstack(rows_b))
    labels = np.asarray(labels)
    versions = np.asarray(versions)
    out = {}
    for v in sorted(set(versions.tolist())):
        mask = versions == v
        out[v] = (dist[mask & (labels == 1)], dist[mask & (labels == 0)])
    return out


# ---------------------------------------------------------------------------
# Presentación
# ---------------------------------------------------------------------------
def _pct(x: float) -> str:
    return f'{x * 100:8.4f}%'


def print_report(version: str, res: dict):
    print('=' * 78)
    print(f'MODELO: {version}   pares genuinos={res["n_genuine"]}  impostores={res["n_impostor"]}')
    g, i = res['genuine_distance'], res['impostor_distance']
    print(f'Distancia genuina : media={g["mean"]:.4f} p50={g["p50"]:.4f} p95={g["p95"]:.4f} p99={g["p99"]:.4f} max={g["max"]:.4f}')
    print(f'Distancia impostora: media={i["mean"]:.4f} min={i["min"]:.4f} p0.1={i["p0.1"]:.4f} p1={i["p1"]:.4f} p5={i["p5"]:.4f}')
    print('-' * 78)
    print(f'{"umbral":>8} | {"FAR (falsos aceptados)":>24} | {"FRR (falsos rechazos)":>24}')
    for row in res['table']:
        print(f'{row["threshold"]:8.3f} | {_pct(row["far"]):>24} | {_pct(row["frr"]):>24}')
    print('-' * 78)
    print(f'EER = {res["eer"] * 100:.4f}%  (umbral ~ {res["eer_threshold"]:.4f})')
    rec, cur = res['recommended'], res['current']
    print('\nRECOMENDACIÓN vs ACTUAL')
    print(f'{"parámetro":<16}{"recomendado":>14}{"FAR rec.":>12}{"FRR rec.":>12} | {"actual":>8}{"FAR act.":>12}{"FRR act.":>12}')

    def line(label, r, c):
        rt = f'{r["threshold"]:.3f}' if r else 'n/d'
        rf = f'{r["far"] * 100:.4f}%' if r else '-'
        rr = f'{r["frr"] * 100:.4f}%' if r else '-'
        print(f'{label:<16}{rt:>14}{rf:>12}{rr:>12} | {c["threshold"]:>8.3f}{c["far"] * 100:>11.4f}%{c["frr"] * 100:>11.4f}%')

    line('one_to_one', rec['one_to_one'], cur['one_to_one'])
    line('acceptable_1n', rec['acceptable_1n'], cur['acceptable_1n'])
    line('kyc_duplicate', rec['kyc_duplicate_hint'], cur['kyc_duplicate'])
    print(f'{"min_margin":<16}{rec["min_margin"]:>14.3f}{"":>24} | {cur["min_margin"]["value"]:>8.3f}')
    print(f'  (min_margin: {rec["min_margin_method"]})')
    print('  (kyc_duplicate: debe ser >= acceptable_1n y one_to_one para no dejar pasar identidades que sí harían login)')
    print('  (perfect: FAR/FRR actual en la fila "perfect" -> {:.4f}% / {:.4f}%)'.format(
        cur['perfect']['far'] * 100, cur['perfect']['frr'] * 100))
    for w in res['warnings']:
        print(f'  ! {w}')
    print()


# ---------------------------------------------------------------------------
# Self-test (datos sintéticos)
# ---------------------------------------------------------------------------
def _unit(x):
    return x / np.linalg.norm(x, axis=-1, keepdims=True)


def synthetic_pairs(seed=7, n_ids=300, noise=0.4, n_genuine=3000, n_impostor=30000):
    """
    Identidades = puntos aleatorios en S^511. Una captura = normalize(centro + ruido N(0, noise²/512 · I)).
    Distancia genuina esperada ≈ noise² / (1 + noise²); impostora ≈ 1 ± 1/sqrt(512).
    Devuelve (emb_a, emb_b, same_person, expected_genuine_mean).
    """
    rng = np.random.default_rng(seed)
    centers = _unit(rng.standard_normal((n_ids, EXPECTED_DIM)))

    def capture(idx):
        return _unit(centers[idx] + rng.standard_normal((len(idx), EXPECTED_DIM)) * (noise / math.sqrt(EXPECTED_DIM)))

    gi = rng.integers(0, n_ids, n_genuine)
    ia = rng.integers(0, n_ids, n_impostor)
    ib = (ia + rng.integers(1, n_ids, n_impostor)) % n_ids  # siempre otra identidad
    a = np.vstack([capture(gi), capture(ia)])
    b = np.vstack([capture(gi), capture(ib)])
    same = np.concatenate([np.ones(n_genuine, dtype=int), np.zeros(n_impostor, dtype=int)])
    return a, b, same, noise ** 2 / (1 + noise ** 2)


def run_self_test(as_json=False) -> int:
    failures = []

    def check(name, cond, extra=''):
        print(('PASS ' if cond else 'FAIL ') + name + (f'  -> {extra}' if extra and not cond else ''))
        if not cond:
            failures.append(name)

    # 1. Distancia coseno vs implementación en python puro
    rng = np.random.default_rng(1)
    x, y = rng.standard_normal((5, 16)), rng.standard_normal((5, 16))
    ref = []
    for u, v in zip(x, y):
        dot = sum(p * q for p, q in zip(u, v))
        ref.append(1 - dot / (math.sqrt(sum(p * p for p in u)) * math.sqrt(sum(q * q for q in v))))
    check('cosine_distances coincide con python puro', np.allclose(cosine_distances(x, y), ref, atol=1e-12))
    check('distancia de un vector consigo mismo = 0', np.allclose(cosine_distances(x, x), 0.0, atol=1e-12))
    check('distancia con el opuesto = 2', np.allclose(cosine_distances(x, -x), 2.0, atol=1e-12))

    # 2. FAR/FRR/EER con un caso a mano
    gen = np.array([0.1, 0.2, 0.3, 0.4])
    imp = np.array([0.35, 0.5, 0.6, 0.9])
    far, frr = far_frr(gen, imp, np.array([0.05, 0.3, 0.35, 0.95]))
    check('FAR a mano', np.allclose(far, [0, 0, 0.25, 1.0]), str(far))
    check('FRR a mano', np.allclose(frr, [1.0, 0.25, 0.25, 0.0]), str(frr))
    eer, _ = compute_eer(gen, imp)
    check('EER a mano = 25%', abs(eer - 0.25) < 1e-9, str(eer))
    check('max_threshold_for_far (FAR<=25%) deja pasar a lo sumo 1 impostor',
          max_threshold_for_far(imp, 0.25, 0.05, 0.95) == 0.5 - 0.001 or max_threshold_for_far(imp, 0.25, 0.05, 0.95) == 0.499,
          str(max_threshold_for_far(imp, 0.25, 0.05, 0.95)))

    # 3. Datos sintéticos en S^511
    a, b, same, expected_gen = synthetic_pairs()
    dist = cosine_distances(a, b)
    g, i = dist[same == 1], dist[same == 0]
    check('norma ~1 (puntos sobre S^511)', abs(np.linalg.norm(a[0]) - 1.0) < 1e-9)
    check('distancia genuina media ≈ teórica (±0.02)', abs(g.mean() - expected_gen) < 0.02,
          f'{g.mean():.4f} vs {expected_gen:.4f}')
    check('distancia impostora media ≈ 1.0 (±0.01)', abs(i.mean() - 1.0) < 0.01, f'{i.mean():.4f}')
    check('sigma impostora ≈ 1/sqrt(512)=0.0442 (±0.01)', abs(i.std() - 1 / math.sqrt(512)) < 0.01, f'{i.std():.4f}')

    res = analyze(g, i, 0.05, 0.60, 0.01, CURRENT_THRESHOLDS)
    fars = [r['far'] for r in res['table']]
    frrs = [r['frr'] for r in res['table']]
    check('FAR no decreciente y FRR no creciente', all(x2 >= x1 for x1, x2 in zip(fars, fars[1:]))
          and all(y2 <= y1 for y1, y2 in zip(frrs, frrs[1:])))
    check('FAR(0.60) = 0 con modelo bien separado', fars[-1] == 0.0, str(fars[-1]))
    check('FRR(0.05) alto y FRR(0.60) = 0', frrs[0] > 0.9 and frrs[-1] == 0.0, f'{frrs[0]}, {frrs[-1]}')
    check('EER ≈ 0 en datos bien separados', res['eer'] < 0.001, str(res['eer']))
    rec = res['recommended']
    check('1:1 recomendado cumple FAR<=0.1%', rec['one_to_one'] and rec['one_to_one']['far'] <= FAR_TARGET_1TO1)
    check('1:N recomendado cumple FAR<=0.01%', rec['acceptable_1n'] and rec['acceptable_1n']['far'] <= FAR_TARGET_1TON)
    check('1:N <= 1:1 (más estricto)', rec['acceptable_1n']['threshold'] <= rec['one_to_one']['threshold'])
    check('min_margin sugerido en rango razonable (0.02..0.15)', 0.02 <= rec['min_margin'] <= 0.15, str(rec['min_margin']))

    # Caso con solapamiento (noise alto) -> EER > 0 y umbral recomendado dentro de rango
    a2, b2, same2, _ = synthetic_pairs(seed=3, noise=3.0, n_genuine=3000, n_impostor=30000)
    d2 = cosine_distances(a2, b2)
    res2 = analyze(d2[same2 == 1], d2[same2 == 0], 0.05, 0.60, 0.01, CURRENT_THRESHOLDS)
    check('con ruido alto el EER es > 0', res2['eer'] > 0.001, str(res2['eer']))
    t1 = res2['recommended']['one_to_one']
    check('con ruido alto el 1:1 recomendado cumple FAR<=0.1%', t1 is None or t1['far'] <= FAR_TARGET_1TO1)

    # 4. Carga de datos: CSV (listas JSON), JSONL, .npy y .json
    with tempfile.TemporaryDirectory(prefix='calib_') as tmp:
        n = 40
        sel = list(range(n // 2)) + list(range(3000, 3000 + n // 2))
        np.save(os.path.join(tmp, 'a0.npy'), a[sel[0]])
        with open(os.path.join(tmp, 'b0.json'), 'w', encoding='utf-8') as fh:
            json.dump(b[sel[0]].tolist(), fh)
        csv_path = os.path.join(tmp, 'pairs.csv')
        with open(csv_path, 'w', newline='', encoding='utf-8') as fh:
            w = csv.writer(fh)
            w.writerow(['embedding_a', 'embedding_b', 'same_person', 'model_version'])
            w.writerow(['a0.npy', 'b0.json', 1, 'mobilefacenet-int8-v1'])
            for k in sel[1:]:
                w.writerow([json.dumps(a[k].tolist()), json.dumps(b[k].tolist()), int(same[k]), 'mobilefacenet-fp32-v1'])
        loaded = load_pairs(csv_path)
        check('CSV: agrupa por model_version', set(loaded) == {'mobilefacenet-int8-v1', 'mobilefacenet-fp32-v1'})
        check('CSV: .npy/.json cargados correctamente',
              np.allclose(loaded['mobilefacenet-int8-v1'][0], [dist[sel[0]]], atol=1e-9))
        fp = loaded['mobilefacenet-fp32-v1']
        check('CSV: conteos genuinos/impostores', len(fp[0]) == n // 2 - 1 and len(fp[1]) == n // 2,
              f'{len(fp[0])}/{len(fp[1])}')
        jl_path = os.path.join(tmp, 'pairs.jsonl')
        with open(jl_path, 'w', encoding='utf-8') as fh:
            for k in sel:
                fh.write(json.dumps({'embedding_a': a[k].tolist(), 'embedding_b': b[k].tolist(),
                                     'same_person': bool(same[k])}) + '\n')
        jl = load_pairs(jl_path)['default']
        check('JSONL: distancias idénticas a las calculadas',
              np.allclose(np.sort(np.concatenate(jl)), np.sort(dist[sel]), atol=1e-9))

    if as_json:
        print(json.dumps({'self_test': 'FAIL' if failures else 'PASS', 'failures': failures}))
    print(f'\nSELF-TEST: {"FALLÓ" if failures else "OK"} ({len(failures)} fallos)')
    print('Nota: datos sintéticos; esto valida el cálculo, NO sustituye un set real de pares de personas.')
    return 1 if failures else 0


# ---------------------------------------------------------------------------
def main(argv=None) -> int:
    p = argparse.ArgumentParser(description='Calibra umbrales de distancia coseno biométrica (FAR/FRR/EER).')
    p.add_argument('input', nargs='?', help='CSV o JSONL con pares etiquetados')
    p.add_argument('--model-version', help='Analizar solo esta versión de modelo (columna model_version)')
    p.add_argument('--min', dest='lo', type=float, default=0.05)
    p.add_argument('--max', dest='hi', type=float, default=0.60)
    p.add_argument('--step', type=float, default=0.01)
    p.add_argument('--json', action='store_true', help='Además de la tabla, imprime un JSON con los resultados')
    p.add_argument('--json-only', action='store_true', help='Solo JSON (sin tabla)')
    p.add_argument('--self-test', action='store_true', help='Valida el cálculo con datos sintéticos (S^511)')
    for key, val in CURRENT_THRESHOLDS.items():
        p.add_argument(f'--current-{key.replace("_", "-")}', type=float, default=val,
                       help=f'Umbral vigente de {key} (default {val})')
    args = p.parse_args(argv)

    if args.self_test:
        return run_self_test(as_json=args.json or args.json_only)
    if not args.input:
        p.error('Indique el archivo de pares o use --self-test')
    if not (0 <= args.lo < args.hi <= 2 and args.step > 0):
        p.error('Rango de umbrales inválido')

    current = {k: getattr(args, f'current_{k}') for k in CURRENT_THRESHOLDS}
    groups = load_pairs(args.input)
    if args.model_version:
        key = args.model_version.strip().lower()
        if key not in groups:
            raise SystemExit(f'model_version {key!r} no encontrado. Disponibles: {", ".join(sorted(groups))}')
        groups = {key: groups[key]}

    results = {}
    for version, (gen, imp) in groups.items():
        try:
            results[version] = analyze(gen, imp, args.lo, args.hi, args.step, current)
        except ValueError as exc:
            raise SystemExit(f'[{version}] {exc}')
        if not args.json_only:
            print_report(version, results[version])
    if args.json or args.json_only:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
