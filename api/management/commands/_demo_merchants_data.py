# -*- coding: utf-8 -*-
"""
Datos de demostración para `python manage.py seed_demo_merchants`.

Define 4 comercios de Caracas (uno por usuario) con 15 productos cada uno: descripción, precio, stock por variante,
descuentos por tokens, ofertas porcentuales, variantes, personalizaciones (modifier_groups) y 2 fotos por producto.

Todos los IDs (compañía, sucursal, producto, ítem de inventario) son DETERMINISTAS (uuid5), por lo que:
  * el comando es idempotente (re-ejecutarlo actualiza en lugar de duplicar), y
  * las rutas de S3 de las imágenes ya subidas (`scripts/demo_merchants/upload_images.py`) coinciden siempre.
"""
import uuid

DEMO_NAMESPACE = uuid.UUID('6f1c2b6e-5a77-4c0e-9a3d-0d3e5c0a7e11')


def demo_uuid(*parts) -> uuid.UUID:
    return uuid.uuid5(DEMO_NAMESPACE, 'cartmaker-demo:' + ':'.join(str(p) for p in parts))


# ----------------------------------------------------------------------------------------------------------------------
# Helpers de construcción
# ----------------------------------------------------------------------------------------------------------------------
TOK_A = [{'tokens': 50, 'percentage': 5}, {'tokens': 150, 'percentage': 10}, {'tokens': 300, 'percentage': 15}]
TOK_B = [{'tokens': 100, 'percentage': 8}, {'tokens': 250, 'percentage': 15}]
TOK_C = [{'tokens': 200, 'percentage': 10}, {'tokens': 500, 'percentage': 20}]


def V(options, stock, price=None):
    """Variante: `options` dict (size/color/storage...), `stock` int, `price` precio absoluto opcional."""
    return {'options': options, 'stock': stock, 'price': price}


def grid(key_a, vals_a, key_b, vals_b, stock=6, price=None, sold_out=()):
    """Combina dos ejes en variantes. `sold_out` = tuplas (a, b) con stock 0 (se muestran agotadas)."""
    out = []
    n = 0
    for a in vals_a:
        for b in vals_b:
            n += 1
            st = 0 if (a, b) in sold_out else max(1, stock - (n % 4))
            out.append(V({key_a: a, key_b: b}, st, price))
    return out


def sizes(key, vals, stock=5, price=None, sold_out=()):
    return [V({key: v}, 0 if v in sold_out else stock + (i % 3), price) for i, v in enumerate(vals)]


def M(name, options, required=False, max_sel=1):
    """Grupo de personalización. `options` = [(nombre, sobreprecio USD), ...]."""
    return {
        'name': name,
        'required': required,
        'min_selections': 1 if required else 0,
        'max_selections': max_sel,
        'options': [{'name': n, 'price_delta': d} for n, d in options],
    }


def P(slug, name, sub, parent, price, desc, imgs, *, unit='unit', attrs=None, variants=None, mods=None,
      tokens=None, offer=0, stock=None):
    return {
        'slug': slug, 'name': name, 'sub': sub, 'parent': parent, 'price': price, 'description': desc,
        'img_prompts': list(imgs), 'selling_unit': unit, 'attributes': attrs or {}, 'variants': variants or [],
        'modifier_groups': mods or [], 'tokens': tokens, 'offer': offer, 'stock': stock,
    }


STUDIO = ('professional e-commerce product photograph, {what}, centered, clean white seamless studio background, '
          'soft natural shadow, sharp focus, high detail, no text, no logos overlay, no watermark')
ALT = ('{what}, second angle / lifestyle detail shot, soft natural lighting, shallow depth of field, '
       'realistic photo, no text, no watermark')

# ----------------------------------------------------------------------------------------------------------------------
# 1) SOY TECHNO — Venta de teléfonos
# ----------------------------------------------------------------------------------------------------------------------
TEC = 'Tecnología y Electrónica'
SOY_TECHNO_PRODUCTS = [
    P('iphone-15-128', 'iPhone 15 128 GB', 'Teléfonos y Tablets', TEC, 699.00,
      'iPhone 15 con chip A16 Bionic, pantalla Super Retina XDR de 6.1", cámara principal de 48 MP y puerto USB-C. '
      'Equipo nuevo y sellado, liberado para todas las operadoras, con 1 año de garantía en tienda.',
      (STUDIO.format(what='a brand new smartphone similar to an iPhone 15 in blue color, front and back view'),
       ALT.format(what='close-up of the dual camera module of a modern premium smartphone, pastel blue aluminum frame')),
      attrs={'marca': 'Apple', 'modelo': 'iPhone 15', 'almacenamiento': '128 GB', 'ram': '6 GB',
             'dual_sim': 'SIM Física + eSIM', 'condicion': 'Nuevo (Sellado)', 'garantia': '1 año'},
      variants=[V({'storage': '128 GB', 'color': 'Negro'}, 5), V({'storage': '128 GB', 'color': 'Azul'}, 4),
                V({'storage': '128 GB', 'color': 'Rosado'}, 0), V({'storage': '256 GB', 'color': 'Negro'}, 3, 799.00)],
      mods=[M('Protección para tu iPhone', [('Vidrio templado 9H', 6), ('Forro antigolpes transparente', 10),
                                            ('Combo vidrio + forro', 14)], max_sel=2),
            M('Garantía extendida', [('+6 meses de garantía', 29)])],
      tokens=TOK_A, offer=0),
    P('galaxy-s24-256', 'Samsung Galaxy S24 256 GB', 'Teléfonos y Tablets', TEC, 749.00,
      'Galaxy S24 con Galaxy AI, pantalla Dynamic AMOLED 2X de 6.2" a 120 Hz, procesador Exynos 2400 y triple cámara de 50 MP. '
      'Nuevo, sellado y liberado. Incluye garantía de 1 año.',
      (STUDIO.format(what='a modern flagship Android smartphone in violet color, front and back view'),
       ALT.format(what='flagship Android smartphone held in a hand, bright AMOLED screen showing colorful abstract wallpaper')),
      attrs={'marca': 'Samsung', 'modelo': 'Galaxy S24', 'almacenamiento': '256 GB', 'ram': '8 GB',
             'dual_sim': 'SIM Física + eSIM', 'condicion': 'Nuevo (Sellado)', 'garantia': '1 año'},
      variants=grid('color', ['Violeta', 'Negro Onyx', 'Gris Marble'], 'storage', ['256 GB'], stock=4),
      mods=[M('Accesorios', [('Cargador rápido 25W original', 22), ('Vidrio templado 9H', 6),
                             ('Forro oficial', 14)], max_sel=3)],
      tokens=TOK_B, offer=10),
    P('redmi-note-13-pro', 'Xiaomi Redmi Note 13 Pro 256 GB', 'Teléfonos y Tablets', TEC, 289.00,
      'Pantalla AMOLED de 6.67" a 120 Hz, cámara de 200 MP con estabilización óptica y carga turbo de 67 W. '
      'Equipo nuevo, liberado, con 6 meses de garantía.',
      (STUDIO.format(what='a mid-range Android smartphone in midnight black, large camera module, front and back view'),
       ALT.format(what='mid-range smartphone showing camera app, taking a photo of a colorful city street, bokeh background')),
      attrs={'marca': 'Xiaomi / Redmi / POCO', 'modelo': 'Redmi Note 13 Pro', 'almacenamiento': '256 GB',
             'ram': '8 GB', 'dual_sim': 'Dual SIM Física (Liberado)', 'condicion': 'Nuevo (Sellado)',
             'garantia': '6 meses'},
      variants=[V({'storage': '256 GB', 'ram': '8 GB', 'color': 'Negro Medianoche'}, 8),
                V({'storage': '256 GB', 'ram': '8 GB', 'color': 'Azul Océano'}, 6),
                V({'storage': '512 GB', 'ram': '12 GB', 'color': 'Negro Medianoche'}, 3, 339.00)],
      mods=[M('Protección', [('Vidrio templado 9H', 5), ('Forro de silicón', 7)], max_sel=2)],
      tokens=TOK_A, offer=15),
    P('tecno-spark-20-pro', 'Tecno Spark 20 Pro 256 GB', 'Teléfonos y Tablets', TEC, 149.00,
      'Pantalla de 6.78" a 120 Hz, 8 GB de RAM (ampliable), batería de 5000 mAh y cámara de 108 MP. '
      'La mejor opción calidad-precio, liberado y con 6 meses de garantía.',
      (STUDIO.format(what='an affordable Android smartphone in green color, large display, front and back view'),
       ALT.format(what='affordable smartphone lying on a wooden desk next to earbuds and a coffee cup, top view')),
      attrs={'marca': 'Tecno', 'modelo': 'Spark 20 Pro', 'almacenamiento': '256 GB', 'ram': '8 GB',
             'dual_sim': 'Dual SIM Física (Liberado)', 'condicion': 'Nuevo (Sellado)', 'garantia': '6 meses'},
      variants=grid('color', ['Verde Lunar', 'Negro Espacial', 'Blanco Perla'], 'storage', ['256 GB'], stock=9),
      tokens=TOK_C, offer=20),
    P('moto-g54-5g', 'Motorola Moto G54 5G 128 GB', 'Teléfonos y Tablets', TEC, 175.00,
      'Conectividad 5G, pantalla FHD+ de 6.5" a 120 Hz, procesador Dimensity 7020 y batería de 6000 mAh con carga de 33 W. '
      'Nuevo, liberado y con garantía de 6 meses.',
      (STUDIO.format(what='a 5G Android smartphone in pearl blue color, front and back view'),
       ALT.format(what='5G smartphone with large battery concept, lifestyle photo with a person using it outdoors, soft light')),
      attrs={'marca': 'Motorola', 'modelo': 'Moto G54 5G', 'almacenamiento': '128 GB', 'ram': '8 GB',
             'dual_sim': 'Dual SIM Física (Liberado)', 'condicion': 'Nuevo (Sellado)', 'garantia': '6 meses'},
      variants=grid('color', ['Azul Perla', 'Verde Menta'], 'storage', ['128 GB'], stock=7),
      mods=[M('Protección', [('Vidrio templado 9H', 5), ('Forro antigolpes', 8)], max_sel=2)],
      tokens=None, offer=0),
    P('ipad-10-64', 'iPad 10.ª generación 64 GB Wi-Fi', 'Teléfonos y Tablets', TEC, 349.00,
      'Pantalla Liquid Retina de 10.9", chip A14 Bionic, cámara frontal de 12 MP y puerto USB-C. Ideal para estudiar, '
      'trabajar y entretenerte. Nuevo y sellado, 1 año de garantía.',
      (STUDIO.format(what='a modern 10.9 inch tablet in silver color, front view with colorful home screen'),
       ALT.format(what='tablet on a desk with a stylus and notebook, student working, soft window light')),
      attrs={'marca': 'Apple', 'modelo': 'iPad 10.ª gen', 'almacenamiento': '64 GB', 'ram': '4 GB',
             'dual_sim': 'Solo Wi-Fi (Tablet)', 'condicion': 'Nuevo (Sellado)', 'garantia': '1 año'},
      variants=grid('color', ['Plata', 'Azul', 'Amarillo'], 'storage', ['64 GB'], stock=4, sold_out=[('Amarillo', '64 GB')]),
      mods=[M('Complementos', [('Funda con teclado', 49), ('Lápiz compatible', 35), ('Vidrio templado', 12)], max_sel=3)],
      tokens=TOK_B, offer=0),
    P('audifonos-tws-pro', 'Audífonos Inalámbricos TWS Pro con Cancelación de Ruido', 'Cargadores, Cables y Powerbanks', TEC, 24.99,
      'Bluetooth 5.3, cancelación activa de ruido, hasta 28 horas de autonomía con el estuche y resistencia al agua IPX5. '
      'Incluye 3 tamaños de almohadillas y cable USB-C.',
      (STUDIO.format(what='a pair of white true wireless earbuds with a charging case open'),
       ALT.format(what='wireless earbuds in a charging case on a marble surface, soft light, minimalist')),
      attrs={'tipo_accesorio': 'Audífonos / Forros y Vidrios', 'marca': 'Soy Techno', 'potencia_capacidad': 'Batería 28 h',
             'garantia': '3 meses'},
      variants=[V({'color': 'Blanco', 'connector': 'USB-C'}, 25), V({'color': 'Negro', 'connector': 'USB-C'}, 18)],
      tokens=TOK_A, offer=25),
    P('powerbank-20000', 'Powerbank 20.000 mAh Carga Rápida 22.5W', 'Cargadores, Cables y Powerbanks', TEC, 29.00,
      'Batería portátil de 20.000 mAh con salida USB-C PD 22.5 W y doble USB-A. Pantalla LED de porcentaje. '
      'Carga un teléfono hasta 4 veces.',
      (STUDIO.format(what='a slim black 20000mAh power bank with digital LED display and USB cable'),
       ALT.format(what='power bank charging a smartphone on a desk, cable connected, warm light')),
      attrs={'tipo_accesorio': 'Powerbank / Batería Portátil', 'marca': 'Soy Techno', 'potencia_capacidad': '20.000 mAh / 22.5 W',
             'garantia': '3 meses'},
      variants=[V({'color': 'Negro', 'connector': 'USB-C'}, 20), V({'color': 'Blanco', 'connector': 'USB-C'}, 12)],
      mods=[M('Personalízalo', [('Grabado láser con tu nombre', 5), ('Estuche protector', 4)], max_sel=2)],
      tokens=TOK_A, offer=0),
    P('cargador-gan-65w', 'Cargador Rápido GaN 65W USB-C + USB-A', 'Cargadores, Cables y Powerbanks', TEC, 27.00,
      'Cargador compacto GaN de 65 W con 2 puertos (USB-C PD y USB-A QC). Carga laptops, tablets y teléfonos al mismo tiempo. '
      'Protección contra sobrecalentamiento.',
      (STUDIO.format(what='a compact white GaN 65W wall charger with USB-C and USB-A ports'),
       ALT.format(what='compact fast wall charger plugged into a socket charging a laptop and a phone, desk scene')),
      attrs={'tipo_accesorio': 'Cargador de Pared (Taco)', 'marca': 'Soy Techno', 'potencia_capacidad': '65 W GaN',
             'garantia': '3 meses'},
      variants=[V({'color': 'Blanco', 'connector': 'USB-C + USB-A'}, 22), V({'color': 'Negro', 'connector': 'USB-C + USB-A'}, 15)],
      tokens=None, offer=10),
    P('cable-usbc-pack2', 'Pack 2 Cables USB-C Trenzados 1 m Carga Rápida', 'Cargadores, Cables y Powerbanks', TEC, 12.00,
      'Dos cables USB-C a USB-C de nailon trenzado, 60 W y datos a 480 Mbps. Resistentes a más de 10.000 flexiones.',
      (STUDIO.format(what='two braided USB-C charging cables coiled neatly, one black and one gray'),
       ALT.format(what='braided USB-C cable plugged into a smartphone, close-up of the connector, soft light')),
      unit='pack',
      attrs={'tipo_accesorio': 'Cable de Carga y Datos', 'marca': 'Soy Techno', 'potencia_capacidad': '60 W / 1 m',
             'garantia': '1 mes'},
      variants=[V({'color': 'Negro + Gris', 'connector': 'USB-C a USB-C'}, 40),
                V({'color': 'Negro + Gris', 'connector': 'USB-C a Lightning'}, 28, 14.00)],
      tokens=None, offer=0),
    P('amazfit-bip-5', 'Smartwatch Amazfit Bip 5', 'Smartwatches y Wearables', TEC, 59.00,
      'Pantalla de 1.91" con llamadas Bluetooth, GPS integrado, más de 120 modos deportivos, oxímetro y hasta 10 días de batería.',
      (STUDIO.format(what='a modern black smartwatch with large square display showing a colorful watch face'),
       ALT.format(what='smartwatch on the wrist of a runner, outdoor park, motion, natural light')),
      attrs={'marca': 'Amazfit', 'modelo': 'Bip 5', 'compatibilidad': 'iOS (iPhone) y Android', 'condicion': 'Nuevo',
             'garantia': '6 meses'},
      variants=[V({'case_size': '46 mm', 'color': 'Negro'}, 10), V({'case_size': '46 mm', 'color': 'Crema'}, 6),
                V({'case_size': '46 mm', 'color': 'Rosa'}, 5)],
      mods=[M('Correa adicional', [('Correa de silicón extra', 6), ('Correa metálica', 12)])],
      tokens=TOK_B, offer=15),
    P('ssd-nvme-1tb', 'SSD NVMe M.2 1 TB Kingston NV2', 'Almacenamiento y Memorias', TEC, 62.00,
      'Unidad de estado sólido NVMe PCIe 4.0 de 1 TB con lectura de hasta 3500 MB/s. Ideal para actualizar laptops y PC. '
      'Garantía de 6 meses.',
      (STUDIO.format(what='an M.2 NVMe SSD stick with a black PCB and a sticker label, no readable text'),
       ALT.format(what='M.2 NVMe SSD being installed into a laptop motherboard, macro shot, technician hands')),
      attrs={'tipo_memoria': 'Disco Sólido SSD M.2 NVMe', 'marca': 'Kingston', 'capacidad': '1 TB', 'garantia': '6 meses'},
      variants=[V({'capacity': '500 GB', 'format': 'M.2 NVMe'}, 9, 38.00), V({'capacity': '1 TB', 'format': 'M.2 NVMe'}, 12),
                V({'capacity': '2 TB', 'format': 'M.2 NVMe'}, 4, 112.00)],
      tokens=TOK_A, offer=0),
    P('pendrive-128gb', 'Pendrive 128 GB USB 3.2 SanDisk Ultra', 'Almacenamiento y Memorias', TEC, 13.00,
      'Memoria USB 3.2 de 128 GB con velocidades de lectura de hasta 100 MB/s. Diseño compacto con tapa deslizante.',
      (STUDIO.format(what='a small black and red USB flash drive with sliding connector'),
       ALT.format(what='USB flash drive plugged into a laptop USB port, close-up, desk')),
      attrs={'tipo_memoria': 'Pendrive / Memoria USB', 'marca': 'SanDisk', 'capacidad': '128 GB', 'garantia': '3 meses'},
      variants=[V({'capacity': '64 GB', 'format': 'USB 3.2'}, 30, 9.00), V({'capacity': '128 GB', 'format': 'USB 3.2'}, 35),
                V({'capacity': '256 GB', 'format': 'USB 3.2'}, 14, 22.00)],
      tokens=None, offer=10),
    P('combo-teclado-mouse', 'Combo Teclado y Mouse Inalámbrico', 'Teclados y Mouse', TEC, 28.00,
      'Combo inalámbrico 2.4 GHz con teclado en español (con Ñ) y mouse ergonómico de 1000 DPI. Receptor USB compartido '
      'y hasta 12 meses de batería en el mouse.',
      (STUDIO.format(what='a black wireless keyboard and a matching ergonomic wireless mouse'),
       ALT.format(what='wireless keyboard and mouse on a tidy home office desk with a laptop, top view')),
      attrs={'tipo_periferico': 'Combo Teclado + Mouse', 'marca': 'Soy Techno', 'conectividad': 'Inalámbrico USB (Receptor)',
             'idioma_distribucion': 'Español (Con letra Ñ)', 'garantia': '3 meses'},
      variants=[V({'color': 'Negro', 'switch_or_conn': '2.4 GHz'}, 16), V({'color': 'Blanco', 'switch_or_conn': '2.4 GHz'}, 8)],
      tokens=TOK_B, offer=0),
    P('router-wifi6-ax1800', 'Router Wi-Fi 6 AX1800 Doble Banda', 'Redes, Routers y Conectividad', TEC, 59.00,
      'Router Wi-Fi 6 de doble banda con 4 antenas, 4 puertos Gigabit y cobertura para hogares de hasta 3 habitaciones. '
      'Instalación en minutos desde el teléfono.',
      (STUDIO.format(what='a white Wi-Fi 6 router with four antennas'),
       ALT.format(what='white Wi-Fi router on a shelf in a bright living room, subtle blue status lights')),
      attrs={'tipo_equipo_red': 'Router Wi-Fi Dual Band / Wi-Fi 6', 'marca': 'TP-Link', 'puertos_velocidad': '4 x Gigabit / AX1800',
             'garantia': '6 meses'},
      variants=[V({'version': 'AX1800'}, 11), V({'version': 'AX3000'}, 5, 89.00)],
      tokens=TOK_A, offer=12),
]

# ----------------------------------------------------------------------------------------------------------------------
# 2) EPA — Ferretería
# ----------------------------------------------------------------------------------------------------------------------
FER = 'Ferretería y Construcción'
EPA_PRODUCTS = [
    P('taladro-percutor-13mm', 'Taladro Percutor 13 mm 650 W', 'Herramientas Eléctricas, Taladros y Esmeriles', FER, 64.00,
      'Taladro percutor de 650 W con mandril de 13 mm, velocidad variable y reversa. Ideal para concreto, madera y metal. '
      'Incluye empuñadura lateral y tope de profundidad.',
      (STUDIO.format(what='a corded electric hammer drill in blue and black with side handle'),
       ALT.format(what='electric drill drilling into a concrete wall, dust particles, workshop light')),
      attrs={'marca': 'Bosch Professional', 'tipo_alimentacion': 'Eléctrica con Cable (110V)', 'potencia': '650 W',
             'garantia': '6 meses'},
      variants=[V({'spec': '650 W / 13 mm'}, 14), V({'spec': '800 W / 13 mm'}, 6, 79.00)],
      mods=[M('Accesorios', [('Set de 13 brocas multimaterial', 8), ('Maletín plástico', 7),
                             ('Garantía extendida +6 meses', 9)], max_sel=3)],
      tokens=TOK_A, offer=10),
    P('esmeril-angular-4-5', 'Esmeril Angular 4½" 850 W', 'Herramientas Eléctricas, Taladros y Esmeriles', FER, 48.00,
      'Esmeril angular de 850 W y 11.000 rpm con guarda ajustable y mango lateral antivibración. Para corte y desbaste de '
      'metal, concreto y cerámica.',
      (STUDIO.format(what='a corded angle grinder with side handle, yellow and black body'),
       ALT.format(what='angle grinder cutting metal with bright sparks flying, safety gloves, dark workshop')),
      attrs={'marca': 'DeWalt', 'tipo_alimentacion': 'Eléctrica con Cable (110V)', 'potencia': '850 W', 'garantia': '6 meses'},
      variants=[V({'spec': '4½" / 850 W'}, 12), V({'spec': '7" / 2200 W'}, 4, 118.00)],
      mods=[M('Discos', [('Pack 5 discos de corte metal', 6), ('Disco diamantado para concreto', 9)], max_sel=2)],
      tokens=None, offer=0),
    P('taladro-inalambrico-20v', 'Taladro Atornillador Inalámbrico 20V con 2 Baterías', 'Herramientas Eléctricas, Taladros y Esmeriles', FER, 89.00,
      'Taladro atornillador de 20 V con 2 baterías de ion-litio, cargador rápido, 21 posiciones de torque y luz LED. Entrega '
      'en maletín con 30 accesorios.',
      (STUDIO.format(what='a cordless drill driver 20V with two batteries, charger and carrying case open'),
       ALT.format(what='cordless drill screwing a screw into wood plank, workbench, warm light')),
      attrs={'marca': 'Black+Decker', 'tipo_alimentacion': 'Inalámbrica (Batería Ion-Litio)', 'potencia': '20 V / 2.0 Ah',
             'garantia': '1 año'},
      variants=[V({'spec': '20V + 2 baterías'}, 9), V({'spec': '20V + 1 batería'}, 7, 69.00)],
      tokens=TOK_B, offer=15),
    P('llaves-combinadas-12', 'Juego de Llaves Combinadas 12 Piezas (8-19 mm)', 'Herramientas Manuales', FER, 28.00,
      'Set de 12 llaves combinadas en acero cromo-vanadio, acabado espejo y estuche organizador. Medidas de 8 a 19 mm.',
      (STUDIO.format(what='a set of twelve chrome vanadium combination wrenches arranged in a fan shape'),
       ALT.format(what='combination wrenches in a rolled canvas pouch on a wooden workbench, top view')),
      unit='set',
      attrs={'marca': 'Stanley', 'medida_piezas': '12 piezas / 8 a 19 mm', 'garantia': '1 año'},
      variants=[V({'size': 'Métrico 8-19 mm'}, 15), V({'size': 'Pulgadas 1/4"-3/4"'}, 10, 30.00)],
      tokens=TOK_A, offer=0),
    P('martillo-una-16oz', 'Martillo de Uña 16 oz Mango de Fibra', 'Herramientas Manuales', FER, 11.00,
      'Martillo de carpintero con cabeza forjada de 16 oz y mango de fibra de vidrio con empuñadura antideslizante.',
      (STUDIO.format(what='a claw hammer with a fiberglass handle with black rubber grip'),
       ALT.format(what='claw hammer and a few nails on a rustic wooden plank, close-up')),
      attrs={'marca': 'Truper', 'medida_piezas': '16 oz', 'garantia': '3 meses'},
      variants=sizes('size', ['8 oz', '16 oz', '20 oz'], stock=10),
      tokens=None, offer=0),
    P('kit-herramientas-120', 'Kit de Herramientas 120 Piezas con Maletín', 'Herramientas Manuales', FER, 69.00,
      'Maletín con 120 piezas: dados, llaves, destornilladores, alicates, extensiones y cinta métrica. Todo lo que '
      'necesitas para el hogar o el taller.',
      (STUDIO.format(what='a large open red and black toolbox case with 120 piece socket and tool set neatly organized'),
       ALT.format(what='tool kit case open on a garage floor with sockets and screwdrivers, overhead view')),
      unit='set',
      attrs={'marca': 'Pretul', 'medida_piezas': '120 piezas', 'garantia': '6 meses'},
      variants=[V({'size': '120 piezas'}, 10), V({'size': '216 piezas'}, 4, 109.00)],
      mods=[M('Complementos', [('Guantes de trabajo', 4), ('Linterna LED recargable', 9)], max_sel=2)],
      tokens=TOK_B, offer=20),
    P('cinta-metrica-5m', 'Cinta Métrica 5 m x 19 mm', 'Herramientas Manuales', FER, 4.50,
      'Flexómetro con cinta de acero, freno automático y carcasa antigolpes con clip para el cinturón.',
      (STUDIO.format(what='a yellow tape measure with locking button and belt clip'),
       ALT.format(what='tape measure being pulled out over a wooden board, close-up with metric markings')),
      attrs={'marca': 'Stanley', 'medida_piezas': '5 m x 19 mm', 'garantia': '3 meses'},
      variants=sizes('size', ['3 m', '5 m', '8 m'], stock=20),
      tokens=None, offer=0),
    P('cable-thhn-12', 'Cable Eléctrico THHN #12 AWG (por metro)', 'Electricidad, Cables, Breakers y Tomacorrientes', FER, 0.85,
      'Cable de cobre THHN calibre 12 AWG, aislamiento termoplástico, 600 V. Se vende por metro; compra la cantidad que necesites.',
      (STUDIO.format(what='a coil of black insulated electrical copper wire'),
       ALT.format(what='colored electrical wires red black white green coiled together, close-up, workshop')),
      unit='m',
      attrs={'marca': 'Cabel', 'especificacion_electrica': 'THHN #12 AWG, 600 V'},
      variants=[V({'gauge_or_amp': '#12 AWG', 'sale_format': 'Negro'}, 300), V({'gauge_or_amp': '#12 AWG', 'sale_format': 'Rojo'}, 250),
                V({'gauge_or_amp': '#12 AWG', 'sale_format': 'Blanco'}, 280), V({'gauge_or_amp': '#12 AWG', 'sale_format': 'Verde'}, 150)],
      tokens=None, offer=0),
    P('breaker-1p', 'Breaker Termomagnético 1 Polo', 'Electricidad, Cables, Breakers y Tomacorrientes', FER, 5.50,
      'Interruptor termomagnético de 1 polo con montaje en riel DIN. Protección contra sobrecarga y cortocircuito, 120/240 V.',
      (STUDIO.format(what='a white single pole circuit breaker DIN rail mount'),
       ALT.format(what='electrical panel with several circuit breakers installed, close-up, technician hand')),
      attrs={'marca': 'Siemens', 'especificacion_electrica': '1P, 120/240 V, riel DIN'},
      variants=[V({'gauge_or_amp': '15 A', 'sale_format': 'Unidad'}, 30, 5.00), V({'gauge_or_amp': '20 A', 'sale_format': 'Unidad'}, 40),
                V({'gauge_or_amp': '30 A', 'sale_format': 'Unidad'}, 25, 6.50), V({'gauge_or_amp': '40 A', 'sale_format': 'Unidad'}, 0, 7.50)],
      tokens=TOK_A, offer=10),
    P('bombillo-led-9w-x4', 'Bombillo LED 9 W E27 (Pack x4)', 'Bombillos, Reflectores e Iluminación LED', FER, 7.50,
      'Pack de 4 bombillos LED de 9 W (equivalen a 60 W) con rosca E27. Ahorran hasta 85 % de energía y duran 15.000 horas.',
      (STUDIO.format(what='four LED light bulbs E27 arranged in a row'),
       ALT.format(what='warm glowing LED bulb in a ceiling socket lighting a cozy room')),
      unit='pack',
      attrs={'marca': 'Philips', 'rosca_montaje': 'Rosca E27 (Estándar)', 'voltaje': 'Multivoltaje (85V-265V)', 'garantia': '6 meses'},
      variants=[V({'wattage': '9 W', 'light_tone': 'Luz cálida 3000K'}, 35), V({'wattage': '9 W', 'light_tone': 'Luz fría 6500K'}, 40),
                V({'wattage': '12 W', 'light_tone': 'Luz fría 6500K'}, 20, 9.50)],
      tokens=None, offer=15),
    P('reflector-led-50w', 'Reflector LED 50 W IP65 Exterior', 'Bombillos, Reflectores e Iluminación LED', FER, 14.00,
      'Reflector LED de 50 W con carcasa de aluminio y resistencia al agua IP65. Luz fría, ideal para fachadas, patios y galpones.',
      (STUDIO.format(what='a flat rectangular LED floodlight 50W with aluminum housing and bracket'),
       ALT.format(what='LED floodlight illuminating the exterior wall of a house at night')),
      attrs={'marca': 'Sylvania', 'rosca_montaje': 'Reflector Exterior IP65/IP66', 'voltaje': 'Multivoltaje (85V-265V)', 'garantia': '6 meses'},
      variants=[V({'wattage': '30 W', 'light_tone': 'Luz fría 6500K'}, 18, 10.00), V({'wattage': '50 W', 'light_tone': 'Luz fría 6500K'}, 22),
                V({'wattage': '100 W', 'light_tone': 'Luz fría 6500K'}, 10, 22.00)],
      tokens=TOK_B, offer=0),
    P('pintura-caucho-galon', 'Pintura de Caucho Clase A Interior/Exterior', 'Pinturas, Cuñetes, Brochas y Selladores', FER, 18.00,
      'Pintura de caucho lavable de alto rendimiento (hasta 40 m² por galón). Acabado mate, secado rápido y excelente cubrición.',
      (STUDIO.format(what='a one gallon white paint bucket with metal handle and a paint brush on the lid, blank label'),
       ALT.format(what='roller painting a wall with fresh white paint, room being renovated, natural light')),
      unit='gal',
      attrs={'marca': 'Montana', 'tipo_pintura': 'Pintura de Caucho Interior/Exterior'},
      variants=[V({'presentation': '1 galón', 'color': 'Blanco'}, 24), V({'presentation': '1 galón', 'color': 'Hueso'}, 14),
                V({'presentation': '1 galón', 'color': 'Gris Perla'}, 10), V({'presentation': 'Cuñete 4 galones', 'color': 'Blanco'}, 7, 62.00)],
      mods=[M('Servicios y complementos', [('Entonado a color personalizado', 3), ('Brocha de 4"', 3.5), ('Rodillo + bandeja', 6)], max_sel=3)],
      tokens=TOK_A, offer=10),
    P('cemento-gris-42kg', 'Cemento Gris Portland 42.5 kg', 'Cementos, Pegos, Mallas y Bloques', FER, 9.80,
      'Saco de cemento gris Portland tipo I de 42.5 kg para obras, repellos, losas y concreto estructural.',
      (STUDIO.format(what='a gray paper cement bag, 42.5 kg, blank label'),
       ALT.format(what='stack of cement bags at a construction site with bricks, daylight')),
      attrs={'marca': 'Cemex', 'peso_rendimiento': '42.5 kg'},
      variants=[V({'presentation': 'Saco 42.5 kg'}, 120), V({'presentation': 'Pallet 40 sacos'}, 6, 360.00)],
      tokens=None, offer=0),
    P('candado-alta-seguridad', 'Candado de Alta Seguridad 60 mm', 'Cerraduras, Candados y Cilindros', FER, 11.50,
      'Candado de acero con arco endurecido y cuerpo laminado, cilindro antitaladro e incluye 3 llaves. Para portones, '
      'galpones y rejas.',
      (STUDIO.format(what='a heavy duty steel padlock with hardened shackle and brass keys'),
       ALT.format(what='padlock securing a metal gate chain, close-up, outdoor light')),
      attrs={'marca': 'Yale', 'tipo_cerradura': 'Candado'},
      variants=sizes('finish_or_size', ['40 mm', '50 mm', '60 mm', '70 mm'], stock=12),
      tokens=TOK_A, offer=0),
    P('botas-seguridad-punta-acero', 'Botas de Seguridad Punta de Acero', 'Seguridad Industrial, Guantes y Botas', FER, 39.00,
      'Botas de cuero con puntera de acero, suela antideslizante y resistente a aceites. Cumplen normas de seguridad industrial.',
      (STUDIO.format(what='a pair of brown leather safety work boots with steel toe'),
       ALT.format(what='worker wearing safety boots standing at a construction site, low angle shot of boots')),
      unit='pair',
      attrs={'marca': 'Tigre', 'proteccion': 'Punta de Hierro / Acero'},
      variants=grid('size', ['39', '40', '41', '42', '43'], 'color', ['Marrón'], stock=5, sold_out=[('43', 'Marrón')])
               + grid('size', ['41', '42'], 'color', ['Negro'], stock=4),
      mods=[M('Complementos', [('Plantillas ortopédicas', 6), ('Medias térmicas (par)', 4)], max_sel=2)],
      tokens=TOK_B, offer=15),
]

# ----------------------------------------------------------------------------------------------------------------------
# 3) MovilHogar — Mueblería y artículos para el hogar
# ----------------------------------------------------------------------------------------------------------------------
HOG = 'Hogar, Muebles y Jardín'
MOVILHOGAR_PRODUCTS = [
    P('sofa-3-puestos', 'Sofá 3 Puestos en Tela Antifluidos', 'Muebles de Sala y Comedor', HOG, 389.00,
      'Sofá de 3 puestos con estructura de madera de pino, espuma de alta densidad y tapizado en tela antifluidos fácil de '
      'limpiar. Patas en madera maciza.',
      (STUDIO.format(what='a modern three seater fabric sofa in light gray with wooden legs'),
       ALT.format(what='gray fabric sofa in a bright modern living room with cushions, plant and rug')),
      attrs={'material_principal': 'Madera de pino, espuma HR y tela antifluidos', 'dimensiones': '200 x 85 x 90 cm',
             'requiere_armado': 'Se entrega armado', 'garantia': '1 año'},
      variants=[V({'color_finish': 'Gris Grafito'}, 5), V({'color_finish': 'Beige Arena'}, 4), V({'color_finish': 'Azul Petróleo'}, 0)],
      mods=[M('Personaliza tu sofá', [('Tapizado premium (tela chenille)', 45), ('Patas metálicas negras', 18)]),
            M('Servicios', [('Entrega e instalación en Caracas', 15), ('Retiro del mueble anterior', 12)], max_sel=2)],
      tokens=TOK_A, offer=10),
    P('comedor-6-puestos', 'Juego de Comedor 6 Puestos Madera y Vidrio', 'Muebles de Sala y Comedor', HOG, 429.00,
      'Mesa rectangular con tope de vidrio templado de 8 mm, base de madera y 6 sillas tapizadas en cuero sintético. '
      'Incluye herrajes y manual de armado.',
      (STUDIO.format(what='a modern dining set with a glass top rectangular table and six upholstered chairs'),
       ALT.format(what='dining table with glass top and six chairs in an elegant dining room with a pendant lamp')),
      unit='set',
      attrs={'material_principal': 'Madera MDF, vidrio templado y cuero sintético', 'dimensiones': 'Mesa 160 x 90 x 76 cm',
             'requiere_armado': 'En caja (Requiere armado)', 'garantia': '6 meses'},
      variants=[V({'color_finish': 'Nogal / Negro'}, 4), V({'color_finish': 'Blanco / Gris'}, 3), V({'color_finish': 'Roble / Beige'}, 2)],
      mods=[M('Servicios', [('Armado a domicilio', 25), ('Entrega prioritaria 48 h', 10)], max_sel=2)],
      tokens=TOK_B, offer=15),
    P('mesa-centro-roble', 'Mesa de Centro Roble con Estante', 'Muebles de Sala y Comedor', HOG, 89.00,
      'Mesa de centro de diseño minimalista con tope de roble y estante inferior para revistas. Patas con acabado en negro mate.',
      (STUDIO.format(what='a minimalist oak coffee table with lower shelf and black metal legs'),
       ALT.format(what='oak coffee table in front of a sofa with a book and vase, cozy living room')),
      attrs={'material_principal': 'Roble y acero', 'dimensiones': '100 x 50 x 42 cm', 'requiere_armado': 'En caja (Requiere armado)',
             'garantia': '3 meses'},
      variants=[V({'color_finish': 'Roble Natural'}, 8), V({'color_finish': 'Nogal Oscuro'}, 6)],
      tokens=None, offer=0),
    P('rack-tv-65', 'Mueble Rack para TV hasta 65"', 'Muebles de Sala y Comedor', HOG, 119.00,
      'Rack flotante con 2 puertas y repisas abiertas, pasacables ocultos y soporte para televisores de hasta 65" y 40 kg.',
      (STUDIO.format(what='a modern TV stand cabinet with doors and open shelves in walnut and white'),
       ALT.format(what='TV stand with a large TV on, decor items and plants, living room, warm light')),
      attrs={'material_principal': 'MDF melamínico', 'dimensiones': '180 x 45 x 40 cm', 'requiere_armado': 'En caja (Requiere armado)',
             'garantia': '6 meses'},
      variants=[V({'color_finish': 'Nogal / Blanco'}, 7), V({'color_finish': 'Negro / Gris'}, 5)],
      mods=[M('Servicios', [('Armado a domicilio', 20)])],
      tokens=TOK_A, offer=20),
    P('colchon-ortopedico-pillow', 'Colchón Ortopédico Pillow Top', 'Camas, Colchones y Box Spring', HOG, 259.00,
      'Colchón ortopédico de doble acolchado (pillow top) con resortes bonnell y espuma viscoelástica. 24 cm de altura, '
      'soporte firme para la espalda.',
      (STUDIO.format(what='a thick white pillow top mattress seen from a three quarter angle'),
       ALT.format(what='mattress cross section showing layers of foam and springs, studio, soft light')),
      attrs={'marca': 'Springwall', 'tipo_colchon': 'Pillow Top (Doble Acolchado)', 'garantia': '2 años'},
      variants=[V({'bed_size': 'Individual', 'include_box': 'Solo colchón'}, 6, 169.00),
                V({'bed_size': 'Matrimonial', 'include_box': 'Solo colchón'}, 8, 219.00),
                V({'bed_size': 'Queen', 'include_box': 'Solo colchón'}, 6),
                V({'bed_size': 'King', 'include_box': 'Solo colchón'}, 3, 339.00)],
      mods=[M('Complementos', [('Protector impermeable', 22), ('Par de almohadas viscoelásticas', 34)], max_sel=2)],
      tokens=TOK_A, offer=12),
    P('box-spring-matrimonial', 'Base de Cama Box Spring', 'Camas, Colchones y Box Spring', HOG, 179.00,
      'Base box spring con estructura de madera tratada y tapizado en tela, ideal para combinar con cualquier colchón.',
      (STUDIO.format(what='a upholstered gray box spring bed base with wooden feet'),
       ALT.format(what='bedroom with a box spring bed base and neatly made white bedding, minimal decor')),
      attrs={'marca': 'Springwall', 'tipo_colchon': 'Resortes Pocket (Independientes)', 'garantia': '1 año'},
      variants=[V({'bed_size': 'Matrimonial', 'include_box': 'Con patas'}, 5), V({'bed_size': 'Queen', 'include_box': 'Con patas'}, 4, 219.00),
                V({'bed_size': 'King', 'include_box': 'Con patas'}, 2, 279.00)],
      tokens=None, offer=0),
    P('sabanas-microfibra-4pz', 'Juego de Sábanas Microfibra 4 Piezas', 'Sábanas, Edredones y Toallas', HOG, 24.00,
      'Sábanas suaves de microfibra de 1800 hilos: bajera ajustable, sábana superior y 2 fundas de almohada. '
      'No se destiñen ni se arrugan.',
      (STUDIO.format(what='a neatly folded stack of microfibre bed sheets in light blue with matching pillowcases'),
       ALT.format(what='bed with fresh microfibre sheets in soft blue, morning light, bedroom')),
      unit='set',
      attrs={'material_hilos': 'Microfibra 1800 hilos', 'piezas_incluidas': '4 piezas'},
      variants=grid('bed_size', ['Matrimonial', 'Queen', 'King'], 'color', ['Blanco', 'Gris', 'Azul'], stock=7,
                    sold_out=[('King', 'Azul')]),
      tokens=TOK_B, offer=0),
    P('edredon-reversible-queen', 'Edredón Reversible Comforter', 'Sábanas, Edredones y Toallas', HOG, 49.00,
      'Comforter reversible rellenado de fibra hueca siliconada, suave y abrigador. Incluye 2 fundas decorativas.',
      (STUDIO.format(what='a folded reversible comforter in beige and charcoal gray with two matching pillow covers'),
       ALT.format(what='bed dressed with a reversible comforter in warm beige, decorative pillows, cozy bedroom')),
      unit='set',
      attrs={'material_hilos': 'Microfibra con relleno de fibra hueca', 'piezas_incluidas': 'Comforter + 2 fundas'},
      variants=[V({'bed_size': 'Matrimonial', 'color': 'Beige / Gris'}, 8, 42.00), V({'bed_size': 'Queen', 'color': 'Beige / Gris'}, 9),
                V({'bed_size': 'King', 'color': 'Beige / Gris'}, 5, 59.00)],
      tokens=None, offer=18),
    P('toallas-algodon-x6', 'Set de 6 Toallas 100% Algodón', 'Sábanas, Edredones y Toallas', HOG, 29.00,
      'Set de 2 toallas de baño, 2 de mano y 2 faciales de algodón peinado de 500 g/m². Muy absorbentes y de secado rápido.',
      (STUDIO.format(what='a stack of six fluffy cotton towels in white and gray, rolled and folded'),
       ALT.format(what='fluffy towels on a wooden stool in a bright bathroom with a plant')),
      unit='pack',
      attrs={'material_hilos': 'Algodón peinado 500 g/m²', 'piezas_incluidas': '6 piezas'},
      variants=[V({'bed_size': 'Set x6', 'color': 'Blanco'}, 15), V({'bed_size': 'Set x6', 'color': 'Gris'}, 12), V({'bed_size': 'Set x6', 'color': 'Beige'}, 10)],
      mods=[M('Personaliza', [('Bordado con iniciales', 7)])],
      tokens=TOK_A, offer=0),
    P('bateria-cocina-7pz', 'Batería de Cocina Antiadherente 7 Piezas', 'Ollas, Sartenes y Utensilios de Cocina', HOG, 69.00,
      'Set de 7 piezas con 2 ollas con tapa, 1 sartén, 1 caserola y utensilios. Antiadherente libre de PFOA, base apta para '
      'cocina de gas, eléctrica e inducción.',
      (STUDIO.format(what='a set of black non-stick cookware pots and pans with glass lids and utensils'),
       ALT.format(what='non-stick frying pan with vegetables cooking on a stove in a modern kitchen')),
      unit='set',
      attrs={'marca': 'Tramontina', 'material': 'Aluminio / Antiadherente (Teflón)'},
      variants=[V({'size_or_set': 'Set 7 piezas Negro'}, 12), V({'size_or_set': 'Set 7 piezas Rojo'}, 6), V({'size_or_set': 'Set 12 piezas Negro'}, 4, 109.00)],
      mods=[M('Complementos', [('Set de utensilios de silicón', 11)])],
      tokens=TOK_A, offer=15),
    P('licuadora-1200w', 'Licuadora 1200 W Jarra de Vidrio 1.5 L', 'Pequeños Electrodomésticos y Cocina', HOG, 79.00,
      'Licuadora de 1200 W con 6 velocidades y función pulso, jarra de vidrio de 1.5 L y cuchillas de acero inoxidable. '
      'Tritura hielo y prepara batidos al instante.',
      (STUDIO.format(what='a modern blender with glass jar and black base'),
       ALT.format(what='blender making a strawberry smoothie, fruits around on a kitchen counter')),
      attrs={'marca': 'Oster', 'capacidad_potencia': '1200 W / 1.5 L', 'voltaje': '110V', 'garantia': '1 año'},
      variants=[V({'capacity_color': '1.5 L Negro'}, 10), V({'capacity_color': '1.5 L Rojo'}, 6)],
      tokens=TOK_B, offer=0),
    P('freidora-aire-5l', 'Freidora de Aire Digital 5.5 L', 'Pequeños Electrodomésticos y Cocina', HOG, 89.00,
      'Cocina con 85 % menos aceite: pantalla táctil digital, 8 programas, temperatura de 80 a 200 °C y cesta antiadherente '
      'de 5.5 L.',
      (STUDIO.format(what='a black digital air fryer with a front touch panel and removable basket'),
       ALT.format(what='air fryer with golden crispy french fries and chicken on the kitchen counter')),
      attrs={'marca': 'Cosori', 'capacidad_potencia': '1700 W / 5.5 L', 'voltaje': '110V', 'garantia': '1 año'},
      variants=[V({'capacity_color': '5.5 L Negro'}, 9), V({'capacity_color': '5.5 L Blanco'}, 5)],
      tokens=TOK_A, offer=20),
    P('ventilador-pedestal-18', 'Ventilador de Pedestal 18" 3 Velocidades', 'Aires Acondicionados y Ventiladores', HOG, 42.00,
      'Ventilador de pedestal con altura regulable, oscilación de 90°, inclinación ajustable y 3 velocidades. Aspas de 18" '
      'y motor de cobre.',
      (STUDIO.format(what='a white pedestal fan with adjustable height standing on a white background'),
       ALT.format(what='pedestal fan in a warm living room with curtains moving in the breeze')),
      attrs={'marca': 'Mytek', 'tipo_equipo': 'Ventilador de Pedestal / Pared', 'capacidad_btu': 'N/A', 'voltaje': '110V',
             'garantia': '6 meses'},
      variants=[V({'btu_or_size': '18"', 'voltage': '110V'}, 14), V({'btu_or_size': '20" industrial', 'voltage': '110V'}, 5, 58.00)],
      tokens=None, offer=0),
    P('espejo-redondo-80', 'Espejo Redondo Decorativo 80 cm Marco Dorado', 'Decoración, Cuadros y Espejos', HOG, 54.00,
      'Espejo redondo de pared con marco metálico dorado mate. Incluye herrajes de instalación y gancho reforzado.',
      (STUDIO.format(what='a round wall mirror with a thin matte gold metal frame'),
       ALT.format(what='round gold framed mirror on a living room wall above a console table with a vase')),
      attrs={'dimensiones': '80 cm de diámetro', 'material': 'Vidrio y aluminio'},
      variants=[V({'variant': '60 cm'}, 8, 39.00), V({'variant': '80 cm'}, 10), V({'variant': '100 cm'}, 3, 79.00)],
      tokens=TOK_A, offer=10),
    P('cuadros-abstractos-x3', 'Set de 3 Cuadros Decorativos Abstractos', 'Decoración, Cuadros y Espejos', HOG, 39.00,
      'Tres cuadros en lienzo con marco de madera, impresión de alta definición y tonos tierra. Listos para colgar.',
      (STUDIO.format(what='three abstract art canvases in earth tones with thin wooden frames leaning together'),
       ALT.format(what='triptych of three abstract canvas paintings hung above a sofa in a modern living room')),
      unit='set',
      attrs={'dimensiones': '3 piezas de 40 x 60 cm', 'material': 'Lienzo y madera'},
      variants=[V({'variant': 'Tonos tierra'}, 11), V({'variant': 'Azules y dorado'}, 7)],
      mods=[M('Personaliza', [('Cambia el tamaño a 50 x 70 cm c/u', 15), ('Marco blanco en lugar de madera', 6)])],
      tokens=None, offer=0),
]

# ----------------------------------------------------------------------------------------------------------------------
# 4) HERO — Ropa deportiva
# ----------------------------------------------------------------------------------------------------------------------
DEP = 'Deportes y Fitness'
RD = 'Ropa Deportiva, Monos y Licras'
NAME_PRINT = M('Personaliza tu prenda', [('Estampado de nombre', 4), ('Número en la espalda', 2), ('Logo de tu equipo', 6)], max_sel=3)
HERO_PRODUCTS = [
    P('conjunto-seamless-dama', 'Conjunto Deportivo Seamless Dama (Top + Legging)', RD, DEP, 32.00,
      'Conjunto sin costuras de top con soporte medio y legging de tiro alto. Tela elástica transpirable que se adapta al '
      'cuerpo y no transparenta.',
      (STUDIO.format(what='a seamless women sports set top and high waisted leggings in dusty rose displayed flat'),
       ALT.format(what='woman wearing a seamless pink sports set doing yoga stretch in a bright studio')),
      unit='set',
      attrs={'marca': 'HERO', 'genero': 'Dama', 'tela': 'Seamless nylon-elastano'},
      variants=grid('size', ['S', 'M', 'L'], 'color', ['Rosa Palo', 'Negro', 'Verde Salvia'], stock=6, sold_out=[('L', 'Verde Salvia')]),
      mods=[M('Personalización', [('Bordado de nombre en el top', 5)])],
      tokens=TOK_A, offer=15),
    P('legging-push-up', 'Legging Levanta Cola Alta Compresión', RD, DEP, 19.00,
      'Legging de tiro alto con costuras anti-roce y efecto levanta cola. Compresión media, tela suplex que no se transparenta.',
      (STUDIO.format(what='high waisted black sports leggings displayed flat with a subtle scrunch seam on the back'),
       ALT.format(what='woman wearing black high waisted leggings in a gym, back view, natural gym light')),
      attrs={'marca': 'HERO', 'genero': 'Dama', 'tela': 'Suplex premium'},
      variants=grid('size', ['S', 'M', 'L', 'XL'], 'color', ['Negro', 'Vinotinto', 'Gris'], stock=7),
      tokens=None, offer=0),
    P('top-deportivo-soporte-medio', 'Top Deportivo Soporte Medio', RD, DEP, 14.00,
      'Top deportivo con copas removibles, espalda en Y y tela de secado rápido. Soporte medio para gym, yoga y running.',
      (STUDIO.format(what='a black medium support sports bra top with Y back displayed flat'),
       ALT.format(what='woman doing a workout wearing a sports top, gym background, side angle')),
      attrs={'marca': 'HERO', 'genero': 'Dama', 'tela': 'Microfibra dry-fit'},
      variants=grid('size', ['XS', 'S', 'M', 'L'], 'color', ['Negro', 'Blanco', 'Fucsia'], stock=6),
      tokens=TOK_B, offer=10),
    P('biker-short-dama', 'Short Biker Deportivo Dama', RD, DEP, 12.00,
      'Short biker de tiro alto y 20 cm de largo, con bolsillo lateral para el celular. Tela elástica de compresión suave.',
      (STUDIO.format(what='black high waisted biker shorts with a side pocket displayed flat'),
       ALT.format(what='woman wearing black biker shorts and a top stretching in a park, golden hour')),
      attrs={'marca': 'HERO', 'genero': 'Dama', 'tela': 'Suplex'},
      variants=grid('size', ['S', 'M', 'L'], 'color', ['Negro', 'Azul Marino', 'Rojo'], stock=8),
      tokens=None, offer=0),
    P('franela-dryfit-running', 'Franela Dry-Fit Caballero Running', RD, DEP, 15.00,
      'Franela deportiva de secado rápido, tela ligera con paneles de ventilación y costuras planas. Protección UV 30+.',
      (STUDIO.format(what='a men sports running t-shirt in royal blue dry fit mesh displayed flat'),
       ALT.format(what='male runner wearing a blue dry fit running shirt on an urban street at sunrise')),
      attrs={'marca': 'HERO', 'genero': 'Caballero', 'tela': 'Poliéster dry-fit'},
      variants=grid('size', ['S', 'M', 'L', 'XL'], 'color', ['Azul Rey', 'Negro', 'Gris'], stock=8, sold_out=[('XL', 'Gris')]),
      mods=[NAME_PRINT],
      tokens=TOK_A, offer=0),
    P('mono-jogger-caballero', 'Mono Jogger Algodón Caballero', RD, DEP, 26.00,
      'Jogger cómodo de algodón perchado con bolsillos laterales con cierre, cordón ajustable y puños elásticos. '
      'Ideal para entrenar o para uso diario.',
      (STUDIO.format(what='gray cotton jogger sweatpants with elastic cuffs displayed flat'),
       ALT.format(what='man wearing gray jogger sweatpants and sneakers walking in the city, lower body shot')),
      attrs={'marca': 'HERO', 'genero': 'Caballero', 'tela': 'Algodón perchado'},
      variants=grid('size', ['S', 'M', 'L', 'XL'], 'color', ['Gris Jaspe', 'Negro', 'Azul Marino'], stock=6),
      tokens=TOK_B, offer=12),
    P('chaqueta-rompevientos-unisex', 'Chaqueta Rompevientos Unisex', RD, DEP, 34.00,
      'Chaqueta ligera impermeable con capucha empacable, cierre completo y bolsillos con cierre. Para running y outdoor.',
      (STUDIO.format(what='a lightweight windbreaker jacket in black with neon yellow details and hood'),
       ALT.format(what='runner wearing a black windbreaker jacket on a mountain trail, windy day')),
      attrs={'marca': 'HERO', 'genero': 'Unisex', 'tela': 'Nylon ripstop impermeable'},
      variants=grid('size', ['S', 'M', 'L', 'XL'], 'color', ['Negro', 'Azul Rey'], stock=5),
      mods=[M('Personalización', [('Logo de tu equipo en el pecho', 6), ('Nombre en la espalda', 5)], max_sel=2)],
      tokens=TOK_A, offer=20),
    P('short-gym-2en1', 'Short Deportivo 2 en 1 Doble Capa', RD, DEP, 17.00,
      'Short con licra interna de compresión, bolsillo trasero con cierre y tela ligera de secado rápido. Ideal para gym, '
      'crossfit y running.',
      (STUDIO.format(what='black sports shorts 2 in 1 with inner compression liner displayed flat'),
       ALT.format(what='man doing squats in a gym wearing black sports shorts, side view')),
      attrs={'marca': 'HERO', 'genero': 'Caballero', 'tela': 'Poliéster / licra'},
      variants=grid('size', ['S', 'M', 'L', 'XL'], 'color', ['Negro', 'Azul Marino', 'Gris'], stock=7),
      tokens=None, offer=0),
    P('franela-compresion-ml', 'Franela de Compresión Manga Larga', RD, DEP, 18.00,
      'Camiseta de compresión manga larga, base layer para entrenamiento y deportes de contacto. Costuras planas y '
      'tecnología anti-olor.',
      (STUDIO.format(what='a black long sleeve compression athletic shirt displayed flat'),
       ALT.format(what='athletic man in black compression shirt flexing in a dark gym with dramatic light')),
      attrs={'marca': 'HERO', 'genero': 'Caballero', 'tela': 'Elastano compresión'},
      variants=grid('size', ['S', 'M', 'L', 'XL'], 'color', ['Negro', 'Blanco'], stock=6),
      mods=[NAME_PRINT],
      tokens=TOK_B, offer=0),
    P('zapatos-running-ligeros', 'Zapatos Running Ligeros Hero Pro', 'Zapatos Deportivos y Gomas', DEP, 49.00,
      'Zapatillas de running con malla transpirable, mediasuela de espuma de alto retorno y suela de goma antideslizante. '
      'Solo 240 g por zapato.',
      (STUDIO.format(what='a single lightweight running shoe in white and electric blue, side profile'),
       ALT.format(what='pair of running shoes on an asphalt track with a runner blurred in the background')),
      unit='pair',
      attrs={'marca': 'HERO', 'disciplina': 'Running / Maratón', 'genero': 'Unisex'},
      variants=grid('shoe_size', ['38', '39', '40', '41', '42', '43', '44'], 'color', ['Blanco / Azul'], stock=4, sold_out=[('44', 'Blanco / Azul')]),
      mods=[M('Complementos', [('Plantillas deportivas con soporte de arco', 6), ('Medias deportivas (par)', 3)], max_sel=2)],
      tokens=TOK_A, offer=15),
    P('zapatos-training-crossfit', 'Zapatos Training / Crossfit', 'Zapatos Deportivos y Gomas', DEP, 54.00,
      'Calzado estable para gym y crossfit: suela plana de alta tracción, puntera reforzada y talón firme para levantamientos.',
      (STUDIO.format(what='a single black and red training cross fit shoe side profile'),
       ALT.format(what='cross fit athlete wearing training shoes lifting a barbell in a gym, low angle on shoes')),
      unit='pair',
      attrs={'marca': 'HERO', 'disciplina': 'Gym / Crossfit / Training', 'genero': 'Unisex'},
      variants=grid('shoe_size', ['39', '40', '41', '42', '43', '44'], 'color', ['Negro / Rojo'], stock=4),
      tokens=TOK_B, offer=0),
    P('balon-futbol-n5', 'Balón de Fútbol N°5 Profesional', 'Fútbol y Futsal (Balones, Tacos y Canilleras)', DEP, 22.00,
      'Balón cosido a máquina con cámara de butilo, 32 paneles y cubierta de PU resistente. Tamaño oficial N°5, '
      'ideal para campo y grama sintética.',
      (STUDIO.format(what='a classic black and white soccer ball size 5'),
       ALT.format(what='soccer ball on a green grass pitch near the goal at sunset')),
      attrs={'marca': 'HERO', 'superficie': 'Todo Uso / Accesorios'},
      variants=[V({'size': 'N°4', 'color': 'Blanco / Negro'}, 12, 19.00), V({'size': 'N°5', 'color': 'Blanco / Negro'}, 20),
                V({'size': 'N°5', 'color': 'Naranja / Amarillo'}, 8)],
      mods=[M('Personaliza', [('Grabado de nombre', 3), ('Bomba de aire + aguja', 4)], max_sel=2)],
      tokens=None, offer=10),
    P('mancuernas-hexagonales', 'Mancuernas Hexagonales Engomadas (Par)', 'Pesas, Mancuernas y Máquinas de Gym', DEP, 29.00,
      'Par de mancuernas hexagonales con recubrimiento de caucho y mango cromado con agarre moleteado. No ruedan ni '
      'dañan el piso.',
      (STUDIO.format(what='a pair of black rubber coated hexagonal dumbbells with chrome handles'),
       ALT.format(what='rack of hexagonal dumbbells in a gym, close-up in dramatic light')),
      unit='pair',
      attrs={'marca': 'HERO', 'material_recubrimiento': 'Caucho / Engomado (Hexagonal)', 'venta_formato': 'Por Par (2 unidades)'},
      variants=[V({'weight': '5 lb (par)'}, 15, 29.00), V({'weight': '10 lb (par)'}, 12, 49.00), V({'weight': '15 lb (par)'}, 8, 69.00),
                V({'weight': '20 lb (par)'}, 6, 89.00)],
      tokens=TOK_A, offer=0),
    P('proteina-whey-2lb', 'Proteína Whey 2 lb Sabor Chocolate', 'Proteínas, Creatinas y Suplementos Gym', DEP, 39.00,
      'Proteína de suero de leche con 24 g de proteína por servicio, bajo en azúcar, con enzimas digestivas. Mezcla fácil '
      'y sin grumos. 30 servicios por envase.',
      (STUDIO.format(what='a black plastic protein powder tub with scoop, blank label'),
       ALT.format(what='protein shake in a shaker bottle next to a tub of protein powder on a gym bench')),
      attrs={'marca': 'HERO Nutrition', 'tipo_suplemento': 'Proteína (Whey Isolate / Concentrate)', 'servicios_por_envase': '30 servicios'},
      variants=grid('flavor', ['Chocolate', 'Vainilla', 'Fresa'], 'size', ['2 lb'], stock=10) + [V({'flavor': 'Chocolate', 'size': '5 lb'}, 6, 82.00)],
      tokens=TOK_B, offer=0),
    P('termo-botella-acero-1l', 'Termo Botella Deportiva Acero Inoxidable 1 L', 'Cavas, Coolers y Termos', DEP, 18.00,
      'Botella térmica de doble pared al vacío que mantiene el frío 24 h y el calor 12 h. Tapa antiderrame con asa y '
      'acabado antideslizante. Libre de BPA.',
      (STUDIO.format(what='a matte black stainless steel insulated sports water bottle with a carrying handle lid'),
       ALT.format(what='insulated sports bottle on a gym bench next to a towel and sneakers, soft light')),
      attrs={'marca': 'HERO', 'material_retencion': 'Acero inoxidable doble pared / frío 24 h'},
      variants=grid('capacity', ['750 ml', '1 L'], 'color', ['Negro', 'Verde Neón', 'Azul'], stock=9, sold_out=[('750 ml', 'Azul')]),
      mods=[M('Personaliza', [('Grabado láser con tu nombre', 4)])],
      tokens=None, offer=10),
]

# ----------------------------------------------------------------------------------------------------------------------
# Comercios (un usuario -> una compañía + sucursal principal a pie de calle en Caracas)
# ----------------------------------------------------------------------------------------------------------------------
COMPANIES = [
    {
        'key': 'soy-techno',
        'user_id': '98e14e2c-b1ad-4704-841b-baeaf87e2da8',
        'name': 'Soy Techno',
        'company_category': 'Tecnología',
        'address': 'Av. Francisco de Miranda, Chacao, Caracas',
        'details': 'Local a pie de calle en la Av. Francisco de Miranda, a pocos metros de la plaza Altamira.',
        'lat': 10.4953129, 'lng': -66.8493552,  # punto real de la vía (OSM way 278028838)
        'tokens_per_dollar': 3,
        'logo_prompt': 'minimal modern circular logo icon for a smartphone store called Soy Techno, stylized phone with a smile, '
                       'electric blue and white, flat vector design, centered, plain background, no text except optional tiny brand initials',
        'store_prompt': 'photograph of a modern small smartphone store front on a Caracas city street, glass windows with phones on display, '
                        'blue illuminated sign without readable text, daytime, realistic',
        'products': SOY_TECHNO_PRODUCTS,
    },
    {
        'key': 'epa',
        'user_id': 'afa3404c-0a8a-4d65-9d8a-b6e32ae5d133',
        'name': 'EPA',
        'company_category': 'Ferretería',
        'address': 'Av. Baralt, Caracas',
        'details': 'Ferretería a pie de calle sobre la Av. Baralt, con estacionamiento frente al local.',
        'lat': 10.5049935, 'lng': -66.9177207,  # punto real de la vía (OSM way 221407686)
        'tokens_per_dollar': 2,
        'logo_prompt': 'bold flat vector logo icon for a hardware store called EPA, crossed hammer and wrench inside a hexagon, '
                       'safety orange and dark gray, centered, plain background, no text',
        'store_prompt': 'photograph of a hardware store (ferretería) front on a busy Caracas avenue, tools and paint buckets displayed outside, '
                        'orange awning without readable text, daytime, realistic',
        'products': EPA_PRODUCTS,
    },
    {
        'key': 'movilhogar',
        'user_id': 'b15e2cec-c0f1-4e7d-adb2-7da25ac8c412',
        'name': 'MovilHogar',
        'company_category': 'Hogar y Muebles',
        'address': 'Calle Madrid, Las Mercedes, Caracas',
        'details': 'Showroom a pie de calle en la Calle Madrid de Las Mercedes.',
        'lat': 10.484158, 'lng': -66.8616072,  # punto real de la vía (OSM way 259277287)
        'tokens_per_dollar': 2,
        'logo_prompt': 'elegant flat vector logo icon for a furniture and home goods store called MovilHogar, minimal house shaped like an armchair, '
                       'warm terracotta and cream colors, centered, plain background, no text',
        'store_prompt': 'photograph of a stylish furniture showroom front on a tree lined street in Caracas, large windows showing sofas and lamps, '
                        'warm lighting, no readable text, realistic',
        'products': MOVILHOGAR_PRODUCTS,
    },
    {
        'key': 'hero',
        'user_id': 'f0afff8b-dcd9-44ea-b8f3-774f2606bf53',
        'name': 'HERO',
        'company_category': 'Deportes',
        'address': 'Av. Casanova, Sabana Grande, Caracas',
        'details': 'Tienda deportiva a pie de calle en la Av. Casanova, cerca del bulevar de Sabana Grande.',
        'lat': 10.4920839, 'lng': -66.8753196,  # punto real de la vía (OSM way 701207326)
        'tokens_per_dollar': 4,
        'logo_prompt': 'bold dynamic flat vector logo icon for a sportswear brand called HERO, stylized lightning bolt inside a shield, '
                       'black and neon green, centered, plain background, no text',
        'store_prompt': 'photograph of a sportswear store front on a Caracas street, mannequins wearing athletic clothes in the window, '
                        'black and neon green sign without readable text, daytime, realistic',
        'products': HERO_PRODUCTS,
    },
]


def company_ids(company):
    return {'company': demo_uuid('company', company['key']), 'store': demo_uuid('store', company['key'])}


def product_id(company_key, slug):
    return demo_uuid('product', company_key, slug)


def inventory_item_id(company_key, slug):
    return demo_uuid('item', company_key, slug)


def product_image_keys(company_key, slug, count=2):
    pid = product_id(company_key, slug)
    return [f'product_pictures/{pid}/{slug}_{n}.jpg' for n in range(1, count + 1)]


def company_logo_key(company):
    return f"company_profile_pictures/{demo_uuid('company', company['key'])}/logo.jpg"


def store_image_key(company):
    return f"store_pictures/{demo_uuid('store', company['key'])}/fachada.jpg"


def local_image_name(kind, company_key, slug=None, n=1):
    """Ruta relativa (dentro de scripts/demo_merchants/images/) del archivo local generado."""
    if kind == 'product':
        return f'{company_key}/{slug}_{n}.jpg'
    return f'{company_key}/_{kind}.jpg'
