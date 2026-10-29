# -*- coding: utf-8 -*-
"""Catálogo demo de Ferretería Dos Caminos (Ferretería y Construcción): 20 productos."""
from ._helpers import ALT, STUDIO, TOK_A, TOK_B, TOK_C, M, P, V, grid, sizes  # noqa: F401

CAT = 'Ferretería y Construcción'

PRODUCTS = [
    # ------------------------------------------------------------------ Herramientas Manuales
    P('juego-destornilladores-stanley-6', 'Juego de Destornilladores Stanley 6 Piezas', 'Herramientas Manuales', CAT, 12.50,
      'Tres destornilladores de pala y tres de estría con punta imantada, vástago de acero cromo vanadio y mango '
      'bimaterial antideslizante. El juego básico que no puede faltar en la casa ni en el taller.',
      (STUDIO.format(what='a set of six screwdrivers with yellow and black ergonomic handles arranged in a fan shape'),
       ALT.format(what='hand using a yellow handled screwdriver to tighten a wall outlet cover screw, close-up')),
      unit='set',
      attrs={'marca': 'Stanley', 'medida_piezas': '3 planos (1/8", 3/16", 1/4") + 3 estría (#0, #1, #2)',
             'garantia': '1 año'},
      tokens=TOK_A, stock=25),
    P('alicate-universal-truper-8', 'Alicate Universal Truper 8"', 'Herramientas Manuales', CAT, 9.50,
      'Alicate de electricista de 8" en acero forjado con cuchilla de corte para cable de hasta 12 AWG y mangos '
      'aislados con agarre cómodo. Sirve para sujetar, doblar, cortar y pelar.',
      (STUDIO.format(what='an 8 inch lineman combination plier with orange and black insulated grips'),
       ALT.format(what='electrician hands cutting a copper wire with combination pliers, electrical box in background')),
      attrs={'marca': 'Truper', 'medida_piezas': '8" (200 mm)', 'garantia': '6 meses'},
      offer=10, stock=30),
    P('llave-ajustable-perico-truper', 'Llave Ajustable (Perico) Truper', 'Herramientas Manuales', CAT, 8.00,
      'Llave ajustable de acero cromo vanadio con escala grabada en milímetros y pulgadas y mandíbula de apertura '
      'amplia. La herramienta clásica para plomería, bicicletas y mantenimiento general.',
      (STUDIO.format(what='three chrome adjustable wrenches of different sizes laid side by side'),
       ALT.format(what='plumber tightening a pipe fitting under a kitchen sink with a chrome adjustable wrench')),
      attrs={'marca': 'Truper', 'medida_piezas': '8", 10" y 12"', 'garantia': '6 meses'},
      variants=[V({'size': '8"'}, 14), V({'size': '10"'}, 10, 10.50), V({'size': '12"'}, 6, 13.50)],
      tokens=TOK_B),
    # ------------------------------------------------------------------ Herramientas Eléctricas
    P('rotomartillo-bosch-gbh-2-24', 'Rotomartillo Bosch GBH 2-24 D SDS Plus 790 W', 'Herramientas Eléctricas, Taladros y Esmeriles', CAT, 189.00,
      'Rotomartillo profesional de 790 W con 2.7 J de energía de impacto y 3 modos: taladro, percutor y cincel. '
      'Ideal para concreto, viga y bloque. Incluye maletín, empuñadura auxiliar y tope de profundidad. 1 año de garantía.',
      (STUDIO.format(what='a professional blue SDS plus rotary hammer drill with auxiliary handle next to its hard carrying case'),
       ALT.format(what='construction worker drilling into a concrete wall with a blue rotary hammer, dust particles, safety glasses')),
      attrs={'marca': 'Bosch', 'tipo_alimentacion': 'Eléctrica con Cable (110V)', 'potencia': '790 W / 2.7 J',
             'garantia': '1 año'},
      tokens=TOK_C, stock=4),
    P('sierra-circular-dewalt-7-1-4', 'Sierra Circular DeWalt 7-1/4" 1800 W', 'Herramientas Eléctricas, Taladros y Esmeriles', CAT, 139.00,
      'Sierra circular de 1800 W y 5200 RPM con base de aluminio, ajuste de bisel hasta 57° y profundidad de corte de '
      '2-1/2". Incluye disco de 24 dientes para madera. Para carpintería, encofrado y obra. 1 año de garantía.',
      (STUDIO.format(what='a yellow and black 7-1/4 inch circular saw with a carbide blade and aluminum shoe'),
       ALT.format(what='carpenter cutting a plywood sheet with a yellow circular saw on sawhorses, wood shavings flying')),
      attrs={'marca': 'DeWalt', 'tipo_alimentacion': 'Eléctrica con Cable (110V)', 'potencia': '1800 W / 5200 RPM',
             'garantia': '1 año'},
      offer=8, stock=5),
    P('soldadora-inversora-lincoln-200a', 'Soldadora Inversora Lincoln Electric 200 A Bivoltaje', 'Herramientas Eléctricas, Taladros y Esmeriles', CAT, 219.00,
      'Soldadora tipo inversor de 200 A para electrodos de hasta 5/32", bivoltaje 110 V / 220 V, liviana y con '
      'arranque en caliente. Incluye pinza porta electrodo, tenaza de tierra y careta. Para herrería y rejas. 1 año de garantía.',
      (STUDIO.format(what='a compact red inverter arc welding machine with welding cables, electrode holder and ground clamp'),
       ALT.format(what='welder with protective mask welding a steel gate frame, bright sparks, workshop at dusk')),
      attrs={'marca': 'Lincoln Electric', 'tipo_alimentacion': 'Bivoltaje (110V/220V - Soldadoras)', 'potencia': '200 A',
             'garantia': '1 año'},
      tokens=TOK_B, stock=3),
    # ------------------------------------------------------------------ Electricidad
    P('tomacorriente-doble-leviton', 'Tomacorriente Doble con Tapa Leviton', 'Electricidad, Cables, Breakers y Tomacorrientes', CAT, 3.20,
      'Tomacorriente doble polarizado con conexión a tierra, contactos de latón y tapa de policarbonato blanco incluida. '
      'Disponible en 110 V (15 A) y en 220 V (20 A) para aires acondicionados y secadoras.',
      (STUDIO.format(what='a white duplex wall electrical outlet with its cover plate and mounting screws'),
       ALT.format(what='electrician installing a white wall outlet with a screwdriver, freshly painted wall')),
      attrs={'marca': 'Leviton', 'especificacion_electrica': '110 V 15 A / 220 V 20 A, con tierra'},
      variants=[V({'gauge_or_amp': '110V', 'sale_format': 'Unidad'}, 60),
                V({'gauge_or_amp': '220V', 'sale_format': 'Unidad'}, 25, 6.50)],
      tokens=TOK_A),
    # ------------------------------------------------------------------ Bombillos e Iluminación LED
    P('panel-led-empotrable-18w', 'Panel LED Empotrable Redondo 18 W', 'Bombillos, Reflectores e Iluminación LED', CAT, 6.50,
      'Plafón LED ultradelgado de 22 cm para techo raso, con driver incluido y multivoltaje. Consume 80 % menos que un '
      'bombillo convencional. Elige luz blanca fría para cocina y oficina o cálida para sala y cuartos.',
      (STUDIO.format(what='a round ultra slim recessed LED ceiling panel light, white frame, shown from front and side'),
       ALT.format(what='modern kitchen ceiling with several round recessed LED panel lights turned on, bright clean look')),
      attrs={'marca': 'Sylvania', 'rosca_montaje': 'Panel Empotrable', 'voltaje': 'Multivoltaje (85V-265V)',
             'garantia': '1 año'},
      variants=[V({'wattage': '18W', 'light_tone': 'Luz Blanca Fría (6500K)'}, 40),
                V({'wattage': '18W', 'light_tone': 'Luz Cálida (3000K)'}, 22),
                V({'wattage': '24W', 'light_tone': 'Luz Blanca Fría (6500K)'}, 18, 8.50)],
      tokens=TOK_A),
    P('lampara-emergencia-recargable-60led', 'Lámpara de Emergencia Recargable 60 LED', 'Bombillos, Reflectores e Iluminación LED', CAT, 15.00,
      'Se enciende sola cuando se va la luz y da hasta 8 horas de iluminación. 60 LED de alto brillo, dos niveles de '
      'intensidad, montaje en pared o uso portátil con asa. Batería de litio recargable. 6 meses de garantía.',
      (STUDIO.format(what='a white rectangular rechargeable emergency light with two rows of LEDs and a carry handle'),
       ALT.format(what='emergency LED light glowing on a hallway wall lighting a dark apartment during a power outage')),
      attrs={'marca': 'Ecolite', 'rosca_montaje': 'Recargable de Emergencia', 'voltaje': 'Solar / Recargable',
             'garantia': '6 meses'},
      offer=15, stock=18),
    # ------------------------------------------------------------------ Plomería
    P('griferia-monomando-fregadero-inox', 'Grifería Monomando para Fregadero Acero Inoxidable', 'Plomería, Tuberías de PVC y Grifería', CAT, 48.00,
      'Grifo de cocina monomando con cuello alto giratorio 360° y cartucho cerámico de 35 mm. Acero inoxidable 304 '
      'acabado satinado que no se oxida. Incluye mangueras flexibles y kit de instalación.',
      (STUDIO.format(what='a modern high arc single handle stainless steel kitchen faucet with satin finish'),
       ALT.format(what='stainless steel kitchen faucet with running water over a sink, fresh vegetables nearby, morning light')),
      attrs={'marca': 'Grival', 'material': 'Acero Inoxidable 304'},
      tokens=TOK_B, stock=6),
    P('tubo-pvc-aguas-blancas-tubrica', 'Tubo PVC Aguas Blancas Tubrica 3 m', 'Plomería, Tuberías de PVC y Grifería', CAT, 4.50,
      'Tubo de PVC para presión, uso en tuberías de agua potable fría, en tramo de 3 metros con extremo liso para pegar. '
      'Fabricación nacional. Pídelo en 1/2", 3/4" o 1".',
      (STUDIO.format(what='several white PVC pressure pipes of different diameters stacked neatly'),
       ALT.format(what='plumber cutting a white PVC pipe with a pipe cutter on a workbench, fittings around')),
      attrs={'marca': 'Tubrica', 'material': 'PVC Aguas Blancas (Presión)'},
      variants=[V({'diameter': '1/2"'}, 80), V({'diameter': '3/4"'}, 50, 6.50), V({'diameter': '1"'}, 30, 9.00)]),
    # ------------------------------------------------------------------ Hidroneumático y Bombas
    P('bomba-periferica-pedrollo-pkm', 'Bomba de Agua Periférica Pedrollo PKm', 'Sistemas de Hidroneumático y Bombas de Agua', CAT, 89.00,
      'Bomba periférica italiana para subir agua al tanque o presurizar la casa, con impulsor de latón y motor '
      'silencioso de uso continuo. Ideal para llenar tanques en edificios y casas. 1 año de garantía.',
      (STUDIO.format(what='a compact blue peripheral electric water pump with brass inlet and outlet fittings'),
       ALT.format(what='blue water pump installed next to a water tank on a rooftop with PVC pipes, sunny day')),
      attrs={'marca': 'Pedrollo', 'voltaje': '110V', 'potencia_caudal': '0.5 HP (PKm60) / 1 HP (PKm80), hasta 40 L/min',
             'garantia': '1 año'},
      variants=[V({'hp_or_liters': '1/2 HP'}, 5), V({'hp_or_liters': '1 HP'}, 3, 149.00)],
      tokens=TOK_C),
    # ------------------------------------------------------------------ Pinturas
    P('esmalte-anticorrosivo-montana', 'Esmalte Anticorrosivo Montana', 'Pinturas, Cuñetes, Brochas y Selladores', CAT, 9.00,
      'Esmalte sintético con anticorrosivo incorporado para rejas, portones, ventanas y tubos de hierro. Excelente '
      'brillo y secado al tacto en 2 horas. Disponible en 1/4 de galón y galón.',
      (STUDIO.format(what='two metal paint cans, a quart and a gallon, with plain unlabeled glossy black lids'),
       ALT.format(what='person painting a metal security gate glossy black with a brush, sunny residential street')),
      attrs={'marca': 'Montana', 'tipo_pintura': 'Esmalte / Anticorrosivo'},
      variants=[V({'presentation': '1/4 de Galón', 'color': 'Negro Brillante'}, 18),
                V({'presentation': '1/4 de Galón', 'color': 'Blanco Satinado'}, 12),
                V({'presentation': '1/4 de Galón', 'color': 'Gris'}, 9),
                V({'presentation': '1 Galón (3.78L)', 'color': 'Negro Brillante'}, 8, 28.00),
                V({'presentation': '1 Galón (3.78L)', 'color': 'Blanco Satinado'}, 6, 28.00),
                V({'presentation': '1 Galón (3.78L)', 'color': 'Gris'}, 0, 28.00)],
      tokens=TOK_A),
    P('impermeabilizante-elastomerico-4gal', 'Impermeabilizante Elastomérico para Techos Cuñete 4 Galones', 'Pinturas, Cuñetes, Brochas y Selladores', CAT, 79.00,
      'Recubrimiento elastomérico acrílico blanco que sella grietas y refleja el calor del sol. Rinde unos 30 m² a dos '
      'manos por cuñete. Ideal para preparar la platabanda antes de la temporada de lluvias.',
      (STUDIO.format(what='a large white plastic paint bucket of roof waterproofing coating with a plain unlabeled lid'),
       ALT.format(what='worker applying white elastomeric waterproofing with a roller on a flat concrete rooftop, blue sky')),
      attrs={'marca': 'Sika', 'tipo_pintura': 'Impermeabilizante Elastómero'},
      offer=10, stock=8),
    P('kit-pintura-rodillo-bandeja-brocha', 'Kit de Pintura: Rodillo 9" + Bandeja + Brocha 3"', 'Pinturas, Cuñetes, Brochas y Selladores', CAT, 11.00,
      'Todo lo necesario para pintar una habitación: rodillo de felpa de 9" con mango, bandeja plástica resistente y '
      'brocha de cerdas mixtas de 3" para bordes y esquinas.',
      (STUDIO.format(what='a paint roller kit with a 9 inch roller, a plastic paint tray and a 3 inch brush'),
       ALT.format(what='couple painting a living room wall in light beige with a roller and tray, drop cloth on floor')),
      unit='pack',
      attrs={'marca': 'Goya', 'tipo_pintura': 'Brochas, Rodillos y Lijas'},
      tokens=TOK_B, stock=20),
    # ------------------------------------------------------------------ Cementos y Pegos
    P('pego-ceramica-porcelanato-20kg', 'Pego para Cerámica y Porcelanato Saco 20 kg', 'Cementos, Pegos, Mallas y Bloques', CAT, 11.50,
      'Adhesivo cementicio gris de alta adherencia para colocar cerámica y porcelanato en pisos y paredes, interior y '
      'exterior. Rinde de 4 a 5 m² por saco con llana dentada de 8 mm.',
      (STUDIO.format(what='a 20 kg paper bag of gray tile adhesive mortar with a plain unlabeled design, standing upright'),
       ALT.format(what='mason spreading gray tile adhesive with a notched trowel on a floor before laying porcelain tiles')),
      attrs={'marca': 'Sika', 'peso_rendimiento': '20 kg, 4-5 m² por saco'},
      offer=5, stock=40),
    # ------------------------------------------------------------------ Tornillería
    P('tornillos-drywall-punta-fina', 'Tornillos para Drywall Punta Fina', 'Tornillería, Clavos y Chazos', CAT, 3.50,
      'Tornillos fosfatados negros de cabeza trompeta y rosca fina para fijar láminas de drywall sobre perfil metálico. '
      'Paquete de 100 unidades.',
      (STUDIO.format(what='a pile of black phosphate drywall screws with bugle heads, a few standing upright'),
       ALT.format(what='installer driving a black screw into a gypsum board wall with a cordless screwdriver, close-up')),
      unit='pack',
      attrs={'medida_rosca': '#6 rosca fina, 1" a 2"'},
      variants=[V({'size': '1"', 'pack_qty': 'Paquete x100'}, 50),
                V({'size': '1-1/2"', 'pack_qty': 'Paquete x100'}, 40, 4.20),
                V({'size': '2"', 'pack_qty': 'Paquete x100'}, 25, 5.00)],
      tokens=TOK_A),
    # ------------------------------------------------------------------ Cerraduras
    P('cerradura-pomo-cisa-alcoba-bano', 'Cerradura de Pomo Cisa Acero Inoxidable', 'Cerraduras, Candados y Cilindros', CAT, 14.00,
      'Cerradura tubular de pomo en acabado acero inoxidable mate, para puertas de 35 a 45 mm. Versión alcoba con '
      'llave (3 llaves incluidas) o versión baño con seguro de botón, sin llave.',
      (STUDIO.format(what='a brushed stainless steel door knob lock set with three keys and latch mechanism'),
       ALT.format(what='brushed steel door knob installed on a white bedroom door, soft interior daylight')),
      attrs={'marca': 'Cisa', 'tipo_cerradura': 'Cerradura de Pomo / Manilla'},
      variants=[V({'finish_or_size': 'Alcoba (Con Llave)'}, 15), V({'finish_or_size': 'Baño (Sin Llave)'}, 12, 12.00)],
      offer=12),
    P('cerradura-sobreponer-porton-cisa', 'Cerradura de Sobreponer para Portón Cisa', 'Cerraduras, Candados y Cilindros', CAT, 38.00,
      'Cerradura de sobreponer de alta resistencia para portones y rejas, con cerrojo de doble paso, caja de acero '
      'pintado y cilindro de seguridad de 5 pines. Incluye 3 llaves y tornillería.',
      (STUDIO.format(what='a heavy duty surface mounted gate lock with a steel body, keyhole cylinder and three keys'),
       ALT.format(what='heavy duty lock mounted on a black iron gate of a Caracas house entrance, daytime')),
      attrs={'marca': 'Cisa', 'tipo_cerradura': 'Cerradura de Sobreponer (Portón)'},
      tokens=TOK_B, stock=9),
    # ------------------------------------------------------------------ Seguridad Industrial
    P('guantes-carnaza-reforzados', 'Guantes de Carnaza Reforzados', 'Seguridad Industrial, Guantes y Botas', CAT, 3.50,
      'Par de guantes de cuero carnaza con palma reforzada y puño de tela, para obra, herrería, jardinería y carga. '
      'Resistentes a la abrasión y al calor moderado.',
      (STUDIO.format(what='a pair of tan split leather work gloves with reinforced palms and fabric cuffs'),
       ALT.format(what='construction worker wearing leather work gloves carrying concrete blocks at a building site')),
      unit='pair',
      attrs={'marca': 'Truper', 'proteccion': 'Guantes Anticorte / Carnaza / Nitrilo'},
      variants=sizes('size', ['M', 'L', 'XL'], stock=30, sold_out=('M',))),
]
