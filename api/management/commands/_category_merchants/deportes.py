# -*- coding: utf-8 -*-
"""Catálogo demo de Zona Fit Altamira (Deportes y Fitness): 20 productos."""
from ._helpers import ALT, STUDIO, TOK_A, TOK_B, TOK_C, M, P, V, grid, sizes  # noqa: F401

CAT = 'Deportes y Fitness'

GYM = 'Pesas, Mancuernas y Máquinas de Gym'
BEISBOL = 'Béisbol y Sóftbol (Guantes, Bates y Pelotas)'
FUTBOL = 'Fútbol y Futsal (Balones, Tacos y Canilleras)'
BASKET = 'Básquetbol'
PADEL = 'Pádel y Tenis'
BICI = 'Bicicletas y Ciclismo'
ROPA = 'Ropa Deportiva, Monos y Licras'
ZAPATOS = 'Zapatos Deportivos y Gomas'
TERMOS = 'Cavas, Coolers y Termos'
SUPLE = 'Proteínas, Creatinas y Suplementos Gym'

PRODUCTS = [
    # ------------------------------------------------------------------ Gym en casa
    P('mancuernas-hexagonales-caucho-par', 'Par de Mancuernas Hexagonales Engomadas', GYM, CAT, 28.00,
      'Par de mancuernas hexagonales recubiertas en caucho, con mango cromado moleteado para un agarre firme. '
      'La forma hexagonal evita que rueden y protege el piso. Precio por par.',
      (STUDIO.format(what='a pair of black rubber coated hexagonal dumbbells with knurled chrome handles'),
       ALT.format(what='person doing bicep curls with black hex dumbbells in a home gym, natural window light')),
      unit='pair',
      attrs={'marca': 'Body Solid', 'material_recubrimiento': 'Caucho / Engomado (Hexagonal)',
             'venta_formato': 'Por Par (2 unidades)'},
      variants=[V({'weight': '10 lb'}, 10), V({'weight': '15 lb'}, 8, 40.00), V({'weight': '20 lb'}, 6, 52.00),
                V({'weight': '25 lb'}, 4, 64.00), V({'weight': '30 lb'}, 0, 76.00)],
      tokens=TOK_A),
    P('kettlebell-hierro-fundido-20lb', 'Kettlebell de Hierro Fundido 20 lb', GYM, CAT, 34.00,
      'Pesa rusa de 20 lb fundida en una sola pieza, con base plana y asa amplia para swings, sentadillas goblet y '
      'entrenamiento funcional. Acabado en pintura electrostática anticorrosión.',
      (STUDIO.format(what='a black cast iron kettlebell with a wide handle and flat base, side view'),
       ALT.format(what='athlete performing a kettlebell swing in a functional training studio, motion blur, dramatic light')),
      attrs={'marca': 'Body Solid', 'material_recubrimiento': 'Hierro Fundido', 'venta_formato': 'Por Unidad'},
      offer=10, stock=9),
    P('set-bandas-resistencia-5-niveles', 'Set de 5 Bandas de Resistencia con Accesorios', GYM, CAT, 18.00,
      'Kit de 5 bandas de látex con distintos niveles de resistencia (de 10 a 50 lb), 2 mangos acolchados, tobilleras, '
      'anclaje para puerta y bolso de transporte. Entrena todo el cuerpo en casa o en el parque.',
      (STUDIO.format(what='a set of five colorful latex resistance tubes with foam handles, ankle straps and a door anchor'),
       ALT.format(what='woman training with resistance bands anchored to a door in a bright apartment living room')),
      unit='set',
      attrs={'marca': 'Zona Fit', 'material_recubrimiento': 'Látex / Tela (Bandas)', 'venta_formato': 'Set / Kit Completo'},
      stock=40),
    P('mat-yoga-tpe-6mm', 'Mat de Yoga TPE 6 mm Antideslizante', GYM, CAT, 24.00,
      'Colchoneta de yoga de TPE de 6 mm, doble capa antideslizante, liviana y libre de olores. Medidas 183 x 61 cm; '
      'incluye correa para llevarla al gimnasio o al Parque del Este.',
      (STUDIO.format(what='a rolled purple TPE yoga mat with a carrying strap, partially unrolled to show texture'),
       ALT.format(what='woman stretching on a yoga mat on a wooden deck surrounded by tropical plants, morning sunlight')),
      attrs={'marca': 'Zona Fit', 'material_recubrimiento': 'PVC / Goma EVA (Mat)', 'venta_formato': 'Por Unidad'},
      offer=15, stock=25),

    # ------------------------------------------------------------------ Béisbol
    P('guante-beisbol-rawlings-select-pro', 'Guante de Béisbol Rawlings Select Pro Lite', BEISBOL, CAT, 89.00,
      'Guante de cuero premium con red tipo I, palma acolchada y cierre ajustable. Viene semi-domado de fábrica, listo '
      'para el juego de caimanera o la liga del fin de semana.',
      (STUDIO.format(what='a tan brown leather baseball glove with an I-web pocket, open palm view'),
       ALT.format(what='baseball glove catching a ball on a sunny field, close-up with dirt and grass, shallow depth of field')),
      attrs={'marca': 'Rawlings', 'categoria_edad': 'Adulto / Profesional', 'condicion': 'Nuevo'},
      variants=[V({'size_inches': '11.75"', 'throwing_hand': 'Lanza Derecho (Guante en mano izquierda - RHT)'}, 5),
                V({'size_inches': '12"', 'throwing_hand': 'Lanza Derecho (Guante en mano izquierda - RHT)'}, 4),
                V({'size_inches': '12"', 'throwing_hand': 'Lanza Zurdo (Guante en mano derecha - LHT)'}, 2),
                V({'size_inches': '12.75"', 'throwing_hand': 'Lanza Derecho (Guante en mano izquierda - RHT)'}, 3, 95.00)],
      tokens=TOK_B),
    P('bate-aluminio-easton-32-29', 'Bate de Aluminio Easton 32" / 29 oz', BEISBOL, CAT, 119.00,
      'Bate de aleación de aluminio de una sola pieza, balance ligero para mayor velocidad de swing y mango con grip '
      'acolchado antivibración. Medida 32" / 29 oz, ideal para juveniles y adultos.',
      (STUDIO.format(what='a sleek silver and black aluminum baseball bat lying diagonally, full length view'),
       ALT.format(what='batter swinging an aluminum bat at home plate during a sunset game, motion freeze')),
      attrs={'marca': 'Easton', 'categoria_edad': 'Adulto / Profesional', 'condicion': 'Nuevo'},
      tokens=TOK_C, stock=6),
    P('caja-12-pelotas-beisbol-entrenamiento', 'Caja de 12 Pelotas de Béisbol de Entrenamiento', BEISBOL, CAT, 54.00,
      'Docena de pelotas de béisbol con centro de corcho y goma, forro de cuero y costura roja en relieve. '
      'Perfectas para prácticas de bateo, fildeo y escuelitas de béisbol menor.',
      (STUDIO.format(what='an open box of twelve white leather baseballs with red stitching'),
       ALT.format(what='bucket of baseballs next to a glove on the dugout bench, sunny baseball field in background')),
      unit='box',
      attrs={'marca': 'Rawlings', 'categoria_edad': 'Entrenamiento', 'condicion': 'Nuevo'},
      offer=10, stock=15),

    # ------------------------------------------------------------------ Fútbol
    P('balon-futbol-adidas-league', 'Balón de Fútbol adidas League', FUTBOL, CAT, 35.00,
      'Balón termosellado con cámara de butilo que mantiene la presión por más tiempo y superficie texturizada para un '
      'mejor control. Apto para grama natural, sintética y canchas de tierra.',
      (STUDIO.format(what='a white soccer ball with colorful geometric panels, thermally bonded, front view'),
       ALT.format(what='soccer ball on artificial turf near the goal line, stadium lights in the background at dusk')),
      attrs={'marca': 'adidas', 'superficie': 'Todo Uso / Accesorios'},
      variants=[V({'size': 'Balón #5 (Oficial)'}, 14), V({'size': 'Balón #4 (Futsal / Juvenil)'}, 8, 32.00)],
      tokens=TOK_A),
    P('tacos-futbol-nike-phantom-fg', 'Tacos de Fútbol Nike Phantom Club FG', FUTBOL, CAT, 79.00,
      'Tacos con capellada sintética texturizada para un toque preciso y suela de tapones cónicos para grama natural. '
      'Plantilla acolchada y ajuste cómodo desde el primer uso.',
      (STUDIO.format(what='a pair of black and neon soccer cleats with conical studs, side profile view'),
       ALT.format(what='soccer player striking the ball with cleats on natural grass, close-up, flying grass bits')),
      unit='pair',
      attrs={'marca': 'Nike', 'superficie': 'Fútbol Campo (Grama Natural FG)'},
      variants=sizes('size', ['39', '40', '41', '42', '43', '44'], stock=3, sold_out=('44',)),
      offer=20),

    # ------------------------------------------------------------------ Básquet
    P('balon-basket-spalding-tf-1000', 'Balón de Básquet Spalding TF-1000 Legacy', BASKET, CAT, 59.00,
      'Balón oficial talla 7 de cuero compuesto con canales profundos y excelente agarre. Diseñado para canchas techadas, '
      'el favorito de las ligas locales.',
      (STUDIO.format(what='an orange composite leather basketball with deep black channels, front view'),
       ALT.format(what='basketball going through a net on an indoor court, dramatic overhead lighting')),
      attrs={'marca': 'Spalding', 'material': 'Cuero Compuesto (Indoor/Outdoor)'},
      tokens=TOK_B, stock=10),
    P('aro-basket-reglamentario-malla', 'Aro de Básquet Reglamentario con Malla', BASKET, CAT, 45.00,
      'Aro de acero macizo de 45 cm de diámetro con resorte retráctil y malla de nylon trenzado para exteriores. '
      'Incluye tornillería para fijarlo a tablero de madera o acrílico.',
      (STUDIO.format(what='an orange steel basketball rim with a white nylon net and mounting bracket'),
       ALT.format(what='outdoor basketball hoop on a neighborhood court at golden hour, ball about to go in')),
      attrs={'marca': 'Spalding', 'material': 'Acero / Nylon (Aros y Mallas)'},
      offer=12, stock=6),

    # ------------------------------------------------------------------ Pádel
    P('pala-padel-bullpadel', 'Pala de Pádel Bullpadel Vertex', PADEL, CAT, 149.00,
      'Pala de pádel con caras de fibra de carbono, núcleo de goma EVA de densidad media y marco tubular reforzado. '
      'Elige tu forma según tu juego: control, polivalente o potencia. Incluye funda.',
      (STUDIO.format(what='a modern carbon fiber padel racket with a perforated face and a protective cover beside it'),
       ALT.format(what='padel player hitting a volley on a glass-walled court, motion and dramatic light')),
      attrs={'marca': 'Bullpadel', 'disciplina': 'Pádel', 'material_nucleo': 'Goma EVA y caras de fibra de carbono'},
      variants=[V({'variant': 'Control (Redonda)'}, 4), V({'variant': 'Polivalente (Lágrima)'}, 5),
                V({'variant': 'Potencia (Diamante)'}, 3, 169.00)],
      tokens=TOK_C),
    P('tubo-3-pelotas-padel-head', 'Tubo de 3 Pelotas de Pádel Head Pro', PADEL, CAT, 8.50,
      'Tubo presurizado con 3 pelotas de pádel de felpa premium y alta durabilidad. Rebote constante partido tras partido; '
      'aprobadas para torneos.',
      (STUDIO.format(what='a clear pressurized tube with three yellow padel balls inside, one ball beside it'),
       ALT.format(what='padel balls resting near the net on a blue artificial grass padel court')),
      unit='pack',
      attrs={'marca': 'Head', 'disciplina': 'Pádel', 'material_nucleo': 'Caucho presurizado con felpa'},
      tokens=TOK_A, stock=60),

    # ------------------------------------------------------------------ Ciclismo
    P('bicicleta-montana-gw-rin-29', 'Bicicleta de Montaña GW Hyena Rin 29', BICI, CAT, 329.00,
      'Bicicleta MTB con cuadro de aluminio, 21 velocidades Shimano Tourney, frenos de disco mecánicos y suspensión '
      'delantera. Ideal para subir a El Ávila o rodar por la Cota Mil los domingos. Se entrega armada y ajustada.',
      (STUDIO.format(what='an aluminum hardtail mountain bike with 29 inch wheels, disc brakes and front suspension, side view'),
       ALT.format(what='mountain biker riding uphill on a forest trail with green mountains in the background, morning light')),
      attrs={'marca': 'GW', 'velocidades_componentes': '21 velocidades Shimano Tourney, frenos de disco mecánicos',
             'condicion': 'Nueva'},
      variants=grid('wheel_or_frame', ['Rin 27.5', 'Rin 29'], 'color', ['Negro', 'Rojo'], stock=3,
                    sold_out=[('Rin 27.5', 'Rojo')]),
      tokens=TOK_C),

    # ------------------------------------------------------------------ Ropa y calzado
    P('licra-deportiva-dama-tiro-alto', 'Licra Deportiva Dama Tiro Alto', ROPA, CAT, 22.00,
      'Licra larga de tiro alto en suplex de compresión con tecnología de secado rápido, pretina ancha que estiliza y '
      'bolsillo lateral para el teléfono. No transparenta al hacer sentadillas.',
      (STUDIO.format(what='high-waisted women athletic leggings in black, flat lay with side pocket visible'),
       ALT.format(what='woman in high-waisted leggings doing lunges in a modern gym, natural light')),
      attrs={'marca': 'Zona Fit', 'genero': 'Dama', 'tela': 'Suplex de compresión'},
      variants=grid('size', ['S', 'M', 'L'], 'color', ['Negro', 'Azul Marino', 'Vinotinto'], stock=5,
                    sold_out=[('L', 'Vinotinto')]),
      offer=15),
    P('franela-dry-fit-caballero-under-armour', 'Franela Dry Fit Caballero Under Armour Tech', ROPA, CAT, 25.00,
      'Franela de entrenamiento en poliéster ultraliviano que absorbe el sudor y se seca rápido, con costuras planas '
      'antirroce. Perfecta para el gym, el trote o el pádel.',
      (STUDIO.format(what='a men athletic short sleeve dry-fit t-shirt, folded neatly, front view'),
       ALT.format(what='man running in a dry-fit t-shirt on an urban park path at sunrise')),
      attrs={'marca': 'Under Armour', 'genero': 'Caballero', 'tela': 'Poliéster Dry Fit'},
      variants=grid('size', ['M', 'L', 'XL'], 'color', ['Negro', 'Gris', 'Azul Rey'], stock=6),
      tokens=TOK_A),
    P('zapatos-running-nike-revolution-7', 'Zapatos Running Nike Revolution 7', ZAPATOS, CAT, 89.00,
      'Zapatos para correr con espuma suave en la entresuela, malla transpirable y suela de goma con buen agarre. '
      'Livianos y cómodos para trotar o para el día a día.',
      (STUDIO.format(what='a lightweight running shoe with breathable mesh upper and foam midsole, side profile'),
       ALT.format(what='runner jogging on a city sidewalk at sunrise, close-up of running shoes in motion')),
      unit='pair',
      attrs={'marca': 'Nike', 'disciplina': 'Running / Maratón', 'genero': 'Caballero'},
      variants=grid('shoe_size', ['40', '41', '42', '43'], 'color', ['Negro', 'Blanco'], stock=4,
                    sold_out=[('43', 'Blanco')]),
      tokens=TOK_B),

    # ------------------------------------------------------------------ Hidratación
    P('termo-stanley-quencher-40oz', 'Termo Stanley Quencher 40 oz', TERMOS, CAT, 45.00,
      'Vaso térmico de acero inoxidable con doble pared al vacío, asa ergonómica, tapa giratoria y pitillo. Mantiene el '
      'agua fría hasta 11 horas y con hielo hasta 2 días. Cabe en el portavasos del carro.',
      (STUDIO.format(what='a 40 oz stainless steel insulated tumbler with handle, lid and straw, side view'),
       ALT.format(what='insulated tumbler with straw on a gym bench next to a towel and dumbbells')),
      attrs={'marca': 'Stanley', 'material_retencion': 'Acero inoxidable doble pared al vacío; frío hasta 11 h'},
      variants=grid('capacity', ['40 oz (1.18L)'], 'color', ['Negro', 'Rosado', 'Azul Claro', 'Beige / Crema'], stock=6),
      tokens=TOK_B),

    # ------------------------------------------------------------------ Suplementos
    P('proteina-whey-gold-standard-5lb', 'Proteína Whey Gold Standard Optimum Nutrition 5 lb', SUPLE, CAT, 89.00,
      'Proteína de suero con 24 g por servicio, aislado como fuente principal y baja en azúcar. Se mezcla fácil con agua '
      'o leche. Producto original importado, con fecha de vencimiento vigente.',
      (STUDIO.format(what='a large 5 lb tub of whey protein powder next to a scoop with powder, plain label'),
       ALT.format(what='protein shake being poured from a shaker into a glass on a gym counter, dumbbells behind')),
      attrs={'marca': 'Optimum Nutrition', 'tipo_suplemento': 'Proteína (Whey Isolate / Concentrate)',
             'servicios_por_envase': '74 servicios'},
      variants=grid('flavor', ['Chocolate', 'Vainilla', 'Cookies & Cream'], 'size', ['5 lb'], stock=5),
      tokens=TOK_A),
    P('creatina-monohidratada-nutrex-300g', 'Creatina Monohidratada Nutrex 300 g', SUPLE, CAT, 35.00,
      'Creatina monohidratada micronizada sin sabor, 5 g por servicio. Mejora la fuerza y la recuperación; se disuelve '
      'en agua, jugo o en tu batido de proteína.',
      (STUDIO.format(what='a white tub of micronized creatine monohydrate powder with an open lid and a scoop'),
       ALT.format(what='scoop of white creatine powder being added to a shaker bottle, close-up, gym background')),
      attrs={'marca': 'Nutrex', 'tipo_suplemento': 'Creatina Monohidratada', 'servicios_por_envase': '60 servicios'},
      offer=10, stock=30),
]
