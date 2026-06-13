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
            'Alimentos y Bebidas': {
                'img_url': 'static/img/categories/alimentos_y_bebidas.jpg',
                'subcategories': [
                    {'name': 'Víveres y Despensa', 'img_url': 'static/img/categories/sub_categories/viveres_y_despensa.jpg'},
                    {'name': 'Carnes y Aves', 'img_url': 'static/img/categories/sub_categories/carnes_y_aves.jpg'},
                    {'name': 'Frutas y Verduras', 'img_url': 'static/img/categories/sub_categories/frutas_y_verduras.jpg'},
                    {'name': 'Charcutería', 'img_url': 'static/img/categories/sub_categories/charcuteria.jpg'},
                    {'name': 'Licores y Bebidas', 'img_url': 'static/img/categories/sub_categories/licores_y_bebidas.jpg'},
                    {'name': 'Snacks y Dulces', 'img_url': 'static/img/categories/sub_categories/snacks_y_dulces.jpg'},
                ]
            },
            'Moda y Textil': {
                'img_url': 'static/img/categories/moda_y_textil.jpg',
                'subcategories': [
                    {'name': 'Ropa Femenina', 'img_url': 'static/img/categories/sub_categories/ropa_femenina.jpg'},
                    {'name': 'Ropa Masculina', 'img_url': 'static/img/categories/sub_categories/ropa_masculina.jpg'},
                    {'name': 'Moda Infantil', 'img_url': 'static/img/categories/sub_categories/moda_infantil.jpg'},
                    {'name': 'Calzado', 'img_url': 'static/img/categories/sub_categories/calzado.jpg'},
                    {'name': 'Accesorios de Moda', 'img_url': 'static/img/categories/sub_categories/accesorios_de_moda.jpg'},
                ]
            },
            'Tecnología': {
                'img_url': 'static/img/categories/tecnologia.jpg',
                'subcategories': [
                    {'name': 'Teléfonos y Tablets', 'img_url': 'static/img/categories/sub_categories/telefonos_y_tablets.jpg'},
                    {'name': 'Computación', 'img_url': 'static/img/categories/sub_categories/computacion.jpg'},
                    {'name': 'Audio y Video', 'img_url': 'static/img/categories/sub_categories/audio_y_video.jpg'},
                    {'name': 'Smartwatches', 'img_url': 'static/img/categories/sub_categories/smartwatches.jpg'},
                    {'name': 'Accesorios Tecnológicos', 'img_url': 'static/img/categories/sub_categories/accesorios_tecnologicos.jpg'},
                ]
            },
            'Salud y Belleza': {
                'img_url': 'static/img/categories/salud_y_belleza.jpg',
                'subcategories': [
                    {'name': 'Medicamentos y Farmacia', 'img_url': 'static/img/categories/sub_categories/medicamentos_y_farmacia.jpg'},
                    {'name': 'Cuidado Personal', 'img_url': 'static/img/categories/sub_categories/cuidado_personal.jpg'},
                    {'name': 'Maquillaje y Cosméticos', 'img_url': 'static/img/categories/sub_categories/maquillaje_y_cosmeticos.jpg'},
                    {'name': 'Perfumería', 'img_url': 'static/img/categories/sub_categories/perfumeria.jpg'},
                ]
            },
            'Hogar y Decoración': {
                'img_url': 'static/img/categories/hogar_y_decoracion.jpg',
                'subcategories': [
                    {'name': 'Electrodomésticos', 'img_url': 'static/img/categories/sub_categories/electrodomesticos.jpg'},
                    {'name': 'Muebles', 'img_url': 'static/img/categories/sub_categories/muebles.jpg'},
                    {'name': 'Artículos de Dormitorio', 'img_url': 'static/img/categories/sub_categories/articulos_de_dormitorio.jpg'},
                    {'name': 'Artículos de Baño', 'img_url': 'static/img/categories/sub_categories/articulos_de_bano.jpg'},
                    {'name': 'Artículos de Limpieza', 'img_url': 'static/img/categories/sub_categories/articulos_de_limpieza.jpg'},
                ]
            },
            'Ferretería y Construcción': {
                'img_url': 'static/img/categories/ferreteria_y_construccion.jpg',
                'subcategories': [
                    {'name': 'Herramientas', 'img_url': 'static/img/categories/sub_categories/herramientas.jpg'},
                    {'name': 'Materiales Eléctricos', 'img_url': 'static/img/categories/sub_categories/materiales_electricos.jpg'},
                    {'name': 'Plomería', 'img_url': 'static/img/categories/sub_categories/plomeria.jpg'},
                    {'name': 'Pinturas y Acabados', 'img_url': 'static/img/categories/sub_categories/pinturas_y_acabados.jpg'},
                ]
            },
            'Automotriz': {
                'img_url': 'static/img/categories/automotriz.jpg',
                'subcategories': [
                    {'name': 'Repuestos', 'img_url': 'static/img/categories/sub_categories/repuestos.jpg'},
                    {'name': 'Lubricantes y Fluidos', 'img_url': 'static/img/categories/sub_categories/lubricantes_y_fluidos.jpg'},
                    {'name': 'Neumáticos', 'img_url': 'static/img/categories/sub_categories/neumaticos.jpg'},
                ]
            },
            'Deportes y Entretenimiento': {
                'img_url': 'static/img/categories/deportes_y_entretenimiento.jpg',
                'subcategories': [
                    {'name': 'Ropa Deportiva', 'img_url': 'static/img/categories/sub_categories/ropa_deportiva.jpg'},
                    {'name': 'Equipos de Ejercicio', 'img_url': 'static/img/categories/sub_categories/equipos_de_ejercicio.jpg'},
                    {'name': 'Juguetes', 'img_url': 'static/img/categories/sub_categories/juguetes.jpg'},
                    {'name': 'Libros y Papelería', 'img_url': 'static/img/categories/sub_categories/libros_y_papeleria.jpg'},
                ]
            },
            'Mascotas': {
                'img_url': 'static/img/categories/mascotas.jpg',
                'subcategories': [
                    {'name': 'Alimentos para Mascotas', 'img_url': 'static/img/categories/sub_categories/alimentos_para_mascotas.jpg'},
                    {'name': 'Higiene Animal', 'img_url': 'static/img/categories/sub_categories/higiene_animal.jpg'},
                    {'name': 'Accesorios para Mascotas', 'img_url': 'static/img/categories/sub_categories/accesorios_para_mascotas.jpg'},
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