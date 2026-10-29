# -*- coding: utf-8 -*-
"""Catálogo demo de Librería y Papelería Altamira (Papelería, Oficina y Libros): 20 productos."""
from ._helpers import ALT, STUDIO, TOK_A, TOK_B, TOK_C, M, P, V, grid, sizes  # noqa: F401

CAT = 'Papelería, Oficina y Libros'

PRODUCTS = [
    # ------------------------------------------------------------------ Cuadernos
    P('cuaderno-cosido-100-hojas', 'Cuaderno Cosido Escolar 100 Hojas', 'Cuadernos, Libretas y Blocks', CAT, 1.80,
      'Cuaderno escolar cosido de 100 hojas (200 páginas), papel bond de 56 g que no traspasa y tapa plastificada. '
      'El de toda la vida para el colegio, en línea o cuadriculado.',
      (STUDIO.format(what='a stack of school notebooks with glossy colorful covers, one open showing ruled pages'),
       ALT.format(what='an open lined school notebook on a desk with pencils and an eraser, morning light')),
      attrs={'marca': 'Caribe', 'encuadernacion': 'Cosido Escolar'},
      variants=grid('ruling', ['Una Línea', 'Doble Línea', 'Cuadriculado Grande'],
                    'design_or_pack', ['Niño / Deportivo', 'Niña / Fantasía'], stock=40,
                    sold_out=[('Doble Línea', 'Niña / Fantasía')]),
      tokens=TOK_A),
    P('cuaderno-espiral-5-materias', 'Cuaderno Espiral 5 Materias 200 Hojas', 'Cuadernos, Libretas y Blocks', CAT, 6.50,
      'Cuaderno universitario con doble anillo metálico, 5 separadores de colores con bolsillo y 200 hojas '
      'rayadas microperforadas. Tapa dura de polipropileno resistente a la humedad.',
      (STUDIO.format(what='a thick spiral bound notebook with a dark blue plastic cover and colored tab dividers'),
       ALT.format(what='university student writing in a spiral notebook at a cafe table with a laptop')),
      attrs={'marca': 'Norma', 'encuadernacion': 'Espiral / Doble Anillo (Ring)'},
      offer=10, stock=35),
    P('agenda-ejecutiva-2027', 'Agenda Ejecutiva 2027 Tapa Dura', 'Cuadernos, Libretas y Blocks', CAT, 12.00,
      'Agenda diaria 2027 de 17 x 24 cm con tapa dura en semicuero, cinta separadora, planificador mensual '
      'y directorio. Ideal para organizar tus reuniones y pendientes del año.',
      (STUDIO.format(what='a closed hardcover executive planner in dark brown faux leather with a ribbon bookmark'),
       ALT.format(what='an open daily planner on an office desk with a fountain pen and a cup of coffee')),
      attrs={'marca': 'Norma', 'encuadernacion': 'Tapa Dura / Agenda'},
      tokens=TOK_B, stock=15),
    # ------------------------------------------------------------------ Lápices y colores
    P('colores-faber-castell', 'Colores Faber-Castell Ecolápices', 'Lápices, Colores, Bolígrafos y Marcadores', CAT, 4.50,
      'Lápices de colores Faber-Castell de mina resistente y colores brillantes, fabricados con madera reforestada. '
      'Los preferidos de las listas escolares.',
      (STUDIO.format(what='a box of colored pencils open with pencils arranged in a rainbow gradient'),
       ALT.format(what='a child coloring a drawing with colored pencils scattered on a table, top view')),
      attrs={'marca': 'Faber-Castell'},
      variants=[V({'presentation': 'Caja x12 Colores', 'ink_color': 'Surtido'}, 45),
                V({'presentation': 'Caja x24 Colores', 'ink_color': 'Surtido'}, 25, 8.50),
                V({'presentation': 'Caja x36 Colores', 'ink_color': 'Surtido'}, 10, 12.50)],
      tokens=TOK_A),
    P('boligrafos-bic-cristal-x12', 'Bolígrafos BIC Cristal Punta Media Caja x12', 'Lápices, Colores, Bolígrafos y Marcadores', CAT, 4.80,
      'Caja de 12 bolígrafos BIC Cristal de punta media 1.0 mm, tinta de secado rápido y hasta 2 km de escritura. '
      'Disponible en negro, azul o rojo.',
      (STUDIO.format(what='a row of clear hexagonal ballpoint pens with colored caps next to their cardboard box'),
       ALT.format(what='a hand writing with a clear ballpoint pen on lined paper, macro shot of the tip')),
      unit='box', attrs={'marca': 'BIC'},
      variants=grid('presentation', ['Caja x12 Unidades (Docena)'], 'ink_color', ['Negro', 'Azul', 'Rojo'], stock=20)),
    P('resaltadores-stabilo-x4', 'Resaltadores Stabilo Boss Original Pack x4', 'Lápices, Colores, Bolígrafos y Marcadores', CAT, 7.90,
      'Pack de 4 resaltadores Stabilo Boss (amarillo, verde, rosado y naranja) con tinta fluorescente a base de agua '
      'y punta biselada de 2 y 5 mm. Hasta 4 horas destapados sin secarse.',
      (STUDIO.format(what='four fluorescent highlighter markers in yellow, green, pink and orange laid side by side'),
       ALT.format(what='highlighting text in a printed textbook with a fluorescent yellow marker, study scene')),
      unit='pack', attrs={'marca': 'Stabilo'},
      offer=15, stock=20),
    # ------------------------------------------------------------------ Resmas y cartulinas
    P('resma-papel-bond-75g', 'Resma de Papel Bond 75 g', 'Resmas de Hojas, Cartulinas y Papelería', CAT, 6.90,
      'Resma de 500 hojas de papel bond blanco de 75 g/m², ideal para impresoras láser e inyección de tinta. '
      'Precio especial por bulto de 10 resmas para oficinas.',
      (STUDIO.format(what='a sealed ream of white printer paper next to a few loose white sheets'),
       ALT.format(what='printer paper sheets loaded into an office laser printer tray, office background')),
      attrs={'marca': 'Chamex', 'gramaje_base': '75 g/m²'},
      variants=[V({'size': 'Tamaño Carta (500 hojas)', 'color': 'Blanco'}, 60),
                V({'size': 'Tamaño Oficio (500 hojas)', 'color': 'Blanco'}, 30, 8.40),
                V({'size': 'Bulto (10 Resmas)', 'color': 'Blanco'}, 8, 64.00)],
      tokens=TOK_B),
    P('cartulina-escolar-pliego', 'Cartulina Escolar por Pliego', 'Resmas de Hojas, Cartulinas y Papelería', CAT, 0.60,
      'Pliego de cartulina escolar de 150 g/m² (50 x 70 cm) en colores vivos, ideal para carteleras, maquetas '
      'y trabajos del colegio.',
      (STUDIO.format(what='large sheets of colored cardstock paper fanned out in white, yellow, blue, green, red and black'),
       ALT.format(what='a school bulletin board project made with colorful cardstock cutouts on a table')),
      attrs={'marca': 'Bristol', 'gramaje_base': '150 g/m²'},
      variants=grid('size', ['Pliego'], 'color', ['Blanco', 'Amarillo', 'Azul', 'Verde', 'Rojo', 'Negro'], stock=50)),
    # ------------------------------------------------------------------ Morrales
    P('morral-combo-3-en-1', 'Morral Escolar Combo 3 en 1', 'Morrales Escolares y Cartucheras', CAT, 25.00,
      'Combo escolar con morral acolchado de 16", lonchera térmica y cartuchera a juego. Tela poliéster '
      'impermeable, cierres reforzados y espalda ergonómica.',
      (STUDIO.format(what='a matching set of a kids school backpack, insulated lunch bag and pencil case'),
       ALT.format(what='a child wearing a colorful school backpack walking to school on a tree lined street')),
      unit='set', attrs={'marca': 'Mundo Escolar', 'piezas': 'Combo 3 en 1 (Morral + Lonchera + Cartuchera)'},
      variants=sizes('design', ['Azul', 'Rosa', 'Morado'], stock=6),
      offer=20),
    P('morral-totto-laptop-15', 'Morral Totto para Laptop 15.6"', 'Morrales Escolares y Cartucheras', CAT, 49.00,
      'Morral Totto con compartimiento acolchado para laptop de hasta 15.6", bolsillo antirrobo trasero, '
      'puerto USB externo y tela repelente al agua. Garantía de 1 año por defectos de fábrica.',
      (STUDIO.format(what='a sleek black laptop backpack with padded straps and a side water bottle pocket'),
       ALT.format(what='a young professional carrying a black laptop backpack on a city sidewalk')),
      attrs={'marca': 'Totto', 'piezas': 'Solo Morral'},
      tokens=TOK_C, stock=9),
    # ------------------------------------------------------------------ Manualidades
    P('foami-escarchado-carta-x10', 'Foami Escarchado Tamaño Carta Pack x10', 'Material de Manualidades, Foami y Pinturas', CAT, 4.50,
      'Pack de 10 láminas de foami escarchado de 2 mm tamaño carta, con adhesivo en el reverso. Perfecto para '
      'decoraciones, tarjetas y manualidades escolares.',
      (STUDIO.format(what='a fan of glitter foam sheets in gold, silver and assorted bright colors'),
       ALT.format(what='craft table with glitter foam cutouts, scissors and glue for a school project')),
      unit='pack', attrs={'marca': 'Foamy'},
      variants=sizes('color_or_size', ['Surtido', 'Dorado', 'Plateado'], stock=15),
      offer=10),
    P('set-pinturas-acrilicas-12', 'Set de Pinturas Acrílicas 12 Colores', 'Material de Manualidades, Foami y Pinturas', CAT, 9.90,
      'Set de 12 tubos de pintura acrílica de 22 ml, secado rápido y acabado satinado. Sirve sobre lienzo, '
      'madera, cartón y foami. Incluye 2 pinceles.',
      (STUDIO.format(what='a set of twelve acrylic paint tubes in a row with two small brushes'),
       ALT.format(what='artist painting a colorful canvas with acrylic paints, palette and brushes on a table')),
      unit='set', attrs={'marca': 'Pelikan'},
      tokens=TOK_A, stock=14),
    # ------------------------------------------------------------------ Carpetas
    P('carpetas-manila-x25', 'Carpetas Manila Paquete x25', 'Carpetas, Archivadores y Sobres', CAT, 4.50,
      'Paquete de 25 carpetas manila de cartulina color crema con pestaña, ideales para archivar documentos '
      'en la oficina o entregar trabajos.',
      (STUDIO.format(what='a stack of beige manila file folders with tabs, slightly fanned'),
       ALT.format(what='manila folders with documents inside an office filing drawer')),
      unit='pack', attrs={'marca': 'Pacific Paper'},
      variants=[V({'size': 'Tamaño Carta', 'pack': 'Paquete x25'}, 30),
                V({'size': 'Tamaño Oficio', 'pack': 'Paquete x25'}, 20, 5.50)]),
    P('archivador-palanca-lomo-ancho', 'Archivador de Palanca Lomo Ancho', 'Carpetas, Archivadores y Sobres', CAT, 4.80,
      'Archivador tamaño oficio con mecanismo de palanca metálico, lomo de 8 cm con etiqueta y anillo para sacarlo '
      'del estante. Cartón forrado de alta duración.',
      (STUDIO.format(what='a black lever arch file binder with a wide spine and metal ring mechanism open'),
       ALT.format(what='a row of lever arch binders on an office shelf, organized workspace')),
      attrs={'marca': 'Leitz'},
      tokens=TOK_B, stock=25),
    # ------------------------------------------------------------------ Calculadoras y oficina
    P('calculadora-casio-fx-82la-x', 'Calculadora Científica Casio fx-82LA X', 'Calculadoras, Grapadoras y Tijeras', CAT, 22.00,
      'Calculadora científica con 274 funciones, pantalla natural que muestra fracciones y raíces como en el '
      'libro y tapa protectora. Permitida en exámenes de bachillerato y universidad.',
      (STUDIO.format(what='a gray scientific calculator with a natural display and protective slide cover'),
       ALT.format(what='student using a scientific calculator while solving math exercises in a notebook')),
      attrs={'marca': 'Casio'},
      tokens=TOK_C, stock=12),
    P('engrapadora-metalica', 'Engrapadora de Escritorio Metálica', 'Calculadoras, Grapadoras y Tijeras', CAT, 9.50,
      'Engrapadora de metal con base antideslizante para grapas 26/6. La versión de oficina grande engrapa hasta '
      '100 hojas de una sola vez. Incluye 1.000 grapas.',
      (STUDIO.format(what='a sturdy black metal desktop stapler with a box of staples beside it'),
       ALT.format(what='a hand stapling a thick stack of documents on an office desk')),
      attrs={'marca': 'Swingline'},
      variants=[V({'model': 'Estándar'}, 18), V({'model': 'Oficina Grande'}, 5, 18.00)],
      offer=15),
    # ------------------------------------------------------------------ Sillas
    P('silla-oficina-ergonomica-malla', 'Silla de Oficina Ergonómica en Malla', 'Sillas de Oficina y Escritorios', CAT, 119.00,
      'Silla ejecutiva con respaldo de malla transpirable, soporte lumbar ajustable, apoyabrazos regulables y '
      'pistón a gas clase 3. Ideal para teletrabajo y largas jornadas.',
      (STUDIO.format(what='an ergonomic office chair with mesh backrest, lumbar support and padded armrests'),
       ALT.format(what='an ergonomic mesh office chair at a modern home office desk with a monitor and plant')),
      attrs={'material': 'Malla transpirable, asiento de espuma y base de nailon', 'dimensiones': '62 x 60 x 110-120 cm',
             'garantia': '6 meses'},
      variants=sizes('color_or_size', ['Negro', 'Gris'], stock=3),
      offer=10),
    # ------------------------------------------------------------------ Libros
    P('dona-barbara-romulo-gallegos', 'Doña Bárbara - Rómulo Gallegos', 'Libros Escolares, Novelas y Literatura', CAT, 12.00,
      'La gran novela venezolana de Rómulo Gallegos sobre la lucha entre civilización y barbarie en el llano. '
      'Lectura obligatoria de bachillerato, edición completa con prólogo y notas.',
      (STUDIO.format(what='a classic novel book with an illustrated cover of the Venezuelan plains at sunset, no readable text'),
       ALT.format(what='an open novel resting on a hammock with a cup of coffee, warm afternoon light')),
      attrs={'autor_editorial': 'Rómulo Gallegos / Monte Ávila Editores', 'genero_categoria': 'Novela / Literatura / Ficción',
             'idioma': 'Español', 'condicion': 'Nuevo'},
      variants=[V({'edition_or_grade': 'Tapa Blanda'}, 15), V({'edition_or_grade': 'Tapa Dura'}, 4, 20.00)],
      tokens=TOK_A),
    P('cien-anos-de-soledad', 'Cien Años de Soledad - Gabriel García Márquez', 'Libros Escolares, Novelas y Literatura', CAT, 18.50,
      'La obra maestra de Gabriel García Márquez y del realismo mágico, la historia de los Buendía en Macondo. '
      'Edición de bolsillo de Penguin Random House.',
      (STUDIO.format(what='a paperback novel with a colorful magical realism illustrated cover, no readable text'),
       ALT.format(what='a person reading a paperback novel in a cozy armchair next to a window')),
      attrs={'autor_editorial': 'Gabriel García Márquez / Penguin Random House',
             'genero_categoria': 'Novela / Literatura / Ficción', 'idioma': 'Español', 'condicion': 'Nuevo'},
      tokens=TOK_B, stock=10),
    P('libro-nacho-lee', 'Libro Nacho Lee - Método de Lectura Inicial', 'Libros Escolares, Novelas y Literatura', CAT, 6.00,
      'El clásico silabario con el que generaciones de venezolanos aprendieron a leer. Ilustraciones a color y '
      'método fonético paso a paso para preescolar y 1er grado.',
      (STUDIO.format(what='a children early reading primer book with a colorful illustrated cover of a smiling boy, no readable text'),
       ALT.format(what='a parent and a small child reading a colorful reading primer together at a table')),
      attrs={'autor_editorial': 'Editorial Susaeta', 'genero_categoria': 'Infantil / Cuentos / Colorear',
             'idioma': 'Español', 'condicion': 'Nuevo'},
      stock=20),
]
