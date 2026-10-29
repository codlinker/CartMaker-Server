# -*- coding: utf-8 -*-
"""Catálogo demo de Casa Ávila Deco (Hogar, Muebles y Jardín): 20 productos."""
from ._helpers import ALT, STUDIO, TOK_A, TOK_B, TOK_C, M, P, V, grid, sizes  # noqa: F401

CAT = 'Hogar, Muebles y Jardín'

SALA = 'Muebles de Sala y Comedor'
CAMAS = 'Camas, Colchones y Box Spring'
LENCERIA = 'Sábanas, Edredones y Toallas'
COCINA = 'Ollas, Sartenes y Utensilios de Cocina'
ELECTRO = 'Pequeños Electrodomésticos y Cocina'
DECO = 'Decoración, Cuadros y Espejos'
BANO = 'Pocetas, Lavamanos y Baño'
JARDIN = 'Jardinería, Mangueras y Exteriores'

PRODUCTS = [
    # ------------------------------------------------------------------ Sala y comedor
    P('sofa-3-puestos-lino-avila', 'Sofá 3 Puestos Ávila Tapizado en Lino', SALA, CAT, 489.00,
      'Sofá de 3 puestos con estructura de madera de pino tratada, cojines de espuma de alta densidad y tapizado en tela '
      'tipo lino antimanchas. Mide 2,10 m de largo y se entrega armado en Caracas. Fabricación nacional con 1 año de garantía.',
      (STUDIO.format(what='a modern three-seater sofa upholstered in light gray linen fabric with wooden legs, front three-quarter view'),
       ALT.format(what='cozy living room with a gray linen three-seater sofa, throw pillows, a knitted blanket and a plant, warm afternoon light')),
      attrs={'material_principal': 'Madera de pino y tela tipo lino antimanchas', 'dimensiones': '210 x 88 x 85 cm',
             'requiere_armado': 'Se entrega armado', 'garantia': '1 año'},
      variants=[V({'color_finish': 'Gris'}, 3), V({'color_finish': 'Beige'}, 2), V({'color_finish': 'Azul Rey'}, 0)],
      offer=10),
    P('juego-comedor-6-puestos-madera', 'Juego de Comedor 6 Puestos en Madera Maciza', SALA, CAT, 690.00,
      'Mesa rectangular de 1,60 x 0,90 m en madera maciza con 6 sillas de espaldar curvo y asiento tapizado. '
      'Acabado laqueado resistente a la humedad, ideal para el clima caraqueño. Se entrega armado y con 1 año de garantía.',
      (STUDIO.format(what='a solid wood rectangular dining table with six upholstered wooden chairs, three-quarter view'),
       ALT.format(what='bright dining room with a solid wood table set for six, ceramic plates, linen napkins and a pendant lamp above')),
      attrs={'material_principal': 'Madera maciza laqueada', 'dimensiones': 'Mesa 160 x 90 x 76 cm',
             'requiere_armado': 'Se entrega armado', 'garantia': '1 año'},
      variants=[V({'color_finish': 'Madera Natural'}, 2), V({'color_finish': 'Wengué'}, 2)],
      tokens=TOK_C),
    P('mesa-centro-roble-vidrio', 'Mesa de Centro Nórdica Roble y Vidrio Templado', SALA, CAT, 129.00,
      'Mesa de centro de estilo nórdico con tope de vidrio templado de 8 mm, repisa inferior en MDF acabado roble y patas '
      'de madera. Mide 110 x 60 cm. Viene en caja con instructivo y herrajes para armar en menos de 20 minutos.',
      (STUDIO.format(what='a scandinavian style coffee table with tempered glass top, light oak lower shelf and tapered wooden legs'),
       ALT.format(what='nordic coffee table in a minimalist living room with books, a small vase and a candle on top, soft daylight')),
      attrs={'material_principal': 'MDF acabado roble y vidrio templado 8 mm', 'dimensiones': '110 x 60 x 45 cm',
             'requiere_armado': 'En caja (Requiere armado)', 'garantia': '3 meses'},
      tokens=TOK_B, stock=6),
    P('butaca-acento-terciopelo', 'Butaca de Acento en Terciopelo Verde Esmeralda', SALA, CAT, 219.00,
      'Butaca individual con tapizado de terciopelo suave, espaldar capitoneado y patas metálicas con acabado dorado. '
      'Perfecta para un rincón de lectura o para darle un toque de color a la sala. Se entrega armada.',
      (STUDIO.format(what='an emerald green velvet accent armchair with tufted back and slim golden metal legs, three-quarter view'),
       ALT.format(what='emerald velvet armchair in a reading corner next to a floor lamp and a bookshelf, cozy evening light')),
      attrs={'material_principal': 'Terciopelo y estructura metálica', 'dimensiones': '72 x 75 x 82 cm',
             'requiere_armado': 'Se entrega armado', 'garantia': '6 meses'},
      tokens=TOK_A, stock=4),
    P('rack-tv-flotante-180', 'Mueble para TV Flotante 180 cm', SALA, CAT, 159.00,
      'Rack flotante de 180 cm para televisores de hasta 75", con 2 puertas abatibles, repisa central para decodificador '
      'y pasacables ocultos. Fabricado en MDF de 18 mm; incluye herrajes de anclaje a pared.',
      (STUDIO.format(what='a modern floating TV stand cabinet 180 cm wide with two flip-down doors and an open middle shelf'),
       ALT.format(what='floating TV cabinet mounted under a large flat TV on a living room wall, decor items on top, ambient light')),
      attrs={'material_principal': 'MDF 18 mm', 'dimensiones': '180 x 35 x 30 cm',
             'requiere_armado': 'En caja (Requiere armado)', 'garantia': '6 meses'},
      variants=[V({'color_finish': 'Blanco'}, 5), V({'color_finish': 'Wengué'}, 4), V({'color_finish': 'Madera Natural'}, 3)],
      offer=15),

    # ------------------------------------------------------------------ Dormitorio
    P('colchon-ortopedico-resortes-pocket', 'Colchón Ortopédico Lujo Resortes Pocket', CAMAS, CAT, 189.00,
      'Colchón de resortes independientes tipo pocket con capa de espuma de alta densidad y tela jacquard acolchada. '
      'Soporte firme que reduce el movimiento entre dos personas. Despacho a domicilio en el este de Caracas y 5 años de garantía de fábrica.',
      (STUDIO.format(what='a thick orthopedic pocket spring mattress with white quilted jacquard fabric, three-quarter view'),
       ALT.format(what='bedroom with a freshly made bed on a new mattress, white sheets, pillows and a bedside lamp, morning light')),
      attrs={'marca': 'Lujo', 'tipo_colchon': 'Resortes Pocket (Independientes)', 'garantia': '5 años'},
      variants=[V({'bed_size': 'Individual (1.00 x 1.90m)', 'include_box': 'Solo Colchón'}, 4),
                V({'bed_size': 'Matrimonial (1.40 x 1.90m)', 'include_box': 'Solo Colchón'}, 3, 259.00),
                V({'bed_size': 'Matrimonial (1.40 x 1.90m)', 'include_box': 'Colchón + Box Spring'}, 2, 389.00),
                V({'bed_size': 'Queen (1.60 x 1.90m)', 'include_box': 'Solo Colchón'}, 3, 319.00),
                V({'bed_size': 'Queen (1.60 x 1.90m)', 'include_box': 'Colchón + Box Spring'}, 2, 469.00),
                V({'bed_size': 'King (2.00 x 2.00m)', 'include_box': 'Colchón + Box Spring'}, 0, 619.00)],
      tokens=TOK_C),
    P('almohada-viscoelastica-memory-foam', 'Almohada Viscoelástica Memory Foam', CAMAS, CAT, 29.00,
      'Almohada de espuma viscoelástica que se adapta a la forma de la cabeza y el cuello, con funda removible de bambú '
      'lavable. Mide 60 x 40 cm y es hipoalergénica.',
      (STUDIO.format(what='a white memory foam pillow with a soft quilted bamboo cover, slightly angled view'),
       ALT.format(what='hand pressing into a memory foam pillow showing the slow recovery imprint, close-up, soft light')),
      attrs={'marca': 'Lujo', 'garantia': '6 meses'},
      tokens=TOK_A, stock=24),
    P('juego-sabanas-algodon-400-hilos', 'Juego de Sábanas 400 Hilos 100% Algodón', LENCERIA, CAT, 45.00,
      'Juego de sábanas de percal 100% algodón de 400 hilos: sábana ajustable con elástico perimetral, sábana plana y '
      '2 fundas. Frescas para el calor y cada vez más suaves con cada lavada.',
      (STUDIO.format(what='a neatly folded set of white cotton percale bed sheets with two pillowcases stacked'),
       ALT.format(what='bed dressed with crisp white cotton sheets, slightly wrinkled, sunlight through sheer curtains')),
      unit='set',
      attrs={'material_hilos': '100% algodón percal, 400 hilos', 'piezas_incluidas': 'Sábana ajustable, sábana plana y 2 fundas'},
      variants=grid('bed_size', ['Matrimonial', 'Queen', 'King'], 'color', ['Blanco', 'Gris', 'Beige'], stock=6,
                    sold_out=[('King', 'Beige')]),
      offer=20),
    P('edredon-reversible-microfibra', 'Edredón Reversible de Microfibra', LENCERIA, CAT, 59.00,
      'Edredón reversible de microfibra con relleno siliconado de 250 g/m², costuras en cuadros que evitan que el relleno '
      'se desplace. Liviano, ideal para las noches frescas de Caracas. Lavable en lavadora.',
      (STUDIO.format(what='a folded reversible microfiber comforter showing two different solid colors on each side'),
       ALT.format(what='bed with a reversible quilted comforter partially folded back, decorative pillows, cozy bedroom')),
      unit='unit',
      attrs={'material_hilos': 'Microfibra con relleno siliconado 250 g/m²', 'piezas_incluidas': 'Edredón'},
      variants=[V({'bed_size': 'Matrimonial', 'color': 'Gris'}, 6), V({'bed_size': 'Queen', 'color': 'Gris'}, 5, 65.00),
                V({'bed_size': 'Queen', 'color': 'Azul'}, 4, 65.00), V({'bed_size': 'King', 'color': 'Vinotinto'}, 3, 72.00)],
      tokens=TOK_B),
    P('set-toallas-algodon-6-piezas', 'Set de 6 Toallas de Algodón Egipcio', LENCERIA, CAT, 38.00,
      'Set de toallas de algodón egipcio de 550 g/m²: 2 de cuerpo completo, 2 de manos y 2 faciales. Muy absorbentes, '
      'de secado rápido y con bordes reforzados.',
      (STUDIO.format(what='a stack of six fluffy cotton towels in three sizes, neatly folded'),
       ALT.format(what='fluffy rolled towels on a wooden shelf in a bright spa-like bathroom with a plant')),
      unit='set',
      attrs={'material_hilos': 'Algodón egipcio 550 g/m²', 'piezas_incluidas': '2 de cuerpo, 2 de manos y 2 faciales'},
      variants=sizes('color', ['Blanco', 'Beige', 'Gris', 'Azul'], stock=7)),

    # ------------------------------------------------------------------ Cocina
    P('set-ollas-acero-inoxidable-10-piezas', 'Batería de Ollas Tramontina 10 Piezas Acero Inoxidable', COCINA, CAT, 129.00,
      'Juego de ollas en acero inoxidable con fondo triple que distribuye el calor de forma pareja; sirve en cocinas a gas, '
      'eléctricas y de inducción. Incluye 4 ollas con tapa de vidrio y 1 sartén.',
      (STUDIO.format(what='a ten-piece stainless steel cookware set with glass lids, pots and a frying pan arranged together'),
       ALT.format(what='stainless steel pot with glass lid simmering on a gas stove in a modern kitchen, steam rising')),
      unit='set',
      attrs={'marca': 'Tramontina', 'material': 'Acero Inoxidable'},
      tokens=TOK_A, stock=8),
    P('sarten-antiadherente-granito', 'Sartén Antiadherente Efecto Granito Imusa', COCINA, CAT, 18.00,
      'Sartén de aluminio con recubrimiento antiadherente efecto granito libre de PFOA y mango de baquelita "touch" que no '
      'se calienta. Cocina con muy poco aceite: perfecta para arepas, huevos y tortillas.',
      (STUDIO.format(what='a granite-effect non-stick frying pan with a soft-touch black handle, top angled view'),
       ALT.format(what='fried eggs cooking in a speckled granite non-stick pan on a stove, close-up, warm kitchen light')),
      attrs={'marca': 'Imusa', 'material': 'Cerámica / Granito'},
      variants=[V({'size_or_set': '20 cm'}, 12), V({'size_or_set': '24 cm'}, 10, 22.00), V({'size_or_set': '28 cm'}, 6, 27.00)]),
    P('set-cuchillos-tramontina-base', 'Set de Cuchillos Tramontina con Base de Madera', COCINA, CAT, 39.00,
      'Set de 6 piezas: cuchillo chef, cuchillo para pan, cuchillo deshuesador, cuchillo multiuso, chaira y base de madera. '
      'Hojas de acero inoxidable con filo duradero y mangos ergonómicos.',
      (STUDIO.format(what='a kitchen knife set with stainless steel blades in a wooden knife block'),
       ALT.format(what='chef knife slicing fresh vegetables on a wooden cutting board, knife block in the background')),
      unit='set',
      attrs={'marca': 'Tramontina', 'material': 'Acero Inoxidable'},
      offer=10, stock=15),
    P('freidora-aire-oster-4l', 'Freidora de Aire Oster 4 Litros', ELECTRO, CAT, 79.00,
      'Freidora de aire de 4 litros y 1500 W con control digital, 8 programas predefinidos y cesta antiadherente apta para '
      'lavavajillas. Tequeños y papas crujientes sin aceite. Garantía oficial de 1 año.',
      (STUDIO.format(what='a modern digital air fryer with a 4 liter basket and touch control panel, front three-quarter view'),
       ALT.format(what='air fryer basket pulled out showing golden crispy fries and cheese sticks, kitchen counter, warm light')),
      attrs={'marca': 'Oster', 'capacidad_potencia': '4 litros / 1500 W', 'voltaje': '110V', 'garantia': '1 año'},
      variants=[V({'capacity_color': 'Negro'}, 7), V({'capacity_color': 'Acero Inoxidable'}, 4, 89.00)],
      tokens=TOK_B),

    # ------------------------------------------------------------------ Decoración e iluminación
    P('espejo-redondo-marco-dorado', 'Espejo Redondo con Marco Metálico Dorado', DECO, CAT, 45.00,
      'Espejo redondo de 5 mm con marco metálico fino en acabado dorado cepillado. Amplía visualmente cualquier espacio; '
      'ideal para recibidor, baño o sobre el aparador. Incluye colgador.',
      (STUDIO.format(what='a round wall mirror with a thin brushed gold metal frame, front view'),
       ALT.format(what='round gold framed mirror hanging above a wooden console with a vase and books in an entryway')),
      attrs={'dimensiones': '50 / 70 / 90 cm de diámetro', 'material': 'Vidrio de 5 mm y marco metálico'},
      variants=[V({'variant': 'Pequeño'}, 8), V({'variant': 'Mediano'}, 6, 65.00), V({'variant': 'Grande'}, 3, 89.00)],
      tokens=TOK_A),
    P('cuadro-triptico-abstracto-canvas', 'Cuadro Tríptico Abstracto en Canvas', DECO, CAT, 55.00,
      'Set de 3 cuadros en lienzo canvas impreso con tintas resistentes a la luz y bastidor de madera, con motivos '
      'abstractos en tonos tierra. Cada pieza mide 40 x 60 cm y viene lista para colgar.',
      (STUDIO.format(what='a set of three abstract canvas paintings in earth tones with organic shapes, displayed side by side'),
       ALT.format(what='three abstract canvas prints hanging above a beige sofa in a modern living room, natural light')),
      unit='set',
      attrs={'dimensiones': '3 piezas de 40 x 60 cm', 'material': 'Lienzo canvas y bastidor de madera'},
      offer=25, stock=10),
    P('lampara-pie-arco-marmol', 'Lámpara de Pie Tipo Arco con Base de Mármol', DECO, CAT, 119.00,
      'Lámpara de pie de 1,90 m con brazo en arco, pantalla metálica orientable y base de mármol que le da estabilidad. '
      'Rosca E27 compatible con bombillos LED; incluye interruptor de pie.',
      (STUDIO.format(what='a modern arc floor lamp with a dome metal shade and a round white marble base'),
       ALT.format(what='arc floor lamp illuminating a cozy sofa corner in the evening, warm glowing light')),
      attrs={'dimensiones': 'Altura 190 cm, alcance 150 cm', 'material': 'Acero, aluminio y base de mármol'},
      tokens=TOK_B, stock=5),
    P('set-accesorios-bano-4-piezas', 'Set de Accesorios de Baño 4 Piezas', BANO, CAT, 32.00,
      'Juego de baño en resina con dispensador de jabón líquido, vaso para cepillos, jabonera y portacepillos. '
      'Diseño moderno que combina con cualquier lavamanos.',
      (STUDIO.format(what='a four-piece bathroom accessory set with soap dispenser, tumbler, soap dish and toothbrush holder'),
       ALT.format(what='matching bathroom accessory set on a white vanity countertop next to folded towels and a plant')),
      unit='set',
      attrs={'marca': 'Casa Ávila', 'incluye': 'Dispensador, vaso, jabonera y portacepillos'},
      variants=[V({'color': 'Blanco'}, 10), V({'color': 'Negro Mate'}, 8), V({'color': 'Dorado'}, 4, 36.00)],
      tokens=TOK_A),

    # ------------------------------------------------------------------ Jardín y terraza
    P('manguera-jardin-reforzada-20m', 'Manguera de Jardín Reforzada 20 m con Pistola', JARDIN, CAT, 24.00,
      'Manguera de PVC de 1/2" con malla de refuerzo anti-torsión, 20 metros de largo, con pistola de riego de 7 '
      'chorros y conectores rápidos incluidos.',
      (STUDIO.format(what='a coiled green reinforced garden hose with a multi-pattern spray nozzle and quick connectors'),
       ALT.format(what='garden hose spraying water over lush green plants on a sunny terrace, droplets in the air')),
      attrs={'material_tipo': 'PVC reforzado con malla, 1/2 pulgada'},
      offer=15, stock=18),
    P('juego-terraza-ratan-4-piezas', 'Juego de Terraza en Ratán Sintético 4 Piezas', JARDIN, CAT, 549.00,
      'Sofá de 2 puestos, 2 butacas y mesa de centro con tope de vidrio, tejidos en ratán sintético resistente al sol y '
      'la lluvia. Cojines con forro removible e impermeable. Ideal para balcones y terrazas.',
      (STUDIO.format(what='a four-piece synthetic rattan patio furniture set with cream cushions and a glass top coffee table'),
       ALT.format(what='rattan outdoor furniture set on a balcony with plants and a view of green mountains at sunset')),
      unit='set',
      attrs={'material_tipo': 'Ratán sintético, aluminio y vidrio templado'},
      offer=12, stock=3),
]
