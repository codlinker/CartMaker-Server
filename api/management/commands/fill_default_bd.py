import json
import os
from decimal import Decimal
from django.conf import settings
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
# Importante: Añadimos SubCategory a la importación
from api.models import Category, SubCategory, MerchantPlan, Announcement, Mall, CompanyCategory

class Command(BaseCommand):
    help = "Puebla la base de datos con registros por defecto optimizados con bulk_create sin duplicar datos."

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.MIGRATE_HEADING('Iniciando carga de datos por defecto...'))
        
        self._poblar_categorias()
        self._poblar_planes()
        self._poblar_anuncios()
        self._poblar_malls()
        self._poblar_categorias_empresa()

        self.stdout.write(self.style.SUCCESS('Carga de datos finalizada exitosamente.'))

    def _bulk_create_if_not_exists(self, model, data_list, unique_field):
        """
        Método helper centralizado. Recibe el modelo, la lista de diccionarios 
        con la data, y el campo que define si el registro ya existe (ej: 'name').
        """
        # Obtenemos los valores existentes de la BD en un set (búsqueda O(1))
        existing_values = set(model.objects.values_list(unique_field, flat=True))
        
        # Filtramos solo los registros que NO existen en la base de datos
        objects_to_create = [
            model(**data) for data in data_list if data[unique_field] not in existing_values
        ]
        
        if objects_to_create:
            model.objects.bulk_create(objects_to_create)
            self.stdout.write(self.style.SUCCESS(f'  [+] Se crearon {len(objects_to_create)} registros en {model.__name__}.'))
        else:
            self.stdout.write(self.style.WARNING(f'  [-] Sin cambios en {model.__name__}. Los registros ya existen.'))

    def _poblar_categorias_empresa(self):
        self.stdout.write("Verificando CompanyCategories (Rubros comerciales)...")
        
        company_categories_data = [
            # --- Sector Automotriz ---
            {'name': 'Repuestos Automotrices'},
            {'name': 'Servicios Automotrices'},
            
            # --- Alimentación y Bebidas ---
            {'name': 'Restaurante'},
            {'name': 'Supermercado'},
            {'name': 'Panadería y Pastelería'},
            {'name': 'Licorería'},
            
            # --- Salud, Belleza y Cuidado ---
            {'name': 'Farmacia'},
            {'name': 'Salud y Belleza'},
            {'name': 'Mascotas'},
            {'name': 'Lavandería'},
            
            # --- Tecnología y Hogar ---
            {'name': 'Tecnología'},
            {'name': 'Electrodomésticos'},
            {'name': 'Hogar y Muebles'},
            {'name': 'Ferretería'},
            {'name': 'Construcción y Materiales'},
            
            # --- Comercio y Retail ---
            {'name': 'Moda y Ropa'},
            {'name': 'Joyería y Relojería'},
            {'name': 'Juguetería'},
            {'name': 'Deportes'},
            {'name': 'Papelería y Oficina'},
            {'name': 'Floristería y Jardinería'},
            {'name': 'Arte y Artesanías'},
            
            # --- Servicios Profesionales y Financieros ---
            {'name': 'Servicios Financieros'},
            {'name': 'Inmobiliaria'},
            {'name': 'Educación'},
            
            # --- Logística, Turismo y Eventos ---
            {'name': 'Transporte y Logística'},
            {'name': 'Turismo y Hotelería'},
            {'name': 'Entretenimiento y Eventos'},
            {'name': 'Agroindustria y Campo'},
        ]
        
        self._bulk_create_if_not_exists(CompanyCategory, company_categories_data, unique_field='name')

    def _poblar_categorias(self):
        self.stdout.write("Verificando Categories y SubCategories de Productos...")
        
        # Estructura centralizada con rutas completamente hardcodeadas para fácil edición futura.
        catalogo_estructura = {
            'Alimentos y Bebidas (Supermercado)': {
                'img_url': 'static/img/categories/alimentos_y_bebidas.jpg',
                'subcategories': [
                    {'name': 'Despensa y Víveres', 'img_url': 'static/img/categories/sub_categories/despensa_y_viveres.jpg'},
                    {'name': 'Frescos', 'img_url': 'static/img/categories/sub_categories/frescos.jpg'},
                    {'name': 'Charcutería y Lácteos', 'img_url': 'static/img/categories/sub_categories/charcuteria_y_lacteos.jpg'},
                    {'name': 'Bebidas', 'img_url': 'static/img/categories/sub_categories/bebidas.jpg'},
                    {'name': 'Licores', 'img_url': 'static/img/categories/sub_categories/licores.jpg'},
                    {'name': 'Snacks y Dulces', 'img_url': 'static/img/categories/sub_categories/snacks_y_dulces.jpg'},
                    {'name': 'Limpieza del Hogar', 'img_url': 'static/img/categories/sub_categories/limpieza_del_hogar.jpg'},
                ]
            },
            'Tecnología y Electrónica': {
                'img_url': 'static/img/categories/tecnologia_y_electronica.jpg',
                'subcategories': [
                    {'name': 'Celulares y Tablets', 'img_url': 'static/img/categories/sub_categories/celulares_y_tablets.jpg'},
                    {'name': 'Computación', 'img_url': 'static/img/categories/sub_categories/computacion.jpg'},
                    {'name': 'Periféricos y Accesorios', 'img_url': 'static/img/categories/sub_categories/perifericos_y_accesorios.jpg'},
                    {'name': 'TV, Audio y Video', 'img_url': 'static/img/categories/sub_categories/tv_audio_y_video.jpg'},
                    {'name': 'Videojuegos y Consolas', 'img_url': 'static/img/categories/sub_categories/videojuegos_y_consolas.jpg'},
                    {'name': 'Wearables', 'img_url': 'static/img/categories/sub_categories/wearables.jpg'},
                    {'name': 'Cámaras y Fotografía', 'img_url': 'static/img/categories/sub_categories/camaras_y_fotografia.jpg'},
                ]
            },
            'Moda y Accesorios': {
                'img_url': 'static/img/categories/moda_y_accesorios.jpg',
                'subcategories': [
                    {'name': 'Ropa Femenina', 'img_url': 'static/img/categories/sub_categories/ropa_femenina.jpg'},
                    {'name': 'Ropa Masculina', 'img_url': 'static/img/categories/sub_categories/ropa_masculina.jpg'},
                    {'name': 'Ropa Infantil', 'img_url': 'static/img/categories/sub_categories/ropa_infantil.jpg'},
                    {'name': 'Calzado', 'img_url': 'static/img/categories/sub_categories/calzado.jpg'},
                    {'name': 'Bolsos y Carteras', 'img_url': 'static/img/categories/sub_categories/bolsos_y_carteras.jpg'},
                    {'name': 'Accesorios y Joyería', 'img_url': 'static/img/categories/sub_categories/accesorios_y_joyeria.jpg'},
                ]
            },
            'Salud y Belleza': {
                'img_url': 'static/img/categories/salud_y_belleza.jpg',
                'subcategories': [
                    {'name': 'Cuidado Personal', 'img_url': 'static/img/categories/sub_categories/cuidado_personal.jpg'},
                    {'name': 'Skincare y Cuidado Facial', 'img_url': 'static/img/categories/sub_categories/skincare_y_cuidado_facial.jpg'},
                    {'name': 'Maquillaje', 'img_url': 'static/img/categories/sub_categories/maquillaje.jpg'},
                    {'name': 'Perfumería', 'img_url': 'static/img/categories/sub_categories/perfumeria.jpg'},
                    {'name': 'Farmacia y Bienestar', 'img_url': 'static/img/categories/sub_categories/farmacia_y_bienestar.jpg'},
                ]
            },
            'Hogar, Muebles y Jardín': {
                'img_url': 'static/img/categories/hogar_muebles_y_jardin.jpg',
                'subcategories': [
                    {'name': 'Electrodomésticos', 'img_url': 'static/img/categories/sub_categories/electrodomesticos.jpg'},
                    {'name': 'Muebles', 'img_url': 'static/img/categories/sub_categories/muebles.jpg'},
                    {'name': 'Dormitorio', 'img_url': 'static/img/categories/sub_categories/dormitorio.jpg'},
                    {'name': 'Baño', 'img_url': 'static/img/categories/sub_categories/bano.jpg'},
                    {'name': 'Decoración', 'img_url': 'static/img/categories/sub_categories/decoracion.jpg'},
                    {'name': 'Jardín y Exteriores', 'img_url': 'static/img/categories/sub_categories/jardin_y_exteriores.jpg'},
                ]
            },
            'Ferretería y Construcción': {
                'img_url': 'static/img/categories/ferreteria_y_construccion.jpg',
                'subcategories': [
                    {'name': 'Herramientas', 'img_url': 'static/img/categories/sub_categories/herramientas.jpg'},
                    {'name': 'Electricidad e Iluminación', 'img_url': 'static/img/categories/sub_categories/electricidad_e_iluminacion.jpg'},
                    {'name': 'Plomería', 'img_url': 'static/img/categories/sub_categories/plomeria.jpg'},
                    {'name': 'Materiales de Construcción', 'img_url': 'static/img/categories/sub_categories/materiales_de_construccion.jpg'},
                    {'name': 'Seguridad y Domótica', 'img_url': 'static/img/categories/sub_categories/seguridad_y_domotica.jpg'},
                ]
            },
            'Carros, Motos y Otros': {
                'img_url': 'static/img/categories/carros_motos_y_otros.jpg',
                'subcategories': [
                    {'name': 'Venta de Autos', 'img_url': 'static/img/categories/sub_categories/venta_de_autos.jpg'},
                    {'name': 'Venta de Motos', 'img_url': 'static/img/categories/sub_categories/venta_de_motos.jpg'},
                    {'name': 'Repuestos para Autos', 'img_url': 'static/img/categories/sub_categories/repuestos_para_autos.jpg'},
                    {'name': 'Lubricantes y Fluidos', 'img_url': 'static/img/categories/sub_categories/lubricantes_y_fluidos.jpg'},
                    {'name': 'Neumáticos y Rines', 'img_url': 'static/img/categories/sub_categories/neumaticos_y_rines.jpg'},
                    {'name': 'Accesorios para Vehículos', 'img_url': 'static/img/categories/sub_categories/accesorios_para_vehiculos.jpg'},
                    {'name': 'Motos', 'img_url': 'static/img/categories/sub_categories/motos.jpg'},
                ]
            },
            'Deportes y Fitness': {
                'img_url': 'static/img/categories/deportes_y_fitness.jpg',
                'subcategories': [
                    {'name': 'Fitness y Musculación', 'img_url': 'static/img/categories/sub_categories/fitness_y_musculacion.jpg'},
                    {'name': 'Ropa y Calzado Deportivo', 'img_url': 'static/img/categories/sub_categories/ropa_y_calzado_deportivo.jpg'},
                    {'name': 'Deportes Específicos', 'img_url': 'static/img/categories/sub_categories/deportes_especificos.jpg'},
                    {'name': 'Camping y Outdoors', 'img_url': 'static/img/categories/sub_categories/camping_y_outdoors.jpg'},
                ]
            },
            'Bebés y Maternidad': {
                'img_url': 'static/img/categories/bebes_y_maternidad.jpg',
                'subcategories': [
                    {'name': 'Pañales y Toallitas', 'img_url': 'static/img/categories/sub_categories/panales_y_toallitas.jpg'},
                    {'name': 'Lactancia y Alimentación', 'img_url': 'static/img/categories/sub_categories/lactancia_y_alimentacion.jpg'},
                    {'name': 'Paseo y Viaje', 'img_url': 'static/img/categories/sub_categories/paseo_y_viaje.jpg'},
                    {'name': 'Higiene y Cuidado del Bebé', 'img_url': 'static/img/categories/sub_categories/higiene_y_cuidado_del_bebe.jpg'},
                    {'name': 'Cuarto del Bebé', 'img_url': 'static/img/categories/sub_categories/cuarto_del_bebe.jpg'},
                ]
            },
            'Juegos y Juguetes': {
                'img_url': 'static/img/categories/juegos_y_juguetes.jpg',
                'subcategories': [
                    {'name': 'Juguetes para Bebés', 'img_url': 'static/img/categories/sub_categories/juguetes_para_bebes.jpg'},
                    {'name': 'Muñecas y Peluches', 'img_url': 'static/img/categories/sub_categories/munecas_y_peluches.jpg'},
                    {'name': 'Figuras de Acción', 'img_url': 'static/img/categories/sub_categories/figuras_de_accion.jpg'},
                    {'name': 'Juegos de Mesa y Rompecabezas', 'img_url': 'static/img/categories/sub_categories/juegos_de_mesa_y_rompecabezas.jpg'},
                    {'name': 'Bloques y Construcción', 'img_url': 'static/img/categories/sub_categories/bloques_y_construccion.jpg'},
                    {'name': 'Juguetes de Exterior', 'img_url': 'static/img/categories/sub_categories/juguetes_de_exterior.jpg'},
                ]
            },
            'Mascotas': {
                'img_url': 'static/img/categories/mascotas.jpg',
                'subcategories': [
                    {'name': 'Perros', 'img_url': 'static/img/categories/sub_categories/perros.jpg'},
                    {'name': 'Gatos', 'img_url': 'static/img/categories/sub_categories/gatos.jpg'},
                    {'name': 'Higiene y Salud Animal', 'img_url': 'static/img/categories/sub_categories/higiene_y_salud_animal.jpg'},
                ]
            },
            'Papelería, Oficina y Libros': {
                'img_url': 'static/img/categories/papeleria_oficina_y_libros.jpg',
                'subcategories': [
                    {'name': 'Útiles Escolares', 'img_url': 'static/img/categories/sub_categories/utiles_escolares.jpg'},
                    {'name': 'Oficina', 'img_url': 'static/img/categories/sub_categories/oficina.jpg'},
                    {'name': 'Libros', 'img_url': 'static/img/categories/sub_categories/libros.jpg'},
                ]
            },
            'Instrumentos Musicales': {
                'img_url': 'static/img/categories/instrumentos_musicales.jpg',
                'subcategories': [
                    {'name': 'Guitarras y Bajos', 'img_url': 'static/img/categories/sub_categories/guitarras_y_bajos.jpg'},
                    {'name': 'Teclados y Pianos', 'img_url': 'static/img/categories/sub_categories/teclados_y_pianos.jpg'},
                    {'name': 'Baterías y Percusión', 'img_url': 'static/img/categories/sub_categories/baterias_y_percusion.jpg'},
                    {'name': 'Instrumentos de Viento', 'img_url': 'static/img/categories/sub_categories/instrumentos_de_viento.jpg'},
                    {'name': 'Instrumentos de Cuerda', 'img_url': 'static/img/categories/sub_categories/instrumentos_de_cuerda.jpg'},
                    {'name': 'Audio Profesional y DJ', 'img_url': 'static/img/categories/sub_categories/audio_profesional_y_dj.jpg'},
                    {'name': 'Accesorios Musicales', 'img_url': 'static/img/categories/sub_categories/accesorios_musicales.jpg'},
                ]
            },
            'Otras Categorías (Varios)': {
        'img_url': 'static/img/categories/otras_categorias.jpg',
        'subcategories': [
            {'name': 'Otros', 'img_url': 'static/img/categories/sub_categories/otros.jpg'},
        ]
    }
}
        # 1. Preparar y crear Categorías Principales
        categories_data = [
            {'name': cat_name, 'img_url': cat_info['img_url']} 
            for cat_name, cat_info in catalogo_estructura.items()
        ]
        self._bulk_create_if_not_exists(Category, categories_data, unique_field='name')

        # 2. Extraer instancias de la BD para asociar los ForeignKeys
        db_categories = {
            cat.name: cat 
            for cat in Category.objects.filter(name__in=catalogo_estructura.keys())
        }

        # 3. Preparar Subcategorías iterando la estructura
        subcategories_data = []
        for cat_name, cat_info in catalogo_estructura.items():
            parent_instance = db_categories.get(cat_name)
            
            if parent_instance:
                for sub in cat_info['subcategories']:
                    subcategories_data.append({
                        'name': sub['name'],
                        'parent_category': parent_instance,
                        'img_url': sub['img_url']
                    })

        # 4. Crear Subcategorías
        self.stdout.write("Verificando SubCategories...")
        self._bulk_create_if_not_exists(SubCategory, subcategories_data, unique_field='name')

    def _poblar_planes(self):
        self.stdout.write("Verificando MerchantPlans...")
        plans_data = [
            {
                'name': "Plan Emprendo",
                'price': Decimal(15.0),
                'inventory_capacity': 25,
                'products_registration_with_ia': True,
                'digital_performance_analytics': True,
                'short_description_html': "Diseñado para <b>emprendedores</b> que suelen vender de forma informal por redes sociales.",
                'large_description_html': "Dile adiós al «vendedor de DM» para convertirte en un comercio con una <b>vitrina digital estructurada</b>. Podrás organizar tus ofertas sin barreras técnicas complicadas.",
                'card_bg_color': "#E7E6ED",
                'label_bg_color': "#9E8ED9",
                'label_border_color': "#6D49F2",
                'label_text_color': "#F2F2F2"
            },
            {
                'name': "Plan Comercio",
                'price': Decimal(35.0),
                'inventory_capacity': 60,
                'products_registration_with_ia': True,
                'profile_histories': True,
                'gamification_system': True,
                'gamification_analytics': True,
                'digital_performance_analytics': True,
                'is_popular': True,
                'short_description_html': "Diseñado para negocios con <b>clientes recurrentes</b> que necesitan una <b>plataforma robusta</b> para escalar sus ventas.",
                'large_description_html': "Convierte tu catálogo en una herramienta de marketing activo mediante <b>historias</b> y <b>gamificación</b> para potenciar la lealtad y el rendimiento de tu marca en el mercado.",
                'card_bg_color': "#DCD7EF",
                'label_bg_color': "#6D49F2",
                'label_border_color': "#F2F2F2",
                'label_text_color': "#F2F2F2"
            },
            {
                'name': "Plan Franquicia",
                'price': Decimal(165.0),
                'inventory_capacity': 100,
                'products_registration_with_ia': True,
                'profile_histories': True,
                'gamification_system': True,
                'gamification_analytics': True,
                'digital_performance_analytics': True,
                'clients_behavior_analytics': True,
                'operative_management_analytics': True,
                'company_branches': True,
                'company_employees': True,
                'short_description_html': 'Construido para <b>marcas consolidadas</b> que ya no se preocupan solo por "vender", sino por "<b>controlar</b>" lo que venden en <b>diferentes puntos geográficos</b>.',
                'large_description_html': "Diseñado para directores de negocio que necesitan una visión de 360 grados de su operación, gestionando la complejidad de <b>múltiples inventarios</b> y logística distribuida desde un solo centro de mando, asegurando que la experiencia de marca sea la misma en cada <b>sucursal</b>.",
                'card_bg_color': "#FFFFF2",
                'label_bg_color': "#6D49F2",
                'label_border_color': "#F2ED49",
                'label_text_color': "#F2ED49",
                'requires_business': True
            }
        ]
        self._bulk_create_if_not_exists(MerchantPlan, plans_data, unique_field='name')

    def _poblar_anuncios(self):
        self.stdout.write("Verificando Announcements...")
        announcements_data = [
            {'banner_img': 'static/img/third_banner_test.png', 'navigate_to': 'home'},
            {'banner_img': 'static/img/2_banner_test.png', 'navigate_to': 'home'},
            {'banner_img': 'static/img/first_banner_test.png', 'navigate_to': 'home'}
        ]
        self._bulk_create_if_not_exists(Announcement, announcements_data, unique_field='banner_img')

    def _poblar_malls(self):
        self.stdout.write("Verificando Malls desde JSON...")
        json_path = os.path.join(settings.BASE_DIR, 'api', 'static', 'json', 'malls.json')
        
        if not os.path.exists(json_path):
            self.stdout.write(self.style.ERROR(f'  [!] Archivo JSON no encontrado: {json_path}'))
            return

        with open(json_path, 'r', encoding='utf-8') as f:
            malls_data = json.load(f)

        existing_malls = set(Mall.objects.values_list('name', flat=True))
        malls_to_create = []

        for estado, ciudades in malls_data.items():
            for ciudad, malls in ciudades.items():
                for mall in malls:
                    # Si el nombre ya existe en la BD, lo saltamos automáticamente
                    if mall['name'] in existing_malls:
                        continue
                    
                    if mall.get('lat') and mall.get('lng'):
                        try:
                            lng = float(mall['lng'])
                            lat = float(mall['lat'])
                            ubicacion = Point(lng, lat, srid=4326)
                            
                            malls_to_create.append(
                                Mall(
                                    name=mall['name'],
                                    coordinates=ubicacion,
                                    floors_quantity=mall['floors_quantity'],
                                    img_url=mall['img_url']
                                )
                            )
                        except (ValueError, TypeError):
                            self.stdout.write(self.style.WARNING(f"  [!] Error en coordenadas para: {mall['name']}. Saltando..."))
                            continue

        if malls_to_create:
            Mall.objects.bulk_create(malls_to_create)
            self.stdout.write(self.style.SUCCESS(f'  [+] Se crearon {len(malls_to_create)} registros en Mall.'))
        else:
            self.stdout.write(self.style.WARNING('  [-] Sin cambios en Mall. Los registros ya existen o no tienen coordenadas válidas.'))