import json
from typing import List, Dict, Any
from google import genai
from google.genai import types
from django.conf import settings
from asgiref.sync import sync_to_async
import re

from ..models import SubCategory, AtlasThread, AtlasMessage

class AtlasManager:
    """
    Controlador principal de Atlas (Integración con Google Gemini).
    Dios del Clean Code para el manejo de Visión e IA Conversacional en CartMaker.
    """
    
    # Constantes de origen (Ajusta estos números si tu MessageOrigin usa otros valores)
    ORIGIN_USER = 1 
    ORIGIN_AI = 2

    def __init__(self):
        # 1. Autenticación creando el Cliente (El nuevo estándar unificado)
        if not hasattr(settings, 'GEMINI_API_KEY') or not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY no está configurada en settings.py")
        
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        
        # Guardamos el nombre del modelo que usaremos en las llamadas
        self.model_name = 'gemini-flash-latest'
        # self.model_name = "gemini-2.5-flash"
        # self.model_name = 'gemini-2.5-flash-exp'
        
        # 2. System Prompt General para darle personalidad a Atlas en el chat
        chat_system_instruction = (
            "Eres 'Atlas', el asistente virtual experto e inteligente de CartMaker. "
            "Ayudas a los dueños de negocios a gestionar su inventario, entender métricas "
            "y organizar sus productos. Responde de manera profesional, concisa y amigable. "
            "Si no sabes algo, admítelo, no inventes datos."
        )
        
        # 3. Configuración para la generación de texto
        self.chat_config = types.GenerateContentConfig(
            system_instruction=chat_system_instruction,
            temperature=0.7, # Un poco de creatividad para que suene más natural
        )

    # =========================================================================
    # SECCIÓN 1: ESCANEO DE IMÁGENES (VISIÓN)
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

    async def analyze_image_for_multiple_products_async(self, image_data: bytes, mime_type: str) -> Dict[str, Any]:
        """Endpoint para escanear múltiples productos en una sola foto."""
        try:
            subcategories = await self._get_available_subcategories()
            prompt = self._build_multi_product_analysis_prompt(subcategories)
            
            image_part = types.Part.from_bytes(data=image_data, mime_type=mime_type)
            
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=[prompt, image_part]
            )
            # Reutilizamos tu parseador a prueba de balas
            return self._parse_gemini_json_response(response.text)
        except Exception as e:
            print(f"[ATLAS MULTI-VISION ERROR]: {e}")
            return {"products": [], "error": "Atlas no pudo procesar el lote de productos."}

    def _parse_gemini_json_response(self, text_response: str) -> Dict[str, Any]:
        """Limpia el markdown, decodifica el JSON y normaliza los saltos de línea."""
        try:
            clean_text = text_response.strip()
            if clean_text.startswith('```json'): 
                clean_text = clean_text[7:]
            if clean_text.startswith('```'): 
                clean_text = clean_text[3:]
            if clean_text.endswith('```'): 
                clean_text = clean_text[:-3]
                
            json_result = json.loads(clean_text.strip(), strict=False)
            
            # 💡 PROTECCIÓN ABSOLUTA: Forzar \n\n programáticamente
            if "products" in json_result and isinstance(json_result["products"], list):
                for product in json_result["products"]:
                    if "description" in product and isinstance(product["description"], str):
                        desc = product["description"]
                        
                        # 1. Limpiamos espacios basura que queden pegados a los saltos de línea
                        desc = re.sub(r' *(\n)+ *', r'\1', desc)
                        
                        # 2. Expresión regular que busca un '\n' SOLITARIO 
                        # (que no tenga otro \n antes ni después) y lo duplica a '\n\n'
                        desc_normalizada = re.sub(r'(?<!\n)\n(?!\n)', '\n\n', desc)
                        
                        product["description"] = desc_normalizada.strip()

            print(f"[ATLAS PARSE RESPONSE]: {json_result}")
            # Ahora verás en consola los '\n\n' perfectos
            return json_result
            
        except json.JSONDecodeError as e:
            print(f"[ATLAS PARSE ERROR]: {e} | Text: {text_response}")
            return {"products": [], "error": "Atlas no pudo procesar la imagen correctamente."}

    async def analyze_image_for_products_async(self, image_data: bytes, mime_type: str) -> Dict[str, Any]:
        """Endpoint principal para escanear inventario a través de imágenes."""
        try:
            subcategories = await self._get_available_subcategories()
            prompt = self._build_product_analysis_prompt(subcategories)
            
            # NUEVO SDK: Formateamos los bytes de la imagen en un objeto Part nativo
            image_part = types.Part.from_bytes(data=image_data, mime_type=mime_type)
            
            # NUEVO SDK: Llamada usando el cliente asíncrono (.aio)
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=[prompt, image_part]
            )
            return self._parse_gemini_json_response(response.text)
        except Exception as e:
            print(f"[ATLAS VISION ERROR]: {e}")
            return {"products": [], "error": "Error de conexión con el núcleo visual de Atlas."}
        
    def _build_excel_json_prompt(self, subcategories: List[Dict[str, Any]]) -> str:
        """Prompt ultra optimizado para procesar JSON estructurado a alta velocidad."""
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
        """Procesa datos pre-formateados por Python a velocidad relámpago."""
        try:
            subcategories = await self._get_available_subcategories()
            prompt = self._build_excel_json_prompt(subcategories)
            
            # Pasamos los datos como texto JSON compacto estructurado, no como archivo adjunto visual
            data_payload = json.dumps(raw_products_json, ensure_ascii=False)
            
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=[prompt, f"DATASET A PROCESAR:\n{data_payload}"]
            )
            return self._parse_gemini_json_response(response.text)
        except Exception as e:
            print(f"[ATLAS FAST-EXCEL ERROR]: {e}")
            return {"products": [], "error": "Atlas tardó demasiado en responder."}

    # =========================================================================
    # SECCIÓN 2: CHAT CONTEXTUAL (NLP)
    # =========================================================================

    @sync_to_async
    def _get_thread_history(self, thread_id: int) -> List[types.Content]:
        """Extrae el historial de la BD y lo formatea al tipo nativo de Gemini."""
        messages = AtlasMessage.objects.filter(conversation_id=thread_id).order_by('creation')
        gemini_history = []
        for msg in messages:
            role = 'user' if msg.origin == self.ORIGIN_USER else 'model'
            
            # NUEVO SDK: El historial exige objetos Content y Part
            content_block = types.Content(
                role=role, 
                parts=[types.Part.from_text(text=msg.text)]
            )
            gemini_history.append(content_block)
            
        return gemini_history

    @sync_to_async
    def _save_message(self, thread_id: int, origin: int, text: str) -> AtlasMessage:
        """Guarda un nuevo mensaje en la base de datos."""
        return AtlasMessage.objects.create(conversation_id=thread_id, origin=origin, text=text)

    async def send_chat_message_async(self, thread_id: int, user_text: str) -> Dict[str, Any]:
        """Envía un mensaje al hilo, mantiene memoria y guarda la respuesta de Atlas."""
        try:
            # 1. Recuperamos la historia pasada de la BD
            history = await self._get_thread_history(thread_id)
            
            # 2. NUEVO SDK: Inicializamos la sesión de chat con el cliente
            chat_session = self.client.aio.chats.create(
                model=self.model_name,
                history=history,
                config=self.chat_config
            )
            
            # 3. Guardamos el mensaje del usuario en nuestra BD
            await self._save_message(thread_id, self.ORIGIN_USER, user_text)
            
            # 4. Enviamos el mensaje a Google (Asíncrono)
            response = await chat_session.send_message(user_text)
            ai_text = response.text
            
            # 5. Guardamos la respuesta de Atlas en nuestra BD
            saved_msg = await self._save_message(thread_id, self.ORIGIN_AI, ai_text)
            
            return {
                "success": True,
                "response": ai_text,
                "message_id": saved_msg.id
            }
            
        except Exception as e:
            print(f"[ATLAS CHAT ERROR]: {e}")
            return {"success": False, "error": "Atlas está fuera de línea en este momento."}