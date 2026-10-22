import json
import uuid
from typing import Any, Dict, List, Optional, Tuple


# ==============================================================================
# 1. ESTRUCTURA OFICIAL DEL CATÁLOGO (15 CATEGORÍAS Y 158 SUBCATEGORÍAS)
# ==============================================================================

CATALOGO_ESTRUCTURA: List[Dict[str, Any]] = [
    {
        "categoria": "Alimentos y Bebidas",
        "imagen": "static/img/categories/alimentos_y_bebidas.jpg",
        "subcategorias": [
            {"nombre": "Víveres y Granos", "imagen": "static/img/categories/sub_categories/alimentos_y_bebidas/viveres_y_granos.jpg"},
            {"nombre": "Frutas, Verduras y Hortalizas", "imagen": "static/img/categories/sub_categories/alimentos_y_bebidas/frutas_verduras_y_hortalizas.jpg"},
            {"nombre": "Carnicería y Aves", "imagen": "static/img/categories/sub_categories/alimentos_y_bebidas/carniceria_y_aves.jpg"},
            {"nombre": "Pescadería y Mariscos", "imagen": "static/img/categories/sub_categories/alimentos_y_bebidas/pescaderia_y_mariscos.jpg"},
            {"nombre": "Charcutería", "imagen": "static/img/categories/sub_categories/alimentos_y_bebidas/charcuteria.jpg"},
            {"nombre": "Lácteos y Huevos", "imagen": "static/img/categories/sub_categories/alimentos_y_bebidas/lacteos_y_huevos.jpg"},
            {"nombre": "Panadería y Pastelería", "imagen": "static/img/categories/sub_categories/alimentos_y_bebidas/panaderia_y_pasteleria.jpg"},
            {"nombre": "Enlatados y Conservas", "imagen": "static/img/categories/sub_categories/alimentos_y_bebidas/enlatados_y_conservas.jpg"},
            {"nombre": "Salsas, Condimentos y Aceites", "imagen": "static/img/categories/sub_categories/alimentos_y_bebidas/salsas_condimentos_y_aceites.jpg"},
            {"nombre": "Café, Té e Infusiones", "imagen": "static/img/categories/sub_categories/alimentos_y_bebidas/cafe_te_e_infusiones.jpg"},
            {"nombre": "Bebidas, Refrescos y Maltas", "imagen": "static/img/categories/sub_categories/alimentos_y_bebidas/bebidas_refrescos_y_maltas.jpg"},
            {"nombre": "Licores", "imagen": "static/img/categories/sub_categories/alimentos_y_bebidas/licores.jpg"},
            {"nombre": "Chucherías, Snacks y Dulces", "imagen": "static/img/categories/sub_categories/alimentos_y_bebidas/chucherias_snacks_y_dulces.jpg"},
            {"nombre": "Congelados y Pasapalos", "imagen": "static/img/categories/sub_categories/alimentos_y_bebidas/congelados_y_pasapalos.jpg"},
            {"nombre": "Avena y Cereales", "imagen": "static/img/categories/sub_categories/alimentos_y_bebidas/avena_y_cereales.jpg"},
        ],
    },
    {
        "categoria": "Tecnología y Electrónica",
        "imagen": "static/img/categories/tecnologia_y_electronica.jpg",
        "subcategorias": [
            {"nombre": "Teléfonos y Tablets", "imagen": "static/img/categories/sub_categories/tecnologia_y_electronica/telefonos_y_tablets.jpg"},
            {"nombre": "Computadoras y Laptops", "imagen": "static/img/categories/sub_categories/tecnologia_y_electronica/computadoras_y_laptops.jpg"},
            {"nombre": "Componentes de PC y Hardware", "imagen": "static/img/categories/sub_categories/tecnologia_y_electronica/componentes_de_pc_y_hardware.jpg"},
            {"nombre": "Almacenamiento y Memorias", "imagen": "static/img/categories/sub_categories/tecnologia_y_electronica/almacenamiento_y_memorias.jpg"},
            {"nombre": "Monitores y Televisores", "imagen": "static/img/categories/sub_categories/tecnologia_y_electronica/monitores_y_televisores.jpg"},
            {"nombre": "Impresoras y Escaners", "imagen": "static/img/categories/sub_categories/tecnologia_y_electronica/impresoras_y_escaners.jpg"},
            {"nombre": "Smartwatches y Wearables", "imagen": "static/img/categories/sub_categories/tecnologia_y_electronica/smartwatches_y_wearables.jpg"},
            {"nombre": "Cámaras y Fotografía", "imagen": "static/img/categories/sub_categories/tecnologia_y_electronica/camaras_y_fotografia.jpg"},
            {"nombre": "Teclados y Mouse", "imagen": "static/img/categories/sub_categories/tecnologia_y_electronica/teclados_y_mouse.jpg"},
            {"nombre": "Redes, Routers y Conectividad", "imagen": "static/img/categories/sub_categories/tecnologia_y_electronica/redes_routers_y_conectividad.jpg"},
            {"nombre": "Consolas y Videojuegos", "imagen": "static/img/categories/sub_categories/tecnologia_y_electronica/consolas_y_videojuegos.jpg"},
            {"nombre": "Cargadores, Cables y Powerbanks", "imagen": "static/img/categories/sub_categories/tecnologia_y_electronica/cargadores_cables_y_powerbanks.jpg"},
            {"nombre": "Reguladores, Protectores y UPS", "imagen": "static/img/categories/sub_categories/tecnologia_y_electronica/reguladores_protectores_y_ups.jpg"},
            {"nombre": "Smart Home y Domótica", "imagen": "static/img/categories/sub_categories/tecnologia_y_electronica/smart_home_y_domotica.jpg"},
            {"nombre": "Seguridad y Cámaras de Vigilancia", "imagen": "static/img/categories/sub_categories/tecnologia_y_electronica/seguridad_y_camaras_de_vigilancia.jpg"},
            {"nombre": "Proyectores y Video Beam", "imagen": "static/img/categories/sub_categories/tecnologia_y_electronica/proyectores_y_video_beam.jpg"},
        ],
    },
    {
        "categoria": "Ropa y Accesorios",
        "imagen": "static/img/categories/ropa_y_accesorios.jpg",
        "subcategorias": [
            {"nombre": "Blusas, Tops y Franelas de Dama", "imagen": "static/img/categories/sub_categories/ropa_y_accesorios/blusas_tops_y_franelas_de_dama.jpg"},
            {"nombre": "Vestidos, Faldas y Enterizos", "imagen": "static/img/categories/sub_categories/ropa_y_accesorios/vestidos_faldas_y_enterizos.jpg"},
            {"nombre": "Pantalones, Jeans y Leggings de Dama", "imagen": "static/img/categories/sub_categories/ropa_y_accesorios/pantalones_jeans_y_leggings_de_dama.jpg"},
            {"nombre": "Franelas, Chemises y Camisas de Caballero", "imagen": "static/img/categories/sub_categories/ropa_y_accesorios/franelas_chemises_y_camisas_de_caballero.jpg"},
            {"nombre": "Pantalones, Jeans y Bermudas de Caballero", "imagen": "static/img/categories/sub_categories/ropa_y_accesorios/pantalones_jeans_y_bermudas_de_caballero.jpg"},
            {"nombre": "Ropa Deportiva, Monos y Fitness", "imagen": "static/img/categories/sub_categories/ropa_y_accesorios/ropa_deportiva_monos_y_fitness.jpg"},
            {"nombre": "Trajes de Baño y Ropa Playera", "imagen": "static/img/categories/sub_categories/ropa_y_accesorios/trajes_de_bano_y_ropa_playera.jpg"},
            {"nombre": "Ropa Íntima, Lencería y Pijamas", "imagen": "static/img/categories/sub_categories/ropa_y_accesorios/ropa_intima_lenceria_y_pijamas.jpg"},
            {"nombre": "Ropa para Niños y Niñas", "imagen": "static/img/categories/sub_categories/ropa_y_accesorios/ropa_para_ninos_y_ninas.jpg"},
            {"nombre": "Ropa para Bebés", "imagen": "static/img/categories/sub_categories/ropa_y_accesorios/ropa_para_bebes.jpg"},
            {"nombre": "Zapatos Deportivos y de Goma", "imagen": "static/img/categories/sub_categories/ropa_y_accesorios/zapatos_deportivos_y_de_goma.jpg"},
            {"nombre": "Cholas, Sandalias y Tacones", "imagen": "static/img/categories/sub_categories/ropa_y_accesorios/cholas_sandalias_y_tacones.jpg"},
            {"nombre": "Zapatos Casuales y Formales", "imagen": "static/img/categories/sub_categories/ropa_y_accesorios/zapatos_casuales_y_formales.jpg"},
            {"nombre": "Bolsos y Carteras", "imagen": "static/img/categories/sub_categories/ropa_y_accesorios/bolsos_y_carteras.jpg"},
            {"nombre": "Billeteras y Monederos", "imagen": "static/img/categories/sub_categories/ropa_y_accesorios/billeteras_y_monederos.jpg"},
            {"nombre": "Joyería y Bisutería", "imagen": "static/img/categories/sub_categories/ropa_y_accesorios/joyeria_y_bisuteria.jpg"},
            {"nombre": "Lentes y Relojes", "imagen": "static/img/categories/sub_categories/ropa_y_accesorios/lentes_y_relojes.jpg"},
            {"nombre": "Gorras, Sombreros y Correas", "imagen": "static/img/categories/sub_categories/ropa_y_accesorios/gorras_sombreros_y_correas.jpg"},
            {"nombre": "Maletas y Bolsos de Viaje", "imagen": "static/img/categories/sub_categories/ropa_y_accesorios/maletas_y_bolsos_de_viaje.jpg"},
        ],
    },
    {
        "categoria": "Salud y Belleza",
        "imagen": "static/img/categories/salud_y_belleza.jpg",
        "subcategorias": [
            {"nombre": "Cuidado Capilar, Tintes y Secadores", "imagen": "static/img/categories/sub_categories/salud_y_belleza/cuidado_capilar_y_tintes.jpg"},
            {"nombre": "Skincare y Cuidado Facial", "imagen": "static/img/categories/sub_categories/salud_y_belleza/skincare_y_cuidado_facial.jpg"},
            {"nombre": "Maquillaje de Rostro, Ojos y Labios", "imagen": "static/img/categories/sub_categories/salud_y_belleza/maquillaje.jpg"},
            {"nombre": "Perfumería, Splash y Fragancias", "imagen": "static/img/categories/sub_categories/salud_y_belleza/perfumeria_y_splash.jpg"},
            {"nombre": "Manicura, Pedicura y Uñas", "imagen": "static/img/categories/sub_categories/salud_y_belleza/manicura_y_pedicura.jpg"},
            {"nombre": "Higiene Personal, Desodorantes y Afeitado", "imagen": "static/img/categories/sub_categories/salud_y_belleza/higiene_personal.jpg"},
            {"nombre": "Farmacia, Botiquín y Primeros Auxilios", "imagen": "static/img/categories/sub_categories/salud_y_belleza/farmacia_y_primeros_auxilios.jpg"},
            {"nombre": "Vitaminas, Suplementos y Proteínas", "imagen": "static/img/categories/sub_categories/salud_y_belleza/vitaminas_y_suplementos.jpg"},
            {"nombre": "Salud Sexual y Preservativos", "imagen": "static/img/categories/sub_categories/salud_y_belleza/salud_sexual.jpg"},
            {"nombre": "Equipos Médicos y Tensiómetros", "imagen": "static/img/categories/sub_categories/salud_y_belleza/equipos_medicos.jpg"},
        ],
    },
    {
        "categoria": "Hogar, Muebles y Jardín",
        "imagen": "static/img/categories/hogar_muebles_y_jardin.jpg",
        "subcategorias": [
            {"nombre": "Línea Blanca, Neveras y Lavadoras", "imagen": "static/img/categories/sub_categories/hogar_muebles_y_jardin/linea_blanca.jpg"},
            {"nombre": "Pequeños Electrodomésticos y Cocina", "imagen": "static/img/categories/sub_categories/hogar_muebles_y_jardin/pequenos_electrodomesticos.jpg"},
            {"nombre": "Aires Acondicionados y Ventiladores", "imagen": "static/img/categories/sub_categories/hogar_muebles_y_jardin/aires_y_ventiladores.jpg"},
            {"nombre": "Plantas Eléctricas Domésticas e Inversores", "imagen": "static/img/categories/sub_categories/hogar_muebles_y_jardin/plantas_electricas_e_inversores.jpg"},
            {"nombre": "Tanques de Agua, Bombas y Filtros", "imagen": "static/img/categories/sub_categories/hogar_muebles_y_jardin/tanques_bombas_y_filtros.jpg"},
            {"nombre": "Muebles de Sala y Comedor", "imagen": "static/img/categories/sub_categories/hogar_muebles_y_jardin/muebles_de_sala_y_comedor.jpg"},
            {"nombre": "Camas, Colchones y Box Spring", "imagen": "static/img/categories/sub_categories/hogar_muebles_y_jardin/camas_y_colchones.jpg"},
            {"nombre": "Sábanas, Edredones y Toallas", "imagen": "static/img/categories/sub_categories/hogar_muebles_y_jardin/sabanas_y_lenceria.jpg"},
            {"nombre": "Ollas, Sartenes y Utensilios de Cocina", "imagen": "static/img/categories/sub_categories/hogar_muebles_y_jardin/ollas_y_utensilios.jpg"},
            {"nombre": "Pocetas, Lavamanos y Baño", "imagen": "static/img/categories/sub_categories/hogar_muebles_y_jardin/piezas_de_bano.jpg"},
            {"nombre": "Decoración, Cuadros y Espejos", "imagen": "static/img/categories/sub_categories/hogar_muebles_y_jardin/decoracion_y_espejos.jpg"},
            {"nombre": "Productos de Limpieza, Detergentes y Mopas", "imagen": "static/img/categories/sub_categories/hogar_muebles_y_jardin/limpieza_del_hogar.jpg"},
            {"nombre": "Jardinería, Mangueras y Exteriores", "imagen": "static/img/categories/sub_categories/hogar_muebles_y_jardin/jardineria_y_exteriores.jpg"},
        ],
    },
    {
        "categoria": "Ferretería y Construcción",
        "imagen": "static/img/categories/ferreteria_y_construccion.jpg",
        "subcategorias": [
            {"nombre": "Herramientas Manuales", "imagen": "static/img/categories/sub_categories/ferreteria_y_construccion/herramientas_manuales.jpg"},
            {"nombre": "Herramientas Eléctricas, Taladros y Esmeriles", "imagen": "static/img/categories/sub_categories/ferreteria_y_construccion/herramientas_electricas.jpg"},
            {"nombre": "Electricidad, Cables, Breakers y Tomacorrientes", "imagen": "static/img/categories/sub_categories/ferreteria_y_construccion/electricidad_y_breakers.jpg"},
            {"nombre": "Bombillos, Reflectores e Iluminación LED", "imagen": "static/img/categories/sub_categories/ferreteria_y_construccion/bombillos_e_iluminacion.jpg"},
            {"nombre": "Plomería, Tuberías de PVC y Grifería", "imagen": "static/img/categories/sub_categories/ferreteria_y_construccion/plomeria_y_tubos.jpg"},
            {"nombre": "Sistemas de Hidroneumático y Bombas de Agua", "imagen": "static/img/categories/sub_categories/ferreteria_y_construccion/hidroneumaticos_y_bombas.jpg"},
            {"nombre": "Pinturas, Cuñetes, Brochas y Selladores", "imagen": "static/img/categories/sub_categories/ferreteria_y_construccion/pinturas_y_brochas.jpg"},
            {"nombre": "Cementos, Pegos, Mallas y Bloques", "imagen": "static/img/categories/sub_categories/ferreteria_y_construccion/cementos_y_pegos.jpg"},
            {"nombre": "Tornillería, Clavos y Chazos", "imagen": "static/img/categories/sub_categories/ferreteria_y_construccion/tornilleria_y_fijaciones.jpg"},
            {"nombre": "Cerraduras, Candados y Cilindros", "imagen": "static/img/categories/sub_categories/ferreteria_y_construccion/cerraduras_y_candados.jpg"},
            {"nombre": "Seguridad Industrial, Guantes y Botas", "imagen": "static/img/categories/sub_categories/ferreteria_y_construccion/seguridad_industrial.jpg"},
        ],
    },
    {
        "categoria": "Carros, Motos y Otros",
        "imagen": "static/img/categories/carros_motos_y_otros.jpg",
        "subcategorias": [
            {"nombre": "Venta de Carros y Camionetas", "imagen": "static/img/categories/sub_categories/automotriz_y_motos/venta_de_carros.jpg"},
            {"nombre": "Venta de Motos", "imagen": "static/img/categories/sub_categories/automotriz_y_motos/venta_de_motos.jpg"},
            {"nombre": "Cauchos y Rines", "imagen": "static/img/categories/sub_categories/automotriz_y_motos/cauchos_y_rines.jpg"},
            {"nombre": "Aceites de Motor, Filtros y Fluidos", "imagen": "static/img/categories/sub_categories/automotriz_y_motos/aceites_filtros_y_fluidos.jpg"},
            {"nombre": "Repuestos de Motor y Tren Delantero", "imagen": "static/img/categories/sub_categories/automotriz_y_motos/repuestos_motor_y_tren_delantero.jpg"},
            {"nombre": "Frenos, Pastillas y Discos", "imagen": "static/img/categories/sub_categories/automotriz_y_motos/frenos_y_pastillas.jpg"},
            {"nombre": "Repuestos, Cascos y Accesorios para Motos", "imagen": "static/img/categories/sub_categories/automotriz_y_motos/repuestos_y_cascos_motos.jpg"},
            {"nombre": "Luces LED, Barras y Faros", "imagen": "static/img/categories/sub_categories/automotriz_y_motos/luces_led_y_barras.jpg"},
            {"nombre": "Sonido para Carros, Reproductores y Plantas", "imagen": "static/img/categories/sub_categories/automotriz_y_motos/sonido_para_carros.jpg"},
            {"nombre": "Alarmas, Trancapalancas y Papel Ahumado", "imagen": "static/img/categories/sub_categories/automotriz_y_motos/alarmas_y_seguridad_vehicular.jpg"},
            {"nombre": "Cuidado Automotriz, Ceras y Champú", "imagen": "static/img/categories/sub_categories/automotriz_y_motos/limpieza_y_estetica_automotriz.jpg"},
        ],
    },
    {
        "categoria": "Deportes y Fitness",
        "imagen": "static/img/categories/deportes_y_fitness.jpg",
        "subcategorias": [
            {"nombre": "Pesas, Mancuernas y Máquinas de Gym", "imagen": "static/img/categories/sub_categories/deportes_y_fitness/pesas_y_gym.jpg"},
            {"nombre": "Béisbol y Sóftbol (Guantes, Bates y Pelotas)", "imagen": "static/img/categories/sub_categories/deportes_y_fitness/beisbol_y_softbol.jpg"},
            {"nombre": "Fútbol y Futsal (Balones, Tacos y Canilleras)", "imagen": "static/img/categories/sub_categories/deportes_y_fitness/futbol_y_futsal.jpg"},
            {"nombre": "Básquetbol", "imagen": "static/img/categories/sub_categories/deportes_y_fitness/basquetbol.jpg"},
            {"nombre": "Pádel y Tenis", "imagen": "static/img/categories/sub_categories/deportes_y_fitness/padel_y_tenis.jpg"},
            {"nombre": "Bicicletas y Ciclismo", "imagen": "static/img/categories/sub_categories/deportes_y_fitness/bicicletas_y_ciclismo.jpg"},
            {"nombre": "Ropa Deportiva, Monos y Licras", "imagen": "static/img/categories/sub_categories/deportes_y_fitness/ropa_deportiva.jpg"},
            {"nombre": "Zapatos Deportivos y Gomas", "imagen": "static/img/categories/sub_categories/deportes_y_fitness/zapatos_deportivos.jpg"},
            {"nombre": "Camping, Carpas y Colchones Inflables", "imagen": "static/img/categories/sub_categories/deportes_y_fitness/camping_y_carpas.jpg"},
            {"nombre": "Cavas, Coolers y Termos", "imagen": "static/img/categories/sub_categories/deportes_y_fitness/cavas_coolers_y_termos.jpg"},
            {"nombre": "Proteínas, Creatinas y Suplementos Gym", "imagen": "static/img/categories/sub_categories/deportes_y_fitness/suplementos_gym.jpg"},
        ],
    },
    {
        "categoria": "Bebés y Maternidad",
        "imagen": "static/img/categories/bebes_y_maternidad.jpg",
        "subcategorias": [
            {"nombre": "Pañales, Toallitas y Crema Antipañalitis", "imagen": "static/img/categories/sub_categories/bebes_y_maternidad/panales_y_toallitas.jpg"},
            {"nombre": "Teteros, Esterilizadores y Chupones", "imagen": "static/img/categories/sub_categories/bebes_y_maternidad/teteros_y_chupones.jpg"},
            {"nombre": "Lactancia Materna y Extractores", "imagen": "static/img/categories/sub_categories/bebes_y_maternidad/lactancia_materna.jpg"},
            {"nombre": "Fórmulas Infantiles y Papillas", "imagen": "static/img/categories/sub_categories/bebes_y_maternidad/formulas_y_alimentos_bebe.jpg"},
            {"nombre": "Coches, Portabebés y Sillas para Carro", "imagen": "static/img/categories/sub_categories/bebes_y_maternidad/coches_y_portabebes.jpg"},
            {"nombre": "Cunas, Corrales y Moisés", "imagen": "static/img/categories/sub_categories/bebes_y_maternidad/cunas_y_corrales.jpg"},
            {"nombre": "Bañeras, Champú y Jabones de Bebé", "imagen": "static/img/categories/sub_categories/bebes_y_maternidad/bano_y_cuidado_bebe.jpg"},
            {"nombre": "Ropa de Bebé, Monillos y Bodies", "imagen": "static/img/categories/sub_categories/bebes_y_maternidad/ropa_de_bebe.jpg"},
            {"nombre": "Monitores y Seguridad para Bebé", "imagen": "static/img/categories/sub_categories/bebes_y_maternidad/monitores_y_seguridad_para_bebe.jpg"},
        ],
    },
    {
        "categoria": "Juegos y Juguetes",
        "imagen": "static/img/categories/juegos_y_juguetes.jpg",
        "subcategorias": [
            {"nombre": "Muñecas, Barbies y Bebés", "imagen": "static/img/categories/sub_categories/juegos_y_juguetes/munecas_y_barbies.jpg"},
            {"nombre": "Peluches", "imagen": "static/img/categories/sub_categories/juegos_y_juguetes/peluches.jpg"},
            {"nombre": "Figuras de Acción y Superhéroes", "imagen": "static/img/categories/sub_categories/juegos_y_juguetes/figuras_de_accion.jpg"},
            {"nombre": "Bloques, Legos y Armables", "imagen": "static/img/categories/sub_categories/juegos_y_juguetes/bloques_y_legos.jpg"},
            {"nombre": "Juegos de Mesa, Cartas y Dominó", "imagen": "static/img/categories/sub_categories/juegos_y_juguetes/juegos_de_mesa_y_domino.jpg"},
            {"nombre": "Juguetes de Exterior, Patinetas y Triciclos", "imagen": "static/img/categories/sub_categories/juegos_y_juguetes/juguetes_de_exterior.jpg"},
            {"nombre": "Juguetes de Piscina, Playa e Inflables", "imagen": "static/img/categories/sub_categories/juegos_y_juguetes/juguetes_de_playa_e_inflables.jpg"},
            {"nombre": "Juguetes de Estimulación para Bebés", "imagen": "static/img/categories/sub_categories/juegos_y_juguetes/juguetes_para_bebes.jpg"},
        ],
    },
    {
        "categoria": "Mascotas",
        "imagen": "static/img/categories/mascotas.jpg",
        "subcategorias": [
            {"nombre": "Perrarina y Comida para Perros", "imagen": "static/img/categories/sub_categories/mascotas/perrarina.jpg"},
            {"nombre": "Gatarina y Comida para Gatos", "imagen": "static/img/categories/sub_categories/mascotas/gatarina.jpg"},
            {"nombre": "Snacks, Galletas y Huesos para Mascotas", "imagen": "static/img/categories/sub_categories/mascotas/snacks_para_mascotas.jpg"},
            {"nombre": "Arena para Gatos y Areneras", "imagen": "static/img/categories/sub_categories/mascotas/arena_para_gatos.jpg"},
            {"nombre": "Antipulgas, Garrapaticidas y Desparasitantes", "imagen": "static/img/categories/sub_categories/mascotas/salud_animal_y_garrapaticidas.jpg"},
            {"nombre": "Champú, Cepillos y Estética Canina", "imagen": "static/img/categories/sub_categories/mascotas/champu_y_estetica_canina.jpg"},
            {"nombre": "Camas, Casas y Transportadoras", "imagen": "static/img/categories/sub_categories/mascotas/camas_y_transportadoras.jpg"},
            {"nombre": "Paseo, Collares, Pecheras y Correas", "imagen": "static/img/categories/sub_categories/mascotas/collares_y_correas.jpg"},
            {"nombre": "Aves, Peces y Otras Mascotas", "imagen": "static/img/categories/sub_categories/mascotas/aves_y_peces.jpg"},
        ],
    },
    {
        "categoria": "Papelería, Oficina y Libros",
        "imagen": "static/img/categories/papeleria_oficina_y_libros.jpg",
        "subcategorias": [
            {"nombre": "Cuadernos, Libretas y Blocks", "imagen": "static/img/categories/sub_categories/papeleria_oficina_y_libros/cuadernos_y_libretas.jpg"},
            {"nombre": "Lápices, Colores, Bolígrafos y Marcadores", "imagen": "static/img/categories/sub_categories/papeleria_oficina_y_libros/lapices_y_colores.jpg"},
            {"nombre": "Resmas de Hojas, Cartulinas y Papelería", "imagen": "static/img/categories/sub_categories/papeleria_oficina_y_libros/resmas_y_papel.jpg"},
            {"nombre": "Morrales Escolares y Cartucheras", "imagen": "static/img/categories/sub_categories/papeleria_oficina_y_libros/morrales_y_cartucheras.jpg"},
            {"nombre": "Material de Manualidades, Foami y Pinturas", "imagen": "static/img/categories/sub_categories/papeleria_oficina_y_libros/foami_y_manualidades.jpg"},
            {"nombre": "Carpetas, Archivadores y Sobres", "imagen": "static/img/categories/sub_categories/papeleria_oficina_y_libros/carpetas_y_archivadores.jpg"},
            {"nombre": "Calculadoras, Grapadoras y Tijeras", "imagen": "static/img/categories/sub_categories/papeleria_oficina_y_libros/grapadoras_y_oficina.jpg"},
            {"nombre": "Sillas de Oficina y Escritorios", "imagen": "static/img/categories/sub_categories/papeleria_oficina_y_libros/sillas_y_escritorios.jpg"},
            {"nombre": "Libros Escolares, Novelas y Literatura", "imagen": "static/img/categories/sub_categories/papeleria_oficina_y_libros/libros_y_novelas.jpg"},
        ],
    },
    {
        "categoria": "Instrumentos Musicales",
        "imagen": "static/img/categories/instrumentos_musicales.jpg",
        "subcategorias": [
            {"nombre": "Cuatros Venezolanos, Maracas y Furrucos", "imagen": "static/img/categories/sub_categories/instrumentos_musicales/cuatros_y_maracas.jpg"},
            {"nombre": "Guitarras y Bajos", "imagen": "static/img/categories/sub_categories/instrumentos_musicales/guitarras_y_bajos.jpg"},
            {"nombre": "Instrumentos de Cuerda", "imagen": "static/img/categories/sub_categories/instrumentos_musicales/instrumentos_de_cuerda.jpg"},
            {"nombre": "Amplificadores", "imagen": "static/img/categories/sub_categories/instrumentos_musicales/amplificadores.jpg"},
            {"nombre": "Teclados, Sintetizadores y Pianos Eléctricos", "imagen": "static/img/categories/sub_categories/instrumentos_musicales/teclados_y_pianos.jpg"},
            {"nombre": "Baterías y Percusión", "imagen": "static/img/categories/sub_categories/instrumentos_musicales/baterias_y_percusion.jpg"},
            {"nombre": "Percusión Latina, Congas, Timbales y Bongós", "imagen": "static/img/categories/sub_categories/instrumentos_musicales/congas_y_percusion_latina.jpg"},
            {"nombre": "Instrumentos de Viento, Flautas y Saxofones", "imagen": "static/img/categories/sub_categories/instrumentos_musicales/instrumentos_de_viento.jpg"},
            {"nombre": "Micrófonos, Consolas y Sonido en Vivo", "imagen": "static/img/categories/sub_categories/instrumentos_musicales/microfonos_y_consolas.jpg"},
            {"nombre": "Equipos para DJ y Audífonos de Monitoreo", "imagen": "static/img/categories/sub_categories/instrumentos_musicales/equipos_dj_y_monitoreo.jpg"},
            {"nombre": "Cuerdas, Fundas, Afinadores y Pedales", "imagen": "static/img/categories/sub_categories/instrumentos_musicales/cuerdas_y_fundas.jpg"},
        ],
    },
    {
        "categoria": "Fiestas y Piñatería",
        "imagen": "static/img/categories/fiestas_y_pinateria.jpg",
        "subcategorias": [
            {"nombre": "Piñatas, Cotillones y Globos", "imagen": "static/img/categories/sub_categories/fiesstas_pinateria_y_otro/pinatas_y_cotillones.jpg"},
            {"nombre": "Descartables, Vasos, Platos y Servilletas", "imagen": "static/img/categories/sub_categories/fiesstas_pinateria_y_otro/descartables_para_fiestas.jpg"},
            {"nombre": "Embalaje, Cajas y Bolsas Plásticas", "imagen": "static/img/categories/sub_categories/fiesstas_pinateria_y_otro/embalaje_y_bolsas.jpg"},
            {"nombre": "Servicios Profesionales", "imagen": "static/img/categories/sub_categories/fiesstas_pinateria_y_otro/servicios_profesionales.jpg"},
            {"nombre": "Inmuebles y Locales Comerciales", "imagen": "static/img/categories/sub_categories/fiesstas_pinateria_y_otro/inmuebles_y_locales.jpg"},
        ],
    },
    {
        "categoria": "Otras Categorías",
        "imagen": "static/img/categories/otras_categorias.jpg",
        "subcategorias": [
            {"nombre": "Otros", "imagen": "static/img/categories/sub_categories/otras_categorias/otros.jpg"},
        ],
    },
]


# ==============================================================================
# 2. CATÁLOGO DE UNIDADES DE VENTA (SELLING UNITS) Y PRESETS DE VENEZUELA
# ==============================================================================

SELLING_UNITS_CATALOG: Dict[str, Dict[str, Any]] = {
    "unit": {
        "code": "unit",
        "label": "Unidad",
        "short_label": "und",
        "price_label": "Precio por unidad",
        "allow_fractional": False,
        "default_step": 1.0,
        "default_min": 1.0,
    },
    "kg": {
        "code": "kg",
        "label": "Kilogramo (kg)",
        "short_label": "kg",
        "price_label": "Precio por kg",
        "allow_fractional": True,
        "default_step": 0.25,
        "default_min": 0.25,
    },
    "g": {
        "code": "g",
        "label": "Gramos (g)",
        "short_label": "g",
        "price_label": "Precio por cada 100g / porción en g",
        "allow_fractional": False,
        "default_step": 100.0,
        "default_min": 100.0,
    },
    "lb": {
        "code": "lb",
        "label": "Libra (lb)",
        "short_label": "lb",
        "price_label": "Precio por libra",
        "allow_fractional": True,
        "default_step": 0.5,
        "default_min": 0.5,
    },
    "l": {
        "code": "l",
        "label": "Litro (L)",
        "short_label": "L",
        "price_label": "Precio por litro",
        "allow_fractional": True,
        "default_step": 0.5,
        "default_min": 0.5,
    },
    "ml": {
        "code": "ml",
        "label": "Mililitros (ml)",
        "short_label": "ml",
        "price_label": "Precio por envase / ml",
        "allow_fractional": False,
        "default_step": 100.0,
        "default_min": 100.0,
    },
    "pack": {
        "code": "pack",
        "label": "Empaque / Paquete",
        "short_label": "paq",
        "price_label": "Precio por paquete",
        "allow_fractional": False,
        "default_step": 1.0,
        "default_min": 1.0,
    },
    "dozen": {
        "code": "dozen",
        "label": "Docena (12 und)",
        "short_label": "docena",
        "price_label": "Precio por docena",
        "allow_fractional": False,
        "default_step": 1.0,
        "default_min": 1.0,
    },
    "box": {
        "code": "box",
        "label": "Caja / Bulto",
        "short_label": "caja",
        "price_label": "Precio por caja/bulto",
        "allow_fractional": False,
        "default_step": 1.0,
        "default_min": 1.0,
    },
    "portion": {
        "code": "portion",
        "label": "Porción / Ración / Plato",
        "short_label": "porción",
        "price_label": "Precio por porción",
        "allow_fractional": False,
        "default_step": 1.0,
        "default_min": 1.0,
    },
    "combo": {
        "code": "combo",
        "label": "Combo / Promoción",
        "short_label": "combo",
        "price_label": "Precio del combo",
        "allow_fractional": False,
        "default_step": 1.0,
        "default_min": 1.0,
    },
    "pair": {
        "code": "pair",
        "label": "Par",
        "short_label": "par",
        "price_label": "Precio por par",
        "allow_fractional": False,
        "default_step": 1.0,
        "default_min": 1.0,
    },
    "set": {
        "code": "set",
        "label": "Set / Juego",
        "short_label": "set",
        "price_label": "Precio por set",
        "allow_fractional": False,
        "default_step": 1.0,
        "default_min": 1.0,
    },
    "m": {
        "code": "m",
        "label": "Metro lineal (m)",
        "short_label": "m",
        "price_label": "Precio por metro",
        "allow_fractional": True,
        "default_step": 0.5,
        "default_min": 0.5,
    },
    "m2": {
        "code": "m2",
        "label": "Metro cuadrado (m²)",
        "short_label": "m²",
        "price_label": "Precio por m²",
        "allow_fractional": True,
        "default_step": 1.0,
        "default_min": 1.0,
    },
    "gal": {
        "code": "gal",
        "label": "Galón / Cuñete",
        "short_label": "gal",
        "price_label": "Precio por galón",
        "allow_fractional": False,
        "default_step": 1.0,
        "default_min": 1.0,
    },
}


# Nomenclaturas oficiales de tallas y medidas más utilizadas en Venezuela
VE_CLOTHING_LETTER_SIZES: List[str] = ["XS", "S", "M", "L", "XL", "XXL", "XXXL", "Talla Única"]
VE_WOMEN_PANTS_SIZES: List[str] = [
    "4", "6", "8", "10", "12", "14", "16", "18",
    "24", "26", "28", "30", "32", "34", "36", "38",
    "XS", "S", "M", "L", "XL", "XXL",
]
VE_MEN_PANTS_SIZES: List[str] = [
    "28", "30", "32", "34", "36", "38", "40", "42", "44",
    "S", "M", "L", "XL", "XXL",
]
VE_KIDS_CLOTHING_SIZES: List[str] = [
    "2T", "3T", "4T", "5T",
    "Talla 2", "Talla 4", "Talla 6", "Talla 8", "Talla 10", "Talla 12", "Talla 14", "Talla 16",
]
VE_BABY_CLOTHING_SIZES: List[str] = [
    "RN (Recién Nacido)", "0-3M", "3-6M", "6-9M", "9-12M", "12-18M", "18-24M",
]
VE_BRA_SIZES: List[str] = [
    "32A", "32B", "34A", "34B", "34C", "36B", "36C", "36D", "38B", "38C", "38D", "40C",
    "XS", "S", "M", "L", "XL",
]
VE_ADULT_SHOE_SIZES: List[str] = [
    "34", "35", "36", "37", "38", "39", "40", "41", "42", "43", "44", "45", "46",
]
VE_KIDS_SHOE_SIZES: List[str] = [
    "18", "19", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32", "33",
]
VE_ALL_SHOE_SIZES: List[str] = VE_ADULT_SHOE_SIZES + VE_KIDS_SHOE_SIZES
VE_SHOE_US_SIZES: List[str] = [
    "5 US", "5.5 US", "6 US", "6.5 US", "7 US", "7.5 US", "8 US", "8.5 US",
    "9 US", "9.5 US", "10 US", "10.5 US", "11 US", "12 US", "13 US",
]
VE_COMMON_COLORS: List[str] = [
    "Negro", "Blanco", "Azul Marino", "Azul Rey", "Azul Claro", "Rojo", "Vinotinto",
    "Verde", "Verde Oliva", "Beige / Crema", "Gris", "Marrón / Camel", "Rosado",
    "Fucsia", "Amarillo", "Morado", "Dorado", "Plateado", "Multicolor / Estampado",
]
VE_DIAPER_SIZES: List[str] = [
    "RN (Recién Nacido)", "P (Pequeño)", "M (Mediano)", "G (Grande)",
    "XG (Extra Grande)", "XXG", "XXXG",
]

VENEZUELA_SIZING_PRESETS: Dict[str, List[str]] = {
    "clothing_letters": VE_CLOTHING_LETTER_SIZES,
    "women_pants": VE_WOMEN_PANTS_SIZES,
    "men_pants": VE_MEN_PANTS_SIZES,
    "kids_clothing": VE_KIDS_CLOTHING_SIZES,
    "baby_clothing": VE_BABY_CLOTHING_SIZES,
    "bra_lingerie": VE_BRA_SIZES,
    "adult_shoes_ve": VE_ADULT_SHOE_SIZES,
    "kids_shoes_ve": VE_KIDS_SHOE_SIZES,
    "shoes_us": VE_SHOE_US_SIZES,
    "common_colors": VE_COMMON_COLORS,
    "diapers": VE_DIAPER_SIZES,
}


# Presets de grupos de elección para combos (ej. elegir bebida, contorno o agrandar combo)
DEFAULT_COMBO_CHOICE_PRESETS: List[Dict[str, Any]] = [
    {
        "name": "Elige la Bebida del Combo",
        "required": True,
        "min_selections": 1,
        "max_selections": 1,
        "options": [
            {"name": "Coca-Cola", "price_delta": 0.0},
            {"name": "Pepsi", "price_delta": 0.0},
            {"name": "Kolita / Frescolita", "price_delta": 0.0},
            {"name": "Chinotto / 7Up", "price_delta": 0.0},
            {"name": "Malta", "price_delta": 0.0},
            {"name": "Nestea / Té Frío", "price_delta": 0.0},
            {"name": "Agua Mineral", "price_delta": 0.0},
        ],
    },
    {
        "name": "Elige tu Contorno / Acompañante",
        "required": True,
        "min_selections": 1,
        "max_selections": 1,
        "options": [
            {"name": "Papas Fritas", "price_delta": 0.0},
            {"name": "Ensalada César / Fresca", "price_delta": 0.0},
            {"name": "Ensalada Rallada (Coleslaw)", "price_delta": 0.0},
            {"name": "Yuca Frita / Sancochada", "price_delta": 0.0},
            {"name": "Arepitas con Nata / Hallaquitas", "price_delta": 0.0},
            {"name": "Tostones / Tajadas", "price_delta": 0.0},
        ],
    },
    {
        "name": "Agrandar o Mejorar tu Combo (Opcional)",
        "required": False,
        "min_selections": 0,
        "max_selections": 4,
        "options": [
            {"name": "Agrandar Bebida a 1.5 Litros", "price_delta": 1.5},
            {"name": "Doble Ración de Contorno / Papas", "price_delta": 1.5},
            {"name": "Extra Queso / Tocineta", "price_delta": 1.5},
            {"name": "Salsas Adicionales (Ajo, Tártara, Guasacaca)", "price_delta": 0.5},
        ],
    },
]

FOOD_COMBO_TEMPLATES: List[Dict[str, Any]] = [
    {
        "name": "Combo Hamburguesa + Refresco + Ensalada",
        "description": "1 Hamburguesa + 1 Refresco + 1 Ensalada fresca.",
        "combo_items": [
            {"name": "Hamburguesa", "quantity": 1, "unit": "und", "notes": "Con queso, vegetales y salsas"},
            {"name": "Refresco", "quantity": 1, "unit": "und", "notes": "355 ml bien frío"},
            {"name": "Ensalada", "quantity": 1, "unit": "porción", "notes": "Porción individual"},
        ],
    },
    {
        "name": "Combo Hamburguesa + Papas Fritas + Refresco",
        "description": "1 Hamburguesa + 1 Ración de Papas Fritas + 1 Refresco.",
        "combo_items": [
            {"name": "Hamburguesa Clásica", "quantity": 1, "unit": "und", "notes": ""},
            {"name": "Papas Fritas", "quantity": 1, "unit": "porción", "notes": "Porción mediana"},
            {"name": "Refresco 355ml", "quantity": 1, "unit": "und", "notes": ""},
        ],
    },
    {
        "name": "Combo Dúo (2 Principales + 2 Bebidas + 2 Contornos)",
        "description": "Ideal para compartir en pareja.",
        "combo_items": [
            {"name": "Plato / Hamburguesa Principal", "quantity": 2, "unit": "und", "notes": ""},
            {"name": "Contorno (Papas o Ensalada)", "quantity": 2, "unit": "porción", "notes": ""},
            {"name": "Bebida 355ml", "quantity": 2, "unit": "und", "notes": ""},
        ],
    },
    {
        "name": "Combo Familiar + Refresco 1.5L",
        "description": "Combo para 4 personas con contornos y bebida familiar.",
        "combo_items": [
            {"name": "Porción / Unidad Principal", "quantity": 4, "unit": "und", "notes": ""},
            {"name": "Ración Familiar de Contorno / Ensalada", "quantity": 1, "unit": "porción", "notes": ""},
            {"name": "Refresco Familiar 1.5L o 2L", "quantity": 1, "unit": "botella", "notes": ""},
        ],
    },
]


def _units(*codes: str) -> List[Dict[str, Any]]:
    return [SELLING_UNITS_CATALOG[c] for c in codes if c in SELLING_UNITS_CATALOG]


# ==============================================================================
# 3. ARQUETIPOS BASE DE ESQUEMAS DINÁMICOS Y COMBOS
# ==============================================================================

def _build_schema(
    *,
    archetype: str,
    ui_hint: str,
    buyer_ui_hint: str,
    allowed_units: List[str],
    default_unit: str = "unit",
    supports_variants: bool = True,
    variant_config: Optional[Dict[str, Any]] = None,
    supports_modifier_groups: bool = False,
    modifier_group_presets: Optional[List[Dict[str, Any]]] = None,
    supports_combos: bool = True,
    combo_item_placeholder: str = "Ej: 1 Hamburguesa, 1 Refresco 355ml, 1 Ensalada...",
    combo_templates: Optional[List[Dict[str, Any]]] = None,
    combo_choice_presets: Optional[List[Dict[str, Any]]] = None,
    order_notes_enabled: bool = True,
    order_notes_placeholder: str = "Indicaciones adicionales para este producto (opcional)",
    fields: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    effective_units = list(dict.fromkeys(list(allowed_units) + (["combo"] if supports_combos else [])))
    default_unit_info = SELLING_UNITS_CATALOG.get(default_unit, SELLING_UNITS_CATALOG["unit"])
    return {
        "schema_version": 2,
        "archetype": archetype,
        "ui_hint": ui_hint,
        "buyer_ui_hint": buyer_ui_hint,
        "allowed_selling_unit_codes": effective_units,
        "allowed_selling_units": _units(*effective_units),
        "default_selling_unit": default_unit,
        "default_allow_fractional": default_unit_info["allow_fractional"],
        "default_unit_step": default_unit_info["default_step"],
        "default_min_order_quantity": default_unit_info["default_min"],
        "supports_variants": supports_variants,
        "variant_config": variant_config or {
            "enabled": supports_variants,
            "label": "Variantes / Presentaciones",
            "axes": [],
        },
        "supports_modifier_groups": True if supports_combos else supports_modifier_groups,
        "modifier_group_presets": modifier_group_presets or [],
        "supports_combos": supports_combos,
        "combo_config": {
            "enabled": supports_combos,
            "label": "Armar como Combo / Promoción",
            "helper_text": (
                "Activa el modo Combo para detallar todos los productos incluidos por un mismo precio "
                "(ej. 1 Hamburguesa + 1 Refresco + 1 Ensalada) y agrega grupos de elección si el cliente "
                "debe escoger bebida o contorno."
            ),
            "min_items": 2,
            "max_items": 25,
            "item_placeholder": combo_item_placeholder,
            "unit_options": ["und", "porción", "lata", "botella", "vaso", "paq", "docena", "kg", "g", "L", "ml", "par", "set"],
            "suggested_templates": combo_templates or [],
            "choice_group_presets": combo_choice_presets or DEFAULT_COMBO_CHOICE_PRESETS,
        },
        "order_notes_enabled": order_notes_enabled,
        "order_notes_placeholder": order_notes_placeholder,
        "fields": fields or [],
    }


def _warranty_field(placeholder: str = "Ej: 30 días, 6 meses o 1 año") -> Dict[str, Any]:
    return {
        "key": "garantia",
        "label": "Garantía",
        "type": "warranty",
        "required": False,
        "unit_options": ["días", "meses", "años", "sin garantía"],
        "default_unit": "meses",
        "options": [
            "Sin garantía",
            "7 días",
            "15 días",
            "30 días",
            "3 meses",
            "6 meses",
            "1 año",
            "2 años",
            "3 años",
            "5 años",
        ],
        "placeholder": placeholder,
        "helper_text": "Puedes indicar cantidad y unidad (días, meses o años) o seleccionar una opción rápida.",
        "section": "condition",
    }


# ==============================================================================
# 4. DEFINICIÓN ESPECÍFICA POR SUBCATEGORÍA (158 SUBCATEGORÍAS + ALIAS LEGACY)
# ==============================================================================

SUBCATEGORY_SCHEMAS: Dict[str, Dict[str, Any]] = {
    # --------------------------------------------------------------------------
    # 1. ALIMENTOS Y BEBIDAS (15 SUBCATEGORÍAS OFICIALES + ARQUETIPOS BASE)
    # --------------------------------------------------------------------------
    "Víveres y Granos": _build_schema(
        archetype="grocery_packaged",
        ui_hint="Ideal para harina de maíz precocida, arroz, pasta, caraotas, lentejas, azúcar, sal, leche en polvo y combos de mercado. Puedes vender por unidad, paquete, kg, bulto o armar un Combo de Víveres.",
        buyer_ui_hint="Selecciona la presentación (unidad, paquete o bulto) o revisa qué incluye el combo.",
        allowed_units=["unit", "pack", "box", "kg", "g", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Presentación / Peso / Empaque",
            "axes": [
                {"key": "presentation", "label": "Presentación", "type": "select", "presets": ["250 g", "500 g", "900 g", "1 kg", "2 kg", "Paquete x4", "Medio Bulto", "Bulto Cerrado"]},
                {"key": "type", "label": "Variante / Tipo", "type": "text", "presets": ["Tradicional", "Integral", "Suave", "Extra Especial", "Sin Gluten"]},
            ],
        },
        supports_modifier_groups=True,
        combo_item_placeholder="Ej: 2 Harina PAN 1kg, 2 Arroz Primor 1kg, 1 Pasta 1kg, 1 Aceite 1L...",
        combo_templates=[
            {
                "name": "Combo Despensa Básica",
                "description": "Combo ahorrador con los víveres esenciales del hogar.",
                "combo_items": [
                    {"name": "Harina de Maíz Precocida 1kg", "quantity": 2, "unit": "paq", "notes": ""},
                    {"name": "Arroz Blanco 1kg", "quantity": 2, "unit": "paq", "notes": ""},
                    {"name": "Pasta Alimenticia 500g", "quantity": 2, "unit": "paq", "notes": ""},
                    {"name": "Caraotas Negras 500g", "quantity": 1, "unit": "paq", "notes": ""},
                    {"name": "Azúcar Refinada 1kg", "quantity": 1, "unit": "paq", "notes": ""},
                ],
            },
        ],
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: PAN, Primor, Mary, Juana, Capri, Montalbán", "section": "details"},
            {"key": "tipo_vivere", "label": "Tipo de Producto", "type": "select", "required": False, "options": ["Harina de Maíz / Trigo", "Arroz", "Pasta", "Granos (Caraotas, Lentejas, Arvejas)", "Azúcar y Endulzantes", "Sal", "Leche en Polvo", "Combo de Mercado"], "section": "details"},
            {"key": "contenido_neto", "label": "Contenido Neto", "type": "text", "required": False, "placeholder": "Ej: 1 kg, 500 g, Bulto 20 unidades", "section": "specs"},
            {"key": "unidades_por_bulto", "label": "Unidades por Bulto (si aplica)", "type": "number", "required": False, "placeholder": "Ej: 20", "section": "specs"},
        ],
    ),
    "Frutas, Verduras y Hortalizas": _build_schema(
        archetype="fresh_weight_and_portion",
        ui_hint="Para plátanos, cambures, aguacates, tomates, cebollas, papas, verduras para sopa y frutas. Puedes vender por kg, gramos, bandeja, unidad o armar Combos de Feria / Sopa.",
        buyer_ui_hint="Elige el peso o presentación y especifica el nivel de maduración (verde, pintón o maduro).",
        allowed_units=["kg", "g", "lb", "unit", "pack", "box", "combo"],
        default_unit="kg",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Presentación y Maduración",
            "axes": [
                {"key": "presentation", "label": "Peso / Empaque", "type": "select", "presets": ["500 g", "1 kg", "Bandeja", "Unidad", "Mano / Racimo", "Bolsa Surtida", "Saco / Cesta"]},
                {"key": "ripeness", "label": "Maduración / Estado", "type": "select", "presets": ["Verde", "Pintón (Semi-maduro)", "Maduro (Para hoy)", "Surtido (Verdes y Maduros)", "Pelado y Picado"]},
            ],
        },
        supports_modifier_groups=True,
        modifier_group_presets=[
            {
                "name": "Punto de Maduración",
                "required": False,
                "min_selections": 0,
                "max_selections": 1,
                "options": [
                    {"name": "Verde", "price_delta": 0.0},
                    {"name": "Pintón (Mitad y mitad)", "price_delta": 0.0},
                    {"name": "Maduro (Para consumir hoy)", "price_delta": 0.0},
                ],
            },
            {
                "name": "Preparación",
                "required": False,
                "min_selections": 0,
                "max_selections": 1,
                "options": [
                    {"name": "Entero natural", "price_delta": 0.0},
                    {"name": "Pelado y picado en bandeja", "price_delta": 0.5},
                ],
            },
        ],
        combo_item_placeholder="Ej: 1kg Plátano, 1kg Papa, 1kg Tomate, 1kg Cebolla, Monte para sopa...",
        combo_templates=[
            {
                "name": "Combo Verduras para Sopa / Hervido",
                "description": "Bandeja o bolsa lista con verduras seleccionadas para sancocho.",
                "combo_items": [
                    {"name": "Yuca, Ocumo y Ñame", "quantity": 1, "unit": "kg", "notes": "Surtido de verduras"},
                    {"name": "Auyama y Jojoto", "quantity": 500, "unit": "g", "notes": ""},
                    {"name": "Ramillete de Cilantro, Cebollín y Ají Dulce", "quantity": 1, "unit": "paq", "notes": ""},
                ],
            },
        ],
        order_notes_enabled=True,
        order_notes_placeholder="Ej: 2 plátanos maduros y 2 pintones, aguacate para hoy, tomates firmes...",
        fields=[
            {"key": "tipo_fresco", "label": "Clasificación", "type": "select", "required": False, "options": ["Frutas", "Verduras y Tubérculos (Papa, Yuca, Ocumo)", "Hortalizas y Vegetales", "Hierbas, Monte y Aliños", "Plátanos y Topocho", "Combo de Feria / Sopa"], "section": "details"},
            {"key": "origen", "label": "Origen / Cosecha", "type": "text", "required": False, "placeholder": "Ej: Los Andes (Mérida/Táchira), Colonia Tovar, Importado", "section": "details"},
            {"key": "estado_conservacion", "label": "Estado", "type": "select", "required": False, "options": ["Fresco del día", "Hidropónico", "Orgánico", "Pelado / Empacado al vacío"], "section": "specs"},
        ],
    ),
    "Carnicería y Aves": _build_schema(
        archetype="fresh_weight_and_portion",
        ui_hint="Cortes de res, pollo, cerdo, chorizos, hamburguesas artesanales y comida a la parrilla. Puedes vender por kg, bandeja, porción o crear Combos Parrilleros y Combos de Hamburguesa/Parrilla.",
        buyer_ui_hint="Elige el peso o presentación y cómo prefieres el corte (bistec, molida, mechar, entero o término de cocción).",
        allowed_units=["kg", "g", "lb", "unit", "pack", "portion", "combo"],
        default_unit="kg",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Corte / Peso / Presentación",
            "axes": [
                {"key": "cut_or_weight", "label": "Presentación / Peso", "type": "select", "presets": ["500 g", "1 kg", "Bandeja Familiar", "Pollo Entero", "Media Res / Pieza", "Porción Lista", "Combo Parrillero"]},
                {"key": "preparation", "label": "Tipo de Corte", "type": "select", "presets": ["En Bistec / Fileteado", "Molida", "Para Mechar", "En Trozos para Guisar", "Corte Grueso Parrillero", "Entero", "Limpio sin grasa"]},
            ],
        },
        supports_modifier_groups=True,
        modifier_group_presets=[
            {
                "name": "Preparación de Carnicería",
                "required": False,
                "min_selections": 0,
                "max_selections": 1,
                "options": [
                    {"name": "En bistec delgado", "price_delta": 0.0},
                    {"name": "En bistec grueso (Parrilla)", "price_delta": 0.0},
                    {"name": "Molida limpia", "price_delta": 0.0},
                    {"name": "En trozos / cubos", "price_delta": 0.0},
                    {"name": "Pieza entera", "price_delta": 0.0},
                ],
            },
        ] + DEFAULT_COMBO_CHOICE_PRESETS,
        combo_item_placeholder="Ej: 1kg Solomo, 1kg Pollo, 500g Chorizo, 1 Morcilla o 1 Hamburguesa + 1 Refresco + 1 Ensalada...",
        combo_templates=[
            {
                "name": "Combo Parrillero Fin de Semana",
                "description": "Todo listo para armar tu parrilla en casa.",
                "combo_items": [
                    {"name": "Solomo de Cuerito o Punta Trasera", "quantity": 1, "unit": "kg", "notes": ""},
                    {"name": "Pechuga o Churrasco de Pollo", "quantity": 1, "unit": "kg", "notes": ""},
                    {"name": "Chorizo Parrillero / Chistorra", "quantity": 500, "unit": "g", "notes": ""},
                    {"name": "Morcilla", "quantity": 500, "unit": "g", "notes": ""},
                ],
            },
        ] + FOOD_COMBO_TEMPLATES,
        order_notes_enabled=True,
        order_notes_placeholder="Ej: Poca grasa, picado en bistec, empacado en bolsas de 500g...",
        fields=[
            {"key": "tipo_carne", "label": "Tipo de Proteína", "type": "select", "required": False, "options": ["Res (Solomo, Punta, Lomito, Molida, Mechar)", "Pollo y Aves (Pechuga, Muslo, Entero, Alas)", "Cerdo (Chuleta, Costilla, Pernil, Lomo)", "Chorizos, Chistorras y Morcillas", "Carne de Hamburguesa", "Cordero / Chivo", "Parrilla / Pollo en Brasa Listo", "Combo Carnicero / Parrillero"], "section": "details"},
            {"key": "corte_especifico", "label": "Corte Específico", "type": "text", "required": False, "placeholder": "Ej: Punta Trasera Premium, Solomo de Cuerito, Pechuga sin hueso", "section": "details"},
            {"key": "estado_conservacion", "label": "Conservación", "type": "select", "required": False, "options": ["Fresco del día", "Madurado al vacío", "Congelado", "Listo para comer (Caliente)"], "section": "specs"},
        ],
    ),
    "Pescadería y Mariscos": _build_schema(
        archetype="fresh_weight_and_portion",
        ui_hint="Pargo, merluza, dorado, salmón, atún, camarones, calamares, pulpo y cazón. Vende por kg, bandeja, rueda o filete.",
        buyer_ui_hint="Elige el peso o empaque y cómo deseas que preparen tu pescado (entero limpio, en ruedas o filete).",
        allowed_units=["kg", "g", "lb", "unit", "pack", "portion", "combo"],
        default_unit="kg",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Corte y Presentación",
            "axes": [
                {"key": "cut", "label": "Corte / Limpieza", "type": "select", "presets": ["Filete sin espinas", "En Ruedas", "Entero Evicerado y Escamado", "Pelado y Desvenado (Camarón)", "Bandeja 500 g", "Paquete 1 kg"]},
            ],
        },
        supports_modifier_groups=True,
        modifier_group_presets=[
            {
                "name": "Preparación del Pescado",
                "required": False,
                "min_selections": 0,
                "max_selections": 1,
                "options": [
                    {"name": "Entero limpio (sin escamas ni vísceras)", "price_delta": 0.0},
                    {"name": "Cortado en ruedas", "price_delta": 0.0},
                    {"name": "En filetes", "price_delta": 0.0},
                ],
            },
        ],
        combo_item_placeholder="Ej: 500g Camarón, 500g Calamar, 500g Mejillones, 500g Pepitonas...",
        combo_templates=[
            {
                "name": "Combo Paella / Mariscada",
                "description": "Surtido de mariscos limpios para paella, fosforera o arroz a la marinera.",
                "combo_items": [
                    {"name": "Camarones Pelados", "quantity": 500, "unit": "g", "notes": ""},
                    {"name": "Anillos de Calamar", "quantity": 500, "unit": "g", "notes": ""},
                    {"name": "Mejillones / Pepitonas", "quantity": 500, "unit": "g", "notes": ""},
                ],
            },
        ],
        fields=[
            {"key": "especie", "label": "Especie", "type": "select", "required": False, "options": ["Pargo", "Merluza / Curvina", "Dorado / Carite", "Atún / Salmón", "Cazón / Raya", "Camarones / Langostinos", "Calamares y Pulpo", "Mix de Mariscos / Paella"], "section": "details"},
            {"key": "estado_conservacion", "label": "Estado", "type": "select", "required": False, "options": ["Fresco del día", "Congelado IQF", "Empacado al vacío", "Salado / Seco"], "section": "specs"},
        ],
    ),
    "Charcutería": _build_schema(
        archetype="fresh_weight_and_portion",
        ui_hint="Jamón de pierna, pavo, tocineta, salchichas, chorizos, mortadela, salami y tablas de embutidos. Vende por kg, gramos, paquete o arma Combos Charcuteros.",
        buyer_ui_hint="Elige cuántos gramos o kilos deseas y el grosor de las rebanadas.",
        allowed_units=["kg", "g", "lb", "unit", "pack", "combo"],
        default_unit="kg",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Peso y Tipo de Rebanado",
            "axes": [
                {"key": "weight", "label": "Peso / Presentación", "type": "select", "presets": ["100 g", "200 g", "250 g", "500 g", "1 kg", "Pieza Entera", "Paquete Sellado"]},
                {"key": "slice", "label": "Rebanado", "type": "select", "presets": ["Rebanado Fino", "Rebanado Normal", "Rebanado Grueso", "En Trozo / Taco"]},
            ],
        },
        supports_modifier_groups=True,
        modifier_group_presets=[
            {
                "name": "Grosor del Rebanado",
                "required": False,
                "min_selections": 0,
                "max_selections": 1,
                "options": [
                    {"name": "Rebanado bien finito (con separador)", "price_delta": 0.0},
                    {"name": "Rebanado estándar", "price_delta": 0.0},
                    {"name": "En trozo sin rebanar", "price_delta": 0.0},
                ],
            },
        ],
        combo_item_placeholder="Ej: 500g Jamón de Pierna, 500g Queso Amarillo, 250g Tocineta...",
        combo_templates=[
            {
                "name": "Combo Desayuno Charcutero",
                "description": "Jamón, queso y tocineta rebanados para la semana.",
                "combo_items": [
                    {"name": "Jamón de Pierna o Pavo", "quantity": 500, "unit": "g", "notes": "Rebanado fino"},
                    {"name": "Queso Blanco o Amarillo", "quantity": 500, "unit": "g", "notes": "Rebanado"},
                    {"name": "Tocineta Ahumada", "quantity": 250, "unit": "g", "notes": ""},
                ],
            },
        ],
        order_notes_enabled=True,
        order_notes_placeholder="Ej: Rebanado bien finito con separadores plásticos...",
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Plumrose, Oscar Mayer, Alibal, Hermo, La Montserratina", "section": "details"},
            {"key": "tipo_embutido", "label": "Tipo de Charcutería", "type": "select", "required": False, "options": ["Jamón de Pierna / Espaldilla", "Pechuga de Pavo / Pollo", "Tocineta Ahumada", "Mortadela / Bologna", "Salchichas", "Salami / Pepperoni / Jamón Serrano", "Tabla de Charcutería"], "section": "details"},
            {"key": "requiere_refrigeracion", "label": "Requiere Refrigeración", "type": "boolean", "required": False, "section": "specs"},
        ],
    ),
    "Lácteos y Huevos": _build_schema(
        archetype="fresh_weight_and_portion",
        ui_hint="Queso blanco duro/llanero, paisa, guayanés, telita, mano, mozzarella, amarillo, suero, natilla, mantequilla, yogurt, leche y cartones de huevos.",
        buyer_ui_hint="Selecciona el peso (en quesos) o la cantidad de huevos (medio cartón 15 und, cartón 30 und, docena).",
        allowed_units=["kg", "g", "unit", "pack", "dozen", "box", "l", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Presentación / Peso / Cantidad",
            "axes": [
                {"key": "presentation", "label": "Presentación", "type": "select", "presets": ["Medio Cartón (15 huevos)", "Cartón Completo (30 huevos)", "Docena (12 huevos)", "Caja (12 cartones)", "250 g", "500 g", "1 kg", "1 Litro", "Pote 500 g"]},
                {"key": "cut", "label": "Preparación (Quesos)", "type": "select", "presets": ["En Trozo", "Rebanado", "Rallado", "No aplica"]},
            ],
        },
        supports_modifier_groups=True,
        combo_item_placeholder="Ej: 1 Cartón de Huevos + 1kg Queso Blanco Duro + 1 Suero...",
        combo_templates=[
            {
                "name": "Combo Queso + Cartón de Huevos",
                "description": "1 Cartón de huevos (30 und) + 1 kg de Queso Blanco.",
                "combo_items": [
                    {"name": "Cartón de Huevos (30 und)", "quantity": 1, "unit": "paq", "notes": "Huevos frescos"},
                    {"name": "Queso Blanco Duro / Semiduro", "quantity": 1, "unit": "kg", "notes": ""},
                ],
            },
        ],
        fields=[
            {"key": "tipo_lacteo_huevo", "label": "Tipo de Producto", "type": "select", "required": False, "options": ["Huevos de Gallina / Codorniz", "Queso Blanco (Duro, Llanero, Semiduro, Paisa)", "Queso Fresco (Guayanés, Telita, Mano, Mozzarella)", "Queso Amarillo (Gouda, Edam, Parmesano)", "Leche Líquida / Crema de Leche", "Mantequilla y Margarina", "Suero, Natilla y Ricotta", "Yogurt"], "section": "details"},
            {"key": "marca", "label": "Marca / Productor", "type": "text", "required": False, "placeholder": "Ej: Paisa, Los Andes, Torondoy, Mavesa, Finca Nacional", "section": "details"},
            {"key": "unidades_por_empaque", "label": "Cantidad / Peso", "type": "text", "required": False, "placeholder": "Ej: 30 unidades (Cartón) / 1 kg", "section": "specs"},
        ],
    ),
    "Panadería y Pastelería": _build_schema(
        archetype="prepared_or_beverage",
        ui_hint="Pan canilla, campesino, pan de jamón, cachitos, pastelitos, empanadas, arepas, hamburguesas, pizzas, tortas, quesillos y comida preparada. Ideal también para crear Combos de Comida (ej. 1 Hamburguesa + 1 Refresco + 1 Ensalada).",
        buyer_ui_hint="Elige el tamaño, relleno o las opciones de bebida y contorno de tu combo.",
        allowed_units=["unit", "combo", "portion", "pack", "dozen", "kg"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tamaño / Relleno / Versión",
            "axes": [
                {"key": "size_or_portion", "label": "Tamaño / Presentación", "type": "select", "presets": ["Individual / Unidad", "Combo con Bebida y Contorno", "Media Docena (6 und)", "Docena (12 und)", "Mediana", "Familiar / Completa"]},
                {"key": "flavor_or_filling", "label": "Sabor / Relleno", "type": "text", "presets": ["Clásica", "Especial con Todo", "Queso", "Jamón y Queso", "Carne Mechada", "Pollo", "Chocolate", "Arequipe", "Tres Leches"]},
            ],
        },
        supports_modifier_groups=True,
        modifier_group_presets=DEFAULT_COMBO_CHOICE_PRESETS + [
            {
                "name": "Salsas y Aderezos",
                "required": False,
                "min_selections": 0,
                "max_selections": 5,
                "options": [
                    {"name": "Salsa de Ajo", "price_delta": 0.0},
                    {"name": "Salsa Tártara", "price_delta": 0.0},
                    {"name": "Guasacaca", "price_delta": 0.0},
                    {"name": "Ketchup / Mayonesa / Mostaza", "price_delta": 0.0},
                    {"name": "Picante aparte", "price_delta": 0.0},
                ],
            },
        ],
        combo_item_placeholder="Ej: 1 Hamburguesa + 1 Refresco + 1 Ensalada, o 2 Pastelitos + 1 Malta...",
        combo_templates=FOOD_COMBO_TEMPLATES + [
            {
                "name": "Combo Desayuno Venezolano",
                "description": "2 Empanadas o Pastelitos + 1 Malta o Jugo Natural.",
                "combo_items": [
                    {"name": "Empanada o Pastelito Recién Hecho", "quantity": 2, "unit": "und", "notes": "Sabor a elección"},
                    {"name": "Malta, Café con Leche o Jugo", "quantity": 1, "unit": "und", "notes": "Bien frío / caliente"},
                ],
            },
        ],
        order_notes_enabled=True,
        order_notes_placeholder="Ej: Sin cebolla, salsas aparte, dedicatoria 'Feliz Cumpleaños'...",
        fields=[
            {"key": "tipo_producto", "label": "Tipo de Producto", "type": "select", "required": False, "options": ["Panadería (Canilla, Campesino, Sándwich, Pan de Jamón)", "Desayunos (Empanadas, Arepas, Cachitos, Pastelitos, Golfeados)", "Comida Rápida (Hamburguesas, Perros Calientes, Pepitos, Pizzas)", "Almuerzos, Pollo y Platos Preparados", "Pastelería y Tortas (Porción o Completa)", "Galletas y Dulces Secos", "Combo Especial"], "section": "details"},
            {"key": "tiempo_preparacion_min", "label": "Tiempo estimado de entrega/preparación", "type": "number", "required": False, "unit_suffix": "min", "placeholder": "Ej: 15", "section": "specs"},
            {"key": "porciones_personas", "label": "Rinde para (Personas / Porciones)", "type": "text", "required": False, "placeholder": "Ej: Individual / 2 personas / 10 porciones", "section": "specs"},
        ],
    ),
    "Enlatados y Conservas": _build_schema(
        archetype="grocery_packaged",
        ui_hint="Atún enlatado, sardinas, maíz dulce, guisantes, diablito endiablado, aceitunas, alcaparras, duraznos en almíbar y frijoles en lata.",
        buyer_ui_hint="Selecciona la presentación (lata individual, pack o caja).",
        allowed_units=["unit", "pack", "box", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tamaño / Medio de Conserva",
            "axes": [
                {"key": "size", "label": "Tamaño de Lata", "type": "select", "presets": ["Pequeña (85g - 140g)", "Mediana (170g - 200g)", "Grande (300g - 400g)", "Pack x3", "Caja Cerrada"]},
                {"key": "medium", "label": "Variante", "type": "select", "presets": ["En Aceite", "En Agua", "Con Vegetales", "Picante", "En Salsa de Tomate"]},
            ],
        },
        combo_item_placeholder="Ej: 3 Latas de Atún + 1 Maíz Dulce + 1 Diablito...",
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Margarita, Eveba, Underwood, Eureka, Del Monte", "section": "details"},
            {"key": "contenido_neto", "label": "Peso Neto / Escurrido", "type": "text", "required": False, "placeholder": "Ej: 140 g", "section": "specs"},
            {"key": "abre_facil", "label": "Tapa Abre Fácil", "type": "boolean", "required": False, "section": "specs"},
        ],
    ),
    "Salsas, Condimentos y Aceites": _build_schema(
        archetype="grocery_packaged",
        ui_hint="Aceite vegetal/maíz/soya/oliva, mayonesa, salsa de tomate ketchup, mostaza, salsa de ajo, inglesa, soya, picante, vinagre, adobo, cubitos y especias.",
        buyer_ui_hint="Elige el tamaño del envase (sobre, frasco, litro o galón).",
        allowed_units=["unit", "l", "ml", "gal", "pack", "box", "g", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tamaño / Contenido",
            "axes": [
                {"key": "size", "label": "Presentación", "type": "select", "presets": ["Sobre 50g", "Frasco 150 ml", "200 g", "445 g", "500 ml", "900 g", "1 Litro", "Galón (3.78L)", "Bidón 5L", "Caja / Display"]},
            ],
        },
        combo_item_placeholder="Ej: 1 Mayonesa 445g + 1 Salsa de Tomate 397g + 1 Mostaza...",
        combo_templates=[
            {
                "name": "Combo Salsas (Mayonesa + Ketchup + Mostaza)",
                "description": "Trío de salsas esenciales para el hogar o perro calientes.",
                "combo_items": [
                    {"name": "Mayonesa", "quantity": 1, "unit": "und", "notes": "445g"},
                    {"name": "Salsa de Tomate Ketchup", "quantity": 1, "unit": "und", "notes": "397g"},
                    {"name": "Mostaza", "quantity": 1, "unit": "und", "notes": "200g"},
                ],
            },
        ],
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Mavesa, Heinz, Pampero, Mazeite, Vatel, Iberia, Maggi, Carmencita", "section": "details"},
            {"key": "tipo_producto", "label": "Categoría", "type": "select", "required": False, "options": ["Aceite Vegetal / Maíz / Girasol", "Aceite de Oliva", "Mayonesa", "Salsa de Tomate / Ketchup / Pasta", "Mostaza y Salsas para Carnes", "Vinagre", "Condimentos, Especias y Cubitos", "Combo de Salsas"], "section": "details"},
            {"key": "contenido_neto", "label": "Contenido Neto", "type": "text", "required": False, "placeholder": "Ej: 1 Litro, 445 g, 150 ml", "section": "specs"},
        ],
    ),
    "Café, Té e Infusiones": _build_schema(
        archetype="grocery_packaged",
        ui_hint="Café molido, café en grano, café instantáneo, cacao, té negro/verde, manzanilla y bebidas de café listas para llevar.",
        buyer_ui_hint="Selecciona el peso (100g, 250g, 500g, 1kg) y el tipo de molienda o preparación.",
        allowed_units=["unit", "pack", "kg", "g", "box", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Peso y Tipo de Molienda",
            "axes": [
                {"key": "weight", "label": "Peso / Presentación", "type": "select", "presets": ["100 g", "200 g", "250 g", "500 g", "1 kg", "Caja x20 sobres", "Vaso 8 oz", "Vaso 12 oz"]},
                {"key": "grind", "label": "Molienda / Tueste", "type": "select", "presets": ["Molido Estándar (Greca/Colador)", "Molido Espresso", "En Grano Entero", "Descafeinado", "Instantáneo"]},
            ],
        },
        combo_item_placeholder="Ej: 2 Paquetes de Café 250g + 1 Azúcar 1kg...",
        fields=[
            {"key": "marca", "label": "Marca / Origen", "type": "text", "required": False, "placeholder": "Ej: Fama de América, Madrid, Páramo, Amanecer, San Salvador, McCormick", "section": "details"},
            {"key": "tipo_molienda", "label": "Presentación", "type": "select", "required": False, "options": ["Café Molido Gourmet", "Café en Grano", "Café Instantáneo", "Té / Infusión en Sobres", "Cacao / Chocolate en Polvo", "Café Listo (Bebida)"], "section": "specs"},
            {"key": "contenido_neto", "label": "Peso Neto", "type": "text", "required": False, "placeholder": "Ej: 250 g, 500 g", "section": "specs"},
        ],
    ),
    "Bebidas, Refrescos y Maltas": _build_schema(
        archetype="prepared_or_beverage",
        ui_hint="Refrescos (lata, 1.5L, 2L), maltas, jugos naturales o pasteurizados, té frío, agua mineral, botellones de agua (20L) y bebidas energizantes.",
        buyer_ui_hint="Elige el sabor, tamaño (lata, litro, six-pack o caja) y si la deseas fría o natural.",
        allowed_units=["unit", "pack", "box", "l", "ml", "gal", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tamaño / Sabor / Empaque",
            "axes": [
                {"key": "volume", "label": "Presentación", "type": "select", "presets": ["Lata 355 ml", "Botella 355 ml", "Botella 600 ml", "1 Litro", "1.5 Litros", "2 Litros", "Botellón 5 Litros", "Botellón 20 Litros", "Six-Pack (6 und)", "Caja / Bulto (24 und)"]},
                {"key": "flavor", "label": "Sabor", "type": "text", "presets": ["Cola Negra", "Sin Azúcar / Zero", "Kolita", "Limón / Chinotto", "Naranja", "Uva", "Manzana", "Durazno", "Parchita"]},
            ],
        },
        supports_modifier_groups=True,
        modifier_group_presets=[
            {
                "name": "Temperatura de Entrega",
                "required": False,
                "min_selections": 0,
                "max_selections": 1,
                "options": [
                    {"name": "Bien fría (De nevera)", "price_delta": 0.0},
                    {"name": "Natural / Al clima", "price_delta": 0.0},
                ],
            },
        ],
        combo_item_placeholder="Ej: 2 Refrescos 1.5L + 1 Six-pack de Malta...",
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Coca-Cola, Pepsi, Maltín Polar, Yukery, Minalba, Gatorade, Nestea", "section": "details"},
            {"key": "volumen_neto", "label": "Volumen", "type": "text", "required": False, "placeholder": "Ej: 1.5 L, 355 ml, 20 L", "section": "specs"},
            {"key": "retornable", "label": "Envase Retornable", "type": "boolean", "required": False, "section": "specs"},
            {"key": "sin_azucar", "label": "Sin Azúcar / Light / Zero", "type": "boolean", "required": False, "section": "details"},
        ],
    ),
    "Licores": _build_schema(
        archetype="prepared_or_beverage",
        ui_hint="Cervezas (tercio, lata, six-pack, caja/gavera), rones venezolanos, whiskies, vinos, sangrías, vodka y combos rumberos con hielo y refresco.",
        buyer_ui_hint="Selecciona la presentación (unidad, six-pack, caja o combo con mezclador y hielo).",
        allowed_units=["unit", "pack", "box", "l", "ml", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Presentación de Venta",
            "axes": [
                {"key": "presentation", "label": "Presentación", "type": "select", "presets": ["Botella / Tercio", "Lata 355 ml", "Six-Pack (6 und)", "Media Caja (12 und)", "Caja / Gavera (24 und)", "Caja (36 und)", "Botella 0.70L / 750ml", "Botella 1 Litro", "Botella 1.75L"]},
            ],
        },
        supports_modifier_groups=True,
        modifier_group_presets=[
            {
                "name": "Temperatura y Adicionales",
                "required": False,
                "min_selections": 0,
                "max_selections": 3,
                "options": [
                    {"name": "Bien fría (Lista para tomar)", "price_delta": 0.0},
                    {"name": "Agregar Bolsa de Hielo", "price_delta": 2.0},
                    {"name": "Agregar Vasos Descartables", "price_delta": 1.5},
                ],
            },
        ],
        combo_item_placeholder="Ej: 1 Botella de Ron + 1 Coca-Cola 1.5L + 1 Bolsa de Hielo + Limones...",
        combo_templates=[
            {
                "name": "Combo Cuba Libre (Ron + Refresco + Hielo)",
                "description": "1 Botella de Ron 0.70L + 1 Refresco 1.5L + 1 Bolsa de Hielo.",
                "combo_items": [
                    {"name": "Botella de Ron", "quantity": 1, "unit": "botella", "notes": "0.70L"},
                    {"name": "Refresco Cola 1.5L", "quantity": 1, "unit": "botella", "notes": "Frío"},
                    {"name": "Bolsa de Hielo", "quantity": 1, "unit": "paq", "notes": ""},
                ],
            },
        ],
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Polar, Solera, Zulia, Santa Teresa, Cacique, Diplomático, Old Parr, Caroreña", "section": "details"},
            {"key": "tipo_licor", "label": "Tipo de Bebida", "type": "select", "required": False, "options": ["Cerveza", "Ron Añejo", "Whisky / Escocés", "Vino Tinto / Blanco / Rosado", "Sangría / Tinto de Verano", "Espumante / Prosecco", "Vodka / Ginebra / Tequila", "Anís / Ponche Crema", "Combo Rumbero"], "section": "details"},
            {"key": "volumen_neto", "label": "Volumen", "type": "text", "required": False, "placeholder": "Ej: 750 ml, 222 ml, 355 ml", "section": "specs"},
            {"key": "grado_alcoholico", "label": "Grado Alcohólico", "type": "text", "required": False, "placeholder": "Ej: 40° GL / 4.5%", "section": "specs"},
        ],
    ),
    "Chucherías, Snacks y Dulces": _build_schema(
        archetype="prepared_or_beverage",
        ui_hint="Chocolates Savoy, galletas, pepitos, doritos, tostones, maní, caramelos, gomitas, helados y combos de chucherías o regalo.",
        buyer_ui_hint="Elige el sabor, tamaño (detal, familiar o display) o revisa qué trae el combo.",
        allowed_units=["unit", "pack", "box", "kg", "g", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Sabor y Presentación",
            "axes": [
                {"key": "presentation", "label": "Presentación", "type": "select", "presets": ["Unidad / Detal", "Tamaño Grande / Familiar", "Pack x4 / x6", "Display / Tira (12 und)", "Caja (24 und)"]},
                {"key": "flavor", "label": "Sabor", "type": "text", "presets": ["Chocolate con Leche", "Chocolate Oscuro", "Queso", "Picante", "Vainilla", "Fresa", "Arequipe", "Limón"]},
            ],
        },
        combo_item_placeholder="Ej: 1 Samba + 1 Toronto + 1 Cocosette + 1 Pepito + 1 Refresco...",
        combo_templates=[
            {
                "name": "Combo Chucherías Venezolanas",
                "description": "Selección de chocolates, galletas y snacks salados.",
                "combo_items": [
                    {"name": "Chocolate / Galleta Dulce", "quantity": 3, "unit": "und", "notes": "Surtidos"},
                    {"name": "Snack Salado (Pepito / Doritos / Tostones)", "quantity": 2, "unit": "paq", "notes": ""},
                    {"name": "Refresco o Malta", "quantity": 1, "unit": "und", "notes": ""},
                ],
            },
        ],
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Savoy, Puig, Nabisco, Frito-Lay, Pirulín, Nucita, Tío Rico", "section": "details"},
            {"key": "tipo_snack", "label": "Tipo", "type": "select", "required": False, "options": ["Chocolates y Bombones", "Galletas Dulces y Saladas", "Snacks Salados (Pepitos, Papas, Tostones)", "Frutos Secos y Maní", "Caramelos, Chupetas y Gomitas", "Dulces Criollos", "Helados", "Combo de Chucherías"], "section": "details"},
            {"key": "contenido_neto", "label": "Peso Neto", "type": "text", "required": False, "placeholder": "Ej: 32 g, 150 g", "section": "specs"},
        ],
    ),
    "Congelados y Pasapalos": _build_schema(
        archetype="prepared_or_beverage",
        ui_hint="Tequeños crudos o listos para comer, pastelitos andinos, empanaditas, masa fácil, nuggets, papas prefritas y Combos Festeros de Pasapalos.",
        buyer_ui_hint="Selecciona la cantidad (bandeja de 12, 20, 50 o 100 unidades), el relleno y si los deseas crudos (congelados) o fritos listos para comer.",
        allowed_units=["pack", "dozen", "unit", "box", "kg", "combo", "portion"],
        default_unit="pack",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Cantidad, Relleno y Estado",
            "axes": [
                {"key": "count", "label": "Cantidad / Bandeja", "type": "select", "presets": ["Ración (5-6 und)", "Docena (12 und)", "Bandeja x20 und", "Bandeja x24 und", "Bandeja x50 und", "Caja Fiesta x100 und", "Bolsa 1 kg", "Bolsa 2.5 kg"]},
                {"key": "filling", "label": "Relleno / Sabor", "type": "select", "presets": ["Queso Blanco", "Guayaba y Queso", "Jamón y Queso", "Carne Molida", "Pollo", "Pizza", "Chistorra", "Chocolate / Nutella", "Mixto Surtido"]},
            ],
        },
        supports_modifier_groups=True,
        modifier_group_presets=[
            {
                "name": "Modo de Entrega",
                "required": False,
                "min_selections": 0,
                "max_selections": 1,
                "options": [
                    {"name": "Congelados (Para freír/hornear en casa)", "price_delta": 0.0},
                    {"name": "Fritos / Listos para comer", "price_delta": 1.5},
                ],
            },
        ] + DEFAULT_COMBO_CHOICE_PRESETS,
        combo_item_placeholder="Ej: 25 Tequeños + 25 Pastelitos + 1 Salsa Tártara + 1 Refresco 1.5L...",
        combo_templates=[
            {
                "name": "Combo Pasapalos Festero (50 Unidades + Salsa + Bebida)",
                "description": "Ideal para reuniones, cumpleaños y compartir.",
                "combo_items": [
                    {"name": "Tequeños de Queso", "quantity": 25, "unit": "und", "notes": ""},
                    {"name": "Pastelitos Surtidos (Carne/Pollo/Queso)", "quantity": 25, "unit": "und", "notes": ""},
                    {"name": "Salsa de Ajo o Tártara", "quantity": 1, "unit": "und", "notes": "Envase 8 oz"},
                    {"name": "Refresco 1.5L", "quantity": 1, "unit": "botella", "notes": ""},
                ],
            },
        ],
        fields=[
            {"key": "tipo_congelado", "label": "Tipo de Producto", "type": "select", "required": False, "options": ["Tequeños", "Pastelitos y Empanaditas", "Masas y Discos para Pastelitos", "Papas Prefritas y Yuca Congelada", "Nuggets, Milanesas y Croquetas", "Combo de Pasapalos"], "section": "details"},
            {"key": "unidades_por_empaque", "label": "Unidades por Bandeja", "type": "number", "required": False, "placeholder": "Ej: 20", "section": "specs"},
            {"key": "estado_entrega", "label": "Estado", "type": "select", "required": False, "options": ["Crudo Congelado", "Precocido Congelado", "Frito / Listo para comer"], "section": "specs"},
        ],
    ),
    "Avena y Cereales": _build_schema(
        archetype="grocery_packaged",
        ui_hint="Avena en hojuelas o molida, fororo, crema de arroz, cereales infantiles y de desayuno (Corn Flakes, Zucaritas, Flips, Granola).",
        buyer_ui_hint="Elige el tamaño del empaque (bolsa, caja o vaso).",
        allowed_units=["unit", "pack", "box", "kg", "g", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Peso / Sabor",
            "axes": [
                {"key": "weight", "label": "Contenido", "type": "select", "presets": ["200 g", "300 g", "400 g", "500 g", "800 g", "1 kg"]},
                {"key": "type", "label": "Tipo / Sabor", "type": "text", "presets": ["En Hojuelas", "Molida", "Chocolate", "Avellana", "Miel y Almendras", "Tradicional"]},
            ],
        },
        combo_item_placeholder="Ej: 2 Avenas 400g + 1 Leche en Polvo 400g + 1 Cereal...",
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Quaker, Avelina, Alfonso Rivas, Flips, Kellogg's, Maizoritos", "section": "details"},
            {"key": "contenido_neto", "label": "Peso Neto", "type": "text", "required": False, "placeholder": "Ej: 400 g, 800 g", "section": "specs"},
        ],
    ),

    # Alias legacy de Alimentos y Bebidas (compatibilidad hacia atrás)
    "Frescos": _build_schema(
        archetype="fresh_weight_and_portion",
        ui_hint="Frutas, verduras, carnes, aves y pescados. Puedes vender por kg, gramos, bandeja o armar combos.",
        buyer_ui_hint="Elige el peso o presentación y especifica cómo lo prefieres.",
        allowed_units=["kg", "g", "lb", "unit", "pack", "portion", "combo"],
        default_unit="kg",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Presentaciones o Pesos",
            "axes": [
                {"key": "presentation", "label": "Presentación / Peso", "type": "select", "presets": ["250 g", "500 g", "1 kg", "Bandeja", "Unidad"]},
                {"key": "ripeness_or_cut", "label": "Maduración / Corte", "type": "select", "presets": ["Verde", "Pintón", "Maduro", "Entero", "Fileteado", "Molido"]},
            ],
        },
        supports_modifier_groups=True,
        fields=[
            {"key": "tipo_fresco", "label": "Tipo de Producto", "type": "select", "required": False, "options": ["Frutas", "Verduras y Hortalizas", "Carnes Rojas", "Pollo y Aves", "Pescados y Mariscos"], "section": "details"},
            {"key": "estado_conservacion", "label": "Estado de Conservación", "type": "select", "required": False, "options": ["Fresco del día", "Refrigerado", "Congelado", "Al vacío"], "section": "specs"},
        ],
    ),
    "Charcutería y Lácteos": _build_schema(
        archetype="fresh_weight_and_portion",
        ui_hint="Quesos, jamones, embutidos, huevos y lácteos. Puedes vender por kg, gramos, paquete o unidad.",
        buyer_ui_hint="Selecciona cuántos gramos o kilos deseas y cómo prefieres el corte.",
        allowed_units=["kg", "g", "unit", "pack", "dozen", "l", "combo"],
        default_unit="kg",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Presentaciones por Peso",
            "axes": [
                {"key": "weight_option", "label": "Peso / Presentación", "type": "select", "presets": ["200 g", "250 g", "500 g", "1 kg", "Pieza entera"]},
                {"key": "cut_style", "label": "Tipo de Corte", "type": "select", "presets": ["Rebanado fino", "Rebanado normal", "Trozos / Taco", "Rallado"]},
            ],
        },
        supports_modifier_groups=True,
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Plumrose, Paisa, Los Andes", "section": "details"},
        ],
    ),
    "Despensa y Víveres": _build_schema(
        archetype="grocery_packaged",
        ui_hint="Harinas, arroz, pasta, granos, aceites, salsas, enlatados y comida preparada.",
        buyer_ui_hint="Elige la presentación o adicionales disponibles.",
        allowed_units=["unit", "pack", "box", "kg", "g", "l", "ml", "portion", "combo"],
        default_unit="unit",
        supports_variants=True,
        supports_modifier_groups=True,
        combo_templates=FOOD_COMBO_TEMPLATES,
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: PAN, Primor, Mary, Mavesa", "section": "details"},
            {"key": "contenido_neto", "label": "Contenido Neto", "type": "text", "required": False, "placeholder": "Ej: 1 kg, 500 g", "section": "specs"},
        ],
    ),
    "Bebidas": _build_schema(
        archetype="prepared_or_beverage",
        ui_hint="Refrescos, agua, jugos, café, té y malta.",
        buyer_ui_hint="Elige el tamaño o sabor de tu bebida.",
        allowed_units=["unit", "pack", "box", "l", "ml", "combo"],
        default_unit="unit",
        supports_variants=True,
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Pepsi, Coca-Cola, Maltín Polar, Minalba", "section": "details"},
        ],
    ),
    "Snacks y Dulces": _build_schema(
        archetype="prepared_or_beverage",
        ui_hint="Chucherías, chocolates, galletas, tortas, postres, comida rápida y combos.",
        buyer_ui_hint="Elige el sabor, tamaño y tus extras favoritos.",
        allowed_units=["unit", "pack", "box", "portion", "combo", "kg", "g"],
        default_unit="unit",
        supports_variants=True,
        supports_modifier_groups=True,
        combo_templates=FOOD_COMBO_TEMPLATES,
        fields=[
            {"key": "marca", "label": "Marca / Elaboración", "type": "text", "required": False, "placeholder": "Ej: Savoy, Puig, Artesanal", "section": "details"},
        ],
    ),
    "Limpieza del Hogar": _build_schema(
        archetype="grocery_packaged",
        ui_hint="Detergentes, cloro, desinfectantes, lavaplatos y papel higiénico.",
        buyer_ui_hint="Selecciona el aroma y tamaño de presentación.",
        allowed_units=["unit", "l", "ml", "gal", "kg", "g", "pack", "box", "combo"],
        default_unit="unit",
        supports_variants=True,
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Las Llaves, Ace, Ariel, Rosal", "section": "details"},
        ],
    ),

    # --------------------------------------------------------------------------
    # 2. TECNOLOGÍA Y ELECTRÓNICA (16 SUBCATEGORÍAS OFICIALES + ALIAS LEGACY)
    # --------------------------------------------------------------------------
    "Teléfonos y Tablets": _build_schema(
        archetype="mobile_and_computing",
        ui_hint="Especifica marca, modelo exacto, almacenamiento interno, memoria RAM, estado del equipo, SIM y garantía. Agrega variantes por capacidad o color.",
        buyer_ui_hint="Selecciona el color y la capacidad de almacenamiento antes de comprar.",
        allowed_units=["unit", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Almacenamiento y Color",
            "axes": [
                {"key": "storage", "label": "Almacenamiento", "type": "select", "presets": ["32 GB", "64 GB", "128 GB", "256 GB", "512 GB", "1 TB"]},
                {"key": "ram", "label": "Memoria RAM", "type": "select", "presets": ["4 GB", "6 GB", "8 GB", "12 GB", "16 GB"]},
                {"key": "color", "label": "Color", "type": "text", "presets": ["Negro", "Blanco", "Plata", "Titanio Natural", "Titanio Desierto", "Azul", "Morado", "Verde", "Dorado"]},
            ],
        },
        combo_item_placeholder="Ej: 1 Teléfono + 1 Forro Antigolpes + 1 Vidrio Templado + 1 Cargador 20W...",
        combo_templates=[
            {
                "name": "Combo Smartphone + Forro + Vidrio Templado + Cargador",
                "description": "Equipo listo para usar con protección completa.",
                "combo_items": [
                    {"name": "Smartphone / Teléfono", "quantity": 1, "unit": "und", "notes": "Nuevo en caja"},
                    {"name": "Forro Protector", "quantity": 1, "unit": "und", "notes": ""},
                    {"name": "Vidrio Templado 9D", "quantity": 1, "unit": "und", "notes": "Instalado"},
                    {"name": "Taco Cargador Carga Rápida", "quantity": 1, "unit": "und", "notes": ""},
                ],
            },
        ],
        fields=[
            {"key": "marca", "label": "Marca", "type": "select", "required": True, "options": ["Apple", "Samsung", "Xiaomi / Redmi / POCO", "Tecno", "Infinix", "Motorola", "Honor", "Realme", "Huawei", "ZTE / Blade", "Google Pixel", "Otra"], "section": "details"},
            {"key": "modelo", "label": "Modelo Exacto", "type": "text", "required": True, "placeholder": "Ej: iPhone 15 Pro Max / Redmi Note 13 Pro+ / Tecno Spark 20", "section": "details"},
            {"key": "almacenamiento", "label": "Almacenamiento Interno", "type": "select", "required": False, "options": ["32 GB", "64 GB", "128 GB", "256 GB", "512 GB", "1 TB"], "section": "specs"},
            {"key": "ram", "label": "Memoria RAM", "type": "select", "required": False, "options": ["2 GB", "3 GB", "4 GB", "6 GB", "8 GB", "12 GB", "16 GB", "24 GB"], "section": "specs"},
            {"key": "dual_sim", "label": "SIM / Conectividad", "type": "select", "required": False, "options": ["Dual SIM Física (Liberado)", "SIM Física + eSIM", "Solo eSIM", "Single SIM", "Solo Wi-Fi (Tablet)"], "section": "specs"},
            {"key": "condicion", "label": "Condición del Equipo", "type": "select", "required": True, "options": ["Nuevo (Sellado)", "Open Box", "Reacondicionado / Refurbished", "Usado - Como Nuevo", "Usado - Buen Estado"], "section": "condition"},
            _warranty_field("Ej: 3 meses, 6 meses o 1 año"),
        ],
    ),
    "Computadoras y Laptops": _build_schema(
        archetype="mobile_and_computing",
        ui_hint="Para laptops, MacBooks, PCs de escritorio, All-in-One y Mini PC. Detalla procesador, memoria RAM, disco SSD, pantalla y tarjeta gráfica.",
        buyer_ui_hint="Revisa las especificaciones técnicas y elige la configuración deseada.",
        allowed_units=["unit", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Configuración (RAM / SSD / Color)",
            "axes": [
                {"key": "config", "label": "RAM y Almacenamiento", "type": "select", "presets": ["8GB RAM / 256GB SSD", "8GB RAM / 512GB SSD", "16GB RAM / 512GB SSD", "16GB RAM / 1TB SSD", "32GB RAM / 1TB SSD"]},
                {"key": "color", "label": "Color", "type": "text", "presets": ["Plata", "Gris Espacial", "Negro", "Azul Medianoche"]},
            ],
        },
        combo_item_placeholder="Ej: 1 Laptop + 1 Mouse Inalámbrico + 1 Morral / Forro...",
        fields=[
            {"key": "marca", "label": "Marca", "type": "select", "required": True, "options": ["Apple", "HP", "Lenovo", "Dell", "ASUS", "Acer", "MSI", "Samsung", "Gigabyte", "Clon / Ensamblada", "Otra"], "section": "details"},
            {"key": "modelo", "label": "Modelo", "type": "text", "required": True, "placeholder": "Ej: MacBook Air M3 / Lenovo IdeaPad Slim 3 / HP Victus", "section": "details"},
            {"key": "procesador", "label": "Procesador", "type": "text", "required": False, "placeholder": "Ej: Intel Core i5-1335U / Ryzen 7 5700U / Apple M3", "section": "specs"},
            {"key": "ram", "label": "Memoria RAM", "type": "select", "required": False, "options": ["4 GB", "8 GB", "12 GB", "16 GB", "24 GB", "32 GB", "64 GB"], "section": "specs"},
            {"key": "almacenamiento", "label": "Disco Principal", "type": "select", "required": False, "options": ["128 GB SSD", "256 GB SSD", "512 GB SSD NVMe", "1 TB SSD NVMe", "2 TB SSD", "1 TB HDD"], "section": "specs"},
            {"key": "pantalla", "label": "Pantalla", "type": "text", "required": False, "placeholder": "Ej: 15.6\" Full HD IPS / 14\" / 13.6\" Retina", "section": "specs"},
            {"key": "tarjeta_grafica", "label": "Gráficos (GPU)", "type": "text", "required": False, "placeholder": "Ej: Integrados Intel Iris Xe / NVIDIA RTX 4050 6GB", "section": "specs"},
            {"key": "condicion", "label": "Condición", "type": "select", "required": True, "options": ["Nuevo (Sellado)", "Open Box", "Reacondicionado / Refurbished", "Usado"], "section": "condition"},
            _warranty_field("Ej: 6 meses o 1 año"),
        ],
    ),
    "Componentes de PC y Hardware": _build_schema(
        archetype="mobile_and_computing",
        ui_hint="Tarjetas madre, procesadores, tarjetas de video (GPU), fuentes de poder, cases/chasis, coolers y pasta térmica.",
        buyer_ui_hint="Verifica el socket, generación o potencia compatible con tu PC.",
        allowed_units=["unit", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Capacidad / Versión / Socket",
            "axes": [
                {"key": "spec", "label": "Versión / Capacidad", "type": "text", "presets": ["AM4", "AM5", "LGA1700", "600W 80+ Bronze", "750W 80+ Gold", "8GB GDDR6", "12GB GDDR6"]},
            ],
        },
        combo_item_placeholder="Ej: Procesador Ryzen 5 + Tarjeta Madre B550 + 16GB RAM DDR4...",
        fields=[
            {"key": "tipo_componente", "label": "Tipo de Componente", "type": "select", "required": False, "options": ["Procesador (CPU)", "Tarjeta Madre (Motherboard)", "Tarjeta de Video (GPU)", "Fuente de Poder (PSU)", "Case / Chasis Gamer", "Cooler / Refrigeración Líquida", "Pasta Térmica / Ventilador", "Combo Actualización (Board + CPU + RAM)"], "section": "details"},
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: ASUS, MSI, Gigabyte, AMD, Intel, Corsair, EVGA, Redragon", "section": "details"},
            {"key": "especificacion_tecnica", "label": "Socket / Compatibilidad / Potencia", "type": "text", "required": False, "placeholder": "Ej: Socket AM4 / DDR4 / 650W 80 Plus", "section": "specs"},
            {"key": "condicion", "label": "Condición", "type": "select", "required": False, "options": ["Nuevo (Sellado)", "Open Box", "Usado"], "section": "condition"},
            _warranty_field("Ej: 3 meses, 6 meses o 1 año"),
        ],
    ),
    "Almacenamiento y Memorias": _build_schema(
        archetype="mobile_and_computing",
        ui_hint="Discos sólidos SSD (NVMe M.2 y SATA), discos duros externos, pendrives USB, tarjetas MicroSD y memorias RAM (DDR3, DDR4, DDR5 para PC o Laptop).",
        buyer_ui_hint="Selecciona la capacidad (GB/TB) y el formato compatible.",
        allowed_units=["unit", "pack", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Capacidad y Formato",
            "axes": [
                {"key": "capacity", "label": "Capacidad", "type": "select", "presets": ["8 GB", "16 GB", "32 GB", "64 GB", "128 GB", "240 GB", "256 GB", "480 GB", "512 GB", "1 TB", "2 TB", "4 TB"]},
                {"key": "format", "label": "Formato / Interfaz", "type": "select", "presets": ["M.2 NVMe PCIe", "SSD SATA 2.5\"", "DDR4 3200MHz", "DDR5", "SO-DIMM (Laptop)", "USB 3.2", "MicroSD Clase 10"]},
            ],
        },
        fields=[
            {"key": "tipo_memoria", "label": "Tipo de Dispositivo", "type": "select", "required": False, "options": ["Disco Sólido SSD M.2 NVMe", "Disco Sólido SSD 2.5\" SATA", "Disco Duro Externo Portátil", "Memoria RAM para PC (DIMM)", "Memoria RAM para Laptop (SO-DIMM)", "Pendrive / Memoria USB", "Tarjeta MicroSD / SD"], "section": "details"},
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Kingston, SanDisk, Crucial, Western Digital, Samsung, ADATA, Corsair", "section": "details"},
            {"key": "capacidad", "label": "Capacidad", "type": "text", "required": False, "placeholder": "Ej: 512 GB / 16 GB DDR4", "section": "specs"},
            _warranty_field("Ej: 3 meses, 6 meses o 1 año"),
        ],
    ),
    "Monitores y Televisores": _build_schema(
        archetype="electronics_and_gaming",
        ui_hint="Televisores Smart TV y monitores para PC o gaming. Indica pulgadas, resolución (FHD, 2K, 4K), hercios (Hz) y sistema operativo.",
        buyer_ui_hint="Selecciona el tamaño en pulgadas y revisa la resolución.",
        allowed_units=["unit", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tamaño en Pulgadas / Versión",
            "axes": [
                {"key": "size", "label": "Pulgadas", "type": "select", "presets": ["22\"", "24\"", "27\"", "32\"", "40\"", "43\"", "50\"", "55\"", "65\"", "75\"", "85\""]},
                {"key": "refresh_or_res", "label": "Resolución / Tasa", "type": "select", "presets": ["HD", "Full HD 1080p", "4K UHD", "75 Hz", "100 Hz", "144 Hz", "165 Hz", "240 Hz"]},
            ],
        },
        combo_item_placeholder="Ej: 1 Smart TV + 1 Base de Pared + 1 Protector de Voltaje...",
        fields=[
            {"key": "tipo_pantalla", "label": "Tipo de Equipo", "type": "select", "required": False, "options": ["Smart TV / Televisor", "Monitor de Oficina / Diseño", "Monitor Gamer (Alta tasa Hz)", "TV Box / Fire TV / Chromecast"], "section": "details"},
            {"key": "marca", "label": "Marca", "type": "text", "required": True, "placeholder": "Ej: Samsung, LG, Xiaomi, Hisense, Aiwa, Daewoo, ASUS, AOC, MSI", "section": "details"},
            {"key": "tamano_pulgadas", "label": "Pulgadas", "type": "text", "required": False, "placeholder": "Ej: 55 pulgadas / 27 pulgadas", "section": "specs"},
            {"key": "resolucion", "label": "Resolución / Panel", "type": "select", "required": False, "options": ["HD (720p)", "Full HD (1080p)", "2K QHD", "4K UHD", "QLED", "OLED", "IPS"], "section": "specs"},
            {"key": "sistema_operativo", "label": "Sistema Smart (si es TV)", "type": "select", "required": False, "options": ["No aplica (Monitor)", "Google TV / Android TV", "WebOS (LG)", "Tizen (Samsung)", "Roku TV", "Fire TV", "Vidaa"], "section": "specs"},
            {"key": "condicion", "label": "Condición", "type": "select", "required": True, "options": ["Nuevo (Sellado)", "Open Box", "Usado"], "section": "condition"},
            _warranty_field("Ej: 6 meses o 1 año"),
        ],
    ),
    "Impresoras y Escaners": _build_schema(
        archetype="mobile_and_computing",
        ui_hint="Impresoras multifuncionales EcoTank, láser, impresoras térmicas de recibos, escáneres, botellas de tinta, cartuchos y tóners.",
        buyer_ui_hint="Verifica el modelo de impresora o color de tinta compatible.",
        allowed_units=["unit", "set", "pack", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Color de Tinta / Modelo",
            "axes": [
                {"key": "color_or_model", "label": "Color / Versión", "type": "select", "presets": ["Equipo Completo", "Kit 4 Tintas (CMYK)", "Negro (BK)", "Cian (C)", "Magenta (M)", "Amarillo (Y)"]},
            ],
        },
        combo_item_placeholder="Ej: 1 Impresora Epson EcoTank + 4 Botellas de Tinta + 1 Resma de Papel...",
        fields=[
            {"key": "tipo_producto", "label": "Tipo de Producto", "type": "select", "required": False, "options": ["Impresora Multifuncional Sistema Continuo", "Impresora Láser", "Impresora Térmica / POS", "Escáner", "Botella de Tinta Original / Genérica", "Cartucho de Tinta", "Tóner Láser"], "section": "details"},
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Epson, HP, Canon, Brother, Zebra, 3nStar", "section": "details"},
            {"key": "modelo_compatible", "label": "Modelo / Código de Tinta o Tóner", "type": "text", "required": False, "placeholder": "Ej: Epson L3250 / T544 / Tóner 85A", "section": "specs"},
            {"key": "conectividad", "label": "Conectividad", "type": "select", "required": False, "options": ["Wi-Fi + USB", "Solo USB", "USB + Red Ethernet / Bluetooth", "No aplica (Consumible)"], "section": "specs"},
            _warranty_field(),
        ],
    ),
    "Smartwatches y Wearables": _build_schema(
        archetype="electronics_and_gaming",
        ui_hint="Smartwatches, Apple Watch, bandas inteligentes, correas para reloj inteligente y audífonos inalámbricos.",
        buyer_ui_hint="Selecciona el tamaño de caja (mm) y el color de correa.",
        allowed_units=["unit", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tamaño de Caja y Color",
            "axes": [
                {"key": "case_size", "label": "Tamaño de Caja", "type": "select", "presets": ["40 mm", "41 mm", "42 mm", "44 mm", "45 mm", "46 mm", "49 mm Ultra", "Único"]},
                {"key": "color", "label": "Color / Correa", "type": "text", "presets": ["Negro", "Plata", "Blanco Estelar", "Rosa", "Naranja", "Azul"]},
            ],
        },
        combo_item_placeholder="Ej: 1 Smartwatch + 1 Audífonos Inalámbricos + 2 Correas...",
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": True, "placeholder": "Ej: Apple, Samsung, Xiaomi, Huawei, Garmin, Amazfit, Haylou, Genérico", "section": "details"},
            {"key": "modelo", "label": "Modelo", "type": "text", "required": True, "placeholder": "Ej: Apple Watch Series 9 / Xiaomi Smart Band 8 / Watch Ultra", "section": "details"},
            {"key": "compatibilidad", "label": "Compatibilidad", "type": "select", "required": False, "options": ["iOS (iPhone) y Android", "Solo iOS (iPhone)", "Solo Android"], "section": "specs"},
            {"key": "condicion", "label": "Condición", "type": "select", "required": True, "options": ["Nuevo", "Open Box", "Usado"], "section": "condition"},
            _warranty_field("Ej: 30 días, 3 meses o 1 año"),
        ],
    ),
    "Cámaras y Fotografía": _build_schema(
        archetype="electronics_and_gaming",
        ui_hint="Cámaras profesionales Mirrorless/DSLR, drones DJI, cámaras de acción GoPro, lentes, aros de luz LED, trípodes, gimbals e iluminación.",
        buyer_ui_hint="Revisa el kit o accesorios incluidos.",
        allowed_units=["unit", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Kit / Paquete",
            "axes": [
                {"key": "kit", "label": "Versión / Kit", "type": "text", "presets": ["Solo Cuerpo (Body)", "Con Lente 18-55mm / 16-50mm", "Fly More Combo", "Kit Creador"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": True, "placeholder": "Ej: Sony, Canon, Nikon, DJI, GoPro, Insta360, Godox, Ulanzi", "section": "details"},
            {"key": "modelo", "label": "Modelo", "type": "text", "required": True, "placeholder": "Ej: Sony ZV-E10 / DJI Mini 4 Pro / GoPro Hero 12", "section": "details"},
            {"key": "resolucion", "label": "Resolución / Especificación", "type": "text", "required": False, "placeholder": "Ej: 24.2 MP / Video 4K 60fps", "section": "specs"},
            {"key": "condicion", "label": "Condición", "type": "select", "required": True, "options": ["Nuevo", "Open Box", "Usado"], "section": "condition"},
            _warranty_field("Ej: 6 meses o 1 año"),
        ],
    ),
    "Teclados y Mouse": _build_schema(
        archetype="electronics_and_gaming",
        ui_hint="Teclados mecánicos o de membrana, mouse gamer/oficina, combos teclado+mouse, mousepads XL, webcams, audífonos USB y hubs.",
        buyer_ui_hint="Elige el color, idioma del teclado o tipo de conexión (inalámbrico o cableado).",
        allowed_units=["unit", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Color / Switch / Conexión",
            "axes": [
                {"key": "color", "label": "Color", "type": "text", "presets": ["Negro", "Blanco", "Rosa", "Gris", "RGB"]},
                {"key": "switch_or_conn", "label": "Conexión / Switch", "type": "select", "presets": ["Inalámbrico Bluetooth + 2.4GHz", "USB Cableado", "Switch Rojo (Lineal)", "Switch Azul (Clicky)", "Switch Marrón (Táctil)", "Membrana Silencioso"]},
            ],
        },
        combo_item_placeholder="Ej: 1 Teclado Gamer RGB + 1 Mouse + 1 Audífonos + 1 Mousepad...",
        fields=[
            {"key": "tipo_periferico", "label": "Tipo de Periférico", "type": "select", "required": False, "options": ["Teclado Mecánico", "Teclado de Oficina / Membrana", "Mouse Inalámbrico / Gamer", "Combo Teclado + Mouse", "Audífonos / Headset", "Mousepad / Alfombrilla", "Webcam / Micrófono USB"], "section": "details"},
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Logitech, Redragon, Razer, HyperX, Corsair, Genius, Jedel", "section": "details"},
            {"key": "conectividad", "label": "Conectividad", "type": "select", "required": False, "options": ["Inalámbrico 2.4GHz + Bluetooth", "Inalámbrico USB (Receptor)", "Bluetooth", "Cableado USB"], "section": "specs"},
            {"key": "idioma_distribucion", "label": "Distribución (si es teclado)", "type": "select", "required": False, "options": ["Español (Con letra Ñ)", "Inglés US", "60% / 65% Compacto", "75% / TKL", "100% Completo con Numérico", "No aplica"], "section": "specs"},
            _warranty_field("Ej: 30 días, 3 meses o 6 meses"),
        ],
    ),
    "Redes, Routers y Conectividad": _build_schema(
        archetype="mobile_and_computing",
        ui_hint="Routers Wi-Fi 6 / Dual Band, ONUs de fibra óptica, sistemas Mesh, repetidores, switches Gigabit, antenas Ubiquiti/MikroTik y cable UTP Cat5e/Cat6.",
        buyer_ui_hint="Verifica la velocidad (Mbps), bandas (Dual Band / Wi-Fi 6) o cantidad de metros de cable.",
        allowed_units=["unit", "m", "box", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Versión / Velocidad / Metros",
            "axes": [
                {"key": "version", "label": "Modelo / Medida", "type": "text", "presets": ["AC1200 Dual Band", "AX1500 Wi-Fi 6", "AX3000 Wi-Fi 6", "Pack x2 Mesh", "Pack x3 Mesh", "Por Metro", "Bobina 305m"]},
            ],
        },
        combo_item_placeholder="Ej: 1 Router Wi-Fi 6 + 1 Mini UPS de Respaldo para Fibra...",
        combo_templates=[
            {
                "name": "Combo Internet sin Cortes (Router Wi-Fi + Mini UPS)",
                "description": "Router de alta velocidad + Mini UPS para mantener el internet encendido durante apagones.",
                "combo_items": [
                    {"name": "Router Dual Band / Wi-Fi 6", "quantity": 1, "unit": "und", "notes": ""},
                    {"name": "Mini UPS 10400mAh para Router y ONU Fibra", "quantity": 1, "unit": "und", "notes": "Cable doble DC incluido"},
                ],
            },
        ],
        fields=[
            {"key": "tipo_equipo_red", "label": "Tipo de Equipo", "type": "select", "required": False, "options": ["Router Wi-Fi Dual Band / Wi-Fi 6", "Sistema Wi-Fi Mesh", "Repetidor / Extensor de Rango", "ONU / Modem Fibra Óptica", "Switch de Red", "Adaptador Wi-Fi USB / PCIe", "Antena / Radioenlace", "Cable de Red UTP / Conectores RJ45"], "section": "details"},
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: TP-Link, Mercusys, Huawei, MikroTik, Ubiquiti, Tenda, Cudy", "section": "details"},
            {"key": "puertos_velocidad", "label": "Velocidad / Puertos", "type": "text", "required": False, "placeholder": "Ej: Gigabit (1000 Mbps) / Wi-Fi 6 AX1800", "section": "specs"},
            _warranty_field("Ej: 3 meses, 6 meses o 1 año"),
        ],
    ),
    "Consolas y Videojuegos": _build_schema(
        archetype="electronics_and_gaming",
        ui_hint="Consolas PlayStation 5, Nintendo Switch, Xbox Series X/S, videojuegos físicos, controles DualSense/Joy-Con y accesorios gamer.",
        buyer_ui_hint="Elige la plataforma, edición o color del control/consola.",
        allowed_units=["unit", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Plataforma / Edición / Color",
            "axes": [
                {"key": "platform", "label": "Plataforma", "type": "select", "presets": ["PlayStation 5", "PlayStation 4", "Nintendo Switch", "Xbox Series X/S", "PC"]},
                {"key": "edition", "label": "Edición / Color", "type": "text", "presets": ["Edición con Lector de Disco", "Edición Digital", "Switch OLED", "Switch Lite", "Blanco", "Negro Medianoche", "Rojo Cósmico", "Azul"]},
            ],
        },
        combo_item_placeholder="Ej: 1 Consola PS5 + 2 Controles DualSense + 1 Juego Físico...",
        combo_templates=[
            {
                "name": "Combo Consola + 2 Controles + Juego",
                "description": "Consola completa lista para jugar en familia.",
                "combo_items": [
                    {"name": "Consola de Videojuegos", "quantity": 1, "unit": "und", "notes": "1TB"},
                    {"name": "Control Inalámbrico Original", "quantity": 2, "unit": "und", "notes": ""},
                    {"name": "Videojuego Físico", "quantity": 1, "unit": "und", "notes": ""},
                ],
            },
        ],
        fields=[
            {"key": "plataforma", "label": "Plataforma", "type": "select", "required": True, "options": ["PlayStation 5 (PS5)", "PlayStation 4 (PS4)", "Nintendo Switch", "Xbox Series X / S", "PC Gaming / Steam Deck", "Consola Retro / Portátil"], "section": "details"},
            {"key": "tipo_producto", "label": "Tipo de Producto", "type": "select", "required": False, "options": ["Consola", "Videojuego Físico", "Control / Mando", "Estación de Carga / Accesorios", "Combo Gamer"], "section": "details"},
            {"key": "almacenamiento", "label": "Capacidad (si es consola)", "type": "text", "required": False, "placeholder": "Ej: 1 TB SSD Slim / 64 GB OLED", "section": "specs"},
            {"key": "condicion", "label": "Condición", "type": "select", "required": True, "options": ["Nuevo (Sellado)", "Usado - Como Nuevo", "Usado"], "section": "condition"},
            _warranty_field("Ej: 3 meses, 6 meses o 1 año"),
        ],
    ),
    "Cargadores, Cables y Powerbanks": _build_schema(
        archetype="electronics_and_gaming",
        ui_hint="Tacos de carga rápida (20W, 25W, 33W, 45W, 65W), cables USB-C / Lightning / Micro-USB, baterías portátiles Powerbank (10.000mAh / 20.000mAh), forros y audífonos.",
        buyer_ui_hint="Selecciona el tipo de conector (USB-C, Lightning iPhone, Micro-USB), potencia o color.",
        allowed_units=["unit", "pack", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Conector, Potencia y Color",
            "axes": [
                {"key": "connector", "label": "Conector / Capacidad", "type": "select", "presets": ["USB-C a USB-C", "USB-C a Lightning (iPhone)", "USB-A a Tipo C", "Micro-USB", "20W / 25W", "45W / 65W", "10.000 mAh", "20.000 mAh", "30.000 mAh"]},
                {"key": "color", "label": "Color", "type": "text", "presets": ["Blanco", "Negro", "Transparente", "Azul", "Morado"]},
            ],
        },
        combo_item_placeholder="Ej: 1 Taco Carga Rápida 20W + 1 Cable USB-C a Lightning 1m...",
        fields=[
            {"key": "tipo_accesorio", "label": "Tipo de Accesorio", "type": "select", "required": False, "options": ["Cargador de Pared (Taco)", "Cable de Carga y Datos", "Combo Cargador + Cable", "Powerbank / Batería Portátil", "Cargador Inalámbrico / MagSafe", "Cargador para Carro", "Audífonos / Forros y Vidrios"], "section": "details"},
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Apple, Samsung, Anker, Baseus, Ugreen, Xiaomi, Hora, 1Hora", "section": "details"},
            {"key": "potencia_capacidad", "label": "Potencia (W) / Capacidad (mAh)", "type": "text", "required": False, "placeholder": "Ej: 20W PD / 25W Super Fast / 20.000 mAh", "section": "specs"},
            _warranty_field("Ej: 15 días, 30 días o 3 meses"),
        ],
    ),
    "Reguladores, Protectores y UPS": _build_schema(
        archetype="electronics_and_gaming",
        ui_hint="Indispensables en Venezuela: protectores de voltaje para neveras, aires acondicionados y TV, reguladores AVR, UPS de computadora, Mini UPS para router/fibra óptica y regletas.",
        buyer_ui_hint="Verifica el voltaje (110V o 220V), capacidad (VA/Watts) o el equipo que deseas proteger.",
        allowed_units=["unit", "pack", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Aplicación / Capacidad / Voltaje",
            "axes": [
                {"key": "application", "label": "Uso / Capacidad", "type": "select", "presets": ["Nevera / TV (110V)", "Aire Acondicionado 110V", "Aire Acondicionado 220V", "Mini UPS Fibra 8800mAh / 10400mAh", "UPS 600VA / 750VA", "UPS 1000VA / 1500VA", "Regulador 1200VA / 2000VA"]},
            ],
        },
        combo_item_placeholder="Ej: 2 Protectores de Nevera/TV + 1 Protector de Aire 220V + 1 Mini UPS Router...",
        combo_templates=[
            {
                "name": "Combo Protección Hogar (Nevera + TV + Aire)",
                "description": "Kit de protectores de voltaje para los equipos principales de la casa.",
                "combo_items": [
                    {"name": "Protector de Voltaje para Nevera (110V)", "quantity": 1, "unit": "und", "notes": ""},
                    {"name": "Protector de Voltaje para TV / Electrónicos", "quantity": 1, "unit": "und", "notes": ""},
                    {"name": "Protector de Voltaje para Aire Acondicionado", "quantity": 1, "unit": "und", "notes": "110V o 220V a elección"},
                ],
            },
        ],
        fields=[
            {"key": "tipo_proteccion", "label": "Tipo de Equipo", "type": "select", "required": False, "options": ["Protector de Voltaje (Enchufe)", "Protector Supervisor Trifásico / Riel", "Mini UPS para Router y Fibra Óptica", "UPS con Batería de Respaldo", "Regulador de Voltaje Automático (AVR)", "Regleta / Supresor de Picos", "Batería de Reemplazo para UPS (12V 7Ah/9Ah)"], "section": "details"},
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Exceline, Forza, APC, CDP, Avtek, Tripp Lite, Marsriva, Shanqiu", "section": "details"},
            {"key": "voltaje", "label": "Voltaje de Operación", "type": "select", "required": False, "options": ["110V / 120V", "220V", "Salidas 5V / 9V / 12V + PoE (Mini UPS)"], "section": "specs"},
            {"key": "capacidad_va_w", "label": "Capacidad (VA / Watts / mAh)", "type": "text", "required": False, "placeholder": "Ej: 1000VA / 500W / 10.400 mAh", "section": "specs"},
            _warranty_field("Ej: 6 meses, 1 año o 3 años"),
        ],
    ),
    "Smart Home y Domótica": _build_schema(
        archetype="electronics_and_gaming",
        ui_hint="Cornetas inteligentes Alexa Echo Dot, bombillos inteligentes RGB Wi-Fi, enchufes e interruptores inteligentes Sonoff/Tuya y cerraduras digitales.",
        buyer_ui_hint="Verifica la compatibilidad con Alexa, Google Home o Apple HomeKit.",
        allowed_units=["unit", "pack", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Color / Generación / Cantidad",
            "axes": [
                {"key": "variant", "label": "Versión / Color", "type": "text", "presets": ["Negro / Carbón", "Blanco / Glaciar", "Azul", "1 Canal", "2 Canales", "3 Canales", "Pack x2", "Pack x4"]},
            ],
        },
        combo_item_placeholder="Ej: 1 Alexa Echo Dot + 2 Bombillos Inteligentes RGB + 1 Enchufe Smart...",
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Amazon Alexa, Google, Sonoff, Tuya Smart, Broadlink, TP-Link Tapo, Xiaomi", "section": "details"},
            {"key": "ecosistema", "label": "Asistente / App Compatible", "type": "select", "required": False, "options": ["Amazon Alexa y Google Home (Smart Life / Tuya)", "eWeLink (Sonoff)", "Amazon Alexa", "Apple HomeKit", "Xiaomi Home"], "section": "specs"},
            _warranty_field("Ej: 3 meses o 6 meses"),
        ],
    ),
    "Seguridad y Cámaras de Vigilancia": _build_schema(
        archetype="hardware_and_construction",
        ui_hint="Cámaras Wi-Fi 360° PTZ exterior/interior, cámaras doble lente, cámaras solares 4G, kits DVR/NVR CCTV, discos duros de videovigilancia y video porteros.",
        buyer_ui_hint="Elige la resolución de la cámara y si deseas incluir tarjeta MicroSD de grabación.",
        allowed_units=["unit", "set", "pack", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Resolución y Almacenamiento",
            "axes": [
                {"key": "resolution", "label": "Resolución / Lentes", "type": "select", "presets": ["Full HD 1080p (2MP)", "2K (3MP / 4MP)", "Doble Lente (Dual)", "Triple Lente", "Kit 4 Cámaras + DVR", "Kit 8 Cámaras + DVR"]},
                {"key": "memory", "label": "Memoria MicroSD", "type": "select", "presets": ["Sin Memoria", "Con MicroSD 32GB", "Con MicroSD 64GB", "Con MicroSD 128GB"]},
            ],
        },
        combo_item_placeholder="Ej: 2 Cámaras Wi-Fi Exterior 360° + 2 Memorias MicroSD 64GB...",
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Ezviz, Imou, Hikvision, Dahua, TP-Link Tapo, ICSEE / V380", "section": "details"},
            {"key": "ubicacion_uso", "label": "Uso", "type": "select", "required": False, "options": ["Exterior Impermeable (IP66)", "Interior", "Interior y Exterior", "Solar con Chip 4G"], "section": "specs"},
            {"key": "conectividad_app", "label": "App / Conexión", "type": "text", "required": False, "placeholder": "Ej: Wi-Fi 2.4GHz / App Ezviz, Imou Life, iCSee", "section": "specs"},
            _warranty_field("Ej: 3 meses, 6 meses o 1 año"),
        ],
    ),
    "Proyectores y Video Beam": _build_schema(
        archetype="electronics_and_gaming",
        ui_hint="Proyectores portátiles Smart (tipo HY300/HY320), Video Beams empresariales/educativos Epson/BenQ y pantallas de proyección.",
        buyer_ui_hint="Revisa los lúmenes, resolución nativa y conexiones (HDMI, Wi-Fi, Bluetooth).",
        allowed_units=["unit", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Modelo / Versión",
            "axes": [
                {"key": "model", "label": "Versión", "type": "text", "presets": ["HD 720p Nativo", "Full HD 1080p Nativo", "Con Pantalla de Proyección"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Epson, BenQ, Magcubic, Wanbo, Samsung, ViewSonic", "section": "details"},
            {"key": "resolucion_lumenes", "label": "Resolución y Brillo (Lúmenes)", "type": "text", "required": False, "placeholder": "Ej: 1080p Full HD (Soporta 4K) / 350 ANSI Lúmenes", "section": "specs"},
            {"key": "sistema_integrado", "label": "Sistema / Conectividad", "type": "select", "required": False, "options": ["Android TV Integrado (Wi-Fi + Bluetooth + HDMI)", "HDMI + VGA + USB", "Inalámbrico Mirroring"], "section": "specs"},
            _warranty_field("Ej: 3 meses, 6 meses o 1 año"),
        ],
    ),

    # Alias legacy de Tecnología y Electrónica
    "Celulares y Tablets": _build_schema(
        archetype="mobile_and_computing",
        ui_hint="Teléfonos inteligentes y tablets. Especifica marca, modelo, almacenamiento, RAM y garantía.",
        buyer_ui_hint="Selecciona el color y capacidad de almacenamiento.",
        allowed_units=["unit", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Color y Almacenamiento",
            "axes": [
                {"key": "storage", "label": "Almacenamiento", "type": "select", "presets": ["64 GB", "128 GB", "256 GB", "512 GB", "1 TB"]},
                {"key": "color", "label": "Color", "type": "text", "presets": ["Negro", "Blanco", "Plata", "Titanio Natural", "Azul"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": True, "placeholder": "Ej: Apple, Samsung, Xiaomi", "section": "details"},
            {"key": "modelo", "label": "Modelo", "type": "text", "required": True, "placeholder": "Ej: iPhone 15 Pro", "section": "details"},
            _warranty_field(),
        ],
    ),
    "Computación": _build_schema(
        archetype="mobile_and_computing",
        ui_hint="Laptops, computadoras, componentes y almacenamiento.",
        buyer_ui_hint="Revisa las especificaciones técnicas y elige la configuración.",
        allowed_units=["unit", "combo"],
        default_unit="unit",
        supports_variants=True,
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": True, "placeholder": "Ej: HP, Lenovo, Apple, Dell", "section": "details"},
            _warranty_field(),
        ],
    ),
    "Periféricos y Accesorios": _build_schema(
        archetype="electronics_and_gaming",
        ui_hint="Audífonos, cargadores, cables, teclados, mouse y reguladores.",
        buyer_ui_hint="Selecciona el color o conector compatible.",
        allowed_units=["unit", "pack", "combo"],
        default_unit="unit",
        supports_variants=True,
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Logitech, Anker, Redragon", "section": "details"},
            _warranty_field(),
        ],
    ),
    "TV, Audio y Video": _build_schema(
        archetype="electronics_and_gaming",
        ui_hint="Televisores Smart TV, cornetas, barras de sonido y proyectores.",
        buyer_ui_hint="Verifica las pulgadas y especificaciones.",
        allowed_units=["unit", "combo"],
        default_unit="unit",
        supports_variants=True,
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": True, "placeholder": "Ej: Samsung, LG, JBL", "section": "details"},
            _warranty_field(),
        ],
    ),
    "Videojuegos y Consolas": _build_schema(
        archetype="electronics_and_gaming",
        ui_hint="Consolas, videojuegos y controles.",
        buyer_ui_hint="Elige la plataforma o edición.",
        allowed_units=["unit", "combo"],
        default_unit="unit",
        supports_variants=True,
        fields=[
            {"key": "plataforma", "label": "Plataforma", "type": "text", "required": True, "placeholder": "Ej: PS5, Nintendo Switch, Xbox", "section": "details"},
            _warranty_field(),
        ],
    ),
    "Wearables": _build_schema(
        archetype="electronics_and_gaming",
        ui_hint="Smartwatches y bandas inteligentes.",
        buyer_ui_hint="Selecciona el color y tamaño.",
        allowed_units=["unit", "combo"],
        default_unit="unit",
        supports_variants=True,
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": True, "placeholder": "Ej: Apple, Samsung, Xiaomi", "section": "details"},
            _warranty_field(),
        ],
    ),

    # --------------------------------------------------------------------------
    # 3. ROPA Y ACCESORIOS (19 SUBCATEGORÍAS OFICIALES CON TALLAS DE VENEZUELA)
    # --------------------------------------------------------------------------
    "Blusas, Tops y Franelas de Dama": _build_schema(
        archetype="apparel_fashion",
        ui_hint="Agrega las tallas de ropa de dama usadas en Venezuela (XS, S, M, L, XL, XXL, XXXL o Talla Única) y los colores disponibles.",
        buyer_ui_hint="Selecciona tu talla (XS, S, M, L, XL...) y color antes de agregar al carrito.",
        allowed_units=["unit", "set", "pack", "dozen", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tallas de Ropa (Letras) y Colores",
            "helper_text": "Selecciona las tallas (XS, S, M, L, XL, XXL, XXXL, Talla Única) y los colores disponibles.",
            "axes": [
                {"key": "size", "label": "Talla", "type": "select", "presets": VE_CLOTHING_LETTER_SIZES},
                {"key": "color", "label": "Color", "type": "text", "presets": VE_COMMON_COLORS},
            ],
        },
        combo_item_placeholder="Ej: 3 Blusas Básicas de Algodón (Blanca, Negra y Beige)...",
        combo_templates=[
            {
                "name": "Combo 3 Blusas / Franelas Básicas",
                "description": "Promoción de 3 blusas o tops (puedes elegir tallas y colores).",
                "combo_items": [
                    {"name": "Blusa / Top / Franela de Dama", "quantity": 3, "unit": "und", "notes": "Colores a elección"},
                ],
            },
        ],
        fields=[
            {"key": "tipo_prenda", "label": "Tipo de Prenda", "type": "select", "required": False, "options": ["Blusa Casual / Elegante", "Crop Top / Top", "Body", "Franela / T-Shirt", "Camisa Manga Larga / Corta", "Suéter / Cardigan / Chaqueta"], "section": "details"},
            {"key": "marca", "label": "Marca / Confección", "type": "text", "required": False, "placeholder": "Ej: Zara, Shein, Stradivarius, Confección Nacional", "section": "details"},
            {"key": "tela_material", "label": "Tela", "type": "text", "required": False, "placeholder": "Ej: Algodón, Microdurazno, Rib Acanalado, Lino, Satén, Bebé", "section": "specs"},
            {"key": "condicion", "label": "Condición", "type": "select", "required": False, "options": ["Nuevo con etiqueta", "Nuevo", "Second Hand / Pre-loved"], "section": "condition"},
        ],
    ),
    "Vestidos, Faldas y Enterizos": _build_schema(
        archetype="apparel_fashion",
        ui_hint="Vestidos cortos, midi, largos de fiesta, bragas/enterizos, faldas y conjuntos de dama. Configura las tallas (XS, S, M, L, XL, XXL, Talla Única) y colores.",
        buyer_ui_hint="Selecciona tu talla y color disponible.",
        allowed_units=["unit", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tallas (XS a XXXL) y Colores",
            "axes": [
                {"key": "size", "label": "Talla", "type": "select", "presets": VE_CLOTHING_LETTER_SIZES},
                {"key": "color", "label": "Color / Estampado", "type": "text", "presets": VE_COMMON_COLORS},
            ],
        },
        fields=[
            {"key": "tipo_prenda", "label": "Tipo de Prenda", "type": "select", "required": False, "options": ["Vestido Corto / Casual", "Vestido Midi", "Vestido Largo / Fiesta / Gala", "Enterizo / Braga", "Falda / Falda-Short (Skort)", "Conjunto de 2 Piezas"], "section": "details"},
            {"key": "tela_material", "label": "Tela", "type": "text", "required": False, "placeholder": "Ej: Lino, Seda, Licra Colombiana, Chiffon, Denim", "section": "specs"},
            {"key": "ocasion", "label": "Ocasión", "type": "select", "required": False, "options": ["Casual / Diario", "Fiesta / Noche / Cóctel", "Playa / Verano", "Ejecutivo / Oficina", "Gala / Graduación / Boda"], "section": "details"},
        ],
    ),
    "Pantalones, Jeans y Leggings de Dama": _build_schema(
        archetype="apparel_fashion",
        ui_hint="Jeans levanta cola, mom jeans, wide leg, pantalones de vestir, palazzos, shorts y leggings. Incluye tanto la numeración de dama en Venezuela (4 al 18 y 24 al 38) como tallas en letras (XS a XXL).",
        buyer_ui_hint="Selecciona tu talla de pantalón (ej. 6, 8, 10, 12 o 26, 28, 30, 32 o S, M, L) y el color o tono.",
        allowed_units=["unit", "pack", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tallas de Pantalón / Jean de Dama y Colores",
            "helper_text": "Usa numeración nacional/colombiana (6, 8, 10, 12, 14, 16), cintura (26, 28, 30, 32, 34, 36) o letras (XS, S, M, L, XL).",
            "axes": [
                {"key": "size", "label": "Talla de Dama", "type": "select", "presets": VE_WOMEN_PANTS_SIZES},
                {"key": "color", "label": "Color / Tono Denim", "type": "text", "presets": ["Azul Oscuro", "Azul Medio", "Azul Claro / Celeste", "Negro", "Blanco", "Beige", "Gris", "Verde Oliva", "Marrón"]},
            ],
        },
        fields=[
            {"key": "corte_pantalon", "label": "Corte / Estilo", "type": "select", "required": False, "options": ["Jean Levanta Cola / Horma Colombiana", "Wide Leg / Bota Ancha", "Mom Jean / Boyfriend", "Skinny / Tubito", "Pantalón de Vestir / Palazzo", "Pantalón Cargo", "Short / Bermuda", "Legging / Licra"], "section": "details"},
            {"key": "tiro", "label": "Tiro", "type": "select", "required": False, "options": ["Tiro Alto (Corte Alto)", "Tiro Medio", "Tiro Bajo"], "section": "specs"},
            {"key": "tela_stretch", "label": "Tela / Elasticidad", "type": "select", "required": False, "options": ["Denim Con Stretch (Elástico)", "Denim Rígido (Sin Stretch)", "Dril / Gabardina", "Tela de Vestir / Lino", "Suplex / Algodón Licrado"], "section": "specs"},
        ],
    ),
    "Franelas, Chemises y Camisas de Caballero": _build_schema(
        archetype="apparel_fashion",
        ui_hint="Franelas, chemises/polos, camisas manga larga/corta, guayaberas, suéteres y chaquetas de caballero. Configura tallas (XS, S, M, L, XL, XXL, XXXL) y colores.",
        buyer_ui_hint="Selecciona tu talla (XS, S, M, L, XL, XXL, XXXL) y color.",
        allowed_units=["unit", "pack", "dozen", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tallas de Caballero (Letras) y Colores",
            "axes": [
                {"key": "size", "label": "Talla", "type": "select", "presets": VE_CLOTHING_LETTER_SIZES},
                {"key": "color", "label": "Color", "type": "text", "presets": VE_COMMON_COLORS},
            ],
        },
        combo_item_placeholder="Ej: 3 Franelas Unicolores de Algodón (Negra, Blanca y Azul Marino)...",
        combo_templates=[
            {
                "name": "Combo 3 Franelas / Chemises de Caballero",
                "description": "Pack promocional de 3 franelas o chemises.",
                "combo_items": [
                    {"name": "Franela / Chemise de Caballero", "quantity": 3, "unit": "und", "notes": "Talla y colores a elección"},
                ],
            },
        ],
        fields=[
            {"key": "tipo_prenda", "label": "Tipo de Prenda", "type": "select", "required": False, "options": ["Franela / T-Shirt", "Franela Oversize", "Chemise / Polo", "Camisa Manga Larga", "Camisa Manga Corta / Guayabera", "Suéter / Hoodie / Chaqueta", "Traje / Flux / Blazer"], "section": "details"},
            {"key": "corte_fit", "label": "Corte (Fit)", "type": "select", "required": False, "options": ["Regular Fit (Clásico)", "Slim Fit (Entallado)", "Oversize (Holgado)"], "section": "specs"},
            {"key": "tela_material", "label": "Tela", "type": "text", "required": False, "placeholder": "Ej: Algodón Pima 100%, Piqué Lacoste, Lino, Oxford, Franela", "section": "specs"},
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Tommy Hilfiger, Polo Ralph Lauren, Lacoste, Ovejita, Nacional", "section": "details"},
        ],
    ),
    "Pantalones, Jeans y Bermudas de Caballero": _build_schema(
        archetype="apparel_fashion",
        ui_hint="Jeans, pantalones chinos/gabardina, pantalones cargo, joggers y bermudas de caballero. Incluye las tallas numéricas usadas en Venezuela (28, 30, 32, 34, 36, 38, 40, 42, 44) y letras (S a XXL).",
        buyer_ui_hint="Selecciona tu talla (28, 30, 32, 34, 36, 38, 40, 42, 44 o S, M, L, XL) y color.",
        allowed_units=["unit", "pack", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tallas de Caballero (28 a 44 / S a XXL) y Colores",
            "axes": [
                {"key": "size", "label": "Talla", "type": "select", "presets": VE_MEN_PANTS_SIZES},
                {"key": "color", "label": "Color", "type": "text", "presets": ["Azul Oscuro", "Azul Clásico", "Azul Claro", "Negro", "Gris", "Beige / Caqui", "Verde Militar", "Marrón"]},
            ],
        },
        fields=[
            {"key": "tipo_pantalon", "label": "Tipo de Prenda", "type": "select", "required": False, "options": ["Jean Clásico / Recto", "Jean Slim Fit", "Pantalón Chino / Gabardina / Dril", "Pantalón Cargo", "Jogger / Mono", "Pantalón de Vestir", "Bermuda / Short"], "section": "details"},
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Levi's, Wrangler, Dockers, Zara, Nacional", "section": "details"},
            {"key": "tela_material", "label": "Tela", "type": "text", "required": False, "placeholder": "Ej: Denim Stretch, Denim Rígido, Gabardina, Algodón", "section": "specs"},
        ],
    ),
    "Ropa Deportiva, Monos y Fitness": _build_schema(
        archetype="apparel_fashion",
        ui_hint="Conjuntos deportivos de dama (top + licra/short), monos joggers, franelas dry-fit, licras de compresión y uniformes deportivos. Configura tallas (XS, S, M, L, XL, XXL) y colores.",
        buyer_ui_hint="Selecciona tu talla (XS, S, M, L, XL, XXL) y color.",
        allowed_units=["unit", "set", "pack", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tallas Deportivas y Colores",
            "axes": [
                {"key": "size", "label": "Talla", "type": "select", "presets": VE_CLOTHING_LETTER_SIZES},
                {"key": "color", "label": "Color", "type": "text", "presets": VE_COMMON_COLORS},
            ],
        },
        fields=[
            {"key": "genero", "label": "Para quién", "type": "select", "required": False, "options": ["Dama", "Caballero", "Unisex", "Infantil"], "section": "details"},
            {"key": "tipo_prenda", "label": "Tipo de Prenda", "type": "select", "required": False, "options": ["Conjunto Deportivo (2 o 3 piezas)", "Legging / Licra Larga", "Short / Biker Deportivo", "Top Deportivo", "Franela Dry-Fit / Compresión", "Mono / Jogger", "Chaqueta Deportiva / Rompevientos"], "section": "details"},
            {"key": "tela_material", "label": "Tela", "type": "text", "required": False, "placeholder": "Ej: Suplex Brasileño / Colombiano, Microfibra Dry-Fit, Seamless (Sin costuras)", "section": "specs"},
        ],
    ),
    "Trajes de Baño y Ropa Playera": _build_schema(
        archetype="apparel_fashion",
        ui_hint="Bikinis de 2 piezas, trajes de baño enterizos, trikinis, shorts playeros de caballero, salidas de baño y franelas con protección UV.",
        buyer_ui_hint="Selecciona tu talla (XS, S, M, L, XL, XXL) y el color o estampado.",
        allowed_units=["unit", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tallas y Colores / Estampados",
            "axes": [
                {"key": "size", "label": "Talla", "type": "select", "presets": VE_CLOTHING_LETTER_SIZES},
                {"key": "color", "label": "Color / Estampado", "type": "text", "presets": VE_COMMON_COLORS},
            ],
        },
        fields=[
            {"key": "tipo_traje_bano", "label": "Tipo", "type": "select", "required": False, "options": ["Bikini (2 Piezas)", "Enterizo / Trikini", "Set 3 Piezas (Bikini + Pareo/Salida)", "Short Playero Caballero", "Salida de Baño / Kimono", "Franela UV / Rashguard", "Infantil"], "section": "details"},
            {"key": "incluye_copas", "label": "Incluye Copas Removibles", "type": "boolean", "required": False, "section": "specs"},
        ],
    ),
    "Ropa Íntima, Lencería y Pijamas": _build_schema(
        archetype="apparel_fashion",
        ui_hint="Conjuntos de lencería, sostenes/brassieres (32B a 40D), panties/hilos, bóxers de caballero, pijamas, batas, fajas colombianas y medias/calcetines.",
        buyer_ui_hint="Selecciona tu talla (XS, S, M, L, XL o copa 32B, 34B, 36B, 36C, 38C) y color.",
        allowed_units=["unit", "set", "pack", "dozen", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tallas (Letras / Copa de Sostén) y Colores",
            "axes": [
                {"key": "size", "label": "Talla / Copa", "type": "select", "presets": VE_BRA_SIZES + ["XXL", "XXXL", "Talla Única"]},
                {"key": "color", "label": "Color", "type": "text", "presets": ["Negro", "Blanco", "Beige / Nude", "Rojo", "Vinotinto", "Rosa", "Azul", "Surtido"]},
            ],
        },
        combo_item_placeholder="Ej: Pack de 3 Panties o 3 Bóxers de Algodón, o Docena de Medias...",
        fields=[
            {"key": "tipo_prenda", "label": "Tipo de Prenda", "type": "select", "required": False, "options": ["Conjunto de Lencería", "Sostén / Brassiere / Bralette", "Panty / Hilo / Cachetero", "Bóxer / Interior de Caballero", "Pijama / Dormilona / Bata", "Faja Moldeadora / Postoperatoria", "Medias / Calcetines"], "section": "details"},
            {"key": "tela_material", "label": "Material", "type": "text", "required": False, "placeholder": "Ej: Encaje, Algodón Hipoalergénico, Satén, Microfibra, Powernet", "section": "specs"},
            {"key": "unidades_por_empaque", "label": "Cantidad en el Empaque", "type": "select", "required": False, "options": ["Individual (1 pieza)", "Conjunto (2 piezas)", "Pack x3", "Pack x6 (Media docena)", "Docena (12 piezas)"], "section": "specs"},
        ],
    ),
    "Ropa para Niños y Niñas": _build_schema(
        archetype="apparel_fashion",
        ui_hint="Ropa infantil y juvenil (tallas 2, 4, 6, 8, 10, 12, 14, 16 y 2T a 5T), conjuntos, vestidos, pijamas y uniformes escolares (chemises blancas/azules/beige, monos y pantalones escolares).",
        buyer_ui_hint="Selecciona la talla infantil (2T a 5T o Talla 2 a la 16) y el color.",
        allowed_units=["unit", "set", "pack", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tallas Infantiles / Escolares y Colores",
            "axes": [
                {"key": "size", "label": "Talla Infantil", "type": "select", "presets": VE_KIDS_CLOTHING_SIZES},
                {"key": "color", "label": "Color", "type": "text", "presets": ["Blanco", "Azul Marino", "Azul Celeste", "Beige", "Rojo", "Rosado", "Negro", "Amarillo", "Verde", "Estampado"]},
            ],
        },
        combo_item_placeholder="Ej: 2 Chemises Escolares + 1 Pantalón o Mono Escolar...",
        combo_templates=[
            {
                "name": "Combo Uniforme Escolar",
                "description": "2 Chemises escolares + 1 Pantalón o Mono escolar.",
                "combo_items": [
                    {"name": "Chemise Escolar (Blanca / Azul / Beige)", "quantity": 2, "unit": "und", "notes": "Talla a elección"},
                    {"name": "Pantalón o Mono Escolar Azul Marino", "quantity": 1, "unit": "und", "notes": ""},
                ],
            },
        ],
        fields=[
            {"key": "genero", "label": "Género", "type": "select", "required": False, "options": ["Niña", "Niño", "Unisex"], "section": "details"},
            {"key": "tipo_prenda", "label": "Tipo de Prenda", "type": "select", "required": False, "options": ["Conjunto Infantil", "Franela / Camisa", "Vestido / Braga", "Jean / Pantalón / Short", "Uniforme Escolar (Chemise, Mono, Pantalón, Falda)", "Pijama Infantil", "Suéter / Chaqueta"], "section": "details"},
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: EPK, Carter's, OshKosh, Ovejita, Nacional", "section": "details"},
        ],
    ),
    "Ropa para Bebés": _build_schema(
        archetype="apparel_fashion",
        ui_hint="Bodies, monitos, pijamas enterizas, ajuares de recién nacido (salida de clínica) y conjuntos por meses (RN, 0-3M, 3-6M, 6-9M, 9-12M, 12-18M, 18-24M).",
        buyer_ui_hint="Selecciona la talla por meses del bebé y el color o diseño.",
        allowed_units=["unit", "set", "pack", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tallas de Bebé (Por Meses) y Colores",
            "axes": [
                {"key": "size", "label": "Edad / Meses", "type": "select", "presets": VE_BABY_CLOTHING_SIZES},
                {"key": "color", "label": "Color / Diseño", "type": "text", "presets": ["Blanco", "Rosado", "Azul", "Amarillo", "Verde Menta", "Beige", "Estampado"]},
            ],
        },
        fields=[
            {"key": "genero", "label": "Género", "type": "select", "required": False, "options": ["Bebé Niña", "Bebé Niño", "Unisex / Neutro"], "section": "details"},
            {"key": "piezas_incluidas", "label": "Piezas en el Set", "type": "text", "required": False, "placeholder": "Ej: Set de 5 Bodies / Ajuar 4 piezas (Body, Pantalón, Gorro, Manoplas)", "section": "specs"},
            {"key": "tela_material", "label": "Tela", "type": "text", "required": False, "placeholder": "Ej: 100% Algodón Pima Hipoalergénico", "section": "specs"},
        ],
    ),
    "Zapatos Deportivos y de Goma": _build_schema(
        archetype="footwear",
        ui_hint="Zapatos de goma, sneakers casuales y deportivos. Incluye la nomenclatura numérica usada en Venezuela (34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46 e infantiles 18 al 33).",
        buyer_ui_hint="Selecciona tu talla numérica de calzado (34 al 46, o infantil 18 al 33) y el color.",
        allowed_units=["pair", "unit", "combo"],
        default_unit="pair",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tallas de Calzado en Número (34 al 46 / Infantil) y Colores",
            "helper_text": "Selecciona los números disponibles en inventario (34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46 o tallas infantiles 18-33).",
            "axes": [
                {"key": "shoe_size", "label": "Talla en Número (VE / EU)", "type": "select", "presets": VE_ADULT_SHOE_SIZES + VE_KIDS_SHOE_SIZES},
                {"key": "color", "label": "Color", "type": "text", "presets": ["Blanco", "Negro", "Blanco con Negro", "Gris", "Azul Marino", "Rojo", "Beige", "Rosado", "Verde", "Multicolor"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Nike, Adidas, New Balance, Puma, Converse, Vans, Skechers, RS21, Apolo", "section": "details"},
            {"key": "modelo", "label": "Modelo", "type": "text", "required": False, "placeholder": "Ej: Air Force 1 / Samba / Campus / 550 / Chuck Taylor", "section": "details"},
            {"key": "genero", "label": "Para quién", "type": "select", "required": False, "options": ["Caballero (39-46)", "Dama (34-40)", "Unisex (34-46)", "Infantil / Juvenil (18-35)"], "section": "details"},
            {"key": "calidad_origen", "label": "Calidad / Clasificación", "type": "select", "required": False, "options": ["100% Original", "Calidad PK / G5 / Top Quality", "Importado AAA", "Nacional"], "section": "condition"},
            {"key": "condicion", "label": "Condición", "type": "select", "required": False, "options": ["Nuevo en caja", "Nuevo sin caja", "Usado"], "section": "condition"},
        ],
    ),
    "Cholas, Sandalias y Tacones": _build_schema(
        archetype="footwear",
        ui_hint="Sandalias bajitas, tacones de fiesta, plataformas/yute, cholas playeras/sliders, zuecos tipo Crocs y alpargatas. Incluye numeración venezolana (34 al 46 e infantil 18 al 33).",
        buyer_ui_hint="Selecciona tu talla en número (34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46) y el color.",
        allowed_units=["pair", "unit", "dozen", "combo"],
        default_unit="pair",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tallas en Número (34 al 46) y Colores",
            "axes": [
                {"key": "shoe_size", "label": "Talla en Número (VE / EU)", "type": "select", "presets": VE_ADULT_SHOE_SIZES + VE_KIDS_SHOE_SIZES},
                {"key": "color", "label": "Color", "type": "text", "presets": ["Negro", "Beige / Nude", "Dorado", "Plateado", "Blanco", "Marrón / Miel", "Rojo", "Rosado", "Fucsia"]},
            ],
        },
        fields=[
            {"key": "tipo_calzado", "label": "Tipo de Calzado", "type": "select", "required": False, "options": ["Sandalias Bajitas / Planas", "Sandalias de Tacón", "Tacones / Stilettos", "Plataformas / Corridos / Yute", "Cholas Playeras / Sliders", "Zuecos (Tipo Crocs)", "Torera / Balerina"], "section": "details"},
            {"key": "altura_tacon", "label": "Altura de Tacón / Plataforma", "type": "select", "required": False, "options": ["Plano (Sin tacón)", "Bajo (3 a 5 cm)", "Medio (6 a 8 cm)", "Alto (9 a 12 cm)", "Plataforma Corrida"], "section": "specs"},
            {"key": "genero", "label": "Para quién", "type": "select", "required": False, "options": ["Dama", "Caballero", "Unisex", "Niña / Niño"], "section": "details"},
            {"key": "material", "label": "Material", "type": "text", "required": False, "placeholder": "Ej: Cuero, Semicuero, Charol, Goma EVA, Yute", "section": "specs"},
        ],
    ),
    "Zapatos Casuales y Formales": _build_schema(
        archetype="footwear",
        ui_hint="Mocasines, zapatos de vestir, botas, botines, zapatos colegiales/escolares y calzado casual en tallas numéricas de Venezuela (34 al 46 y escolares 24 al 38).",
        buyer_ui_hint="Selecciona tu talla numérica (34 al 46 o talla escolar) y el color.",
        allowed_units=["pair", "unit", "combo"],
        default_unit="pair",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tallas de Calzado en Número (34 al 46 / Escolar) y Colores",
            "axes": [
                {"key": "shoe_size", "label": "Talla en Número (VE / EU)", "type": "select", "presets": VE_ADULT_SHOE_SIZES + VE_KIDS_SHOE_SIZES},
                {"key": "color", "label": "Color", "type": "text", "presets": ["Negro", "Marrón Oscuro", "Miel / Cognac", "Azul Marino", "Beige", "Vino", "Blanco"]},
            ],
        },
        fields=[
            {"key": "tipo_calzado", "label": "Estilo", "type": "select", "required": False, "options": ["Mocasines", "Zapatos de Vestir / Oxford", "Botas y Botines", "Zapatos Escolares / Colegiales", "Casual / Náuticos", "Balerinas / Flats"], "section": "details"},
            {"key": "genero", "label": "Para quién", "type": "select", "required": False, "options": ["Caballero", "Dama", "Escolar Niño / Niña"], "section": "details"},
            {"key": "material_exterior", "label": "Material Exterior", "type": "select", "required": False, "options": ["100% Cuero Legítimo", "Semicuero / Sintético", "Gamuza / Nobuck", "Patente / Charol"], "section": "specs"},
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Kickers, Rex, Clarks, Timberland, Calzado Nacional", "section": "details"},
        ],
    ),
    "Bolsos y Carteras": _build_schema(
        archetype="fashion_accessories",
        ui_hint="Carteras de dama, bandoleras, bolsos tote, koalas/riñoneras y morrales casuales. Agrega variantes por color o tamaño.",
        buyer_ui_hint="Selecciona el color o modelo disponible.",
        allowed_units=["unit", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Color y Tamaño",
            "axes": [
                {"key": "color", "label": "Color", "type": "text", "presets": ["Negro", "Camel / Miel", "Marrón", "Beige / Crema", "Blanco", "Rojo", "Rosado", "Dorado"]},
                {"key": "size", "label": "Tamaño", "type": "select", "presets": ["Mini / Bandolera", "Mediana", "Grande / Tote", "Set (Cartera + Monedero)"]},
            ],
        },
        fields=[
            {"key": "tipo_bolso", "label": "Tipo", "type": "select", "required": False, "options": ["Cartera de Mano / Hombro", "Bandolera / Crossbody", "Bolso Tote / Shopping Bag", "Morral Casual / Ejecutivo", "Koala / Riñonera / Pechera", "Sobre / Clutch de Fiesta"], "section": "details"},
            {"key": "material", "label": "Material", "type": "select", "required": False, "options": ["Cuero Genuino", "Semicuero / PU", "Lona / Nylon Impermeable", "Tejido / Artesanal"], "section": "specs"},
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Michael Kors, Coach, Bimba y Lola, Totto, Nacional", "section": "details"},
        ],
    ),
    "Billeteras y Monederos": _build_schema(
        archetype="fashion_accessories",
        ui_hint="Billeteras de cuero para caballero, tarjeteros RFID, chequeras y monederos de dama.",
        buyer_ui_hint="Elige el color y diseño.",
        allowed_units=["unit", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Color",
            "axes": [
                {"key": "color", "label": "Color", "type": "text", "presets": ["Negro", "Marrón", "Miel / Cognac", "Azul Marino", "Rojo", "Rosado", "Beige"]},
            ],
        },
        fields=[
            {"key": "genero", "label": "Para quién", "type": "select", "required": False, "options": ["Caballero", "Dama", "Unisex"], "section": "details"},
            {"key": "material", "label": "Material", "type": "select", "required": False, "options": ["100% Cuero", "Cuero Sintético / PU", "Aluminio / RFID Blocking", "Tela / Lona"], "section": "specs"},
        ],
    ),
    "Joyería y Bisutería": _build_schema(
        archetype="fashion_accessories",
        ui_hint="Cadenas, collares, anillos, zarcillos/aretes, pulseras, tobilleras y dijes en oro laminado, plata 925 o acero inoxidable.",
        buyer_ui_hint="Selecciona el baño/material y la talla del anillo o largo de cadena.",
        allowed_units=["unit", "pair", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Material / Baño y Medida",
            "axes": [
                {"key": "finish", "label": "Color / Material", "type": "select", "presets": ["Dorado (Oro Laminado / Baño)", "Plateado (Plata 925 / Acero)", "Oro Rosa", "Acero Quirúrgico"]},
                {"key": "size", "label": "Talla de Anillo / Largo", "type": "select", "presets": ["Ajustable", "Talla 5", "Talla 6", "Talla 7", "Talla 8", "Talla 9", "Talla 10", "40 cm", "45 cm", "50 cm", "60 cm"]},
            ],
        },
        fields=[
            {"key": "tipo_joya", "label": "Tipo de Pieza", "type": "select", "required": False, "options": ["Cadena / Collar", "Zarcillos / Aretes / Topitos", "Pulsera / Brazalete / Esclava", "Anillo / Sortija", "Juego Completo (Collar + Zarcillos + Pulsera)", "Tobillera", "Dije / Charm"], "section": "details"},
            {"key": "material", "label": "Material", "type": "select", "required": False, "options": ["Acero Inoxidable (No mancha)", "Plata Ley 925", "Oro 18K", "Oro Laminado 18K / Gold Filled", "Bisutería / Fantasía Fina", "Perlas / Piedras Naturales"], "section": "specs"},
        ],
    ),
    "Lentes y Relojes": _build_schema(
        archetype="fashion_accessories",
        ui_hint="Relojes de pulsera (analógicos, digitales, cronógrafos), lentes de sol UV400 y monturas para cristales formulados.",
        buyer_ui_hint="Selecciona el color de montura, esfera o correa.",
        allowed_units=["unit", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Color / Modelo",
            "axes": [
                {"key": "color", "label": "Color", "type": "text", "presets": ["Dorado", "Plateado", "Negro", "Carey / Marrón", "Oro Rosa", "Azul"]},
            ],
        },
        fields=[
            {"key": "tipo_articulo", "label": "Artículo", "type": "select", "required": False, "options": ["Reloj Analógico / Cuarzo", "Reloj Digital / Deportivo", "Reloj Automático", "Lentes de Sol (UV400 / Polarizados)", "Montura Óptica (Para formular)"], "section": "details"},
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Casio, Invicta, Fossil, Curren, Poedagar, Ray-Ban, Oakley", "section": "details"},
            {"key": "genero", "label": "Para quién", "type": "select", "required": False, "options": ["Caballero", "Dama", "Unisex", "Infantil"], "section": "details"},
            {"key": "resistente_agua", "label": "Resistente al Agua (si es reloj)", "type": "boolean", "required": False, "section": "specs"},
            _warranty_field("Ej: 30 días, 3 meses o 1 año"),
        ],
    ),
    "Gorras, Sombreros y Correas": _build_schema(
        archetype="fashion_accessories",
        ui_hint="Gorras deportivas o casuales, sombreros playeros/llaneros, correas/cinturones de cuero para dama o caballero, corbatas y bufandas.",
        buyer_ui_hint="Selecciona la talla de correa (28 a 42) o el color de la gorra.",
        allowed_units=["unit", "pack", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Talla y Color",
            "axes": [
                {"key": "size", "label": "Talla (Gorra o Correa)", "type": "select", "presets": ["Ajustable / Talla Única", "Talla 30", "Talla 32", "Talla 34", "Talla 36", "Talla 38", "Talla 40", "Talla 42", "7", "7 1/8", "7 1/4", "7 3/8", "7 1/2"]},
                {"key": "color", "label": "Color", "type": "text", "presets": ["Negro", "Marrón", "Reversible (Negro/Marrón)", "Blanco", "Azul Marino", "Beige", "Rojo", "Verde"]},
            ],
        },
        fields=[
            {"key": "tipo_accesorio", "label": "Tipo de Accesorio", "type": "select", "required": False, "options": ["Gorra / Snapback / Trucker", "Sombrero / Pava Playera", "Correa / Cinturón de Caballero", "Correa / Cinturón de Dama", "Corbata / Pajarita"], "section": "details"},
            {"key": "material", "label": "Material", "type": "text", "required": False, "placeholder": "Ej: 100% Cuero, Algodón, Lona", "section": "specs"},
        ],
    ),
    "Maletas y Bolsos de Viaje": _build_schema(
        archetype="fashion_accessories",
        ui_hint="Maletas de viaje con ruedas (mano/cabina 10kg, mediana 23kg, grande), juegos de 3 maletas, bolsos deportivos de viaje y organizadores.",
        buyer_ui_hint="Selecciona el tamaño de la maleta (Carry-On 20\", Mediana 24\", Grande 28\" o Set) y el color.",
        allowed_units=["unit", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tamaño de Equipaje y Color",
            "axes": [
                {"key": "luggage_size", "label": "Tamaño / Capacidad", "type": "select", "presets": ["Bolso de Mano (8 kg)", "Carry-On Cabina 20\" (10 kg)", "Mediana Bodega 24\" (23 kg)", "Grande Bodega 28\"", "Juego de 3 Maletas (20\"+24\"+28\")"]},
                {"key": "color", "label": "Color", "type": "text", "presets": ["Negro", "Gris / Plata", "Azul Marino", "Rosado / Oro Rosa", "Verde", "Vino"]},
            ],
        },
        fields=[
            {"key": "material", "label": "Material", "type": "select", "required": False, "options": ["Rígida (ABS / Policarbonato)", "Tela / Lona Impermeable", "Cuero / Sintético"], "section": "specs"},
            {"key": "ruedas", "label": "Ruedas", "type": "select", "required": False, "options": ["4 Ruedas Dobles 360°", "2 Ruedas", "Sin Ruedas (Bolso de mano)"], "section": "specs"},
        ],
    ),

    # Alias legacy de Ropa y Accesorios
    "Ropa Femenina": _build_schema(
        archetype="apparel_fashion",
        ui_hint="Tallas de dama (XS, S, M, L, XL, XXL o 6-16 / 26-36) y colores.",
        buyer_ui_hint="Selecciona tu talla y color.",
        allowed_units=["unit", "set", "pack", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tallas y Colores",
            "axes": [
                {"key": "size", "label": "Talla", "type": "select", "presets": VE_CLOTHING_LETTER_SIZES + ["26", "28", "30", "32", "34", "36"]},
                {"key": "color", "label": "Color", "type": "text", "presets": VE_COMMON_COLORS},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Zara, Shein, Nacional", "section": "details"},
        ],
    ),
    "Ropa Masculina": _build_schema(
        archetype="apparel_fashion",
        ui_hint="Tallas de caballero (XS, S, M, L, XL, XXL, XXXL o pantalones 28 al 44) y colores.",
        buyer_ui_hint="Selecciona tu talla y color.",
        allowed_units=["unit", "set", "pack", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tallas y Colores",
            "axes": [
                {"key": "size", "label": "Talla", "type": "select", "presets": VE_CLOTHING_LETTER_SIZES + ["28", "30", "32", "34", "36", "38", "40", "42", "44"]},
                {"key": "color", "label": "Color", "type": "text", "presets": VE_COMMON_COLORS},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Tommy Hilfiger, Levi's, Polo", "section": "details"},
        ],
    ),
    "Ropa Infantil": _build_schema(
        archetype="apparel_fashion",
        ui_hint="Tallas por meses o años (RN a 24M y 2 a 16) y colores.",
        buyer_ui_hint="Elige la talla y el color.",
        allowed_units=["unit", "set", "pack", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tallas Infantiles y Colores",
            "axes": [
                {"key": "size", "label": "Talla", "type": "select", "presets": VE_BABY_CLOTHING_SIZES + VE_KIDS_CLOTHING_SIZES},
                {"key": "color", "label": "Color", "type": "text", "presets": VE_COMMON_COLORS},
            ],
        },
        fields=[
            {"key": "genero", "label": "Género", "type": "select", "required": False, "options": ["Niña", "Niño", "Unisex / Bebé"], "section": "details"},
        ],
    ),
    "Calzado": _build_schema(
        archetype="footwear",
        ui_hint="Tallas numéricas de calzado en Venezuela (34 al 46 e infantil 18 al 33) y colores.",
        buyer_ui_hint="Selecciona tu talla en número y color.",
        allowed_units=["pair", "unit", "combo"],
        default_unit="pair",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tallas de Calzado (34 al 46) y Colores",
            "axes": [
                {"key": "shoe_size", "label": "Talla en Número (VE / EU)", "type": "select", "presets": VE_ADULT_SHOE_SIZES + VE_KIDS_SHOE_SIZES},
                {"key": "color", "label": "Color", "type": "text", "presets": VE_COMMON_COLORS},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Nike, Adidas, New Balance", "section": "details"},
            {"key": "genero", "label": "Para quién", "type": "select", "required": False, "options": ["Dama", "Caballero", "Unisex", "Infantil"], "section": "details"},
        ],
    ),
    "Accesorios y Joyería": _build_schema(
        archetype="fashion_accessories",
        ui_hint="Relojes, cadenas, anillos, zarcillos, pulseras, lentes y correas.",
        buyer_ui_hint="Elige el color/baño o medida.",
        allowed_units=["unit", "pair", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        fields=[
            {"key": "material", "label": "Material Principal", "type": "text", "required": False, "placeholder": "Ej: Acero Inoxidable, Plata 925, Oro 18K", "section": "specs"},
        ],
    ),

    # --------------------------------------------------------------------------
    # 4. SALUD Y BELLEZA (10 Subcategorías Oficiales)
    # --------------------------------------------------------------------------
    "Cuidado Capilar, Tintes y Secadores": _build_schema(
        archetype="beauty_and_personal_care",
        ui_hint="Shampoo, acondicionador, baños de crema, ampollas, tintes (con numeración de tono), planchas y secadores de cabello.",
        buyer_ui_hint="Elige el tono del tinte, presentación en ml/g o modelo.",
        allowed_units=["unit", "pack", "set", "ml", "g", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tono de Tinte / Presentación / Modelo",
            "axes": [
                {"key": "shade_or_size", "label": "Tono / Presentación", "type": "text", "presets": ["1.0 Negro", "3.0 Castaño Oscuro", "5.0 Castaño Claro", "6.0 Rubio Oscuro", "7.0 Rubio Medio", "8.1 Rubio Cenizo", "250 ml", "500 ml", "1 Litro", "Keratina", "Argán"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Salerm, L'Oréal, Igora, Pantene, Karseell, Babyliss, Remington", "section": "details"},
            {"key": "tipo_producto", "label": "Tipo de Producto", "type": "select", "required": False, "options": ["Shampoo / Acondicionador", "Mascarilla / Baño de Crema", "Tinte / Decolorante / Agua Oxigenada", "Ampolla / Gotas / Termoprotector", "Secador / Plancha / Rizador", "Cepillos y Peines"], "section": "details"},
            {"key": "tipo_cabello", "label": "Ideal para", "type": "select", "required": False, "options": ["Todo tipo de cabello", "Cabello Seco / Maltratado", "Cabello Teñido / Decolorado", "Cabello Rizado / Afro", "Cabello Graso / Anticaspa", "Alisado / Keratina"], "section": "specs"},
            {"key": "contenido_neto", "label": "Contenido Neto / Potencia", "type": "text", "required": False, "placeholder": "Ej: 500 ml, Tubo 60 g, 450°F", "section": "specs"},
        ],
    ),
    "Skincare y Cuidado Facial": _build_schema(
        archetype="beauty_and_personal_care",
        ui_hint="Limpiadores faciales, serums, cremas hidratantes, contornos de ojos, protectores solares y mascarillas. Especifica tipo de piel, ingrediente activo y contenido.",
        buyer_ui_hint="Revisa el tipo de piel recomendado y contenido del envase.",
        allowed_units=["unit", "set", "pack", "ml", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tamaño / Tipo de Piel / Tono",
            "axes": [
                {"key": "variant", "label": "Presentación", "type": "text", "presets": ["30 ml", "50 ml", "88 ml", "236 ml", "473 ml", "Piel Grasa / Mixta", "Piel Seca", "Con Color", "Sin Color (Invisible)"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": True, "placeholder": "Ej: CeraVe, La Roche-Posay, The Ordinary, Eucerin, Bioderma, Neutrogena, COSRX", "section": "details"},
            {"key": "tipo_piel", "label": "Tipo de Piel", "type": "select", "required": False, "options": ["Todo tipo de piel", "Piel Grasa / Mixta", "Piel Seca", "Piel Sensible / Rosácea", "Piel con tendencia acnéica", "Piel Madura / Antiedad"], "section": "specs"},
            {"key": "ingrediente_activo", "label": "Ingrediente Principal / FPS", "type": "text", "required": False, "placeholder": "Ej: Ácido Hialurónico, Niacinamida 10%, Vitamina C, Retinol, SPF 50+", "section": "specs"},
            {"key": "contenido_neto", "label": "Contenido Neto", "type": "text", "required": False, "placeholder": "Ej: 30 ml, 50 ml, 236 ml", "section": "specs"},
        ],
    ),
    "Maquillaje de Rostro, Ojos y Labios": _build_schema(
        archetype="beauty_and_personal_care",
        ui_hint="Bases, correctores, polvos compactos/sueltos, labiales, rubores, rímel, delineadores y paletas. Agrega los tonos y acabados disponibles como variantes.",
        buyer_ui_hint="Selecciona tu tono o acabado antes de agregar al carrito.",
        allowed_units=["unit", "set", "pack", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tonos y Acabados Disponibles",
            "axes": [
                {"key": "shade", "label": "Tono / Número", "type": "text", "presets": ["Tono 01 (Claro)", "Tono 02 (Medio Claro)", "Tono 03 (Medio)", "Tono 04 (Bronce)", "Traslúcido", "Nude", "Rosa", "Rojo", "Vinotinto", "Negro", "Marrón"]},
                {"key": "finish", "label": "Acabado", "type": "select", "presets": ["Mate", "Satinado / Glow", "Brillante / Gloss", "Waterproof (A prueba de agua)"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Salomé, Dolce Bella, Maybelline, MAC, L'Oréal, NYX, Rare Beauty, Mon Reve", "section": "details"},
            {"key": "zona_aplicacion", "label": "Zona de Aplicación", "type": "select", "required": False, "options": ["Rostro (Base / Polvo / Corrector / Rubor)", "Labios (Labial / Gloss / Tinta)", "Ojos y Cejas (Rímel / Delineador / Sombras)", "Brochas, Esponjas y Accesorios", "Desmaquillantes y Fijadores"], "section": "details"},
            {"key": "acabado", "label": "Acabado", "type": "select", "required": False, "options": ["Mate", "Luminoso / Hidratante", "Natural", "Larga Duración / Waterproof"], "section": "specs"},
        ],
    ),
    "Perfumería, Splash y Fragancias": _build_schema(
        archetype="beauty_and_personal_care",
        ui_hint="Perfumes originales, árabes, colonias, body splash, cremas perfumadas y decants. Especifica volumen en ml, concentración y género.",
        buyer_ui_hint="Elige el tamaño (ml), aroma o presentación.",
        allowed_units=["unit", "ml", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tamaño (ml) / Aroma",
            "axes": [
                {"key": "volume", "label": "Presentación (ml)", "type": "select", "presets": ["Decant 5 ml", "Decant 10 ml", "30 ml", "50 ml", "75 ml", "100 ml", "125 ml", "200 ml", "250 ml (Body Splash)"]},
                {"key": "scent", "label": "Fragancia / Aroma", "type": "text", "presets": ["Original", "Bare Vanilla", "Pure Seduction", "Coconut Passion", "Velvet Petals", "Love Spell", "Aqua Kiss"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Casa / Marca", "type": "text", "required": True, "placeholder": "Ej: Lattafa, Armaf, Carolina Herrera, Dior, Victoria's Secret, Bath & Body Works, Yanbal", "section": "details"},
            {"key": "concentracion", "label": "Concentración", "type": "select", "required": False, "options": ["Eau de Parfum (EDP)", "Eau de Toilette (EDT)", "Parfum / Extrait", "Body Mist / Splash", "Crema Corporal Perfumada", "Estuche / Set de Regalo"], "section": "specs"},
            {"key": "genero", "label": "Para quién", "type": "select", "required": False, "options": ["Dama", "Caballero", "Unisex", "Infantil"], "section": "details"},
            {"key": "volumen_ml", "label": "Volumen", "type": "text", "required": False, "placeholder": "Ej: 100 ml / 250 ml", "section": "specs"},
        ],
    ),
    "Manicura, Pedicura y Uñas": _build_schema(
        archetype="beauty_and_personal_care",
        ui_hint="Pinturas de uñas, esmaltes semipermanentes, gel constructor, acrílicos, lámparas UV/LED, dremel/pulidoras, limas y cortaúñas.",
        buyer_ui_hint="Selecciona el color/tono, tamaño o modelo.",
        allowed_units=["unit", "set", "pack", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tono / Color / Medida",
            "axes": [
                {"key": "color_or_type", "label": "Tono / Tipo", "type": "text", "presets": ["Base Coat", "Top Coat", "Blanco Francés", "Vinotinto", "Rojo", "Nude /Vía Láctea", "Negro", "Brillo / Glitter"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Masglo, Valmy, Organic Nails, Mia Secret, OPI", "section": "details"},
            {"key": "tipo_producto", "label": "Tipo de Producto", "type": "select", "required": False, "options": ["Esmalte Tradicional", "Esmalte Semipermanente / Gel", "Acrílico / Monómero / Polygel", "Lámpara UV/LED / Dremel", "Herramientas (Cortaúñas, Alicate, Limas)", "Removedor / Acetona"], "section": "details"},
            {"key": "contenido_neto", "label": "Contenido / Potencia", "type": "text", "required": False, "placeholder": "Ej: 14 ml, 1 oz, 48W", "section": "specs"},
        ],
    ),
    "Higiene Personal, Desodorantes y Afeitado": _build_schema(
        archetype="beauty_and_personal_care",
        ui_hint="Desodorantes, jabones de tocador, cremas dentales, cepillos de dientes, afeitadoras, espuma de afeitar, toallas sanitarias y cuidado íntimo.",
        buyer_ui_hint="Elige la presentación o aroma.",
        allowed_units=["unit", "pack", "box", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Presentación / Aroma",
            "axes": [
                {"key": "presentation", "label": "Presentación", "type": "text", "presets": ["Unidad", "Pack x2", "Pack x3", "Barra / Stick", "Roll-On", "Spray / Aerosol", "Gel", "Nocturna", "Normal con Alas"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Colgate, Gillette, Rexona, Dove, Lady Speed Stick, Old Spice, Kotex, Nosotras, Listerine", "section": "details"},
            {"key": "contenido_neto", "label": "Contenido / Unidades", "type": "text", "required": False, "placeholder": "Ej: 100 ml, 150 g, Paquete x10", "section": "specs"},
        ],
    ),
    "Farmacia, Botiquín y Primeros Auxilios": _build_schema(
        archetype="pharmacy_and_wellness",
        ui_hint="Medicamentos de venta libre (OTC), analgésicos, antigripales, alcohol, gasas, curitas, algodón y soluciones antisépticas.",
        buyer_ui_hint="Verifica la presentación (tabletas, jarabe, sobres) y concentración.",
        allowed_units=["unit", "box", "pack", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Presentación / Concentración",
            "axes": [
                {"key": "presentation", "label": "Presentación", "type": "text", "presets": ["Blíster x10", "Caja x10", "Caja x20", "Caja x30", "Sobre", "Jarabe 120 ml", "Adulto", "Pediátrico"]},
            ],
        },
        fields=[
            {"key": "laboratorio_marca", "label": "Laboratorio / Marca", "type": "text", "required": False, "placeholder": "Ej: Calox, Leti, Genven, La Santé, Bayer, Elmor, Teragrip, Atamel", "section": "details"},
            {"key": "principio_activo", "label": "Principio Activo y Concentración", "type": "text", "required": False, "placeholder": "Ej: Acetaminofén 500mg, Ibuprofeno 400mg, Loratadina 10mg", "section": "specs"},
            {"key": "forma_farmaceutica", "label": "Forma Farmacéutica", "type": "select", "required": False, "options": ["Tabletas / Comprimidos", "Cápsulas / Cápsulas Blandas", "Jarabe / Suspensión", "Sobres / Polvo", "Crema / Gel / Ungüento", "Gotas Oftálmicas / Óticas / Nasales", "Insumo de Botiquín (Alcohol, Gasas, Curitas)"], "section": "specs"},
            {"key": "requiere_recipe", "label": "Requiere Récipe Médico", "type": "boolean", "required": False, "section": "condition"},
        ],
    ),
    "Vitaminas, Suplementos y Proteínas": _build_schema(
        archetype="pharmacy_and_wellness",
        ui_hint="Multivitamínicos, vitamina C, magnesio, colágeno, omega 3, probióticos y suplementos nutricionales.",
        buyer_ui_hint="Selecciona el sabor o cantidad de cápsulas/tabletas.",
        allowed_units=["unit", "box", "pack", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Presentación / Sabor",
            "axes": [
                {"key": "presentation", "label": "Contenido / Sabor", "type": "text", "presets": ["30 cápsulas", "60 cápsulas", "90 cápsulas", "120 cápsulas", "Gomitas", "Efervescente", "Naranja", "Sin Sabor"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca / Laboratorio", "type": "text", "required": False, "placeholder": "Ej: Now Foods, Centrum, Nature's Bounty, Kirkland, Sascha Fitness, Vitabiotics", "section": "details"},
            {"key": "componente_principal", "label": "Suplemento / Vitamina", "type": "text", "required": False, "placeholder": "Ej: Citrato de Magnesio 400mg, Vitamina C 1000mg, Colágeno Hidrolizado, Omega 3", "section": "specs"},
            {"key": "formato", "label": "Formato", "type": "select", "required": False, "options": ["Cápsulas / Softgels", "Tabletas", "Gomitas Masticables", "Polvo Soluble", "Sobres / Ampollas Bebibles", "Gotas"], "section": "specs"},
        ],
    ),
    "Salud Sexual y Preservativos": _build_schema(
        archetype="pharmacy_and_wellness",
        ui_hint="Preservativos, lubricantes íntimos, pruebas de embarazo y productos de bienestar íntimo.",
        buyer_ui_hint="Elige la presentación o tipo.",
        allowed_units=["unit", "box", "pack", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tipo / Cantidad",
            "axes": [
                {"key": "type", "label": "Tipo / Caja", "type": "text", "presets": ["Caja x3", "Caja x12", "Texturizado / Estriado", "Ultra Sensible / Delgado", "Retardante", "Sabores"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Durex, Duo, Prudence, Climax, K-Y, Clearblue", "section": "details"},
            {"key": "presentacion", "label": "Unidades / Contenido", "type": "text", "required": False, "placeholder": "Ej: Caja x3 unidades / Gel 50 ml", "section": "specs"},
        ],
    ),
    "Equipos Médicos y Tensiómetros": _build_schema(
        archetype="pharmacy_and_wellness",
        ui_hint="Tensiómetros digitales/manuales, glucómetros, cintas reactivas, nebulizadores, oxímetros, termómetros, sillas de ruedas, muletas y fajas ortopédicas.",
        buyer_ui_hint="Verifica las especificaciones o talla del equipo.",
        allowed_units=["unit", "box", "set", "pack", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Talla / Modelo / Presentación",
            "axes": [
                {"key": "variant", "label": "Talla / Versión", "type": "text", "presets": ["De Brazo", "De Muñeca", "Talla S", "Talla M", "Talla L", "Talla XL", "Caja x50 tiras"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Omron, Beurer, Accu-Chek, Sinocare, Littmann, Drive Medical", "section": "details"},
            {"key": "tipo_equipo", "label": "Tipo de Equipo", "type": "select", "required": False, "options": ["Tensiómetro", "Glucómetro / Cintas / Lancetas", "Nebulizador / Oxímetro / Termómetro", "Ortopedia y Movilidad (Sillas, Bastones, Fajas)", "Insumos Médicos Descartables"], "section": "details"},
            _warranty_field(),
        ],
    ),

    # Alias legacy de Salud y Belleza
    "Cuidado Personal": _build_schema(
        archetype="beauty_and_personal_care",
        ui_hint="Shampoo, acondicionador, cremas corporales, desodorantes, tintes y cuidado capilar.",
        buyer_ui_hint="Elige el aroma o presentación.",
        allowed_units=["unit", "pack", "set", "ml", "g", "combo"],
        default_unit="unit",
        supports_variants=True,
        fields=[{"key": "marca", "label": "Marca", "type": "text", "required": False, "section": "details"}],
    ),
    "Maquillaje": _build_schema(
        archetype="beauty_and_personal_care",
        ui_hint="Bases, correctores, labiales, rubores, máscaras de pestañas y paletas.",
        buyer_ui_hint="Selecciona tu tono o acabado.",
        allowed_units=["unit", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        fields=[{"key": "marca", "label": "Marca", "type": "text", "required": False, "section": "details"}],
    ),
    "Perfumería": _build_schema(
        archetype="beauty_and_personal_care",
        ui_hint="Perfumes, colonias, splash y decants.",
        buyer_ui_hint="Elige el tamaño (ml) o presentación.",
        allowed_units=["unit", "ml", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        fields=[{"key": "marca", "label": "Casa / Marca", "type": "text", "required": True, "section": "details"}],
    ),
    "Farmacia y Bienestar": _build_schema(
        archetype="pharmacy_and_wellness",
        ui_hint="Medicamentos OTC, vitaminas, suplementos y primeros auxilios.",
        buyer_ui_hint="Verifica la presentación y concentración.",
        allowed_units=["unit", "box", "pack", "combo"],
        default_unit="unit",
        supports_variants=True,
        fields=[{"key": "laboratorio_marca", "label": "Laboratorio / Marca", "type": "text", "required": False, "section": "details"}],
    ),

    # --------------------------------------------------------------------------
    # 5. HOGAR, MUEBLES Y JARDÍN (13 Subcategorías Oficiales)
    # --------------------------------------------------------------------------
    "Línea Blanca, Neveras y Lavadoras": _build_schema(
        archetype="home_appliances",
        ui_hint="Neveras, congeladores (freezers), lavadoras, secadoras, cocinas a gas/eléctricas, topes y hornos. Especifica capacidad, voltaje y garantía.",
        buyer_ui_hint="Verifica las dimensiones, capacidad, voltaje y garantía.",
        allowed_units=["unit", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Capacidad / Color / Voltaje",
            "axes": [
                {"key": "capacity_or_color", "label": "Capacidad / Acabado", "type": "text", "presets": ["Acero Inoxidable (Inox)", "Blanco", "Negro / Gris", "10 Pies", "12 Pies", "14 Pies", "18 Pies", "12 kg", "15 kg", "18 kg", "4 Hornillas", "6 Hornillas"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": True, "placeholder": "Ej: Samsung, LG, Mabe, Frigilux, Condesa, Haier, Whirlpool, Drija", "section": "details"},
            {"key": "modelo", "label": "Modelo", "type": "text", "required": False, "placeholder": "Ej: Lavadora Automática 15kg / Nevera No Frost", "section": "details"},
            {"key": "capacidad", "label": "Capacidad (Pies / Litros / Kg / Hornillas)", "type": "text", "required": False, "placeholder": "Ej: 14 Pies Cúbicos / 15 Kg / 300 Litros", "section": "specs"},
            {"key": "voltaje_alimentacion", "label": "Alimentación / Voltaje", "type": "select", "required": False, "options": ["110V", "220V", "Gas Directo / Bombona GLP", "Dual (Gas y Eléctrica)"], "section": "specs"},
            {"key": "condicion", "label": "Condición", "type": "select", "required": True, "options": ["Nuevo en Caja", "Open Box", "Usado"], "section": "condition"},
            _warranty_field("Ej: 1 año o 2 años de garantía"),
        ],
    ),
    "Pequeños Electrodomésticos y Cocina": _build_schema(
        archetype="home_appliances",
        ui_hint="Licuadoras, freidoras de aire (airfryers), cafeteras, microondas, batidoras, sanducheras, tostiarepas y planchas de ropa.",
        buyer_ui_hint="Revisa la capacidad (litros/tazas), potencia y color.",
        allowed_units=["unit", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Capacidad / Color",
            "axes": [
                {"key": "capacity_color", "label": "Capacidad / Color", "type": "text", "presets": ["Negro", "Acero Inoxidable", "Blanco", "Rojo", "4 Litros", "6 Litros", "8 Litros", "0.7 Pies", "1.1 Pies"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": True, "placeholder": "Ej: Oster, Black+Decker, Hamilton Beach, Ninja, Premier, Koblenz, KitchenAid", "section": "details"},
            {"key": "capacidad_potencia", "label": "Capacidad / Potencia", "type": "text", "required": False, "placeholder": "Ej: 4.5 Litros / 600W / 12 Tazas", "section": "specs"},
            {"key": "voltaje", "label": "Voltaje", "type": "select", "required": False, "options": ["110V", "220V", "Recargable USB"], "section": "specs"},
            _warranty_field(),
        ],
    ),
    "Aires Acondicionados y Ventiladores": _build_schema(
        archetype="home_appliances",
        ui_hint="Aires acondicionados Split, de ventana o portátiles (9.000 a 36.000 BTU) y ventiladores de pedestal, pared, techo o recargables.",
        buyer_ui_hint="Selecciona los BTU o tamaño en pulgadas y verifica el voltaje (110V/220V).",
        allowed_units=["unit", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Capacidad (BTU / Pulgadas) y Voltaje",
            "axes": [
                {"key": "btu_or_size", "label": "Capacidad / Tamaño", "type": "select", "presets": ["9.000 BTU", "12.000 BTU", "18.000 BTU", "24.000 BTU", "36.000 BTU", "Ventilador 16\"", "Ventilador 18\"", "Ventilador Recargable"]},
                {"key": "voltage", "label": "Voltaje", "type": "select", "presets": ["110V", "220V", "Recargable / Batería"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": True, "placeholder": "Ej: Frigilux, Condesa, Gplus, Samsung, LG, Haier, Alizz, Samurai, Taurus", "section": "details"},
            {"key": "tipo_equipo", "label": "Tipo de Equipo", "type": "select", "required": False, "options": ["Aire Split (Consola)", "Aire de Ventana", "Aire Portátil", "Ventilador de Pedestal / Pared", "Ventilador Recargable", "Ventilador Industrial / Techo"], "section": "details"},
            {"key": "capacidad_btu", "label": "Capacidad (BTU / Pulgadas)", "type": "text", "required": False, "placeholder": "Ej: 12.000 BTU / 18 pulgadas", "section": "specs"},
            {"key": "voltaje", "label": "Voltaje", "type": "select", "required": False, "options": ["110V", "220V", "110V / Batería Recargable"], "section": "specs"},
            _warranty_field("Ej: 1 año en equipo / 3 años en compresor"),
        ],
    ),
    "Plantas Eléctricas Domésticas e Inversores": _build_schema(
        archetype="home_appliances",
        ui_hint="Plantas eléctricas a gasolina/gas/diésel, estaciones de energía portátiles (EcoFlow/Bluetti), inversores de corriente y baterías de respaldo.",
        buyer_ui_hint="Revisa la potencia en Watts/kVA, autonomía y tipo de arranque.",
        allowed_units=["unit", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Potencia / Capacidad",
            "axes": [
                {"key": "power", "label": "Potencia", "type": "text", "presets": ["1000W", "2000W Inverter", "3500W", "5500W", "7500W", "10000W"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": True, "placeholder": "Ej: Honda, Generac, Champion, EcoFlow, Bluetti, Hyundai, Toyama, Total", "section": "details"},
            {"key": "tipo_energia", "label": "Tipo de Alimentación", "type": "select", "required": False, "options": ["Gasolina", "Dual (Gasolina + Gas GLP)", "Diésel / Gasoil", "Estación Portátil de Litio (Solar/AC)", "Inversor + Batería"], "section": "specs"},
            {"key": "potencia_watts", "label": "Potencia Nominal / Pico", "type": "text", "required": True, "placeholder": "Ej: 3500W / 4000W Pico (110V/220V)", "section": "specs"},
            {"key": "arranque", "label": "Tipo de Arranque", "type": "select", "required": False, "options": ["Eléctrico (Botón/Llave) + Manual", "Manual (Retráctil)", "Automático (Con ATS)", "Digital (Estación de Batería)"], "section": "specs"},
            _warranty_field(),
        ],
    ),
    "Tanques de Agua, Bombas y Filtros": _build_schema(
        archetype="hardware_and_construction",
        ui_hint="Tanques de agua cilíndricos o cónicos, bombas periféricas/centrífugas, presurizadores, filtros purificadores de agua, botellones y dispensadores.",
        buyer_ui_hint="Selecciona la capacidad en litros o potencia en HP.",
        allowed_units=["unit", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Capacidad (Litros) / Potencia (HP)",
            "axes": [
                {"key": "capacity_hp", "label": "Capacidad / Potencia", "type": "text", "presets": ["500 Litros", "540 Litros (Cilíndrico)", "1000 Litros", "1500 Litros", "2000 Litros", "1/2 HP", "3/4 HP", "1 HP", "Cartucho de Repuesto"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Resinca, Tinaco, Hidrojet, Pedrollo, Pasteur, Ozono, Griven", "section": "details"},
            {"key": "capacidad_medida", "label": "Capacidad / Dimensiones", "type": "text", "required": False, "placeholder": "Ej: 560 Litros (60 cm ancho, pasa por puerta) / 1/2 HP", "section": "specs"},
            _warranty_field(),
        ],
    ),
    "Muebles de Sala y Comedor": _build_schema(
        archetype="furniture_and_decor",
        ui_hint="Sofás, juegos de recibo, poltronas, comedores (4, 6, 8 puestos), centros de entretenimiento (TV), mesas de centro y sillas.",
        buyer_ui_hint="Selecciona el color o tapizado y verifica las medidas.",
        allowed_units=["unit", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Color / Tapizado / Puestos",
            "axes": [
                {"key": "color_finish", "label": "Color / Acabado", "type": "text", "presets": ["Gris", "Beige", "Negro", "Azul Rey", "Blanco", "Madera Natural", "Wengué", "4 Puestos", "6 Puestos"]},
            ],
        },
        fields=[
            {"key": "material_principal", "label": "Material / Tapizado", "type": "text", "required": False, "placeholder": "Ej: Madera Pino, Tela Antifluidos / Lino, MDF Melamina, Vidrio Templado", "section": "specs"},
            {"key": "dimensiones", "label": "Dimensiones (Ancho x Alto x Profundidad)", "type": "text", "required": False, "placeholder": "Ej: 200 x 85 x 90 cm", "section": "specs"},
            {"key": "requiere_armado", "label": "Modalidad de Entrega", "type": "select", "required": False, "options": ["Se entrega armado", "En caja (Requiere armado)", "Fabricación bajo pedido"], "section": "condition"},
            _warranty_field(),
        ],
    ),
    "Camas, Colchones y Box Spring": _build_schema(
        archetype="furniture_and_decor",
        ui_hint="Colchones ortopédicos y semi-ortopédicos, box spring, bases de cama, copetes y camas. Variantes por medida venezolana (Individual, Matrimonial, Queen, King).",
        buyer_ui_hint="Selecciona el tamaño de cama (Individual, Matrimonial, Queen o King).",
        allowed_units=["unit", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tamaño de Cama",
            "axes": [
                {"key": "bed_size", "label": "Medida de Cama", "type": "select", "presets": ["Individual (1.00 x 1.90m)", "Matrimonial (1.40 x 1.90m)", "Queen (1.60 x 1.90m)", "King (2.00 x 2.00m)", "Cuna / Infantil"]},
                {"key": "include_box", "label": "Modalidad", "type": "select", "presets": ["Solo Colchón", "Colchón + Box Spring", "Solo Base / Box Spring"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Paraíso, Simmons, confort, Divenca, Sweet Dreams", "section": "details"},
            {"key": "tipo_colchon", "label": "Firmeza / Tecnología", "type": "select", "required": False, "options": ["Ortopédico (Firme)", "Semi-Ortopédico", "Pillow Top (Doble Acolchado)", "Espuma / Gomaespuma", "Resortes Pocket (Independientes)"], "section": "specs"},
            _warranty_field("Ej: 3 años o 5 años de garantía"),
        ],
    ),
    "Sábanas, Edredones y Toallas": _build_schema(
        archetype="furniture_and_decor",
        ui_hint="Juegos de sábanas, edredones, cobijas térmicas, protectores de colchón, almohadas y toallas de baño.",
        buyer_ui_hint="Selecciona el tamaño de cama y el color o estampado.",
        allowed_units=["unit", "set", "pack", "combo"],
        default_unit="set",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tamaño y Color",
            "axes": [
                {"key": "bed_size", "label": "Tamaño", "type": "select", "presets": ["Individual", "Matrimonial", "Queen", "King", "Toalla Cuerpo Completo", "Set de Toallas"]},
                {"key": "color", "label": "Color / Estampado", "type": "text", "presets": ["Blanco", "Gris", "Beige", "Azul", "Rosa", "Vinotinto", "Estampado"]},
            ],
        },
        fields=[
            {"key": "material_hilos", "label": "Material / Cantidad de Hilos", "type": "text", "required": False, "placeholder": "Ej: 100% Algodón, Microfibra Suave, Bambú, Viscoelástica", "section": "specs"},
            {"key": "piezas_incluidas", "label": "Piezas Incluidas", "type": "text", "required": False, "placeholder": "Ej: 4 piezas (Sábana esquinera, plana y 2 fundas)", "section": "specs"},
        ],
    ),
    "Ollas, Sartenes y Utensilios de Cocina": _build_schema(
        archetype="furniture_and_decor",
        ui_hint="Baterías de cocina, sartenes antiadherentes, ollas de presión, calderos, budares, vajillas, cubiertos, vasos y envases.",
        buyer_ui_hint="Elige el tamaño, cantidad de piezas o color.",
        allowed_units=["unit", "set", "pack", "dozen", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Medida / Piezas / Color",
            "axes": [
                {"key": "size_or_set", "label": "Medida / Set", "type": "text", "presets": ["20 cm", "24 cm", "28 cm", "5 Litros", "7 Litros", "Set 5 piezas", "Set 10 piezas", "Set 12 piezas"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Tramontina, Magefesa, Rena Ware, Royal Prestige, T-fal, Corona", "section": "details"},
            {"key": "material", "label": "Material", "type": "select", "required": False, "options": ["Acero Inoxidable", "Aluminio / Antiadherente (Teflón)", "Cerámica / Granito", "Hierro Fundido", "Vidrio Refractario / Porcelana", "Silicona / Plástico Libre de BPA"], "section": "specs"},
        ],
    ),
    "Pocetas, Lavamanos y Baño": _build_schema(
        archetype="hardware_and_construction",
        ui_hint="Pocetas (sanitarios one-piece o dos piezas), lavamanos, muebles de baño, espejos LED, duchas, regaderas y accesorios de baño.",
        buyer_ui_hint="Verifica las medidas, color y si incluye grifería o herrajes.",
        allowed_units=["unit", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Color / Modelo",
            "axes": [
                {"key": "color", "label": "Color / Acabado", "type": "text", "presets": ["Blanco", "Negro Mate", "Cromado", "Dorado", "Con Mueble", "Solo Pieza"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Venceramica, Corona, Briggs, Griven, Franz Viegener", "section": "details"},
            {"key": "incluye", "label": "Qué incluye", "type": "text", "required": False, "placeholder": "Ej: Incluye tapa cierre suave y herraje interno", "section": "specs"},
        ],
    ),
    "Decoración, Cuadros y Espejos": _build_schema(
        archetype="furniture_and_decor",
        ui_hint="Espejos de cuerpo entero o decorativos, cuadros, lámparas de mesa/techo, alfombras, cortinas, persianas y plantas artificiales.",
        buyer_ui_hint="Elige el diseño, color o medida.",
        allowed_units=["unit", "set", "pair", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Medida / Color",
            "axes": [
                {"key": "variant", "label": "Medida / Marco", "type": "text", "presets": ["Dorado", "Negro", "Blanco", "Madera", "Con Luz LED", "Pequeño", "Mediano", "Grande"]},
            ],
        },
        fields=[
            {"key": "dimensiones", "label": "Medidas (Alto x Ancho)", "type": "text", "required": False, "placeholder": "Ej: 160 x 60 cm", "section": "specs"},
            {"key": "material", "label": "Material", "type": "text", "required": False, "placeholder": "Ej: Vidrio biselado, Lienzo Canvas, Tela Blackout", "section": "specs"},
        ],
    ),
    "Productos de Limpieza, Detergentes y Mopas": _build_schema(
        archetype="grocery_packaged",
        ui_hint="Detergente en polvo o líquido, suavizante, cloro, desinfectante, lavaplatos, papel toilette, bolsas de basura, escobas y mopas giratorias.",
        buyer_ui_hint="Selecciona el aroma, peso o presentación (litro, galón, bulto).",
        allowed_units=["unit", "l", "gal", "kg", "pack", "box", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Presentación y Aroma",
            "axes": [
                {"key": "size", "label": "Presentación", "type": "select", "presets": ["500 g", "900 g / 1 kg", "2.5 kg", "4 kg", "1 Litro", "Galón (3.78L)", "Carboy / Pimpina 20L", "Paquete 4 Rollos", "Paquete 12 Rollos"]},
                {"key": "scent", "label": "Aroma", "type": "text", "presets": ["Lavanda", "Bebé", "Floral", "Manzana / Canela", " Pino", "Limón", "Brisa Marina"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Ace, Ariel, Las Llaves, Suavitel, Downy, Axion, Mistolín, Rosal, Nevex", "section": "details"},
            {"key": "contenido_neto", "label": "Contenido Neto", "type": "text", "required": False, "placeholder": "Ej: 1 kg, 3.78 Litros, 4 Rollos", "section": "specs"},
        ],
    ),
    "Jardinería, Mangueras y Exteriores": _build_schema(
        archetype="furniture_and_decor",
        ui_hint="Mangueras de riego, desmalezadoras, grama artificial, plantas, materos, tierra abonada, parrilleras/BBQ y toldos.",
        buyer_ui_hint="Selecciona el largo en metros, tamaño o presentación.",
        allowed_units=["unit", "m", "m2", "kg", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Medida / Largo / Tamaño",
            "axes": [
                {"key": "size", "label": "Medida", "type": "text", "presets": ["10 metros", "15 metros", "20 metros", "30 metros", "1/2 pulgada", "Pequeño", "Mediano", "Grande"]},
            ],
        },
        fields=[
            {"key": "material_tipo", "label": "Material / Especificación", "type": "text", "required": False, "placeholder": "Ej: Manguera culebrilla reforzada, Grama sintética 20mm", "section": "specs"},
        ],
    ),

    # Alias legacy de Hogar, Muebles y Jardín
    "Electrodomésticos": _build_schema(
        archetype="home_appliances",
        ui_hint="Neveras, lavadoras, aires acondicionados, cocinas, licuadoras, cafeteras y airfryers.",
        buyer_ui_hint="Verifica el voltaje, capacidad y garantía del equipo.",
        allowed_units=["unit", "combo"],
        default_unit="unit",
        supports_variants=True,
        fields=[{"key": "marca", "label": "Marca", "type": "text", "required": True, "section": "details"}, _warranty_field()],
    ),
    "Muebles": _build_schema(
        archetype="furniture_and_decor",
        ui_hint="Sofás, comedores, escritorios, sillas, estantes y armarios.",
        buyer_ui_hint="Selecciona el color o tapizado y verifica las medidas.",
        allowed_units=["unit", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        fields=[{"key": "dimensiones", "label": "Dimensiones", "type": "text", "required": False, "section": "specs"}],
    ),
    "Dormitorio": _build_schema(
        archetype="furniture_and_decor",
        ui_hint="Colchones, juegos de sábanas, edredones, almohadas y camas.",
        buyer_ui_hint="Selecciona el tamaño de cama (Individual, Matrimonial, Queen o King) y color.",
        allowed_units=["unit", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        fields=[{"key": "tamano_cama", "label": "Tamaño", "type": "select", "required": False, "options": ["Individual", "Matrimonial", "Queen", "King"], "section": "specs"}],
    ),
    "Baño": _build_schema(
        archetype="furniture_and_decor",
        ui_hint="Juegos de toallas, alfombras, cortinas de baño, pocetas y accesorios.",
        buyer_ui_hint="Elige el color o tamaño.",
        allowed_units=["unit", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
    ),
    "Decoración": _build_schema(
        archetype="furniture_and_decor",
        ui_hint="Lámparas, espejos, cuadros, alfombras, cojines y cortinas.",
        buyer_ui_hint="Elige el diseño, color o medida.",
        allowed_units=["unit", "set", "pair", "combo"],
        default_unit="unit",
        supports_variants=True,
    ),
    "Limpieza del Hogar": _build_schema(
        archetype="grocery_packaged",
        ui_hint="Detergentes, cloro, desinfectantes, lavaplatos, bolsas y mopas.",
        buyer_ui_hint="Elige el aroma o presentación.",
        allowed_units=["unit", "l", "gal", "kg", "pack", "combo"],
        default_unit="unit",
        supports_variants=True,
    ),
    "Jardín y Exteriores": _build_schema(
        archetype="furniture_and_decor",
        ui_hint="Plantas, materos, parrilleras, mangueras y muebles de terraza.",
        buyer_ui_hint="Selecciona el tamaño o cantidad requerida.",
        allowed_units=["unit", "set", "kg", "m", "m2", "combo"],
        default_unit="unit",
        supports_variants=True,
    ),

    # --------------------------------------------------------------------------
    # 6. FERRETERÍA Y CONSTRUCCIÓN (11 Subcategorías Oficiales)
    # --------------------------------------------------------------------------
    "Herramientas Manuales": _build_schema(
        archetype="hardware_and_construction",
        ui_hint="Juegos de llaves, dados/copas, alicates, destornilladores, martillos, cintas métricas, niveles y cajas de herramientas.",
        buyer_ui_hint="Selecciona la medida en pulgadas o milímetros.",
        allowed_units=["unit", "set", "box", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Medida / Cantidad de Piezas",
            "axes": [
                {"key": "size", "label": "Medida", "type": "text", "presets": ["1/4\"", "3/8\"", "1/2\"", "8\"", "10\"", "12\"", "5 metros", "8 metros", "Milimétrico (mm)", "Pulgadas (SAE)"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Stanley, Truper, Total, Ingco, Urrea, Craftsman, Bahco", "section": "details"},
            {"key": "medida_piezas", "label": "Medida / Piezas Incluidas", "type": "text", "required": False, "placeholder": "Ej: Juego de 40 piezas / Llave ajustable 10\"", "section": "specs"},
            _warranty_field(),
        ],
    ),
    "Herramientas Eléctricas, Taladros y Esmeriles": _build_schema(
        archetype="hardware_and_construction",
        ui_hint="Taladros percutores/inalámbricos, esmeriles angulares, máquinas de soldar, compresores, sierras circulares, sopladoras e hidrolavadoras.",
        buyer_ui_hint="Revisa la potencia (W/V), diámetro de mandril/disco y accesorios incluidos.",
        allowed_units=["unit", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Potencia / Voltaje / Medida",
            "axes": [
                {"key": "spec", "label": "Versión / Medida", "type": "text", "presets": ["110V con Cable", "Inalámbrico 12V", "Inalámbrico 20V", "Disco 4-1/2\"", "Disco 7\"", "Mandril 1/2\"", "Mandril 3/8\""]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": True, "placeholder": "Ej: DeWalt, Makita, Bosch, Milwaukee, Total, Ingco, Truper, Stanley", "section": "details"},
            {"key": "tipo_alimentacion", "label": "Alimentación", "type": "select", "required": False, "options": ["Eléctrica con Cable (110V)", "Eléctrica (220V)", "Inalámbrica (Batería Ion-Litio)", "Bivoltaje (110V/220V - Soldadoras)", "Gasolina", "Neumática"], "section": "specs"},
            {"key": "potencia", "label": "Potencia / Capacidad", "type": "text", "required": False, "placeholder": "Ej: 850W / 20V Max (2 Baterías) / 200 Amperios", "section": "specs"},
            _warranty_field(),
        ],
    ),
    "Electricidad, Cables, Breakers y Tomacorrientes": _build_schema(
        archetype="hardware_and_construction",
        ui_hint="Cables eléctricos THW/SPT (por metro o rollo de 100m), breakers termomagnéticos, tableros, tomacorrientes, interruptores (switches), cajetines y teipe eléctrico.",
        buyer_ui_hint="Selecciona el calibre AWG, amperaje o modalidad de venta (metro o rollo).",
        allowed_units=["unit", "m", "pack", "box", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Calibre AWG / Amperaje / Presentación",
            "axes": [
                {"key": "gauge_or_amp", "label": "Calibre / Amperaje", "type": "text", "presets": ["Calibre #14 AWG", "Calibre #12 AWG", "Calibre #10 AWG", "Calibre #8 AWG", "1x15A", "1x20A", "1x30A", "2x20A", "2x30A", "2x40A", "2x50A", "110V", "220V"]},
                {"key": "sale_format", "label": "Formato", "type": "text", "presets": ["Por Metro", "Rollo 100m", "Unidad", "Caja"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Elecon, Cabel, General Electric, Square D, Siemens, Bticino, Veto, 3M", "section": "details"},
            {"key": "especificacion_electrica", "label": "Calibre / Amperaje / Polos", "type": "text", "required": False, "placeholder": "Ej: THW #12 Cobre 100% / Breaker 2x30A Enchufable", "section": "specs"},
        ],
    ),
    "Bombillos, Reflectores e Iluminación LED": _build_schema(
        archetype="hardware_and_construction",
        ui_hint="Bombillos LED, lámparas de emergencia recargables, paneles LED (empotrables o superficiales), reflectores de exterior, tubos LED y cintas LED.",
        buyer_ui_hint="Elige los Watts de potencia y el tono de luz (blanca fría o cálida).",
        allowed_units=["unit", "pack", "box", "m", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Potencia (W) y Tono de Luz",
            "axes": [
                {"key": "wattage", "label": "Potencia (Watts)", "type": "select", "presets": ["7W", "9W", "12W", "15W", "18W", "24W", "30W", "50W", "100W", "200W"]},
                {"key": "light_tone", "label": "Tono de Luz", "type": "select", "presets": ["Luz Blanca Fría (6500K)", "Luz Cálida (3000K)", "Luz Neutra (4000K)", "Multicolor RGB"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Sylvania, Hammer, Ilumina, Philips, Ledvance", "section": "details"},
            {"key": "rosca_montaje", "label": "Rosca / Tipo de Montaje", "type": "select", "required": False, "options": ["Rosca E27 (Estándar)", "Panel Empotrable", "Panel Superficial", "Reflector Exterior IP65/IP66", "Recargable de Emergencia", "Tubo T8 / Cinta LED"], "section": "specs"},
            {"key": "voltaje", "label": "Voltaje", "type": "select", "required": False, "options": ["Multivoltaje (85V-265V)", "110V", "220V", "Solar / Recargable"], "section": "specs"},
            _warranty_field(),
        ],
    ),
    "Plomería, Tuberías de PVC y Grifería": _build_schema(
        archetype="hardware_and_construction",
        ui_hint="Griferías para lavamanos/fregadero/ducha, llaves de paso, canillas, tuberías y conexiones PVC/PPR/HG, sifones y teflón.",
        buyer_ui_hint="Verifica la medida en pulgadas (1/2\", 3/4\", 2\", 4\") y el material.",
        allowed_units=["unit", "m", "set", "pack", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Medida en Pulgadas / Milímetros",
            "axes": [
                {"key": "diameter", "label": "Medida / Diámetro", "type": "select", "presets": ["1/2\"", "3/4\"", "1\"", "1-1/2\"", "2\"", "3\"", "4\"", "20 mm", "25 mm", "32 mm"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Griven, Tubrica, Pavco, Fundición Pacífico, FP, Cobra", "section": "details"},
            {"key": "material", "label": "Material", "type": "select", "required": False, "options": ["Acero Inoxidable 304", "Bronce / Latón Cromado", "PVC Aguas Blancas (Presión)", "PVC Aguas Negras (Sanitario)", "PPR Termofusión (Verde)", "Hierro Galvanizado (HG)", "ABS / Plástico"], "section": "specs"},
        ],
    ),
    "Sistemas de Hidroneumático y Bombas de Agua": _build_schema(
        archetype="hardware_and_construction",
        ui_hint="Bombas de agua periféricas, centrífugas y sumergibles, pulmones hidroneumáticos, presostatos, manómetros, válvulas check y flotantes eléctricos.",
        buyer_ui_hint="Verifica la potencia en HP, voltaje y diámetro de succión/descarga.",
        allowed_units=["unit", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Potencia (HP) / Capacidad",
            "axes": [
                {"key": "hp_or_liters", "label": "Potencia / Litros", "type": "select", "presets": ["1/2 HP", "3/4 HP", "1 HP", "1.5 HP", "2 HP", "Tanque 24 Litros", "Tanque 50 Litros", "Tanque 80 Litros", "Tanque 100 Litros"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": True, "placeholder": "Ej: Pedrollo, Hidrojet, Shimge, Leo, Total, Truper, Square D", "section": "details"},
            {"key": "voltaje", "label": "Voltaje", "type": "select", "required": False, "options": ["110V", "220V", "Bivoltaje (110V/220V)"], "section": "specs"},
            {"key": "potencia_caudal", "label": "Potencia / Altura Máxima", "type": "text", "required": False, "placeholder": "Ej: 1/2 HP - Altura máx 35m - Succión 1\"x1\"", "section": "specs"},
            _warranty_field(),
        ],
    ),
    "Pinturas, Cuñetes, Brochas y Selladores": _build_schema(
        archetype="hardware_and_construction",
        ui_hint="Pinturas de caucho (Clases A, B, C), esmaltes, fondos anticorrosivos, impermeabilizantes, rodillos, brochas, lijas y silicón/selladores.",
        buyer_ui_hint="Selecciona la presentación (1/4 galón, galón, cuñete) y el color.",
        allowed_units=["unit", "gal", "pack", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Presentación y Color",
            "axes": [
                {"key": "presentation", "label": "Envase / Medida", "type": "select", "presets": ["1/4 de Galón", "1 Galón (3.78L)", "Cuñete 4 Galones", "Cuñete 5 Galones", "Spray / Aerosol", "Cartucho 300 ml", "Brocha 2\"", "Brocha 3\"", "Brocha 4\"", "Rodillo 9\""]},
                {"key": "color", "label": "Color / Acabado", "type": "text", "presets": ["Blanco Mate", "Blanco Satinado", "Gris", "Marfil / Crema", "Negro Mate", "Negro Brillante", "Rojo Teja", "Transparente"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Venezolana de Pinturas (VP), Montana, Flamuko, Reinco, Pinco, Sika, Cebrisil", "section": "details"},
            {"key": "tipo_pintura", "label": "Tipo de Producto", "type": "select", "required": False, "options": ["Pintura de Caucho Interior/Exterior", "Pintura Satinada Lavable", "Esmalte / Anticorrosivo", "Impermeabilizante Elastómero", "Pasta Profesional / Estuco", "Thinner / Solvente", "Brochas, Rodillos y Lijas", "Silicón / Sellador"], "section": "specs"},
        ],
    ),
    "Cementos, Pegos, Mallas y Bloques": _build_schema(
        archetype="hardware_and_construction",
        ui_hint="Sacos de cemento, pego blanco/gris, cal, yeso, manto asfáltico, mallas electrosoldadas (Trucson), cabillas, bloques y cerámica.",
        buyer_ui_hint="Selecciona la unidad (saco, rollo, m² o unidad).",
        allowed_units=["unit", "kg", "m2", "m", "pack", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Presentación / Medida",
            "axes": [
                {"key": "presentation", "label": "Presentación", "type": "text", "presets": ["Saco 14 kg", "Saco 20 kg", "Saco 42.5 kg", "Rollo 10 m²", "Bloque 10 cm", "Bloque 15 cm", "Cabilla 3/8\"", "Cabilla 1/2\""]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Sika, Cindu, Edil, Vencemos, Pegoccidente", "section": "details"},
            {"key": "peso_rendimiento", "label": "Peso / Rendimiento", "type": "text", "required": False, "placeholder": "Ej: Saco de 14 kg (rinde 3-4 m²)", "section": "specs"},
        ],
    ),
    "Tornillería, Clavos y Chazos": _build_schema(
        archetype="hardware_and_construction",
        ui_hint="Tornillos tirafondo, drywall, autoperforantes, tuercas, arandelas, ramplugs (chazos plásticos/metálicos), clavos, discos de corte y electrodos.",
        buyer_ui_hint="Elige la medida y si se vende por unidad, paquete, cien o kilo.",
        allowed_units=["unit", "pack", "box", "kg", "combo"],
        default_unit="pack",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Medida y Empaque",
            "axes": [
                {"key": "size", "label": "Medida / Diámetro", "type": "text", "presets": ["1\"", "1-1/2\"", "2\"", "2-1/2\"", "3\"", "Chazo 1/4\" (Verde)", "Chazo 5/16\" (Azul)", "Chazo 3/8\" (Naranja)", "Electrodo E6013 3/32\"", "Electrodo E6013 1/8\"", "Disco Corte 4-1/2\""]},
                {"key": "pack_qty", "label": "Cantidad", "type": "text", "presets": ["Unidad", "Paquete x10", "Paquete x50", "Paquete x100", "Caja", "1 Kg"]},
            ],
        },
        fields=[
            {"key": "medida_rosca", "label": "Medida Exacta", "type": "text", "required": False, "placeholder": "Ej: #8 x 1-1/2\" / 5/16\"", "section": "specs"},
        ],
    ),
    "Cerraduras, Candados y Cilindros": _build_schema(
        archetype="hardware_and_construction",
        ui_hint="Cerraduras de pomo, manilla, embutir o sobreponer, cilindros de seguridad, candados anticizalla, bisagras y pasadores.",
        buyer_ui_hint="Selecciona el acabado o medida del cilindro/candado.",
        allowed_units=["unit", "set", "pair", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Acabado / Medida",
            "axes": [
                {"key": "finish_or_size", "label": "Acabado / Medida", "type": "text", "presets": ["Acero Inoxidable (Mate)", "Bronce / Dorado", "Negro", "30 mm", "40 mm", "50 mm", "60 mm", "70 mm", "Alcoba (Con Llave)", "Baño (Sin Llave)"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Cisa, Yale, Viro, Papaiz, Geo, Hermex, Tesa", "section": "details"},
            {"key": "tipo_cerradura", "label": "Tipo", "type": "select", "required": False, "options": ["Cerradura de Pomo / Manilla", "Cerradura de Sobreponer (Portón)", "Cerradura de Embutir (Reja/Puerta)", "Cilindro de Seguridad", "Candado", "Bisagras / Rieles / Herrajes"], "section": "details"},
        ],
    ),
    "Seguridad Industrial, Guantes y Botas": _build_schema(
        archetype="hardware_and_construction",
        ui_hint="Botas de seguridad con punta de hierro/dieléctricas (tallas 36 al 46), guantes de carnaza/nitrilo/puntos, lentes de seguridad, cascos, mascarillas, arneses y chalecos.",
        buyer_ui_hint="Selecciona tu talla (36 al 46 en botas o S-XXL en dotación).",
        allowed_units=["pair", "unit", "pack", "dozen", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tallas de Botas (36-46) / Dotación",
            "axes": [
                {"key": "size", "label": "Talla", "type": "select", "presets": ["36", "37", "38", "39", "40", "41", "42", "43", "44", "45", "46", "S", "M", "L", "XL", "XXL", "Talla Única"]},
                {"key": "color", "label": "Color", "type": "text", "presets": ["Negro", "Marrón", "Amarillo", "Blanco", "Naranja", "Azul"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Berrendo, Saga, 3M, Steelpro, Truper, Total", "section": "details"},
            {"key": "proteccion", "label": "Especificación de Seguridad", "type": "select", "required": False, "options": ["Punta de Hierro / Acero", "Dieléctrica (Punta Composite)", "Guantes Anticorte / Carnaza / Nitrilo", "Protección Visual / Auditiva / Respiratoria", "Casco / Arnés / Vial"], "section": "specs"},
        ],
    ),

    # Alias legacy de Ferretería y Construcción
    "Herramientas": _build_schema(
        archetype="hardware_and_construction",
        ui_hint="Taladros, esmeriles, juegos de llaves y herramientas manuales o eléctricas.",
        buyer_ui_hint="Revisa la potencia, voltaje y accesorios incluidos.",
        allowed_units=["unit", "set", "box", "combo"],
        default_unit="unit",
        supports_variants=True,
        fields=[{"key": "marca", "label": "Marca", "type": "text", "required": False, "section": "details"}],
    ),
    "Electricidad e Iluminación": _build_schema(
        archetype="hardware_and_construction",
        ui_hint="Bombillos LED, reflectores, protectores de voltaje, cables y breakers.",
        buyer_ui_hint="Elige la potencia (W), tono de luz o cantidad de metros.",
        allowed_units=["unit", "m", "pack", "box", "combo"],
        default_unit="unit",
        supports_variants=True,
        fields=[{"key": "marca", "label": "Marca", "type": "text", "required": False, "section": "details"}],
    ),
    "Plomería": _build_schema(
        archetype="hardware_and_construction",
        ui_hint="Griferías, bombas de agua, tanques, tuberías y conexiones PVC.",
        buyer_ui_hint="Verifica la medida en pulgadas y el material.",
        allowed_units=["unit", "m", "set", "pack", "combo"],
        default_unit="unit",
        supports_variants=True,
    ),
    "Materiales de Construcción": _build_schema(
        archetype="hardware_and_construction",
        ui_hint="Pinturas, impermeabilizantes, cemento, pego y tornillería.",
        buyer_ui_hint="Selecciona la unidad y el color o medida.",
        allowed_units=["unit", "gal", "kg", "m2", "m", "box", "pack", "combo"],
        default_unit="unit",
        supports_variants=True,
    ),

    # --------------------------------------------------------------------------
    # 7. CARROS, MOTOS Y OTROS (11 Subcategorías Oficiales)
    # --------------------------------------------------------------------------
    "Venta de Carros y Camionetas": _build_schema(
        archetype="vehicle_listing",
        ui_hint="Ficha completa para vehículos: indica marca, modelo, año, kilometraje, transmisión, tracción (4x2/4x4), tipo de combustible y estado legal de documentos.",
        buyer_ui_hint="Revisa la ficha técnica del vehículo (año, kilometraje, transmisión y documentación).",
        allowed_units=["unit"],
        default_unit="unit",
        supports_variants=False,
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": True, "placeholder": "Ej: Toyota, Chevrolet, Ford, Hyundai, Jeep, Chery, Mitsubishi, Nissan", "section": "details"},
            {"key": "modelo", "label": "Modelo y Versión", "type": "text", "required": True, "placeholder": "Ej: Corolla SE / 4Runner Limited / Hilux Kavak / Aveo LT", "section": "details"},
            {"key": "ano", "label": "Año", "type": "number", "required": True, "placeholder": "Ej: 2022", "section": "specs"},
            {"key": "kilometraje", "label": "Kilometraje", "type": "number", "required": True, "unit_suffix": "km", "placeholder": "Ej: 45000", "section": "specs"},
            {"key": "transmision", "label": "Transmisión", "type": "select", "required": True, "options": ["Automática", "Sincrónica (Manual)", "Secuencial / Dual", "4x4 Automática", "4x4 Sincrónica"], "section": "specs"},
            {"key": "combustible", "label": "Combustible", "type": "select", "required": False, "options": ["Gasolina", "Diésel / Gasoil", "Híbrido", "Eléctrico", "Dual (Gasolina/Gas)"], "section": "specs"},
            {"key": "color", "label": "Color", "type": "text", "required": False, "placeholder": "Ej: Blanco Perla, Plata, Gris Plomo, Negro", "section": "details"},
            {"key": "condicion", "label": "Estado / Documentación", "type": "select", "required": False, "options": ["0 km (Nuevo de Agencia)", "Usado - Único Dueño (Título 1-1)", "Usado - Papeles al día (Listo para firmar)"], "section": "condition"},
        ],
    ),
    "Venta de Motos": _build_schema(
        archetype="vehicle_listing",
        ui_hint="Ficha técnica de motocicletas: indica marca, modelo, cilindrada (cc), año y kilometraje.",
        buyer_ui_hint="Revisa el año, cilindrada, color y kilometraje de la moto.",
        allowed_units=["unit"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Color Disponible",
            "axes": [
                {"key": "color", "label": "Color", "type": "text", "presets": ["Negro", "Rojo", "Azul", "Blanco", "Gris", "Verde", "Amarillo"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": True, "placeholder": "Ej: Bera, Empire Keeway, Toro, Haojue, Suzuki, Yamaha, Honda, Ek", "section": "details"},
            {"key": "modelo", "label": "Modelo", "type": "text", "required": True, "placeholder": "Ej: SBR 150 / Horse KW-150 / RK 200 / TX 200 / KLR 650", "section": "details"},
            {"key": "cilindrada_cc", "label": "Cilindrada (cc)", "type": "text", "required": False, "placeholder": "Ej: 150 cc, 200 cc, 250 cc", "section": "specs"},
            {"key": "ano", "label": "Año", "type": "number", "required": True, "placeholder": "Ej: 2025", "section": "specs"},
            {"key": "kilometraje", "label": "Kilometraje", "type": "number", "required": False, "unit_suffix": "km", "placeholder": "Ej: 0", "section": "specs"},
            {"key": "condicion", "label": "Condición", "type": "select", "required": True, "options": ["Nueva (0 km)", "Usada - Papeles al día"], "section": "condition"},
            _warranty_field(),
        ],
    ),
    "Cauchos y Rines": _build_schema(
        archetype="auto_parts_and_fluids",
        ui_hint="Cauchos para carro, camioneta o camión, tripas, válvulas y juegos de rines. Especifica la medida exacta (ej. 185/65 R14, 195/65 R15, 265/70 R16).",
        buyer_ui_hint="Verifica la medida exacta del caucho o rin antes de pedir.",
        allowed_units=["unit", "pair", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Medida del Caucho / Rin",
            "axes": [
                {"key": "tire_size", "label": "Medida", "type": "text", "presets": ["175/70 R13", "185/60 R14", "185/65 R14", "195/60 R15", "195/65 R15", "205/55 R16", "235/75 R15", "265/70 R16", "265/65 R17", "285/70 R17"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": True, "placeholder": "Ej: Pirelli, Goodyear, Bridgestone, Firestone, Dunlop, Kumho, Linglong, BFGoodrich", "section": "details"},
            {"key": "medida_caucho_rin", "label": "Medida (Ancho/Perfil/Rin)", "type": "text", "required": True, "placeholder": "Ej: 195/65 R15 o Rin 16\" 6 Huecos", "section": "specs"},
            {"key": "tipo_terreno", "label": "Tipo de Terreno", "type": "select", "required": False, "options": ["Pista / Ciudad (H/T)", "Todo Terreno (A/T)", "Pantano / Barro (M/T)", "Carga Pesada"], "section": "specs"},
            {"key": "condicion", "label": "Condición", "type": "select", "required": False, "options": ["Nuevo", "Usado"], "section": "condition"},
            _warranty_field(),
        ],
    ),
    "Aceites de Motor, Filtros y Fluidos": _build_schema(
        archetype="auto_parts_and_fluids",
        ui_hint="Aceites de motor (20W-50, 15W-40, 10W-30, 5W-30, 2T/4T), filtros de aceite/aire/gasolina, valvulina, liga de frenos y refrigerantes. Puedes armar combos de cambio de aceite (Aceite + Filtro).",
        buyer_ui_hint="Selecciona la viscosidad o presentación (litro, galón, caja o combo con filtro).",
        allowed_units=["unit", "l", "gal", "box", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Viscosidad y Presentación",
            "axes": [
                {"key": "viscosity", "label": "Viscosidad / Tipo", "type": "select", "presets": ["20W-50", "15W-40", "10W-30", "10W-40", "5W-30", "5W-20", "4T 20W-50 (Moto)", "ATF Dexron III / Mercon", "Valvulina 80W-90", "DOT 3 / DOT 4", "Refrigerante 50/50"]},
                {"key": "presentation", "label": "Envase", "type": "select", "presets": ["Pinta / Cuarto (946 ml)", "1 Litro", "Galón (3.78L)", "Pimpina 5 Litros", "Caja x12 Litros", "Combo Cambio de Aceite + Filtro"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": True, "placeholder": "Ej: Shell, Castrol, Valvoline, Venoco, Inca, Mobil, Motul, Wix, Millard, Fram", "section": "details"},
            {"key": "tipo_aceite", "label": "Base / Categoría", "type": "select", "required": False, "options": ["Mineral", "Semi-Sintético", "100% Sintético (Full Synthetic)", "Filtro de Aceite / Aire / Gasolina", "Hidráulico / Caja Automática", "Refrigerante / Coolant", "Liga de Frenos"], "section": "specs"},
            {"key": "viscosidad_codigo", "label": "Viscosidad / Código de Filtro", "type": "text", "required": False, "placeholder": "Ej: 15W-40 API SP / Filtro PH3614 / ML-4967", "section": "specs"},
        ],
    ),
    "Repuestos de Motor y Tren Delantero": _build_schema(
        archetype="auto_parts_and_fluids",
        ui_hint="Amortiguadores, mesetas, muñones, terminales, bombas de agua/gasolina, correas de tiempo/única, bujías, empacaduras, baterías y sensores.",
        buyer_ui_hint="Verifica la compatibilidad con la marca, modelo y año de tu vehículo.",
        allowed_units=["unit", "pair", "set", "box", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Posición / Lado / Medida",
            "axes": [
                {"key": "position", "label": "Posición / Lado", "type": "select", "presets": ["Delantero", "Trasero", "Izquierdo (Piloto)", "Derecho (Copiloto)", "Par (Izquierdo + Derecho)", "Estándar (STD)", "0.10", "0.20", "0.30"]},
            ],
        },
        fields=[
            {"key": "marca_repuesto", "label": "Marca del Repuesto", "type": "text", "required": True, "placeholder": "Ej: Original (OEM), ACDelco, Motorcraft, Gabriel, Monroe, KYB, Denso, NGK, Bosch, Fulgor, Duncan", "section": "details"},
            {"key": "compatibilidad", "label": "Vehículos y Años Compatibles", "type": "text", "required": True, "placeholder": "Ej: Toyota Corolla 2003-2014 / Chevrolet Aveo / Ford Fiesta Power", "section": "specs"},
            {"key": "numero_parte_oem", "label": "Número de Parte / Código OEM", "type": "text", "required": False, "placeholder": "Ej: 96535011 / 23300-21010", "section": "specs"},
            {"key": "condicion", "label": "Condición", "type": "select", "required": True, "options": ["Nuevo Original (OEM)", "Nuevo Reemplazo (Aftermarket)", "Importadora / Chivera (Usado Garantizado)"], "section": "condition"},
            _warranty_field(),
        ],
    ),
    "Frenos, Pastillas y Discos": _build_schema(
        archetype="auto_parts_and_fluids",
        ui_hint="Juegos de pastillas de freno (cerámica o semimetálicas), bandas, discos de freno, tambores, bombas de freno y cilindros.",
        buyer_ui_hint="Verifica si es para tren delantero o trasero y el modelo de tu carro.",
        allowed_units=["set", "pair", "unit", "combo"],
        default_unit="set",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Posición / Compuesto",
            "axes": [
                {"key": "position", "label": "Posición", "type": "select", "presets": ["Delanteras", "Traseras", "Juego 4 Ruedas", "Cerámica", "Semi-Metálica"]},
            ],
        },
        fields=[
            {"key": "marca_repuesto", "label": "Marca", "type": "text", "required": True, "placeholder": "Ej: Wagner, Raybestos, Mamusa, Brembo, Kashima, Abe, ACDelco", "section": "details"},
            {"key": "compatibilidad", "label": "Vehículos Compatibles", "type": "text", "required": True, "placeholder": "Ej: Corsa / Aveo / Optra / Hilux / Fortuner", "section": "specs"},
            {"key": "codigo_fmsi", "label": "Código FMSI / Referencia", "type": "text", "required": False, "placeholder": "Ej: 7947-D1035 / 7298", "section": "specs"},
        ],
    ),
    "Repuestos, Cascos y Accesorios para Motos": _build_schema(
        archetype="auto_parts_and_fluids",
        ui_hint="Cascos (integrales, abatibles, certificados DOT), guantes, impermeables, cauchos y tripas de moto, kits de arrastre (catalina/piñón/cadena), baterías y repuestos.",
        buyer_ui_hint="Selecciona la talla (casco/impermeable) o el modelo de moto compatible.",
        allowed_units=["unit", "pair", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Talla / Modelo Compatible / Color",
            "axes": [
                {"key": "variant", "label": "Talla / Modelo / Medida", "type": "text", "presets": ["Talla S", "Talla M", "Talla L", "Talla XL", "Talla XXL", "SBR / Horse / Owen / Arsen", "TX 200 / RK 200", "2.75-18", "90/90-18", "3.00-18"]},
                {"key": "color", "label": "Color", "type": "text", "presets": ["Negro Mate", "Negro Brillante", "Rojo", "Azul", "Blanco", "Fluo"]},
            ],
        },
        fields=[
            {"key": "tipo_articulo", "label": "Tipo de Producto", "type": "select", "required": False, "options": ["Casco (Integral / Abatible / Abierto)", "Impermeable / Guantes / Indumentaria", "Kit de Arrastre / Frenos / Motor", "Caucho / Tripa de Moto", "Batería / Bujía / Eléctrico", "Parrilla / Maleta / Accesorios"], "section": "details"},
            {"key": "compatibilidad", "label": "Motos Compatibles / Certificación", "type": "text", "required": False, "placeholder": "Ej: Universal / Certificación DOT / Bera SBR / Empire Horse", "section": "specs"},
        ],
    ),
    "Luces LED, Barras y Faros": _build_schema(
        archetype="auto_parts_and_fluids",
        ui_hint="Bombillos LED para faros (H4, H7, H11, 9005, 9006), barras LED, exploradoras, neblineros, faros delanteros y stops traseros.",
        buyer_ui_hint="Selecciona el conector del bombillo (H4, H7, H11, 9005, etc.) o lado del faro.",
        allowed_units=["pair", "unit", "set", "combo"],
        default_unit="pair",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Conector (Socket) / Lado",
            "axes": [
                {"key": "socket", "label": "Socket / Conector", "type": "select", "presets": ["H4 (Alta y Baja)", "H7", "H11", "9005 (HB3)", "9006 (HB4)", "H1", "H3", "880", "T10 (Cocuyo)", "Universal 12V/24V", "Lado Piloto (Izq)", "Lado Copiloto (Der)"]},
            ],
        },
        fields=[
            {"key": "potencia_lumenes", "label": "Lúmenes / Potencia / Temperatura", "type": "text", "required": False, "placeholder": "Ej: 20.000 Lúmenes - 6500K Blanco Frío / Tricolor", "section": "specs"},
            {"key": "voltaje", "label": "Voltaje", "type": "select", "required": False, "options": ["12V", "12V - 24V (Carro y Camión)"], "section": "specs"},
            _warranty_field(),
        ],
    ),
    "Sonido para Carros, Reproductores y Plantas": _build_schema(
        archetype="auto_parts_and_fluids",
        ui_hint="Pantallas Android / Apple CarPlay (7\", 9\", 10\"), reproductores 1 DIN, cornetas coaxiales/ triaxiales, medios rangos, bajos, plantas (amplificadores) y kits de cables.",
        buyer_ui_hint="Revisa la medida en pulgadas, potencia en Watts/RMS y conectividad.",
        allowed_units=["unit", "pair", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Medida / Configuración",
            "axes": [
                {"key": "spec", "label": "Medida / Memoria", "type": "text", "presets": ["Pantalla 7\"", "Pantalla 9\"", "Pantalla 10\"", "2GB + 32GB CarPlay", "4GB + 64GB CarPlay", "6\"", "6x9\"", "8\"", "10\"", "12\""]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Pioneer, Lanzar Pro, Soundstream, JBL, Orion, Boss, Genérico Android", "section": "details"},
            {"key": "potencia_rms", "label": "Potencia (Watts Max / RMS)", "type": "text", "required": False, "placeholder": "Ej: 400W Max / 1000W 4 Canales", "section": "specs"},
            _warranty_field(),
        ],
    ),
    "Alarmas, Trancapalancas y Papel Ahumado": _build_schema(
        archetype="auto_parts_and_fluids",
        ui_hint="Alarmas automotrices, GPS Tracker, cortacorrientes, trancapalancas, trancavolantes, cierre centralizado y papel ahumado (porcentaje de oscuridad).",
        buyer_ui_hint="Selecciona el tono o modelo.",
        allowed_units=["unit", "set", "m", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tono / Modelo",
            "axes": [
                {"key": "shade_or_model", "label": "Tono / Versión", "type": "text", "presets": ["Claro (35% - 50%)", "Medio (20%)", "Oscuro (5%)", "Nanocerámico", "Universal"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Genius, Viper, Nemesis, Mul-T-Lock, 3M, Coban GPS", "section": "details"},
            _warranty_field(),
        ],
    ),
    "Cuidado Automotriz, Ceras y Champú": _build_schema(
        archetype="auto_parts_and_fluids",
        ui_hint="Champú para carros, cera líquida/en pasta, silicón para cauchos y tablero, limpia tapicería, paños de microfibra y ambientadores (pinitos).",
        buyer_ui_hint="Selecciona el tamaño del envase o aroma.",
        allowed_units=["unit", "gal", "l", "pack", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Presentación / Aroma",
            "axes": [
                {"key": "size", "label": "Presentación", "type": "text", "presets": ["500 ml", "1 Litro", "Galón (3.78L)", "Uva", "Fresa", "Carro Nuevo", "Vainilla", "Black Ice"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Meguiar's, 3M, Mothers, Armor All, Simoniz, SQ, Little Trees", "section": "details"},
        ],
    ),

    # Alias legacy de Carros, Motos y Otros
    "Venta de Autos": _build_schema(
        archetype="vehicle_listing",
        ui_hint="Ficha completa para vehículos: marca, modelo, año, kilometraje y transmisión.",
        buyer_ui_hint="Revisa la ficha técnica del vehículo.",
        allowed_units=["unit"],
        default_unit="unit",
        supports_variants=False,
        fields=[{"key": "marca", "label": "Marca", "type": "text", "required": True, "section": "details"}, {"key": "modelo", "label": "Modelo", "type": "text", "required": True, "section": "details"}, {"key": "ano", "label": "Año", "type": "number", "required": True, "section": "specs"}],
    ),
    "Repuestos para Autos": _build_schema(
        archetype="auto_parts_and_fluids",
        ui_hint="Pastillas de freno, amortiguadores, filtros, bombas, correas y baterías.",
        buyer_ui_hint="Verifica la compatibilidad con la marca, modelo y año de tu vehículo.",
        allowed_units=["unit", "pair", "set", "box", "combo"],
        default_unit="unit",
        supports_variants=True,
        fields=[{"key": "marca_repuesto", "label": "Marca del Repuesto", "type": "text", "required": True, "section": "details"}, {"key": "compatibilidad", "label": "Vehículos Compatibles", "type": "text", "required": True, "section": "specs"}],
    ),
    "Lubricantes y Fluidos": _build_schema(
        archetype="auto_parts_and_fluids",
        ui_hint="Aceites de motor, valvulina, liga de frenos y refrigerantes.",
        buyer_ui_hint="Selecciona la viscosidad o presentación.",
        allowed_units=["unit", "l", "gal", "box", "combo"],
        default_unit="unit",
        supports_variants=True,
        fields=[{"key": "marca", "label": "Marca", "type": "text", "required": True, "section": "details"}],
    ),
    "Neumáticos y Rines": _build_schema(
        archetype="auto_parts_and_fluids",
        ui_hint="Cauchos, tripas y rines.",
        buyer_ui_hint="Verifica la medida exacta del caucho o rin.",
        allowed_units=["unit", "pair", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        fields=[{"key": "marca", "label": "Marca", "type": "text", "required": True, "section": "details"}, {"key": "medida_caucho_rin", "label": "Medida", "type": "text", "required": True, "section": "specs"}],
    ),
    "Accesorios para Vehículos": _build_schema(
        archetype="auto_parts_and_fluids",
        ui_hint="Luces LED, reproductores, forros de asiento, alarmas y autolavado.",
        buyer_ui_hint="Selecciona el conector o versión compatible.",
        allowed_units=["unit", "pair", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
    ),
    "Motos": _build_schema(
        archetype="auto_parts_and_fluids",
        ui_hint="Repuestos de motos, cascos, guantes, cauchos de moto y baterías.",
        buyer_ui_hint="Selecciona la talla o el modelo de moto compatible.",
        allowed_units=["unit", "pair", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
    ),

    # --------------------------------------------------------------------------
    # 8. DEPORTES Y FITNESS (11 Subcategorías Oficiales)
    # --------------------------------------------------------------------------
    "Pesas, Mancuernas y Máquinas de Gym": _build_schema(
        archetype="sports_and_fitness",
        ui_hint="Mancuernas hexagonales o ajustables, discos olímpicos/estándar, barras, pesas rusas (kettlebells), bandas de resistencia, mats de yoga, bancos y máquinas.",
        buyer_ui_hint="Selecciona el peso en kg o libras (lb) y si se vende por unidad o par.",
        allowed_units=["unit", "pair", "set", "kg", "lb", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Peso / Resistencia",
            "axes": [
                {"key": "weight", "label": "Peso / Nivel", "type": "select", "presets": ["2 lb", "5 lb", "10 lb", "15 lb", "20 lb", "25 lb", "30 lb", "35 lb", "40 lb", "45 lb", "50 lb", "2.5 kg", "5 kg", "10 kg", "15 kg", "20 kg", "Set de Bandas"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Everlast, Rogue, York, Athletic, Body Solid, Genérico", "section": "details"},
            {"key": "material_recubrimiento", "label": "Material / Tipo", "type": "select", "required": False, "options": ["Caucho / Engomado (Hexagonal)", "Hierro Fundido", "Neopreno / Vinilo", "Acero Cromado", "Látex / Tela (Bandas)", "PVC / Goma EVA (Mat)"], "section": "specs"},
            {"key": "venta_formato", "label": "Formato de Venta", "type": "select", "required": False, "options": ["Por Unidad", "Por Par (2 unidades)", "Set / Kit Completo"], "section": "specs"},
        ],
    ),
    "Béisbol y Sóftbol (Guantes, Bates y Pelotas)": _build_schema(
        archetype="sports_and_fitness",
        ui_hint="Guantes y mascotas de béisbol/sóftbol (por pulgadas y mano de lanzamiento), bates de aluminio/madera/compuesto, pelotas, ganchos (spikes), bultos y cascos.",
        buyer_ui_hint="Selecciona la medida en pulgadas (guante/bate) y la mano de lanzamiento.",
        allowed_units=["unit", "pair", "dozen", "box", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Medida (Pulgadas) y Mano / Talla",
            "axes": [
                {"key": "size_inches", "label": "Medida / Talla", "type": "select", "presets": ["11.5\"", "11.75\"", "12\"", "12.5\"", "12.75\"", "13\"", "14\"", "Bate 32\" / 29 oz", "Bate 33\" / 30 oz", "Bate 34\" / 26 oz", "Pelota Oficial", "Caja x12 Pelotas"]},
                {"key": "throwing_hand", "label": "Mano del Lanzador", "type": "select", "presets": ["Lanza Derecho (Guante en mano izquierda - RHT)", "Lanza Zurdo (Guante en mano derecha - LHT)", "No aplica"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Rawlings, Wilson, Mizuno, Tamanaco, Louisville Slugger, Easton, DeMarini, Marucci", "section": "details"},
            {"key": "categoria_edad", "label": "Categoría", "type": "select", "required": False, "options": ["Adulto / Profesional", "Juvenil / Menor (Semillita a Junior)", "Sóftbol", "Entrenamiento"], "section": "specs"},
            {"key": "condicion", "label": "Condición", "type": "select", "required": False, "options": ["Nuevo", "Usado"], "section": "condition"},
        ],
    ),
    "Fútbol y Futsal (Balones, Tacos y Canilleras)": _build_schema(
        archetype="sports_and_fitness",
        ui_hint="Balones de fútbol campo (#5, #4) y salón/futsal, zapatos de tacos/multitacos/futsal (tallas 34 al 46 y niño 24 al 33), canilleras y guantes de portero.",
        buyer_ui_hint="Selecciona el número de balón o tu talla de calzado (34 al 46).",
        allowed_units=["unit", "pair", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Talla / Número y Color",
            "axes": [
                {"key": "size", "label": "Talla / Número", "type": "select", "presets": ["Balón #5 (Oficial)", "Balón #4 (Futsal / Juvenil)", "Balón #3", "Talla S", "Talla M", "Talla L"] + VE_ADULT_SHOE_SIZES + ["28", "29", "30", "31", "32", "33"]},
                {"key": "color", "label": "Color", "type": "text", "presets": VE_COMMON_COLORS},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Nike, Adidas, Puma, Mikasa, Golty, Penalty, Joma, Tamanaco", "section": "details"},
            {"key": "superficie", "label": "Superficie / Tipo", "type": "select", "required": False, "options": ["Fútbol Campo (Grama Natural FG)", "Grama Artificial (Turf / TF)", "Fútbol Sala / Futsal (Suela Lisa IC)", "Todo Uso / Accesorios"], "section": "specs"},
        ],
    ),
    "Básquetbol": _build_schema(
        archetype="sports_and_fitness",
        ui_hint="Balones de baloncesto (#7 oficial, #6, #5) para cancha interna o asfalto (outdoor), aros, mallas, tableros y accesorios.",
        buyer_ui_hint="Selecciona el tamaño del balón (#7, #6, #5) o talla.",
        allowed_units=["unit", "pair", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tamaño (#7, #6, #5) / Talla",
            "axes": [
                {"key": "ball_size", "label": "Tamaño / Talla", "type": "select", "presets": ["Número 7 (Oficial Adulto)", "Número 6 (Femenino / Juvenil)", "Número 5 (Infantil)", "Indoor / Outdoor", "Outdoor (Asfalto)"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Spalding, Wilson, Molten, Tamanaco, Nike, Jordan", "section": "details"},
            {"key": "material", "label": "Material", "type": "select", "required": False, "options": ["Cuero Compuesto (Indoor/Outdoor)", "Caucho / Goma (Outdoor / Cancha Abierta)", "Acero / Nylon (Aros y Mallas)"], "section": "specs"},
        ],
    ),
    "Pádel y Tenis": _build_schema(
        archetype="sports_and_fitness",
        ui_hint="Palas de pádel, raquetas de tenis y beach tennis, tubos de pelotas presurizadas, overgrips, paleteros/bolsos y protectores.",
        buyer_ui_hint="Revisa la forma de la pala/raqueta, peso y accesorios.",
        allowed_units=["unit", "pack", "box", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Formato / Color / Empaque",
            "axes": [
                {"key": "variant", "label": "Presentación / Modelo", "type": "text", "presets": ["Unidad", "Tubo x3 Pelotas", "Caja x24 Tubos", "Pack x3 Overgrips", "Control (Redonda)", "Polivalente (Lágrima)", "Potencia (Diamante)"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Bullpadel, Nox, Babolat, Adidas, Head, Wilson, Siux, Kuikma", "section": "details"},
            {"key": "disciplina", "label": "Disciplina", "type": "select", "required": False, "options": ["Pádel", "Tenis", "Beach Tennis", "Pickleball", "Ping Pong (Tenis de Mesa)"], "section": "details"},
            {"key": "material_nucleo", "label": "Material (Carbono / Fibra / EVA)", "type": "text", "required": False, "placeholder": "Ej: Carbono 12K / 18K / Fibra de Vidrio / Goma EVA Soft", "section": "specs"},
        ],
    ),
    "Bicicletas y Ciclismo": _build_schema(
        archetype="sports_and_fitness",
        ui_hint="Bicicletas montañeras (MTB), de ruta o BMX (por rin 16, 20, 24, 26, 27.5, 29), cascos de ciclismo, luces, cauchos, tripas y repuestos.",
        buyer_ui_hint="Verifica la medida del rin (20, 26, 27.5, 29) y talla del cuadro.",
        allowed_units=["unit", "pair", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Rin / Talla y Color",
            "axes": [
                {"key": "wheel_or_frame", "label": "Rin / Talla", "type": "select", "presets": ["Rin 29", "Rin 27.5", "Rin 26", "Rin 24", "Rin 20", "Rin 16", "Rin 12", "Talla S", "Talla M", "Talla L"]},
                {"key": "color", "label": "Color", "type": "text", "presets": VE_COMMON_COLORS},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Trek, Specialized, Giant, Shimano,GW, Greco, Sforzo, Rockbros", "section": "details"},
            {"key": "velocidades_componentes", "label": "Velocidades / Componentes", "type": "text", "required": False, "placeholder": "Ej: 21 Velocidades Shimano / Frenos de Disco Hidráulicos / Cuadro de Aluminio", "section": "specs"},
            {"key": "condicion", "label": "Condición", "type": "select", "required": False, "options": ["Nueva", "Usada"], "section": "condition"},
        ],
    ),
    "Ropa Deportiva, Monos y Licras": _build_schema(
        archetype="apparel_fashion",
        ui_hint="Conjuntos de gym, leggings, licras, bikers, tops deportivos, franelas dry-fit, shorts y monos deportivos en tallas venezolanas (XS a XXXL).",
        buyer_ui_hint="Selecciona tu talla (XS a XXXL) y color.",
        allowed_units=["unit", "set", "pack", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tallas Deportivas y Colores",
            "axes": [
                {"key": "size", "label": "Talla", "type": "select", "presets": VE_CLOTHING_LETTER_SIZES},
                {"key": "color", "label": "Color", "type": "text", "presets": VE_COMMON_COLORS},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Nike, Adidas, Under Armour, Gymshark, Puma, Nacional", "section": "details"},
            {"key": "genero", "label": "Para quién", "type": "select", "required": False, "options": ["Dama", "Caballero", "Unisex", "Infantil"], "section": "details"},
            {"key": "tela", "label": "Tipo de Tela", "type": "text", "required": False, "placeholder": "Ej: Suplex Brasileño, Lycra Poliamida, Dry-Fit Microperforado", "section": "specs"},
        ],
    ),
    "Zapatos Deportivos y Gomas": _build_schema(
        archetype="footwear",
        ui_hint="Zapatos para correr (running), entrenamiento (training), pádel, tenis o básquet en nomenclatura numérica venezolana (34 al 46).",
        buyer_ui_hint="Selecciona tu talla en número (34 al 46) y el color.",
        allowed_units=["pair", "unit", "combo"],
        default_unit="pair",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tallas de Calzado Deportivo (34 al 46) y Colores",
            "axes": [
                {"key": "shoe_size", "label": "Talla en Número (VE / EU)", "type": "select", "presets": VE_ADULT_SHOE_SIZES + VE_KIDS_SHOE_SIZES},
                {"key": "color", "label": "Color", "type": "text", "presets": VE_COMMON_COLORS},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Nike, Adidas, Asics, New Balance, Under Armour, Brooks, Salomon", "section": "details"},
            {"key": "disciplina", "label": "Disciplina", "type": "select", "required": False, "options": ["Running / Maratón", "Gym / Crossfit / Training", "Pádel / Tenis", "Básquetbol", "Senderismo / Trail", "Uso Diario"], "section": "details"},
            {"key": "genero", "label": "Para quién", "type": "select", "required": False, "options": ["Dama", "Caballero", "Unisex", "Infantil"], "section": "details"},
        ],
    ),
    "Camping, Carpas y Colchones Inflables": _build_schema(
        archetype="sports_and_fitness",
        ui_hint="Carpas de campaña (2, 4, 6, 8 personas), colchones inflables (Individual, Matrimonial, Queen), bombas de aire, sacos de dormir, sillas plegables y linternas.",
        buyer_ui_hint="Selecciona la capacidad (personas o tamaño de colchón) y color.",
        allowed_units=["unit", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Capacidad / Tamaño",
            "axes": [
                {"key": "capacity", "label": "Capacidad / Medida", "type": "select", "presets": ["2 Personas", "4 Personas", "6 Personas", "8 Personas", "Individual", "Matrimonial", "Queen", "Con Bomba Incorporada"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Coleman, Intex, Bestway, Klimber, Ozark Trail, National Geographic", "section": "details"},
            {"key": "impermeabilidad_medidas", "label": "Dimensiones / Especificaciones", "type": "text", "required": False, "placeholder": "Ej: Impermeable / Incluye bolso de transporte", "section": "specs"},
        ],
    ),
    "Cavas, Coolers y Termos": _build_schema(
        archetype="sports_and_fitness",
        ui_hint="Cavas rígidas o de tela con ruedas, coolers, termos térmicos de acero inoxidable (Stanley, Yeti, Contigo, Hydro Flask) y botellones deportivos.",
        buyer_ui_hint="Selecciona la capacidad en onzas (oz), litros o latas y el color.",
        allowed_units=["unit", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Capacidad y Color",
            "axes": [
                {"key": "capacity", "label": "Capacidad", "type": "select", "presets": ["16 oz", "20 oz", "24 oz", "30 oz", "40 oz (1.18L)", "64 oz (Medio Galón)", "1 Galón", "Cava 16 Quart", "Cava 28 Quart", "Cava 48 Quart", "Cava 52 Quart", "Cava 70 Quart"]},
                {"key": "color", "label": "Color", "type": "text", "presets": VE_COMMON_COLORS},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Stanley, Yeti, Coleman, Igloo, Contigo, Hydro Flask, Owala, Thermos", "section": "details"},
            {"key": "material_retencion", "label": "Material / Conservación Térmica", "type": "text", "required": False, "placeholder": "Ej: Acero Inoxidable Doble Pared al Vacío (24h frío)", "section": "specs"},
        ],
    ),
    "Proteínas, Creatinas y Suplementos Gym": _build_schema(
        archetype="sports_and_fitness",
        ui_hint="Whey Protein (aislada/concentrada), ganadores de peso (Mass Gainer), creatina monohidratada, pre-entrenos (pre-workout), aminoácidos (BCAA/EAA) y barras proteicas.",
        buyer_ui_hint="Selecciona el sabor y el peso/servicios del envase.",
        allowed_units=["unit", "lb", "kg", "box", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Sabor y Presentación",
            "axes": [
                {"key": "flavor", "label": "Sabor", "type": "text", "presets": ["Vainilla", "Chocolate", "Fresa", "Cookies & Cream", "Mantequilla de Maní", "Fruit Punch", "Watermelon (Patilla)", "Blue Raspberry", "Sin Sabor (Unflavored)"]},
                {"key": "size", "label": "Peso / Servicios", "type": "select", "presets": ["300 g (60 serv)", "500 g", "1 kg", "2 lb", "5 lb", "Bolsón 6 lb", "Bolsón 12 lb", "30 Servicios", "60 Servicios", "100 Servicios"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": True, "placeholder": "Ej: Optimum Nutrition (ON), Sascha Fitness, Dymatize, MuscleTech, BSN, Dragon Pharma, Nutrex", "section": "details"},
            {"key": "tipo_suplemento", "label": "Tipo de Suplemento", "type": "select", "required": False, "options": ["Proteína (Whey Isolate / Concentrate)", "Ganador de Peso (Mass Gainer)", "Creatina Monohidratada", "Pre-Entreno (Pre-Workout)", "Aminoácidos (BCAA / EAA / Glutamina)", "Quemador / Carnitina", "Shaker / Accesorios"], "section": "details"},
            {"key": "servicios_por_envase", "label": "Servicios / Peso Neto", "type": "text", "required": False, "placeholder": "Ej: 2 lb (28 servicios) / 300g (60 servicios)", "section": "specs"},
        ],
    ),

    # Alias legacy de Deportes y Fitness
    "Fitness y Musculación": _build_schema(
        archetype="sports_and_fitness",
        ui_hint="Mancuernas, discos, bandas elásticas, mats de yoga y suplementos deportivos.",
        buyer_ui_hint="Selecciona el peso, resistencia o sabor.",
        allowed_units=["unit", "pair", "set", "kg", "lb", "combo"],
        default_unit="unit",
        supports_variants=True,
    ),
    "Ropa y Calzado Deportivo": _build_schema(
        archetype="apparel_fashion",
        ui_hint="Conjuntos deportivos, leggings, franelas dry-fit y zapatos deportivos.",
        buyer_ui_hint="Selecciona tu talla y color.",
        allowed_units=["unit", "pair", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tallas y Colores",
            "axes": [
                {"key": "size", "label": "Talla", "type": "select", "presets": VE_CLOTHING_LETTER_SIZES + VE_ADULT_SHOE_SIZES},
                {"key": "color", "label": "Color", "type": "text", "presets": VE_COMMON_COLORS},
            ],
        },
    ),
    "Deportes Específicos": _build_schema(
        archetype="sports_and_fitness",
        ui_hint="Palas de pádel, raquetas, balones, guantes de béisbol, bates y bicicletas.",
        buyer_ui_hint="Revisa la talla o especificaciones técnicas del implemento.",
        allowed_units=["unit", "pair", "set", "pack", "combo"],
        default_unit="unit",
        supports_variants=True,
    ),
    "Camping y Outdoors": _build_schema(
        archetype="sports_and_fitness",
        ui_hint="Cavas, coolers, termos, carpas y sillas plegables.",
        buyer_ui_hint="Selecciona la capacidad o color.",
        allowed_units=["unit", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
    ),

    # --------------------------------------------------------------------------
    # 9. BEBÉS Y MATERNIDAD (9 Subcategorías Oficiales)
    # --------------------------------------------------------------------------
    "Pañales, Toallitas y Crema Antipañalitis": _build_schema(
        archetype="baby_and_maternity",
        ui_hint="Pañales desechables (tallas RN, P, M, G, XG, XXG), toallitas húmedas y cremas antipañalitis (Desitin, Beducen, Nistatina).",
        buyer_ui_hint="Selecciona la talla del bebé (RN, P, M, G, XG, XXG) y la cantidad del paquete.",
        allowed_units=["pack", "box", "unit", "combo"],
        default_unit="pack",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Talla de Pañal y Cantidad",
            "axes": [
                {"key": "diaper_size", "label": "Talla de Pañal", "type": "select", "presets": VE_DIAPER_SIZES},
                {"key": "count", "label": "Unidades / Empaque", "type": "text", "presets": ["Paquete x10", "Paquete x20", "Paquete x30", "Paquete x40", "Paquete x50", "Paquete x80", "Paquete x100", "Caja / Bulto"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Huggies, Pampers, Pequeñín, Babysec, Winny, Desitin, Beducen", "section": "details"},
            {"key": "unidades_por_empaque", "label": "Unidades por Paquete", "type": "number", "required": False, "placeholder": "Ej: 40", "section": "specs"},
        ],
    ),
    "Teteros, Esterilizadores y Chupones": _build_schema(
        archetype="baby_and_maternity",
        ui_hint="Teteros anticólicos (4 oz, 8 oz, 9 oz, 11 oz), tetinas por flujo/etapa, chupones, vasos entrenadores, esterilizadores y cepillos limpiateteros.",
        buyer_ui_hint="Selecciona la capacidad en onzas (oz), etapa o color.",
        allowed_units=["unit", "pack", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Capacidad (oz) / Etapa y Color",
            "axes": [
                {"key": "capacity_stage", "label": "Capacidad / Etapa", "type": "select", "presets": ["2 oz", "4 oz", "5 oz", "8 oz", "9 oz", "11 oz", "0-6 Meses (Nivel 1)", "6-18 Meses (Nivel 2-3)", "+18 Meses"]},
                {"key": "color", "label": "Color", "type": "text", "presets": ["Transparente", "Azul", "Rosa", "Verde", "Blanco"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Philips Avent, Dr. Brown's, Chicco, Nuby, Tommee Tippee, Pigeon, Evenflo", "section": "details"},
            {"key": "libre_bpa", "label": "Libre de BPA / Anticólico", "type": "boolean", "required": False, "section": "specs"},
        ],
    ),
    "Lactancia Materna y Extractores": _build_schema(
        archetype="baby_and_maternity",
        ui_hint="Extractores de leche (eléctricos, manos libres o manuales), bolsas recolectoras de leche, protectores de lactancia, pezoneras y cremas de lanolina.",
        buyer_ui_hint="Revisa el tipo de extractor o cantidad de unidades.",
        allowed_units=["unit", "box", "pack", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Modelo / Talla de Copa / Unidades",
            "axes": [
                {"key": "variant", "label": "Modelo / Presentación", "type": "text", "presets": ["Simple (1 Lado)", "Doble (2 Lados)", "Manos Libres (Wearable)", "Manual", "Copa 24 mm", "Caja x30 Bolsas", "Caja x60 Protectores"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Medela, Lansinoh, Momcozy, Philips Avent, Pigeon", "section": "details"},
            _warranty_field(),
        ],
    ),
    "Fórmulas Infantiles y Papillas": _build_schema(
        archetype="baby_and_maternity",
        ui_hint="Fórmulas lácteas infantiles (Etapa 1, 2, 3, Sin Lactosa, Confort, AR), cereales infantiles (arroz, trigo, multicereales), compotas y snacks de bebé.",
        buyer_ui_hint="Verifica la etapa recomendada (0-6m, 6-12m, +1 año) y el peso de la lata/empaque.",
        allowed_units=["unit", "pack", "box", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Etapa y Presentación en Gramos",
            "axes": [
                {"key": "stage", "label": "Etapa / Tipo", "type": "select", "presets": ["Etapa 1 (0 a 6 meses)", "Etapa 2 (6 a 12 meses)", "Etapa 3 (+1 año)", "Sin Lactosa / Soya", "Confort / Antirreflujo", "Manzana", "Pera", "Cambur", "Arroz"]},
                {"key": "weight", "label": "Contenido", "type": "select", "presets": ["113 g (Compota)", "225 g", "400 g", "800 g", "900 g", "1.1 kg"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": True, "placeholder": "Ej: NAN, Enfamil, Similac, Alula, Nestum, Cerelac, Gerber, Heinz", "section": "details"},
            {"key": "edad_recomendada", "label": "Edad / Etapa", "type": "text", "required": False, "placeholder": "Ej: Etapa 1 (0-6 meses) / +6 meses", "section": "specs"},
            {"key": "contenido_neto", "label": "Peso Neto", "type": "text", "required": False, "placeholder": "Ej: Lata 400 g / 800 g", "section": "specs"},
        ],
    ),
    "Coches, Portabebés y Sillas para Carro": _build_schema(
        archetype="baby_and_maternity",
        ui_hint="Coches de paseo, coches paraguas, sistemas Travel System (coche + portabebé), sillas de carro (car seats), fulares, canguros y pañaleras.",
        buyer_ui_hint="Elige el color y revisa el peso o edad máxima soportada.",
        allowed_units=["unit", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Color / Modelo",
            "axes": [
                {"key": "color", "label": "Color", "type": "text", "presets": ["Gris", "Negro", "Azul Marino", "Rosa", "Beige"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Graco, Chicco, Evenflo, Infanti, Baby Trend, Doona", "section": "details"},
            {"key": "peso_maximo_kg", "label": "Capacidad / Etapas", "type": "text", "required": False, "placeholder": "Ej: Recién nacido hasta 22 kg (Convertible 3 en 1)", "section": "specs"},
            {"key": "condicion", "label": "Condición", "type": "select", "required": False, "options": ["Nuevo en Caja", "Usado - Excelente estado"], "section": "condition"},
            _warranty_field(),
        ],
    ),
    "Cunas, Corrales y Moisés": _build_schema(
        archetype="baby_and_maternity",
        ui_hint="Corrales cuna plegables, cunas de madera, colechos, moisés, mecedoras vibradoras, sillas de comer y lencería de cuna.",
        buyer_ui_hint="Selecciona el color o diseño.",
        allowed_units=["unit", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Color / Diseño",
            "axes": [
                {"key": "color", "label": "Color", "type": "text", "presets": ["Gris", "Blanco", "Azul", "Rosa", "Beige", "Madera"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Graco, Ingenuity, Fisher-Price, Infanti, Ronbei", "section": "details"},
            {"key": "niveles_accesorios", "label": "Niveles / Qué incluye", "type": "text", "required": False, "placeholder": "Ej: 2 niveles, cambiador, mosquitero y móvil musical", "section": "specs"},
            {"key": "condicion", "label": "Condición", "type": "select", "required": False, "options": ["Nuevo", "Usado - Como nuevo"], "section": "condition"},
        ],
    ),
    "Bañeras, Champú y Jabones de Bebé": _build_schema(
        archetype="baby_and_maternity",
        ui_hint="Bañeras plegables o con paral, termómetros de baño, champú sin lágrimas, jabón líquido de glicerina/avena, colonias, talcos, aceites y cortaúñas de bebé.",
        buyer_ui_hint="Selecciona el tamaño o aroma.",
        allowed_units=["unit", "set", "pack", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tamaño / Aroma / Color",
            "axes": [
                {"key": "size_or_scent", "label": "Presentación / Aroma", "type": "text", "presets": ["100 ml", "200 ml", "400 ml", "750 ml", "Manzanilla", "Lavanda / Dulces Sueños", "Avena", "Original"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Johnson's Baby, Arrurú, Mustela, Chicco, Aveeno Baby, Mennen", "section": "details"},
            {"key": "contenido_neto", "label": "Contenido Neto", "type": "text", "required": False, "placeholder": "Ej: 400 ml", "section": "specs"},
        ],
    ),
    "Ropa de Bebé, Monillos y Bodies": _build_schema(
        archetype="apparel_fashion",
        ui_hint="Bodies, monillos, pijamas, sets de primera puesta (salida de clínica), baberos, medias, gorritos y escarpines (tallas Prematuro y RN hasta 24 meses).",
        buyer_ui_hint="Selecciona la talla por meses (RN a 24M) y el color o set.",
        allowed_units=["unit", "set", "pack", "pair", "combo"],
        default_unit="set",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Talla en Meses y Color",
            "axes": [
                {"key": "size", "label": "Talla (Meses)", "type": "select", "presets": VE_BABY_CLOTHING_SIZES},
                {"key": "color", "label": "Color / Set", "type": "text", "presets": ["Blanco", "Amarillo", "Azul Celeste", "Rosa Pastel", "Gris", "Beige", "Set Surtido Niña", "Set Surtido Niño", "Set Neutro"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Carter's, Gerber, Ovejita, EPK, Disney Baby", "section": "details"},
            {"key": "piezas_incluidas", "label": "Piezas del Set", "type": "text", "required": False, "placeholder": "Ej: Pack de 5 bodies / Set 4 piezas", "section": "specs"},
        ],
    ),
    "Monitores y Seguridad para Bebé": _build_schema(
        archetype="baby_and_maternity",
        ui_hint="Monitores de video/audio para bebé, rejas de seguridad para escaleras/puertas, protectores de enchufes/esquinas y seguros de gavetas.",
        buyer_ui_hint="Verifica las funciones o cantidad de piezas del paquete.",
        allowed_units=["unit", "pack", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Versión / Cantidad",
            "axes": [
                {"key": "version", "label": "Versión", "type": "text", "presets": ["Con Pantalla LCD", "Wi-Fi (App Celular)", "Solo Audio", "Pack x4", "Pack x10"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: VTech, Motorola, HelloBaby, Safety 1st, Munchkin", "section": "details"},
            _warranty_field(),
        ],
    ),

    # Alias legacy de Bebés y Maternidad
    "Pañales y Toallitas": _build_schema(
        archetype="baby_and_maternity",
        ui_hint="Pañales desechables y toallitas húmedas.",
        buyer_ui_hint="Selecciona la talla del bebé y el empaque.",
        allowed_units=["pack", "box", "unit", "combo"],
        default_unit="pack",
        supports_variants=True,
        variant_config={"enabled": True, "label": "Talla de Pañal", "axes": [{"key": "diaper_size", "label": "Talla", "type": "select", "presets": VE_DIAPER_SIZES}]},
    ),
    "Lactancia y Alimentación": _build_schema(
        archetype="baby_and_maternity",
        ui_hint="Fórmulas infantiles, teteros, chupones, extractores de leche y compotas.",
        buyer_ui_hint="Verifica la etapa/edad recomendada y contenido.",
        allowed_units=["unit", "pack", "combo"],
        default_unit="unit",
        supports_variants=True,
    ),
    "Paseo y Viaje": _build_schema(
        archetype="baby_and_maternity",
        ui_hint="Coches, sillas de carro, pañaleras y portabebés.",
        buyer_ui_hint="Elige el color y revisa el peso máximo soportado.",
        allowed_units=["unit", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
    ),
    "Higiene y Cuidado del Bebé": _build_schema(
        archetype="baby_and_maternity",
        ui_hint="Colonia de bebé, crema antipañalitis, shampoo sin lágrimas y bañeras.",
        buyer_ui_hint="Selecciona el tamaño o aroma.",
        allowed_units=["unit", "set", "pack", "combo"],
        default_unit="unit",
        supports_variants=True,
    ),
    "Cuarto del Bebé": _build_schema(
        archetype="baby_and_maternity",
        ui_hint="Cunas, corrales, mecedoras y monitores de bebé.",
        buyer_ui_hint="Selecciona el color o diseño.",
        allowed_units=["unit", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
    ),

    # --------------------------------------------------------------------------
    # 10. JUEGOS Y JUGUETES (8 Subcategorías Oficiales)
    # --------------------------------------------------------------------------
    "Muñecas, Barbies y Bebés": _build_schema(
        archetype="toys_and_games",
        ui_hint="Muñecas Barbie, bebés llorones/reborn, LOL Surprise, coches de muñeca, casas de muñecas y accesorios.",
        buyer_ui_hint="Selecciona el modelo o personaje.",
        allowed_units=["unit", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Modelo / Personaje",
            "axes": [
                {"key": "character", "label": "Modelo / Versión", "type": "text", "presets": ["Rubia", "Morena", "Sirena", "Princesa", "Con Accesorios"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca / Franquicia", "type": "text", "required": False, "placeholder": "Ej: Barbie (Mattel), Disney, LOL Surprise, Baby Alive, Cry Babies", "section": "details"},
            {"key": "edad_recomendada", "label": "Edad Recomendada", "type": "select", "required": False, "options": ["+18 meses", "+3 años", "+5 años", "+8 años"], "section": "specs"},
        ],
    ),
    "Peluches": _build_schema(
        archetype="toys_and_games",
        ui_hint="Peluches antialérgicos, osos gigantes, personajes (Stitch, Hello Kitty/Sanrio, Pokémon, Disney) y arreglos con peluche.",
        buyer_ui_hint="Selecciona el tamaño en cm o personaje.",
        allowed_units=["unit", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tamaño / Personaje / Color",
            "axes": [
                {"key": "size_or_char", "label": "Tamaño / Personaje", "type": "text", "presets": ["Pequeño (20 cm)", "Mediano (35 cm)", "Grande (50 cm)", "Jumbo (80 cm)", "Gigante (1 Metro+)", "Rosa", "Azul", "Marrón"]},
            ],
        },
        fields=[
            {"key": "personaje", "label": "Personaje / Temática", "type": "text", "required": False, "placeholder": "Ej: Stitch, Kuromi, Hello Kitty, Oso de Peluche, Capibara", "section": "details"},
            {"key": "tamano_cm", "label": "Altura Aproximada (cm)", "type": "text", "required": False, "placeholder": "Ej: 40 cm", "section": "specs"},
        ],
    ),
    "Figuras de Acción y Superhéroes": _build_schema(
        archetype="toys_and_games",
        ui_hint="Figuras articuladas (Marvel, DC, Dragon Ball, Anime), Funko Pop, carros a escala (Hot Wheels), carros a control remoto (RC), pistas y dinosaurios.",
        buyer_ui_hint="Elige el personaje o modelo disponible.",
        allowed_units=["unit", "set", "pack", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Personaje / Modelo",
            "axes": [
                {"key": "character", "label": "Personaje / Modelo", "type": "text", "presets": ["Spider-Man", "Batman", "Avengers", "Goku", "Naruto", "Edición Especial"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Hasbro, Mattel, Hot Wheels, Funko, Bandai, McFarlane, Marvel", "section": "details"},
            {"key": "franquicia", "label": "Franquicia / Serie", "type": "text", "required": False, "placeholder": "Ej: Marvel, Star Wars, Pokémon, Jurassic World, Hot Wheels", "section": "details"},
            {"key": "condicion", "label": "Condición", "type": "select", "required": False, "options": ["Nuevo en caja sellada", "Colección (Abierto)"], "section": "condition"},
        ],
    ),
    "Bloques, Legos y Armables": _build_schema(
        archetype="toys_and_games",
        ui_hint="Sets de LEGO originales, bloques armables compatibles, bloques magnéticos y rompecabezas 3D. Indica la cantidad de piezas.",
        buyer_ui_hint="Verifica la cantidad de piezas y edad recomendada.",
        allowed_units=["unit", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Modelo / Set",
            "axes": [
                {"key": "model", "label": "Modelo", "type": "text", "presets": ["Set Estándar", "Edición Coleccionista"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: LEGO, Mega Bloks, Sluban, Qman", "section": "details"},
            {"key": "cantidad_piezas", "label": "Cantidad de Piezas", "type": "number", "required": False, "placeholder": "Ej: 520", "section": "specs"},
            {"key": "edad_recomendada", "label": "Edad Recomendada", "type": "text", "required": False, "placeholder": "Ej: +6 años / +8 años", "section": "specs"},
        ],
    ),
    "Juegos de Mesa, Cartas y Dominó": _build_schema(
        archetype="toys_and_games",
        ui_hint="Juegos de dominó (doble 6, doble 9, profesional), mesas de dominó, ajedrez, Monopoly, UNO, cartas Pokémon/Yu-Gi-Oh!, ludo, bingo y rompecabezas.",
        buyer_ui_hint="Revisa el número de jugadores y versión del juego.",
        allowed_units=["unit", "set", "pack", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Versión / Edición",
            "axes": [
                {"key": "edition", "label": "Versión", "type": "text", "presets": ["Clásico", "Profesional Acrílico", "De Viaje / Magnético", "Sobre (Booster Pack)", "Caja / Estuche"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Hasbro, Mattel, Ronda, Spin Master, Bicycle, Pokémon TCG", "section": "details"},
            {"key": "jugadores", "label": "Cantidad de Jugadores / Piezas", "type": "text", "required": False, "placeholder": "Ej: 2 a 6 jugadores / 28 piedras", "section": "specs"},
        ],
    ),
    "Juguetes de Exterior, Patinetas y Triciclos": _build_schema(
        archetype="toys_and_games",
        ui_hint="Monopatines (scooters), patines en línea o de 4 ruedas (ajustables por talla), patinetas (skateboards), triciclos, carros eléctricos montables, lanzadores Nerf/hidrogel y pelotas.",
        buyer_ui_hint="Selecciona el color o rango de talla.",
        allowed_units=["unit", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Color / Talla Ajustable",
            "axes": [
                {"key": "color", "label": "Color", "type": "text", "presets": ["Azul", "Rosa", "Rojo", "Verde", "Negro", "Morado"]},
                {"key": "size", "label": "Talla (Patines / Rin)", "type": "text", "presets": ["Talla S (28-31)", "Talla M (32-35)", "Talla L (36-39)", "Talla Única"]},
            ],
        },
        fields=[
            {"key": "edad_peso", "label": "Edad / Peso Máximo", "type": "text", "required": False, "placeholder": "Ej: 3 a 8 años (Soporta hasta 40 kg)", "section": "specs"},
        ],
    ),
    "Juguetes de Piscina, Playa e Inflables": _build_schema(
        archetype="toys_and_games",
        ui_hint="Piscinas estructurales o inflables, salvavidas, flotadores, chalecos inflables, lentes de natación, pistolas de agua y sets de arena.",
        buyer_ui_hint="Revisa las medidas en cm o litros de capacidad.",
        allowed_units=["unit", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tamaño / Capacidad / Color",
            "axes": [
                {"key": "size", "label": "Medida / Color", "type": "text", "presets": ["Pequeña", "Mediana", "Familiar Grande", "Azul", "Rosa", "Amarillo"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Intex, Bestway, Speedo", "section": "details"},
            {"key": "dimensiones_litros", "label": "Dimensiones / Litros", "type": "text", "required": False, "placeholder": "Ej: 200 x 150 x 50 cm / 1.200 Litros", "section": "specs"},
        ],
    ),
    "Juguetes de Estimulación para Bebés": _build_schema(
        archetype="toys_and_games",
        ui_hint="Gimnasios de actividades, alfombras acolchadas (playmats), caminadoras/andaderas, sonajeros, mordedores y juguetes Montessori/didácticos.",
        buyer_ui_hint="Revisa la edad recomendada del bebé.",
        allowed_units=["unit", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Color / Diseño",
            "axes": [
                {"key": "color", "label": "Color / Diseño", "type": "text", "presets": ["Multicolor", "Azul", "Rosa", "Madera Montessori"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Fisher-Price, VTech, Baby Einstein, Melissa & Doug, Bright Starts", "section": "details"},
            {"key": "edad_recomendada", "label": "Edad Recomendada", "type": "select", "required": False, "options": ["0 a 6 meses", "6 a 12 meses", "1 a 3 años", "+3 años"], "section": "specs"},
        ],
    ),

    # Alias legacy de Juegos y Juguetes
    "Juguetes para Bebés": _build_schema(archetype="toys_and_games", ui_hint="Gimnasios, sonajeros y juguetes sensoriales.", buyer_ui_hint="Revisa la edad recomendada.", allowed_units=["unit", "set", "combo"], default_unit="unit", supports_variants=True),
    "Muñecas y Peluches": _build_schema(archetype="toys_and_games", ui_hint="Muñecas, peluches y casas de muñecas.", buyer_ui_hint="Selecciona el modelo o tamaño.", allowed_units=["unit", "set", "combo"], default_unit="unit", supports_variants=True),
    "Figuras de Acción": _build_schema(archetype="toys_and_games", ui_hint="Figuras coleccionables, Funko Pop y Hot Wheels.", buyer_ui_hint="Elige el personaje o modelo.", allowed_units=["unit", "set", "combo"], default_unit="unit", supports_variants=True),
    "Juegos de Mesa y Rompecabezas": _build_schema(archetype="toys_and_games", ui_hint="Juegos familiares, cartas, dominó y rompecabezas.", buyer_ui_hint="Revisa el número de jugadores.", allowed_units=["unit", "combo"], default_unit="unit", supports_variants=False),
    "Bloques y Construcción": _build_schema(archetype="toys_and_games", ui_hint="Sets de LEGO y bloques armables.", buyer_ui_hint="Verifica la cantidad de piezas.", allowed_units=["unit", "set", "combo"], default_unit="unit", supports_variants=False),
    "Juguetes de Exterior": _build_schema(archetype="toys_and_games", ui_hint="Monopatines, patines, triciclos e inflables.", buyer_ui_hint="Elige el color o talla.", allowed_units=["unit", "set", "combo"], default_unit="unit", supports_variants=True),

    # --------------------------------------------------------------------------
    # 11. MASCOTAS (9 Subcategorías Oficiales)
    # --------------------------------------------------------------------------
    "Perrarina y Comida para Perros": _build_schema(
        archetype="pets",
        ui_hint="Perrarina y alimento concentrado o húmedo para perros. Puedes vender por kilo detallado (granel), empaque sellado (1kg, 2kg, 4kg, 8kg) o saco completo (15kg, 18kg, 20kg).",
        buyer_ui_hint="Selecciona el peso (1 kg detal, empaque o saco) y la etapa (cachorro o adulto).",
        allowed_units=["kg", "g", "unit", "pack", "box", "combo"],
        default_unit="kg",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Presentación de Peso y Etapa",
            "axes": [
                {"key": "presentation", "label": "Peso / Empaque", "type": "select", "presets": ["1 kg (Detal / Granel)", "Empaque 1 kg", "Empaque 2 kg", "Empaque 4 kg", "Empaque 8 kg", "Empaque 10 kg", "Saco 15 kg", "Saco 18 kg", "Saco 20 kg", "Saco 25 kg", "Lata / Sobre Húmedo"]},
                {"key": "stage", "label": "Etapa / Raza", "type": "select", "presets": ["Cachorro (Puppy)", "Adulto Raza Pequeña", "Adulto Raza Mediana y Grande", "Senior"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": True, "placeholder": "Ej: Dog Chow, Dogourmet, Kantal, Protinal, Super Can, Pedigree, Pro Plan, Royal Canin", "section": "details"},
            {"key": "etapa_mascota", "label": "Etapa / Tamaño de Raza", "type": "select", "required": False, "options": ["Cachorro (Puppy)", "Adulto Raza Pequeña", "Adulto Raza Mediana / Grande", "Todas las Etapas", "Dieta Medicada / Renal / Hepática"], "section": "specs"},
            {"key": "sabor_proteina", "label": "Sabor / Proteína", "type": "text", "required": False, "placeholder": "Ej: Carne y Pollo, Cordero y Arroz, Salmón", "section": "specs"},
        ],
    ),
    "Gatarina y Comida para Gatos": _build_schema(
        archetype="pets",
        ui_hint="Gatarina y alimento seco o húmedo (sobres/latas) para gatos. Puedes vender por kilo detallado, paquete sellado o saco.",
        buyer_ui_hint="Selecciona el peso o sabor.",
        allowed_units=["kg", "g", "unit", "pack", "box", "combo"],
        default_unit="kg",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Presentación de Peso y Sabor",
            "axes": [
                {"key": "presentation", "label": "Peso / Empaque", "type": "select", "presets": ["500 g", "1 kg (Detal / Granel)", "Empaque 1 kg", "Empaque 1.5 kg", "Empaque 3 kg", "Saco 8 kg", "Saco 10 kg", "Saco 15 kg", "Sobre Húmedo (85g)", "Lata Paté"]},
                {"key": "flavor", "label": "Sabor / Etapa", "type": "text", "presets": ["Pescado / Salmón", "Carne", "Pollo", "Mariscos", "Gatitos (Kitten)", "Castrados / Indoor", "Control Bolas de Pelo"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": True, "placeholder": "Ej: Cat Chow, Gatsy, Mirringo, Félix, Whiskas, Oh Mai Gat, Royal Canin, Monello", "section": "details"},
            {"key": "etapa_gato", "label": "Etapa", "type": "select", "required": False, "options": ["Gatitos (Kitten)", "Adultos", "Esterilizados / Castrados / Urinary", "Todas las edades"], "section": "specs"},
        ],
    ),
    "Snacks, Galletas y Huesos para Mascotas": _build_schema(
        archetype="pets",
        ui_hint="Galletas caninas, huesos de carnaza, premios de entrenamiento, churu (snacks cremosos para gatos), dentastix y orejas deshidratadas.",
        buyer_ui_hint="Elige el sabor o tamaño del empaque.",
        allowed_units=["unit", "pack", "g", "kg", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Sabor / Tamaño",
            "axes": [
                {"key": "flavor_or_size", "label": "Sabor / Presentación", "type": "text", "presets": ["Pollo", "Carne / Tocineta", "Atún / Salmón", "Pequeño", "Mediano", "Grande", "Pack x4 Tubos"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Pedigree, Dog Chow, Inaba Churu, Félix, Kantal", "section": "details"},
            {"key": "especie", "label": "Para qué mascota", "type": "select", "required": False, "options": ["Perros", "Gatos", "Perros y Gatos"], "section": "details"},
        ],
    ),
    "Arena para Gatos y Areneras": _build_schema(
        archetype="pets",
        ui_hint="Arena sanitaria aglomerante, sílica o ecológica para gatos, cajas de arena (areneras abiertas o cerradas), palas recolectoras y rascadores.",
        buyer_ui_hint="Selecciona el peso en kg y el aroma de la arena.",
        allowed_units=["unit", "kg", "pack", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Peso (kg) y Aroma",
            "axes": [
                {"key": "weight", "label": "Peso / Tipo", "type": "select", "presets": ["2 kg", "4 kg", "4.5 kg", "5 kg", "9 kg", "10 kg", "20 kg", "Arenera con Pala"]},
                {"key": "scent", "label": "Aroma", "type": "select", "presets": ["Lavanda", "Limón / Cítrico", "Manzana", "Talco de Bebé", "Café", "Carbón Activado", "Sin Aroma (Neutra)"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Tidy Cats, Klump, Cat Litter, Sanicat, Michu", "section": "details"},
            {"key": "tipo_arena", "label": "Tipo", "type": "select", "required": False, "options": ["Arena Aglomerante (Bentonita)", "Cristales de Sílica", "Biodegradable (Maíz/Madera)", "Arenera / Caja Sanitaria / Pala"], "section": "specs"},
        ],
    ),
    "Antipulgas, Garrapaticidas y Desparasitantes": _build_schema(
        archetype="pets",
        ui_hint="Pastillas masticables antipulgas/garrapatas (Bravecto, NexGard, Simparica), pipetas (Frontline), collares antipulgas, desparasitantes internos y vitaminas veterinarias.",
        buyer_ui_hint="Selecciona el rango de peso exacto de tu mascota (ej. 2-4.5 kg, 4.5-10 kg, 10-20 kg, 20-40 kg).",
        allowed_units=["unit", "pack", "box", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Rango de Peso de la Mascota",
            "axes": [
                {"key": "pet_weight_range", "label": "Peso de la Mascota", "type": "select", "presets": ["2 a 4.5 kg (Mini)", "4.5 a 10 kg (Pequeño)", "10 a 20 kg (Mediano)", "20 a 40 kg (Grande)", "40 a 56 kg (Extra Grande)", "Gatos", "Uso General"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca / Laboratorio", "type": "text", "required": True, "placeholder": "Ej: Bravecto, NexGard, Simparica, Frontline, Drontal, Endogard, Asuntol", "section": "details"},
            {"key": "especie", "label": "Especie", "type": "select", "required": False, "options": ["Perros", "Gatos", "Perros y Gatos"], "section": "specs"},
            {"key": "via_administracion", "label": "Formato", "type": "select", "required": False, "options": ["Tableta Masticable", "Pipeta (Spot-On)", "Collar Antipulgas", "Suspensión Oral / Gotas", "Spray / Baño Medicado"], "section": "specs"},
        ],
    ),
    "Champú, Cepillos y Estética Canina": _build_schema(
        archetype="pets",
        ui_hint="Champú cosmético o medicado (clorhexidina, amitraz, avena), colonias para mascotas, cepillos quitapelos (Furminator), cortaúñas, máquinas de afeitar y pañales/centros de entrenamiento.",
        buyer_ui_hint="Elige el tamaño o presentación.",
        allowed_units=["unit", "pack", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tamaño / Tipo",
            "axes": [
                {"key": "variant", "label": "Presentación", "type": "text", "presets": ["250 ml", "500 ml", "Galón (3.78L)", "Cachorro", "Pelo Blanco", "Antipulgas / Medicado"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Bravo, Kantal, Dr. Pet, Wahl, Furminator", "section": "details"},
        ],
    ),
    "Camas, Casas y Transportadoras": _build_schema(
        archetype="pets",
        ui_hint="Camas acolchadas/lavables para perros y gatos, casas plásticas, kennels (transportadoras rígidas o bolsos de viaje), jaulas y rascadores tipo torre.",
        buyer_ui_hint="Selecciona la talla (S, M, L, XL) y el color.",
        allowed_units=["unit", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Talla y Color",
            "axes": [
                {"key": "size", "label": "Talla / Tamaño", "type": "select", "presets": ["Talla XS (Mini)", "Talla S (Pequeña)", "Talla M (Mediana)", "Talla L (Grande)", "Talla XL (Raza Grande)"]},
                {"key": "color", "label": "Color", "type": "text", "presets": ["Gris", "Azul", "Negro", "Rosa", "Beige", "Marrón"]},
            ],
        },
        fields=[
            {"key": "dimensiones", "label": "Medidas (Largo x Ancho x Alto)", "type": "text", "required": False, "placeholder": "Ej: 60 x 50 cm", "section": "specs"},
        ],
    ),
    "Paseo, Collares, Pecheras y Correas": _build_schema(
        archetype="pets",
        ui_hint="Pecheras (arneses) antitirón, collares, placas de identificación, correas retráctiles o fijas, bozales, comederos, bebederos, ropa para perros y juguetes (Kong, pelotas).",
        buyer_ui_hint="Selecciona la talla (XS, S, M, L, XL) y el color.",
        allowed_units=["unit", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Talla y Color",
            "axes": [
                {"key": "size", "label": "Talla", "type": "select", "presets": ["XS", "S", "M", "L", "XL"]},
                {"key": "color", "label": "Color", "type": "text", "presets": ["Rojo", "Negro", "Azul", "Rosa", "Verde", "Naranja", "Camuflado"]},
            ],
        },
        fields=[
            {"key": "tipo_accesorio", "label": "Tipo de Accesorio", "type": "select", "required": False, "options": ["Pechera / Arnés", "Collar / Correa / Traílla", "Comedero / Bebedero / Fuente", "Ropa / Impermeable para Mascota", "Juguete / Mordedor"], "section": "details"},
        ],
    ),
    "Aves, Peces y Otras Mascotas": _build_schema(
        archetype="pets",
        ui_hint="Alpiste, girasol, mijo, alimentos en escamas/pellets para peces y tortugas, jaulas, peceras, filtros de acuario, bombas de oxígeno y viruta para hámsters/conejos.",
        buyer_ui_hint="Selecciona el peso o presentación.",
        allowed_units=["kg", "g", "unit", "pack", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Presentación / Peso",
            "axes": [
                {"key": "presentation", "label": "Presentación", "type": "text", "presets": ["250 g", "500 g", "1 kg", "Saco", "Unidad"]},
            ],
        },
        fields=[
            {"key": "especie", "label": "Para qué animal", "type": "select", "required": False, "options": ["Aves / Pájaros / Loros", "Peces / Acuariofilia", "Tortugas / Reptiles", "Hámsters / Conejos / Cobayos", "Caballos / Granja"], "section": "details"},
        ],
    ),

    # Alias legacy de Mascotas
    "Perros": _build_schema(archetype="pets", ui_hint="Perrarina, snacks, collares, camas y juguetes para perros.", buyer_ui_hint="Elige el peso en kg o la talla.", allowed_units=["kg", "g", "unit", "pack", "box", "combo"], default_unit="unit", supports_variants=True),
    "Gatos": _build_schema(archetype="pets", ui_hint="Gatarina, arena sanitaria, rascadores y accesorios para gatos.", buyer_ui_hint="Selecciona el peso o presentación deseada.", allowed_units=["kg", "g", "unit", "pack", "combo"], default_unit="unit", supports_variants=True),
    "Higiene y Salud Animal": _build_schema(archetype="pets", ui_hint="Antipulgas, garrapaticidas, desparasitantes y champú.", buyer_ui_hint="Selecciona el rango de peso de tu mascota.", allowed_units=["unit", "pack", "combo"], default_unit="unit", supports_variants=True),

    # --------------------------------------------------------------------------
    # 12. PAPELERÍA, OFICINA Y LIBROS (9 Subcategorías Oficiales)
    # --------------------------------------------------------------------------
    "Cuadernos, Libretas y Blocks": _build_schema(
        archetype="books_and_stationery",
        ui_hint="Cuadernos cosidos o espiral (una línea, doble línea, cuadriculado, pentagramado), libretas universitarias (1, 3, 6 materias), agendas y blocks de dibujo/construcción.",
        buyer_ui_hint="Selecciona el tipo de rayado, diseño o paquete.",
        allowed_units=["unit", "pack", "dozen", "box", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Rayado / Diseño / Cantidad",
            "axes": [
                {"key": "ruling", "label": "Tipo de Línea / Hojas", "type": "select", "presets": ["Una Línea", "Doble Línea", "Cuadriculado Grande", "Cuadriculado Pequeño", "100 Hojas (200 págs)", "1 Materia", "6 Materias"]},
                {"key": "design_or_pack", "label": "Motivo / Empaque", "type": "text", "presets": ["Unicolor", "Niño / Deportivo", "Niña / Fantasía", "Unidad", "Media Docena (6 und)", "Docena (12 und)"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Norma, Caribe, Alpes, Scribe, Primavera", "section": "details"},
            {"key": "encuadernacion", "label": "Encuadernación", "type": "select", "required": False, "options": ["Cosido Escolar", "Espiral / Doble Anillo (Ring)", "Engrapado", "Tapa Dura / Agenda", "Block Desprendible"], "section": "specs"},
        ],
    ),
    "Lápices, Colores, Bolígrafos y Marcadores": _build_schema(
        archetype="books_and_stationery",
        ui_hint="Cajas de lápices de grafito (Mongol), creyones/colores de madera, marcadores escolares/permanentes/acrílicos/pizarra, bolígrafos, resaltadores, borradores y sacapuntas.",
        buyer_ui_hint="Selecciona la cantidad de colores/unidades o color de tinta.",
        allowed_units=["unit", "box", "pack", "dozen", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Presentación / Color de Tinta",
            "axes": [
                {"key": "presentation", "label": "Cantidad / Caja", "type": "select", "presets": ["Unidad", "Caja x12 Colores", "Caja x24 Colores", "Caja x36 Colores", "Caja x48 Colores", "Caja x12 Unidades (Docena)", "Blíster x3", "Blíster x4"]},
                {"key": "ink_color", "label": "Color / Punta", "type": "text", "presets": ["Surtido", "Negro", "Azul", "Rojo", "Punta Fina", "Punta Gruesa / Biselada"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Mongol, Prismacolor, Faber-Castell, Kores, Solita, Norma, Paper Mate, Sharpie, Pilot", "section": "details"},
        ],
    ),
    "Resmas de Hojas, Cartulinas y Papelería": _build_schema(
        archetype="books_and_stationery",
        ui_hint="Resmas de papel bond blanco (Carta y Oficio), medio resma, cartulinas escolares/opalina/hilo, papel crepé, papel seda, papel lustrillo, papel contact y etiquetas.",
        buyer_ui_hint="Selecciona el tamaño (Carta u Oficio), color o formato (pliego, resma, bulto).",
        allowed_units=["unit", "pack", "box", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tamaño / Formato / Color",
            "axes": [
                {"key": "size", "label": "Tamaño / Presentación", "type": "select", "presets": ["Tamaño Carta (500 hojas)", "Tamaño Oficio (500 hojas)", "Media Resma (250 hojas)", "Paquete x100 Hojas", "Bulto (10 Resmas)", "Pliego", "Carta"]},
                {"key": "color", "label": "Color", "type": "text", "presets": ["Blanco", "Surtido", "Azul", "Amarillo", "Verde", "Rojo", "Negro", "Transparente"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Alpes, HP, Reprograf, Chamex, Report, Kores", "section": "details"},
            {"key": "gramaje_base", "label": "Gramaje / Base", "type": "text", "required": False, "placeholder": "Ej: Base 20 (75 g/m²) / Opalina 180g", "section": "specs"},
        ],
    ),
    "Morrales Escolares y Cartucheras": _build_schema(
        archetype="books_and_stationery",
        ui_hint="Morrales escolares (de espalda o con ruedas), loncheras térmicas, cartucheras de 1, 2 o 3 cierres y combos escolares (Morral + Lonchera + Cartuchera).",
        buyer_ui_hint="Elige el diseño, personaje o color.",
        allowed_units=["unit", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Diseño / Personaje / Color",
            "axes": [
                {"key": "design", "label": "Diseño / Color", "type": "text", "presets": ["Negro", "Azul", "Rosa", "Morado", "Con Ruedas", "De Espalda", "Combo 3 Piezas (Morral+Lonchera+Cartuchera)"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Totto, RS21, Chenson, Kipling, Disney, Marvel", "section": "details"},
            {"key": "piezas", "label": "Qué incluye", "type": "select", "required": False, "options": ["Solo Morral", "Solo Cartuchera", "Solo Lonchera", "Combo 3 en 1 (Morral + Lonchera + Cartuchera)"], "section": "specs"},
        ],
    ),
    "Material de Manualidades, Foami y Pinturas": _build_schema(
        archetype="books_and_stationery",
        ui_hint="Láminas de foami (liso o escarchado), pinturas al frío, témperas, acuarelas, pinceles, plastilina, masa flexible, silicón líquido/en barra, pistola de silicón y pega blanca/en barra.",
        buyer_ui_hint="Selecciona el color o tamaño del envase.",
        allowed_units=["unit", "pack", "dozen", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Color / Tamaño",
            "axes": [
                {"key": "color_or_size", "label": "Color / Presentación", "type": "text", "presets": VE_COMMON_COLORS + ["Escarchado", "Surtido", "30 ml", "60 ml", "125 ml", "250 ml", "Barra Fina", "Barra Gruesa"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Orocolor, Kores, Solita, Elefante, Pinto, Pelikan", "section": "details"},
        ],
    ),
    "Carpetas, Archivadores y Sobres": _build_schema(
        archetype="books_and_stationery",
        ui_hint="Carpetas manila, carpetas marrones con gancho (Carta/Oficio), carpetas plásticas con liga, archivadores lomo ancho (Oslo), fundas transparentes y sobres.",
        buyer_ui_hint="Selecciona el tamaño (Carta u Oficio) y si se vende por unidad o caja.",
        allowed_units=["unit", "pack", "dozen", "box", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tamaño y Empaque",
            "axes": [
                {"key": "size", "label": "Tamaño", "type": "select", "presets": ["Tamaño Carta", "Tamaño Oficio", "Extra Oficio", "Medio Oficio"]},
                {"key": "pack", "label": "Cantidad", "type": "select", "presets": ["Unidad", "Paquete x10", "Paquete x25", "Caja x50", "Caja x100"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Oslo, Ofimak, Caribe, Norma", "section": "details"},
        ],
    ),
    "Calculadoras, Grapadoras y Tijeras": _build_schema(
        archetype="books_and_stationery",
        ui_hint="Calculadoras científicas, sumadoras o de escritorio, grapadoras, cajas de grapas (26/6), saca grapas, perforadoras, tijeras escolares/oficina, exactos (cúter) y teipe transparente/embalaje.",
        buyer_ui_hint="Elige el modelo o presentación.",
        allowed_units=["unit", "box", "pack", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Modelo / Presentación",
            "axes": [
                {"key": "model", "label": "Modelo / Medida", "type": "text", "presets": ["Estándar", "Científica", "Escritorio 12 Dígitos", "Punta Roma (Escolar)", "Oficina Grande"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Casio, Ofimak, Kores, 3M Scotch, Celoven, Barrilito", "section": "details"},
        ],
    ),
    "Sillas de Oficina y Escritorios": _build_schema(
        archetype="furniture_and_decor",
        ui_hint="Sillas ejecutivas, secretarias, ergonómicas de malla o gamer, escritorios de oficina, mesas de computadora, archivos metálicos/melamina y pizarras acrílicas/de corcho.",
        buyer_ui_hint="Selecciona el color o medida.",
        allowed_units=["unit", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Color / Medida",
            "axes": [
                {"key": "color_or_size", "label": "Color / Medida", "type": "text", "presets": ["Negro", "Gris", "Blanco", "Madera / Wengué", "60 x 40 cm", "90 x 60 cm", "120 x 80 cm"]},
            ],
        },
        fields=[
            {"key": "material", "label": "Material", "type": "text", "required": False, "placeholder": "Ej: Malla transpirable, Cuero sintético, Melamina 18mm", "section": "specs"},
            {"key": "dimensiones", "label": "Dimensiones", "type": "text", "required": False, "placeholder": "Ej: 120 x 60 x 75 cm", "section": "specs"},
            _warranty_field(),
        ],
    ),
    "Libros Escolares, Novelas y Literatura": _build_schema(
        archetype="books_and_stationery",
        ui_hint="Textos escolares (Nacho, Girasol, Santillana, enciclopedias, diccionarios), novelas, desarrollo personal, finanzas, Biblias, mangas y cómics.",
        buyer_ui_hint="Revisa el autor, grado escolar, editorial y estado del ejemplar.",
        allowed_units=["unit", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Grado / Edición / Tapa",
            "axes": [
                {"key": "edition_or_grade", "label": "Grado / Encuadernación", "type": "text", "presets": ["Tapa Blanda", "Tapa Dura", "1er Grado", "2do Grado", "3er Grado", "4to Grado", "5to Grado", "6to Grado", "1er Año", "2do Año", "3er Año", "4to Año", "5to Año"]},
            ],
        },
        fields=[
            {"key": "autor_editorial", "label": "Autor / Editorial", "type": "text", "required": True, "placeholder": "Ej: Editorial Girasol / Santillana / Nacho / Planeta / Penguin", "section": "details"},
            {"key": "genero_categoria", "label": "Categoría del Libro", "type": "select", "required": False, "options": ["Texto Escolar / Diccionario", "Novela / Literatura / Ficción", "Desarrollo Personal / Finanzas / Negocios", "Infantil / Cuentos / Colorear", "Religión / Espiritualidad", "Manga / Cómic", "Universitario / Técnico"], "section": "details"},
            {"key": "idioma", "label": "Idioma", "type": "select", "required": False, "options": ["Español", "Inglés", "Bilingüe"], "section": "specs"},
            {"key": "condicion", "label": "Condición", "type": "select", "required": False, "options": ["Nuevo", "Usado - Buen estado"], "section": "condition"},
        ],
    ),

    # Alias legacy de Papelería, Oficina y Libros
    "Útiles Escolares": _build_schema(archetype="books_and_stationery", ui_hint="Cuadernos, lápices, colores, marcadores y morrales.", buyer_ui_hint="Selecciona el color o presentación.", allowed_units=["unit", "pack", "box", "set", "combo"], default_unit="unit", supports_variants=True),
    "Oficina": _build_schema(archetype="books_and_stationery", ui_hint="Resmas de papel, carpetas, calculadoras y sillas.", buyer_ui_hint="Elige el tamaño o modelo.", allowed_units=["unit", "pack", "box", "combo"], default_unit="unit", supports_variants=True),
    "Libros": _build_schema(archetype="books_and_stationery", ui_hint="Libros de lectura, textos escolares y novelas.", buyer_ui_hint="Revisa el autor y estado.", allowed_units=["unit", "set", "combo"], default_unit="unit", supports_variants=True, fields=[{"key": "autor", "label": "Autor", "type": "text", "required": True, "section": "details"}]),

    # --------------------------------------------------------------------------
    # 13. INSTRUMENTOS MUSICALES (11 Subcategorías Oficiales)
    # --------------------------------------------------------------------------
    "Cuatros Venezolanos, Maracas y Furrucos": _build_schema(
        archetype="musical_instruments",
        ui_hint="Cuatros venezolanos (estándar 14 trastes, concierto 17 trastes, electroacústicos), maracas llaneras/gaiteras, furrucos, tamboras gaiteras y charrascas.",
        buyer_ui_hint="Selecciona el tipo de instrumento, número de trastes o madera.",
        allowed_units=["unit", "pair", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Versión / Trastes / Incluye Forro",
            "axes": [
                {"key": "version", "label": "Tipo / Trastes", "type": "select", "presets": ["Estándar (14 Trastes)", "Concierto (17 Trastes)", "Electroacústico", "Con Forro Incluido", "Par de Maracas"]},
            ],
        },
        fields=[
            {"key": "luthier_marca", "label": "Luthier / Fabricante", "type": "text", "required": False, "placeholder": "Ej: Luthier de Lara (Carora/Barquisimeto), Nacional, Profesional", "section": "details"},
            {"key": "madera_material", "label": "Madera / Material", "type": "text", "required": False, "placeholder": "Ej: Cedro, Caoba, Pino, Tapara seleccionada", "section": "specs"},
            {"key": "incluye_forro", "label": "Incluye Forro / Estuche", "type": "boolean", "required": False, "section": "specs"},
        ],
    ),
    "Guitarras y Bajos": _build_schema(
        archetype="musical_instruments",
        ui_hint="Guitarras clásicas (cuerdas de nylon), acústicas (cuerdas de metal), electroacústicas, eléctricas y bajos eléctricos de 4 y 5 cuerdas.",
        buyer_ui_hint="Elige el color o acabado disponible.",
        allowed_units=["unit", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Color / Acabado",
            "axes": [
                {"key": "color", "label": "Color / Acabado", "type": "text", "presets": ["Natural", "Sunburst", "Negro", "Blanco", "Rojo", "Azul"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": True, "placeholder": "Ej:Yamaha, Fender, Squier, Ibanez, Epiphone, Gibson, Cort, Valencian", "section": "details"},
            {"key": "tipo_instrumento", "label": "Tipo", "type": "select", "required": False, "options": ["Guitarra Clásica (Nylon)", "Guitarra Acústica / Electroacústica", "Guitarra Eléctrica", "Bajo Eléctrico (4 cuerdas)", "Bajo Eléctrico (5 cuerdas)", "Combo Guitarra + Amplificador"], "section": "specs"},
            {"key": "condicion", "label": "Condición", "type": "select", "required": True, "options": ["Nuevo", "Usado"], "section": "condition"},
            _warranty_field(),
        ],
    ),
    "Instrumentos de Cuerda": _build_schema(
        archetype="musical_instruments",
        ui_hint="Violines (4/4, 3/4, 1/2, 1/4), ukeleles (soprano, concierto, tenor), mandolinas, bandolas llaneras, arpas y violonchelos.",
        buyer_ui_hint="Selecciona la medida (ej. Violín 4/4 o Ukelele Concierto) y color.",
        allowed_units=["unit", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Medida / Tamaño",
            "axes": [
                {"key": "size", "label": "Medida", "type": "select", "presets": ["4/4 (Adulto)", "3/4", "1/2", "1/4", "Ukelele Soprano", "Ukelele Concierto", "Ukelele Tenor"]},
            ],
        },
        fields=[
            {"key": "instrumento", "label": "Instrumento", "type": "select", "required": False, "options": ["Violín", "Ukelele", "Mandolina / Bandola", "Violonchelo (Cello)", "Viola", "Arpa"], "section": "details"},
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Cremona, Stentor, Kala, Mahalo, Yamaha", "section": "details"},
            {"key": "incluye_estuche", "label": "Incluye Estuche y Arco", "type": "boolean", "required": False, "section": "specs"},
        ],
    ),
    "Amplificadores": _build_schema(
        archetype="musical_instruments",
        ui_hint="Amplificadores para guitarra eléctrica, electroacústica, bajo o teclado, cabezales y gabinetes. Especifica la potencia en Watts.",
        buyer_ui_hint="Revisa la potencia en Watts y el instrumento compatible.",
        allowed_units=["unit", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Potencia (Watts)",
            "axes": [
                {"key": "wattage", "label": "Potencia", "type": "select", "presets": ["10W", "15W", "20W", "25W", "40W", "50W", "100W"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": True, "placeholder": "Ej: Fender, Marshall, Boss, Orange, Laney, Peavey, Ampeg, Blackstar", "section": "details"},
            {"key": "instrumento_uso", "label": "Para qué instrumento", "type": "select", "required": False, "options": ["Guitarra Eléctrica", "Bajo Eléctrico", "Guitarra Acústica / Voz", "Teclado / Multipropósito"], "section": "specs"},
            {"key": "potencia_watts", "label": "Potencia (Watts)", "type": "text", "required": False, "placeholder": "Ej: 25W / 50W", "section": "specs"},
            {"key": "condicion", "label": "Condición", "type": "select", "required": True, "options": ["Nuevo", "Usado"], "section": "condition"},
            _warranty_field(),
        ],
    ),
    "Teclados, Sintetizadores y Pianos Eléctricos": _build_schema(
        archetype="musical_instruments",
        ui_hint="Teclados órgano, pianos digitales de 88 teclas pesadas, sintetizadores, controladores MIDI y acordeones.",
        buyer_ui_hint="Verifica la cantidad de teclas (61, 76, 88) y si incluye base o pedal.",
        allowed_units=["unit", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Cantidad de Teclas / Combo",
            "axes": [
                {"key": "keys_or_bundle", "label": "Versión", "type": "select", "presets": ["61 Teclas (5 Octavas)", "88 Teclas Pesadas", "25 Teclas MIDI", "49 Teclas MIDI", "Solo Teclado", "Combo con Paral/Base"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": True, "placeholder": "Ej: Yamaha, Casio, Roland, Korg, Arturia, M-Audio, Nord", "section": "details"},
            {"key": "modelo", "label": "Modelo", "type": "text", "required": False, "placeholder": "Ej: PSR-E373 / Casio CT-S300 / FP-30X", "section": "details"},
            {"key": "condicion", "label": "Condición", "type": "select", "required": True, "options": ["Nuevo", "Usado"], "section": "condition"},
            _warranty_field(),
        ],
    ),
    "Baterías y Percusión": _build_schema(
        archetype="musical_instruments",
        ui_hint="Baterías acústicas y electrónicas, redoblantes (tarolas), sets de platillos (Hi-Hat, Crash, Ride), pedales de bombo, parches y baquetas.",
        buyer_ui_hint="Revisa las piezas incluidas o medida en pulgadas.",
        allowed_units=["unit", "set", "pair", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Medida / Color",
            "axes": [
                {"key": "size_color", "label": "Medida / Color", "type": "text", "presets": ["14\"", "16\"", "18\"", "20\"", "22\"", "Negro", "Rojo Vino", "Azul"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Pearl, Tama, Mapex, Ludwig, Zildjian, Sabian, Meinl, Remo, Evans, Alesis", "section": "details"},
            {"key": "condicion", "label": "Condición", "type": "select", "required": False, "options": ["Nuevo", "Usado"], "section": "condition"},
        ],
    ),
    "Percusión Latina, Congas, Timbales y Bongós": _build_schema(
        archetype="musical_instruments",
        ui_hint="Tumbadoras (congas, quinto, tumba), timbales (pailas), bongós, güiros, campanas (cencerros), jam blocks, cajón peruano y percusión afrovenezolana.",
        buyer_ui_hint="Verifica las medidas en pulgadas y si incluye paral/soporte.",
        allowed_units=["unit", "pair", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Medida / Acabado",
            "axes": [
                {"key": "size", "label": "Medida / Set", "type": "text", "presets": ["11\" y 12\" (Par)", "14\" y 15\"", "Madera Natural", "Rojo", "Cromado", "Dorado"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: LP (Latin Percussion), Meinl, Toca, Tycoon, Matador", "section": "details"},
            {"key": "incluye_paral", "label": "Incluye Paral / Soporte", "type": "boolean", "required": False, "section": "specs"},
        ],
    ),
    "Instrumentos de Viento, Flautas y Saxofones": _build_schema(
        archetype="musical_instruments",
        ui_hint="Flautas dulces (escolares Yamaha/Hohner), flautas transversas, saxofones (alto, tenor), trompetas, trombones, clarinetes y armónicas.",
        buyer_ui_hint="Verifica la afinación y si incluye estuche.",
        allowed_units=["unit", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tono / Afinación / Color",
            "axes": [
                {"key": "key_or_color", "label": "Afinación / Modelo", "type": "text", "presets": ["Soprano (Escolar)", "Alto (Eb)", "Tenor (Bb)", "Do (C)", "Dorado Laqueado", "Plateado"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Yamaha, Hohner, Selmer, Jupiter, Mendini", "section": "details"},
            {"key": "condicion", "label": "Condición", "type": "select", "required": False, "options": ["Nuevo", "Usado"], "section": "condition"},
        ],
    ),
    "Micrófonos, Consolas y Sonido en Vivo": _build_schema(
        archetype="musical_instruments",
        ui_hint="Micrófonos vocales o de estudio (alámbricos XLR, inalámbricos, USB), interfaces de audio, consolas mezcladoras (mixers), cornetas amplificadas (cabinas 12\"/15\") y parales.",
        buyer_ui_hint="Revisa los canales, potencia y tipo de conexión.",
        allowed_units=["unit", "pair", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Canales / Versión / Pulgadas",
            "axes": [
                {"key": "version", "label": "Versión", "type": "text", "presets": ["Alámbrico XLR", "Inalámbrico Doble", "4 Canales", "8 Canales", "12 Canales", "Cabina 12\"", "Cabina 15\""]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": True, "placeholder": "Ej: Shure, Sennheiser, Audio-Technica, Behringer, Focusrite, Mackie, JBL, Electro-Voice, FBT", "section": "details"},
            {"key": "modelo", "label": "Modelo", "type": "text", "required": False, "placeholder": "Ej: SM58 / Scarlett 2i2 / Xenyx", "section": "details"},
            _warranty_field(),
        ],
    ),
    "Equipos para DJ y Audífonos de Monitoreo": _build_schema(
        archetype="musical_instruments",
        ui_hint="Controladores DJ (Pioneer DJ, Numark, Denon), reproductores CDJ, mezcladores DJ, audífonos de estudio/monitoreo, in-ears (KZ, Shure) y luces de discoteca/humo.",
        buyer_ui_hint="Revisa la compatibilidad de software (Rekordbox, Serato, VirtualDJ) y conectores.",
        allowed_units=["unit", "pair", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Color / Versión",
            "axes": [
                {"key": "color", "label": "Color / Versión", "type": "text", "presets": ["Negro", "Transparente", "Con Micrófono", "Sin Micrófono"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": True, "placeholder": "Ej: Pioneer DJ, AlphaTheta, Numark, Denon, Audio-Technica, KZ, Sennheiser", "section": "details"},
            {"key": "condicion", "label": "Condición", "type": "select", "required": False, "options": ["Nuevo", "Usado"], "section": "condition"},
            _warranty_field(),
        ],
    ),
    "Cuerdas, Fundas, Afinadores y Pedales": _build_schema(
        archetype="musical_instruments",
        ui_hint="Juegos de cuerdas (guitarra clásica, acústica, eléctrica, bajo, cuatro, violín), pedales de efectos, pedaleras multiefectos, afinadores, capotrastes, cables plug/XLR, púas, correas, atriles y forros.",
        buyer_ui_hint="Selecciona el calibre (.009, .010, tensión normal/alta) o medida.",
        allowed_units=["unit", "set", "pack", "pair", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Calibre / Medida",
            "axes": [
                {"key": "gauge", "label": "Calibre / Medida", "type": "select", "presets": ["Calibre .009", "Calibre .010", "Calibre .011", "Nylon Tensión Normal", "Nylon Tensión Alta", "Cuatro Venezolano", "Violín 4/4", "Baquetas 5A", "Baquetas 5B", "Cable 3m", "Cable 6m"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: D'Addario, Ernie Ball, Elixir, Augustine, Boss, Nux, Vic Firth", "section": "details"},
        ],
    ),

    # Alias legacy de Instrumentos Musicales
    "Teclados y Pianos": _build_schema(archetype="musical_instruments", ui_hint="Teclados musicales, pianos digitales y sintetizadores.", buyer_ui_hint="Verifica la cantidad de teclas.", allowed_units=["unit", "set", "combo"], default_unit="unit", supports_variants=False, fields=[{"key": "marca", "label": "Marca", "type": "text", "required": True, "section": "details"}]),
    "Instrumentos de Viento": _build_schema(archetype="musical_instruments", ui_hint="Flautas, saxofones, trompetas y clarinetes.", buyer_ui_hint="Verifica la afinación.", allowed_units=["unit", "combo"], default_unit="unit", supports_variants=False),
    "Audio Profesional y DJ": _build_schema(archetype="musical_instruments", ui_hint="Interfaces de audio, micrófonos, consolas y controladores DJ.", buyer_ui_hint="Revisa la potencia y conectores.", allowed_units=["unit", "pair", "set", "combo"], default_unit="unit", supports_variants=False, fields=[{"key": "marca", "label": "Marca", "type": "text", "required": True, "section": "details"}]),
    "Accesorios Musicales": _build_schema(archetype="musical_instruments", ui_hint="Encordados, cables, atriles, capotrastes, púas y forros.", buyer_ui_hint="Selecciona el calibre o medida.", allowed_units=["unit", "set", "pack", "pair", "combo"], default_unit="unit", supports_variants=True),

    # --------------------------------------------------------------------------
    # 14. FIESTAS Y PIÑATERÍA (5 Subcategorías Oficiales)
    # --------------------------------------------------------------------------
    "Piñatas, Cotillones y Globos": _build_schema(
        archetype="general",
        ui_hint="Piñatas (entamboradas o plegables), paquetes de globos (látex R9/R12, metalizados de números/personajes), cortinas metalizadas, velas de cumpleaños, toppers, juguetes de relleno para piñata y bolsas de cotillón.",
        buyer_ui_hint="Selecciona el número, color, personaje o tamaño del paquete.",
        allowed_units=["unit", "pack", "dozen", "box", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Color / Número / Personaje / Paquete",
            "axes": [
                {"key": "color_or_number", "label": "Color / Número / Motivo", "type": "text", "presets": ["Dorado", "Plateado", "Rosa Gold", "Rojo", "Azul", "Rosa", "Surtido", "Número 0", "Número 1", "Número 2", "Número 3", "Número 4", "Número 5", "Número 6", "Número 7", "Número 8", "Número 9"]},
                {"key": "pack_size", "label": "Presentación", "type": "select", "presets": ["Unidad", "Paquete x12", "Paquete x25", "Paquete x50", "Paquete x100", "Combo Fiesta Completo"]},
            ],
        },
        order_notes_enabled=True,
        order_notes_placeholder="Ej: Indicar número de vela/globo, personaje o colores del combo...",
        fields=[
            {"key": "marca_motivo", "label": "Marca / Personaje / Temática", "type": "text", "required": False, "placeholder": "Ej: Sempertex, Payaso, Cumpleaños, Bautizo, Graduación", "section": "details"},
            {"key": "medida_unidades", "label": "Medida / Unidades por Paquete", "type": "text", "required": False, "placeholder": "Ej: Globos R12 (Paquete de 50 unidades)", "section": "specs"},
        ],
    ),
    "Descartables, Vasos, Platos y Servilletas": _build_schema(
        archetype="general",
        ui_hint="Vasos plásticos o de cartón (por oz), platos descartables para torta/comida, cubiertos plásticos, servilletas, pitillos, envases de anime/plástico con tapa (contenedores de comida) y aluminio/envoplast.",
        buyer_ui_hint="Selecciona la medida en onzas (oz) o número de plato y si se vende por paquete o bulto.",
        allowed_units=["pack", "box", "unit", "dozen", "combo"],
        default_unit="pack",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Capacidad (oz) / Medida y Empaque",
            "axes": [
                {"key": "size_oz", "label": "Capacidad / Medida", "type": "select", "presets": ["Vaso #2 (Café)", "Vaso #5", "Vaso #7", "Vaso 9 oz", "Vaso 12 oz", "Vaso 16 oz", "Plato #6 (Torta)", "Plato #8", "Plato #9", "Envase Almuerzo / Chino"]},
                {"key": "pack_qty", "label": "Empaque", "type": "select", "presets": ["Paquete x20", "Paquete x25", "Paquete x50", "Paquete x100", "Tira / Tubo", "Caja / Bulto"]},
            ],
        },
        fields=[
            {"key": "material", "label": "Material", "type": "select", "required": False, "options": ["Plástico Transparente / Blanco", "Anime (Poliestireno)", "Cartón / Biodegradable", "Papel (Servilletas)", "Aluminio / Envoplast"], "section": "specs"},
        ],
    ),
    "Embalaje, Cajas y Bolsas Plásticas": _build_schema(
        archetype="general",
        ui_hint="Paquetes y bultos de bolsas plásticas (de asa/camiseta por kilos: 2kg, 3kg, 5kg, 10kg, 15kg, 25kg, 30kg), bolsas de basura/escombros, bolsas celofán/kraft de regalo, cajas para tortas/pizzas/envíos y tirro/teipe de embalaje.",
        buyer_ui_hint="Selecciona la capacidad en kilos o medida en cm.",
        allowed_units=["pack", "unit", "box", "kg", "combo"],
        default_unit="pack",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Medida / Capacidad en Kilos",
            "axes": [
                {"key": "capacity_size", "label": "Medida / Kilos", "type": "select", "presets": ["2 Kg", "3 Kg", "5 Kg", "10 Kg", "15 Kg", "20 Kg", "25 Kg", "30 Kg (Tobito)", "40 Litros", "60 Litros", "120 Litros", "200 Litros (Jumbo)", "Paquete x100", "Millar (1000 und)"]},
            ],
        },
        fields=[
            {"key": "tipo_bolsa_caja", "label": "Tipo de Empaque", "type": "select", "required": False, "options": ["Bolsas de Asa (Camiseta)", "Bolsas de Basura / Escombros", "Bolsas Transparentes (Vivero / Hielo / Celofán)", "Bolsas de Papel Kraft / Regalo", "Cajas de Cartón (Torta / Pizza / Mudanza)", "Envoplast / Plástico Burbuja / Teipe"], "section": "details"},
        ],
    ),
    "Servicios Profesionales": _build_schema(
        archetype="general",
        ui_hint="Servicios técnicos, asesorías, diseño, mantenimiento, eventos, decoración, transporte o servicios profesionales. Detalla qué incluye el servicio y la modalidad.",
        buyer_ui_hint="Revisa el alcance del servicio y selecciona el plan o modalidad.",
        allowed_units=["unit", "set", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Plan / Modalidad",
            "axes": [
                {"key": "plan", "label": "Modalidad / Plan", "type": "text", "presets": ["Básico", "Estándar", "Premium", "Por Hora", "Proyecto Completo"]},
            ],
        },
        order_notes_enabled=True,
        order_notes_placeholder="Ej: Detalla tu requerimiento, fecha o dirección...",
        fields=[
            {"key": "modalidad", "label": "Modalidad", "type": "select", "required": False, "options": ["Presencial", "A Domicilio", "Remoto / Online", "Híbrido"], "section": "details"},
            {"key": "tiempo_estimado", "label": "Tiempo de Entrega / Duración", "type": "text", "required": False, "placeholder": "Ej: 24 horas, 1 sesión, 3 días hábiles", "section": "specs"},
            _warranty_field(),
        ],
    ),
    "Inmuebles y Locales Comerciales": _build_schema(
        archetype="general",
        ui_hint="Locales comerciales, oficinas, depósitos, galpones o inmuebles en alquiler o venta. Especifica metraje, ubicación referencial y modalidad.",
        buyer_ui_hint="Consulta el metraje, condiciones y disponibilidad.",
        allowed_units=["unit"],
        default_unit="unit",
        supports_variants=False,
        fields=[
            {"key": "tipo_operacion", "label": "Operación", "type": "select", "required": False, "options": ["Alquiler Mensual", "Venta", "Traspaso / Fondo de Comercio"], "section": "details"},
            {"key": "tipo_inmueble", "label": "Tipo de Inmueble", "type": "select", "required": False, "options": ["Local Comercial", "Oficina", "Galpón / Depósito", "Consultorio", "Apartamento / Casa", "Terreno"], "section": "details"},
            {"key": "area_m2", "label": "Área Aproximada (m²)", "type": "text", "required": False, "placeholder": "Ej: 45 m²", "section": "specs"},
        ],
    ),

    # Alias legacy de Fiestas y Piñatería
    "Fiestas y Cotillones": _build_schema(archetype="general", ui_hint="Piñatas, cotillones, globos y descartables.", buyer_ui_hint="Selecciona el diseño o paquete disponible.", allowed_units=["unit", "pack", "box", "set", "dozen", "combo"], default_unit="unit", supports_variants=True, order_notes_enabled=True),

    # --------------------------------------------------------------------------
    # 15. OTRAS CATEGORÍAS (1 Subcategoría Oficial)
    # --------------------------------------------------------------------------
    "Otros": _build_schema(
        archetype="general",
        ui_hint="Configura libremente la unidad de venta, presentaciones, variantes, combos o grupos de opciones adicionales según tu producto o servicio.",
        buyer_ui_hint="Selecciona las opciones disponibles.",
        allowed_units=["unit", "pack", "box", "set", "kg", "g", "l", "ml", "portion", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Variantes / Opciones",
            "axes": [
                {"key": "option", "label": "Opción / Presentación", "type": "text", "presets": ["Estándar", "Especial", "Combo"]},
            ],
        },
        supports_modifier_groups=True,
        order_notes_enabled=True,
        fields=[
            {"key": "marca", "label": "Marca / Proveedor", "type": "text", "required": False, "placeholder": "Opcional", "section": "details"},
            {"key": "condicion", "label": "Condición", "type": "select", "required": False, "options": ["Nuevo", "Usado", "Servicio / Bajo Pedido"], "section": "condition"},
            _warranty_field(),
        ],
    ),
}

def _norm_text(value: Optional[str]) -> str:
    import unicodedata
    if not value:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(value))
    return "".join(c for c in nfkd if not unicodedata.combining(c)).strip().lower()


def _infer_schema_from_keywords(sub_norm: str, cat_norm: str) -> Dict[str, Any]:
    """
    Infiere el arquetipo de esquema dinámico a partir de palabras clave semánticas
    del nombre de la subcategoría o categoría, sin duplicar diccionarios de catálogo.
    """
    text = f"{sub_norm} {cat_norm}".strip()

    # Reglas semánticas compactas (palabra clave -> arquetipo en SUBCATEGORY_SCHEMAS)
    keyword_rules = (
        # Alimentos y Bebidas
        (("fruta", "verdura", "hortaliza", "carniceria", "ave", "pescaderia", "marisco"), "Frescos"),
        (("charcuteria", "lacteo", "queso", "huevo"), "Charcutería y Lácteos"),
        (("licor", "cerveza", "ron", "whisky", "vino"), "Licores"),
        (("refresco", "malta", "jugo", "agua"), "Bebidas"),
        (("panaderia", "pasteleria", "chucheria", "snack", "dulce", "congelado", "pasapalo"), "Snacks y Dulces"),
        (("vivere", "grano", "enlatado", "conserva", "salsa", "condimento", "aceite", "cafe", "infusion", "avena", "cereal"), "Despensa y Víveres"),
        # Tecnología y Electrónica
        (("telefono", "celular", "tablet"), "Celulares y Tablets"),
        (("smartwatch", "wearable"), "Wearables"),
        (("consola", "videojuego"), "Videojuegos y Consolas"),
        (("monitor", "televisor", "proyector", "video beam"), "TV, Audio y Video"),
        (("camara", "fotografia"), "Cámaras y Fotografía"),
        (("domotica", "smart home", "vigilancia"), "Seguridad y Domótica"),
        (("audifono", "corneta", "teclado y mouse", "cargador", "powerbank", "regulador", "ups"), "Periféricos y Accesorios"),
        (("computadora", "laptop", "hardware", "memoria", "almacenamiento", "impresora", "escaner", "router", "conectividad"), "Computación"),
        # Ropa y Accesorios
        (("zapato", "chola", "zandalia", "sandalia", "tacon", "calzado"), "Calzado"),
        (("bolso", "cartera", "billetera", "monedero", "maleta"), "Bolsos y Carteras"),
        (("joyeria", "bisuteria", "lente", "reloj", "gorra", "sombrero", "correa"), "Accesorios y Joyería"),
        (("caballero",), "Ropa Masculina"),
        (("nino", "nina", "ropa para bebe", "ropa de bebe", "monillo", "bodie"), "Ropa Infantil"),
        (("dama", "vestido", "falda", "enterizo", "blusa", "lenceria", "pijama", "traje de bano"), "Ropa Femenina"),
        # Salud y Belleza
        (("skincare", "facial"), "Skincare y Cuidado Facial"),
        (("maquillaje", "labio"), "Maquillaje"),
        (("perfumeria", "splash", "fragancia"), "Perfumería"),
        (("farmacia", "botiquin", "auxilio", "vitamina", "preservativo", "salud sexual", "tensiometro", "equipo medico"), "Farmacia y Bienestar"),
        (("capilar", "tinte", "manicura", "pedicura", "desodorante", "afeitado", "bucal", "higiene personal"), "Cuidado Personal"),
        # Hogar, Muebles y Jardín
        (("limpieza", "detergente", "mopa"), "Limpieza del Hogar"),
        (("cama", "colchon", "sabana", "edredon"), "Dormitorio"),
        (("poceta", "lavamanos"), "Baño"),
        (("jardineria", "manguera"), "Jardín y Exteriores"),
        (("cuadro", "espejo", "decoracion"), "Decoración"),
        (("mueble", "comedor", "sala"), "Muebles"),
        (("linea blanca", "nevera", "lavadora", "electrodomestico", "aire acondicionado", "ventilador", "planta electrica", "inversor", "olla", "sarten"), "Electrodomésticos"),
        # Ferretería y Construcción
        (("plomeria", "tuberia", "griferia", "hidroneumatico", "bomba", "tanque de agua"), "Plomería"),
        (("electricidad", "breaker", "tomacorriente", "bombillo", "reflector", "iluminacion"), "Electricidad e Iluminación"),
        (("pintura", "cunete", "brocha", "cemento", "pego", "bloque"), "Materiales de Construcción"),
        (("herramienta", "taladro", "esmeril", "tornilleria", "clavo", "cerradura", "candado", "seguridad industrial"), "Herramientas"),
        # Carros, Motos y Otros
        (("venta de carro", "camioneta"), "Venta de Autos"),
        (("venta de moto",), "Venta de Motos"),
        (("caucho", "rin", "neumatico"), "Neumáticos y Rines"),
        (("aceite de motor", "fluido", "lubricante"), "Lubricantes y Fluidos"),
        (("casco", "accesorios para moto"), "Motos"),
        (("freno", "pastilla", "tren delantero", "repuesto", "baterias para carro"), "Repuestos para Autos"),
        (("luces led", "sonido para carro", "alarma", "trancapalanca", "cuidado automotriz", "cera"), "Accesorios para Vehículos"),
        # Deportes y Fitness
        (("pesa", "mancuerna", "gym", "creatina", "suplementos gym"), "Fitness y Musculación"),
        (("camping", "carpa", "cava", "cooler", "termo"), "Camping y Outdoors"),
        (("ropa deportiva", "licra"), "Ropa y Calzado Deportivo"),
        (("beisbol", "softbol", "futbol", "futsal", "basquetbol", "padel", "tenis", "bicicleta", "ciclismo"), "Deportes Específicos"),
        # Bebés y Maternidad
        (("panal", "antipanalitis"), "Pañales y Toallitas"),
        (("tetero", "esterilizador", "chupon", "lactancia", "formula infantil", "papilla"), "Lactancia y Alimentación"),
        (("coche", "portabebe", "sillas para carro"), "Paseo y Viaje"),
        (("cuna", "corral", "moises", "monitores de bebe", "monitores y seguridad"), "Cuarto del Bebé"),
        (("banera", "jabones de bebe"), "Higiene y Cuidado del Bebé"),
        # Juegos y Juguetes
        (("muneca", "barbie", "peluche"), "Muñecas y Peluches"),
        (("bloque", "lego", "armable"), "Bloques y Construcción"),
        (("juegos de mesa", "domino", "cartas"), "Juegos de Mesa y Rompecabezas"),
        (("patineta", "patin", "monopatin", "triciclo", "juguetes de exterior", "piscina", "inflable", "pistola", "dardo"), "Juguetes de Exterior"),
        (("estimulacion", "juguetes para bebe"), "Juguetes para Bebés"),
        (("carrito", "control remoto", "figura", "superheroe"), "Figuras de Acción"),
        # Mascotas
        (("antipulga", "garrapaticida", "desparasitante", "estetica canina"), "Higiene y Salud Animal"),
        (("gatarina", "gato", "arenera", "rascador"), "Gatos"),
        (("perrarina", "perro", "mascota", "pechera", "transportadora", "aves, peces"), "Perros"),
        # Papelería, Oficina y Libros
        (("libro", "novela", "literatura"), "Libros"),
        (("resma", "carpeta", "archivador", "calculadora", "grapadora", "sillas de oficina", "escritorio"), "Oficina"),
        (("cuaderno", "libreta", "lapiz", "boligrafo", "marcador", "morral", "cartuchera", "manualidad", "foami"), "Útiles Escolares"),
        # Instrumentos Musicales
        (("cuatro", "maraca", "furruco", "violin", "ukelele", "instrumentos de cuerda"), "Instrumentos de Cuerda"),
        (("guitarra", "bajo"), "Guitarras y Bajos"),
        (("teclado", "sintetizador", "piano"), "Teclados y Pianos"),
        (("bateria", "percusion", "conga", "timbal", "bongo"), "Baterías y Percusión"),
        (("viento", "flauta", "saxofon"), "Instrumentos de Viento"),
        (("microfono", "sonido en vivo", "dj", "monitoreo", "amplificador"), "Audio Profesional y DJ"),
        (("cuerda", "funda", "afinador", "pedal"), "Accesorios Musicales"),
        # Fiestas, Piñatería y Comercial
        (("pinata", "cotillon", "globo", "descartable", "servilleta", "embalaje", "bolsas plasticas"), "Fiestas y Cotillones"),
        (("servicio profesional", "servicios profesionales"), "Servicios Profesionales"),
        (("inmueble", "local comercial", "locales comerciales"), "Inmuebles y Locales Comerciales"),
    )

    for keywords, schema_key in keyword_rules:
        if any(kw in sub_norm for kw in keywords):
            return SUBCATEGORY_SCHEMAS[schema_key]

    for keywords, schema_key in keyword_rules:
        if any(kw in text for kw in keywords):
            return SUBCATEGORY_SCHEMAS[schema_key]

    return SUBCATEGORY_SCHEMAS["Otros"]


def get_subcategory_schema(
    subcategory_name: Optional[str] = None,
    parent_category_name: Optional[str] = None,
    custom_override: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Devuelve el esquema dinámico completo para una subcategoría o categoría,
    tomando únicamente `CATALOGO_ESTRUCTURA` como fuente de verdad de categorías.
    """
    effective_sub = (subcategory_name or "").strip()
    effective_cat = (parent_category_name or "").strip()

    # Si solo se indicó la categoría padre, tomar su primera subcategoría desde CATALOGO_ESTRUCTURA
    if not effective_sub and effective_cat:
        cat_norm = _norm_text(effective_cat)
        for cat_entry in CATALOGO_ESTRUCTURA:
            if _norm_text(cat_entry.get("categoria")) == cat_norm:
                subs = cat_entry.get("subcategorias") or []
                if subs:
                    effective_sub = subs[0].get("nombre", "")
                break

    base_schema: Optional[Dict[str, Any]] = None
    if effective_sub:
        base_schema = SUBCATEGORY_SCHEMAS.get(effective_sub)
        if not base_schema:
            sub_norm = _norm_text(effective_sub)
            for key, val in SUBCATEGORY_SCHEMAS.items():
                if _norm_text(key) == sub_norm:
                    base_schema = val
                    break

    if not base_schema:
        base_schema = _infer_schema_from_keywords(
            _norm_text(effective_sub),
            _norm_text(effective_cat),
        )

    result = json.loads(json.dumps(base_schema))
    if custom_override and isinstance(custom_override, dict):
        if custom_override.get("is_custom_override"):
            result.update(custom_override)

    result["subcategory_name"] = subcategory_name or ""
    result["parent_category_name"] = parent_category_name or ""

    return result


# ==============================================================================
# 5. VALIDACIÓN Y NORMALIZACIÓN DE DATOS DINÁMICOS DE PRODUCTO
# ==============================================================================

def _parse_json_or_value(raw_val: Any, default: Any) -> Any:
    if raw_val is None or raw_val == "":
        return default
    if isinstance(raw_val, (dict, list)):
        return raw_val
    if isinstance(raw_val, str):
        raw_str = raw_val.strip()
        if not raw_str:
            return default
        try:
            return json.loads(raw_str)
        except Exception:
            return default
    return default


def _to_float(val: Any, default: float) -> float:
    if val is None or val == "":
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _to_bool(val: Any, default: bool) -> bool:
    if val is None or val == "":
        return default
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    if isinstance(val, str):
        v = val.strip().lower()
        if v in ("true", "1", "yes", "si", "sí"):
            return True
        if v in ("false", "0", "no"):
            return False
    return default


def normalize_combo_items(raw_combo_items: Any) -> List[Dict[str, Any]]:
    """
    Normaliza la lista de componentes incluidos en un Combo / Promoción:
    Ejemplo: [{"quantity": 1, "name": "Hamburguesa Clásica"}, {"quantity": 1, "name": "Refresco 355 ml"}, {"quantity": 1, "name": "Ensalada César"}]
    Acepta tanto lista de diccionarios como lista de strings (ej. ["1 Hamburguesa", "1 Refresco", "1 Ensalada"]).
    """
    parsed = _parse_json_or_value(raw_combo_items, [])
    if isinstance(parsed, str):
        # Permitir texto separado por '+' o ',' (ej. "1 Hamburguesa + 1 Refresco + 1 Ensalada")
        sep = "+" if "+" in parsed else ("," if "," in parsed else "\n")
        parsed = [p.strip() for p in parsed.split(sep) if p.strip()]
    if not isinstance(parsed, list):
        return []

    normalized: List[Dict[str, Any]] = []
    for idx, item in enumerate(parsed):
        if isinstance(item, str):
            raw_text = item.strip()
            if not raw_text:
                continue
            parts = raw_text.split(" ", 1)
            qty_val: float = 1.0
            name_val = raw_text
            if len(parts) == 2:
                first_tok = parts[0].lower().rstrip("x")
                try:
                    qty_val = max(0.01, float(first_tok))
                    name_val = parts[1].strip()
                except (ValueError, TypeError):
                    qty_val = 1.0
            qty_out: Any = int(qty_val) if float(qty_val).is_integer() else round(qty_val, 2)
            normalized.append({
                "id": f"cmb_item_{idx + 1}",
                "name": name_val,
                "quantity": qty_out,
                "unit": "und",
                "product_id": None,
                "notes": "",
            })
        elif isinstance(item, dict):
            name_val = str(
                item.get("name")
                or item.get("title")
                or item.get("label")
                or item.get("item")
                or item.get("product_name")
                or ""
            ).strip()
            if not name_val:
                continue
            qty_float = max(0.01, _to_float(item.get("quantity", item.get("qty", item.get("cantidad", 1))), 1.0))
            qty_out = int(qty_float) if float(qty_float).is_integer() else round(qty_float, 2)
            unit_val = str(item.get("unit") or item.get("unidad") or "und").strip() or "und"
            prod_id = item.get("product_id") or item.get("id_producto")
            prod_id_int: Optional[int] = None
            if prod_id not in (None, ""):
                try:
                    prod_id_int = int(prod_id)
                except (ValueError, TypeError):
                    prod_id_int = None
            item_id = str(item.get("id") or f"cmb_item_{idx + 1}")
            notes_val = str(item.get("notes") or item.get("nota") or item.get("description") or "").strip()
            normalized.append({
                "id": item_id,
                "name": name_val,
                "quantity": qty_out,
                "unit": unit_val,
                "product_id": prod_id_int,
                "notes": notes_val,
            })

    return normalized


def build_combo_summary(combo_items: List[Dict[str, Any]]) -> str:
    """
    Construye un resumen legible para mostrar en tarjetas de catálogo, carrito y órdenes:
    Ej: '1x Hamburguesa + 1x Refresco + 1x Ensalada'
    """
    if not combo_items:
        return ""
    parts: List[str] = []
    for item in combo_items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        qty = item.get("quantity", 1)
        unit = str(item.get("unit") or "und").strip().lower()
        if unit in ("und", "unidad", "unidades", "unit", ""):
            parts.append(f"{qty} {name}")
        else:
            parts.append(f"{qty} {unit} {name}")
    return " + ".join(parts)


def normalize_variants(raw_variants: Any, base_price: float = 0.0) -> List[Dict[str, Any]]:
    """
    Normaliza la lista de variantes de un producto:
    Cada variante tiene:
      - id: str
      - name / label: str (ej. 'Talla M - Negro' o '500g' o '42')
      - options / attributes: dict (ej. {'size': 'M', 'color': 'Negro'})
      - price: float | None (precio absoluto opcional; si es None se usa base_price + price_delta)
      - price_delta: float (diferencia sobre el precio base, default 0.0)
      - effective_price: float (precio calculado final de la variante)
      - stock: int | None (inventario opcional de la variante)
      - sku: str (opcional)
      - is_available: bool (default True)
    """
    parsed = _parse_json_or_value(raw_variants, [])
    if not isinstance(parsed, list):
        return []

    normalized: List[Dict[str, Any]] = []
    for idx, item in enumerate(parsed):
        if not isinstance(item, dict):
            continue

        var_id = str(item.get("id") or item.get("uid") or f"var_{idx + 1}_{uuid.uuid4().hex[:6]}")
        options = item.get("options") if isinstance(item.get("options"), dict) else (
            item.get("attributes") if isinstance(item.get("attributes"), dict) else {}
        )
        # Soportar claves directas comunes como size, shoe_size, color, presentation, weight, storage, flavor
        for direct_key in (
            "size", "talla", "shoe_size", "talla_calzado", "color",
            "presentation", "presentacion", "weight", "peso",
            "storage", "almacenamiento", "flavor", "sabor",
        ):
            if direct_key in item and item[direct_key] not in (None, "") and direct_key not in options:
                options[direct_key] = str(item[direct_key])

        name = str(item.get("name") or item.get("label") or item.get("title") or "").strip()
        if not name and options:
            name = " / ".join(str(v) for v in options.values() if v not in (None, ""))
        if not name:
            name = f"Opción {idx + 1}"

        raw_abs_price = item.get("price")
        price_delta = _to_float(item.get("price_delta", item.get("extra_price", 0.0)), 0.0)

        abs_price: Optional[float] = None
        if raw_abs_price not in (None, ""):
            try:
                abs_price = round(max(0.0, float(raw_abs_price)), 2)
            except (ValueError, TypeError):
                abs_price = None

        if abs_price is not None:
            effective_price = abs_price
            if base_price > 0 and price_delta == 0.0:
                price_delta = round(abs_price - base_price, 2)
        else:
            effective_price = round(max(0.0, base_price + price_delta), 2)

        raw_stock = item.get("stock", item.get("quantity"))
        stock_val: Optional[int] = None
        if raw_stock not in (None, ""):
            try:
                stock_val = max(0, int(float(raw_stock)))
            except (ValueError, TypeError):
                stock_val = None

        is_available = _to_bool(item.get("is_available", True), True)
        if stock_val is not None and stock_val <= 0 and "is_available" not in item:
            is_available = False

        normalized.append({
            "id": var_id,
            "name": name,
            "label": name,
            "options": options,
            "price": abs_price,
            "price_delta": round(price_delta, 2),
            "effective_price": effective_price,
            "stock": stock_val,
            "sku": str(item.get("sku") or "").strip(),
            "is_available": is_available,
        })

    return normalized


def normalize_modifier_groups(raw_groups: Any) -> List[Dict[str, Any]]:
    """
    Normaliza grupos de modificadores/extras (estilo PedidosYa):
    Cada grupo tiene:
      - id: str
      - name: str (ej. 'Elige tu contorno', 'Extras', 'Tipo de corte')
      - required: bool
      - min_selections: int
      - max_selections: int
      - options: [{id, name, price_delta, is_available}]
    """
    parsed = _parse_json_or_value(raw_groups, [])
    if not isinstance(parsed, list):
        return []

    normalized_groups: List[Dict[str, Any]] = []
    for g_idx, group in enumerate(parsed):
        if not isinstance(group, dict):
            continue

        group_name = str(group.get("name") or group.get("title") or group.get("label") or "").strip()
        if not group_name:
            continue

        group_id = str(group.get("id") or f"mod_grp_{g_idx + 1}_{uuid.uuid4().hex[:6]}")
        required = _to_bool(group.get("required", False), False)
        min_sel = max(0, int(_to_float(group.get("min_selections", 1 if required else 0), 1 if required else 0)))
        max_sel = max(1, int(_to_float(group.get("max_selections", 1), 1)))
        if max_sel < min_sel and min_sel > 0:
            max_sel = min_sel

        raw_options = group.get("options") if isinstance(group.get("options"), list) else (
            group.get("items") if isinstance(group.get("items"), list) else []
        )
        normalized_options: List[Dict[str, Any]] = []
        for o_idx, opt in enumerate(raw_options):
            if not isinstance(opt, dict):
                continue
            opt_name = str(opt.get("name") or opt.get("label") or opt.get("title") or "").strip()
            if not opt_name:
                continue
            opt_id = str(opt.get("id") or f"mod_opt_{g_idx + 1}_{o_idx + 1}_{uuid.uuid4().hex[:5]}")
            price_delta = round(max(0.0, _to_float(opt.get("price_delta", opt.get("price", 0.0)), 0.0)), 2)
            is_avail = _to_bool(opt.get("is_available", True), True)
            normalized_options.append({
                "id": opt_id,
                "name": opt_name,
                "price_delta": price_delta,
                "is_available": is_avail,
            })

        if normalized_options:
            normalized_groups.append({
                "id": group_id,
                "name": group_name,
                "required": required,
                "min_selections": min_sel,
                "max_selections": max_sel,
                "options": normalized_options,
            })

    return normalized_groups


def _format_warranty_label(value: Any, unit: str) -> str:
    """Formatea un valor numérico + unidad de garantía en español limpio (ej. '1 año', '6 meses', '30 días')."""
    u = str(unit or "meses").strip().lower()
    if u in ("sin garantía", "sin garantia", "ninguna", "no", "none", "0"):
        return "Sin garantía"
    try:
        num = float(value)
        num_int = int(num) if num.is_integer() else num
    except (ValueError, TypeError):
        return str(value).strip()

    if num <= 0:
        return "Sin garantía"

    if u in ("año", "años", "ano", "anos", "year", "years", "yr"):
        return f"{num_int} {'año' if num_int == 1 else 'años'}"
    if u in ("día", "días", "dia", "dias", "day", "days"):
        return f"{num_int} {'día' if num_int == 1 else 'días'}"
    return f"{num_int} {'mes' if num_int == 1 else 'meses'}"


def normalize_attributes(raw_attributes: Any) -> Dict[str, Any]:
    """
    Normaliza el diccionario de atributos dinámicos del producto (ej. marca, modelo, talla, garantía, etc.).
    Soporta garantías flexibles en días, meses o años:
      - Preset o texto: {"garantia": "1 año"} o {"garantia": "6 meses"}
      - Número + unidad separados: {"garantia_valor": 1, "garantia_unidad": "años"} o {"garantia": 6, "garantia_unidad": "meses"}
      - Objeto estructurado: {"garantia": {"value": 1, "unit": "años"}}
      - Legacy en meses: {"garantia_meses": 6}
    """
    parsed = _parse_json_or_value(raw_attributes, {})
    if not isinstance(parsed, dict):
        return {}

    cleaned: Dict[str, Any] = {}
    for k, v in parsed.items():
        key_str = str(k).strip()
        if not key_str or v is None or v == "":
            continue
        cleaned[key_str] = v

    # Normalización inteligente de Garantía (días / meses / años / sin garantía)
    raw_garantia = cleaned.get("garantia")
    raw_garantia_valor = cleaned.get("garantia_valor")
    raw_garantia_unidad = cleaned.get("garantia_unidad")
    raw_garantia_meses = cleaned.get("garantia_meses")

    if isinstance(raw_garantia, dict):
        w_val = raw_garantia.get("value", raw_garantia.get("valor"))
        w_unit = str(raw_garantia.get("unit", raw_garantia.get("unidad", "meses"))).strip().lower()
        if w_unit in ("sin garantía", "sin garantia", "ninguna") or w_val in (0, "0", None, ""):
            cleaned["garantia"] = "Sin garantía"
            cleaned["garantia_valor"] = 0
            cleaned["garantia_unidad"] = "sin garantía"
        else:
            cleaned["garantia"] = _format_warranty_label(w_val, w_unit)
            try:
                cleaned["garantia_valor"] = int(float(w_val)) if float(w_val).is_integer() else float(w_val)
            except (ValueError, TypeError):
                pass
            cleaned["garantia_unidad"] = w_unit
    elif raw_garantia_valor is not None or raw_garantia_unidad is not None:
        w_unit = str(raw_garantia_unidad or "meses").strip().lower()
        w_val = raw_garantia_valor if raw_garantia_valor is not None else raw_garantia
        if w_unit in ("sin garantía", "sin garantia", "ninguna") or w_val in (0, "0"):
            cleaned["garantia"] = "Sin garantía"
            cleaned["garantia_valor"] = 0
            cleaned["garantia_unidad"] = "sin garantía"
        elif w_val is not None:
            cleaned["garantia"] = _format_warranty_label(w_val, w_unit)
    elif isinstance(raw_garantia, (int, float)):
        cleaned["garantia"] = _format_warranty_label(raw_garantia, "meses")
        cleaned["garantia_valor"] = int(raw_garantia) if float(raw_garantia).is_integer() else float(raw_garantia)
        cleaned["garantia_unidad"] = "meses"
    elif isinstance(raw_garantia, str):
        g_str = raw_garantia.strip()
        if g_str.isdigit():
            num_val = int(g_str)
            cleaned["garantia"] = _format_warranty_label(num_val, "meses")
            cleaned["garantia_valor"] = num_val
            cleaned["garantia_unidad"] = "meses"
    elif raw_garantia is None and raw_garantia_meses is not None:
        cleaned["garantia"] = _format_warranty_label(raw_garantia_meses, "meses")
        try:
            cleaned["garantia_valor"] = int(float(raw_garantia_meses))
            cleaned["garantia_unidad"] = "meses"
        except (ValueError, TypeError):
            pass

    return cleaned


def validate_and_normalize_product_dynamic_data(
    data: Dict[str, Any],
    *,
    subcategory_name: Optional[str] = None,
    category_name: Optional[str] = None,
    base_price: float = 0.0,
    existing_product: Any = None,
) -> Dict[str, Any]:
    """
    Recibe un payload de creación o actualización de Producto (JSON o Multipart) y devuelve
    los campos dinámicos limpios y normalizados listos para asignar al modelo `Product`.
    Soporta además configuración de Combos (`is_combo`, `combo_items`, `combo_regular_price`).
    """
    schema = get_subcategory_schema(subcategory_name=subcategory_name, parent_category_name=category_name)

    # 0. Attributes base (para leer también posibles campos de combo enviados dentro de attributes)
    existing_attrs: Dict[str, Any] = {}
    if existing_product is not None:
        existing_attrs = normalize_attributes(getattr(existing_product, "attributes", {}))

    if "attributes" in data:
        attributes = normalize_attributes(data.get("attributes"))
        # Preservar metadatos de combo previos si no se están sobreescribiendo explícitamente
        for cmb_k in ("is_combo", "combo_items", "combo_summary", "combo_regular_price", "combo_savings"):
            if cmb_k not in attributes and cmb_k in existing_attrs and cmb_k not in data:
                attributes[cmb_k] = existing_attrs[cmb_k]
    else:
        attributes = dict(existing_attrs)

    # 1. Normalización de Combos (pueden venir en el nivel superior de `data` o dentro de `attributes`)
    raw_combo_items = data.get("combo_items")
    if raw_combo_items is None and "combo_items" in attributes:
        raw_combo_items = attributes.get("combo_items")
    combo_items = normalize_combo_items(raw_combo_items) if raw_combo_items is not None else []

    raw_is_combo = data.get("is_combo")
    if raw_is_combo is None and "is_combo" in attributes:
        raw_is_combo = attributes.get("is_combo")

    # 2. Selling Unit
    raw_unit = data.get("selling_unit")
    if raw_unit is None and existing_product is not None:
        raw_unit = getattr(existing_product, "selling_unit", None)

    is_combo = _to_bool(raw_is_combo, False) or bool(combo_items) or (str(raw_unit or "").strip().lower() == "combo")
    if raw_is_combo is not None and not _to_bool(raw_is_combo, False) and "combo_items" not in data:
        # Si explícitamente desactivaron is_combo=False
        is_combo = False
        combo_items = []

    if is_combo and not raw_unit:
        selling_unit = "combo"
    else:
        selling_unit = str(raw_unit or schema.get("default_selling_unit") or "unit").strip().lower()
    if selling_unit not in SELLING_UNITS_CATALOG:
        selling_unit = "combo" if is_combo else schema.get("default_selling_unit", "unit")

    unit_meta = SELLING_UNITS_CATALOG.get(selling_unit, SELLING_UNITS_CATALOG["unit"])

    # 3. Unit Label
    raw_unit_label = data.get("unit_label")
    if raw_unit_label is None and existing_product is not None and data.get("selling_unit") is None and not is_combo:
        raw_unit_label = getattr(existing_product, "unit_label", None)
    unit_label = str(raw_unit_label if raw_unit_label is not None else unit_meta["short_label"]).strip()

    # 4. Allow Fractional Quantity
    raw_fractional = data.get("allow_fractional_quantity")
    if raw_fractional is not None:
        allow_fractional = _to_bool(raw_fractional, unit_meta["allow_fractional"])
    elif existing_product is not None and data.get("selling_unit") is None:
        allow_fractional = bool(getattr(existing_product, "allow_fractional_quantity", unit_meta["allow_fractional"]))
    else:
        allow_fractional = bool(unit_meta["allow_fractional"])

    # 5. Unit Step & Min Order Quantity
    raw_step = data.get("unit_step")
    if raw_step is not None:
        unit_step = max(0.01, _to_float(raw_step, unit_meta["default_step"]))
    elif existing_product is not None and data.get("selling_unit") is None:
        unit_step = max(0.01, _to_float(getattr(existing_product, "unit_step", unit_meta["default_step"]), unit_meta["default_step"]))
    else:
        unit_step = unit_meta["default_step"]

    raw_min = data.get("min_order_quantity")
    if raw_min is not None:
        min_order_quantity = max(0.01, _to_float(raw_min, unit_meta["default_min"]))
    elif existing_product is not None and data.get("selling_unit") is None:
        min_order_quantity = max(0.01, _to_float(getattr(existing_product, "min_order_quantity", unit_meta["default_min"]), unit_meta["default_min"]))
    else:
        min_order_quantity = unit_meta["default_min"]

    # 6. Persistir metadatos de Combo dentro de `attributes` para no requerir migración de esquema SQL
    combo_summary = build_combo_summary(combo_items) if combo_items else str(
        data.get("combo_summary") or attributes.get("combo_summary") or ""
    ).strip()

    raw_reg_price = data.get("combo_regular_price", attributes.get("combo_regular_price"))
    combo_regular_price: Optional[float] = None
    combo_savings: Optional[float] = None
    if raw_reg_price not in (None, ""):
        reg_val = round(max(0.0, _to_float(raw_reg_price, 0.0)), 2)
        if reg_val > 0:
            combo_regular_price = reg_val
            if base_price > 0 and reg_val > base_price:
                combo_savings = round(reg_val - base_price, 2)

    if is_combo:
        attributes["is_combo"] = True
        attributes["combo_items"] = combo_items
        if combo_summary:
            attributes["combo_summary"] = combo_summary
        if combo_regular_price is not None:
            attributes["combo_regular_price"] = combo_regular_price
        if combo_savings is not None:
            attributes["combo_savings"] = combo_savings
    else:
        for cmb_k in ("is_combo", "combo_items", "combo_summary", "combo_regular_price", "combo_savings"):
            attributes.pop(cmb_k, None)

    # 7. Variants & Modifier Groups
    if "variants" in data:
        variants = normalize_variants(data.get("variants"), base_price=base_price)
    elif existing_product is not None:
        variants = normalize_variants(getattr(existing_product, "variants", []), base_price=base_price)
    else:
        variants = []

    if "modifier_groups" in data:
        modifier_groups = normalize_modifier_groups(data.get("modifier_groups"))
    elif existing_product is not None:
        modifier_groups = normalize_modifier_groups(getattr(existing_product, "modifier_groups", []))
    else:
        modifier_groups = []

    return {
        "selling_unit": selling_unit,
        "unit_label": unit_label,
        "allow_fractional_quantity": allow_fractional,
        "min_order_quantity": round(min_order_quantity, 3),
        "unit_step": round(unit_step, 3),
        "attributes": attributes,
        "variants": variants,
        "modifier_groups": modifier_groups,
        "is_combo": is_combo,
        "combo_items": combo_items,
        "combo_summary": combo_summary if is_combo else "",
        "combo_regular_price": combo_regular_price if is_combo else None,
        "combo_savings": combo_savings if is_combo else None,
    }


def resolve_cart_item_dynamic_pricing(
    product: Any,
    item_payload: Dict[str, Any],
) -> Tuple[float, Dict[str, Any]]:
    """
    Calcula el precio unitario efectivo de un ítem en el carrito tomando en cuenta:
    - Variante seleccionada (`selected_variant_id` o `selected_variant`)
    - Modificadores/extras seleccionados (`selected_modifiers`: lista de IDs o dicts)
    - Notas u opciones seleccionadas (`selected_options`, `customer_notes`)
    - Componentes del combo si el producto es un combo (`is_combo`, `combo_items`, `combo_summary`)
    Devuelve `(effective_unit_price, selection_metadata_dict)`.
    """
    base_price = round(float(getattr(product, "price", 0.0) or 0.0), 2)
    effective_unit_price = base_price

    variants = normalize_variants(getattr(product, "variants", []), base_price=base_price)
    modifier_groups = normalize_modifier_groups(getattr(product, "modifier_groups", []))

    # 1. Resolver Variante seleccionada
    selected_variant_input = item_payload.get("selected_variant_id") or item_payload.get("selected_variant") or item_payload.get("variant_id")
    matched_variant: Optional[Dict[str, Any]] = None

    if selected_variant_input and variants:
        if isinstance(selected_variant_input, dict):
            target_id = str(selected_variant_input.get("id") or "").strip()
            target_name = str(selected_variant_input.get("name") or selected_variant_input.get("label") or "").strip().lower()
        else:
            target_id = str(selected_variant_input).strip()
            target_name = target_id.lower()

        for v in variants:
            if (target_id and v["id"] == target_id) or (target_name and v["name"].lower() == target_name):
                matched_variant = v
                break

    if matched_variant is not None:
        effective_unit_price = float(matched_variant.get("effective_price", base_price))

    # 2. Resolver Modificadores / Extras seleccionados
    raw_selected_mods = item_payload.get("selected_modifiers") or item_payload.get("modifiers") or []
    if isinstance(raw_selected_mods, str):
        raw_selected_mods = _parse_json_or_value(raw_selected_mods, [])
    if not isinstance(raw_selected_mods, list):
        raw_selected_mods = []

    # Construir índice de opciones válidas del producto
    valid_mod_options: Dict[str, Dict[str, Any]] = {}
    valid_mod_by_name: Dict[str, Dict[str, Any]] = {}
    for grp in modifier_groups:
        for opt in grp.get("options", []):
            opt_entry = {
                "group_id": grp["id"],
                "group_name": grp["name"],
                "id": opt["id"],
                "name": opt["name"],
                "price_delta": float(opt.get("price_delta", 0.0)),
            }
            valid_mod_options[str(opt["id"])] = opt_entry
            valid_mod_by_name[opt["name"].lower()] = opt_entry

    matched_modifiers: List[Dict[str, Any]] = []
    modifiers_total_delta = 0.0

    # Expandir formatos agrupados {"group_id": "...", "option_ids": ["..."]} y formatos planos
    flattened_mod_requests: List[Any] = []
    for mod_req in raw_selected_mods:
        if isinstance(mod_req, dict) and ("option_ids" in mod_req or "options" in mod_req):
            sub_opts = mod_req.get("option_ids") or mod_req.get("options") or []
            if isinstance(sub_opts, list):
                flattened_mod_requests.extend(sub_opts)
        else:
            flattened_mod_requests.append(mod_req)

    for mod_req in flattened_mod_requests:
        matched_opt: Optional[Dict[str, Any]] = None
        qty_multiplier = 1
        if isinstance(mod_req, dict):
            m_id = str(mod_req.get("id") or mod_req.get("option_id") or "").strip()
            m_name = str(mod_req.get("name") or mod_req.get("label") or "").strip().lower()
            qty_multiplier = max(1, int(_to_float(mod_req.get("quantity", 1), 1)))
            if m_id and m_id in valid_mod_options:
                matched_opt = valid_mod_options[m_id]
            elif m_name and m_name in valid_mod_by_name:
                matched_opt = valid_mod_by_name[m_name]
        elif isinstance(mod_req, str):
            m_key = mod_req.strip()
            if m_key in valid_mod_options:
                matched_opt = valid_mod_options[m_key]
            elif m_key.lower() in valid_mod_by_name:
                matched_opt = valid_mod_by_name[m_key.lower()]

        if matched_opt is not None:
            delta = round(matched_opt["price_delta"] * qty_multiplier, 2)
            modifiers_total_delta += delta
            matched_modifiers.append({
                "group_id": matched_opt["group_id"],
                "group_name": matched_opt["group_name"],
                "id": matched_opt["id"],
                "name": matched_opt["name"],
                "price_delta": matched_opt["price_delta"],
                "quantity": qty_multiplier,
                "total_delta": delta,
            })

    effective_unit_price = round(max(0.0, effective_unit_price + modifiers_total_delta), 2)

    # 3. Opciones libres seleccionadas (ej. talla/color si el producto las tiene en attributes o opciones simples)
    selected_options = _parse_json_or_value(item_payload.get("selected_options"), {})
    if not isinstance(selected_options, dict):
        selected_options = {}
    if matched_variant and matched_variant.get("options"):
        merged_opts = dict(matched_variant["options"])
        merged_opts.update(selected_options)
        selected_options = merged_opts

    customer_notes = str(item_payload.get("customer_notes") or item_payload.get("notes") or "").strip()[:300]
    selling_unit = getattr(product, "selling_unit", "unit") or "unit"
    unit_label = getattr(product, "unit_label", "") or SELLING_UNITS_CATALOG.get(selling_unit, SELLING_UNITS_CATALOG["unit"])["short_label"]

    prod_attrs = getattr(product, "attributes", {})
    if not isinstance(prod_attrs, dict):
        prod_attrs = {}
    combo_items = normalize_combo_items(prod_attrs.get("combo_items", []))
    is_combo = _to_bool(prod_attrs.get("is_combo", False), False) or bool(combo_items) or selling_unit == "combo"
    combo_summary = str(prod_attrs.get("combo_summary") or build_combo_summary(combo_items)).strip() if is_combo else ""

    selection_meta = {
        "selling_unit": selling_unit,
        "unit_label": unit_label,
        "base_price": base_price,
        "effective_unit_price": effective_unit_price,
        "is_combo": is_combo,
        "combo_items": combo_items if is_combo else [],
        "combo_summary": combo_summary,
        "selected_variant": {
            "id": matched_variant["id"],
            "name": matched_variant["name"],
            "options": matched_variant.get("options", {}),
            "price_delta": matched_variant.get("price_delta", 0.0),
            "effective_price": matched_variant.get("effective_price", base_price),
        } if matched_variant else None,
        "selected_modifiers": matched_modifiers,
        "modifiers_total_delta": round(modifiers_total_delta, 2),
        "selected_options": selected_options,
        "customer_notes": customer_notes,
    }

    return effective_unit_price, selection_meta
