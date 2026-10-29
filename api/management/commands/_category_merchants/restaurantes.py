# -*- coding: utf-8 -*-
"""Catálogo demo de Sabor del Ávila (Restaurantes y Comida Preparada): 20 productos."""
from ._helpers import ALT, STUDIO, TOK_A, TOK_B, TOK_C, M, P, V, grid, sizes  # noqa: F401

CAT = 'Restaurantes y Comida Preparada'

AREPAS = 'Arepas, Cachapas y Desayunos Criollos'
EMPANADAS = 'Empanadas, Pastelitos y Frituras'
PASAPALOS = 'Tequeños, Pasapalos y Picadas Calientes'
PARRILLA = 'Parrillas, Carnes y Asados'
CRIOLLA = 'Almuerzos, Comida Criolla y Ejecutivos'
SOPAS = 'Sopas, Hervidos y Mondongos'
PESCADOS = 'Pescados Fritos, Mariscos y Ceviches'
CALLEJERAS = 'Chicha, Cocadas y Bebidas Callejeras'
JUGOS = 'Jugos Naturales, Café y Batidos'
POSTRES = 'Tortas, Postres, Donas y Dulcería'

# Grupos de personalización reutilizables (estilo PedidosYa).
_EXTRAS_AREPA = M('Extras y Contornos', [('Extra Queso de Mano / Telita / Guayanés', 2), ('Extra Queso Amarillo Rallado', 1.5),
                                         ('Extra Aguacate', 1.5), ('Ración de Cochino Frito / Chicharrón', 3),
                                         ('Tajadas con Queso', 2.5), ('Nata Criolla / Suero', 1)], max_sel=4)
_SALSAS_AREPA = M('Salsas y Mantequilla', [('Con Mantequilla', 0), ('Sin Mantequilla', 0), ('Guasacaca', 0.5),
                                           ('Salsa de Ajo', 0.5), ('Picante aparte', 0)], max_sel=3)
_TERMINO = M('Término de la Carne', [('Término Medio (1/2 - Jugosa)', 0), ('Tres Cuartos (3/4 - Al punto)', 0),
                                     ('Bien Cocida', 0)], required=True)

PRODUCTS = [
    # ------------------------------------------------------------------------------------------------------------------
    # Arepas, Cachapas y Desayunos Criollos
    # ------------------------------------------------------------------------------------------------------------------
    P('arepa-reina-pepeada', 'Arepa Reina Pepeada', AREPAS, CAT, 5.50,
      'Arepa asada recién hecha, rellena con ensalada de pollo desmechado, aguacate y un toque de mayonesa y cilantro. '
      'La reina de la casa, hecha al momento.',
      (STUDIO.format(what='a Venezuelan arepa stuffed with creamy chicken and avocado salad, on a rustic plate'),
       ALT.format(what='hands holding a reina pepeada arepa overflowing with chicken avocado filling, restaurant terrace')),
      attrs={'tipo_plato': 'Arepa Rellena', 'tiempo_preparacion_min': 10, 'porciones_personas': '1 persona'},
      mods=[M('Tipo de Arepa', [('Arepa Asada', 0), ('Arepa Frita (Con huequito)', 0.5)], required=True),
            _EXTRAS_AREPA, _SALSAS_AREPA],
      tokens=TOK_A, stock=40),
    P('arepa-rellena-a-tu-gusto', 'Arepa Rellena a tu Gusto', AREPAS, CAT, 4.50,
      'Elige tu relleno favorito: dominó, perico, jamón y queso, catira, pelúa o pabellón. Arepa asada al budare, '
      'crujiente por fuera y suavecita por dentro.',
      (STUDIO.format(what='three Venezuelan arepas with different fillings: black beans and white cheese, shredded beef, '
                          'scrambled eggs'),
       ALT.format(what='arepas being grilled on a traditional cast iron griddle, steam rising, open kitchen')),
      attrs={'tipo_plato': 'Arepa Rellena', 'tiempo_preparacion_min': 10, 'porciones_personas': '1 persona'},
      variants=[V({'filling': 'Dominó', 'cooking_style': 'Arepa Asada'}, 40),
                V({'filling': 'Perico con Queso', 'cooking_style': 'Arepa Asada'}, 35),
                V({'filling': 'Jamón y Queso', 'cooking_style': 'Arepa Asada'}, 30),
                V({'filling': 'Catira (Pollo y Queso Amarillo)', 'cooking_style': 'Arepa Asada'}, 25, 5.50),
                V({'filling': 'Pelúa (Carne Mechada y Gouda)', 'cooking_style': 'Arepa Asada'}, 25, 6.50),
                V({'filling': 'Pabellón', 'cooking_style': 'Arepa Asada'}, 20, 6.80)],
      mods=[_EXTRAS_AREPA, _SALSAS_AREPA]),
    P('cachapa-queso-de-mano', 'Cachapa con Queso de Mano', AREPAS, CAT, 7.50,
      'Cachapa de maíz tierno molido en casa, dulcita y dorada en el budare, con queso de mano que se derrite. '
      'Pídela con cochino frito para la versión completa.',
      (STUDIO.format(what='a golden sweet corn cachapa pancake folded over a thick slice of soft white cheese'),
       ALT.format(what='cachapa with fried pork chunks and melted cheese on a wooden table, Venezuelan roadside style')),
      attrs={'tipo_plato': 'Cachapa', 'tiempo_preparacion_min': 12, 'porciones_personas': '1 persona'},
      variants=[V({'filling': 'Cachapa con Queso de Mano', 'cooking_style': 'Cachapa Tradicional de Maíz'}, 30),
                V({'filling': 'Cachapa con Queso y Cochino Frito', 'cooking_style': 'Cachapa Tradicional de Maíz'}, 18,
                  10.50)],
      mods=[_EXTRAS_AREPA, M('Salsas y Mantequilla', [('Con Mantequilla', 0), ('Sin Mantequilla', 0)])],
      tokens=TOK_B),
    P('desayuno-criollo-completo', 'Desayuno Criollo Completo', AREPAS, CAT, 9.50,
      'Perico, caraotas negras refritas, queso blanco rallado, tajadas de plátano maduro, nata y dos arepitas. '
      'El desayuno de domingo que te recuerda a casa.',
      (STUDIO.format(what='a Venezuelan breakfast plate with scrambled eggs with tomato, black beans, grated white cheese, '
                          'fried sweet plantain and small arepas'),
       ALT.format(what='Venezuelan breakfast plate with a cup of black coffee on a sunny restaurant terrace')),
      attrs={'tipo_plato': 'Desayuno Criollo Completo', 'tiempo_preparacion_min': 15, 'porciones_personas': '1 persona'},
      mods=[M('Cambia tu Huevo', [('Perico (Tradicional)', 0), ('Huevos Fritos', 0), ('Huevos Revueltos Solos', 0)],
              required=True),
            M('Agrega a tu Desayuno', [('Carne Mechada', 2.5), ('Aguacate', 1.5), ('Arepita adicional', 0.8),
                                       ('Café Marrón Pequeño', 1.2)], max_sel=4)],
      tokens=TOK_A, stock=30),

    # ------------------------------------------------------------------------------------------------------------------
    # Empanadas, Pastelitos y Frituras
    # ------------------------------------------------------------------------------------------------------------------
    P('empanada-de-maiz', 'Empanada de Maíz', EMPANADAS, CAT, 2.50,
      'Empanada frita de masa de maíz, crujiente y bien rellena. Viene con guasacaca o salsa de ajo a tu elección.',
      (STUDIO.format(what='two golden crispy fried Venezuelan corn empanadas, one cut open showing shredded beef filling'),
       ALT.format(what='a basket of fried corn empanadas with a small bowl of green guasacaca sauce, morning light')),
      attrs={'tipo_fritura': 'Empanada de Maíz', 'relleno_principal': 'Según variante', 'tiempo_preparacion_min': 8},
      variants=[V({'filling': 'Queso Blanco', 'size': 'Regular / Tradicional'}, 40),
                V({'filling': 'Carne Mechada', 'size': 'Regular / Tradicional'}, 35, 2.80),
                V({'filling': 'Pollo Guisado', 'size': 'Regular / Tradicional'}, 35, 2.80),
                V({'filling': 'Cazón / Pescado', 'size': 'Regular / Tradicional'}, 0, 3.20),
                V({'filling': 'Dominó (Caraotas con Queso)', 'size': 'Regular / Tradicional'}, 25),
                V({'filling': 'Pabellón (Carne, Caraota, Tajada y Queso)', 'size': 'Operada / Doble Relleno'}, 20, 3.80)],
      mods=[M('Salsas para Acompañar', [('Guasacaca', 0), ('Salsa de Ajo', 0), ('Picante / Ají Criollo', 0),
                                        ('Sin salsas', 0)], max_sel=2),
            M('Adicionales de Relleno', [('Extra Queso Blanco / Amarillo', 0.8), ('Tajadas de Plátano', 0.8),
                                         ('Aguacate', 1)], max_sel=3)]),
    P('pastelitos-andinos-racion', 'Pastelitos Andinos (Ración de 3)', EMPANADAS, CAT, 6.00,
      'Tres pastelitos de masa de trigo hojaldrada, fritos al momento como en Mérida. Rellenos de carne molida con '
      'arroz, papa con queso o pizza.',
      (STUDIO.format(what='three golden flaky fried Andean pastelitos with bubbly crispy dough on a plate'),
       ALT.format(what='Andean pastelitos with a cup of coffee on a wooden table, mountain cafe vibe')),
      unit='portion',
      attrs={'tipo_fritura': 'Pastelito Andino / Hoja', 'relleno_principal': 'Carne, papa con queso o pizza',
             'tiempo_preparacion_min': 10},
      variants=[V({'filling': 'Carne Molida con Arroz (Pastelito)', 'size': 'Regular / Tradicional'}, 20),
                V({'filling': 'Papa con Queso (Pastelito)', 'size': 'Regular / Tradicional'}, 18),
                V({'filling': 'Pizza (Pastelito)', 'size': 'Regular / Tradicional'}, 15)],
      mods=[M('Salsas para Acompañar', [('Salsa de Ajo', 0), ('Salsa Tártara / Rosada', 0), ('Picante / Ají Criollo', 0)],
              max_sel=2)],
      offer=15),

    # ------------------------------------------------------------------------------------------------------------------
    # Tequeños, Pasapalos y Picadas Calientes
    # ------------------------------------------------------------------------------------------------------------------
    P('tequenos-queso-blanco', 'Tequeños de Queso Blanco', PASAPALOS, CAT, 4.50,
      'Tequeños fritos al momento, con masa crocante y bastón de queso blanco llanero que estira. Desde la ración '
      'para picar hasta la bandeja para la fiesta.',
      (STUDIO.format(what='golden fried tequenos cheese sticks, one broken showing stretchy melted white cheese, with '
                          'garlic dipping sauce'),
       ALT.format(what='a party tray full of fried tequenos with assorted dipping sauces, festive table')),
      attrs={'tipo_pasapalo': 'Tequeños Tradicionales', 'unidades_incluidas': 5, 'tiempo_preparacion_min': 12},
      variants=[V({'count': 'Ración x5 und', 'flavor': 'Queso Blanco Tradicional'}, 40),
                V({'count': 'Ración x10 und', 'flavor': 'Queso Blanco Tradicional'}, 30, 8.00),
                V({'count': 'Bandeja Festera x25 und', 'flavor': 'Queso Blanco Tradicional'}, 10, 18.00),
                V({'count': 'Bandeja Festera x50 und', 'flavor': 'Queso Blanco Tradicional'}, 5, 34.00),
                V({'count': 'Ración x5 und', 'flavor': 'Guayaba y Queso'}, 15, 5.00)],
      mods=[M('Elige tus Salsas (Dip)', [('Salsa de Ajo', 0), ('Salsa Tártara', 0), ('Salsa de Maíz / Rosada', 0),
                                         ('Miel Mostaza', 0.5), ('Guasacaca', 0.5)], max_sel=2)],
      tokens=TOK_B),
    P('tostones-playeros-queso', 'Tostones Playeros con Queso', PASAPALOS, CAT, 7.00,
      'Tostones de plátano verde bien aplastados y crujientes, cubiertos con queso blanco rallado, ensalada rallada, '
      'salsa rosada y salsa de ajo. Como en la playa, pero en Los Palos Grandes.',
      (STUDIO.format(what='crispy smashed green plantain tostones topped with grated white cheese, shredded cabbage and '
                          'pink sauce'),
       ALT.format(what='plate of beach style tostones with cheese on a terrace table, cold drink beside, sunny day')),
      unit='portion',
      attrs={'tipo_pasapalo': 'Tostones Playeros con Queso', 'unidades_incluidas': 4, 'tiempo_preparacion_min': 12},
      mods=[M('Elige tus Salsas (Dip)', [('Salsa de Ajo', 0), ('Salsa de Maíz / Rosada', 0), ('Guasacaca', 0.5)],
              max_sel=3)],
      offer=8, stock=25),

    # ------------------------------------------------------------------------------------------------------------------
    # Parrillas, Carnes y Asados
    # ------------------------------------------------------------------------------------------------------------------
    P('parrilla-mixta-sabor-avila', 'Parrilla Mixta Sabor del Ávila', PARRILLA, CAT, 16.00,
      'Res, pollo, cerdo y chorizo ahumado a la brasa, servidos con yuca sancochada, guasacaca y arepitas. '
      'Elige la porción individual, para dos o la familiar.',
      (STUDIO.format(what='a mixed grill platter with grilled beef, chicken, pork, chorizo sausage, boiled cassava and '
                          'green guasacaca sauce'),
       ALT.format(what='sizzling mixed grill on a charcoal barbecue at a Venezuelan restaurant, flames and smoke')),
      attrs={'peso_aprox_proteina': '400 g por persona', 'porciones_personas': '1, 2 o 4 personas',
             'tiempo_preparacion_min': 25},
      variants=[V({'size': 'Individual (1 Persona)', 'cut': 'Parrilla Mixta (Res, Pollo, Cerdo y Chorizo)'}, 20),
                V({'size': 'Dúo (Para 2 Personas)', 'cut': 'Parrilla Mixta (Res, Pollo, Cerdo y Chorizo)'}, 12, 29.00),
                V({'size': 'Familiar (3-4 Personas)', 'cut': 'Parrilla Mixta (Res, Pollo, Cerdo y Chorizo)'}, 6, 52.00)],
      mods=[_TERMINO,
            M('Contornos y Extras de Parrilla', [('Yuca Frita / Sancochada con Guasacaca', 0), ('Papas Fritas', 0),
                                                 ('Ensalada César / Mixta / Rallada', 0),
                                                 ('Extra Chorizo Ahumado / Chistorra', 3),
                                                 ('Extra Morcilla / Chinchurria', 3), ('Extra Queso a la Plancha', 2.5)],
              max_sel=3)],
      tokens=TOK_C),
    P('punta-trasera-parrilla-300g', 'Punta Trasera a la Parrilla 300 g', PARRILLA, CAT, 15.50,
      'Punta trasera madurada, sellada a la brasa con sal gruesa y servida en su jugo. Incluye dos contornos a tu '
      'elección y chimichurri de la casa.',
      (STUDIO.format(what='a juicy sliced grilled picanha beef steak with fat cap, chimichurri sauce and cassava fries'),
       ALT.format(what='grilled picanha steak being sliced on a wooden board, juicy pink center, restaurant ambiance')),
      attrs={'peso_aprox_proteina': '300 g', 'porciones_personas': '1 persona', 'tiempo_preparacion_min': 20},
      mods=[_TERMINO,
            M('Elige 2 Contornos', [('Yuca Frita / Sancochada con Guasacaca', 0), ('Papas Fritas', 0),
                                    ('Ensalada César / Mixta / Rallada', 0), ('Arepitas con Nata Criolla', 0)],
              required=True, max_sel=2)],
      offer=10, stock=20),

    # ------------------------------------------------------------------------------------------------------------------
    # Almuerzos, Comida Criolla y Ejecutivos
    # ------------------------------------------------------------------------------------------------------------------
    P('pabellon-criollo', 'Pabellón Criollo', CRIOLLA, CAT, 11.00,
      'El plato nacional: carne mechada jugosa, arroz blanco, caraotas negras con queso blanco rallado y tajadas de '
      'plátano maduro. Pídelo a caballo con un huevo frito encima.',
      (STUDIO.format(what='a traditional Venezuelan pabellon criollo plate with shredded beef, white rice, black beans '
                          'with grated cheese and fried sweet plantains'),
       ALT.format(what='pabellon criollo topped with a fried egg on a colorful tablecloth, Venezuelan restaurant')),
      unit='portion',
      attrs={'contornos_incluidos': 'Arroz, caraotas y tajadas', 'incluye_sopa_o_bebida': 'Solo Plato Principal (Seco)',
             'tiempo_preparacion_min': 15},
      mods=[M('Adicionales del Almuerzo', [('Huevo Frito (A Caballo)', 1.5), ('Ración de Aguacate', 1.5),
                                           ('Queso Blanco Rallado sobre Caraotas/Tajadas', 1),
                                           ('Arepa Asada acompañante', 1)], max_sel=4)],
      tokens=TOK_A, stock=35),
    P('asado-negro-arroz-platano', 'Asado Negro con Arroz y Plátano', CRIOLLA, CAT, 12.50,
      'Muchacho redondo cocinado lentamente en salsa de papelón, vino y especias, como lo hacía la abuela caraqueña. '
      'Servido en rebanadas con dos contornos a elegir.',
      (STUDIO.format(what='slices of Venezuelan asado negro beef in dark glossy sauce with white rice and fried plantain'),
       ALT.format(what='asado negro beef roast being sliced, dark caramelized sauce, home style kitchen')),
      unit='portion',
      attrs={'contornos_incluidos': '2 contornos a elegir', 'incluye_sopa_o_bebida': 'Solo Plato Principal (Seco)',
             'tiempo_preparacion_min': 15},
      mods=[M('Elige tus Contornos', [('Arroz Blanco', 0), ('Tajadas de Plátano Maduro', 0), ('Papas Fritas / Puré de Papas', 0),
                                      ('Ensalada del Día (Rusa / César / Mixta)', 0), ('Yuca / Tostones', 0)],
              required=True, max_sel=2)],
      stock=20),
    P('almuerzo-ejecutivo-del-dia', 'Almuerzo Ejecutivo del Día', CRIOLLA, CAT, 8.50,
      'Sopa del día, plato principal con dos contornos y jugo natural. Cada día cambiamos el menú; elige tu proteína '
      'y llévatelo a la oficina en 20 minutos.',
      (STUDIO.format(what='a Venezuelan executive lunch set with a bowl of soup, a plate of grilled chicken with rice '
                          'and salad, and a glass of fruit juice'),
       ALT.format(what='takeaway lunch boxes with homestyle Venezuelan food on an office desk')),
      unit='portion',
      attrs={'contornos_incluidos': '2 contornos a elegir', 'incluye_sopa_o_bebida': 'Incluye Sopa + Seco + Jugo',
             'tiempo_preparacion_min': 20},
      variants=[V({'protein': 'Carne Mechada / Asado Negro', 'size': 'Combo Ejecutivo (Sopa + Seco + Jugo)'}, 20),
                V({'protein': 'Pollo Horneado / A la Plancha / Guisado', 'size': 'Combo Ejecutivo (Sopa + Seco + Jugo)'}, 25),
                V({'protein': 'Milanesa de Pollo / Parmesana', 'size': 'Combo Ejecutivo (Sopa + Seco + Jugo)'}, 15, 9.00),
                V({'protein': 'Pescado / Filete con Contornos', 'size': 'Combo Ejecutivo (Sopa + Seco + Jugo)'}, 10, 9.50)],
      mods=[M('Elige tus Contornos', [('Arroz Blanco', 0), ('Caraotas Negras / Frijoles', 0),
                                      ('Tajadas de Plátano Maduro', 0), ('Ensalada del Día (Rusa / César / Mixta)', 0),
                                      ('Pasta Corta', 0)], required=True, max_sel=2)],
      offer=12),

    # ------------------------------------------------------------------------------------------------------------------
    # Sopas, Hervidos y Mondongos
    # ------------------------------------------------------------------------------------------------------------------
    P('hervido-criollo', 'Hervido Criollo', SOPAS, CAT, 8.00,
      'Sopa criolla con presa, yuca, ocumo, auyama, jojoto y cilantro, cocinada a fuego lento desde temprano. '
      'Sale con arepa asada; también por litro para la familia.',
      (STUDIO.format(what='a big bowl of Venezuelan sancocho soup with beef ribs, cassava, corn on the cob, pumpkin and '
                          'cilantro'),
       ALT.format(what='steaming pot of Venezuelan hervido soup with vegetables on a wood fire, rustic kitchen')),
      unit='portion',
      attrs={'incluye_acompanante': 'Arepa asada', 'tiempo_preparacion_min': 10},
      variants=[V({'type': 'Hervido de Res / Costilla', 'size': 'Porción Regular (Con presa y verdura)'}, 20),
                V({'type': 'Hervido de Gallina / Pollo', 'size': 'Porción Regular (Con presa y verdura)'}, 20),
                V({'type': 'Cruzado (Res y Gallina/Pollo)', 'size': 'Porción Regular (Con presa y verdura)'}, 12, 9.00),
                V({'type': 'Hervido de Res / Costilla', 'size': 'Envase Familiar 1 Litro'}, 8, 13.00)],
      mods=[M('Acompañantes de la Sopa', [('Arepa adicional', 1), ('Casabe', 1), ('Limón y Picante aparte', 0),
                                          ('Porción de Aguacate', 1.5)], max_sel=3)],
      tokens=TOK_B),

    # ------------------------------------------------------------------------------------------------------------------
    # Pescados Fritos, Mariscos y Ceviches
    # ------------------------------------------------------------------------------------------------------------------
    P('pargo-frito-tostones', 'Pargo Rojo Frito con Tostones', PESCADOS, CAT, 18.00,
      'Pargo rojo entero, frito bien crujiente y servido con tostones, ensalada rallada y limón. El sabor de '
      'Higuerote sin salir de Caracas.',
      (STUDIO.format(what='a whole crispy fried red snapper fish with green plantain tostones, shredded cabbage salad '
                          'and lime wedges'),
       ALT.format(what='fried whole fish platter on a seaside style restaurant table with a cold drink')),
      attrs={'tiempo_preparacion_min': 25, 'porciones_personas': '1 a 2 personas'},
      variants=[V({'seafood_type': 'Pargo Rojo Entero Frito', 'size': 'Pescado Mediano (400g - 600g)'}, 10),
                V({'seafood_type': 'Pargo Rojo Entero Frito', 'size': 'Pescado Grande (700g - 1kg)'}, 6, 26.00)],
      mods=[M('Contornos Playeros', [('Tostones con Queso y Ensalada Rallada', 0), ('Yuca Frita con Guasacaca', 0),
                                     ('Arroz Blanco / Arroz con Coco', 0), ('Porción de Aguacate', 1.5)],
              required=True, max_sel=2)],
      tokens=TOK_C),

    # ------------------------------------------------------------------------------------------------------------------
    # Bebidas criollas
    # ------------------------------------------------------------------------------------------------------------------
    P('papelon-con-limon', 'Papelón con Limón 16 oz', CALLEJERAS, CAT, 2.50,
      'Bebida tradicional de papelón de caña con limón recién exprimido, bien fría. Refrescante y sin conservantes, '
      'el acompañante perfecto de cualquier arepa.',
      (STUDIO.format(what='a tall glass of iced amber papelon con limon drink with lime slices and ice cubes'),
       ALT.format(what='pitcher of papelon con limon with lemons and raw cane sugar block on a rustic table')),
      attrs={'tipo_bebida_callejera': 'Papelón con Limón', 'volumen_oz': '16 oz'},
      mods=[M('Hielo', [('Con Hielo Picado', 0), ('Sin Hielo (Pura)', 0)], required=True)],
      offer=5, stock=50),
    P('chicha-venezolana', 'Chicha Venezolana', CALLEJERAS, CAT, 3.00,
      'Chicha de arroz cremosita, con leche condensada y canela por encima. Agrégale tus toppings favoritos.',
      (STUDIO.format(what='a tall plastic cup of creamy Venezuelan rice chicha drink topped with condensed milk and '
                          'cinnamon'),
       ALT.format(what='street vendor style chicha cups with toppings, crushed cookies and condensed milk, sunny day')),
      attrs={'tipo_bebida_callejera': 'Chicha Venezolana', 'volumen_oz': '12 a 16 oz'},
      variants=[V({'size': 'Mediano (12 oz)', 'drink_type': 'Chicha Tradicional de Arroz'}, 30),
                V({'size': 'Grande (16 oz)', 'drink_type': 'Chicha Tradicional de Arroz'}, 25, 3.80),
                V({'size': 'Envase para Llevar (1 Litro)', 'drink_type': 'Chicha Tradicional de Arroz'}, 8, 7.00)],
      mods=[M('Base Incluida (Chicha / Cocada)', [('Con Leche Condensada y Canela', 0),
                                                  ('Solo Leche Condensada (Sin Canela)', 0)], required=True),
            M('Toppings y Extras Dulces', [('Extra Leche Condensada', 0.5), ('Sirope de Chocolate / Nutella', 0.8),
                                           ('Galleta Oreo Triturada', 0.8), ('Pirulín / Susy / Cocosette', 1)],
              max_sel=3)],
      tokens=TOK_A),
    P('jugo-natural-frutas', 'Jugo Natural de Frutas', JUGOS, CAT, 3.00,
      'Jugos naturales hechos al momento con fruta fresca del día: parchita, guanábana, fresa, lechosa o el clásico '
      'tres en uno. En agua o en leche.',
      (STUDIO.format(what='three tall glasses of fresh tropical fruit juices in yellow, white and red colors with fruits'),
       ALT.format(what='fresh passion fruit juice being poured from a blender into a glass, tropical fruits around')),
      attrs={'temperatura': 'Frío / Frappé'},
      variants=[V({'flavor': 'Parchita (Maracuyá)', 'size': 'Grande (12-16 oz)'}, 30),
                V({'flavor': 'Guanábana', 'size': 'Grande (12-16 oz)'}, 20, 3.50),
                V({'flavor': 'Fresa', 'size': 'Grande (12-16 oz)'}, 20),
                V({'flavor': 'Lechosa / Melón / Patilla', 'size': 'Grande (12-16 oz)'}, 25),
                V({'flavor': 'Tres en Uno (Naranja, Zanahoria y Remolacha)', 'size': 'Grande (12-16 oz)'}, 15, 3.50)],
      mods=[M('Preparación y Endulzante', [('En Agua (Tradicional)', 0), ('En Leche (Batido / Merengada)', 0.8),
                                           ('Poca Azúcar', 0), ('Sin Azúcar / Con Edulcorante', 0)], max_sel=2)]),

    # ------------------------------------------------------------------------------------------------------------------
    # Tortas, Postres, Donas y Dulcería
    # ------------------------------------------------------------------------------------------------------------------
    P('quesillo-criollo-porcion', 'Quesillo Criollo (Porción)', POSTRES, CAT, 3.50,
      'Quesillo casero de huevo y leche condensada, con su caramelo dorado y sus huequitos de siempre. '
      'Porción generosa para cerrar el almuerzo.',
      (STUDIO.format(what='a slice of Venezuelan quesillo caramel flan with golden caramel sauce dripping, on a small plate'),
       ALT.format(what='a whole caramel flan quesillo on a cake stand with one slice cut, homestyle kitchen')),
      unit='portion',
      attrs={'tipo_postre': 'Quesillo / Flan', 'porciones_personas': '1 persona'},
      offer=10, stock=20),
    P('torta-tres-leches', 'Torta Tres Leches', POSTRES, CAT, 4.00,
      'Bizcocho esponjoso bañado en tres leches y cubierto con merengue suave y canela. Por porción o torta completa '
      'para celebrar; te ponemos la vela de cumpleaños.',
      (STUDIO.format(what='a moist slice of tres leches cake with whipped meringue topping and cinnamon dust, milk pooling'),
       ALT.format(what='a whole tres leches cake decorated with meringue on a festive birthday table')),
      unit='portion',
      attrs={'tipo_postre': 'Porción de Torta / Marquesa', 'porciones_personas': '1 o 12-15 personas'},
      variants=[V({'presentation': 'Porción Individual', 'flavor': 'Tres Leches'}, 20),
                V({'presentation': 'Torta Completa (12-15 porciones)', 'flavor': 'Tres Leches'}, 3, 38.00)],
      mods=[M('Adicionales de Dulcería', [('Extra Arequipe / Leche Condensada', 0.8), ('Vela de Cumpleaños / Topper', 1.5)],
              max_sel=2)],
      tokens=TOK_B),
]
