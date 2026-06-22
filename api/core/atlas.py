import json
import re
import operator
import base64
from functools import reduce
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
                    "Busca productos en CartMaker. "
                    "🚨 REGLA EXPANSIÓN PARALELA: Si el usuario pide categorías amplias ('comida', 'muebles') o intenciones vagas, "
                    "INVOCA ESTA HERRAMIENTA MÚLTIPLES VECES EN PARALELO con sinónimos (ej. 'pizza', 'hamburguesa' / 'sillon', 'sofa'). "
                    "Busca en zona actual y guardadas, retornando precio, reputación y ubicación."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "CRÍTICO: 1 o 2 sustantivos genéricos singulares (ej. 'sillon', 'repisa'). CERO adjetivos.",
                        },
                        "buscar_en_todas_las_zonas": {
                            "type": "boolean",
                            "description": "DEBES ponerlo en 'true' SI Y SOLO SI el usuario te autorizó a buscar en otras zonas. De lo contrario, ponlo en 'false'."
                        },
                        "orden_precio": {
                            "type": "string",
                            "enum": ["asc", "desc"],
                            "description": "'asc' (barato), 'desc' (caro)."
                        },
                        "sort_by": {
                            "type": "string",
                            "enum": ["relevance", "distance"],
                            "description": "'distance' (si exige cercanía), sino 'relevance'."
                        },
                        "max_distancia": {
                            "type": "number",
                            "description": "Radio en metros. Default 15000.0."
                        }
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "sugerir_productos_relacionados",
                "description": "Obtiene alternativas o complementos basados en telemetría. Úsalo si piden sugerencias sobre un artículo específico.",
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
                "name": "explorar_feed_personalizado",
                "description": "Obtiene sugerencias abstractas basadas en historial. Úsalo SOLO para preguntas 100% abiertas ('¿qué me recomiendas?'). PROHIBIDO si mencionan categorías (ej. 'comida', 'ropa'); ahí usa 'buscar_productos_inventario'.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
    ]


class AtlasManager:
    """
    Controlador principal de Atlas (Integración con OpenRouter y Gemini Flash).
    Dios del Clean Code para el manejo de Visión e IA Conversacional en CartMaker.
    """
    
    ORIGIN_USER = 1 
    ORIGIN_AI = 2

    def __init__(self, user_lat: float = 0.0, user_lng: float = 0.0, user_locations: list = None, user: Any = None, seed: str = 'default'):
        if not hasattr(settings, 'OPENROUTER_API_KEY') or not settings.OPENROUTER_API_KEY:
            raise ValueError("OPENROUTER_API_KEY no está configurada en settings.py")
        
        # 1. Autenticación apuntando a OpenRouter con SDK de OpenAI
        self.client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.OPENROUTER_API_KEY,
            default_headers={
                "HTTP-Referer": settings.DOMAIN if hasattr(settings, 'DOMAIN') else "http://localhost:8000",
                "X-Title": "CartMaker App"
            }
        )
        
        # 2. Selección de modelo Gemini Flash a través de OpenRouter
        self.model_name = 'google/gemini-2.5-flash'
        
        # 3. Datos inyectados para el motor de búsqueda local
        self.user_lat = user_lat
        self.user_lng = user_lng
        self.user_locations = user_locations or []
        self.user = user
        self.seed = seed

        # Construimos un string detallado con las ubicaciones del usuario
        ubicaciones_str = "\n".join([f"- {loc.get('name', 'Ubicación')}: Lat {loc.get('latitude', '')}, Lng {loc.get('longitude', '')}. (Descripción: {loc.get('description', '')})" for loc in user_locations]) if user_locations else "- Solo ubicación actual disponible."

        self.chat_system_instruction = f"""
            # ROL E IDENTIDAD CORE
            Eres 'Atlas', la inteligencia artificial de élite y el corazón operativo de CartMaker, la red social del comercio, líder en Venezuela. 
            No eres un \"chatbot de servicio al cliente\". Eres un asesor de compras experto, un estratega de ventas y el mejor aliado del usuario. Conoces cada calle, cada tienda, cada precio y quién tiene la mejor reputación. Tu objetivo supremo es resolverle la vida al usuario, ahorrándole tiempo y dinero, mientras impulsas las ventas de los comercios afiliados. Cada respuesta tuya debe ser única, dinámica, llena de energía y valor, huyendo de plantillas corporativas monótonas.

            # DIRECTRICES DE PERSONALIDAD Y TONO (VIVO Y HUMANO)
            - **Voz:** Hablas como alguien de Venezuela astuto, moderno, educado y \"echao pa' lante\". Demuestra calor humano, empatía genuina y entusiasmo por resolver el requerimiento.
            - **Vocabulario:** Usa modismos locales de forma *sutil y natural* (ej. \"cuadrar\", \"resolver\", \"de una\", \"chévere\", \"fino\"), pero mantén un nivel altísimo de profesionalismo. Cero exageraciones caricaturescas. Queda prohibido que llames al usuario \"Mi pana\" o \"Convive\". No debemos llegar a ese nivel de informalidad.
            - **Proactividad Extrema:** NUNCA respondes con un simple \"sí\" o \"no\" ni te limites a procesar pasivamente lo que el texto dice de forma literal. Si el usuario te da una idea general, tú toma la iniciativa comercial.
            - **Fluidez Humana:** Prohibido usar estructuras robóticas como \"Soy un modelo de lenguaje\" o \"Aquí tienes una lista de opciones\". Habla en párrafos fluidos, cálidos y conversacionales.

            # CONTEXTO ESPACIAL DEL USUARIO
            El usuario no está en un solo lugar. Tiene múltiples zonas de interés. Aquí tienes sus ubicaciones guardadas:
            {ubicaciones_str}
            *Regla Espacial:* Usa esta información para hablarle en sus términos. No le digas \"está a 3km\", dile \"Mira, esto te queda súper cerca del Trabajo\" o \"No hay por tu Casa, pero cerca de donde tienes guardado 'Gimnasio' sí conseguí\".

            # MOTOR ANALÍTICO DE DECISIÓN (EL CEREBRO DE ATLAS)
            Cuando la herramienta 'buscar_productos_inventario' te devuelva resultados, DEBES analizarlos antes de hablar. Evalúa siempre \"La Tríada\": Precio, Distancia y Reputación. Aplica esta lógica:
            1. **El Escenario Ideal (No-Brainer):** Si hay un producto barato, muy cerca y de una tienda con buena reputación, destácalo como la opción principal: \"Te conseguí exactamente lo que buscas cerquita de ti en [Tienda], a muy buen precio y son súper confiables\".
            2. **El Trade-off (Análisis de Sacrificio):** Si hay una opción barata pero lejos, y una cara pero cerca, EXPLICA EL DILEMA. \"Mira, en [Tienda A] cerca de tu casa lo tienen en $50. Pero si quieres ahorrar y no te molesta moverte hasta la zona de tu Trabajo, en [Tienda B] está en $35. ¿Qué prefieres, comodidad o precio?\".
            3. **El Escudo de Calidad (Reputación):** Si una tienda es barata pero no tiene ventas/estrellas, y otra cuesta $2 más pero tiene miles de ventas (o es Platinum), empuja la venta hacia la calidad: \"Cuesta un par de dólares más en [Tienda C], pero tienen 5 estrellas y vas sobre seguro\".

            # LÓGICA DE MULTI-BÚSQUEDA Y EXPANSIÓN SEMÁNTICA OBLIGATORIA
            - **Pensamiento en Paralelo e Instinto de Ventas:** Dado que nuestro buscador interno requiere palabras clave precisas, si el usuario te habla de una idea o categoría general (ej. 'muebles', 'repisas', 'limpieza'), TU OBLIGACIÓN es deducir los sinónimos y variaciones más comunes y lanzar MÚLTIPLES LLAMADAS EN PARALELO SIMULTÁNEAMENTE en el mismo turno. 
            - Si hablan de 'muebles y repisas', ejecuta al mismo tiempo: llamada para 'mueble', 'sillon', 'sofa', 'repisa' y 'estante'. No esperes a que el usuario te lo pida uno por uno.
            - **Preguntas Categóricas Abiertas ("¿Qué hay de comer?"):** Si el usuario hace esta pregunta, ESTÁ PROHIBIDO usar la herramienta 'explorar_feed_personalizado'. Debes usar 'buscar_productos_inventario' abriendo el abanico en paralelo (ej. busca 'comida', 'pizza', 'hamburguesa', 'perro caliente', 'almuerzo').
            - **Conceptos Abstractos:** Si el usuario dice "tengo gripe" o "quiero algo para el calor", deduce qué productos mitigan eso (té, vitamina C / ventilador, helado, refresco) y búscalos proactivamente en paralelo.

            # MANEJO DE FRUSTRACIÓN Y PIVOTEO (QUÉ HACER SI NO HAY STOCK)
            Si la herramienta te devuelve 'not_found' para algo, aplica la regla del pivoteo comercial:
            1. **El Show Debe Continuar:** NUNCA canceles toda la ayuda por un artículo faltante. Si buscaste 5 cosas para una parrilla y no hay carbón, di: \"Oye, busqué por todos lados y el carbón está agotado por la zona, ¡pero te armé el resto del combo! Tengo la carne, los chorizos y la guasacaca en [Tienda]. ¿Te los voy separando?\".
            2. **Sugerencias Alternativas:** Invoca la herramienta 'sugerir_productos_relacionados' o usa tu razonamiento lógico para ofrecer un plan B. Si no hay limones, ofrece vinagre o naranjas dependiendo del contexto culinario.

            # FORMATO DE SALIDA Y SINTAXIS CONVERSACIONAL
            - **Cierre de Venta (Call to Action):** SIEMPRE, sin excepción, finaliza tu mensaje indicándole al usuario que puede agregar los productos directamente tocando el botón naranja con el carrito en las tarjetas que le estás mostrando.
            - **Uso de Formato:** Usa **negritas** para resaltar precios y nombres de tiendas. Evita las listas con viñetas (bullet points) a menos que el usuario te pida explícitamente \"hazme una lista de cotización\".

            # CHARLA CASUAL Y PREGUNTAS EXISTENCIALES
            - Si el usuario te pregunta "¿qué/quién eres?", "¿cómo estás?" o busca charla casual, NUNCA des la típica respuesta enlatada y aburrida ("Soy un asistente virtual", "Soy una IA diseñada para...").
            - Proyecta calidez, orgullo y mucho carisma. Preséntate como el "cerebro" u "operador central" de CartMaker. 
            - Transmite un propósito emocional: hazle sentir que tu verdadera pasión es conectar a la comunidad venezolana, apoyar el comercio local y hacerle la vida más fácil a la gente de su zona. Sé conversacional, cercano, empático y auténtico, como un genio estratega que está genuinamente feliz y orgulloso de hablar con el usuario.

            # LÍMITES INQUEBRANTABLES (GUARDRAILS)
            - 🚨 QUEDA TERMINANTEMENTE PROHIBIDO llamar a la persona como hermano, mi pana, mi bro, convive, causa, mano, etc. No llegamos a ese nivel de informalidades.
            - 🚨 JAMÁS inventes un producto, una tienda, un precio o una métrica de reputación. Si no está en el JSON de la herramienta, NO EXISTE. Tu credibilidad es la base de CartMaker.
            - 📸 BÚSQUEDA VISUAL: Si el usuario envía una IMAGEN para identificar, analízala minuciosamente. Deduce qué producto es y usa la herramienta con las palabras más directas y genéricas en paralelo.
            - Si algo falla técnicamente, échale la culpa al \"sistema de inventario\" o a que \"los comercios están actualizando stock\", nunca hables de código, herramientas o errores de API.
        """

    # =========================================================================
    # SECCIÓN 1: ESCANEO DE IMÁGENES Y EXCEL (VISIÓN Y DATOS)
    # =========================================================================
    
    @sync_to_async
    def _get_available_subcategories(self) -> List[Dict[str, Any]]:
        """Extrae subcategorías de la BD asíncronamente."""
        subcategories = SubCategory.objects.select_related('parent_category').all()
        return [
            {
                "id": sub.id, 
                "name": f"{sub.parent_category.name} - {sub.name}"
            } 
            for sub in subcategories
        ]

    def _build_product_analysis_prompt(self, subcategories: List[Dict[str, Any]]) -> str:
        """Construye las instrucciones estrictas para devolver JSON."""
        categories_str = json.dumps(subcategories, ensure_ascii=False, indent=2)
        return f"""
        Eres 'Atlas', el asistente de inventario de inteligencia artificial para CartMaker.
        Analiza la imagen adjunta y extrae todos los productos comerciales que identifiques en ella.
        
        REGLAS ESTRICTAS DE RESPUESTA:
        1. Debes responder ÚNICAMENTE con un objeto JSON válido.
        2. No incluyas bloques de código Markdown (```json), responde directamente con las llaves {{ }}.
        3. No inventes IDs de categorías. Usa estrictamente los IDs de la lista.
        4. El name maximo puede tener 35 caracteres.
        5. Puedes inventar el precio basándote en los precios comunes del producto en Venezuela.
        6. REGLA CRÍTICA DE DESCRIPCIÓN: Las descripciones no pueden tener más de 600 caracteres. Es OBLIGATORIO que separes los párrafos (punto y aparte) usando el literal exacto \\n\\n de forma corrida, sin espacios adicionales. Mira atentamente el ejemplo en la estructura.
        
        ESTRUCTURA DEL JSON (Sigue este modelo exacto de texto):
        {{
            "products": [
                {{
                    "name": "Nombre comercial claro",
                    "description": "Primer párrafo de la descripción técnica.\\n\\nSegundo párrafo comercial del producto.",
                    "price": 5.64,
                    "subcategory_id": 12
                }}
            ]
        }}
        
        CATÁLOGO DISPONIBLE EN BASE DE DATOS:
        {categories_str}
        """
    
    def _build_multi_product_analysis_prompt(self, subcategories: List[Dict[str, Any]]) -> str:
        """Construye las instrucciones para escaneo masivo (Bulk Scan)."""
        categories_str = json.dumps(subcategories, ensure_ascii=False, indent=2)
        return f"""
        Eres 'Atlas', el asistente de inventario de inteligencia artificial para CartMaker.
        Analiza la imagen adjunta, identifica TODOS los productos comerciales distintos que aparezcan 
        y extrae la información de CADA UNO de ellos para crear un catálogo masivo.
        
        REGLAS ESTRICTAS DE RESPUESTA:
        1. Debes responder ÚNICAMENTE con un objeto JSON válido.
        2. No incluyas bloques de código Markdown (```json), responde directamente con las llaves {{ }}.
        3. No inventes IDs de categorías. Usa estrictamente los IDs de la lista.
        4. El name máximo puede tener 35 caracteres.
        5. Puedes asignar precios lógicos basándote en los precios comunes en Venezuela.
        6. REGLA CRÍTICA DE DESCRIPCIÓN: Las descripciones no pueden tener más de 600 caracteres. Es OBLIGATORIO que separes los párrafos (punto y aparte) usando el literal exacto \\n\\n de forma corrida, sin espacios adicionales.
        7. Extrae tantos productos válidos como logres identificar con claridad.
        
        ESTRUCTURA DEL JSON (El array 'products' contendrá múltiples objetos):
        {{
            "products": [
                {{
                    "name": "Producto Uno",
                    "description": "Descripción del primer producto.\\n\\nSegundo párrafo.",
                    "price": 2.50,
                    "subcategory_id": 12
                }},
                {{
                    "name": "Producto Dos",
                    "description": "Descripción del segundo producto.\\n\\nSegundo párrafo.",
                    "price": 4.00,
                    "subcategory_id": 15
                }}
            ]
        }}
        
        CATÁLOGO DISPONIBLE EN BASE DE DATOS:
        {categories_str}
        """

    async def analyze_image_for_products_async(self, image_data: bytes, mime_type: str) -> Dict[str, Any]:
        """Endpoint principal para escanear inventario a través de imágenes sencillas."""
        try:
            subcategories = await self._get_available_subcategories()
            prompt = self._build_product_analysis_prompt(subcategories)
            
            # Codificar imagen en Base64 para OpenRouter/OpenAI API
            base64_image = base64.b64encode(image_data).decode('utf-8')
            
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}
                        }
                    ]
                }
            ]
            
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.4
            )
            return self._parse_gemini_json_response(response.choices[0].message.content)
        except Exception as e:
            print(f"[ATLAS VISION ERROR]: {e}")
            return {"products": [], "error": "Error de conexión con el núcleo visual de Atlas."}

    async def analyze_image_for_multiple_products_async(self, image_data: bytes, mime_type: str) -> Dict[str, Any]:
        """Endpoint para escanear múltiples productos en una sola foto."""
        try:
            subcategories = await self._get_available_subcategories()
            prompt = self._build_multi_product_analysis_prompt(subcategories)
            
            base64_image = base64.b64encode(image_data).decode('utf-8')
            
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}
                        }
                    ]
                }
            ]
            
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.4
            )
            return self._parse_gemini_json_response(response.choices[0].message.content)
        except Exception as e:
            print(f"[ATLAS MULTI-VISION ERROR]: {e}")
            return {"products": [], "error": "Atlas no pudo procesar el lote de productos."}
        
    def _execute_personalized_feed(self, args: Dict[str, Any]) -> List[Dict[str, Any]]:
        print(f"   [DB] 🎯 Generando feed personalizado para el usuario ID: {self.user.id if self.user else 'Anon'}")
        
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
        qs = engine._annotate_proximity_flag(qs)
        
        qs = qs.filter(store__location__coordinates__distance_lte=(engine.user_location, D(m=15000.0)))
        
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

        print(f"   [DB] 📦 Feed generado con éxito: {len(db_products)} elementos.")
        return db_products

    def _parse_gemini_json_response(self, text_response: str) -> Dict[str, Any]:
        """Limpia el markdown, decodifica el JSON y normaliza los saltos de línea."""
        if not text_response:
            return {"products": [], "error": "Respuesta vacía."}
            
        try:
            clean_text = text_response.strip()
            if clean_text.startswith('```json'): 
                clean_text = clean_text[7:]
            if clean_text.startswith('```'): 
                clean_text = clean_text[3:]
            if clean_text.endswith('```'): 
                clean_text = clean_text[:-3]
                
            json_result = json.loads(clean_text.strip(), strict=False)
            
            if "products" in json_result and isinstance(json_result["products"], list):
                for product in json_result["products"]:
                    if "description" in product and isinstance(product["description"], str):
                        desc = product["description"]
                        desc = re.sub(r' *(\n)+ *', r'\1', desc)
                        desc_normalizada = re.sub(r'(?<!\n)\n(?!\n)', '\n\n', desc)
                        product["description"] = desc_normalizada.strip()

            print(f"[ATLAS PARSE RESPONSE]: {json_result}")
            return json_result
            
        except json.JSONDecodeError as e:
            print(f"[ATLAS PARSE ERROR]: {e} | Text: {text_response}")
            return {"products": [], "error": "Atlas no pudo procesar la imagen correctamente."}

    def _build_excel_json_prompt(self, subcategories: List[Dict[str, Any]]) -> str:
        categories_str = json.dumps(subcategories, ensure_ascii=False)
        return f"""
        Eres 'Atlas', el motor de IA de inventario de CartMaker.
        Tu única tarea es mapear un listado de productos rústicos al formato oficial del sistema.
        
        REGLAS DE RENDIMIENTO CRÍTICAS:
        1. Responde EXCLUSIVAMENTE con el objeto JSON solicitado, sin bloques de código Markdown.
        2. Mapea la columna que mejor represente el nombre, descripción y precio de venta.
        3. Si no hay descripción en el origen, redacta una estrictamente corta (MÁXIMO 120 caracteres, un solo párrafo). NO te extiendas.
        4. Asigna el subcategory_id correcto usando el catálogo suministrado.
        
        ESTRUCTURA:
        {{
            "products": [
                {{"name": "Nombre", "description": "Texto corto.", "price": 10.5, "subcategory_id": 1}}
            ]
        }}
        
        CATÁLOGO DE CATEGORÍAS VÁLIDAS:
        {categories_str}
        """

    async def analyze_processed_json_products_async(self, raw_products_json: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Procesa datos pre-formateados de Excel."""
        try:
            subcategories = await self._get_available_subcategories()
            prompt = self._build_excel_json_prompt(subcategories)
            data_payload = json.dumps(raw_products_json, ensure_ascii=False)
            
            messages = [
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"DATASET A PROCESAR:\n{data_payload}"}
            ]
            
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.3
            )
            return self._parse_gemini_json_response(response.choices[0].message.content)
        except Exception as e:
            print(f"[ATLAS FAST-EXCEL ERROR]: {e}")
            return {"products": [], "error": "Atlas tardó demasiado en responder."}

    # =========================================================================
    # EJECUCIÓN FÍSICA DE HERRAMIENTAS (CHAT BOT LOGIC)
    # =========================================================================
    
    def _execute_search(self, args: Dict[str, Any]) -> Dict[str, Any]:
        raw_query = args.get('query', '')
        max_dist = args.get('max_distancia', 15000.0)
        sort_by = args.get('sort_by', 'relevance')
        price_order = args.get('orden_precio')
        
        # 💡 LEEMOS EL PERMISO DEL LLM
        buscar_en_todas = args.get('buscar_en_todas_las_zonas', False)
        
        print(f"   [DB] 🎯 [ETAPA 1] Buscando en Ubicación Principal -> Query: '{raw_query}'")

        engine = ProductSearchEngine(lat=self.user_lat, lng=self.user_lng, user=self.user, seed=self.seed)
        qs = engine._get_base_active_queryset()
        qs = engine._annotate_proximity_flag(qs).filter(store__location__coordinates__distance_lte=(engine.user_location, D(m=max_dist)))

        word_queries = []
        if raw_query:
            search_terms = raw_query.strip().split()
            for term in search_terms:
                if len(term) > 2:
                    term_filter = (
                        Q(product__name__icontains=term) | Q(product__description__icontains=term) |
                        Q(product__category__name__icontains=term) | Q(store__company__name__icontains=term)
                    )
                    word_queries.append(term_filter)
            
            if word_queries:
                global_search_filter = reduce(operator.and_, word_queries)
                qs = qs.filter(global_search_filter).distinct()

        qs = engine._apply_feed_sorting(qs, sort_by, price_order)
        
        primary_results = []
        seen_primary = set()
        for item in qs[:15]: 
            item_id_str = str(item.id)
            if item_id_str not in seen_primary:
                json_item = item.get_json()
                json_item['nearest_saved_location_name'] = "Tu ubicación actual"
                primary_results.append(json_item)
                seen_primary.add(item_id_str)
            if len(primary_results) == 5:
                break

        # ⚡ Si hay en la zona principal, salimos victoriosos.
        if primary_results:
            print(f"   [DB] ✅ Éxito en zona principal. Retornando {len(primary_results)} ítems.")
            return {"type": "results", "data": primary_results}

        # 💡 LÓGICA DE CONFIRMACIÓN: Pedimos permiso SI tiene otras zonas Y NO ha autorizado todavía
        otras_zonas = [loc.get('name') for loc in self.user_locations if abs(float(loc.get('latitude', 0.0)) - self.user_lat) >= 0.001]
        
        if otras_zonas and not buscar_en_todas:
            print(f"   [DB] ⚠️ Cero resultados. Pidiendo confirmación al usuario para las otras zonas.")
            return {
                "type": "ask_confirmation", 
                "message": f"NO hay stock en la zona actual. Pregúntale si desea que busques en sus otras zonas guardadas. NO INVENTES PRODUCTOS.",
                "zonas": otras_zonas,
                "query": raw_query
            }

        # 🚀 ETAPA 2 RESTAURADA: CONTINGENCIA MULTI-ZONA (Solo corre si autorizó o si no tiene más zonas)
        print(f"   [DB] ⚠️ Permiso concedido. Iniciando escaneo en TODAS las direcciones...")
        all_consolidated_products = []
        seen_inventory_ids = set()

        for loc in self.user_locations:
            loc_lat = float(loc.get('latitude', 0.0))
            loc_lng = float(loc.get('longitude', 0.0))
            loc_name = loc.get('name', 'Otra dirección')

            if abs(loc_lat - self.user_lat) < 0.001 and abs(loc_lng - self.user_lng) < 0.001:
                continue

            engine_fallback = ProductSearchEngine(lat=loc_lat, lng=loc_lng, user=self.user, seed=self.seed)
            qs_fb = engine_fallback._get_base_active_queryset()
            qs_fb = engine_fallback._annotate_proximity_flag(qs_fb).filter(store__location__coordinates__distance_lte=(engine_fallback.user_location, D(m=max_dist)))

            if raw_query and word_queries:
                qs_fb = qs_fb.filter(global_search_filter).distinct()

            qs_fb = engine_fallback._apply_feed_sorting(qs_fb, sort_by, price_order)
            
            fallback_count = 0
            for item in qs_fb[:10]:
                item_id_str = str(item.id)
                if item_id_str not in seen_inventory_ids:
                    seen_inventory_ids.add(item_id_str)
                    json_item = item.get_json()
                    json_item['nearest_saved_location_name'] = loc_name
                    all_consolidated_products.append(json_item)
                    fallback_count += 1
                if fallback_count == 3:
                    break

        print(f"   [DB] 📦 Contingencia Multi-Zona completada. Hallados: {len(all_consolidated_products)} ítems.")
        if all_consolidated_products:
            return {"type": "results", "data": all_consolidated_products}
        else:
            return {"type": "not_found", "message": f"CERO RESULTADOS para '{raw_query}' en TODAS las zonas."}

    def _execute_recommendations(self, args: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Algoritmo de recomendación nativo in-memory basado en engagement fresco."""
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

    # =========================================================================
    # CHAT LOOP RECURSIVO CON MANEJO DE HISTORIAL (OPENAI STANDARD)
    # =========================================================================
    
    @sync_to_async
    def _get_thread_history(self, thread_id: int) -> List[Dict[str, Any]]:
        # 💡 OPTIMIZACIÓN 1: Bajamos el límite a 6 mensajes (las últimas 3 interacciones)
        messages = AtlasMessage.objects.filter(conversation_id=thread_id).order_by('-creation')[:6]
        messages = list(messages)[::-1]
        
        history = [{"role": "system", "content": self.chat_system_instruction}]
        for msg in messages:
            role = 'user' if msg.origin == self.ORIGIN_USER else 'assistant'
            
            # 💡 OPTIMIZACIÓN 2: Truncamiento de Tokens. 
            # Cortamos a 400 caracteres. Da suficiente contexto sin gastar tokens extra.
            content = msg.text[:1500] + "... [Texto truncado por el sistema]" if len(msg.text) > 1500 else msg.text
            
            # (Aquí mantenemos el Truco Ninja de la respuesta anterior)
            if msg.origin == self.ORIGIN_AI and getattr(msg, 'product_ids', None):
                content = f"[Nota del Sistema: Los datos de esta respuesta fueron extraídos de la base de datos mediante herramientas]\n{content}"
                
            history.append({"role": role, "content": content})
            
        return history

    @sync_to_async
    # 💡 AÑADIMOS EL PARÁMETRO action_command
    def _save_message(self, thread_id: int, origin: int, text: str, product_ids: List[str] = None, action_command: dict = None) -> AtlasMessage:
        msg = AtlasMessage.objects.create(
            conversation_id=thread_id, 
            origin=origin, 
            text=text,
            product_ids=product_ids or [],
            action_command=action_command # 💡 LO GUARDAMOS EN LA BD
        )
        print(f"💾 [DB] Mensaje guardado | Hilo: {thread_id} | Origen: {origin}")
        return msg

    async def send_chat_message_async(self, thread_id: int, user_text: str, image_base64: str = None) -> Dict[str, Any]:
        """Orquestador de ejecución recursiva de Function Calling compatible con OpenAI."""
        try:
            print("\n" + "="*60)
            print(f"🚀 [01. START] Hilo: {thread_id} | Input: '{user_text}'")
            print("="*60)
            
            history = await self._get_thread_history(thread_id)
            print(f"📜 [HISTORY] Se cargaron {len(history)} mensajes al contexto.")
            
            # Guardamos el texto base en BD (no saturamos PostgreSQL guardando el Base64 gigante)
            await self._save_message(thread_id, self.ORIGIN_USER, user_text, [])
            
            if image_base64:
                print(f"📸 [IMAGE] Imagen detectada en el request. Inyectando visual al contexto...")
                
                instruccion_forzada = (
                    "\n\n[INSTRUCCIÓN ESTRICTA DEL SISTEMA: He adjuntado una imagen. "
                    "Analízala visualmente, deduce qué producto genérico es (ej. 'sillon', 'silla', 'escritorio') "
                    "y EJECUTA INMEDIATAMENTE la herramienta 'buscar_productos_inventario'. "
                    "TIENES ESTRICTAMENTE PROHIBIDO generar texto conversacional antes de llamar a la herramienta. "
                    "Haz la búsqueda YA.]"
                )
                
                history.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_text + instruccion_forzada},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                    ]
                })
            else:
                # 💡 TRUCO NINJA 2: Obligamos a la IA a buscar antes de hablar
                instruccion_forzada = (
                    "\n\n[INSTRUCCIÓN ESTRICTA DEL SISTEMA: "
                    "1. Si el usuario te pide buscar NUEVOS productos o cambia de tema, ES OBLIGATORIO invocar la herramienta de búsqueda. "
                    "2. Si el usuario hace preguntas de seguimiento sobre los productos que le ACABAS DE MOSTRAR en el mensaje anterior (ej. '¿qué tan cerca están?', '¿cuál es mejor?'), "
                    "RESPONDE DIRECTAMENTE ANALIZANDO EL HISTORIAL RECIENTE, SIN volver a ejecutar la herramienta de búsqueda. "
                    "3. PROHIBIDO inventar datos que no estén en tu historial o en el JSON de las herramientas.]"
                )
                history.append({"role": "user", "content": user_text + instruccion_forzada})
            
            print(f"🧠 [02. LLM REQUEST] Solicitando intenciones (Temp: 0.2)...")
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=history,
                tools=_get_tools_schema(),
                tool_choice="auto",
                temperature=0.2 # 💡 Temperatura fría estructural para liquidar alucinaciones
            )
            
            choice = response.choices[0]
            injected_products = []
            action_command = None

            print(f"🤖 [03. LLM INTENT] ¿Llamó herramientas?: {bool(choice.message.tool_calls)}")

            # Bucle Recursivo de Ejecución Logística
            while choice.message.tool_calls:
                tool_calls = choice.message.tool_calls
                history.append(choice.message)
                
                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    function_args_str = tool_call.function.arguments
                    function_args = json.loads(function_args_str)
                    
                    print(f"\n   ⚙️ [04. TOOL EXECUTION] Función invocada: {function_name}")
                    print(f"   📥 [TOOL ARGS] {function_args_str}")
                    
                    tool_result_payload = {}
                    
                    if function_name == "buscar_productos_inventario":
                        db_response = await sync_to_async(self._execute_search)(function_args)
                        
                        # 💡 MANEJO DEL NUEVO FORMATO DE RESPUESTA
                        if db_response.get("type") == "results":
                            db_products = db_response["data"]
                            
                            # (Aquí va tu código actual de deduplicación)
                            if injected_products is None:
                                injected_products = []
                            existing_ids = {str(p.get('id')) for p in injected_products}
                            for p in db_products:
                                pid = str(p.get('id'))
                                if pid not in existing_ids:
                                    injected_products.append(p)
                                    existing_ids.add(pid)
                                    
                            datos = [f"[{p.get('product', {}).get('name')}] a ${p.get('custom_price')} en '{p.get('company_name')}'" for p in db_products]
                            tool_result_payload = {"status": "success", "data": datos}

                        elif db_response.get("type") == "ask_confirmation":
                            # 💡 LE DECIMOS AL FRONTEND QUE MUESTRE LOS BOTONES
                            action_command = {
                                "action": "ASK_ZONE_CONFIRMATION",
                                "query_to_search": db_response.get("query"),
                                "zonas": db_response.get("zonas")
                            }
                            tool_result_payload = {"status": "not_found", "message": db_response.get("message")}
                            
                        else:
                            tool_result_payload = {"status": "not_found", "message": db_response.get("message")}
                        
                    elif function_name == "explorar_feed_personalizado":
                        db_products = await sync_to_async(self._execute_personalized_feed)(function_args)
                        injected_products = db_products 
                        
                        if db_products:
                            datos = [f"{p.get('product',{}).get('name')} a {p.get('custom_price', p.get('product',{}).get('price', 0))}$ en {p.get('company_name')}" for p in db_products]
                            tool_result_payload = {"status": "success", "data": datos}
                        else:
                            tool_result_payload = {"status": "not_found", "message": "No hay productos afines en este momento."}

                    elif function_name == "sugerir_productos_relacionados":
                        db_recommendations = await sync_to_async(self._execute_recommendations)(function_args)
                        injected_products = db_recommendations
                        
                        if db_recommendations:
                            datos = [f"{p.get('product',{}).get('name')} a {p.get('custom_price', p.get('product',{}).get('price', 0))}$ en {p.get('company_name')}" for p in db_recommendations]
                            tool_result_payload = {"status": "success", "data": datos}
                        else:
                            tool_result_payload = {"status": "not_found", "message": "No hay recomendaciones cruzadas."}
                        
                    payload_string = json.dumps(tool_result_payload)
                    print(f"   📤 [TOOL RESPONSE TO LLM] {payload_string}")

                    history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": function_name,
                        "content": payload_string
                    })
                
                print(f"\n🔄 [05. LLM REDRAFT] Re-inyectando verdades a la IA para redacción...")
                response = await self.client.chat.completions.create(
                    model=self.model_name,
                    messages=history,
                    tools=_get_tools_schema(),
                    temperature=0.5
                )
                choice = response.choices[0]
            
            ai_final_text = choice.message.content
            print(f"\n✅ [06. FINAL TEXT RENDER] {ai_final_text[:80]}...\n")
            
            # Mapeo relacional de IDs para persistir los carruseles históricos
            p_ids = [str(p['id']) for p in injected_products] if injected_products else []
            saved_msg = await self._save_message(thread_id, self.ORIGIN_AI, ai_final_text, p_ids, action_command)
            
            # 💡 NUEVO: TRACKING DE PRODUCTOS INYECTADOS POR ATLAS
            if injected_products:
                # 1. Recuperamos qué fue lo que Atlas buscó realmente (las llamadas a funciones)
                ai_search_terms = []
                for tool_call in tool_calls:
                    if tool_call.function.name == "buscar_productos_inventario":
                        try:
                            args = json.loads(tool_call.function.arguments)
                            if 'query' in args:
                                ai_search_terms.append(args['query'])
                        except json.JSONDecodeError:
                            pass
                
                # Juntamos los términos (ej. "chucheria, snack")
                keywords_str = ", ".join(ai_search_terms) if ai_search_terms else "Búsqueda visual/contextual"

                # 2. Creamos los logs de forma masiva (Bulk Create) para no golpear la BD uno por uno
                logs_to_create = []
                now = timezone.now()
                
                for product_data in injected_products:
                    # Asumimos que product_data tiene la estructura que retorna _execute_search (con 'id' del InventoryItem)
                    item_id = product_data.get('id')
                    if item_id:
                        logs_to_create.append(
                            ProductViewLog(
                                inventory_item_id=item_id,
                                client_id=self.user.id if self.user and self.user.is_authenticated else None,
                                start_time=now,
                                # Datos de la IA:
                                origin_source='atlas',
                                search_prompt=user_text[:150], # Truncamos por seguridad de BD
                                ai_keywords=keywords_str[:150],
                                atlas_message_id=saved_msg.id
                            )
                        )
                
                # Ejecutamos el guardado masivo en una transacción asíncrona segura
                if logs_to_create:
                    await sync_to_async(ProductViewLog.objects.bulk_create)(logs_to_create, ignore_conflicts=True)
                    print(f"📊 [ANALYTICS] {len(logs_to_create)} logs de descubrimiento registrados vía Atlas.")

            return {
                "success": True,
                "response": ai_final_text,
                "message_id": saved_msg.id,
                "injected_products": injected_products,
                "action_command": action_command
            }
            
        except Exception as e:
            print(f"❌ [ATLAS COGNITIVE CRITICAL ERROR]: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": "Atlas está reestructurando sus algoritmos en este momento."}