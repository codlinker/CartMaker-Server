# -*- coding: utf-8 -*-
"""Catálogo demo de Piñatería La Fiesta (Fiestas y Piñatería): 20 productos."""
from ._helpers import ALT, STUDIO, TOK_A, TOK_B, TOK_C, M, P, V, grid, sizes  # noqa: F401

CAT = 'Fiestas y Piñatería'

PINATAS = 'Piñatas, Cotillones y Globos'
DESCARTABLES = 'Descartables, Vasos, Platos y Servilletas'
EMBALAJE = 'Embalaje, Cajas y Bolsas Plásticas'
SERVICIOS = 'Servicios Profesionales'

_NUMEROS = ['Número 0', 'Número 1', 'Número 2', 'Número 3', 'Número 4', 'Número 5', 'Número 6', 'Número 7',
            'Número 8', 'Número 9']

PRODUCTS = [
    # ------------------------------------------------------------------------------------------------------------------
    # Piñatas, Cotillones y Globos
    # ------------------------------------------------------------------------------------------------------------------
    P('pinata-tradicional-personaje', 'Piñata Tradicional de Personaje Mediana', PINATAS, CAT, 25.00,
      'Piñata artesanal de cartón y papel seda hecha en Caracas, de unos 70 cm de alto, con capacidad para 3 kg de '
      'relleno. Elige el motivo de tu fiesta; también la hacemos por encargo con el personaje que quieras.',
      (STUDIO.format(what='a colorful handmade Venezuelan party pinata shaped like a cute cartoon unicorn, made of '
                          'crepe paper fringes'),
       ALT.format(what='children around a hanging colorful pinata at a backyard birthday party, balloons in background')),
      attrs={'marca_motivo': 'Artesanal La Fiesta', 'medida_unidades': '70 cm de alto / 3 kg de relleno'},
      variants=[V({'color_or_number': 'Unicornio', 'pack_size': 'Unidad'}, 4),
                V({'color_or_number': 'Superhéroe', 'pack_size': 'Unidad'}, 5),
                V({'color_or_number': 'Princesa', 'pack_size': 'Unidad'}, 3),
                V({'color_or_number': 'Dinosaurio', 'pack_size': 'Unidad'}, 0),
                V({'color_or_number': 'Fútbol', 'pack_size': 'Unidad'}, 3)],
      tokens=TOK_A),
    P('pinata-numero-metalizada', 'Piñata de Número Metalizada', PINATAS, CAT, 22.00,
      'Piñata en forma de número, forrada en papel metalizado con flecos, de 60 cm de alto. Ideal para primeros '
      'añitos y fiestas temáticas modernas; incluye cordón para colgar.',
      (STUDIO.format(what='a party pinata shaped like the number one covered in shiny gold metallic fringe paper'),
       ALT.format(what='gold number shaped pinata hanging at an elegant first birthday party with pastel balloons')),
      attrs={'marca_motivo': 'Artesanal La Fiesta', 'medida_unidades': '60 cm de alto'},
      variants=[V({'color_or_number': n, 'pack_size': 'Unidad'}, 0 if n == 'Número 7' else 3) for n in _NUMEROS[1:8]],
      offer=10),
    P('relleno-pinata-surtido', 'Relleno para Piñata Surtido', PINATAS, CAT, 10.00,
      'Mezcla lista de caramelos, chupetas, chicles, juguetitos y pitos para rellenar la piñata. Bolsa de 50 o '
      '100 piezas surtidas.',
      (STUDIO.format(what='a pile of assorted wrapped candies, lollipops, small plastic toys and whistles for a pinata'),
       ALT.format(what='candies and small toys falling from a broken pinata, children hands reaching, party')),
      unit='pack',
      attrs={'marca_motivo': 'Surtido Savoy / Chupetas / juguetitos', 'medida_unidades': '50 o 100 piezas'},
      variants=[V({'pack_size': 'Paquete x50'}, 20), V({'pack_size': 'Paquete x100'}, 14, 18.00)],
      tokens=TOK_B),
    P('globos-latex-r12-x50', 'Globos de Látex R12 Sempertex x50', PINATAS, CAT, 6.50,
      'Globos de látex de 12 pulgadas, perlados o pastel, resistentes y de color uniforme. Bolsa de 50 unidades; '
      'sirven para helio o aire y para arcos orgánicos.',
      (STUDIO.format(what='a pile of glossy 12 inch latex party balloons in assorted pastel colors, uninflated and inflated'),
       ALT.format(what='bunch of inflated pastel latex balloons floating at a birthday party, bright room')),
      unit='pack',
      attrs={'marca_motivo': 'Sempertex', 'medida_unidades': '12" / 50 unidades'},
      variants=grid('color_or_number', ['Dorado', 'Plateado', 'Rosa', 'Azul', 'Rojo', 'Surtido'],
                    'pack_size', ['Paquete x50'], stock=12, sold_out=[('Rojo', 'Paquete x50')]),
      tokens=TOK_A),
    P('globo-metalizado-numero-40', 'Globo Metalizado de Número 40" Dorado', PINATAS, CAT, 4.50,
      'Globo metalizado de 40 pulgadas (1 metro) en forma de número, color dorado. Se infla con helio o aire y se '
      'reutiliza; perfecto para la torta y las fotos.',
      (STUDIO.format(what='a giant shiny gold foil balloon shaped like a number, inflated, standing upright'),
       ALT.format(what='two big gold number foil balloons next to a birthday cake table, festive decor')),
      attrs={'marca_motivo': 'Metalizado Dorado', 'medida_unidades': '40" (1 m)'},
      variants=sizes('color_or_number', _NUMEROS, stock=8, sold_out=('Número 0',)),
      tokens=TOK_A),
    P('kit-arco-organico-globos', 'Kit Arco Orgánico de Globos (100 piezas)', PINATAS, CAT, 15.00,
      'Kit para armar tu propio arco orgánico: 100 globos de varios tamaños (5", 10", 12" y 18"), cinta para arco, '
      'puntos de pega y guía de armado. Rinde para unos 3 metros.',
      (STUDIO.format(what='a balloon garland kit with assorted size latex balloons, a plastic strip and glue dots laid out'),
       ALT.format(what='an organic balloon garland arch in rose gold and white tones decorating a party backdrop')),
      unit='set',
      attrs={'marca_motivo': 'Sempertex', 'medida_unidades': '100 globos / 3 m aprox.'},
      variants=[V({'color_or_number': 'Rosa Gold', 'pack_size': 'Combo Fiesta Completo'}, 8),
                V({'color_or_number': 'Dorado', 'pack_size': 'Combo Fiesta Completo'}, 6),
                V({'color_or_number': 'Azul', 'pack_size': 'Combo Fiesta Completo'}, 6),
                V({'color_or_number': 'Surtido', 'pack_size': 'Combo Fiesta Completo'}, 10)],
      offer=20),
    P('cotillon-infantil-x12', 'Cotillón Infantil Surtido x12', PINATAS, CAT, 9.00,
      'Doce bolsitas de cotillón con gorrito, pito, antifaz, serpentina y matraca para que todos los invitados se '
      'unan a la celebración. Elige el motivo.',
      (STUDIO.format(what='colorful kids party favors set: cone party hats, whistles, masks, streamers and rattles'),
       ALT.format(what='children wearing cone party hats and blowing party whistles around a birthday table')),
      unit='pack',
      attrs={'marca_motivo': 'La Fiesta', 'medida_unidades': '12 bolsitas'},
      variants=[V({'color_or_number': 'Surtido', 'pack_size': 'Paquete x12'}, 15),
                V({'color_or_number': 'Rosa', 'pack_size': 'Paquete x12'}, 8),
                V({'color_or_number': 'Azul', 'pack_size': 'Paquete x12'}, 8)],
      tokens=TOK_B),
    P('velas-chispitas-x4', 'Velas Chispitas para Torta x4', PINATAS, CAT, 2.50,
      'Paquete de 4 velas bengala de 18 cm que sueltan chispitas frías por unos 40 segundos. El toque mágico para '
      'el momento del cumpleaños.',
      (STUDIO.format(what='four sparkler birthday candles in a small pack, thin metal sticks'),
       ALT.format(what='sparkler candles glowing on top of a birthday cake in a dim room, sparks flying')),
      unit='pack',
      attrs={'marca_motivo': 'Bengalas para torta', 'medida_unidades': '4 unidades / 18 cm'},
      tokens=TOK_A, stock=60),
    P('canon-confeti-metalizado-30cm', 'Cañón de Confeti Metalizado 30 cm', PINATAS, CAT, 4.00,
      'Lanzador de confeti de aire comprimido, sin pólvora, que dispara papelillo metalizado a varios metros. Se '
      'activa girando la base; ideal para la hora loca y revelaciones de género.',
      (STUDIO.format(what='a cardboard confetti cannon party popper tube with metallic confetti spilling out'),
       ALT.format(what='shiny metallic confetti bursting in the air at a party celebration, bokeh lights')),
      attrs={'marca_motivo': 'Hora Loca', 'medida_unidades': '30 cm'},
      offer=15, stock=40),
    P('banderin-feliz-cumpleanos', 'Banderín de Feliz Cumpleaños Metalizado', PINATAS, CAT, 3.50,
      'Guirnalda de letras metalizadas de cartulina con cinta incluida, de 2.5 metros de largo. Reutilizable y lista '
      'para colgar en la pared o en la mesa de la torta.',
      (STUDIO.format(what='a shiny gold metallic letter bunting garland banner with pennant shapes, letters not readable'),
       ALT.format(what='gold pennant banner hanging on a wall above a decorated birthday dessert table')),
      attrs={'marca_motivo': 'Feliz Cumpleaños', 'medida_unidades': '2.5 m'},
      offer=10, stock=50),
    P('inflador-manual-globos', 'Inflador Manual de Globos Doble Acción', PINATAS, CAT, 5.50,
      'Bomba manual que infla al subir y al bajar, con dos boquillas para globos de látex y globos largos. Ahorra '
      'tiempo y pulmones al decorar.',
      (STUDIO.format(what='a handheld double action plastic balloon air pump with nozzle'),
       ALT.format(what='person inflating a latex balloon with a hand pump while decorating for a party')),
      attrs={'marca_motivo': 'Inflador doble acción', 'medida_unidades': '30 cm / 2 boquillas'},
      stock=25),

    # ------------------------------------------------------------------------------------------------------------------
    # Descartables, Vasos, Platos y Servilletas
    # ------------------------------------------------------------------------------------------------------------------
    P('vasos-plasticos-darnel', 'Vasos Plásticos Darnel x50', DESCARTABLES, CAT, 2.20,
      'Vasos desechables de plástico resistente para refrescos, chicha y cotillón. Paquete de 50 unidades en '
      'varias medidas.',
      (STUDIO.format(what='a stack of clear disposable plastic cups in a sleeve, several sizes'),
       ALT.format(what='plastic cups filled with soda and juice on a kids party table with snacks')),
      attrs={'material': 'Plástico Transparente / Blanco'},
      variants=[V({'size_oz': 'Vaso #7', 'pack_qty': 'Paquete x50'}, 40),
                V({'size_oz': 'Vaso 9 oz', 'pack_qty': 'Paquete x50'}, 30, 2.60),
                V({'size_oz': 'Vaso 12 oz', 'pack_qty': 'Paquete x50'}, 20, 3.20)],
      tokens=TOK_A),
    P('platos-carton-decorados', 'Platos de Cartón Decorados x20', DESCARTABLES, CAT, 3.00,
      'Platos de cartón biodegradable con borde decorado en colores de fiesta. Paquete de 20; plato #6 para torta '
      'o plato #9 para la comida.',
      (STUDIO.format(what='a stack of colorful party paper plates with polka dot and stripe borders'),
       ALT.format(what='party paper plates with slices of birthday cake on a festive dessert table')),
      attrs={'material': 'Cartón / Biodegradable'},
      variants=[V({'size_oz': 'Plato #6 (Torta)', 'pack_qty': 'Paquete x20'}, 25),
                V({'size_oz': 'Plato #9', 'pack_qty': 'Paquete x20'}, 18, 3.80)],
      tokens=TOK_B),
    P('servilletas-decoradas-x20', 'Servilletas Decoradas de Fiesta x20', DESCARTABLES, CAT, 1.80,
      'Servilletas de papel de doble hoja, 33 x 33 cm, con estampado de fiesta a juego con platos y vasos. '
      'Paquete de 20 unidades.',
      (STUDIO.format(what='a stack of folded colorful printed paper party napkins with confetti pattern'),
       ALT.format(what='printed party napkins arranged next to paper plates and cups on a birthday table')),
      attrs={'material': 'Papel (Servilletas)'},
      offer=8, stock=80),
    P('envases-anime-pasapalos-x25', 'Envases de Anime para Comida x25', DESCARTABLES, CAT, 4.50,
      'Envases con tapa de anime para llevar la torta, los pasapalos o el almuerzo de la fiesta. Paquete de 25 '
      'unidades, tamaño almuerzo.',
      (STUDIO.format(what='a stack of white foam hinged takeaway food containers'),
       ALT.format(what='open white foam food container with party snacks and a slice of cake inside')),
      attrs={'material': 'Anime (Poliestireno)'},
      stock=40),
    P('cubiertos-plasticos-x50', 'Cucharitas y Tenedores Plásticos x50', DESCARTABLES, CAT, 2.00,
      'Kit de 50 cubiertos desechables (25 cucharitas y 25 tenedores) de plástico resistente, para la torta, el '
      'helado y los pasapalos.',
      (STUDIO.format(what='a pile of white disposable plastic spoons and forks'),
       ALT.format(what='plastic dessert spoons next to cake slices on paper plates at a party')),
      attrs={'material': 'Plástico Transparente / Blanco'},
      offer=12, stock=55),

    # ------------------------------------------------------------------------------------------------------------------
    # Embalaje, Cajas y Bolsas
    # ------------------------------------------------------------------------------------------------------------------
    P('bolsas-regalo-kraft-x12', 'Bolsas de Regalo Kraft con Asa x12', EMBALAJE, CAT, 6.00,
      'Bolsas de papel kraft con asa retorcida, ideales para sorpresas de cumpleaños o para empacar regalos. '
      'Paquete de 12 unidades en tres medidas.',
      (STUDIO.format(what='a set of brown kraft paper gift bags with twisted paper handles in three sizes'),
       ALT.format(what='kraft paper gift bags filled with candies and tissue paper on a party favor table')),
      attrs={'tipo_bolsa_caja': 'Bolsas de Papel Kraft / Regalo'},
      variants=[V({'capacity_size': 'Pequeña 15 x 20 cm'}, 20),
                V({'capacity_size': 'Mediana 22 x 28 cm'}, 15, 8.00),
                V({'capacity_size': 'Grande 32 x 40 cm'}, 10, 10.50)],
      tokens=TOK_A),
    P('bolsas-celofan-sorpresas-x100', 'Bolsas de Celofán para Sorpresas x100', EMBALAJE, CAT, 3.50,
      'Bolsas transparentes de celofán de 15 x 25 cm con cintas de amarre, perfectas para armar las sorpresas, '
      'galletas y chucherías de la fiesta. Paquete de 100.',
      (STUDIO.format(what='a pack of clear cellophane treat bags with colorful twist ties'),
       ALT.format(what='clear cellophane bags filled with candies and cookies tied with ribbons, party favors')),
      attrs={'tipo_bolsa_caja': 'Bolsas Transparentes (Vivero / Hielo / Celofán)'},
      stock=45),
    P('caja-torta-con-ventana', 'Caja para Torta con Ventana', EMBALAJE, CAT, 1.50,
      'Caja de cartón blanco con ventana transparente para tortas, ponquecitos y postres. Se arma en segundos y '
      'protege tu torta en el traslado.',
      (STUDIO.format(what='a white cardboard cake box with a clear plastic window on the lid'),
       ALT.format(what='decorated birthday cake visible inside a white cake box with window, bakery counter')),
      unit='unit',
      attrs={'tipo_bolsa_caja': 'Cajas de Cartón (Torta / Pizza / Mudanza)'},
      variants=[V({'capacity_size': '20 x 20 x 12 cm'}, 30),
                V({'capacity_size': '25 x 25 x 15 cm'}, 25, 1.90),
                V({'capacity_size': '30 x 30 x 15 cm'}, 15, 2.40)],
      offer=5),

    # ------------------------------------------------------------------------------------------------------------------
    # Servicios (decoración de fiestas, servicio habitual de las piñaterías)
    # ------------------------------------------------------------------------------------------------------------------
    P('decoracion-arco-globos-domicilio', 'Decoración con Arco de Globos a Domicilio', SERVICIOS, CAT, 60.00,
      'Montamos la decoración de tu fiesta en casa o salón en el este de Caracas: arco orgánico de globos en los '
      'colores que elijas, panel de fondo y globos de número. Agenda con 3 días de anticipación.',
      (STUDIO.format(what='an elegant organic balloon arch in pink, gold and white framing a round party backdrop panel'),
       ALT.format(what='decorators assembling a colorful balloon garland in a living room before a birthday party')),
      attrs={'modalidad': 'A Domicilio', 'tiempo_estimado': '2 a 3 horas de montaje', 'garantia': 'Sin garantía'},
      variants=[V({'plan': 'Básico'}, 5), V({'plan': 'Estándar'}, 4, 95.00), V({'plan': 'Premium'}, 2, 150.00)],
      tokens=TOK_C),
]
