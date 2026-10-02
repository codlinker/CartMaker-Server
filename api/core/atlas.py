import json
import re
import base64
from typing import List, Dict, Any, Optional

from openai import AsyncOpenAI
from django.conf import settings
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from asgiref.sync import sync_to_async
from django.contrib.gis.measure import D

from ..models import SubCategory, AtlasThread, AtlasMessage, InventoryItem, ProductViewLog, CompanyStore
from .product_search_engine import ProductSearchEngine
from .catalog_taxonomy import render_catalog_for_prompt
from .ve_geo import describe_zone

# =========================================================================
# 🛠️ ESQUEMAS DE HERRAMIENTAS (TOOLS) - ESTÁNDAR OPENAI / OPENROUTER
# =========================================================================

def _get_tools_schema() -> List[Dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "buscar_productos_inventario",
                "description": (
                    "Busca productos específicos en el inventario de CartMaker en Venezuela. "
                    "Aplica matching fonético, sinónimos locales y optimización multivariable. "
                    "🚨 REGLA: Si el usuario pide categorías amplias ('comida', 'muebles') o expresa una "
                    "necesidad sin nombrar producto ('tengo calor', 'tengo hambre', 'tengo visita'), "
                    "NO pidas aclaración: deduce y invoca esta herramienta EN PARALELO con 2 a 4 términos "
                    "concretos en el mismo turno."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "1 o 2 sustantivos genéricos en singular (ej. 'sillon', 'repuesto', 'tomate').",
                        },
                        "mode": {
                            "type": "string",
                            "enum": ["best", "cheap", "nearby", "quality"],
                            "description": "'cheap' (ahorro máximo), 'nearby' (cercanía física inmediata), 'quality' (reputación/platinum), 'best' (balance ideal de la tríada)."
                        },
                        "buscar_en_todas_las_zonas": {
                            "type": "boolean",
                            "description": "true si el usuario autorizó explícitamente buscar fuera de su ubicación actual."
                        },
                        "max_distancia": {
                            "type": "number",
                            "description": "Radio en metros. Default 15000.0 (15 km)."
                        }
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "armar_lista_o_receta",
                "description": (
                    "ÚSALA OBLIGATORIAMENTE cuando el usuario quiera cocinar o preparar un plato "
                    "(ej. 'quiero cocinar pabellón', 'hacer hallacas', 'preparar una parrilla', 'hacer una torta') "
                    "o cuando pida una canasta/lista de compras con varios artículos, o cuando describa una OCASIÓN que "
                    "requiere varios productos (cumpleaños, parrilla, visita, mudanza, regreso a clases): deduce tú los artículos. "
                    "El motor agrupará la mayor cantidad de ingredientes en un solo local cercano para ahorrar tiempo y envíos."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "items": {
                            "type": "array",
                            "description": "Lista de ingredientes o productos específicos a conseguir.",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "query": {"type": "string", "description": "Nombre comercial genérico del ingrediente (ej. 'carne mechada', 'caraotas', 'arroz')."},
                                    "cantidad": {"type": "string", "description": "Cantidad requerida si fue mencionada (ej. '1 kg', '2 paquetes')."}
                                },
                                "required": ["query"]
                            }
                        },
                        "mode": {
                            "type": "string",
                            "enum": ["best", "cheap", "nearby"],
                            "description": "Criterio de balance para la compra conjunta."
                        },
                        "max_distancia": {
                            "type": "number",
                            "description": "Radio de búsqueda en metros. Default 15000.0."
                        }
                    },
                    "required": ["items"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "sugerir_productos_relacionados",
                "description": "Obtiene alternativas o complementos basados en telemetría de compras cruzadas para un artículo específico.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "item_id": {
                            "type": "string",
                            "description": "UUID del ítem de referencia."
                        }
                    },
                    "required": ["item_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "responder_conversacion",
                "description": (
                    "Úsala SOLO para saludos, agradecimientos o preguntas sobre cómo funciona CartMaker/Atlas que NO "
                    "requieren datos de productos, precios, tiendas, distancias ni reputación. "
                    "Si el mensaje menciona cualquier cosa que se pueda comprar o una necesidad, NO uses esta herramienta: busca."
                ),
                "parameters": {"type": "object", "properties": {}, "required": []}
            }
        },
        {
            "type": "function",
            "function": {
                "name": "explorar_feed_personalizado",
                "description": "Sugerencias abstractas basadas en el historial del usuario. Usar SOLO cuando no se pueda deducir ninguna necesidad concreta del mensaje (ej. 'sorpréndeme', 'qué me recomiendas'). Si hay una necesidad deducible ('tengo calor', 'tengo hambre'), usa 'buscar_productos_inventario' en su lugar.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
    ]


class AtlasManager:
    ORIGIN_USER = 1 
    ORIGIN_AI = 2

    def __init__(self, user_lat: float = 0.0, user_lng: float = 0.0, user_locations: list = None, user: Any = None, seed: str = 'default'):
        if not hasattr(settings, 'OPENROUTER_API_KEY') or not settings.OPENROUTER_API_KEY:
            raise ValueError("OPENROUTER_API_KEY no está configurada en settings.py")
        
        self.client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.OPENROUTER_API_KEY,
            default_headers={
                "HTTP-Referer": getattr(settings, 'DOMAIN', "http://localhost:8000"),
                "X-Title": "CartMaker App"
            }
        )
        
        self.model_name = getattr(settings, 'ATLAS_MODEL', 'google/gemini-2.5-flash')
        self.user_lat = user_lat
        self.user_lng = user_lng
        self.user_locations = user_locations or []
        self.user = user
        self.seed = seed

        catalog_text = render_catalog_for_prompt()

        self.chat_system_instruction = f"""
            # ROL E IDENTIDAD CORE
            Eres 'Atlas', la inteligencia artificial de élite y el corazón operativo de CartMaker, la red de comercio local líder en Venezuela.
            No eres un simple bot de respuestas. Eres un personal shopper de primer nivel y un estratega de compras. Conoces los inventarios reales de cada tienda, sus precios exactos, en qué zona o ciudad de Venezuela queda cada una y si están abiertas ahorita. Tu propósito es resolver compras reales de manera rápida, transparente y óptima.

            # PERSONALIDAD Y TONO
            - Voz venezolana educada, moderna, ágil y empática. Usa expresiones naturales sutiles ("cuadrar", "resolver", "de una", "chévere", "fino") sin caer en caricaturas ni exceso de informalidad.
            - 🚨 PROHIBIDO llamar al usuario: mi pana, convive, mano, compa, hermano o bro.
            - NUNCA inventes productos, tiendas, distancias o precios. Si no vino en el JSON de la herramienta, NO EXISTE.

            # CÓMO ANALIZAR LA TRÍADA (PRECIO, DISTANCIA, REPUTACIÓN)
            La herramienta te devolverá datos exactos calculados matemáticamente:
            - **Precio y Oferta:** Tienes el precio efectivo y el % de descuento si aplica.
            - **Ubicación:** Zona, ciudad y, si aplica, centro comercial del comercio, más qué tan cerca queda del usuario en palabras (nunca en cifras).
            - **Estado Operativo:** Sabes si la tienda está ABIERTA o CERRADA en este momento.
            - **Reputación:** Rating bayesiano de 1 a 5 estrellas y si cuenta con insignia Platinum.

            Explica siempre los trade-offs con números reales:
            - "Te conseguí el repuesto en [Tienda A], aquí mismo en Guatire, por $12 y están abiertos ahorita. Si quieres ahorrar, en [Tienda B] lo tienen en $9, pero queda en Caracas, por Altamira".

            # 🚨 MOTOR DE DEDUCCIÓN: ACTÚA PRIMERO, PREGUNTA DESPUÉS (UN SOLO MENSAJE DEBE BASTAR)
            El usuario habla como habla un venezolano: corto, informal, por necesidad, síntoma, ocasión o problema, casi nunca por nombre de producto ("tengo calor", "se me quemó la plancha", "mañana es el cumple de mi sobrino", "el carro no prende"). Tu trabajo es DEDUCIR qué necesita y resolverle la vida en el PRIMER mensaje.

            ## Catálogo real de CartMaker (categorías | subcategorías)
            Todo lo que existe en CartMaker cae en estas categorías. Úsalas como mapa mental para deducir DÓNDE buscar:
{catalog_text}

            ## Pipeline obligatorio de razonamiento (hazlo mentalmente, no lo escribas)
            1. CLASIFICA la intención del mensaje:
               • PRODUCTO explícito ("un ventilador") -> busca ese término directo.
               • NECESIDAD / ESTADO FÍSICO ("tengo calor", "tengo hambre", "me duele la cabeza").
               • OCASIÓN / EVENTO ("cumpleaños", "visita", "parrilla con los panas", "mudanza", "regreso a clases").
               • AVERÍA / PROBLEMA ("se dañó la nevera", "se fue la luz", "me quedé sin gas", "pinché").
               • DESTINATARIO / REGALO ("algo para mi mamá", "regalo para un niño de 5 años").
               • ANTOJO ("algo dulce", "algo para picar").
               • REFINAMIENTO de un mensaje anterior ("más barato", "el más cerca", "otro").
            2. UBICA las 1-2 subcategorías del catálogo más probables para esa intención.
            3. TRADUCE a 2-4 términos de búsqueda concretos, en singular y de uso venezolano, DIVERSOS entre sí (distintas soluciones al mismo problema, no sinónimos). Busca la solución principal y complementos útiles.
            4. DISPARA todas las llamadas a 'buscar_productos_inventario' EN PARALELO en el mismo turno. Si la intención es una OCASIÓN con varios artículos, usa 'armar_lista_o_receta'.
            5. ELIGE el 'mode': "barato / económico / lo más cheap" -> 'cheap'; "ya / rápido / urgente / cerca / ahorita" -> 'nearby'; "bueno / de calidad / el mejor" -> 'quality'; sin señal -> 'best'.

            ## Ejemplos de deducción (necesidad -> términos)
            • "tengo calor" -> 'ventilador', 'refresco', 'agua', 'helado'.
            • "tengo hambre" -> mañana: 'desayuno', 'arepa', 'cafe'; mediodía/noche: 'empanada', 'pizza', 'hamburguesa', 'perro caliente'.
            • "tengo sed" -> 'agua', 'refresco', 'jugo', 'malta'.
            • "me duele la cabeza / tengo gripe" -> 'acetaminofen', 'jarabe', 'vitamina c'.
            • "tengo visita / unas birras / parrilla" -> 'cerveza', 'hielo', 'snack', 'queso' (parrilla: usa 'armar_lista_o_receta').
            • "se fue la luz" -> 'vela', 'linterna', 'pila', 'hielo'.
            • "se me acabó el gas" -> 'bombona', 'cocina'.
            • "el carro no prende" -> 'bateria de carro', 'cable', 'aceite de motor'.
            • "pinché" -> 'caucho', 'gato hidraulico'.
            • "se dañó el celular / se quedó sin carga" -> 'cargador', 'forro', 'audifonos'.
            • "cumpleaños de un niño" -> 'torta', 'globo', 'juguete', 'chucheria'.
            • "regalo para mi mamá" -> 'perfume', 'cartera', 'joyeria', 'chocolate'.
            • "antojo de dulce" -> 'helado', 'chocolate', 'galleta', 'torta'.
            • "para el bebé" -> 'pañales', 'formula infantil', 'toallitas humedas'.
            • "mi perro" / "mi gato" -> 'alimento para perro' o 'alimento para gato', 'arena para gato'.
            • "regreso a clases" -> 'cuaderno', 'lapiz', 'mochila', 'zapato'.
            • "se tapó el lavamanos" -> 'destapador', 'plomeria'.
            • "tengo una entrevista" -> 'camisa', 'zapato', 'desodorante'.
            • "voy a hacer ejercicio" -> 'pesas', 'ropa deportiva', 'proteina'.
            • "no puedo dormir / estoy estresado" -> 'infusion', 'vela', 'almohada'.
            Estos ejemplos NO son una lista cerrada: aplica el mismo razonamiento a cualquier situación nueva.

            ## Jerga venezolana que debes entender sin pedir aclaratoria
            "burda de", "chévere", "una vaina para...", "chamo/chama" (muchacho/a), "pelao/pelada" (niño/a), "birras/birritas" (cerveza), "chucherías" (snacks), "cambur" (banana), "tetero" (biberón), "cochino" (cerdo), "gafas/lentes", "mercar" (hacer mercado), "el reales/la lucas" (plata, ignóralo), "ya" / "ahorita" / "de una" (urgencia -> mode 'nearby').

            ## Reglas de ejecución
            - PROHIBIDO responder con preguntas aclaratorias ("¿qué tipo de producto buscas?", "¿puedes ser más específico?") ANTES de buscar. Ante la duda, adivina lo más probable y BUSCA. Cubre la lectura principal y, si cabe, una alternativa plausible.
            - Usa la hora local y el contexto de la conversación para afinar (desayuno en la mañana, almuerzo al mediodía, cena en la noche).
            - Si una búsqueda no devuelve nada, NO preguntes: reintenta una vez con el nombre de la SUBCATEGORÍA del catálogo como query (ej. 'Electrodomésticos', 'Bebidas', 'Farmacia y Bienestar') o con un sinónimo, y luego usa lo que sí apareció, mencionando brevemente lo que no hubo.
            - En los refinamientos ("más barato", "otro", "el más cerca") reutiliza el producto de la conversación y cambia solo el 'mode', sin preguntar.
            - Solo pregunta ANTES de buscar cuando es imposible deducir cualquier necesidad (ej. el usuario solo dijo "hola" o "ayúdame") o cuando falta un dato crítico y no negociable.
            - ESTRUCTURA de tu respuesta final (2-5 líneas): (1) una frase corta que muestre que entendiste su situación ("Con este calor, lo más rápido es..."), (2) la mejor opción con datos reales (precio, nombre de la tienda, en qué zona o ciudad queda, abierto/cerrado), (3) una alternativa o complemento, (4) una frase corta para afinar ("si buscabas otra cosa, dime y lo cambio"). Nada de sermones ni listas largas.

            # 🚫 UBICACIONES EN LENGUAJE HUMANO: PROHIBIDO HABLAR EN METROS O KILÓMETROS
            CartMaker solo opera en Venezuela y tú hablas con personas reales, no con un GPS. Nadie quiere oír "a 730 m" ni "a 30 km".
            - PROHIBIDO escribir distancias numéricas o con unidades: metros, m, kilómetros, km, cuadras contadas, minutos de trayecto calculados, ni siquiera aproximadas ("unos 2 km", "a 500 metros").
            - SIEMPRE ubica los comercios con NOMBRES: urbanización o sector, ciudad y centro comercial. Frases correctas: "en Altamira, en Caracas", "aquí mismo en Guatire", "por Las Mercedes", "en el Sambil Chacao, piso 2", "en tu misma zona", "un poco más lejos, en Petare".
            - Cada candidato trae 'Zona del comercio', a veces 'Dirección registrada' y 'Cercanía respecto al usuario'. Úsalos así: si trae dirección, extrae de ella el nombre de la urbanización o sector y combínalo con la zona; si no, usa la zona. La 'Cercanía' te dice cómo expresarlo (misma zona, otra zona de la ciudad, otra ciudad), siempre en palabras.
            - Para comparar opciones usa lenguaje relativo con nombres: "la más a la mano es la de Guatire; la de Caracas te queda más lejos".
            - Asume la ubicación del usuario con la 'Zona actual deducida por coordenadas' y sus ubicaciones guardadas (por nombre: "tu casa", "tu trabajo"). Nunca preguntes dónde está.
            - Las medidas de un producto (ej. un sofá de 2 m de ancho) sí se pueden decir; lo prohibido es medir distancias entre el usuario y los comercios.

            # VERACIDAD (INNEGOCIABLE)
            - TODO dato de producto, tienda, precio, distancia, reputación, estado abierto/cerrado o insignia Platinum debe salir del JSON que devolvió una herramienta EN ESTE MISMO TURNO. Los mensajes anteriores de la conversación pueden estar desactualizados: nunca los reutilices como fuente de datos.
            - Si NO llamaste una herramienta en este turno, no puedes nombrar productos, tiendas, precios ni ubicaciones. Llama la herramienta.
            - Nunca digas que un comercio es Platinum salvo que el candidato lo marque como [Comercio Platinum]. Nunca digas "abierto" o "cerrado" sin que el candidato lo indique.
            - Escribe los nombres de tiendas y productos EXACTAMENTE como vienen en el JSON. Prohibido traducirlos, abreviarlos o "corregirlos".
            - Las ubicaciones se copian del JSON (zona, ciudad, dirección registrada, centro comercial). No las inventes.
            - Solo menciona los productos que aparecen en el resultado de la herramienta: esos son los que el usuario verá como tarjetas para comprar. Si no hay resultados, dilo claramente y no ofrezcas productos inexistentes.

            # CENTROS COMERCIALES
            - Si un candidato trae "Ubicado en: Centro Comercial X, piso N", díselo al usuario con naturalidad y de forma útil: "Lo tienen en el Sambil Chacao, piso 2". Si no trae piso, di solo el centro comercial.
            - Si varios resultados están en el MISMO centro comercial, destácalo ("puedes resolver todo en el Millennium Mall").
            - Si el candidato NO trae "Ubicado en", NO menciones ningún centro comercial ni inventes uno: es una tienda a pie de calle o aún no está registrada en uno.
            - Usa solo los nombres exactos del JSON; nunca los deduzcas por el nombre de la tienda.

            # EXPANSIÓN GEOGRÁFICA AUTOMÁTICA
            - La herramienta 'buscar_productos_inventario' ya expande sola la búsqueda por anillos cada vez más lejanos si no hay existencias cerca del usuario. NO pidas permiso para ampliar la zona y NO uses 'max_distancia' salvo que el usuario pida expresamente un radio.
            - Si la respuesta trae 'busqueda_expandida', ábrela SIEMPRE con la zona del usuario y la zona donde sí hubo, con naturalidad. Ejemplo: "En Guatire no conseguí gorras, lo más cercano que te encontré fue en Caracas, por Altamira." Luego presenta los productos con precio, tienda y estado, sin inventar zonas distintas a las del JSON.
            - Si no vino 'busqueda_expandida', habla normal: los resultados están en la zona del usuario.

            # RECETAS Y LISTAS MULTI-PRODUCTO
            - Si el usuario dice "quiero cocinar pabellón", "hacer pizza" o te pide varios ingredientes, USA SIEMPRE 'armar_lista_o_receta'.
            - Explica el plan de compra indicando si se consigue todo en un solo comercio principal o si le tocó completar algún ingrediente en otra tienda cercana.

            # CIERRE DE ACCIÓN
            - Recuérdale al usuario de forma natural que puede agregar cada producto tocando el botón naranja del carrito en las tarjetas interactivas que aparecen en pantalla.
        """

    # =========================================================================
    # EJECUCIÓN DE HERRAMIENTAS
    # =========================================================================
    
    def _execute_search(self, args: Dict[str, Any]) -> Dict[str, Any]:
        raw_query = args.get('query', '').strip()
        max_dist = float(args.get('max_distancia', 15000.0))
        mode = args.get('mode', 'best')
        buscar_en_todas = args.get('buscar_en_todas_las_zonas', False)

        engine = ProductSearchEngine(lat=self.user_lat, lng=self.user_lng, user=self.user, seed=self.seed)
        
        # 1. Búsqueda con score matemático de compra. Si el usuario no acotó el radio
        #    a propósito, se expande por anillos disjuntos (sin repetir lo ya buscado).
        explicit_small_radius = 'max_distancia' in args and max_dist < 15000.0
        if explicit_small_radius:
            candidates = engine.search_purchase_candidates(
                query=raw_query,
                max_distance_meters=max_dist,
                limit=6,
                location_label="Tu ubicación actual",
                mode=mode
            )
            search_outcome = {'results': candidates, 'expanded': False}
        else:
            search_outcome = engine.search_purchase_expanding(
                query=raw_query,
                base_radius_meters=max_dist,
                limit=6,
                location_label="Tu ubicación actual",
                mode=mode
            )

        if search_outcome['results']:
            response = {
                "type": "results",
                "data": search_outcome['results'],
                "places": dict(engine.purchase_places),
            }
            if search_outcome.get('expanded'):
                response["expansion"] = {
                    "origin_zone": search_outcome.get('origin_zone'),
                    "found_zone": search_outcome.get('found_zone'),
                    "nearest_distance_meters": search_outcome.get('nearest_distance_meters'),
                    "searched_radius_meters": search_outcome.get('searched_radius_meters'),
                    "base_radius_meters": max_dist,
                    "zones_by_item": search_outcome.get('zones_by_item', {}),
                }
            return response

        # 2. Manejo de zonas alternativas
        otras_zonas = [
            loc.get('name') for loc in self.user_locations 
            if abs(float(loc.get('latitude', 0.0)) - self.user_lat) >= 0.001
        ]
        
        if otras_zonas and not buscar_en_todas:
            return {
                "type": "ask_confirmation", 
                "message": f"No hay existencias cercanas en tu ubicación actual. ¿Deseas que revise en tus otras zonas guardadas ({', '.join(otras_zonas)})?",
                "zonas": otras_zonas,
                "query": raw_query
            }

        # 3. Contingencia Multi-Zona
        fallback_results = []
        fallback_places = {}
        for loc in self.user_locations:
            loc_lat = float(loc.get('latitude', 0.0))
            loc_lng = float(loc.get('longitude', 0.0))
            loc_name = loc.get('name', 'Otra dirección')

            if abs(loc_lat - self.user_lat) < 0.001 and abs(loc_lng - self.user_lng) < 0.001:
                continue

            eng_fb = ProductSearchEngine(lat=loc_lat, lng=loc_lng, user=self.user, seed=self.seed)
            fb_candidates = eng_fb.search_purchase_candidates(
                query=raw_query,
                max_distance_meters=max_dist,
                limit=3,
                location_label=loc_name,
                mode=mode
            )
            fallback_results.extend(fb_candidates)
            fallback_places.update(eng_fb.purchase_places)
            if len(fallback_results) >= 6:
                break

        if fallback_results:
            return {"type": "results", "data": fallback_results, "places": fallback_places}

        # 4. Telemetría de Demanda Insatisfecha
        if raw_query:
            try:
                from django.core.cache import cache
                redis_conn = cache.client.get_client()
                redis_conn.rpush("telemetry:unmet_demand", json.dumps({
                    'client_id': str(self.user.id) if self.user and self.user.is_authenticated else None,
                    'search_term': raw_query,
                    'lat': self.user_lat,
                    'lng': self.user_lng,
                    'timestamp': timezone.now().isoformat()
                }))
            except Exception as e:
                print(f"[ATLAS TELEMETRY ERROR]: {e}")

        return {"type": "not_found", "message": f"Cero existencias para '{raw_query}' en todas tus zonas registradas."}

    @staticmethod
    def _format_place_label(place: Optional[Dict[str, Any]]) -> str:
        """Texto de ubicación en nombres de zona/ciudad/centro comercial; nunca cifras de distancia."""
        if not place:
            return ""
        parts = []
        if place.get('zone'):
            parts.append(f"Zona del comercio: {place['zone']}")
        if place.get('address'):
            parts.append(f"Dirección registrada: {place['address']}")
        if place.get('proximity'):
            parts.append(f"Cercanía respecto al usuario: {place['proximity']}")
        mall_label = AtlasManager._format_mall_label(place)
        if mall_label:
            parts.append(f"Ubicado en: {mall_label}")
        return (" | " + " | ".join(parts)) if parts else ""

    @staticmethod
    def _format_mall_label(place: Optional[Dict[str, Any]]) -> Optional[str]:
        """'Centro Comercial Sambil Chacao, piso 2' o None si la tienda no está en un centro comercial."""
        if not place or not place.get('mall_name'):
            return None
        label = f"Centro Comercial {place['mall_name']}"
        if place.get('mall_floor') is not None:
            label += f", piso {place['mall_floor']}"
        return label

    def _execute_shopping_list(self, args: Dict[str, Any]) -> Dict[str, Any]:
        needs = args.get('items', [])
        mode = args.get('mode', 'best')
        max_dist = float(args.get('max_distancia', 15000.0))

        engine = ProductSearchEngine(lat=self.user_lat, lng=self.user_lng, user=self.user, seed=self.seed)
        plan = engine.resolve_shopping_list(
            needs=needs,
            max_distance_meters=max_dist,
            location_label="Tu ubicación actual",
            mode=mode
        )
        plan['places'] = dict(engine.purchase_places)
        return plan

    def _execute_recommendations(self, args: Dict[str, Any]) -> List[Dict[str, Any]]:
        item_id = args.get('item_id')
        if not item_id:
            return []
            
        time_horizon = timezone.now() - timedelta(days=14)
        buyers = ProductViewLog.objects.filter(
            inventory_item_id=item_id, start_time__gte=time_horizon
        ).filter(Q(added_to_cart=True) | Q(bought=True)).values_list('client_id', flat=True).distinct()

        recommended = ProductViewLog.objects.filter(
            client_id__in=list(buyers), start_time__gte=time_horizon
        ).filter(Q(added_to_cart=True) | Q(bought=True)).exclude(
            inventory_item_id=item_id
        ).values('inventory_item_id').annotate(co_occurrence=Count('id')).order_by('-co_occurrence')[:3]

        results = []
        for log in recommended:
            try:
                item = InventoryItem.objects.get(id=log['inventory_item_id'], paused=False, stock__gt=0)
                results.append(item.get_json())
            except InventoryItem.DoesNotExist:
                continue

        if not results:
            try:
                base_item = InventoryItem.objects.select_related('product').get(id=item_id)
                fallback = InventoryItem.objects.filter(
                    product__category_id=base_item.product.category_id, paused=False, stock__gt=0
                ).exclude(id=item_id).order_by('-cached_popularity_score')[:3]
                results = [i.get_json() for i in fallback]
            except Exception:
                pass
                
        return results

    def _execute_personalized_feed(self, args: Dict[str, Any]) -> List[Dict[str, Any]]:
        favorite_category_ids = []
        if self.user and self.user.is_authenticated:
            time_horizon = timezone.now() - timedelta(days=30)
            recent_views = ProductViewLog.objects.filter(
                client=self.user,
                start_time__gte=time_horizon
            ).values('inventory_item__product__category_id').annotate(
                interactions=Count('id')
            ).order_by('-interactions')[:2]
            favorite_category_ids = [item['inventory_item__product__category_id'] for item in recent_views if item['inventory_item__product__category_id']]

        engine = ProductSearchEngine(lat=self.user_lat, lng=self.user_lng, user=self.user, seed=self.seed)
        qs = engine._get_base_active_queryset()
        qs = engine._annotate_proximity_flag(qs).filter(store__location__coordinates__distance_lte=(engine.user_location, D(m=15000.0)))
        
        db_products = []
        if favorite_category_ids:
            qs_affinity = qs.filter(product__category_id__in=favorite_category_ids).order_by('-cached_popularity_score')
            db_products = [item.get_json() for item in qs_affinity[:3]]
            if len(db_products) < 3:
                exclude_ids = [p['id'] for p in db_products]
                qs_fill = qs.exclude(id__in=exclude_ids).order_by('-cached_popularity_score')
                db_products.extend([item.get_json() for item in qs_fill[:3 - len(db_products)]])
        else:
            qs = qs.order_by('-cached_popularity_score')
            db_products = [item.get_json() for item in qs[:3]]

        return db_products

    # =========================================================================
    # CHAT LOOP ASÍNCRONO
    # =========================================================================

    @sync_to_async
    def _get_thread_history(self, thread_id: int) -> List[Dict[str, Any]]:
        messages = AtlasMessage.objects.filter(conversation_id=thread_id).order_by('-creation')[:6]
        messages = list(messages)[::-1]
        
        history = [{"role": "system", "content": self.chat_system_instruction}]
        
        ubicaciones_str = "\n".join([
            f"- {loc.get('name', 'Ubicación')}: Lat {loc.get('latitude', '')}, Lng {loc.get('longitude', '')}." 
            for loc in self.user_locations
        ]) if self.user_locations else "- Solo ubicación actual en vivo disponible."
        
        now_local = timezone.localtime(timezone.now())
        dias = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
        if now_local.hour < 11:
            momento = 'mañana (desayuno)'
        elif now_local.hour < 15:
            momento = 'mediodía (almuerzo)'
        elif now_local.hour < 19:
            momento = 'tarde (merienda)'
        else:
            momento = 'noche (cena)'

        history.append({
            "role": "system", 
            "content": (
                f"CONTEXTO ESPACIAL DEL USUARIO:\n{ubicaciones_str}\n"
                f"Zona actual deducida por coordenadas: {describe_zone(self.user_lat, self.user_lng)}.\n\n"
                f"CONTEXTO TEMPORAL: {dias[now_local.weekday()]} {now_local.strftime('%I:%M %p')}, {momento}. "
                "Úsalo para deducir lo que el usuario probablemente necesita sin preguntarle."
            )
        })

        for msg in messages:
            role = 'user' if msg.origin == self.ORIGIN_USER else 'assistant'
            content = msg.text[:1500] if len(msg.text) > 1500 else msg.text
            history.append({"role": role, "content": content})
            
        return history

    @sync_to_async
    def _save_message(self, thread_id: int, origin: int, text: str, product_ids: List[str] = None, action_command: dict = None) -> AtlasMessage:
        return AtlasMessage.objects.create(
            conversation_id=thread_id, 
            origin=origin, 
            text=text,
            product_ids=product_ids or [],
            action_command=action_command
        )

    @staticmethod
    def _data_tools_schema() -> List[Dict[str, Any]]:
        """Herramientas que consultan datos reales (todas menos la conversacional)."""
        return [t for t in _get_tools_schema() if t["function"]["name"] != "responder_conversacion"]

    _COMMERCE_CLAIM_PATTERN = re.compile(
        r"(\$\s?\d)|(\b\d+(?:[.,]\d+)?\s?(?:km|kil[oó]metros?|metros)\b)|(\b\d+\s?m\b)|(platinum)|(abiert[oa]\s+(?:ahora|ahorita))",
        re.IGNORECASE,
    )

    _UNIT = r"(?:km|kil[oó]metros?|metros|mts|m)"
    _TAIL = r"(?:\s+de\s+(?:tu\s+ubicaci[oó]n(?:\s+actual)?|ti|tu\s+zona|aqu[ií]|distancia))?"
    # Frases tipo "(a 30.7 km)", "a 730 m de tu ubicación", "a unos 2 kilómetros", "38 km de aquí".
    # Las medidas de producto ("un sofá de 2 m de ancho") NO coinciden: exigen 'a', paréntesis o km.
    _DISTANCE_PHRASE_PATTERN = re.compile(
        "|".join([
            r"\s*\(\s*(?:a\s+|unos\s+)?\d+(?:[.,]\d+)?\s?" + _UNIT + r"\s*\)",
            r"\s+a\s+(?:unos\s+|unas\s+)?\d+(?:[.,]\d+)?\s?" + _UNIT + r"\b" + _TAIL,
            r"\s+(?:unos\s+|unas\s+)?\d+(?:[.,]\d+)?\s?(?:km|kil[oó]metros?)\b" + _TAIL,
        ]),
        re.IGNORECASE,
    )
    _KM_WORD_PATTERN = re.compile(r"\bkm\b|kil[oó]metros?", re.IGNORECASE)

    def _mentions_distance_units(self, text: Optional[str]) -> bool:
        return bool(text and (self._DISTANCE_PHRASE_PATTERN.search(text) or self._KM_WORD_PATTERN.search(text)))

    def _scrub_distance_phrases(self, text: str) -> str:
        """Último recurso: elimina frases de distancia numérica que el modelo haya dejado pasar."""
        cleaned = self._DISTANCE_PHRASE_PATTERN.sub("", text)
        cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
        return re.sub(r"[ \t]{2,}", " ", cleaned).strip()

    async def _enforce_human_locations(self, text: str, history: list, thread_id: int) -> str:
        """
        Atlas jamás debe hablar en metros/kilómetros. Si el borrador lo hace, se le pide
        reescribirlo con nombres de zonas; si aún así persiste, se eliminan las frases.
        """
        if not self._mentions_distance_units(text):
            return text

        print(f"[ATLAS GUARD] Distancias numéricas en la respuesta; reescribiendo. Texto: {text[:200]}")
        try:
            rewrite_history = list(history) + [
                {"role": "assistant", "content": text},
                {
                    "role": "system",
                    "content": (
                        "CORRECCIÓN OBLIGATORIA: tu respuesta anterior usó distancias numéricas (metros o kilómetros), "
                        "lo cual está PROHIBIDO. Reescríbela con el mismo contenido (mismos productos, precios y tiendas) "
                        "pero ubicando cada comercio SOLO con nombres de urbanización, ciudad o centro comercial "
                        "(ej. 'aquí mismo en Guatire', 'por Altamira, en Caracas'). No incluyas ninguna cifra de distancia. "
                        "Responde únicamente con el texto reescrito."
                    ),
                },
            ]
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=rewrite_history,
                temperature=0.2,
                extra_body={"session_id": f"cartmaker-atlas-thread-{thread_id}"},
            )
            rewritten = response.choices[0].message.content or ""
            if rewritten.strip() and not self._mentions_distance_units(rewritten):
                return rewritten
            text = rewritten or text
        except Exception as e:
            print(f"[ATLAS GUARD] Error reescribiendo sin distancias: {e}")

        return self._scrub_distance_phrases(text)

    def _claims_commerce_data(self, text: Optional[str]) -> bool:
        """True si el texto afirma precios, distancias, Platinum o estado abierto (datos que solo pueden venir de una herramienta)."""
        return bool(text and self._COMMERCE_CLAIM_PATTERN.search(text))

    async def _create_completion(self, history: list, thread_id: int, tools: list, tool_choice: str, temperature: float):
        """Llama al LLM; si el proveedor rechaza tool_choice='required', degrada a 'auto'."""
        kwargs = dict(
            model=self.model_name,
            messages=history,
            tools=tools,
            temperature=temperature,
            extra_body={"session_id": f"cartmaker-atlas-thread-{thread_id}"},
        )
        try:
            return await self.client.chat.completions.create(tool_choice=tool_choice, **kwargs)
        except Exception as e:
            if tool_choice == "required":
                print(f"[ATLAS] tool_choice='required' no soportado, usando 'auto': {e}")
                return await self.client.chat.completions.create(tool_choice="auto", **kwargs)
            raise

    async def send_chat_message_async(self, thread_id: int, user_text: str, image_base64: str = None) -> Dict[str, Any]:
        try:
            history = await self._get_thread_history(thread_id)
            await self._save_message(thread_id, self.ORIGIN_USER, user_text, [])
            
            if image_base64:
                forced_instruction = (
                    "\n\n[INSTRUCCIÓN VISUAL OBLIGATORIA: Analiza la foto adjunta, "
                    "deduce qué producto comercial es y ejecuta de inmediato la herramienta "
                    "'buscar_productos_inventario' con términos concisos sin inventar texto antes]."
                )
                history.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_text + forced_instruction},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                    ]
                })
            else:
                history.append({"role": "user", "content": user_text})
            
            # 'required': el modelo DEBE elegir una herramienta (buscar o 'responder_conversacion'),
            # así no puede inventar productos, tiendas o precios respondiendo "de memoria".
            response = await self._create_completion(
                history, thread_id, _get_tools_schema(), tool_choice="required", temperature=0.2
            )
            
            choice = response.choices[0]
            injected_products = []
            action_command = None
            data_tool_used = False

            for _attempt in range(2):
                while choice.message.tool_calls:
                    tool_calls = choice.message.tool_calls
                    history.append(choice.message)
                
                    for tool_call in tool_calls:
                        fn_name = tool_call.function.name
                        try:
                            fn_args = json.loads(tool_call.function.arguments or "{}")
                        except ValueError:
                            fn_args = {}
                        tool_payload = {}
                        if fn_name != "responder_conversacion":
                            data_tool_used = True

                        # 1. Búsqueda Unitaria / Por Palabras
                        if fn_name == "buscar_productos_inventario":
                            db_res = await sync_to_async(self._execute_search)(fn_args)
                        
                            if db_res.get("type") == "results":
                                items = db_res["data"]
                                # Deduplicar e inyectar en la lista para Flutter
                                existing_ids = {str(p.get('id')) for p in injected_products}
                                for item in items:
                                    if str(item.get('id')) not in existing_ids:
                                        injected_products.append(item)
                                        existing_ids.add(str(item.get('id')))

                                # Formatear la Tríada exacta para el razonamiento de Gemini
                                formatted_data = []
                                for it in items:
                                    triad = it.get('triad', {})
                                    p_name = it.get('product', {}).get('name', 'Artículo')
                                    p_price = triad.get('price_usd', it.get('effective_price'))
                                    p_open = "ABIERTO AHORA" if triad.get('open_now') else "CERRADO"
                                    p_plat = " [Comercio Platinum 🏆]" if triad.get('platinum') else ""
                                    p_off = f" [Oferta: {triad.get('offer_pct')}% off]" if triad.get('offer_pct') else ""
                                
                                    m_rating = triad.get('merchant_rating', 0.0)
                                    m_count = triad.get('merchant_reviews_count', 0)
                                    p_rating = triad.get('product_rating', 0.0)
                                    p_count = triad.get('product_reviews_count', 0)

                                    # Etiqueta transparente para que Gemini sepa exactamente qué decir
                                    if m_count > 0:
                                        rep_label = f"Reputación Tienda: {m_rating} de 5 estrellas ({m_count} opinión{'es' if m_count > 1 else ''})"
                                    else:
                                        rep_label = "Reputación Tienda: Comercio nuevo (aún sin calificaciones registradas)"

                                    if p_count > 0:
                                        rep_label += f" | Calificación del producto: {p_rating}★ ({p_count})"

                                    formatted_data.append(
                                        f"• [{p_name}] a ${p_price}{p_off} en '{it.get('store_name')}' ({it.get('company_name')}{p_plat}) | "
                                        f"{rep_label} | Estado: {p_open}"
                                    )
                                # Ubicación SIEMPRE en nombres de zona (sin metros ni kilómetros)
                                places = db_res.get("places", {})
                                for idx, it in enumerate(items):
                                    place = places.get(str(it.get('id')))
                                    formatted_data[idx] += self._format_place_label(place)
                                tool_payload = {"status": "success", "candidatos_reales": formatted_data}

                                expansion = db_res.get("expansion")
                                if expansion:
                                    tool_payload["busqueda_expandida"] = {
                                        "zona_del_usuario": expansion.get("origin_zone"),
                                        "zona_donde_se_encontro": expansion.get("found_zone"),
                                        "instruccion": (
                                            f"NO había existencias de '{fn_args.get('query')}' en {expansion.get('origin_zone')} "
                                            "ni en sus alrededores. Díselo al usuario de forma natural y breve, indica que lo "
                                            f"más cercano que encontraste fue en {expansion.get('found_zone')}, "
                                            "y presenta los productos. Habla SOLO con nombres de zonas y ciudades; "
                                            "PROHIBIDO usar metros, kilómetros o cualquier cifra de distancia."
                                        ),
                                    }

                            elif db_res.get("type") == "ask_confirmation":
                                action_command = {
                                    "action": "ASK_ZONE_CONFIRMATION",
                                    "query_to_search": db_res.get("query"),
                                    "zonas": db_res.get("zonas")
                                }
                                tool_payload = {"status": "not_found", "message": db_res.get("message")}
                            else:
                                tool_payload = {"status": "not_found", "message": db_res.get("message")}

                        # 2. Armar Receta o Lista de Compras
                        elif fn_name == "armar_lista_o_receta":
                            plan = await sync_to_async(self._execute_shopping_list)(fn_args)
                        
                            # Inyectamos los productos encontrados a las tarjetas de Flutter
                            for item in plan.get('injected', []):
                                if str(item.get('id')) not in {str(p.get('id')) for p in injected_products}:
                                    injected_products.append(item)

                            # Formato claro del plan conjunto para Gemini
                            store_info = plan.get('primary_store')
                            summary = {
                                "comercio_principal": store_info.get('store_name') if store_info else "No hubo tienda única",
                                "ingredientes_en_comercio_principal": f"{store_info.get('items_in_store', 0)} de {store_info.get('needs_total', 0)}" if store_info else "0",
                                    "completados_en_otras_tiendas": plan.get('filled_elsewhere', []),
                                "ingredientes_sin_stock": plan.get('missing_queries', []),
                                "total_estimado_usd": plan.get('estimated_total_usd', 0.0)
                            }

                            # Centros comerciales de los artículos encontrados (solo los que están en uno)
                            plan_places = plan.get('places', {})
                            primary_store_id = str(store_info.get('store_id')) if store_info else None
                            malls_in_plan = []
                            for found in plan.get('found', []):
                                mall_label = self._format_mall_label(plan_places.get(str(found.get('id'))))
                                if primary_store_id and str(found.get('store_id')) == primary_store_id:
                                    primary_place = plan_places.get(str(found.get('id'))) or {}
                                    summary["zona_comercio_principal"] = primary_place.get('zone')
                                    summary["cercania_comercio_principal"] = primary_place.get('proximity')
                                if not mall_label:
                                    continue
                                entry = {
                                    "producto": found.get('product', {}).get('name'),
                                    "tienda": found.get('store_name'),
                                    "ubicado_en": mall_label,
                                }
                                malls_in_plan.append(entry)
                                if primary_store_id and str(found.get('store_id')) == primary_store_id:
                                    summary["comercio_principal_ubicado_en"] = mall_label
                            if malls_in_plan:
                                summary["articulos_en_centros_comerciales"] = malls_in_plan
                            tool_payload = {"status": "success", "plan_de_compra": summary}

                        # 3. Feed Personalizado
                        elif fn_name == "explorar_feed_personalizado":
                            db_products = await sync_to_async(self._execute_personalized_feed)(fn_args)
                            for p in db_products:
                                if str(p.get('id')) not in {str(x.get('id')) for x in injected_products}:
                                    injected_products.append(p)
                            tool_payload = {
                                "status": "success" if db_products else "not_found",
                                "data": [f"{p.get('product',{}).get('name')} a ${p.get('effective_price', p.get('custom_price'))} en {p.get('company_name')}" for p in db_products]
                            }

                        # 3.5 Conversación sin datos de comercio
                        elif fn_name == "responder_conversacion":
                            tool_payload = {
                                "status": "ok",
                                "instruccion": (
                                    "Responde de forma breve y cálida SIN mencionar productos, tiendas, precios, "
                                    "distancias ni reputación. Si el usuario en realidad necesita algo, invítalo a decirte qué busca."
                                ),
                            }

                        # 4. Sugerencias Cruzadas
                        elif fn_name == "sugerir_productos_relacionados":
                            db_recs = await sync_to_async(self._execute_recommendations)(fn_args)
                            for p in db_recs:
                                if str(p.get('id')) not in {str(x.get('id')) for x in injected_products}:
                                    injected_products.append(p)
                            tool_payload = {
                                "status": "success" if db_recs else "not_found",
                                "data": [f"{p.get('product',{}).get('name')} a ${p.get('custom_price', 0)} en {p.get('company_name')}" for p in db_recs]
                            }

                        print(f"[ATLAS TOOL] {fn_name}({fn_args}) -> {tool_payload.get('status')} | cards_acumuladas={len(injected_products)}")
                        history.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": fn_name,
                            "content": json.dumps(tool_payload)
                        })

                    response = await self.client.chat.completions.create(
                        model=self.model_name,
                        messages=history,
                        tools=_get_tools_schema(),
                        temperature=0.4,
                        extra_body={"session_id": f"cartmaker-atlas-thread-{thread_id}"}
                    )
                    choice = response.choices[0]
                if (
                    data_tool_used
                    or _attempt == 1
                    or not self._claims_commerce_data(choice.message.content)
                ):
                    break

                # Guardia anti-alucinación: afirmó datos de comercio sin consultar nada.
                print(f"[ATLAS GUARD] Respuesta con datos sin herramienta; reintentando con búsqueda obligatoria. Texto: {choice.message.content[:200]}")
                history.append({
                    "role": "system",
                    "content": (
                        "CORRECCIÓN: tu borrador mencionaba productos, precios, distancias o tiendas sin haber consultado "
                        "ninguna herramienta en este turno. Descártalo. Consulta ahora la herramienta adecuada con el "
                        "pedido del usuario y responde SOLO con los datos que devuelva."
                    ),
                })
                response = await self._create_completion(
                    history, thread_id, self._data_tools_schema(), tool_choice="required", temperature=0.2
                )
                choice = response.choices[0]


            ai_final_text = choice.message.content
            if ai_final_text:
                ai_final_text = await self._enforce_human_locations(ai_final_text, history, thread_id)
            if not data_tool_used and self._claims_commerce_data(ai_final_text):
                print(f"[ATLAS GUARD] Respuesta descartada por datos sin respaldo: {ai_final_text[:200]}")
                ai_final_text = (
                    "Ahorita no pude consultar el inventario para darte datos confiables. "
                    "¿Me repites lo que buscas para intentarlo de nuevo?"
                )
            p_ids = [str(p['id']) for p in injected_products if 'id' in p]
            saved_msg = await self._save_message(thread_id, self.ORIGIN_AI, ai_final_text, p_ids, action_command)

            # Telemetría de productos vistos mediante Atlas
            if injected_products:
                now = timezone.now()
                logs = [
                    ProductViewLog(
                        inventory_item_id=p['id'],
                        client_id=self.user.id if self.user and self.user.is_authenticated else None,
                        start_time=now,
                        origin_source='atlas',
                        search_prompt=user_text[:150],
                        atlas_message_id=saved_msg.id
                    )
                    for p in injected_products if 'id' in p
                ]
                await sync_to_async(ProductViewLog.objects.bulk_create)(logs, ignore_conflicts=True)

            return {
                "success": True,
                "response": ai_final_text,
                "message_id": saved_msg.id,
                "injected_products": injected_products,
                "action_command": action_command
            }

        except Exception as e:
            print(f"❌ [ATLAS CRITICAL ERROR]: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": "Atlas está optimizando sus rutas de inventario. Intenta de nuevo en unos segundos."}

    # =========================================================================
    # RECONOCIMIENTO VISUAL Y EXCEL (VISIÓN Y DATOS)
    # =========================================================================

    @sync_to_async
    def _get_available_subcategories(self) -> List[Dict[str, Any]]:
        return [{"id": s.id, "name": f"{s.parent_category.name} - {s.name}"} for s in SubCategory.objects.select_related('parent_category').all()]

    def _parse_gemini_json_response(self, text_response: str) -> Dict[str, Any]:
        if not text_response:
            return {"products": [], "error": "Respuesta vacía."}
        try:
            clean = text_response.strip()
            if clean.startswith('```json'): clean = clean[7:]
            if clean.startswith('```'): clean = clean[3:]
            if clean.endswith('```'): clean = clean[:-3]
            res = json.loads(clean.strip(), strict=False)
            if "products" in res and isinstance(res["products"], list):
                for prod in res["products"]:
                    if "description" in prod and isinstance(prod["description"], str):
                        prod["description"] = re.sub(r'(?<!\n)\n(?!\n)', '\n\n', prod["description"]).strip()
            return res
        except json.JSONDecodeError:
            return {"products": [], "error": "Atlas no pudo interpretar el formato de los datos."}

    async def analyze_image_for_products_async(self, image_data: bytes, mime_type: str) -> Dict[str, Any]:
        subcats = await self._get_available_subcategories()
        prompt = f"Analiza la imagen, extrae los productos y responde ÚNICAMENTE con JSON: {{\"products\": [{{\"name\": \"...\", \"description\": \"...\", \"price\": 0.0, \"subcategory_id\": 1}}]}}. Catálogo: {json.dumps(subcats, ensure_ascii=False)}"
        b64 = base64.b64encode(image_data).decode('utf-8')
        res = await self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}}]}],
            temperature=0.3
        )
        return self._parse_gemini_json_response(res.choices[0].message.content)

    async def analyze_image_for_multiple_products_async(self, image_data: bytes, mime_type: str) -> Dict[str, Any]:
        return await self.analyze_image_for_products_async(image_data, mime_type)

    async def analyze_processed_json_products_async(self, raw_products_json: List[Dict[str, Any]]) -> Dict[str, Any]:
        subcats = await self._get_available_subcategories()
        prompt = f"Mapea estos productos rústicos al catálogo oficial. Responde solo JSON: {{\"products\": [...]}}. Catálogo: {json.dumps(subcats, ensure_ascii=False)}"
        res = await self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "system", "content": prompt}, {"role": "user", "content": json.dumps(raw_products_json, ensure_ascii=False)}],
            temperature=0.2
        )
        return self._parse_gemini_json_response(res.choices[0].message.content)