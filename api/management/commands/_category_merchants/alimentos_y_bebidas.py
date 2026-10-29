# -*- coding: utf-8 -*-
"""Catálogo demo de Bodegón Altamira Gourmet (Alimentos y Bebidas): 20 productos."""
from ._helpers import ALT, STUDIO, TOK_A, TOK_B, TOK_C, M, P, V, grid, sizes  # noqa: F401

CAT = 'Alimentos y Bebidas'

PRODUCTS = [
    # ------------------------------------------------------------------------------------------------------------------
    # Víveres y Enlatados
    # ------------------------------------------------------------------------------------------------------------------
    P('harina-pan-1kg', 'Harina PAN Blanca 1 kg', 'Víveres y Granos', CAT, 1.45,
      'Harina de maíz blanco precocida, la de siempre para tus arepas, hallaquitas y empanadas. Paquete de 1 kg; '
      'también disponible en versión integral y en paquete de 4 unidades para la semana.',
      (STUDIO.format(what='a 1 kg paper package of white precooked corn flour standing upright, yellow and white '
                          'packaging without readable text'),
       ALT.format(what='freshly grilled Venezuelan arepas on a wooden board next to a bowl of white corn flour')),
      attrs={'marca': 'PAN', 'tipo_vivere': 'Harina de Maíz / Trigo', 'contenido_neto': '1 kg'},
      variants=[V({'presentation': '1 kg', 'type': 'Tradicional'}, 60),
                V({'presentation': '1 kg', 'type': 'Integral'}, 18, 1.75),
                V({'presentation': 'Paquete x4', 'type': 'Tradicional'}, 15, 5.40)],
      tokens=TOK_A),
    P('atun-margarita-aceite-140g', 'Atún Margarita en Aceite 140 g', 'Enlatados y Conservas', CAT, 2.30,
      'Lomitos de atún en aceite vegetal, listos para ensaladas, arepas o pasta. Lata de 140 g con abre fácil, '
      'un clásico de la despensa venezolana.',
      (STUDIO.format(what='a small round tin can of tuna in oil with an easy open pull ring lid, red label without '
                          'readable text'),
       ALT.format(what='open tin of tuna chunks in oil next to a fresh green salad bowl on a kitchen counter')),
      attrs={'marca': 'Margarita', 'contenido_neto': '140 g', 'abre_facil': True},
      offer=5, stock=48),

    # ------------------------------------------------------------------------------------------------------------------
    # Charcutería
    # ------------------------------------------------------------------------------------------------------------------
    P('jamon-pierna-plumrose-kg', 'Jamón de Pierna Plumrose Premium', 'Charcutería', CAT, 13.50,
      'Jamón cocido de pierna, bajo en grasa y de sabor suave, ideal para el pan de cada día o el desayuno de los '
      'chamos. Precio por kilo; te lo rebanamos al momento como prefieras.',
      (STUDIO.format(what='a whole cooked ham leg log next to neatly stacked thin pink ham slices on parchment paper'),
       ALT.format(what='deli counter slicer cutting thin slices of cooked ham, gourmet grocery store')),
      unit='kg',
      attrs={'marca': 'Plumrose', 'tipo_embutido': 'Jamón de Pierna / Espaldilla', 'requiere_refrigeracion': True},
      variants=sizes('slice', ['Rebanado Fino', 'Rebanado Normal', 'En Trozo / Taco'], stock=8),
      offer=7),
    P('tabla-charcuteria-gourmet', 'Tabla de Charcutería Gourmet para Compartir', 'Charcutería', CAT, 34.00,
      'Tabla armada con jamón serrano, salami italiano, pechuga de pavo, queso gouda, queso de cabra, uvas, aceitunas '
      'y frutos secos. Rinde para 4 a 6 personas; perfecta para una reunión en casa.',
      (STUDIO.format(what='a wooden charcuterie board with cured ham, salami slices, cheese cubes, grapes, olives and '
                          'nuts, top view'),
       ALT.format(what='friends sharing a charcuterie board with glasses of red wine on a terrace at sunset')),
      attrs={'tipo_embutido': 'Tabla de Charcutería', 'requiere_refrigeracion': True},
      mods=[M('Complementa tu tabla', [('Grisines artesanales', 3), ('Mermelada de higo', 4),
                                       ('Pan baguette rebanado', 2.5), ('Envoltorio de regalo', 3)], max_sel=4)],
      tokens=TOK_B, stock=6),
    P('jamon-serrano-loncheado-100g', 'Jamón Serrano Español Loncheado 100 g', 'Charcutería', CAT, 7.90,
      'Jamón serrano curado más de 12 meses, importado de España y loncheado en sobre de 100 g. Sácalo de la nevera '
      '10 minutos antes de servir para disfrutar todo su aroma.',
      (STUDIO.format(what='a vacuum sealed pack of thin cured Spanish serrano ham slices arranged in waves'),
       ALT.format(what='thin slices of cured serrano ham on a slate board with breadsticks and manchego cheese')),
      unit='pack',
      attrs={'marca': 'Navidul', 'tipo_embutido': 'Salami / Pepperoni / Jamón Serrano', 'requiere_refrigeracion': True},
      offer=15, stock=25),

    # ------------------------------------------------------------------------------------------------------------------
    # Lácteos y Huevos
    # ------------------------------------------------------------------------------------------------------------------
    P('queso-guayanes-artesanal-kg', 'Queso Guayanés Artesanal', 'Lácteos y Huevos', CAT, 9.50,
      'Queso guayanés fresco, suave y ligeramente salado, traído directo de Bolívar. Precio por kilo; ideal para '
      'cachapas, arepas y desayunos criollos.',
      (STUDIO.format(what='a round soft fresh white Venezuelan guayanes cheese wheel, glossy surface, on a banana leaf'),
       ALT.format(what='a corn cachapa folded with melting soft white cheese on a rustic plate')),
      unit='kg',
      attrs={'tipo_lacteo_huevo': 'Queso Fresco (Guayanés, Telita, Mano, Mozzarella)', 'marca': 'Artesanal de Bolívar'},
      tokens=TOK_A, stock=18),
    P('huevos-gallina-carton', 'Huevos de Gallina Tamaño AA', 'Lácteos y Huevos', CAT, 4.20,
      'Huevos frescos de granja, tamaño AA, seleccionados y limpios. Elige docena, medio cartón o cartón completo de '
      '30 unidades para todo el mes.',
      (STUDIO.format(what='a cardboard egg tray filled with fresh brown and white chicken eggs'),
       ALT.format(what='fresh eggs in a ceramic bowl on a kitchen table next to a frying pan with scrambled eggs')),
      attrs={'tipo_lacteo_huevo': 'Huevos de Gallina / Codorniz', 'marca': 'Granja Los Andes',
             'unidades_por_empaque': '12, 15 o 30 unidades'},
      variants=[V({'presentation': 'Docena (12 huevos)', 'cut': 'No aplica'}, 20, 3.40),
                V({'presentation': 'Medio Cartón (15 huevos)', 'cut': 'No aplica'}, 16),
                V({'presentation': 'Cartón Completo (30 huevos)', 'cut': 'No aplica'}, 10, 7.90)],
      offer=10),
    P('queso-parmesano-reggiano', 'Queso Parmigiano Reggiano Importado', 'Lácteos y Huevos', CAT, 11.90,
      'Parmigiano Reggiano DOP madurado 24 meses, importado de Italia. En trozo para tabla o rallado al momento para '
      'tus pastas y risottos.',
      (STUDIO.format(what='a wedge of aged parmigiano reggiano cheese with a crumbly texture and a small cheese knife'),
       ALT.format(what='freshly grated parmesan cheese falling over a plate of spaghetti, warm kitchen light')),
      attrs={'tipo_lacteo_huevo': 'Queso Amarillo (Gouda, Edam, Parmesano)', 'marca': 'Parmigiano Reggiano DOP'},
      variants=[V({'presentation': '250 g', 'cut': 'En Trozo'}, 10),
                V({'presentation': '250 g', 'cut': 'Rallado'}, 8),
                V({'presentation': '500 g', 'cut': 'En Trozo'}, 4, 22.50),
                V({'presentation': '500 g', 'cut': 'Rallado'}, 0, 22.50)],
      tokens=TOK_B),

    # ------------------------------------------------------------------------------------------------------------------
    # Café, Té e Infusiones
    # ------------------------------------------------------------------------------------------------------------------
    P('cafe-fama-america-500g', 'Café Fama de América Molido 500 g', 'Café, Té e Infusiones', CAT, 6.80,
      'Café venezolano 100 % arábica de tueste medio, con cuerpo y aroma intenso. Disponible molido para greca o '
      'colador, molido espresso y en grano entero.',
      (STUDIO.format(what='a 500 g foil coffee bag standing next to a small pile of roasted coffee beans, no readable text'),
       ALT.format(what='a stovetop moka pot pouring black coffee into a small cup at breakfast, morning window light')),
      attrs={'marca': 'Fama de América', 'tipo_molienda': 'Café Molido Gourmet', 'contenido_neto': '500 g'},
      variants=[V({'weight': '500 g', 'grind': 'Molido Estándar (Greca/Colador)'}, 30),
                V({'weight': '500 g', 'grind': 'Molido Espresso'}, 14),
                V({'weight': '500 g', 'grind': 'En Grano Entero'}, 9),
                V({'weight': '250 g', 'grind': 'Molido Estándar (Greca/Colador)'}, 25, 3.70)],
      tokens=TOK_A),
    P('cacao-polvo-el-rey-250g', 'Cacao en Polvo 100 % El Rey 250 g', 'Café, Té e Infusiones', CAT, 7.20,
      'Cacao venezolano puro en polvo, sin azúcar añadida, de Chocolates El Rey. Ideal para repostería, tortas, '
      'brownies y un buen chocolate caliente.',
      (STUDIO.format(what='a stand-up pouch of pure dark cocoa powder next to a small bowl of cocoa powder and cacao pods'),
       ALT.format(what='a cup of hot chocolate dusted with cocoa powder next to a chocolate cake slice, cozy cafe table')),
      attrs={'marca': 'El Rey', 'tipo_molienda': 'Cacao / Chocolate en Polvo', 'contenido_neto': '250 g'},
      stock=20),

    # ------------------------------------------------------------------------------------------------------------------
    # Bebidas, Refrescos y Maltas
    # ------------------------------------------------------------------------------------------------------------------
    P('maltin-polar-six-pack', 'Maltín Polar Lata 355 ml', 'Bebidas, Refrescos y Maltas', CAT, 0.95,
      'La malta de toda la vida, sin alcohol y con el sabor que acompaña tus empanadas. Lata de 355 ml, en '
      'six-pack o en caja de 24 para la fiesta.',
      (STUDIO.format(what='a cold aluminum soda can of dark malt beverage with condensation droplets, no readable text'),
       ALT.format(what='six pack of cold malt beverage cans on ice next to fried empanadas, outdoor party table')),
      attrs={'marca': 'Polar', 'volumen_neto': '355 ml', 'retornable': False, 'sin_azucar': False},
      variants=[V({'volume': 'Lata 355 ml'}, 72), V({'volume': 'Six-Pack (6 und)'}, 20, 5.40),
                V({'volume': 'Caja / Bulto (24 und)'}, 6, 20.50)],
      mods=[M('Temperatura de Entrega', [('Bien fría (De nevera)', 0), ('Natural / Al clima', 0)], required=True)]),
    P('agua-minalba-1-5l', 'Agua Mineral Minalba 1.5 L', 'Bebidas, Refrescos y Maltas', CAT, 1.20,
      'Agua mineral natural de manantial, baja en sodio, en botella de 1.5 litros. Perfecta para llevar al trabajo o '
      'tener siempre fría en la nevera.',
      (STUDIO.format(what='a clear 1.5 liter plastic bottle of mineral water with a blue cap and blank label'),
       ALT.format(what='a glass of cold sparkling clear water poured from a plastic bottle, mountain view background')),
      attrs={'marca': 'Minalba', 'volumen_neto': '1.5 L', 'retornable': False, 'sin_azucar': True},
      stock=80),

    # ------------------------------------------------------------------------------------------------------------------
    # Licores
    # ------------------------------------------------------------------------------------------------------------------
    P('ron-santa-teresa-1796', 'Ron Santa Teresa 1796 Solera 0.70 L', 'Licores', CAT, 44.00,
      'Ron extra añejo venezolano elaborado por el método solera en la Hacienda Santa Teresa, Aragua. Notas de roble, '
      'cacao y frutos secos; para disfrutar solo o con una piedra de hielo.',
      (STUDIO.format(what='an elegant bottle of extra aged dark amber rum with a cork stopper, label without readable text'),
       ALT.format(what='a glass of aged rum with one large ice cube on a wooden bar counter, warm moody light')),
      attrs={'marca': 'Santa Teresa', 'tipo_licor': 'Ron Añejo', 'volumen_neto': '700 ml', 'grado_alcoholico': '40 %'},
      mods=[M('Presentación de regalo', [('Bolsa de regalo', 2), ('Caja de regalo con lazo', 5)])],
      tokens=TOK_C, stock=12),
    P('ron-diplomatico-reserva-exclusiva', 'Ron Diplomático Reserva Exclusiva', 'Licores', CAT, 38.00,
      'Ron añejo premium de Destilerías Unidas, Lara, con hasta 12 años de añejamiento. Dulce y redondo, con notas '
      'de caramelo, vainilla y naranja.',
      (STUDIO.format(what='a short round bottle of premium dark rum with a wooden stopper, amber liquid, blank label'),
       ALT.format(what='premium dark rum served neat in a tasting glass next to orange peel and dark chocolate')),
      attrs={'marca': 'Diplomático', 'tipo_licor': 'Ron Añejo', 'volumen_neto': '750 ml', 'grado_alcoholico': '40 %'},
      variants=[V({'presentation': 'Botella 0.70L / 750ml'}, 10), V({'presentation': 'Botella 1 Litro'}, 4, 49.00)],
      offer=10),
    P('cerveza-polar-pilsen-lata', 'Cerveza Polar Pilsen Lata 355 ml', 'Licores', CAT, 6.90,
      'La cerveza de Venezuela, refrescante y ligera. Six-pack de latas de 355 ml o caja de 24 para la parrilla del '
      'fin de semana; te la enviamos bien fría.',
      (STUDIO.format(what='a six pack of cold aluminum beer cans with condensation droplets, blank design'),
       ALT.format(what='cold beer cans in a cooler full of ice at a backyard barbecue, sunny day')),
      unit='pack',
      attrs={'marca': 'Polar', 'tipo_licor': 'Cerveza', 'volumen_neto': '355 ml', 'grado_alcoholico': '5 %'},
      variants=[V({'presentation': 'Six-Pack (6 und)'}, 30), V({'presentation': 'Media Caja (12 und)'}, 14, 13.40),
                V({'presentation': 'Caja / Gavera (24 und)'}, 8, 25.90)],
      mods=[M('Temperatura y Adicionales', [('Bien fría (Lista para tomar)', 0), ('Agregar Bolsa de Hielo', 1.5),
                                            ('Agregar Vasos Descartables', 1)], max_sel=3)],
      tokens=TOK_A),
    P('vino-pomar-reserva-tinto', 'Vino Tinto Pomar Reserva 750 ml', 'Licores', CAT, 16.50,
      'Vino tinto venezolano de Bodegas Pomar, Carora, ensamblaje de Tempranillo y Petit Verdot con crianza en roble. '
      'Acompaña carnes rojas, quesos curados y pastas.',
      (STUDIO.format(what='a bottle of red wine with a dark glass and a burgundy foil capsule, blank label'),
       ALT.format(what='red wine poured into a glass at a dinner table with grilled meat and candles')),
      attrs={'marca': 'Pomar', 'tipo_licor': 'Vino Tinto / Blanco / Rosado', 'volumen_neto': '750 ml',
             'grado_alcoholico': '13 %'},
      offer=12, stock=18),

    # ------------------------------------------------------------------------------------------------------------------
    # Chucherías, Snacks y Dulces
    # ------------------------------------------------------------------------------------------------------------------
    P('chocolate-el-rey-barra-80g', 'Chocolate El Rey Barra 80 g', 'Chucherías, Snacks y Dulces', CAT, 3.50,
      'Chocolate venezolano de origen elaborado con cacao Carenero Superior. Elige oscuro 70 % o con leche; también '
      'en display de 12 barras para regalar.',
      (STUDIO.format(what='a premium dark chocolate bar partially unwrapped showing chocolate squares, blank wrapper'),
       ALT.format(what='broken pieces of dark chocolate with cacao beans on a slate surface, moody light')),
      attrs={'marca': 'El Rey', 'tipo_snack': 'Chocolates y Bombones', 'contenido_neto': '80 g'},
      variants=grid('presentation', ['Unidad / Detal'], 'flavor', ['Chocolate Oscuro', 'Chocolate con Leche'], stock=20)
      + [V({'presentation': 'Display / Tira (12 und)', 'flavor': 'Chocolate Oscuro'}, 5, 38.00)],
      tokens=TOK_B),
    P('cocosette-display-12', 'Cocosette Nestlé Display x12', 'Chucherías, Snacks y Dulces', CAT, 6.50,
      'La galleta wafer rellena de crema de coco más querida de Venezuela. Display de 12 unidades para la lonchera o '
      'la merienda de la oficina.',
      (STUDIO.format(what='a display box of individually wrapped coconut cream wafer cookies, blank wrappers'),
       ALT.format(what='a coconut wafer cookie broken in half showing creamy coconut filling, next to a glass of milk')),
      unit='box',
      attrs={'marca': 'Nestlé', 'tipo_snack': 'Galletas Dulces y Saladas', 'contenido_neto': '12 x 50 g'},
      offer=8, stock=30),

    # ------------------------------------------------------------------------------------------------------------------
    # Salsas, Condimentos y Aceites
    # ------------------------------------------------------------------------------------------------------------------
    P('aceite-oliva-borges-extra-virgen', 'Aceite de Oliva Extra Virgen Borges', 'Salsas, Condimentos y Aceites', CAT, 8.90,
      'Aceite de oliva extra virgen de primera presión en frío, importado de España. Afrutado y suave, para ensaladas, '
      'carpaccios y pan tostado.',
      (STUDIO.format(what='a tall glass bottle of golden green extra virgin olive oil with a black cap, blank label'),
       ALT.format(what='olive oil drizzled over a fresh tomato and basil salad, rustic kitchen, sunlight')),
      attrs={'marca': 'Borges', 'tipo_producto': 'Aceite de Oliva', 'contenido_neto': '500 ml'},
      variants=[V({'size': '500 ml'}, 16), V({'size': '1 Litro'}, 8, 15.90)],
      tokens=TOK_B),

    # ------------------------------------------------------------------------------------------------------------------
    # Congelados y Pasapalos
    # ------------------------------------------------------------------------------------------------------------------
    P('tequenos-congelados-queso', 'Tequeños de Queso Blanco Congelados', 'Congelados y Pasapalos', CAT, 6.50,
      'Tequeños artesanales con masa crujiente y bastón de queso blanco llanero. Te los llevamos congelados para '
      'freír en casa en 5 minutos, o fritos y listos para la fiesta.',
      (STUDIO.format(what='a tray of golden fried Venezuelan tequenos cheese sticks with a small bowl of dipping sauce'),
       ALT.format(what='frozen raw tequenos cheese sticks arranged in rows on a tray, kitchen counter')),
      attrs={'tipo_congelado': 'Tequeños', 'unidades_por_empaque': 12, 'estado_entrega': 'Crudo Congelado'},
      variants=[V({'count': 'Docena (12 und)', 'filling': 'Queso Blanco'}, 25),
                V({'count': 'Bandeja x24 und', 'filling': 'Queso Blanco'}, 15, 12.00),
                V({'count': 'Bandeja x50 und', 'filling': 'Queso Blanco'}, 8, 23.00),
                V({'count': 'Docena (12 und)', 'filling': 'Guayaba y Queso'}, 10, 7.20)],
      mods=[M('Modo de Entrega', [('Congelados (Para freír/hornear en casa)', 0), ('Fritos / Listos para comer', 2)],
              required=True)],
      tokens=TOK_C),
]
