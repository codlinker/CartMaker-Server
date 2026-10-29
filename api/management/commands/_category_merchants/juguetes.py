# -*- coding: utf-8 -*-
"""Catálogo demo de Juguetería Mundo Mágico (Juegos y Juguetes): 20 productos."""
from ._helpers import ALT, STUDIO, TOK_A, TOK_B, TOK_C, M, P, V, grid, sizes  # noqa: F401

CAT = 'Juegos y Juguetes'

PRODUCTS = [
    # ------------------------------------------------------------------ Muñecas
    P('barbie-fashionista', 'Barbie Fashionista Surtida', 'Muñecas, Barbies y Bebés', CAT, 18.90,
      'Muñeca Barbie Fashionista original de Mattel, articulada, con outfit de moda y zapatos removibles. '
      'Mide unos 30 cm y viene en caja sellada, ideal para regalo de cumpleaños.',
      (STUDIO.format(what='a fashion doll with long hair wearing a colorful trendy outfit, standing, full body view'),
       ALT.format(what='a little girl playing with fashion dolls and tiny accessories on a bedroom rug')),
      attrs={'marca': 'Mattel', 'edad_recomendada': '+3 años'},
      variants=sizes('character', ['Rubia', 'Morena', 'Con Accesorios'], stock=6),
      tokens=TOK_A),
    P('bebe-interactivo-tetero', 'Bebé Interactivo que Llora y Toma Tetero', 'Muñecas, Barbies y Bebés', CAT, 29.90,
      'Muñeca bebé de 35 cm que llora, ríe y "toma" tetero con sonidos reales. Incluye tetero mágico, chupón y '
      'pañal. Funciona con 3 pilas AA incluidas.',
      (STUDIO.format(what='a soft baby doll wearing pastel pajamas with a small feeding bottle and pacifier'),
       ALT.format(what='a child gently feeding a baby doll with a toy bottle on a sofa, warm home light')),
      attrs={'marca': 'Baby Alive (Hasbro)', 'edad_recomendada': '+3 años'},
      variants=[V({'character': 'Morena'}, 7), V({'character': 'Rubia'}, 5)],
      offer=15),
    P('casa-munecas-madera-3-pisos', 'Casa de Muñecas de Madera 3 Pisos con Muebles', 'Muñecas, Barbies y Bebés', CAT, 89.00,
      'Casa de muñecas de MDF de 3 niveles (90 x 60 x 30 cm) con escalera, balcón y 15 piezas de mobiliario. '
      'Compatible con muñecas de hasta 30 cm. Se entrega en caja para armar con instructivo.',
      (STUDIO.format(what='a three story wooden dollhouse painted in white and pink with tiny furniture inside'),
       ALT.format(what='close-up of a miniature living room inside a wooden dollhouse, tiny sofa and lamp')),
      unit='set', attrs={'marca': 'KidKraft', 'edad_recomendada': '+3 años'},
      tokens=TOK_C, stock=4),
    # ------------------------------------------------------------------ Peluches
    P('oso-peluche-teddy', 'Oso de Peluche Teddy', 'Peluches', CAT, 22.00,
      'Clásico oso Teddy de felpa suave hipoalergénica con lazo de satén. Relleno de fibra siliconada que no se '
      'apelmaza. El regalo perfecto para San Valentín, cumpleaños o graduaciones.',
      (STUDIO.format(what='a fluffy light brown teddy bear with a red satin bow sitting upright'),
       ALT.format(what='a giant teddy bear sitting on a bed next to pillows, cozy bedroom atmosphere')),
      attrs={'personaje': 'Oso Teddy', 'tamano_cm': '35 a 100 cm'},
      variants=[V({'size_or_char': 'Mediano (35 cm)'}, 12), V({'size_or_char': 'Grande (50 cm)'}, 8, 34.00),
                V({'size_or_char': 'Jumbo (80 cm)'}, 4, 59.00), V({'size_or_char': 'Gigante (1 Metro+)'}, 0, 89.00)],
      offer=10),
    P('peluche-stitch-30', 'Peluche Stitch 30 cm', 'Peluches', CAT, 16.50,
      'Peluche de Stitch con licencia Disney, de 30 cm, con orejas flexibles y bordados de alta calidad. '
      'Lavable a mano, apto para todas las edades.',
      (STUDIO.format(what='a cute blue alien plush toy with big ears and large dark eyes, sitting'),
       ALT.format(what='a blue alien plush toy hugged by a child on a couch, soft afternoon light')),
      attrs={'personaje': 'Stitch (Disney)', 'tamano_cm': '30 cm'},
      tokens=TOK_A, stock=15),
    P('peluche-pikachu-25', 'Peluche Pikachu Pokémon 25 cm', 'Peluches', CAT, 19.00,
      'Peluche oficial de Pikachu de 25 cm, felpa amarilla extra suave y mejillas bordadas. Un clásico para los '
      'fanáticos de Pokémon, grandes y chiquitos.',
      (STUDIO.format(what='a yellow electric mouse plush toy with red cheeks and a lightning shaped tail'),
       ALT.format(what='yellow electric mouse plush toy on a shelf with other collectible toys, playful room')),
      attrs={'personaje': 'Pikachu (Pokémon)', 'tamano_cm': '25 cm'},
      stock=10),
    # ------------------------------------------------------------------ Figuras de acción
    P('figura-marvel-titan-hero', 'Figura Marvel Titan Hero Series 30 cm', 'Figuras de Acción y Superhéroes', CAT, 14.90,
      'Figura de acción de 30 cm de la línea Titan Hero Series de Hasbro, con 5 puntos de articulación. '
      'Escoge a tu superhéroe favorito de Marvel. Nueva en caja sellada.',
      (STUDIO.format(what='a 30 cm superhero action figure in a red and blue suit in a dynamic pose'),
       ALT.format(what='several superhero action figures lined up on a kid desk, playful lighting')),
      attrs={'marca': 'Hasbro', 'franquicia': 'Marvel Avengers', 'condicion': 'Nuevo en caja sellada'},
      variants=sizes('character', ['Spider-Man', 'Iron Man', 'Capitán América'], stock=6),
      tokens=TOK_B),
    P('figura-dragon-ball-z', 'Figura Dragon Ball Z 18 cm', 'Figuras de Acción y Superhéroes', CAT, 24.00,
      'Figura coleccionable de Bandai de 18 cm, articulada, con manos intercambiables y efectos de energía. '
      'Perfecta para jugar o para la vitrina de coleccionista.',
      (STUDIO.format(what='an anime martial arts action figure with spiky golden hair and orange outfit, fighting pose'),
       ALT.format(what='anime action figures displayed in a glass collector cabinet with soft spotlight')),
      attrs={'marca': 'Bandai', 'franquicia': 'Dragon Ball', 'condicion': 'Nuevo en caja sellada'},
      variants=[V({'character': 'Goku'}, 8), V({'character': 'Vegeta'}, 5),
                V({'character': 'Edición Especial'}, 2, 32.00)]),
    P('paw-patrol-pack-6-figuras', 'Set de Figuras Paw Patrol x6', 'Figuras de Acción y Superhéroes', CAT, 21.00,
      'Pack con 6 figuras de 6 cm de la Patrulla Canina: Chase, Marshall, Skye, Rubble, Rocky y Zuma. '
      'Plástico resistente, ideal para niños desde 3 años.',
      (STUDIO.format(what='six small cartoon rescue puppy figures in colorful uniforms standing in a row'),
       ALT.format(what='small puppy toy figures on a play mat with toy vehicles, child hands reaching')),
      unit='pack', attrs={'marca': 'Spin Master', 'franquicia': 'Paw Patrol', 'condicion': 'Nuevo en caja sellada'},
      offer=20, stock=8),
    # ------------------------------------------------------------------ Bloques
    P('lego-classic-caja-mediana', 'LEGO Classic Caja Mediana de Ladrillos Creativos', 'Bloques, Legos y Armables', CAT, 34.90,
      'Caja LEGO Classic 10696 con 484 piezas en 35 colores, ventanas, ojos y ruedas para construir sin límites. '
      'Incluye ideas de construcción y caja plástica para guardar.',
      (STUDIO.format(what='a plastic storage box full of colorful interlocking toy bricks, some built models in front'),
       ALT.format(what='kid hands building a small colorful brick house on a wooden table, top view')),
      attrs={'marca': 'LEGO', 'cantidad_piezas': 484, 'edad_recomendada': '4 a 99 años'},
      tokens=TOK_B, stock=7),
    P('lego-city-estacion-policia', 'LEGO City Estación de Policía', 'Bloques, Legos y Armables', CAT, 79.00,
      'Set LEGO City 60316 de 668 piezas con estación de policía, patrulla, moto, camión de basura y 5 minifiguras. '
      'Horas de juego de rol y construcción.',
      (STUDIO.format(what='a built toy brick police station set with a police car, motorcycle and small minifigures'),
       ALT.format(what='close-up of toy brick minifigures and a police car in front of a brick building, playful scene')),
      unit='set', attrs={'marca': 'LEGO', 'cantidad_piezas': 668, 'edad_recomendada': '+6 años'},
      tokens=TOK_C, stock=4),
    P('bloques-magneticos', 'Bloques Magnéticos de Construcción', 'Bloques, Legos y Armables', CAT, 27.00,
      'Piezas magnéticas translúcidas de colores (cuadrados, triángulos y ruedas) para crear figuras 3D. '
      'Estimulan la creatividad y la noción espacial. Imanes encapsulados, seguros para niños.',
      (STUDIO.format(what='colorful translucent magnetic building tiles assembled into a small castle'),
       ALT.format(what='magnetic building tiles glowing in window sunlight while a child builds a tower')),
      unit='set', attrs={'marca': 'MagBlocks', 'cantidad_piezas': 64, 'edad_recomendada': '+3 años'},
      variants=[V({'model': 'Set Estándar'}, 9), V({'model': 'Edición Coleccionista'}, 4, 39.00)],
      offer=10),
    # ------------------------------------------------------------------ Estimulación
    P('mesa-actividades-bebe', 'Mesa de Actividades Musical para Bebé', 'Juguetes de Estimulación para Bebés', CAT, 32.00,
      'Mesa de aprendizaje con luces, más de 70 canciones y frases en español e inglés, piano, teléfono y '
      'engranajes. Las patas se quitan para jugar en el piso. Funciona con 3 pilas AA.',
      (STUDIO.format(what='a colorful baby activity table with buttons, a small piano, gears and a toy phone'),
       ALT.format(what='a baby standing and playing at a colorful activity table in a bright living room')),
      attrs={'marca': 'Fisher-Price', 'edad_recomendada': '6 a 12 meses'},
      stock=6),
    # ------------------------------------------------------------------ Juegos de mesa
    P('monopoly-clasico', 'Monopoly Clásico', 'Juegos de Mesa, Cartas y Dominó', CAT, 26.00,
      'El juego de bienes raíces más famoso del mundo, edición en español con tablero, fichas metálicas, '
      'billetes, casas y hoteles. Para 2 a 6 jugadores desde 8 años.',
      (STUDIO.format(what='a classic property trading board game with colorful paper money, dice and tiny houses'),
       ALT.format(what='a family playing a property trading board game on a dining table at night, warm light')),
      attrs={'marca': 'Hasbro', 'jugadores': '2 a 6'},
      variants=[V({'edition': 'Clásico'}, 10), V({'edition': 'De Viaje / Magnético'}, 6, 18.00)],
      tokens=TOK_A),
    P('domino-doble-seis', 'Dominó Doble Seis', 'Juegos de Mesa, Cartas y Dominó', CAT, 15.00,
      'Dominó de 28 fichas doble seis, el infaltable de toda reunión venezolana. Fichas gruesas con puntos '
      'en bajo relieve que no se borran. Escoge entre la versión clásica, acrílica profesional o con estuche de cuero.',
      (STUDIO.format(what='a set of ivory domino tiles arranged in a fan shape next to a wooden case'),
       ALT.format(what='domino tiles on a wooden table during a game, hands placing a tile, warm outdoor light')),
      unit='set', attrs={'marca': 'Cardinal', 'jugadores': '2 a 4'},
      variants=[V({'edition': 'Clásico'}, 18), V({'edition': 'Profesional Acrílico'}, 8, 24.00),
                V({'edition': 'Caja / Estuche'}, 5, 32.00)],
      tokens=TOK_B),
    P('uno-cartas-clasico', 'UNO Cartas Clásico', 'Juegos de Mesa, Cartas y Dominó', CAT, 6.50,
      'El clásico juego de cartas UNO de Mattel con 112 cartas, incluye cartas comodín personalizables. '
      'Para 2 a 10 jugadores desde 7 años. Ideal para llevar a la playa.',
      (STUDIO.format(what='a deck of colorful card game cards fanned out in red, yellow, green and blue'),
       ALT.format(what='friends playing a colorful card game on a picnic blanket at the beach')),
      attrs={'marca': 'Mattel', 'jugadores': '2 a 10'},
      stock=30),
    P('jenga-clasico', 'Jenga Clásico 54 Bloques', 'Juegos de Mesa, Cartas y Dominó', CAT, 14.00,
      'Torre de 54 bloques de madera maciza. Saca un bloque, ponlo arriba y no dejes que se caiga. '
      'Diversión para toda la familia desde 6 años.',
      (STUDIO.format(what='a tall tower of natural wooden stacking blocks with a few blocks pulled out'),
       ALT.format(what='a hand carefully pulling a wooden block from a wobbly tower, tense moment, shallow focus')),
      attrs={'marca': 'Hasbro', 'jugadores': '1 o más'},
      offer=15, stock=12),
    # ------------------------------------------------------------------ Exterior
    P('carro-rc-monster-truck-4x4', 'Carro a Control Remoto Monster Truck 4x4 Recargable', 'Juguetes de Exterior, Patinetas y Triciclos', CAT, 39.90,
      'Camioneta todoterreno a control remoto escala 1:16, tracción 4x4, suspensión independiente y hasta 20 km/h. '
      'Batería recargable por USB con 25 minutos de autonomía. Control de 2.4 GHz.',
      (STUDIO.format(what='a remote control monster truck with big rubber tires and a remote controller beside it'),
       ALT.format(what='a remote control monster truck jumping over dirt in a park, motion blur, sunny day')),
      attrs={'edad_peso': '+6 años'},
      variants=sizes('color', ['Rojo', 'Azul', 'Verde'], stock=5, sold_out=('Verde',)),
      tokens=TOK_B),
    P('scooter-3-ruedas-led', 'Scooter Monopatín 3 Ruedas con Luces LED', 'Juguetes de Exterior, Patinetas y Triciclos', CAT, 34.00,
      'Monopatín de 3 ruedas con luces LED que se encienden al rodar, manubrio ajustable en 4 alturas y freno '
      'trasero. Plegable y liviano, soporta hasta 50 kg.',
      (STUDIO.format(what='a kids three wheel kick scooter with glowing LED wheels and adjustable handlebar'),
       ALT.format(what='a child riding a three wheel kick scooter with glowing wheels on a sidewalk at sunset')),
      attrs={'edad_peso': '3 a 8 años, hasta 50 kg'},
      variants=grid('color', ['Azul', 'Rosa', 'Morado'], 'size', ['Talla Única'], stock=6),
      offer=10),
    # ------------------------------------------------------------------ Piscina
    P('piscina-inflable-intex', 'Piscina Inflable Intex', 'Juguetes de Piscina, Playa e Inflables', CAT, 22.00,
      'Piscina inflable de vinil resistente con 3 anillos y válvula de drenaje. Perfecta para refrescarse en casa '
      'o en el patio. Incluye parches de reparación.',
      (STUDIO.format(what='a blue round inflatable family swimming pool with three rings, empty'),
       ALT.format(what='kids splashing in an inflatable pool in a sunny backyard with tropical plants')),
      attrs={'marca': 'Intex', 'dimensiones_litros': '262 x 175 x 51 cm (familiar), hasta 777 litros'},
      variants=[V({'size': 'Pequeña'}, 10), V({'size': 'Mediana'}, 7, 32.00), V({'size': 'Familiar Grande'}, 5, 45.00)],
      tokens=TOK_A),
]
