# -*- coding: utf-8 -*-
"""Catálogo demo de Patitas Felices Pet Shop (Mascotas): 20 productos."""
from ._helpers import ALT, STUDIO, TOK_A, TOK_B, TOK_C, M, P, V, grid, sizes  # noqa: F401

CAT = 'Mascotas'

PERROS = 'Perrarina y Comida para Perros'
GATOS = 'Gatarina y Comida para Gatos'
SNACKS = 'Snacks, Galletas y Huesos para Mascotas'
ARENA = 'Arena para Gatos y Areneras'
ANTIPULGAS = 'Antipulgas, Garrapaticidas y Desparasitantes'
ESTETICA = 'Champú, Cepillos y Estética Canina'
CAMAS = 'Camas, Casas y Transportadoras'
PASEO = 'Paseo, Collares, Pecheras y Correas'
OTRAS = 'Aves, Peces y Otras Mascotas'

PRODUCTS = [
    # ------------------------------------------------------------------ Perros
    P('dog-chow-adultos-medianos-grandes', 'Perrarina Dog Chow Adultos Medianos y Grandes', PERROS, CAT, 9.50,
      'Alimento completo y balanceado de Purina para perros adultos de razas medianas y grandes, con proteína de carne y '
      'pollo, fibras naturales y antioxidantes. Croquetas de tamaño ideal para una buena digestión.',
      (STUDIO.format(what='a large bag of dry dog food kibble with a bowl of brown croquettes in front, plain packaging'),
       ALT.format(what='happy golden retriever eating dry kibble from a steel bowl on a kitchen floor, warm light')),
      attrs={'marca': 'Dog Chow (Purina)', 'etapa_mascota': 'Adulto Raza Mediana / Grande', 'sabor_proteina': 'Carne y pollo'},
      variants=[V({'presentation': 'Empaque 2 kg'}, 15), V({'presentation': 'Empaque 4 kg'}, 10, 17.90),
                V({'presentation': 'Saco 15 kg'}, 6, 54.00)],
      tokens=TOK_A),
    P('perrarina-granel-super-can-kg', 'Perrarina Super Can Adultos a Granel (por kg)', PERROS, CAT, 2.80,
      'Perrarina Super Can para perros adultos vendida al detal por kilo, pesada al momento en la tienda. '
      'Rendidora y económica, con proteína de carne y vitaminas. Pide los kilos que necesites.',
      (STUDIO.format(what='a pile of brown dry dog food kibble in a clear bag on a kitchen scale'),
       ALT.format(what='pet shop bulk bins with dry dog food and a metal scoop, close-up, soft light')),
      unit='kg',
      attrs={'marca': 'Super Can', 'etapa_mascota': 'Adulto Raza Mediana / Grande', 'sabor_proteina': 'Carne'},
      offer=8, stock=120),
    P('royal-canin-mini-adult', 'Royal Canin Mini Adult', PERROS, CAT, 15.00,
      'Alimento premium para perros adultos de razas pequeñas (hasta 10 kg), con croqueta pequeña adaptada a su mandíbula, '
      'nutrientes para piel y pelaje brillante y control del peso. Producto original importado.',
      (STUDIO.format(what='a premium bag of small breed adult dog food with tiny kibbles spilled in front, plain label'),
       ALT.format(what='small dog like a shih tzu eating small kibble from a ceramic bowl in a bright apartment')),
      attrs={'marca': 'Royal Canin', 'etapa_mascota': 'Adulto Raza Pequeña', 'sabor_proteina': 'Pollo y arroz'},
      variants=[V({'presentation': 'Empaque 1 kg'}, 12), V({'presentation': 'Empaque 4 kg'}, 5, 48.00)],
      tokens=TOK_C),

    # ------------------------------------------------------------------ Gatos
    P('cat-chow-adultos', 'Gatarina Cat Chow Adultos', GATOS, CAT, 7.90,
      'Alimento de Purina para gatos adultos con proteína de calidad, taurina para la salud visual y fibras que ayudan a '
      'controlar las bolas de pelo. Croquetas crujientes en sabor pescado y carne.',
      (STUDIO.format(what='a bag of dry cat food with a bowl of colorful fish-shaped kibbles in front, plain packaging'),
       ALT.format(what='tabby cat eating dry food from a bowl on a wooden floor, soft window light')),
      attrs={'marca': 'Cat Chow (Purina)', 'etapa_gato': 'Adultos'},
      variants=[V({'presentation': 'Empaque 1.5 kg'}, 14), V({'presentation': 'Empaque 3 kg'}, 9, 14.50),
                V({'presentation': 'Saco 8 kg'}, 4, 36.00)],
      tokens=TOK_A),
    P('whiskas-sobre-humedo-85g', 'Alimento Húmedo Whiskas Sobre 85 g', GATOS, CAT, 1.20,
      'Sobre de alimento húmedo en trocitos con salsa, completo y balanceado para gatos adultos. Aporta hidratación extra '
      'y un sabor que les encanta. Ideal para alternar con la gatarina.',
      (STUDIO.format(what='a few wet cat food pouches beside a small bowl with meat chunks in gravy, plain pouches'),
       ALT.format(what='cat licking wet food chunks from a small ceramic dish, close-up, cozy kitchen')),
      attrs={'marca': 'Whiskas', 'etapa_gato': 'Adultos'},
      variants=[V({'flavor': 'Pescado / Salmón'}, 60), V({'flavor': 'Carne'}, 45), V({'flavor': 'Pollo'}, 50)]),
    P('pro-plan-kitten-1kg', 'Pro Plan Kitten Pollo 1 kg', GATOS, CAT, 18.50,
      'Alimento súper premium para gatitos de 1 a 12 meses, con calostro y DHA para el desarrollo del cerebro y la '
      'visión. Proteína de pollo como primer ingrediente.',
      (STUDIO.format(what='a small premium bag of kitten dry food with tiny kibbles in a bowl, plain label'),
       ALT.format(what='curious kitten sniffing a bowl of small kibble on a soft rug, warm light')),
      unit='unit',
      attrs={'marca': 'Pro Plan (Purina)', 'etapa_gato': 'Gatitos (Kitten)'},
      tokens=TOK_B, stock=12),

    # ------------------------------------------------------------------ Snacks
    P('pedigree-dentastix-7-barras', 'Pedigree Dentastix 7 Barras', SNACKS, CAT, 4.50,
      'Snack dental en forma de X que reduce hasta 80% la formación de sarro con uso diario. Ayuda a mantener el aliento '
      'fresco. Paquete de 7 barras; elige según el tamaño de tu perro.',
      (STUDIO.format(what='a few X-shaped dental chew sticks for dogs arranged on a white surface next to a plain pouch'),
       ALT.format(what='happy beagle chewing a dental stick on a sofa, close-up, natural light')),
      attrs={'marca': 'Pedigree', 'especie': 'Perros'},
      variants=[V({'flavor_or_size': 'Pequeño'}, 20), V({'flavor_or_size': 'Mediano'}, 18, 5.20),
                V({'flavor_or_size': 'Grande'}, 12, 6.50)],
      offer=10),
    P('churu-snack-cremoso-4-tubos', 'Snack Cremoso para Gatos Churu Pack x4 Tubos', SNACKS, CAT, 3.90,
      'Snack cremoso para dar directo del tubo o sobre la comida, hecho con pollo o atún real. Perfecto para premiar, '
      'dar medicinas o consentir a tu gato. Pack de 4 tubos de 14 g.',
      (STUDIO.format(what='four squeezable creamy cat treat tubes fanned out, plain wrappers'),
       ALT.format(what='person feeding a cat a creamy treat from a squeeze tube, cat licking it happily')),
      unit='pack',
      attrs={'marca': 'Inaba Churu', 'especie': 'Gatos'},
      variants=[V({'flavor_or_size': 'Pollo'}, 30), V({'flavor_or_size': 'Atún / Salmón'}, 25)],
      tokens=TOK_A),

    # ------------------------------------------------------------------ Arena
    P('arena-aglomerante-america-litter', 'Arena Aglomerante América Litter Ultra Odor Seal', ARENA, CAT, 8.50,
      'Arena de bentonita de grano fino que forma bolas compactas fáciles de recoger y neutraliza los olores hasta por '
      '15 días. Baja en polvo y rendidora.',
      (STUDIO.format(what='a bag of clumping cat litter with a scoop of fine gray bentonite granules in front, plain bag'),
       ALT.format(what='clean litter box with fresh clumping litter and a scoop, cat peeking in the background')),
      attrs={'marca': 'América Litter', 'tipo_arena': 'Arena Aglomerante (Bentonita)'},
      variants=[V({'weight': '4.5 kg', 'scent': 'Lavanda'}, 15), V({'weight': '4.5 kg', 'scent': 'Sin Aroma (Neutra)'}, 12),
                V({'weight': '9 kg', 'scent': 'Lavanda'}, 8, 15.50), V({'weight': '9 kg', 'scent': 'Carbón Activado'}, 6, 15.50)],
      tokens=TOK_B),
    P('arenera-cubierta-con-pala', 'Arenera Cubierta con Filtro y Pala', ARENA, CAT, 24.00,
      'Caja sanitaria cerrada con puerta abatible, filtro de carbón que retiene olores y asa para transportarla. '
      'Mide 50 x 39 x 38 cm; incluye pala. Evita que la arena se riegue por la casa.',
      (STUDIO.format(what='a covered plastic cat litter box with a swing door, top handle and a scoop beside it'),
       ALT.format(what='cat walking out of a covered litter box in a laundry room corner, soft light')),
      attrs={'marca': 'Trixie', 'tipo_arena': 'Arenera / Caja Sanitaria / Pala'},
      offer=12, stock=8),

    # ------------------------------------------------------------------ Salud
    P('nexgard-tableta-antipulgas', 'NexGard Tableta Masticable Antipulgas y Garrapatas', ANTIPULGAS, CAT, 19.00,
      'Tableta masticable sabor carne que protege a tu perro de pulgas y garrapatas durante un mes completo. Fácil de dar '
      'y sin baños ni olores. Elige según el peso de tu perro; consulta a tu veterinario.',
      (STUDIO.format(what='a blister pack of chewable flea and tick tablets for dogs next to its plain box'),
       ALT.format(what='veterinarian giving a chewable tablet to a happy medium-sized dog in a clinic')),
      attrs={'marca': 'NexGard (Boehringer Ingelheim)', 'especie': 'Perros', 'via_administracion': 'Tableta Masticable'},
      variants=[V({'pet_weight_range': '2 a 4.5 kg (Mini)'}, 10), V({'pet_weight_range': '4.5 a 10 kg (Pequeño)'}, 12, 21.00),
                V({'pet_weight_range': '10 a 20 kg (Mediano)'}, 9, 23.00), V({'pet_weight_range': '20 a 40 kg (Grande)'}, 6, 25.00)],
      tokens=TOK_C),
    P('frontline-plus-pipeta-gatos', 'Frontline Plus Pipeta para Gatos', ANTIPULGAS, CAT, 14.00,
      'Pipeta spot-on que elimina pulgas, huevos, larvas y garrapatas, con protección hasta por 4 semanas. Se aplica en '
      'la nuca y es resistente al agua. Caja con 1 pipeta.',
      (STUDIO.format(what='a single spot-on flea treatment pipette for cats next to its plain box'),
       ALT.format(what='person applying a flea treatment pipette on the neck of a calm cat, close-up')),
      attrs={'marca': 'Frontline', 'especie': 'Gatos', 'via_administracion': 'Pipeta (Spot-On)'},
      tokens=TOK_A, stock=20),

    # ------------------------------------------------------------------ Estética
    P('champu-avena-aloe-perros', 'Champú de Avena y Aloe Vera para Perros', ESTETICA, CAT, 6.50,
      'Champú hipoalergénico con avena coloidal y aloe vera que calma la piel sensible y deja el pelaje suave y con olor '
      'agradable por días. pH balanceado para perros, apto para cachorros desde los 3 meses.',
      (STUDIO.format(what='a bottle of oatmeal and aloe dog shampoo with oats and an aloe leaf beside it, plain label'),
       ALT.format(what='wet dog covered in soapy foam being bathed in a grooming tub, happy expression')),
      attrs={'marca': 'Pet Spa'},
      variants=[V({'variant': '250 ml'}, 20), V({'variant': '500 ml'}, 14, 10.00), V({'variant': 'Galón (3.78L)'}, 4, 32.00)],
      offer=15),
    P('cepillo-slicker-autolimpiante', 'Cepillo Slicker Autolimpiante para Perros y Gatos', ESTETICA, CAT, 12.00,
      'Cepillo de cerdas de acero con puntas protegidas que retira el pelo muerto y los nudos sin lastimar. Con un botón '
      'retraes las cerdas y el pelo cae solo. Mango ergonómico antideslizante.',
      (STUDIO.format(what='a self-cleaning slicker pet brush with fine steel bristles and an ergonomic handle'),
       ALT.format(what='person brushing a fluffy cat with a slicker brush, loose fur visible, cozy living room')),
      attrs={'marca': 'Trixie'},
      tokens=TOK_A, stock=18),

    # ------------------------------------------------------------------ Descanso y transporte
    P('cama-donut-antiestres', 'Cama Donut Antiestrés de Peluche', CAMAS, CAT, 25.00,
      'Cama redonda tipo dona con borde elevado y pelo sintético largo que da sensación de abrigo y seguridad. '
      'Base antideslizante y lavable en lavadora. La favorita de perros pequeños y gatos.',
      (STUDIO.format(what='a round fluffy donut pet bed with raised rim in light gray faux fur'),
       ALT.format(what='small dog curled up sleeping in a fluffy donut bed next to a sofa, soft afternoon light')),
      attrs={'dimensiones': 'S 50 cm / M 70 cm / L 90 cm de diámetro'},
      variants=[V({'size': 'Talla S (Pequeña)', 'color': 'Gris'}, 8), V({'size': 'Talla S (Pequeña)', 'color': 'Beige'}, 6),
                V({'size': 'Talla M (Mediana)', 'color': 'Gris'}, 5, 32.00), V({'size': 'Talla M (Mediana)', 'color': 'Rosa'}, 4, 32.00),
                V({'size': 'Talla L (Grande)', 'color': 'Gris'}, 0, 42.00)],
      offer=20),
    P('transportadora-petmate-kennel-m', 'Transportadora Petmate Kennel Talla M', CAMAS, CAT, 59.00,
      'Transportadora rígida con puerta metálica, ventilación en los 4 lados y cierre de tornillos. Aprobada por la '
      'mayoría de aerolíneas, ideal para viajes y visitas al veterinario. Para mascotas de hasta 11 kg.',
      (STUDIO.format(what='a hard plastic pet travel crate with a metal wire door and side ventilation, three-quarter view'),
       ALT.format(what='cat looking out of a pet carrier on a car seat, ready for a trip, natural light')),
      attrs={'dimensiones': '61 x 40 x 38 cm'},
      tokens=TOK_B, stock=5),

    # ------------------------------------------------------------------ Paseo y juguetes
    P('pechera-acolchada-reflectiva', 'Pechera Acolchada Reflectiva con Correa', PASEO, CAT, 15.00,
      'Pechera tipo chaleco acolchada con malla transpirable, costuras reflectivas para paseos nocturnos y doble anillo '
      'de enganche. Incluye correa de 1,20 m. Ajuste fácil con broches de seguridad.',
      (STUDIO.format(what='a padded mesh dog harness with reflective trim and a matching leash, flat lay'),
       ALT.format(what='dog wearing a padded harness walking on a tree-lined city sidewalk with its owner')),
      attrs={'tipo_accesorio': 'Pechera / Arnés'},
      variants=grid('size', ['S', 'M', 'L'], 'color', ['Negro', 'Rojo', 'Azul'], stock=5, sold_out=[('L', 'Rojo')]),
      tokens=TOK_A),
    P('fuente-agua-automatica-gatos-2-5l', 'Fuente de Agua Automática para Gatos 2.5 L', PASEO, CAT, 29.00,
      'Bebedero eléctrico silencioso con agua en circulación y filtro de carbón activado que motiva a tu gato a tomar más '
      'agua. Capacidad de 2,5 litros, alimentación USB.',
      (STUDIO.format(what='an automatic pet water fountain with flowing water and a carbon filter, white plastic'),
       ALT.format(what='cat drinking from a flowing water fountain in a bright kitchen, close-up')),
      attrs={'tipo_accesorio': 'Comedero / Bebedero / Fuente'},
      tokens=TOK_B, stock=10),
    P('juguete-kong-classic', 'Juguete KONG Classic Rellenable', PASEO, CAT, 16.00,
      'Juguete de caucho natural súper resistente, con rebote impredecible y hueco para rellenar con premios o pasta de '
      'maní. Mantiene a tu perro entretenido y reduce la ansiedad cuando se queda solo.',
      (STUDIO.format(what='a red natural rubber snowman-shaped dog chew toy, front view'),
       ALT.format(what='dog lying on grass chewing a red rubber treat toy, sunny backyard')),
      attrs={'tipo_accesorio': 'Juguete / Mordedor'},
      offer=10, stock=22),

    # ------------------------------------------------------------------ Aves y peces
    P('alimento-peces-tropicales-tetramin', 'Alimento en Hojuelas TetraMin para Peces Tropicales', OTRAS, CAT, 6.50,
      'Hojuelas balanceadas con vitaminas y minerales para peces tropicales de acuario: guppys, mollys, tetras y más. '
      'No enturbia el agua. Envase de 62 g.',
      (STUDIO.format(what='a small canister of tropical fish flake food with colorful flakes spilled beside it, plain label'),
       ALT.format(what='colorful tropical fish eating flakes at the surface of a planted aquarium, vivid lighting')),
      attrs={'especie': 'Peces / Acuariofilia'},
      stock=30),
]
