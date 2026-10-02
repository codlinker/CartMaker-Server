"""Léxico comercial venezolano para matching de compras (no es un recetario duro)."""

import re
from typing import Iterable, List, Set

SEARCH_STOPWORDS = {
    'a', 'al', 'algo', 'algun', 'algún', 'alguna', 'alguno', 'allá', 'alla',
    'buscar', 'compra', 'comprar', 'con', 'consigue', 'conseguir', 'cocinar',
    'de', 'del', 'el', 'en', 'esta', 'está', 'esto', 'hacer', 'hoy', 'la',
    'las', 'lo', 'los', 'me', 'mi', 'necesito', 'o', 'para', 'por', 'que',
    'qué', 'quiero', 'se', 'si', 'sin', 'un', 'una', 'unas', 'unos', 'y',
    'ya', 'yo',
}

# Cada grupo se trata como equivalentes al filtrar inventario.
SYNONYM_GROUPS: List[List[str]] = [
    ['caraota', 'caraotas', 'frijol negro', 'frijoles negros', 'habichuela negra', 'poroto negro'],
    ['caraota palo', 'frijol palo', 'frijoles palo'],
    ['platano', 'plátano', 'platano maduro', 'plátano maduro', 'tajadas'],
    ['platano verde', 'plátano verde', 'verde'],
    ['harina pan', 'harina de maiz', 'harina de maíz', 'harina precocida', 'harina de cachapa'],
    ['papelon', 'papelón', 'panela', 'dulce de papelón'],
    ['queso blanco', 'queso de mano', 'queso llanero', 'queso telita'],
    ['queso guayanes', 'queso guayanés'],
    ['carne mechada', 'carne desmechada', 'pabellon', 'pabellón'],
    ['pollo', 'pechuga', 'muslo de pollo', 'pollo entero'],
    ['res', 'carne de res', 'bistec', 'asado', 'lagarto'],
    ['cerdo', 'cochino', 'chuleta', 'pernil'],
    ['chorizo', 'chorizo criollo'],
    ['mortadela', 'jamonada'],
    ['jamon', 'jamón'],
    ['arepa', 'masa de arepa'],
    ['empanada', 'empanadas'],
    ['cachapa', 'cachapas'],
    ['hallaca', 'hallacas', 'hayaca', 'hayacas'],
    ['pan de jamon', 'pan de jamón'],
    ['tequeño', 'tequeños'],
    ['golfeado', 'golfeados'],
    ['casabe', 'casabé'],
    ['yuca', 'mandioca'],
    ['ocumo', 'ocumo chino'],
    ['auyama', 'calabaza', 'zapallo'],
    ['ajo', 'ajos', 'diente de ajo'],
    ['cebolla', 'cebollas', 'cebolla morada'],
    ['ajicero', 'ají', 'aji dulce', 'ají dulce', 'pimenton', 'pimentón', 'pimiento'],
    ['cilantro', 'culantro'],
    ['onoto', 'achiote'],
    ['tomate', 'tomates', 'jitomate'],
    ['limon', 'limón', 'limones'],
    ['naranja', 'naranjas'],
    ['cambur', 'banana', 'banano', 'guineo'],
    ['lechoza', 'papaya'],
    ['patilla', 'sandia', 'sandía'],
    ['guayaba', 'guayabas'],
    ['leche', 'leche completa', 'leche entera'],
    ['nata', 'crema de leche'],
    ['huevo', 'huevos'],
    ['arroz', 'arroz blanco'],
    ['pasta', 'espagueti', 'spaguetti', 'spaghetti', 'codito', 'coditos'],
    ['aceite', 'aceite vegetal', 'aceite de soya', 'aceite de maíz'],
    ['azucar', 'azúcar'],
    ['sal', 'sal de cocina'],
    ['cafe', 'café', 'cafe molido'],
    ['cacao', 'cocoa'],
    ['malta', 'maltin', 'maltín'],
    ['refresco', 'gaseosa', 'soda'],
    ['jugo', 'nectar', 'néctar'],
    ['agua', 'botella de agua'],
    ['cerveza', 'birra'],
    ['pan', 'pan canilla', 'canilla', 'pan campesino'],
    ['galleta', 'galletas', 'galleta soda'],
    ['chucheria', 'chuchería', 'snack', 'snacks', 'golosina', 'golosinas'],
    ['detergente', 'jabon en polvo', 'jabón en polvo'],
    ['jabon', 'jabón', 'jabon de baño'],
    ['cloro', 'lavandina', 'hipoclorito'],
    ['papel toilet', 'papel higienico', 'papel higiénico'],
    ['pañales', 'panales', 'pampers'],
    ['toallas sanitarias', 'toallas higienicas'],
    ['gas', 'bombona', 'bombona de gas'],
    ['hielo', 'bolsa de hielo'],
    ['charcuteria', 'charcutería', 'fiambre', 'embutido'],
    ['pescado', 'lisa', 'pargo', 'dorado', 'atun', 'atún'],
    ['camarones', 'camaron', 'camarón'],
    ['sardina', 'sardinas'],
    ['atun en lata', 'atún en lata'],
    ['mayonesa', 'mayo'],
    ['ketchup', 'catsup', 'salsa de tomate'],
    ['mostaza', 'mostaza amarilla'],
    ['vinagre', 'vinagre blanco'],
    ['mantequilla', 'margarina'],
    ['queso crema', 'queso philadelphia'],
    ['yogurt', 'yogur', 'yoghurt'],
    ['helado', 'ice cream'],
    ['pizza', 'pizza familiar'],
    ['hamburguesa', 'burger', 'hamburguesas'],
    ['perro caliente', 'hot dog', 'perro'],
    ['arepa rellena', 'pepito'],
    ['almuerzo', 'menu ejecutivo', 'menú ejecutivo', 'menu del dia'],
    ['desayuno', 'desayunos'],
    ['empanada de pabellon', 'empanada pabellón'],
    ['sillon', 'sillón', 'sofa', 'sofá', 'sofa cama'],
    ['repisa', 'estante', 'estanteria', 'estantería'],
    ['nevera', 'refrigerador', 'heladera'],
    ['lavadora', 'lavarropas'],
    ['aire acondicionado', 'split', 'aire'],
    ['ventilador', 'abanico'],
    ['telefono', 'teléfono', 'celular', 'movil', 'móvil'],
    ['cargador', 'cable usb'],
    ['audifonos', 'audífonos', 'cornetas', 'auriculares'],
]


def _fold(text: str) -> str:
    if not text:
        return ''
    replacements = (
        ('á', 'a'), ('é', 'e'), ('í', 'i'), ('ó', 'o'), ('ú', 'u'),
        ('ü', 'u'), ('ñ', 'n'),
    )
    folded = text.lower().strip()
    for src, dst in replacements:
        folded = folded.replace(src, dst)
    return folded


def _build_synonym_index():
    index = {}
    for group in SYNONYM_GROUPS:
        folded_group = [_fold(term) for term in group]
        unique_group = list(dict.fromkeys(folded_group))
        for term in unique_group:
            index.setdefault(term, set()).update(unique_group)
    return index


_SYNONYM_INDEX = _build_synonym_index()


def tokenize_query(query: str) -> List[str]:
    folded = _fold(query)
    raw_tokens = [tok for tok in re.split(r'[^a-z0-9]+', folded) if tok]
    tokens = []
    for tok in raw_tokens:
        if tok in SEARCH_STOPWORDS or len(tok) < 2:
            continue
        tokens.append(tok)
        if len(tok) > 4 and tok.endswith('s'):
            tokens.append(tok[:-1])
        elif len(tok) > 3 and not tok.endswith('s'):
            tokens.append(tok + 's')
    # unique preserve order
    seen = set()
    ordered = []
    for tok in tokens:
        if tok not in seen:
            seen.add(tok)
            ordered.append(tok)
    return ordered


def expand_search_variants(query: str) -> List[str]:
    """Devuelve frases a buscar en nombre/descripcion (query original + sinónimos)."""
    folded = _fold(query)
    variants: List[str] = []
    if query and query.strip():
        variants.append(query.strip())
    if folded and folded not in {_fold(v) for v in variants}:
        variants.append(folded)

    tokens = tokenize_query(query)
    for token in tokens:
        if token not in {_fold(v) for v in variants}:
            variants.append(token)
        for syn in sorted(_SYNONYM_INDEX.get(token, [])):
            if syn not in {_fold(v) for v in variants}:
                variants.append(syn)

    # Frases multi-palabra del léxico si el query las contiene
    for phrase, related in _SYNONYM_INDEX.items():
        if ' ' in phrase and phrase in folded:
            for syn in related:
                if syn not in {_fold(v) for v in variants}:
                    variants.append(syn)

    # Limitar explosión
    return variants[:18]


def significant_tokens(query: str) -> List[str]:
    return [tok for tok in tokenize_query(query) if len(tok) >= 3]


# Términos de esta longitud o menos ('res', 'pan', 'sal', 'gas', 'te') solo
# deben coincidir como palabra aislada, nunca como subcadena ('refresco', 'empanada', 'salsa').
SHORT_TERM_MAX_LEN = 4


def is_short_term(term: str) -> bool:
    """True si el término es lo bastante corto como para exigir límite de palabra."""
    return len((term or '').strip()) <= SHORT_TERM_MAX_LEN


def word_boundary_regex(term: str) -> str:
    """Regex POSIX (PostgreSQL ARE) con límite de palabra `\\y` para usar con `__iregex`."""
    return r'\y' + re.escape((term or '').strip()) + r'\y'


def lexical_match(texts: Iterable[str], variants: Iterable[str]) -> bool:
    """
    Coincidencia léxica directa en memoria, espejo del filtro SQL:
    variantes cortas -> palabra aislada; variantes largas -> subcadena.
    """
    folded_texts = [_fold(text) for text in texts if text]
    if not folded_texts:
        return False
    for variant in variants:
        folded_variant = _fold(variant)
        if len(folded_variant) < 2:
            continue
        if is_short_term(folded_variant):
            pattern = re.compile(r'\b' + re.escape(folded_variant) + r'\b')
            if any(pattern.search(text) for text in folded_texts):
                return True
        elif any(folded_variant in text for text in folded_texts):
            return True
    return False
