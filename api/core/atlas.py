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
                    "🚨 REGLA: Si el usuario pide categorías amplias ('comida', 'muebles'), "
                    "invoca esta herramienta en paralelo con 2 o 3 términos concretos."
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
                    "o cuando pida una canasta/lista de compras con varios artículos. "
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
                "name": "explorar_feed_personalizado",
                "description": "Sugerencias abstractas basadas en el historial del usuario. Usar SOLO para preguntas totalmente abiertas sin productos ni categorías.",
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
        
        self.model_name = 'google/gemini-2.5-flash'
        self.user_lat = user_lat
        self.user_lng = user_lng
        self.user_locations = user_locations or []
        self.user = user
        self.seed = seed

        self.chat_system_instruction = f"""
            # ROL E IDENTIDAD CORE
            Eres 'Atlas', la inteligencia artificial de élite y el corazón operativo de CartMaker, la red de comercio local líder en Venezuela.
            No eres un simple bot de respuestas. Eres un personal shopper de primer nivel y un estratega de compras. Conoces los inventarios reales de cada tienda, sus precios exactos, su distancia física y si están abiertas ahorita. Tu propósito es resolver compras reales de manera rápida, transparente y óptima.

            # PERSONALIDAD Y TONO
            - Voz venezolana educada, moderna, ágil y empática. Usa expresiones naturales sutiles ("cuadrar", "resolver", "de una", "chévere", "fino") sin caer en caricaturas ni exceso de informalidad.
            - 🚨 PROHIBIDO llamar al usuario: mi pana, convive, mano, compa, hermano o bro.
            - NUNCA inventes productos, tiendas, distancias o precios. Si no vino en el JSON de la herramienta, NO EXISTE.

            # CÓMO ANALIZAR LA TRÍADA (PRECIO, DISTANCIA, REPUTACIÓN)
            La herramienta te devolverá datos exactos calculados matemáticamente:
            - **Precio y Oferta:** Tienes el precio efectivo y el % de descuento si aplica.
            - **Distancia:** En metros o kilómetros exactos respecto a la ubicación del usuario.
            - **Estado Operativo:** Sabes si la tienda está ABIERTA o CERRADA en este momento.
            - **Reputación:** Rating bayesiano de 1 a 5 estrellas y si cuenta con insignia Platinum.

            Explica siempre los trade-offs con números reales:
            - "Te conseguí el repuesto a 450 m en [Tienda A] por $12 y están abiertos ahorita. Si quieres ahorrar, en [Tienda B] lo tienen en $9, pero te queda a 4.2 km".

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
        
        # 1. Búsqueda con score matemático de compra
        candidates = engine.search_purchase_candidates(
            query=raw_query,
            max_distance_meters=max_dist,
            limit=6,
            location_label="Tu ubicación actual",
            mode=mode
        )

        if candidates:
            return {"type": "results", "data": candidates}

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
            if len(fallback_results) >= 6:
                break

        if fallback_results:
            return {"type": "results", "data": fallback_results}

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
        
        history.append({
            "role": "system", 
            "content": f"CONTEXTO ESPACIAL DEL USUARIO:\n{ubicaciones_str}"
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
            
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=history,
                tools=_get_tools_schema(),
                tool_choice="auto",
                temperature=0.2,
                extra_body={"session_id": f"cartmaker-atlas-thread-{thread_id}"}
            )
            
            choice = response.choices[0]
            injected_products = []
            action_command = None

            while choice.message.tool_calls:
                tool_calls = choice.message.tool_calls
                history.append(choice.message)
                
                for tool_call in tool_calls:
                    fn_name = tool_call.function.name
                    fn_args = json.loads(tool_call.function.arguments)
                    tool_payload = {}

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
                                p_dist = triad.get('distance_m', it.get('distance_meters', 0))
                                dist_label = f"{int(p_dist)} m" if p_dist < 1000 else f"{round(p_dist/1000, 1)} km"
                                p_open = "ABIERTO AHORA" if triad.get('open_now') else "CERRADO"
                                p_plat = " (Tienda Platinum)" if triad.get('platinum') else ""
                                p_off = f" [Descuento: {triad.get('offer_pct')}%]" if triad.get('offer_pct') else ""
                                
                                formatted_data.append(
                                    f"• [{p_name}] a ${p_price}{p_off} en '{it.get('store_name')}' ({it.get('company_name')}{p_plat}) | "
                                    f"Distancia: {dist_label} de {it.get('nearest_saved_location_name')} | "
                                    f"Rating: {triad.get('rating', it.get('avg_rating'))}/5 | Estado: {p_open}"
                                )
                            tool_payload = {"status": "success", "candidatos_reales": formatted_data}

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
                            "distancia_comercio_principal_m": store_info.get('distance_meters') if store_info else None,
                            "completados_en_otras_tiendas": plan.get('filled_elsewhere', []),
                            "ingredientes_sin_stock": plan.get('missing_queries', []),
                            "total_estimado_usd": plan.get('estimated_total_usd', 0.0)
                        }
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

            ai_final_text = choice.message.content
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