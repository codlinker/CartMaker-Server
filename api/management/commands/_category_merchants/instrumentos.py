# -*- coding: utf-8 -*-
"""Catálogo demo de Sonido Criollo Music Store (Instrumentos Musicales): 20 productos."""
from ._helpers import ALT, STUDIO, TOK_A, TOK_B, TOK_C, M, P, V, grid, sizes  # noqa: F401

CAT = 'Instrumentos Musicales'

PRODUCTS = [
    # ------------------------------------------------------------------ Instrumentos criollos
    P('cuatro-venezolano-cedro', 'Cuatro Venezolano Profesional de Cedro', 'Cuatros Venezolanos, Maracas y Furrucos', CAT, 120.00,
      'Cuatro hecho a mano por luthiers larenses, con tapa de pino abeto, aros y fondo de cedro y diapasón de palo de '
      'rosa. Sonido brillante y afinación estable para joropo, gaita y parranda. Garantía de 6 meses.',
      (STUDIO.format(what='a handcrafted Venezuelan cuatro, a small four string guitar with natural cedar wood finish'),
       ALT.format(what='hands strumming a Venezuelan cuatro guitar, close-up of the sound hole and strings, warm light')),
      attrs={'luthier_marca': 'Taller Luthier Larense (Carora)',
             'madera_material': 'Tapa de pino abeto, aros y fondo de cedro, diapasón de palo de rosa',
             'incluye_forro': False},
      variants=[V({'version': 'Estándar (14 Trastes)'}, 6), V({'version': 'Con Forro Incluido'}, 5, 135.00),
                V({'version': 'Concierto (17 Trastes)'}, 3, 165.00), V({'version': 'Electroacústico'}, 2, 185.00)],
      tokens=TOK_C),
    P('cuatro-escolar-principiante', 'Cuatro Escolar para Principiantes con Forro', 'Cuatros Venezolanos, Maracas y Furrucos', CAT, 55.00,
      'Cuatro de estudio en madera laminada, liviano y fácil de tocar, ideal para niños y para empezar en las '
      'clases del colegio. Incluye forro acolchado y juego de cuerdas de repuesto.',
      (STUDIO.format(what='a small student Venezuelan cuatro guitar in light wood with a padded gig bag beside it'),
       ALT.format(what='a child learning to play a small four string cuatro guitar in a music class')),
      attrs={'luthier_marca': 'Sonido Criollo', 'madera_material': 'Laminado de pino y caoba', 'incluye_forro': True},
      offer=10, stock=12),
    P('maracas-llaneras-tapara', 'Maracas Llaneras de Tapara (Par)', 'Cuatros Venezolanos, Maracas y Furrucos', CAT, 25.00,
      'Par de maracas llaneras artesanales hechas con tapara curada, semillas de capacho y mango de madera torneada. '
      'Sonido seco y parejo, perfectas para el joropo y el arpa llanera.',
      (STUDIO.format(what='a pair of traditional Venezuelan maracas made of natural dried gourds with wooden handles'),
       ALT.format(what='a musician shaking traditional gourd maracas on stage, motion blur, warm stage light')),
      unit='pair', attrs={'luthier_marca': 'Artesanos de Apure',
                          'madera_material': 'Tapara (totuma) curada, capacho y mango de madera'},
      tokens=TOK_A, stock=15),
    P('furruco-tradicional-gaitas', 'Furruco Tradicional para Gaitas', 'Cuatros Venezolanos, Maracas y Furrucos', CAT, 45.00,
      'Furruco artesanal de cuerpo de madera, parche de cuero de chivo templado y vara de caña. El bajo inconfundible '
      'de la gaita zuliana y las parrandas decembrinas.',
      (STUDIO.format(what='a traditional Venezuelan friction drum with a wooden body, goatskin head and a cane stick in the center'),
       ALT.format(what='a traditional friction drum being played at a Christmas folk music gathering, festive lights')),
      attrs={'luthier_marca': 'Artesanos del Zulia',
             'madera_material': 'Cuerpo de madera, parche de cuero de chivo y vara de caña'},
      stock=5),
    # ------------------------------------------------------------------ Cuerda
    P('bandola-llanera-4-cuerdas', 'Bandola Llanera de 4 Cuerdas', 'Instrumentos de Cuerda', CAT, 140.00,
      'Bandola llanera en forma de pera, con tapa de pino, cuerpo de cedro y 4 cuerdas de nylon. Hecha a mano para '
      'el pasaje y el joropo. Incluye estuche semirrígido.',
      (STUDIO.format(what='a pear shaped Venezuelan bandola, a four string folk lute with natural wood finish'),
       ALT.format(what='a folk musician playing a pear shaped bandola with a pick, close-up of hands, warm light')),
      attrs={'instrumento': 'Mandolina / Bandola', 'marca': 'Taller Luthier Larense', 'incluye_estuche': True},
      tokens=TOK_A, stock=3),
    P('arpa-llanera-32-cuerdas', 'Arpa Llanera de 32 Cuerdas', 'Instrumentos de Cuerda', CAT, 650.00,
      'Arpa llanera tradicional de 32 cuerdas de nylon, caja de cedro y clavijero de madera dura. Sonido potente '
      'para joropo y música llanera. Instrumento hecho por encargo, entrega en tienda con afinación incluida.',
      (STUDIO.format(what='a traditional Venezuelan llanera harp with natural wood finish and thirty two nylon strings'),
       ALT.format(what='a musician playing a wooden folk harp on a stage with warm spotlight, side view')),
      attrs={'instrumento': 'Arpa', 'marca': 'Luthería Criolla', 'incluye_estuche': False},
      stock=2),
    # ------------------------------------------------------------------ Guitarras y bajos
    P('guitarra-clasica-yamaha-c40', 'Guitarra Clásica Yamaha C40', 'Guitarras y Bajos', CAT, 145.00,
      'La guitarra de estudio más vendida: tapa de abeto, aros y fondo de meranti y cuerdas de nylon. Cómoda, '
      'bien afinada y con garantía de 1 año.',
      (STUDIO.format(what='a classical nylon string acoustic guitar with natural spruce top, full front view'),
       ALT.format(what='a person playing a classical guitar sitting on a chair in a sunny living room')),
      attrs={'marca': 'Yamaha', 'tipo_instrumento': 'Guitarra Clásica (Nylon)', 'condicion': 'Nuevo', 'garantia': '1 año'},
      variants=sizes('color', ['Natural', 'Negro'], stock=5),
      tokens=TOK_B),
    P('guitarra-fender-cd60sce', 'Guitarra Electroacústica Fender CD-60SCE', 'Guitarras y Bajos', CAT, 279.00,
      'Guitarra dreadnought con tapa sólida de caoba, cutaway para llegar a los trastes altos y preamplificador '
      'Fishman con afinador integrado. Lista para tocar en vivo. Garantía de 1 año.',
      (STUDIO.format(what='a dreadnought cutaway acoustic electric guitar with a sunburst finish'),
       ALT.format(what='an acoustic electric guitar plugged in on a small stage with a microphone stand, warm lights')),
      attrs={'marca': 'Fender', 'tipo_instrumento': 'Guitarra Acústica / Electroacústica', 'condicion': 'Nuevo',
             'garantia': '1 año'},
      variants=sizes('color', ['Natural', 'Sunburst', 'Negro'], stock=3, sold_out=('Negro',)),
      offer=10),
    P('guitarra-squier-sonic-strat', 'Guitarra Eléctrica Squier Sonic Stratocaster', 'Guitarras y Bajos', CAT, 229.00,
      'Stratocaster de Squier con cuerpo de álamo, mástil de arce, 3 pastillas single-coil y puente trémolo. '
      'El primer paso ideal en la guitarra eléctrica. Garantía de 1 año.',
      (STUDIO.format(what='a classic double cutaway electric guitar with three single coil pickups and a white pickguard'),
       ALT.format(what='an electric guitar leaning against a small guitar amplifier in a home studio')),
      attrs={'marca': 'Squier by Fender', 'tipo_instrumento': 'Guitarra Eléctrica', 'condicion': 'Nuevo',
             'garantia': '1 año'},
      variants=sizes('color', ['Sunburst', 'Negro', 'Rojo'], stock=3),
      tokens=TOK_C),
    P('bajo-ibanez-gsr200', 'Bajo Eléctrico Ibanez GSR200 4 Cuerdas', 'Guitarras y Bajos', CAT, 299.00,
      'Bajo de 4 cuerdas con mástil delgado de arce, pastillas PJ y ecualizador activo Phat II para un sonido gordo '
      'y definido. Excelente para salsa, rock y gospel. Garantía de 1 año.',
      (STUDIO.format(what='a four string electric bass guitar with a black body and rosewood fingerboard'),
       ALT.format(what='a bassist playing a four string electric bass on stage, close-up of fingers on strings')),
      attrs={'marca': 'Ibanez', 'tipo_instrumento': 'Bajo Eléctrico (4 cuerdas)', 'condicion': 'Nuevo',
             'garantia': '1 año'},
      stock=3),
    # ------------------------------------------------------------------ Teclados
    P('teclado-yamaha-psr-e383', 'Teclado Yamaha PSR-E383 61 Teclas', 'Teclados, Sintetizadores y Pianos Eléctricos', CAT, 219.00,
      'Teclado de 61 teclas sensibles al tacto, 650 voces, 260 ritmos (incluye ritmos latinos) y modo de lecciones. '
      'Incluye adaptador de corriente. Disponible en combo con paral en X y banqueta.',
      (STUDIO.format(what='a black 61 key portable digital keyboard with control buttons and speakers'),
       ALT.format(what='a teenager practicing on a portable keyboard on an X stand in a bedroom')),
      attrs={'marca': 'Yamaha', 'modelo': 'PSR-E383', 'condicion': 'Nuevo', 'garantia': '1 año'},
      variants=[V({'keys_or_bundle': 'Solo Teclado'}, 5), V({'keys_or_bundle': 'Combo con Paral/Base'}, 3, 249.00)],
      offer=15),
    P('controlador-midi-akai-mpk-mini', 'Controlador MIDI Akai MPK Mini MK3 25 Teclas', 'Teclados, Sintetizadores y Pianos Eléctricos', CAT, 119.00,
      'Controlador USB compacto con 25 miniteclas, 8 pads retroiluminados y 8 perillas asignables. Perfecto para '
      'producir música en casa con cualquier DAW. Incluye software.',
      (STUDIO.format(what='a compact 25 mini key MIDI controller with backlit drum pads and rotary knobs'),
       ALT.format(what='a compact MIDI keyboard next to a laptop with music production software in a home studio')),
      attrs={'marca': 'Akai Professional', 'modelo': 'MPK Mini MK3', 'condicion': 'Nuevo', 'garantia': '6 meses'},
      tokens=TOK_B, stock=6),
    # ------------------------------------------------------------------ Amplificadores
    P('amplificador-fender-frontman', 'Amplificador para Guitarra Fender Frontman', 'Amplificadores', CAT, 79.00,
      'Amplificador de práctica con canales limpio y distorsión, ecualizador de 3 bandas y salida para audífonos. '
      'Sonido Fender clásico para tocar en casa. Garantía de 1 año.',
      (STUDIO.format(what='a small black guitar practice amplifier with a silver grille and control knobs on top'),
       ALT.format(what='an electric guitar plugged into a small practice amplifier in a bedroom, cable visible')),
      attrs={'marca': 'Fender', 'instrumento_uso': 'Guitarra Eléctrica', 'potencia_watts': '10 W / 20 W',
             'condicion': 'Nuevo', 'garantia': '1 año'},
      variants=[V({'wattage': '10W'}, 6), V({'wattage': '20W'}, 4, 115.00)],
      tokens=TOK_A),
    # ------------------------------------------------------------------ Batería y percusión
    P('bateria-acustica-mapex-5-piezas', 'Batería Acústica Mapex Tornado 5 Piezas', 'Baterías y Percusión', CAT, 449.00,
      'Batería completa de 5 cuerpos (bombo de 22", toms de 10" y 12", tom de piso de 16" y redoblante de 14") '
      'con herrajes, platillos hi-hat y crash, banqueta y baquetas. Te la armamos en tienda.',
      (STUDIO.format(what='a complete five piece acoustic drum kit with cymbals, stool and hardware'),
       ALT.format(what='a drummer playing an acoustic drum kit in a rehearsal room, motion on the sticks')),
      unit='set', attrs={'marca': 'Mapex', 'condicion': 'Nuevo'},
      variants=sizes('size_color', ['Negro', 'Rojo Vino', 'Azul'], stock=2, sold_out=('Azul',)),
      offer=8),
    P('bongos-lp-aspire', 'Bongós LP Aspire de Madera', 'Percusión Latina, Congas, Timbales y Bongós', CAT, 89.00,
      'Bongós de madera de siam oak con parches naturales de 6.75" y 8", herrajes cromados y llave de afinación. '
      'Sonido cálido para salsa, merengue y gaita.',
      (STUDIO.format(what='a pair of wooden bongo drums with natural skin heads and chrome tuning lugs'),
       ALT.format(what='hands playing wooden bongo drums at a Latin music jam session, warm light')),
      attrs={'marca': 'LP Latin Percussion', 'incluye_paral': False},
      variants=sizes('size', ['Madera Natural', 'Rojo'], stock=4),
      tokens=TOK_B),
    # ------------------------------------------------------------------ Viento
    P('flauta-dulce-yamaha-yrs-24b', 'Flauta Dulce Soprano Yamaha YRS-24B', 'Instrumentos de Viento, Flautas y Saxofones', CAT, 9.50,
      'Flauta dulce soprano de digitación barroca en resina ABS, la que piden en las listas escolares. '
      'Afinación precisa, incluye funda y limpiador.',
      (STUDIO.format(what='a cream colored plastic soprano recorder flute with its cleaning rod and soft case'),
       ALT.format(what='a school child playing a soprano recorder in a music classroom')),
      attrs={'marca': 'Yamaha', 'condicion': 'Nuevo'},
      offer=20, stock=40),
    # ------------------------------------------------------------------ Sonido en vivo
    P('microfono-shure-sm58', 'Micrófono Vocal Shure SM58', 'Micrófonos, Consolas y Sonido en Vivo', CAT, 119.00,
      'El micrófono dinámico más usado en tarimas de todo el mundo, patrón cardioide que reduce el ruido del ambiente '
      'y cuerpo prácticamente indestructible. Incluye pipa y estuche. Garantía de 2 años.',
      (STUDIO.format(what='a classic dynamic vocal microphone with a silver ball grille and black handle'),
       ALT.format(what='a singer holding a dynamic microphone on stage under colorful concert lights')),
      attrs={'marca': 'Shure', 'modelo': 'SM58', 'garantia': '2 años'},
      tokens=TOK_C, stock=8),
    P('audifonos-audio-technica-m20x', 'Audífonos de Monitoreo Audio-Technica ATH-M20x', 'Equipos para DJ y Audífonos de Monitoreo', CAT, 59.00,
      'Audífonos cerrados de estudio con drivers de 40 mm, respuesta plana para mezcla y excelente aislamiento. '
      'Cable de 3 m y adaptador de 6.3 mm incluidos. Garantía de 1 año.',
      (STUDIO.format(what='black closed back over ear studio monitor headphones with a coiled cable'),
       ALT.format(what='a music producer wearing studio headphones in front of a mixing desk')),
      attrs={'marca': 'Audio-Technica', 'condicion': 'Nuevo', 'garantia': '1 año'},
      offer=15, stock=10),
    # ------------------------------------------------------------------ Accesorios
    P('cuerdas-cuatro-aquila', 'Juego de Cuerdas para Cuatro Venezolano', 'Cuerdas, Fundas, Afinadores y Pedales', CAT, 6.00,
      'Juego de 4 cuerdas de nylon especiales para cuatro venezolano con afinación tradicional (La-Re-Fa#-Si). '
      'Sonido brillante y gran durabilidad.',
      (STUDIO.format(what='a set of four nylon strings for a small folk guitar, coiled in a neat circle'),
       ALT.format(what='a musician changing nylon strings on a small cuatro guitar headstock, close-up of tuning pegs')),
      unit='set', attrs={'marca': 'Aquila'},
      tokens=TOK_A, stock=50),
    P('cuerdas-guitarra-electrica-daddario', "Cuerdas para Guitarra Eléctrica D'Addario EXL", 'Cuerdas, Fundas, Afinadores y Pedales', CAT, 7.50,
      "Juego de 6 cuerdas de níquel entorchado D'Addario EXL, el estándar para guitarra eléctrica. "
      'Escoge tu calibre: .009 para mayor comodidad, .010 balanceado o .011 para un tono más grueso.',
      (STUDIO.format(what='a set of coiled nickel electric guitar strings next to their paper envelopes, no readable text'),
       ALT.format(what='close-up of new strings on an electric guitar headstock with tuning machines')),
      unit='set', attrs={'marca': "D'Addario"},
      variants=sizes('gauge', ['Calibre .009', 'Calibre .010', 'Calibre .011'], stock=20)),
]
