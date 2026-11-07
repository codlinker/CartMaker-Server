"""Léxico comercial venezolano exhaustivo para matching de compras en las 16 categorías y 178 subcategorías de CartMaker."""

import re
from typing import Iterable, List, Set

SEARCH_STOPWORDS = {
    'a', 'al', 'algo', 'algun', 'algún', 'alguna', 'alguno', 'allá', 'alla',
    'buscar', 'compra', 'comprar', 'con', 'consigue', 'conseguir', 'cocinar',
    'de', 'del', 'el', 'en', 'esta', 'está', 'esto', 'hacer', 'hoy', 'la',
    'las', 'lo', 'los', 'me', 'mi', 'necesito', 'o', 'para', 'por', 'que',
    'qué', 'quiero', 'se', 'si', 'sin', 'un', 'una', 'unas', 'unos', 'y',
    'ya', 'yo',
}

# ==============================================================================
# DICCIONARIO EXHAUSTIVO DE SINÓNIMOS, VENEZOLANISMOS, MARCAS GENÉRICAS,
# VARIANTES ORTOGRÁFICAS Y PALABRAS COMPUESTAS (16 CATEGORÍAS / 178 SUBCATEGORÍAS)
# ==============================================================================
SYNONYM_GROUPS: List[List[str]] = [
    # --------------------------------------------------------------------------
    # 1. ALIMENTOS Y BEBIDAS
    # --------------------------------------------------------------------------
    # Víveres y Granos
    ['caraota', 'caraotas', 'caraotas negras', 'frijol negro', 'frijoles negros', 'habichuela negra', 'poroto negro'],
    ['caraota roja', 'caraotas rojas', 'frijol rojo', 'frijoles rojos'],
    ['caraota blanca', 'caraotas blancas', 'frijol blanco'],
    ['caraota palo', 'frijol palo', 'frijoles palo', 'frijol bayo', 'quinchoncho'],
    ['lenteja', 'lentejas'],
    ['arveja', 'arvejas', 'guisante', 'guisantes', 'chicharo'],
    ['garbanzo', 'garbanzos'],
    ['maiz de cotufa', 'maíz de cotufa', 'cotufa', 'cotufas', 'palomitas de maiz', 'popcorn'],
    ['harina pan', 'harina p.a.n.', 'harina de maiz', 'harina de maíz', 'harina precocida', 'harina de cachapa', 'harina Juana', 'harina kapan'],
    ['harina de trigo', 'harina todo uso', 'harina leudante', 'harina panadera'],
    ['arroz', 'arroz blanco', 'arroz mary', 'arroz primor', 'arroz parboiled', 'arroz integral'],
    ['pasta', 'pastas', 'espagueti', 'spaguetti', 'spaghetti', 'linguini', 'vermicelli', 'codito', 'coditos', 'plumita', 'plumitas', 'tornillito', 'pasticho', 'lasaña'],
    ['aceite', 'aceite vegetal', 'aceite de soya', 'aceite de maiz', 'aceite de maíz', 'aceite de girasol', 'aceite mazeite', 'aceite vatel'],
    ['aceite de oliva', 'aceite extravirgen', 'aceite extra virgen'],
    ['azucar', 'azúcar', 'azucar blanca', 'azucar montalban', 'azucar morena', 'azucar moscabada', 'edulcorante', 'stevia', 'splenda'],
    ['papelon', 'papelón', 'panela', 'dulce de papelon', 'dulce de papelón'],
    ['sal', 'sal de cocina', 'sal marina', 'sal refinada', 'sal gruesa'],
    ['avena', 'avena en hojuelas', 'hojuelas de avena', 'quaker', 'avena integral'],
    ['fororo', 'maiz tostado'],
    ['crema de arroz', 'cereal infantil', 'nestum', 'cerelac'],
    ['cereal', 'cereales', 'corn flakes', 'hojuelas de maiz', 'zucaritas', 'choco krispis', 'froot loops', 'granola', 'muesli'],

    # Frutas, Verduras y Hortalizas
    ['platano', 'plátano', 'platano maduro', 'plátano maduro', 'tajadas'],
    ['platano verde', 'plátano verde', 'verde', 'toston', 'tostones'],
    ['cambur', 'banana', 'banano', 'guineo', 'cambur manzano', 'cambur titiaro'],
    ['yuca', 'mandioca', 'casabe', 'casabé', 'naiboa'],
    ['ocumo', 'ocumo blanco', 'ocumo chino', 'malanga'],
    ['ñame', 'name', 'mapuey'],
    ['batata', 'camote', 'boniato'],
    ['apio', 'apio criollo', 'arracacha'],
    ['celery', 'céleri', 'apio españa'],
    ['papa', 'papas', 'papa blanca', 'papa colombiana', 'papa amarilla'],
    ['auyama', 'calabaza', 'zapallo'],
    ['calabacin', 'calabacín', 'zucchini'],
    ['berenjena', 'berenjenas'],
    ['chayota', 'chayote', 'cidra'],
    ['zanahoria', 'zanahorias'],
    ['remolacha', 'remolachas', 'betabel'],
    ['cebolla', 'cebollas', 'cebolla blanca', 'cebolla morada'],
    ['cebollin', 'cebollín', 'cebolla en rama', 'cebolleta'],
    ['ajoporro', 'ajo porro', 'puerro'],
    ['ajo', 'ajos', 'cabeza de ajo', 'diente de ajo', 'ajo pelado'],
    ['ajicero', 'aji', 'ají', 'aji dulce', 'ají dulce', 'aji picante', 'chirel'],
    ['pimenton', 'pimentón', 'pimiento', 'morrón'],
    ['tomate', 'tomates', 'tomate perita', 'tomate manzano', 'jitomate'],
    ['lechuga', 'lechuga americana', 'lechuga romana', 'berro', 'rucula', 'rúcula'],
    ['repollo', 'repollo blanco', 'repollo morado', 'col'],
    ['brocoli', 'brócoli', 'coliflor'],
    ['espinaca', 'espinacas', 'acelga', 'acelgas'],
    ['pepino', 'pepinos'],
    ['vainita', 'vainitas', 'habichuelas verdes', 'ejotes'],
    ['maiz tierno', 'jojoto', 'jojotos', 'mazorca', 'elote'],
    ['cilantro', 'culantro', 'cilantro españa'],
    ['perejil', 'hierbabuena', 'menta', 'albahaca', 'romero', 'tomillo', 'laurel', 'oregano', 'orégano'],
    ['jengibre', 'curcuma', 'cúrcuma'],
    ['aguacate', 'aguacates', 'palta', 'aguacate polo'],
    ['limon', 'limón', 'limones', 'lima'],
    ['naranja', 'naranjas', 'mandarina', 'mandarinas', 'toronja', 'pomelo'],
    ['lechoza', 'lechosa', 'papaya'],
    ['patilla', 'sandia', 'sandía'],
    ['melon', 'melón'],
    ['piña', 'pina', 'anana', 'ananá'],
    ['guayaba', 'guayabas'],
    ['parchita', 'maracuya', 'maracuyá', 'fruta de la pasion'],
    ['mora', 'moras', 'fresa', 'fresas', 'frutilla'],
    ['guanabana', 'guanábana', 'chirimoya', 'nispero', 'níspero', 'tamarindo'],
    ['mango', 'mangos', 'manga'],
    ['durazno', 'duraznos', 'melocoton', 'melocotón'],
    ['manzana', 'manzanas', 'manzana roja', 'manzana verde', 'pera', 'peras'],
    ['uva', 'uvas', 'ciruela', 'ciruelas', 'kiwi'],
    ['coco', 'coco seco', 'agua de coco'],

    # Carnicería, Aves, Pescadería y Charcutería
    ['res', 'carne de res', 'carne roja', 'bistec', 'bisteck'],
    ['lomito', 'solomo', 'solomo de cuerito', 'punta trasera', 'picaña', 'churrasco', 't-bone', 'ribeye'],
    ['carne mechada', 'carne desmechada', 'carne para mechar', 'falda de res', 'pabellon', 'pabellón'],
    ['carne molida', 'carne picada'],
    ['carne para guisar', 'chocozuela', 'pulpa negra', 'muchacho redondo', 'muchacho cuadrado', 'ganso', 'paleta de res'],
    ['lagarto', 'lagarto con hueso', 'ossobuco', 'lagarto la reina', 'costilla de res', 'tira de asado'],
    ['higado', 'hígado', 'higado de res', 'mondongo', 'panza', 'lengua de res', 'chinchurria', 'bofe', 'corazon de res'],
    ['pollo', 'pollo entero', 'pollo beneficiado'],
    ['pechuga', 'pechuga de pollo', 'filet de pechuga', 'milanesa de pollo', 'churrasco de pollo'],
    ['muslo', 'muslos', 'muslo de pollo', 'chupeta de pollo', 'contramuslo'],
    ['alitas', 'alitas de pollo', 'alas de pollo', 'mollejas', 'higaditos de pollo', 'patas de pollo', 'gallina'],
    ['cerdo', 'cochino', 'carne de cerdo', 'puerco', 'chancho'],
    ['chuleta', 'chuletas', 'chuleta ahumada', 'chuleta de cerdo', 'costillitas de cerdo', 'costilla de cerdo', 'lomo de cerdo', 'pernil', 'lomito de cerdo'],
    ['tocineta', 'bacon', 'panceta', 'chicharron', 'chicharrón'],
    ['chorizo', 'chorizos', 'chorizo criollo', 'chorizo parrillero', 'chorizo de ajo', 'chorizo ahumado', 'chistorra', 'morcilla', 'butifarra'],
    ['pescado', 'pescados', 'filete de pescado', 'rueda de pescado'],
    ['pargo', 'pargo rojo', 'mero', 'corvina', 'curvina', 'merluza', 'robalo', 'dorado', 'carite', 'cazon', 'cazón', 'atun fresco', 'salmon', 'salmón', 'trucha', 'tilapia', 'lisa', 'lebisa', 'raya'],
    ['camaron', 'camarón', 'camarones', 'langostino', 'langostinos'],
    ['calamar', 'calamares', 'pulpo', 'mejillon', 'mejillones', 'pepitoria', 'guacuco', 'almejas', 'mariscos', 'paella', 'fosforera'],
    ['charcuteria', 'charcutería', 'fiambre', 'embutido', 'embutidos'],
    ['jamon', 'jamón', 'jamon de espalda', 'jamon de pierna', 'jamon ahumado', 'jamon planchado', 'jamon serrano', 'prosciutto'],
    ['jamon de pavo', 'pechuga de pavo'],
    ['mortadela', 'jamonada', 'bologna', 'mortadela tapara', 'mortadela especial'],
    ['salchicha', 'salchichas', 'salchicha viena', 'salchicha polaca', 'salchicha desayuno'],
    ['salami', 'salame', 'pepperoni', 'peperoni', 'copa'],

    # Lácteos y Huevos
    ['queso blanco', 'queso duro', 'queso llanero', 'queso para rallar', 'queso merideño'],
    ['queso de mano', 'queso telita', 'queso guayanes', 'queso guayanés', 'queso palmita', 'queso santa barbara', 'queso paisa', 'queso crineja', 'queso trenza', 'queso clineja'],
    ['queso amarillo', 'queso gouda', 'queso edam', 'queso holandes', 'queso cheddar', 'queso americano', 'facilistas'],
    ['queso mozzarella', 'mozzarella', 'mozarela', 'queso parmesano', 'queso pecorino', 'queso ricotta', 'requeson', 'requesón', 'queso de cabra'],
    ['queso crema', 'queso philadelphia', 'queso untable'],
    ['nata', 'nata criolla', 'crema de leche', 'suero', 'suero cremoso', 'suero picante', 'suero lara'],
    ['mantequilla', 'margarina', 'mavesa', 'nelly', 'mantequilla con sal'],
    ['leche', 'leche liquida', 'leche completa', 'leche entera', 'leche descremada', 'leche deslactosada'],
    ['leche en polvo', 'leche la campiña', 'leche la campina', 'leche klim'],
    ['leche condensada', 'leche evaporada', 'arequipe', 'dulce de leche'],
    ['yogurt', 'yogur', 'yoghurt', 'yogurt griego', 'migurt', 'kumis'],
    ['huevo', 'huevos', 'carton de huevos', 'medio carton de huevos', 'ñema', 'yema'],

    # Panadería, Enlatados, Salsas, Condimentos, Bebidas y Chucherías
    ['pan', 'pan canilla', 'canilla', 'pan frances', 'pan campesino', 'baguette', 'pan sobado'],
    ['pan de sandwich', 'pan de sándwich', 'pan cuadrado', 'pan de molde', 'pan integral'],
    ['pan de perro', 'pan de perro caliente', 'pan de hamburguesa', 'pan de pepito'],
    ['pan de jamon', 'pan de jamón', 'cachito', 'cachitos', 'croissant', 'pastelito', 'golfeado', 'golfeados', 'piñita', 'acema', 'catalina', 'palmerita'],
    ['atun en lata', 'atún en lata', 'atun enlatado', 'atún enlatado', 'lata de atun', 'atun margarita', 'atun eveba'],
    ['sardina', 'sardinas', 'sardina en lata', 'sardinas enlatadas', 'lata de sardina'],
    ['diablitos', 'jamon endiablado', 'jamón endiablado', 'underwood'],
    ['maiz en lata', 'maiz dulce', 'petit pois', 'guisantes en lata', 'champiñones en lata', 'aceitunas', 'alcaparras', 'encurtidos', 'melocotones en almibar'],
    ['mayonesa', 'mayo', 'mayonesa mavesa', 'mayonesa kraft'],
    ['ketchup', 'catsup', 'salsa de tomate', 'pampero', 'heinz'],
    ['mostaza', 'mostaza amarilla', 'mostaza dijon'],
    ['salsa inglesa', 'salsa de soya', 'salsa de ajo', 'salsa picante', 'picante', 'tabasco', 'salsa bbq', 'salsa barbecue', 'salsa rosada', 'salsa tartara', 'guasacaca'],
    ['pasta de tomate', 'salsa napolitana', 'salsa para pasta', 'passata', 'tomate pelado'],
    ['vinagre', 'vinagre blanco', 'vinagre de manzana', 'vinagre balsamico'],
    ['adobo', 'adobo la comadre', 'cubito', 'cubitos', 'caldo de pollo', 'caldo de res', 'maggi', 'knorr', 'sazonador', 'consome'],
    ['onoto', 'achiote', 'carmencita', 'comino', 'pimienta', 'pimienta negra', 'ajo en polvo', 'cebolla en polvo', 'paprika', 'pimenton en polvo', 'curry', 'canela', 'clavo de olor', 'anís estrellado', 'nuez moscada'],
    ['vainilla', 'esencia de vainilla', 'polvo de hornear', 'bicarbonato', 'bicarbonato de sodio', 'levadura', 'maicena', 'fecula de maiz', 'gelatina'],
    ['cafe', 'café', 'cafe molido', 'cafe en grano', 'cafe instantaneo', 'nescafe', 'cafe madrid', 'cafe fama de america'],
    ['te', 'té', 'te negro', 'te verde', 'manzanilla', 'infusion', 'infusiones', 'jamaica'],
    ['cacao', 'cocoa', 'chocolate en polvo', 'toddy', 'nesquik', 'achocolatado', 'ovomaltina', 'chicha en polvo'],
    ['malta', 'maltin', 'maltín', 'maltin polar'],
    ['refresco', 'refrescos', 'gaseosa', 'soda', 'pepsi', 'coca cola', 'coca-cola', 'chinotto', 'sprite', '7up', 'fanta', 'frescolita', 'golden', 'hit', 'kolita'],
    ['jugo', 'jugos', 'jugo pasteurizado', 'nectar', 'néctar', 'yukery', 'tutti frutti', 'te frio', 'té frío', 'nestea', 'lipton', 'clight', 'tang'],
    ['agua', 'agua mineral', 'botella de agua', 'botellon de agua', 'botellón', 'agua con gas', 'soda', 'minalba'],
    ['bebida energetica', 'energizante', 'red bull', 'monster', 'gatorade', 'powerade', 'hidratante'],
    ['cerveza', 'cervezas', 'birra', 'polar', 'polar pilsen', 'polar light', 'solera', 'zulia', 'regional', 'tercio', 'curda'],
    ['ron', 'ron añejo', 'cacique', 'santa teresa', 'diplomatico', 'carupano', 'pampero', 'whisky', 'whiskey', 'escoces', 'buchanans', 'old parr', 'black label', 'vodka', 'ginebra', 'gin', 'tequila', 'vino', 'vino tinto', 'vino blanco', 'sangria', 'caroreña', 'espumante', 'champaña', 'prosecco', 'anis', 'anís', 'ponche crema', 'licor'],
    ['galleta', 'galletas', 'galleta soda', 'galleta maria', 'club social', 'kraker', 'oreo', 'cocosette', 'susy', 'samba', 'pirulin', 'pirulín', 'wafer'],
    ['chucheria', 'chuchería', 'chucherias', 'snack', 'snacks', 'pasapalo', 'pasapalos', 'pepito', 'cheetos', 'doritos', 'ruffles', 'papitas', 'platanitos', 'tostones', 'chicharron', 'mani', 'maní', 'merey', 'pistacho', 'almendras', 'nueces', 'frutos secos'],
    ['chocolate', 'chocolates', 'savoy', 'carre', 'cri cri', 'cricri', 'galak', 'toronto', 'bombon', 'bombón', 'bombones', 'nutella', 'nucita', 'ovomalta'],
    ['dulce', 'dulces', 'caramelo', 'caramelos', 'chupeta', 'chupetas', 'gomitas', 'chicle', 'chicles', 'masmelos', 'marshmallows'],

    # --------------------------------------------------------------------------
    # 2. RESTAURANTES Y COMIDA PREPARADA
    # --------------------------------------------------------------------------
    ['arepa', 'arepas', 'arepa rellena', 'reina pepiada', 'pelua', 'sifrina', 'catira', 'dominó', 'domino', 'viuda'],
    ['empanada', 'empanadas', 'empanada de queso', 'empanada de carne', 'empanada de cazón', 'empanada de pabellon', 'empanada pabellón', 'pastelito', 'pastelitos', 'pastelito andino', 'mandoca', 'mandocas', ' papa rellena', 'yoyo', 'tequeyoyo'],
    ['cachapa', 'cachapas', 'cachapa con queso'],
    ['tequeño', 'tequeños', 'racion de tequeños', 'tequeños congelados', 'picada', 'bandeja de pasapalos'],
    ['hallaca', 'hallacas', 'hayaca', 'hayacas', 'bollo navideño', 'plato navideño'],
    ['perro caliente', 'perros calientes', 'hot dog', 'asquerosito'],
    ['hamburguesa', 'hamburguesas', 'burger', 'smash burger', 'cheeseburger'],
    ['pepito', 'pepitos', 'pepito mixto', 'pepito gratinado', 'granjero', 'patacon', 'patacón', 'tumbarancho'],
    ['pizza', 'pizzas', 'pizza familiar', 'pizza margarita', 'pizza pepperoni', 'calzone', 'focaccia', 'pasticho', 'ravioli', 'fetuccini'],
    ['pollo en brasa', 'pollo asado', 'pollo rostizado', 'pollo broaster', 'pollo frito', 'crispy chicken', 'tenders de pollo', 'nuggets', 'alitas bbq', 'buffalo wings'],
    ['parrilla', 'parrillada', 'parrilla mar y tierra', 'carne en vara', 'punta trasera asada', 'churrasco', 'costillas bbq'],
    ['almuerzo', 'menu ejecutivo', 'menú ejecutivo', 'menu del dia', 'comida corriente', 'comida casera', 'pabellon criollo', 'asado negro', 'pastelon de platano', 'polvorosa de pollo'],
    ['sopa', 'hervido', 'hervido de res', 'hervido de gallina', 'sancocho', 'cruzado', 'mondongo', 'pisca andina', 'fosforera', 'asopado', 'chupe', 'consome'],
    ['sushi', 'rolls', 'rollos de sushi', 'tempura', 'ceviche', 'poke bowl', 'ramen', 'gyozas', 'teriyaki'],
    ['comida china', 'arroz chino', 'arroz especial', 'lumpias', 'lumpia', 'chop suey', 'pollo agridulce', 'costillitas agridulces', 'mein', 'chow mein'],
    ['tacos', 'taco', 'burrito', 'burritos', 'quesadilla', 'nachos', 'fajitas', 'guacamole', 'comida mexicana'],
    ['shawarma', 'shawarmas', 'falafel', 'kibbe', 'kipe', 'tabule', 'hummus', 'crema de garbanzo', 'crema de berenjena', 'babaganoush', 'pan arabe', 'pan pita', 'comida arabe'],
    ['pescado frito', 'rueda de carite', 'pargo frito', 'vuelve a la vida', 'coctel de camarones', 'camarones al ajillo', 'paella marinera'],
    ['sandwich', 'sándwich', 'club house', 'clubhouse', 'panini', 'wrap', 'sub', 'ensalada cesar', 'ensalada saludable', 'bowl saludable'],
    ['chicha', 'chicha criolla', 'cocada', 'cepilla', 'cepillado', 'raspado', 'tizana', 'papelon con limon', 'guarapo de papelon'],
    ['helado', 'helados', 'barquilla', 'tinita', 'ice cream', 'paleta', 'helado artesanal', 'yogurt helado', 'merengada', 'milkshake', 'waffle', 'waffles', 'crepe', 'crepes'],
    ['torta', 'tortas', 'pastel', 'bizcocho', 'ponque', 'ponqué', 'tres leches', 'quesillo', 'marquesa', 'cheesecake', 'pie de limon', 'pie de parchita', 'brownie', 'profiteroles', 'milhojas', 'cupcake', 'dona', 'donas', 'doughnut', 'churro', 'churros', 'cannoli', 'galleta rellena'],

    # --------------------------------------------------------------------------
    # 3. TECNOLOGÍA Y ELECTRÓNICA
    # --------------------------------------------------------------------------
    ['telefono', 'teléfono', 'telefonos', 'teléfonos', 'celular', 'celulares', 'smartphone', 'movil', 'móvil', 'iphone', 'samsung galaxy', 'xiaomi', 'redmi', 'poco', 'infinix', 'tecno', 'motorola', 'honor', 'realme'],
    ['tablet', 'tablets', 'tableta', 'ipad', 'galaxy tab'],
    ['laptop', 'laptops', 'portatil', 'portátil', 'notebook', 'macbook', 'ultrabook', 'chromebook'],
    ['computadora', 'computadoras', 'pc', 'pc de escritorio', 'computador', 'ordenador', 'all in one', 'mini pc', 'pc gamer'],
    ['procesador', 'cpu', 'ryzen', 'intel core', 'tarjeta madre', 'motherboard', 'placa base', 'tarjeta de video', 'gpu', 'geforce', 'radeon', 'fuente de poder', 'psu', 'case', 'gabinete pc', 'cooler', 'disipador', 'pasta termica'],
    ['memoria ram', 'ram', 'ddr4', 'ddr5', 'dimm', 'sodimm'],
    ['disco solido', 'disco sólido', 'ssd', 'nvme', 'm.2', 'disco duro', 'hdd', 'disco externo', 'pendrive', 'pen drive', 'memoria usb', 'flash drive', 'micro sd', 'microsd', 'tarjeta sd', 'tarjeta de memoria'],
    ['monitor', 'monitores', 'pantalla de computadora', 'monitor gamer'],
    ['television', 'televisión', 'tv', 'televisor', 'televisores', 'smart tv', 'pantalla tv', 'tv box', 'fire tv', 'firestick', 'chromecast', 'roku', 'antena tv'],
    ['impresora', 'impresoras', 'multifuncional', 'escaner', 'escáner', 'tinta de impresora', 'ecotank', 'toner', 'tóner', 'cartucho de tinta'],
    ['smartwatch', 'smart watch', 'reloj inteligente', 'relojes inteligentes', 'banda inteligente', 'smartband', 'mi band', 'apple watch', 'amazfit', 'wearable'],
    ['camara', 'cámara', 'camaras', 'cámaras', 'camara fotografica', 'cámara fotográfica', 'camara digital', 'cámara digital', 'dslr', 'mirrorless', 'gopro', 'camara de accion', 'webcam', 'camara web', 'aro de luz', 'ring light', 'tripode', 'trípode', 'gimbal', 'estabilizador'],
    ['teclado', 'teclados', 'teclado mecanico', 'teclado inalambrico', 'teclado gamer'],
    ['mouse', 'raton', 'ratón', 'mouse inalambrico', 'mouse gamer', 'mousepad', 'alfombrilla', 'combo teclado y mouse'],
    ['router', 'routers', 'modem', 'módem', 'repetidor wifi', 'extensor wifi', 'amplificador wifi', 'sistema mesh', 'switch de red', 'tarjeta de red', 'adaptador wifi', 'cable ethernet', 'cable utp', 'cable de red', 'rj45', 'onu', 'ont', 'fibra optica', 'starlink'],
    ['consola', 'consolas', 'videojuego', 'videojuegos', 'playstation', 'ps4', 'ps5', 'xbox', 'nintendo switch', 'control de ps4', 'control de ps5', 'dualshock', 'dualsense', 'joystick', 'gamepad', 'mando', 'silla gamer'],
    ['cargador', 'cargadores', 'taco de cargador', 'cabezal de carga', 'cargador rapido', 'cargador rápido', 'cargador gan', 'cargador tipo c', 'cargador usb c', 'cargador iphone', 'cargador inalambrico', 'magsafe', 'cargador de laptop'],
    ['cable usb', 'cables usb', 'cable tipo c', 'cable usb-c', 'cable usb c', 'cable lightning', 'cable micro usb', 'cable hdmi', 'adaptador usb', 'hub usb', 'otg'],
    ['power bank', 'powerbank', 'powerbanks', 'bateria portatil', 'batería portátil', 'cargador portatil'],
    ['regulador', 'reguladores', 'regulador de voltaje', 'protector de voltaje', 'supresor de picos', 'ups', 'no break', 'mini ups', 'respaldo de energia', 'regleta', 'multitoma', 'extension electrica'],
    ['alexa', 'echo dot', 'echo show', 'google home', 'bombillo inteligente', 'enchufe inteligente', 'interruptor inteligente', 'domotica', 'smart home'],
    ['camara de seguridad', 'cámara de seguridad', 'camara de vigilancia', 'camara wifi', 'camara ip', 'cctv', 'dvr', 'nvr', 'kit de camaras', 'timbre inteligente', 'video portero'],
    ['proyector', 'proyectores', 'video beam', 'videobeam', 'pantalla de proyeccion'],
    ['audifonos', 'audífonos', 'audifono', 'auriculares', 'airpods', 'earbuds', 'tws', 'audifonos bluetooth', 'audifonos inalambricos', 'headset', 'diadema', 'manos libres', 'cascos'],
    ['corneta', 'cornetas', 'bocina', 'bocinas', 'parlante', 'parlantes', 'altavoz', 'corneta bluetooth', 'jbl', 'barra de sonido', 'soundbar', 'teatro en casa', 'home theater', 'karaoke'],
    ['forro', 'forros', 'funda de celular', 'case de telefono', 'protector de pantalla', 'vidrio templado', 'hidrogel', 'protector de camara', 'popsocket', 'soporte de celular', 'holder de carro'],

    # --------------------------------------------------------------------------
    # 4. ROPA, CALZADO Y ACCESORIOS
    # --------------------------------------------------------------------------
    ['blusa', 'blusas', 'top', 'tops', 'crop top', 'camisola', 'body de dama', 'corset', 'tunica'],
    ['franela', 'franelas', 'camiseta', 'camisetas', 't-shirt', 'tshirt', 'playera', 'polera', 'oversize'],
    ['franelilla', 'franelillas', 'camiseta sin mangas', 'tank top', 'almilla', 'musculosa'],
    ['chemise', 'chemises', 'camisa polo', 'polo'],
    ['camisa', 'camisas', 'camisa manga larga', 'camisa manga corta', 'camisa de vestir', 'camisa columbia', 'guayabera'],
    ['sueter', 'suéter', 'sueteres', 'hoodie', 'sudadera', 'buzo', 'chaqueta', 'chamarra', 'abrigo', 'blazer', 'saco', 'cardigan', 'chaleco', 'rompeviento', 'impermeable'],
    ['vestido', 'vestidos', 'vestido casual', 'vestido de fiesta', 'vestido largo', 'vestido corto', 'falda', 'faldas', 'minifalda', 'falda short', 'skort', 'enterizo', 'enterizos', 'jumpsuit', 'braga', 'overol', 'romper'],
    ['pantalon', 'pantalón', 'pantalones', 'jean', 'jeans', 'blue jean', 'bluejean', 'denim', 'vaquero', 'pantalon de vestir', 'pantalon cargo', 'jogger', 'joggers', 'palazzo'],
    ['legging', 'leggings', 'leggins', 'licra', 'licras', 'lycra', 'calza', 'biker', 'biker short'],
    ['short', 'shorts', 'bermuda', 'bermudas', 'pantalon corto'],
    ['mono', 'monos', 'mono deportivo', 'conjunto deportivo', 'sudadera deportiva', 'ropa deportiva', 'ropa de gym', 'conjunto fitness'],
    ['traje de baño', 'trajes de baño', 'bikini', 'trikini', 'bañador', 'enterizo de baño', 'short de playa', 'pareo', 'salida de playa', 'guardacamisa', 'rashguard'],
    ['ropa interior', 'ropa intima', 'ropa íntima', 'lenceria', 'lencería'],
    ['sosten', 'sostén', 'brasier', 'brassiere', 'bra', 'bralette', 'top deportivo'],
    ['pantaleta', 'pantaletas', 'panty', 'panties', 'cachetero', 'hilo', 'tanga', 'bikini intimo'],
    ['interior', 'interiores', 'boxer', 'bóxer', 'boxers', 'calzoncillo', 'calzoncillos'],
    ['pijama', 'pijamas', 'piyama', 'dormilona', 'bata de dormir', 'conjunto de dormir'],
    ['media', 'medias', 'calcetin', 'calcetines', 'calcetas', 'tobilleras', 'medias panty', 'medias escolares'],
    ['faja', 'fajas', 'faja reductora', 'faja postoperatoria', 'faja moldeadora'],
    ['uniforme escolar', 'chemise escolar', 'mono escolar', 'pantalon escolar'],
    ['zapato', 'zapatos', 'calzado'],
    ['zapato deportivo', 'zapatos deportivos', 'zapatos de goma', 'gomas', 'tenis', 'zapatilla', 'zapatillas', 'sneakers', 'zapatos de correr', 'running', 'botines deportivos'],
    ['chola', 'cholas', 'chancla', 'chanclas', 'sandalia', 'sandalias', 'flip flops', 'crocs', 'zuecos', 'babuchas', 'pantufla', 'pantuflas', 'pantuchas', 'alpargata', 'alpargatas'],
    ['tacon', 'tacón', 'tacones', 'zapatos de tacon', 'estiletos', 'stilettos', 'plataformas', 'sandalias de tacon', ' cuñas', 'toreritas', 'bailarinas', 'flats'],
    ['zapato casual', 'zapatos casuales', 'zapato formal', 'zapatos de vestir', 'mocasin', 'mocasines', 'náuticos', 'bota', 'botas', 'botin', 'botines', 'borcegui'],
    ['bolso', 'bolsos', 'cartera', 'carteras', 'bandolera', 'crossbody', 'tote bag', 'clutch', 'sobre de mano', 'koala', 'riñonera', 'cangurera', 'pechera bolso'],
    ['billetera', 'billeteras', 'monedero', 'monederos', 'tarjetero', 'porta tarjetas', 'portatarjetas', 'porta pasaporte', 'portapasaporte'],
    ['joya', 'joyas', 'joyeria', 'joyería', 'bisuteria', 'bisutería', 'acero inoxidable', 'oro laminado', 'plata 925'],
    ['zarcillo', 'zarcillos', 'arete', 'aretes', 'pendiente', 'pendientes', 'topitos', 'argollas', 'candongas', 'piercing'],
    ['collar', 'collares', 'cadena', 'cadenas', 'gargantilla', 'choker', 'dije', 'dijes', 'medalla', 'rosario'],
    ['pulsera', 'pulseras', 'brazalete', 'manilla', 'esclava', 'tobillera'],
    ['anillo', 'anillos', 'sortija', 'alianza', 'anillo de compromiso', 'aro de matrimonio'],
    ['lente', 'lentes', 'gafas', 'anteojos', 'lentes de sol', 'gafas de sol', 'montura', 'monturas', 'lentes de lectura', 'lentes filtro azul'],
    ['reloj', 'relojes', 'reloj de pulsera', 'reloj casio', 'reloj analogico', 'reloj digital', 'cronografo'],
    ['gorra', 'gorras', 'cachucha', 'visera', 'sombrero', 'sombreros', 'gorro', 'beanie', 'pescador', 'bucket hat', 'bufanda', 'pañoleta', 'bandana', 'corbata', 'corbatín', 'pajarita'],
    ['correa', 'correas', 'cinturon', 'cinturón', 'cinturones', 'hebilla', 'tirantes'],
    ['maleta', 'maletas', 'valija', 'equipaje', 'carry on', 'carry-on', 'maleta de mano', 'maleta de bodega', 'bolso de viaje', 'duffel bag', 'organizadores de maleta'],

    # --------------------------------------------------------------------------
    # 5. SALUD Y BELLEZA
    # --------------------------------------------------------------------------
    ['shampoo', 'champu', 'champú', 'acondicionador', 'enjuague', 'crema para peinar', 'crema de peinar', 'baño de crema', 'mascarilla capilar', 'tratamiento capilar', 'ampolla capilar', 'gotas de brillo', 'protector termico', 'keratina', 'cirugia capilar', 'botox capilar', 'gel fijador', 'gelatina para el cabello', 'cera para el cabello', 'laca', 'mousse'],
    ['tinte', 'tintes', 'tinte de cabello', 'tinte para el pelo', 'coloracion', 'decolorante', 'peroxido', 'agua oxigenada capilar', 'matizador'],
    ['secador', 'secadores', 'secador de cabello', 'secador de pelo', 'cepillo secador', 'plancha de cabello', 'plancha de pelo', 'babyliss', 'rizador', 'tenaza de cabello', 'ondulador', 'difusor'],
    ['cepillo de cabello', 'cepillo para el pelo', 'peine', 'peineta', 'desenredante', 'cola de cabello', 'scrunchie', 'gancho de cabello', 'pinza de cabello', 'cintillo', 'diadema'],
    ['skincare', 'cuidado facial', 'limpiador facial', 'jabon facial', 'espuma limpiadora', 'agua micelar', 'desmaquillante', 'tonico facial', 'tónico facial'],
    ['serum', 'sérum', 'suero facial', 'acido hialuronico', 'ácido hialurónico', 'niacinamida', 'retinol', 'vitamina c facial', 'acido glicolico', 'acido salicilico'],
    ['crema facial', 'crema hidratante', 'crema humectante', 'gel hidratante', 'contorno de ojos', 'parches de ojos', 'mascarilla facial', 'sheet mask', 'exfoliante', 'scrub', 'agua de rosas'],
    ['protector solar', 'bloqueador', 'bloqueador solar', 'pantalla solar', 'bronceador', 'after sun'],
    ['maquillaje', 'cosméticos', 'cosmeticos', 'base de maquillaje', 'foundation', 'bb cream', 'cc cream', 'corrector', 'corrector de ojeras', 'concealer', 'primer', 'prebase'],
    ['polvo compacto', 'polvo suelto', 'polvo traslucido', 'rubor', 'blush', 'colorete', 'bronzer', 'contorno', 'iluminador', 'highlighter', 'fijador de maquillaje', 'setting spray'],
    ['rimel', 'rímel', 'mascara de pestañas', 'máscara de pestañas', 'pestañina', 'encrespador', 'rizador de pestañas', 'pestañas postizas', 'pestañas por punto', 'pega de pestañas'],
    ['delineador', 'delineadores', 'eyeliner', 'plumon delineador', 'lapiz de ojos', 'sombra de ojos', 'sombras', 'paleta de sombras', 'lapiz de cejas', 'pomada de cejas', 'gel de cejas', 'jabon de cejas'],
    ['labial', 'labiales', 'pintalabios', 'pinta labios', 'lipstick', 'brillo labial', 'lip gloss', 'gloss', 'tinta de labios', 'lip tint', 'delineador de labios', 'balsamo labial', 'hidratante de labios', 'chapstick', 'manteca de cacao'],
    ['brocha de maquillaje', 'brochas de maquillaje', 'set de brochas', 'esponja de maquillaje', 'beauty blender', 'borla', 'cosmetiquera', 'portacosmeticos', 'porta cosmeticos', 'neceser'],
    ['perfume', 'perfumes', 'fragancia', 'fragancias', 'colonia', 'agua de colonia', 'eau de parfum', 'edp', 'eau de toilette', 'edt', 'splash', 'body splash', 'body mist', 'decant', 'crema perfumada', 'locion corporal', 'crema corporal'],
    ['pintauñas', 'pinta uñas', 'pintaunas', 'esmalte', 'esmalte de uñas', 'esmalte semipermanente', 'gelish', 'base coat', 'top coat', 'brillo de uñas'],
    ['quitaesmalte', 'quita esmalte', 'acetona', 'removedor de esmalte'],
    ['cortauñas', 'corta uñas', 'cortaunas', 'corta una', 'cortacuticula', 'corta cuticula', 'alicate de uñas', 'empujador de cuticula', 'lima de uñas', 'lima', 'bloque pulidor', 'uñas postizas', 'tips de uñas', 'acrilico para uñas', 'monomero', 'poligel', 'lampara uv', 'lampara led uñas', 'torno de uñas', 'dremel de uñas'],
    ['desodorante', 'desodorantes', 'antitranspirante', 'roll on', 'roll-on', 'desodorante en barra', 'desodorante en spray', 'desodorante en crema', 'piedra de alumbre'],
    ['afeitadora', 'afeitadoras', 'rasuradora', 'prestobarba', 'gillette', 'maquina de afeitar', 'maquina de cortar cabello', 'clipper', 'patillera', 'trimmer', 'hojilla', 'hojillas', 'espuma de afeitar', 'gel de afeitar', 'after shave', 'cera depilatoria', 'crema depilatoria', 'pinza de cejas'],
    ['cepillo de dientes', 'cepillo dental', 'cepillos dentales', 'crema dental', 'pasta de dientes', 'pasta dental', 'colgate', 'enjuague bucal', 'listerine', 'hilo dental', 'seda dental'],
    ['jabon', 'jabón', 'jabones', 'jabon de baño', 'jabon de tocador', 'jabon liquido', 'gel de ducha', 'body wash', 'jabon intimo', 'jabon antibacterial', 'jabon de glicerina', 'jabon de avena', 'jabon azul', 'panela de jabon', 'esponja de baño', 'estropajo', 'talco', 'talco para pies', 'hisopo', 'hisopos', 'cotonetes'],
    ['toallas sanitarias', 'toalla sanitaria', 'toallas higienicas', 'kotex', 'always', 'nosotras', 'protectores diarios', 'protector diario', 'salvadiario', 'tampon', 'tampones', 'copa menstrual'],
    ['acetaminofen', 'acetaminofén', 'paracetamol', 'analgesico', 'analgésico', 'atamel', 'tachipirin', 'ibuprofeno', 'diclofenac', 'ketoprofeno', 'naproxeno', 'aspirina', 'migren', 'dol'],
    ['jarabe', 'jarabe para la tos', 'antigripal', 'antigripales', 'teragrip', 'alivet', 'sinutab', 'loratadina', 'cetirizina', 'desloratadina', 'antialergico', 'antihistaminico', 'descongestionante', 'spray nasal'],
    ['omeprazol', 'antiacido', 'antiácido', 'sal de fruta', 'pepto bismol', 'maalox', 'buscapina', 'antiespasmodico', 'suero oral', 'pedialyte', 'enterogermina', 'probioticos', 'loperamida', 'antidiarreico', 'laxante'],
    ['alcohol', 'alcohol isopropilico', 'alcohol isopropílico', 'alcohol antiseptico', 'gel antibacterial', 'agua oxigenada', 'povidine', 'yodo', 'merthiolate', 'gerdex'],
    ['curita', 'curitas', 'tirita', 'banda adhesiva', 'banditas', 'gasa', 'gasas', 'venda', 'vendas', 'venda elastica', 'adhesivo medico', 'esparadrapo', 'micropore', 'algodon', 'algodón', 'jeringa', 'inyectadora', 'guantes de latex', 'botiquin', 'primeros auxilios'],
    ['tapabocas', 'tapa bocas', 'mascarilla', 'mascarillas', 'kn95'],
    ['vitamina', 'vitaminas', 'vitamina c', 'vitamina d', 'vitamina e', 'complejo b', 'multivitaminico', 'multivitamínico', 'centrum', 'omega 3', 'aceite de pescado', 'magnesio', 'citrato de magnesio', 'cloruro de magnesio', 'colageno', 'colágeno', 'colageno hidrolizado', 'biotina', 'melatonina', 'zinc', 'calcio', 'hierro', 'acido folico'],
    ['preservativo', 'preservativos', 'condon', 'condón', 'condones', 'durex', 'lubricante intimo', 'prueba de embarazo', 'test de embarazo'],
    ['tensiometro', 'tensiómetro', 'baumanometro', 'monitor de presion', 'glucometro', 'glucómetro', 'tiras reactivas', 'lancetas', 'oximetro', 'oxímetro', 'pulsioximetro', 'termometro', 'termómetro', 'nebulizador', 'inhalador', 'silla de ruedas', 'muleta', 'muletas', 'baston', 'bastón', 'andadera', 'collarin cervical', 'rodillera', 'tobillera ortopedica', 'muñequera', 'faja lumbar', 'medias de compresion'],

    # --------------------------------------------------------------------------
    # 6. HOGAR, MUEBLES, COCINA, BAÑO, LIMPIEZA Y JARDÍN
    # --------------------------------------------------------------------------
    # Utensilios de cocina y palabras compuestas
    ['abrelatas', 'abre latas', 'abre lata', 'abrelata', 'destapador de latas'],
    ['sacacorchos', 'saca corchos', 'sacacorcho', 'descorchador', 'destapador', 'abrebotellas', 'abre botellas'],
    ['pelapapas', 'pela papas', 'pelador de papas', 'pelador', 'mondador'],
    ['prensajo', 'prensa ajo', 'prensa ajos', 'machacador de ajo', 'triturador de ajo', 'exprimidor de ajo'],
    ['exprimidor', 'exprimidor de limones', 'exprimelimones', 'exprime limones', 'exprimidor de citricos', 'juguera'],
    ['rallador', 'ralladores', 'ralla queso', 'rallaqueso', 'rallador de queso', 'mandolina'],
    ['colador', 'coladores', 'cedazo', 'tamiz', 'cernidor', 'escurridor', 'escurrepastas', 'escurre pastas'],
    ['escurreplatos', 'escurre platos', 'escurridor de platos', 'secaplatos', 'seca platos', 'platera'],
    ['tabla de picar', 'tabla para picar', 'tabla de cortar', 'tabla de cocina'],
    ['rodillo', 'rodillo de cocina', 'rodillo de amasar', 'palote'],
    ['batidor', 'batidor de mano', 'batidor de globo', 'bate huevos', 'batehuevos'],
    ['espatula', 'espátula', 'espatulas', 'paleta de cocina', 'volteador', 'miserable', 'lengua pastelera', 'brocha de silicona'],
    ['cucharon', 'cucharón', 'cuchara de servir', 'espumadera', 'servidor de pasta'],
    ['pinza de cocina', 'pinzas de cocina', 'tenaza de cocina', 'pinza para carne', 'pinza para hielo'],
    ['tijera de cocina', 'tijeras de cocina', 'cortapizza', 'corta pizza', 'cortador de pizza', 'cascanueces', 'casca nueces'],
    ['mortero', 'pilon', 'pilón', 'machacador', 'pisapapas', 'pisa papas', 'puretera'],
    ['embudo', 'embudos', 'taza medidora', 'jarra medidora', 'cucharas medidoras', 'peso de cocina', 'balanza de cocina', 'gramera'],
    ['envase', 'envases', 'tupper', 'tupperware', 'portacomida', 'porta comida', 'vianda', 'fiambrera', 'contenedor hermetico', 'recipiente de vidrio', 'pote de cocina', 'especiero', 'aceitera', 'salero', 'azucarera'],
    ['olla', 'ollas', 'caldero', 'calderos', 'cacerola', 'cacerolas', 'bateria de cocina', 'juego de ollas'],
    ['olla de presion', 'olla de presión', 'olla a presion', 'olla express', 'olla magefesa'],
    ['sarten', 'sartén', 'sartenes', 'paila', 'wok', 'plancha de cocina', 'sarten antiadherente'],
    ['budare', 'budares', 'aripo', 'plancha para arepas', 'tosty arepa', 'tostiarepa', 'tostyarepa'],
    ['tortera', 'molde para torta', 'molde de hornear', 'bandeja para hornear', 'molde de silicona', 'refractario', 'pirex', 'pyrex', 'quesillera'],
    ['cubiertos', 'juego de cubiertos', 'cubierteria', 'tenedor', 'tenedores', 'cuchara', 'cucharas', 'cucharilla', 'cucharillas', 'cuchillo de mesa'],
    ['cuchillo', 'cuchillos', 'set de cuchillos', 'cuchillo de chef', 'cuchillo carnicero', 'hacha de cocina', 'chaira', 'afilador de cuchillos'],
    ['vajilla', 'vajillas', 'juego de vajilla', 'plato', 'platos', 'plato llano', 'plato hondo', 'taza', 'tazas', 'pocillo', 'mug', 'escudilla', 'bowl', 'tazon', 'tazón'],
    ['vaso', 'vasos', 'juego de vasos', 'copa', 'copas', 'jarra', 'jarra de vidrio', 'jarra plastica'],
    ['portavasos', 'porta vasos', 'posavasos', 'posa vasos', 'individuales de mesa', 'mantel', 'manteles', 'portaservilletas', 'servilletero'],

    # Electrodomésticos y Línea Blanca
    ['nevera', 'neveras', 'refrigerador', 'heladera', 'ejecutivo', 'congelador', 'freezer', 'frezzer', 'perco', 'fabricador de hielo', 'vinera'],
    ['lavadora', 'lavadoras', 'lavarropas', 'secadora', 'secadora de ropa', 'centro de lavado', 'lavaplatos electrico', 'lavavajillas'],
    ['cocina a gas', 'cocina electrica', 'tope de cocina', 'encimera', 'hornilla', 'hornilla electrica', 'reverbero', 'cocinilla', 'campana de cocina', 'extractor de grasa'],
    ['microondas', 'micro ondas', 'horno microondas', 'horno electrico', 'horno tostador'],
    ['freidora de aire', 'air fryer', 'airfryer', 'freidora sin aceite', 'freidora'],
    ['licuadora', 'licuadoras', 'vaso de licuadora', 'cuchilla de licuadora', 'procesador de alimentos', 'picatodo', 'pica todo', 'licuadora de inmersion', 'mixer'],
    ['batidora', 'batidoras', 'batidora de mano', 'batidora de pedestal', 'kitchenaid', 'amasadora'],
    ['cafetera', 'cafeteras', 'greca', 'cafetera italiana', 'moka', 'prensa francesa', 'cafetera expreso', 'tetera', 'hervidor electrico', 'kettle'],
    ['sanduchera', 'sandwichera', 'tostadora', 'waflera', 'wafflera', 'panini grill', 'parrillera electrica', 'arrocera', 'olla arrocera', 'olla multifuncional', 'instant pot', 'vaporera', 'cotufera'],
    ['dispensador de agua', 'enfriador de agua', 'filtro de agua', 'purificador de agua', 'bujia de filtro', 'ozonizador'],
    ['plancha de ropa', 'plancha a vapor', 'plancha seca', 'vaporizador de ropa', 'mesa de planchar', 'burro de planchar'],
    ['aspiradora', 'aspiradoras', 'aspirador', 'aspiradora de carro', 'robot aspirador', 'pulidora de piso'],
    ['aire acondicionado', 'aires acondicionados', 'split', 'aire de ventana', 'aire portatil', 'cortina de aire'],
    ['ventilador', 'ventiladores', 'abanico', 'ventilador de pedestal', 'ventilador de piso', 'ventilador de pared', 'ventilador de techo', 'ventilador recargable', 'mini ventilador', 'enfriador evaporativo'],
    ['planta electrica', 'planta eléctrica', 'plantas electricas', 'generador electrico', 'generador a gasolina', 'inversor de corriente', 'estacion de energia', 'ecoflow', 'panel solar'],
    ['calentador de agua', 'termohedor', 'calentador a gas', 'calentador electrico', 'ducha corona'],

    # Muebles, Dormitorio, Baño, Decoración, Limpieza y Jardín
    ['sillon', 'sillón', 'sofa', 'sofá', 'sofas', 'sofa cama', 'sofá cama', 'juego de recibo', 'mueble de sala', 'seccional', 'poltrona', 'reclinable', 'butaca', 'puff', 'otomana'],
    ['mesa de comedor', 'juego de comedor', 'silla de comedor', 'sillas de comedor', 'mesa de centro', 'mesa lateral', 'mesa de noche', 'nochero', 'barra desayunador', 'banqueta', 'taburete', 'banco'],
    ['cama', 'camas', 'box spring', 'base de cama', 'copete', 'cabecero', 'litera', 'camarote', 'cama individual', 'cama matrimonial', 'cama queen', 'cama king', 'cama duplex'],
    ['colchon', 'colchón', 'colchones', 'colchon ortopedico', 'colchon individual', 'colchon matrimonial', 'colchon queen', 'colchon king', 'colchoneta', 'topper'],
    ['sabana', 'sábana', 'sabanas', 'sábanas', 'juego de sabanas', 'juego de sábanas', 'sabana esquinera', 'funda de almohada'],
    ['edredon', 'edredón', 'edredones', 'cubrecama', 'cubre cama', 'cubrelecho', 'cubre lecho', 'duvet', 'plumon', 'cobija', 'cobijas', 'manta', 'frazada', 'sobrecama', 'sobre cama'],
    ['almohada', 'almohadas', 'cojin', 'cojín', 'cojines', 'almohada viscoelastica', 'memory foam'],
    ['protector de colchon', 'cubrecolchon', 'cubre colchon', 'forro de colchon'],
    ['toalla', 'toallas', 'toalla de baño', 'toalla de mano', 'toalla facial', 'paño de baño', 'bata de baño', 'salida de baño'],
    ['gavetero', 'comoda', 'cómoda', 'peinadora', 'tocador', 'closet', 'clóset', 'armario', 'ropero', 'zapatera', 'organizador de zapatos', 'perchero'],
    ['repisa', 'repisas', 'estante', 'estantes', 'estanteria', 'estantería', 'biblioteca', 'mueble de tv', 'centro de entretenimiento'],
    ['poceta', 'pocetas', 'inodoro', 'sanitario', 'wc', 'one piece', 'tapa de poceta', 'asiento de sanitario', 'herraje de poceta', 'sapito', 'valvula de descarga'],
    ['lavamanos', 'lavabo', 'mueble de baño', 'gabinete de baño', 'botiquin de baño', 'espejo de baño'],
    ['regadera', 'ducha', 'cabezal de ducha', 'ducha telefono', 'griferia', 'grifería', 'llave de lavamanos', 'llave de fregadero', 'monomando', 'mezcladora', 'canilla', 'fregadero', 'batea', 'sifon', 'sifón', 'desague', 'desagüe', 'rejilla de piso', 'centro de piso'],
    ['accesorios de baño', 'cortina de baño', 'alfombra de baño', 'portarollo', 'porta rollo', 'porta papel', 'jabonera', 'dispensador de jabon', 'porta cepillos', 'toallero', 'cepillo de poceta', 'chupo', 'destapador de cañeria'],
    ['espejo', 'espejos', 'espejo cuerpo entero', 'espejo redondo', 'espejo led', 'cuadro', 'cuadros', 'portarretrato', 'porta retrato', 'marco de fotos', 'reloj de pared', 'jarron', 'jarrón', 'florero', 'planta artificial', 'flores artificiales', 'vela aromatica', 'incienso', 'difusor de aromas', 'humidificador'],
    ['cortina', 'cortinas', 'blackout', 'persiana', 'persianas', 'estor', 'tubo de cortina', 'cortinero'],
    ['alfombra', 'alfombras', 'tapete', 'felpudo', 'grama artificial', 'cesped artificial', 'piso vinilico', 'papel tapiz'],
    ['lampara', 'lámpara', 'lamparas', 'lampara de mesa', 'lampara de pie', 'lampara de techo', 'plafon', 'araña de techo'],
    ['detergente', 'jabon en polvo', 'jabón en polvo', 'ace', 'ariel', 'las llaves', 'jabon liquido para ropa', 'suavizante', 'suavitel', 'downy', 'quitamanchas', 'quita manchas', 'vanish', 'jabon en panela', 'jabon las llaves'],
    ['cloro', 'lavandina', 'hipoclorito', 'lejia', 'desinfectante', 'limpiador de pisos', 'mistolin', 'fabuloso', 'pinosol', 'cera para piso', 'acido muriatico'],
    ['lavaplatos', 'lava platos', 'jabon lavaplatos', 'crema lavaplatos', 'axion', 'las llaves lavaplatos', 'lavavajillas liquido'],
    ['desengrasante', 'arrancagrasa', 'arranca grasa', 'limpia hornos', 'limpiavidrios', 'limpia vidrios', 'limpia metales', 'lustramuebles'],
    ['papel toilet', 'papel higienico', 'papel higiénico', 'papel tuale', 'rollo de papel'],
    ['toallin', 'toallín', 'toallas de cocina', 'papel absorbente', 'servilleta', 'servilletas'],
    ['bolsa de basura', 'bolsas de basura', 'bolsas negras', 'papelera', 'pote de basura', 'basurero', 'cesto de basura', 'pipote', 'contenedor de basura'],
    ['coleto', 'mopa', 'trapeador', 'lampazo', 'palo de coleto', 'haragan', 'haragán', 'escurridor de piso', 'cepillo de barrer', 'escoba', 'escobillon', 'pala de basura', 'recogedor', 'chupachupa'],
    ['tobo', 'balde', 'cubeta', 'tobo exprimidor', 'ponchera', 'guantes de limpieza', 'guantes de goma'],
    ['esponja', 'esponja de fregar', 'esponja doble uso', 'brillo', 'brillo de alambre', 'esponjilla', 'bombril', 'pañito', 'paño amarillo', 'paño de microfibra', 'microfibra', 'plumero'],
    ['cesta de ropa', 'canasto de ropa', 'tendedero', 'gancho de ropa', 'ganchos de ropa', 'percha', 'perchas', 'colgador', 'pinzas de ropa'],
    ['insecticida', 'mata plagas', 'mataplagas', 'mata moscas', 'matamoscas', 'mata cucarachas', 'mata zancudos', 'baygon', 'raid', 'plaquitas', 'espirales', 'raqueta mata plagas', 'veneno para ratas', 'raticida', 'repelente', 'off'],
    ['ambientador', 'aromatizante', 'glade', 'air wick'],
    ['manguera', 'manguera de jardin', 'pico de manguera', 'pistola de riego', 'aspersor', 'regadera de jardin'],
    ['matero', 'materos', 'maceta', 'macetas', 'porron', 'porrón', 'jardinera', 'tierra abonada', 'abono', 'fertilizante', 'humus', 'semillas', 'grama', 'pala de jardin', 'tijera de podar', 'cortagrama', 'desmalezadora', 'guaraña', 'silla plastica', 'mesa plastica', 'toldo', 'gazebo', 'hamaca', 'chinchorro', 'parrillera', 'asador', 'carbon', 'carbón'],

    # --------------------------------------------------------------------------
    # 7. FERRETERÍA Y CONSTRUCCIÓN
    # --------------------------------------------------------------------------
    ['martillo', 'martillos', 'mandarria', 'mazo', 'mazo de goma', 'pata de cabra'],
    ['destornillador', 'destornilladores', 'desarmador', 'juego de destornilladores', 'destornillador de estria', 'destornillador phillips', 'destornillador plano', 'buscapolo', 'busca polo'],
    ['alicate', 'alicates', 'pinza', 'pinzas', 'pinza de presion', 'hombre solo', 'hombresolo', 'tenaza', 'pica cable', 'cortafrio', 'pelacables', 'pela cables', 'ponchadora', 'pinza amperimetrica'],
    ['llave ajustable', 'llave inglesa', 'llave francesa', 'llave de tubo', 'llave stilson', 'llaves combinadas', 'juego de llaves', 'juego de dados', 'autocle', 'rache', 'ratchet', 'llave allen', 'llave torx'],
    ['cinta metrica', 'cinta métrica', 'metro', 'flexometro', 'flexómetro', 'nivel', 'nivel de burbuja', 'nivel laser', 'escuadra', 'plomada'],
    ['exacto', 'cuter', 'cutter', 'bisturi', 'navaja', 'navaja multiuso', 'hojas de exacto'],
    ['segueta', 'arco de segueta', 'hoja de segueta', 'serrucho', 'sierra manual', 'formon', 'cincel', 'lima metalica', 'prensa sargento', 'prensa de banco'],
    ['llana', 'palustra', 'cuchara de albañil', 'espatula de albañil', 'nivelador de ceramica'],
    ['taladro', 'taladros', 'taladro percutor', 'taladro inalambrico', 'rotomartillo', 'demoledor', 'atornillador electrico', 'mecha', 'mechas', 'broca', 'brocas', 'juego de mechas'],
    ['esmeril', 'esmeriles', 'esmeriladora', 'amoladora', 'pulidora', 'disco de corte', 'disco de desbaste', 'disco diamantado', 'disco flap'],
    ['sierra circular', 'sierra caladora', 'caladora', 'sierra ingletadora', 'tronzadora', 'lijadora', 'cepillo electrico', 'trompo', 'router para madera', 'mototool', 'dremel'],
    ['soldador', 'maquina de soldar', 'inversor de soldadura', 'electrodo', 'electrodos', 'careta de soldar', 'cautin', 'cautín', 'estaño', 'pasta para soldar', 'pistola de calor'],
    ['compresor', 'compresor de aire', 'hidrolavadora', 'hidrojet', 'pistola de pintar', 'soplador', 'motosierra'],
    ['breaker', 'breakers', 'interruptor termomagnetico', 'pastilla electrica', 'tablero electrico', 'caja de breakers', 'contactor', 'rele termico'],
    ['tomacorriente', 'toma corriente', 'tomacorrientes', 'enchufe', 'clavija', 'interruptor', 'apagador', 'suiche', 'switch', 'conmutador', 'dimmer', 'socate', 'zócalo', 'portalampara', 'portalámparas', 'roseta'],
    ['cable electrico', 'cables electricos', 'alambre electrico', 'cable thhn', 'cable tw', 'cable st', 'cable SPT', 'cable automotriz', 'canaleta', 'tubo conduit', 'cajetin', 'cajetín', 'abrazadera', 'tirrap', 'tie wrap', 'precinto', 'amarres plasticos', 'bornera', 'regleta de conexion'],
    ['cinta aislante', 'teipe', 'teipe negro', 'tape electrico', 'termocontraible'],
    ['tester', 'multimetro', 'multímetro', 'probador de corriente'],
    ['bombillo', 'bombillos', 'bombilla', 'foco', 'bombillo led', 'bombillo recargable', 'reflector', 'reflectores', 'reflector led', 'panel led', 'ojo de buey', 'lampara led', 'tubo led', 'cinta led', 'tira led', 'fotocelda', 'linterna', 'linternas', 'lampara de emergencia'],
    ['tubo pvc', 'tubos pvc', 'tuberia pvc', 'tubo aguas blancas', 'tubo aguas negras', 'tubo pavco', 'tubo termofusion', 'codo pvc', 'tee pvc', 'anillo pvc', 'union universal', 'adaptador macho', 'adaptador hembra', 'reduccion pvc', 'tapon pvc', 'pega pvc', 'soldadura pvc', 'limpiador pvc'],
    ['llave de paso', 'valvula de bola', 'llave de arresto', 'llave de chorro', 'grifo', 'canilla', 'manguera flexible', 'canilla lavamanos', 'teflon', 'teflón', 'cinta teflon'],
    ['tanque de agua', 'tanque cilindrico', 'tanque conico', 'bomba de agua', 'bomba periferica', 'bomba centrifuga', 'bomba sumergible', 'hidroneumatico', 'hidroneumático', 'presostato', 'manometro', 'manómetro', 'valvula check', 'valvula de pie', 'flotante', 'flotante electrico', 'flotante mecanico'],
    ['pintura', 'pinturas', 'cuñete', 'cuñete de pintura', 'galon de pintura', 'cuarto de pintura', 'pintura de caucho', 'esmalte sintetico', 'anticorrosivo', 'fondo anticorrosivo', 'fondo herreria', 'pintura en spray', 'aerosol', 'barniz', 'sellador de madera', 'impermeabilizante', 'manto asfaltico', 'pintura para trafico'],
    ['brocha', 'brochas', 'rodillo de pintar', 'funda de rodillo', 'bandeja de pintar', 'extension de rodillo', 'lija', 'papel de lija', 'thinner', 'varsol', 'solvente', 'removedor de pintura', 'tirro', 'cinta de enmascarar'],
    ['silicon', 'silicón', 'silicona', 'sellador', 'sikaflex', 'pistola de silicon', 'pistola de calafateo', 'mastique', 'masilla', 'pasta profesional', 'encamisado', 'estuco', 'pega loca', 'super glue', 'pega epoxica', 'soldadura en frio', 'pega amarilla', 'cemento de contacto'],
    ['cemento', 'saco de cemento', 'cemento gris', 'cemento blanco', 'pego', 'pego gris', 'pego blanco', 'porcelana', 'carateo', 'cal', 'yeso', 'arena', 'piedra picada', 'bloque', 'bloques', 'ladrillo', 'cabilla', 'cabillas', 'malla trucson', 'malla electrosoldada', 'alambre dulce', 'alambre de puas', 'malla ciclon', 'lamina de acerolit', 'lamina de zinc', 'drywall', 'tabla yeso'],
    ['tornillo', 'tornillos', 'tirafondo', 'autoperforante', 'drywall screw', 'chazo', 'chazos', 'ramplug', 'tarugo', 'clavo', 'clavos', 'clavo de acero', 'tuerca', 'tuercas', 'arandela', 'arandelas', 'perno', 'esparrago', 'remache', 'remaches', 'remachadora', 'alcayata', 'cancamo', 'bisagra', 'bisagras', 'corredera', 'corredera telescopica', 'rueda giratoria', 'rodachina'],
    ['cerradura', 'cerraduras', 'cerradura de pomo', 'cerradura de sobreponer', 'cerradura embutida', 'candado', 'candados', 'cilindro', 'cilindro de seguridad', 'pasador', 'cerrojo', 'aldaba', 'manilla de puerta', 'cierra puerta', 'cadena', 'guaya'],
    ['botas de seguridad', 'botas punta de hierro', 'botas industriales', 'botas dielectricas', 'botas de caucho', 'botas machita', 'casco de seguridad', 'lentes de seguridad', 'gafas de proteccion', 'guantes de seguridad', 'guantes de carnaza', 'guantes de puntos', 'guantes de nitrilo', 'chaleco reflectivo', 'arnes de seguridad', 'eslinga', 'mascarilla con filtro', 'respirador', 'protector auditivo', 'tapa oidos', 'cono de seguridad', 'cinta de peligro', 'escalera', 'escalera de aluminio', 'carretilla', 'carrucha'],

    # --------------------------------------------------------------------------
    # 8. CARROS, MOTOS Y REPUESTOS AUTOMOTRICES
    # --------------------------------------------------------------------------
    ['carro', 'carros', 'auto', 'automovil', 'vehiculo', 'sedan', 'hatchback', 'camioneta', 'pickup', 'pick up', 'rustico', '4x4', 'suv', 'camion'],
    ['moto', 'motos', 'motocicleta', 'scooter', 'pasola', 'bera', 'sbr', 'empire', 'keeway', 'horse', 'owen', 'tx', 'kavak', 'enduro', 'cuatrimoto'],
    ['caucho', 'cauchos', 'neumatico', 'neumático', 'neumaticos', 'llanta', 'llantas', 'rin', 'rines', 'tripa de caucho', 'valvula de caucho', 'parche de caucho', 'inflador de cauchos', 'compresor 12v', 'medidor de presion'],
    ['aceite de motor', 'aceite 20w50', 'aceite 15w40', 'aceite 10w30', 'aceite 10w40', 'aceite 5w30', 'aceite 5w20', 'aceite mineral', 'aceite semisintetico', 'aceite sintetico', 'lubricante', 'lubricante de motor', 'aceite 2 tiempos', 'aceite 4 tiempos'],
    ['refrigerante', 'coolant', 'anticongelante', 'agua para radiador', 'agua desmineralizada', 'agua para bateria'],
    ['liga de freno', 'liquido de freno', 'dot 3', 'dot 4', 'aceite hidraulico', 'aceite de direccion', 'aceite de caja', 'valvulina', 'atf', ' dexron', 'aditivo', 'limpia inyectores', 'octanaje'],
    ['filtro de aceite', 'filtro de aire', 'filtro de gasolina', 'filtro de combustible', 'filtro de aire acondicionado', 'filtro de cabina'],
    ['bujia', 'bujías', 'bujias', 'cables de bujia', 'bobina', 'bobina de encendido', 'inyector', 'inyectores', 'microfiltros', 'pila de gasolina', 'bomba de gasolina', 'flauta de inyectores', 'cuerpo de aceleracion', 'sensor tps', 'sensor map', 'sensor maf', 'sensor de oxigeno', 'valvula iac', 'valvula pcv'],
    ['correa de tiempo', 'kit de tiempo', 'cadena de tiempo', 'correa unica', 'correa de alternador', 'tensor', 'polea', 'bomba de agua automotriz', 'termostato', 'toma de agua', 'estopera', 'empacadura', 'empacadura de camara', 'empacadura de tapa valvula', 'anillos de motor', 'pistones', 'conchas de biela', 'conchas de bancada', 'base de motor', 'base de caja'],
    ['amortiguador', 'amortiguadores', 'espiral', 'ballesta', 'meseta', 'rotula', 'rótula', 'terminal de direccion', 'axial', 'muñon', 'barra estabilizadora', 'lapiz de barra', 'buje', 'bujes', 'goma de barra', 'tripoide', 'punta de tripoide', 'copa caja', 'guardapolvo de tripoide', 'rolinera', 'rodamiento', 'mozo de rueda', 'cubo de rueda', 'cajetin de direccion', 'bomba de direccion', 'cremallera'],
    ['pastilla de freno', 'pastillas de freno', 'disco de freno', 'discos de freno', 'bandas de freno', 'zapata de freno', 'tambor de freno', 'bomba de freno', 'cilindro de rueda', 'hidrovac', 'guaya de freno'],
    ['croche', 'embrague', 'kit de croche', 'disco de croche', 'plato de presion', 'collarin', 'bomba de croche', 'bombín de croche', 'guaya de croche'],
    ['bateria de carro', 'batería de carro', 'bateria automotriz', 'acumulador', 'bateria duncan', 'bateria fulgor', 'bateria titan', 'bornes de bateria', 'cables auxiliares', 'cables de corriente', 'cargador de bateria', 'arrancador portatil'],
    ['alternador', 'arranque', 'motor de arranque', 'bendix', 'carbonera', 'regulador de alternador', 'radiador', 'tapa de radiador', 'electroventilador', 'aspas', 'envase de refrigerante', 'manguera de radiador', 'compresor de aire automotriz', 'evaporador', 'condensador', 'filtro secante', 'gas refrigerante', 'r134a'],
    ['casco de moto', 'casco integral', 'casco abatible', 'casco abierto', 'casco certificado', 'guantes de moto', 'impermeable de moto', 'traje de lluvia', 'chaqueta de moto', 'rodilleras de moto', 'maletero de moto', 'baul de moto', 'malla pulpo', 'candado de disco', 'cadena de moto', 'kit de arrastre', 'piñon', 'corona de moto', 'caucho de moto', 'tripa de moto', 'bateria de moto', 'bujia de moto', 'pastillas de moto', 'bandas de moto', 'manilla de freno', 'manilla de croche', 'retrovisor de moto', 'espejo de moto', 'guaya de acelerador', 'velocimetro', 'tacometro', 'carburador', 'cdi', 'estator', 'regulador de moto', 'amortiguador de moto'],
    ['bombillo automotriz', 'bombillo led carro', 'bombillo h4', 'bombillo h7', 'bombillo h11', 'bombillo 9005', 'bombillo 9006', 'barra led', 'faro', 'faros', 'exploradoras', 'neblineros', 'stop', 'mica', 'cruces', 'rele automotriz', 'fusible', 'fusibles'],
    ['reproductor de carro', 'radio de carro', 'pantalla android', 'carplay', 'cornetas de carro', 'coaxiales', 'medios', 'tweeter', 'bajo', 'subwoofer', 'cajon de bajo', 'planta de sonido', 'amplificador de carro', 'kit de cables para planta'],
    ['alarma de carro', 'cortacorriente', 'corta corriente', 'trancapalanca', 'tranca palanca', 'tranca volante', 'gps automotriz', 'cierre centralizado', 'papel ahumado', 'forros de asiento', 'forro de volante', 'alfombras de carro', 'tapetes de carro', 'cepillo limpiaparabrisas', 'limpiaparabrisas', 'plumillas', 'pito', 'corneta pito', 'gato hidraulico', 'gato caiman', 'gato botella', 'llave de cruz', 'triangulo de seguridad', 'extintor', 'cincha', 'eslinga de remolque'],
    ['cera para carro', 'pulitura', 'champu para carro', 'champú automotriz', 'shampoo automotriz', 'silicon automotriz', 'abrillantador de cauchos', 'limpia tapiceria', 'limpia tablero', 'desengrasante de motor', 'limpia carburador', 'wd40', 'wd-40', 'aflojatodo', 'paño de secado', 'hidrolavadora automotriz'],

    # --------------------------------------------------------------------------
    # 9. DEPORTES Y FITNESS
    # --------------------------------------------------------------------------
    ['pesa', 'pesas', 'mancuerna', 'mancuernas', 'disco de pesas', 'barra olimpica', 'barra z', 'pesa rusa', 'kettlebell', 'tobilleras con peso', 'chaleco con peso', 'banco de pesas', 'multifuerza', 'barra de dominadas', 'rueda abdominal', 'banda elastica', 'bandas de resistencia', 'ligas de ejercicio', 'trx', 'cuerda de saltar', 'guantes de gym', 'calleras', 'cinturon de gym', 'straps', 'muñequeras de gym', 'bicicleta estatica', 'spinning', 'caminadora', 'trotadora', 'eliptica', 'colchoneta de ejercicio', 'mat de yoga', 'esterilla de yoga', 'pelota de pilates', 'foam roller', 'step'],
    ['beisbol', 'béisbol', 'softbol', 'sóftbol', 'guante de beisbol', 'guante de softbol', 'mascota de beisbol', 'mascotin', 'bate', 'bate de beisbol', 'bate de softbol', 'bate de madera', 'bate de aluminio', 'pelota de beisbol', 'pelota de softbol', 'guantines', 'bateo', 'casco de bateo', 'tacos de beisbol', 'ganchos de beisbol', 'peto de receptor', 'careta de catcher'],
    ['futbol', 'fútbol', 'futsal', 'futbolito', 'balon de futbol', 'pelota de futbol', 'balon de futsal', 'tacos de futbol', 'guayos', 'zapatos de futbol', 'zapatos de futsal', 'canilleras', 'espinilleras', 'guantes de portero', 'arquero', 'medias de futbol', 'malla de arquería', 'conos de entrenamiento', 'escalera de agilidad', 'silbato', 'pito'],
    ['basquet', 'básquet', 'basquetbol', 'baloncesto', 'balon de basquet', 'pelota de basquet', 'spalding', 'aro de basquet', 'tablero de basquet', 'malla de basquet'],
    ['padel', 'pádel', 'tenis', 'pala de padel', 'raqueta de padel', 'raqueta de tenis', 'pelotas de padel', 'pelotas de tenis', 'overgrip', 'grip', 'paletero', 'bolso de padel', 'ping pong', 'tenis de mesa', 'raqueta de ping pong', 'pelotas de ping pong', 'voleibol', 'balon de voleibol', 'malla de voleibol'],
    ['bicicleta', 'bicicletas', 'bici', 'bicicleta montañera', 'mtb', 'bicicleta de ruta', 'bmx', 'casco de bicicleta', 'casco de ciclismo', 'guantes de ciclismo', 'licra de ciclismo', 'bomba de inflar', 'inflador de bicicleta', 'tripa de bicicleta', 'caucho de bicicleta', 'candado de bicicleta', 'guaya de bicicleta', 'luz de bicicleta', 'portatermo', 'velocimetro de bicicleta', 'parches de bicicleta'],
    ['natacion', 'natación', 'lentes de natacion', 'gafas de natacion', 'gorro de natacion', 'gorro de piscina', 'nariguera', 'tapones de oido', 'tabla de natacion', 'pull buoy', 'chapaletas', 'aletas', 'careta de buceo', 'snorkel'],
    ['camping', 'campamento', 'carpa', 'carpas', 'tienda de campaña', 'sleeping bag', 'saco de dormir', 'bolsa de dormir', 'colchon inflable', 'inflador electrico', 'silla plegable', 'silla de camping', 'mesa plegable', 'cocinilla de camping', 'bombona coleman', 'linterna recargable', 'linterna frontal', 'navaja suiza', 'cortaplumas', 'binoculares'],
    ['cava', 'cavas', 'cooler', 'coolers', 'hielera', 'cava playera', 'cava igloo', 'cava coleman', 'cava de anime', 'gel refrigerante', 'ice pack', 'termo', 'termos', 'botella deportiva', 'botella de agua', 'vaso termico', 'stanley', 'contigo', 'thermos', 'hydra'],
    ['proteina', 'proteína', 'proteinas', 'whey protein', 'isolate', 'proteina aislada', 'mass gainer', 'ganador de peso', 'creatina', 'creatina monohidratada', 'pre entreno', 'pre-entreno', 'pre workout', 'bcaa', 'aminoacidos', 'glutamina', 'quemador de grasa', 'l-carnitina', 'barra de proteina', 'shaker', 'vaso mezclador'],

    # --------------------------------------------------------------------------
    # 10. BEBÉS Y MATERNIDAD
    # --------------------------------------------------------------------------
    ['pañal', 'pañales', 'panal', 'panales', 'pampers', 'huggies', 'babysec', 'winny', 'pañales recien nacido', 'pañales talla p', 'pañales talla m', 'pañales talla g', 'pañales talla xg', 'pañales talla xxg'],
    ['toallitas humedas', 'toallitas húmedas', 'toallitas de bebe', 'wipes', 'crema antipañalitis', 'antipañalitis', 'crema para pañalitis', 'desitin', 'beducen', 'nistatina', 'oxido de zinc'],
    ['tetero', 'teteros', 'biberon', 'biberón', 'biberones', 'avent', 'dr browns', 'tetero anticolico', 'tetina', 'chupón', 'chupon', 'chupones', 'chupete', 'pacificador', 'porta chupon', 'sujetador de chupon', 'esterilizador de teteros', 'calentador de teteros', 'cepillo limpia teteros', 'escurridor de teteros', 'termo para tetero', 'dosificador de leche'],
    ['extractor de leche', 'sacaleche', 'saca leche', 'tiraleche', 'tira leche', 'extractor materno', 'bolsas recolectoras de leche', 'recolector de leche', 'protectores de lactancia', 'conchas de lactancia', 'crema de lanolina', 'almohada de lactancia', 'cojin de lactancia', 'brasier de lactancia'],
    ['formula infantil', 'fórmula infantil', 'leche de formula', 'leche de fórmula', 'leche maternizada', 'nan', 'enfamil', 'similac', 'nutrilon', 'alula', 'compota', 'compotas', 'papilla', 'gerber', 'heinz compota', 'galletas para bebe', 'vaso entrenador', 'vasito antiderrame', 'plato para bebe', 'cuchara de silicona', 'babero', 'baberos', 'silla de comer', 'trona'],
    ['coche de bebe', 'coche para bebe', 'cochecito', 'carriola', 'coche paraguita', 'travel system', 'portabebe', 'porta bebe', 'portabebés', 'moises portatil', 'canguro para bebe', 'fular', 'mochila ergonomica', 'silla de carro para bebe', 'silla de auto', 'autoasiento', 'booster', 'pañalera', 'bolso maternal', 'cambiador'],
    ['cuna', 'cunas', 'corral', 'corral de bebe', 'corral cuna', 'practicuna', 'moises', 'colecho', 'colchon de cuna', 'lenceria de cuna', 'protector de cuna', 'movil de cuna', 'mecedora de bebe', 'bouncer', 'columpio de bebe', 'andadera', 'andador de bebe', 'saltarin'],
    ['bañera de bebe', 'tina de bebe', 'soporte de bañera', 'malla de bañera', 'champu de bebe', 'jabon de bebe', 'colonia de bebe', 'aceite de bebe', 'crema de bebe', 'talco de bebe', 'cepillo para bebe', 'cortauñas de bebe', 'kit de aseo bebe', 'aspirador nasal', 'sacamocos', 'saca mocos', 'termometro de bebe'],
    ['ropa de bebe', 'monillo', 'monillos', 'body de bebe', 'bodies', 'enterizo de bebe', 'pijama de bebe', 'ajuar de recien nacido', 'conjunto primera puesta', 'escarpines', 'manoplas', 'gorrito de bebe', 'cobija de bebe', 'manta recibidora', 'swaddle'],
    ['monitor de bebe', 'camara para bebe', 'protector de enchufe', 'esquineros de seguridad', 'reja de seguridad'],

    # --------------------------------------------------------------------------
    # 11. JUEGOS Y JUGUETES
    # --------------------------------------------------------------------------
    ['muñeca', 'muñecas', 'barbie', 'barbies', 'muñeca bebe', 'bebe lloron', 'nenuco', 'lol surprise', 'casa de muñecas', 'coche de muñeca', 'accesorios de barbie', 'cocinita de juguete', 'juego de te', 'maquillaje de niña'],
    ['peluche', 'peluches', 'oso de peluche', 'peluche gigante', 'peluche stitch', 'peluche pokemon', 'peluche capibara'],
    ['figura de accion', 'figuras de acción', 'muñeco', 'superheroe', 'superhéroes', 'spiderman', 'hombre araña', 'batman', 'avengers', 'vengadores', 'iron man', 'hulk', 'transformers', 'goku', 'dragon ball', 'max steel', 'dinosaurio', 'dinosaurios', 'jurassic world', 'carro de juguete', 'carritos', 'hot wheels', 'pista hot wheels', 'carro a control remoto', 'rc', 'dron de juguete', 'tren de juguete', 'avion de juguete', 'robot de juguete'],
    ['lego', 'legos', 'bloques de construccion', 'bloques para armar', 'bloques magneticos', 'tacos para armar', 'playmobil', 'slime', 'plastilina play-doh', 'play doh', 'masa moldeable', 'arena magica'],
    ['juego de mesa', 'juegos de mesa', 'monopolio', 'monopoly', 'uno', 'cartas', 'naipes', 'cartas pokemon', 'yugioh', 'domino', 'dominó', 'ajedrez', 'damas', 'ludo', 'parchis', 'jenga', 'twister', 'scrabble', 'adivina quien', 'operando', 'bingo', 'cubo rubik', 'cubo magico'],
    ['patineta', 'patinetas', 'skateboard', 'scooter infantil', 'monopatin', 'monopatín', 'triciclo', 'bicicleta para niños', 'bicicleta con rueditas', 'patines', 'patines en linea', 'patines 4 ruedas', 'carro montable', 'correpasillos', 'carro electrico para niños', 'moto electrica infantil', 'cama elastica', 'trampolin', 'columpio', 'tobogan', 'pistola nerf', 'lanzador de dardos', 'espada de juguete', 'burbujero', 'hula hula', 'cometa', 'papagayo'],
    ['piscina inflable', 'piscina estructural', 'flotador', 'flotadores', 'salvavidas', 'alitas inflables', 'rueda inflable', 'colchoneta de piscina', 'pistola de agua', 'juguetes de playa', 'tobo de playa', 'pelota de playa'],
    ['sonajero', 'maraquita', 'mordedor', 'rascaencias', 'rasca encias', 'gimnasio para bebe', 'alfombra de actividades', 'juguetes de estimulacion', 'juguetes didacticos', 'juguetes montessori', 'juguetes de madera', 'encajables', 'musical para bebe'],

    # --------------------------------------------------------------------------
    # 12. MASCOTAS
    # --------------------------------------------------------------------------
    ['perrarina', 'alimento para perro', 'comida para perro', 'concentrado para perro', 'croquetas para perro', 'dogourmet', 'dog chow', 'purina', 'supercan', 'ringo', 'chunky', 'pro plan', 'pedigree', 'comida humeda para perro', 'lata para perro'],
    ['gatarina', 'alimento para gato', 'comida para gato', 'concentrado para gato', 'cat chow', 'gatsy', 'whiskas', 'felix', 'mirringo', 'oh mai gat', 'sobrecito para gato', 'comida humeda para gato', 'atun para gato'],
    ['snack para perro', 'snacks para mascotas', 'galletas para perro', 'premios para perro', 'hueso para perro', 'hueso de carnaza', 'dentastix', 'churu', 'catnip', 'hierba gatera'],
    ['arena para gato', 'arena sanitaria', 'arena aglomerante', 'arena de silice', 'arenera', 'caja de arena', 'arenero para gato', 'pala para arena', 'tapete para arenera'],
    ['antipulgas', 'anti pulgas', 'garrapaticida', 'pastilla antipulgas', 'nexgard', 'bravecto', 'simparica', 'credelio', 'pipeta', 'pipeta antipulgas', 'frontline', 'advantix', 'collar antipulgas', 'seresto', 'jabon antipulgas', 'spray antipulgas', 'talco antipulgas', 'desparasitante', 'drontal', 'vitaminas para perro', 'protector de patas', 'cono isabelino', 'collar isabelino'],
    ['champu para perro', 'champú para perro', 'shampoo para mascota', 'baño seco mascota', 'perfume para perro', 'colonia canina', 'cepillo para perro', 'cepillo para gato', 'carda', 'deslanador', 'furminator', 'cortauñas para perro', 'cortauñas de mascota', 'maquina de afeitar perros', 'pañales para perro', 'tapete entrenador', 'wee wee pad'],
    ['cama para perro', 'cama para gato', 'cama de mascota', 'colchoneta para perro', 'casa para perro', 'iglú para gato', 'kennel', 'transportadora', 'jaula transportadora', 'bolso transportador mascota', 'jaula para perro', 'corral para mascota', 'rascador para gato', 'gimnasio para gato', 'juguete para perro', 'pelota para perro', 'kong', 'juguete para gato', 'comedero', 'bebedero', 'plato para perro', 'plato antireflujo', 'fuente de agua para gato'],
    ['collar para perro', 'collar para gato', 'pechera', 'pechera para perro', 'arnes para perro', 'arnés para mascota', 'correa para perro', 'paseador', 'correa retractil', 'bozal', 'placa de identificacion', 'ropa para perro', 'impermeable para perro', 'bolsitas para perro', 'bolsas recolectoras', 'porta bolsas'],
    ['alpiste', 'semillas para aves', 'alimento para pajaros', 'girasol para loros', 'jaula para pajaros', 'jaula para aves', 'bebedero para aves', 'comida para peces', 'hojuelas para peces', 'pecera', 'acuario', 'filtro de acuario', 'bomba de aire pecera', 'anticloro', 'alimento para tortuga', 'alimento para hamster', 'viruta de madera', 'heno'],

    # --------------------------------------------------------------------------
    # 13. PAPELERÍA, OFICINA Y LIBROS
    # --------------------------------------------------------------------------
    ['cuaderno', 'cuadernos', 'libreta', 'libretas', 'cuaderno empastado', 'cuaderno espiral', 'cuaderno una linea', 'cuaderno cuadriculado', 'cuaderno doble linea', 'block', 'block de notas', 'block de dibujo', 'block milimetrado', 'agenda', 'planner', 'taco de notas', 'post-it', 'notas adhesivas'],
    ['lapiz', 'lápiz', 'lapices', 'lápices', 'lapiz de grafito', 'lapiz mongol', 'portaminas', 'minas', 'colores', 'creyones', 'caja de colores', 'prismacolor', 'kores', 'norma', 'faber castell'],
    ['boligrafo', 'bolígrafo', 'boligrafos', 'lapicero', 'lapiceros', 'pluma', 'kilometrico', 'paper mate', 'bic', 'marcador', 'marcadores', 'sharpie', 'marcador permanente', 'marcador de pizarra', 'marcador acrilico', 'plumones', 'resaltador', 'resaltadores', 'destacador'],
    ['borrador', 'borradores', 'goma de borrar', 'borrador nata', 'sacapuntas', 'saca puntas', 'tajador', 'corrector', 'corrector liquido', 'liquid paper', 'cinta correctora', 'regla', 'juego de geometria', 'escuadras', 'transportador', 'compas', 'compás'],
    ['resma', 'resmas', 'resma de papel', 'resma de hojas', 'resma carta', 'resma oficio', 'hojas blancas', 'hojas de examen', 'papel bond', 'cartulina', 'cartulina escolar', 'cartulina opalina', 'cartulina bristol', 'papel crepe', 'papel crepé', 'papel seda', 'papel lustrillo', 'papel celofan', 'papel contact', 'forro autoadhesivo', 'papel fotografico', 'papel carbon', 'carton en kilo', 'carton corrugado', 'anime escolar'],
    ['morral', 'morrales', 'mochila', 'mochilas', 'morral escolar', 'morral con ruedas', 'lonchera', 'cartuchera', 'cartucheras', 'portalapices', 'porta lapices'],
    ['foami', 'fomi', 'goma eva', 'foami escarchado', 'silicon liquido', 'silicón líquido', 'barrita de silicon', 'barra de silicon', 'pistola de silicon escolar', 'pega blanca', 'pega escolar', 'colbon', 'pega en barra', 'tempera', 'témpera', 'pintura al frio', 'pinturas al frío', 'acuarela', 'acuarelas', 'oleo', 'acrilico', 'pincel', 'pinceles', 'lienzo', 'bastidor', 'paleta de pintor', 'plastilina', 'arcilla', 'masa flexible', 'porcelana fria', 'estambre', 'lana', 'fieltro', 'escarcha', 'purpurina', 'diamantina', 'ojitos moviles', 'limpiapipas', 'paletas de helado', 'cinta de raso'],
    ['carpeta', 'carpetas', 'carpeta manila', 'carpeta marron', 'carpeta oslo', 'carpeta plastica', 'carpeta con liga', 'archivador', 'archivadores', 'carpeta lomo ancho', 'gancho de carpeta', 'fundas plasticas', 'protector de hojas', 'separadores', 'sobre manila', 'sobres de carta', 'porta carnet', 'lanyard'],
    ['calculadora', 'calculadoras', 'calculadora cientifica', 'casio', 'grapadora', 'engrapadora', 'grapas', 'sacagrapas', 'saca grapas', 'perforadora', 'abrehuecos', 'abre huecos', 'tijera', 'tijeras', 'tijera escolar', 'clips', 'sujetapapeles', 'binder clips', 'chinches', 'tachuelas', 'ligas de billete', 'bandas de goma', 'cinta adhesiva', 'celoven', 'teipe transparente', 'dispensador de cinta', 'almohadilla dactilar', 'tinta para sello', 'pizarra', 'pizarra acrilica', 'pizarra de corcho', 'borrador de pizarra'],
    ['silla de oficina', 'silla ejecutiva', 'silla ergonomica', 'silla secretarial', 'escritorio', 'escritorios', 'mesa de computadora', 'archivador metalico'],
    ['libro', 'libros', 'libro escolar', 'texto escolar', 'caligrafia', 'mi jardin', 'enciclopedia', 'diccionario', 'novela', 'literatura', 'autoayuda', 'cuento', 'cuentos infantiles', 'libro para colorear', 'biblia'],

    # --------------------------------------------------------------------------
    # 14. INSTRUMENTOS MUSICALES Y AUDIO PROFESIONAL
    # --------------------------------------------------------------------------
    ['cuatro', 'cuatro venezolano', 'maraca', 'maracas', 'furruco', 'tambora', 'charrasca', 'arpa', 'bandola'],
    ['guitarra', 'guitarras', 'guitarra acustica', 'guitarra clasica', 'guitarra electroacustica', 'guitarra electrica', 'bajo', 'bajo electrico', 'ukelele', 'ukulele', 'violin', 'violín', 'viola', 'cello', 'violonchelo', 'mandolina'],
    ['amplificador', 'amplificadores', 'amplificador de guitarra', 'amplificador de bajo', 'planta de guitarra', 'cabezal'],
    ['teclado musical', 'organeta', 'piano', 'piano digital', 'piano electrico', 'sintetizador', 'controlador midi', 'acordeon'],
    ['bateria musical', 'bateria acustica', 'bateria electronica', 'redoblante', 'tarola', 'bombo', 'platillos', 'hi-hat', 'baquetas', 'palillos de bateria', 'parche de bateria', 'pedal de bombo'],
    ['percusion', 'percusión', 'conga', 'congas', 'tumbadora', 'timbal', 'timbales', 'bongo', 'bongó', 'bongos', 'cajon peruano', 'cajón flamenco', 'campana', 'cencerro', 'guiro', 'güiro', 'pandereta', 'triangulo', 'xilofono', 'metalofono'],
    ['flauta', 'flauta dulce', 'flauta escolar', 'flauta traversa', 'saxofon', 'saxofón', 'trompeta', 'trombon', 'clarinete', 'oboe', 'armonica', 'armónica', 'melodica'],
    ['microfono', 'micrófono', 'microfonos', 'microfono inalambrico', 'microfono de mano', 'microfono condensador', 'microfono solapa', 'lavalier', 'shure', 'consola de sonido', 'mezcladora', 'mixer de audio', 'interfaz de audio', 'planta profesional', 'corneta activa', 'cabina activa', 'monitor de estudio', 'subwoofer profesional', 'paral de microfono', 'pedestal de microfono', 'filtro pop', 'brazo de microfono'],
    ['controlador dj', 'consola dj', 'pioneer dj', 'audifonos de monitoreo', 'luces de discoteca', 'cabeza movil', 'maquina de humo', 'laser dj'],
    ['cuerdas de guitarra', 'cuerdas de cuatro', 'cuerdas de violin', 'cuerdas de bajo', 'forro de guitarra', 'forro de cuatro', 'estuche rigido', 'afinador', 'metronomo', 'capotraste', 'cejilla', 'pua', 'puas', 'pajuela', 'uñero', 'correa de guitarra', 'pedal de guitarra', 'pedalera', 'cable plug', 'cable xlr', 'cable canon', 'paral de guitarra', 'atril de partitura'],

    # --------------------------------------------------------------------------
    # 15. FIESTAS, PIÑATERÍA, DESCARTABLES Y EMBALAJE
    # --------------------------------------------------------------------------
    ['piñata', 'pinata', 'piñatas', 'palo de piñata', 'cotillon', 'cotillón', 'cotillones', 'bolsitas de cotillon', 'juguetes para cotillon', 'relleno de piñata'],
    ['globo', 'globos', 'bombas de fiesta', 'globos de latex', 'globos cromados', 'globo metalizado', 'globo de numero', 'globo burbuja', 'arco de globos', 'inflador de globos', 'bombona de helio', 'cortina metalizada', 'banderin', 'guirnalda', 'feliz cumpleaños', 'topper de torta', 'vela de cumpleaños', 'vela volcan', 'bengala', 'chispero', 'confeti', 'lanzaconfeti', 'hora loca', 'sombrero de fiesta', 'antifaz', 'disfraz', 'disfraces', 'maquillaje artistico', 'pintacaritas', 'mantel de fiesta'],
    ['descartables', 'desechables', 'vasos desechables', 'vasos plasticos', 'vasos de carton', 'platos desechables', 'platos de anime', 'platos plasticos', 'cubiertos desechables', 'cucharillas plasticas', 'tenedores plasticos', 'pitillo', 'pitillos', 'popotes', 'removedores', 'palillos', 'mondadientes', 'pinchos de madera', 'palillos de altura', 'envase desechable', 'envases de anime', 'contenedor de anime', 'envases bisagra', 'envase para postre', 'envase de aluminio', 'bandeja de aluminio', 'bandeja de anime', 'papel aluminio', 'envoplast', 'plastico film', 'papel encerado', 'capacillos', 'blondas', 'caja para torta', 'base para torta'],
    ['embalaje', 'empaque', 'caja de carton', 'cajas de carton', 'cajas para mudanza', 'cajas para envio', 'bolsa plastica', 'bolsas plasticas', 'bolsas camiseta', 'bolsas de boutique', 'bolsas de regalo', 'bolsas kraft', 'bolsas de papel', 'bolsas ziploc', 'bolsas hermeticas', 'papel de regalo', 'papel celofan', 'lazo de regalo', 'cinta plastica', 'papel burbuja', 'plástico de burbujas', 'stretch film', 'envoplast industrial', 'cinta de embalar', 'tirro de embalaje', 'dispensador de cinta', 'fleje', 'etiquetas adhesivas'],
]

# Prefijos verbales/compuestos que en español e inglés comercial suelen escribirse
# juntos o separados ('abrelatas' <-> 'abre latas', 'sacacorchos' <-> 'saca corchos',
# 'antipulgas' <-> 'anti pulgas', 'cortauñas' <-> 'corta uñas', etc.).
_COMPOUND_PREFIXES = (
    'abre', 'saca', 'corta', 'lava', 'limpia', 'porta', 'posa', 'guarda',
    'cubre', 'quita', 'mata', 'rompe', 'destapa', 'pela', 'pisa', 'escurre',
    'prensa', 'ralla', 'casca', 'tapa', 'apoya', 'espanta', 'rasca', 'pica',
    'bate', 'exprime', 'seca', 'atrapa', 'tranca', 'busca', 'salva', 'arranca',
    'power', 'smart', 'air', 'micro', 'multi', 'anti', 'auto',
)


def _fold(text: str) -> str:
    if not text:
        return ''
    replacements = (
        ('á', 'a'), ('é', 'e'), ('í', 'i'), ('ó', 'o'), ('ú', 'u'),
        ('ü', 'u'), ('ñ', 'n'),
    )
    folded = text.lower().strip()
    for src, dst in replacements:
        folded = folded.replace(src, dst)
    return folded


def _spanish_morph_variants(tok: str) -> List[str]:
    """
    Genera variantes morfológicas singular/plural del español:
    - '-ces' <-> '-z' ('lapices' <-> 'lapiz', 'luces' <-> 'luz', 'nueces' <-> 'nuez')
    - '-es' tras consonante r/n/l/d/j/s ('cargadores' <-> 'cargador', 'pantalones' <-> 'pantalon',
      'colchones' <-> 'colchon', 'morrales' <-> 'morral', 'relojes' <-> 'reloj')
    - '-s' estándar ('camisas' <-> 'camisa', 'zapatos' <-> 'zapato')
    """
    out = [tok]
    if len(tok) > 4 and tok.endswith('ces'):
        out.append(tok[:-3] + 'z')
    elif len(tok) >= 3 and tok.endswith('z'):
        out.append(tok[:-1] + 'ces')

    if len(tok) > 4 and tok.endswith('es') and tok[-3] in 'rnldjs':
        out.append(tok[:-2])
    if len(tok) > 4 and tok.endswith('s'):
        out.append(tok[:-1])
    elif len(tok) > 3 and not tok.endswith('s'):
        if tok[-1] in 'rnldj':
            out.append(tok + 'es')
        if tok[-1] != 'z':
            out.append(tok + 's')

    seen = set()
    ordered = []
    for item in out:
        if item and item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def _build_synonym_index():
    index = {}
    phrase_token_index = []
    for group in SYNONYM_GROUPS:
        folded_group = [_fold(term) for term in group if term]
        unique_group = list(dict.fromkeys(folded_group))
        for term in unique_group:
            index.setdefault(term, set()).update(unique_group)
            # Indexar también formas morfológicas de términos de 1 palabra para que
            # buscar en plural ('colchones', 'cargadores', 'lapices') dispare el grupo.
            if ' ' not in term and len(term) >= 3:
                for morph in _spanish_morph_variants(term):
                    index.setdefault(morph, set()).update(unique_group)
            elif ' ' in term:
                content_words = frozenset(
                    w for w in re.split(r'[^a-z0-9]+', term)
                    if len(w) >= 3 and w not in SEARCH_STOPWORDS
                )
                if len(content_words) >= 2:
                    phrase_token_index.append((content_words, unique_group))
    return index, phrase_token_index


_SYNONYM_INDEX, _PHRASE_TOKEN_INDEX = _build_synonym_index()


def _split_compound_token(token: str) -> List[str]:
    """Si `token` es una palabra compuesta ('abrelatas'), devuelve sus formas separadas ('abre latas', 'abre lata')."""
    out: List[str] = []
    for prefix in _COMPOUND_PREFIXES:
        if token.startswith(prefix) and len(token) - len(prefix) >= 3:
            rest = token[len(prefix):]
            out.append(f"{prefix} {rest}")
            for morph_rest in _spanish_morph_variants(rest):
                candidate = f"{prefix} {morph_rest}"
                if candidate not in out:
                    out.append(candidate)
            break
    return out


def tokenize_query(query: str) -> List[str]:
    folded = _fold(query)
    raw_tokens = [tok for tok in re.split(r'[^a-z0-9]+', folded) if tok and tok not in SEARCH_STOPWORDS]
    tokens = []
    i = 0
    while i < len(raw_tokens):
        tok = raw_tokens[i]
        # Si es un prefijo compuesto seguido de su sustantivo ('abre' + 'latas'),
        # se une como unidad compuesta ('abrelatas') para no emitir 'latas' suelto.
        if tok in _COMPOUND_PREFIXES and (i + 1) < len(raw_tokens) and len(raw_tokens[i + 1]) >= 3:
            joined = tok + raw_tokens[i + 1]
            for morph in _spanish_morph_variants(joined):
                tokens.append(morph)
            i += 2
            continue
        if len(tok) < 2:
            i += 1
            continue
        for morph in _spanish_morph_variants(tok):
            tokens.append(morph)
        i += 1
    # unique preserve order
    seen = set()
    ordered = []
    for tok in tokens:
        if tok not in seen:
            seen.add(tok)
            ordered.append(tok)
    return ordered


def expand_search_variants(query: str) -> List[str]:
    """Devuelve frases a buscar en nombre/descripcion/atributos (query original + sinónimos + compuestos + morfología)."""
    folded = _fold(query)
    variants: List[str] = []
    seen_folded: Set[str] = set()

    def _add(val: str):
        f_val = _fold(val)
        if f_val and f_val not in seen_folded:
            seen_folded.add(f_val)
            variants.append(val.strip())

    if query and query.strip():
        _add(query.strip())
    if folded:
        _add(folded)

    tokens = tokenize_query(query)
    for token in tokens:
        _add(token)
        for split_form in _split_compound_token(token):
            _add(split_form)
        for syn in sorted(_SYNONYM_INDEX.get(token, [])):
            _add(syn)

    # Frases multi-palabra del léxico si el query las contiene literalmente
    for phrase, related in _SYNONYM_INDEX.items():
        if ' ' in phrase and phrase in folded:
            for syn in related:
                _add(syn)

    # Coincidencia por conjunto de palabras significativas de frase ('alimento perro' -> 'alimento para perro' -> 'perrarina')
    token_set = set(tokens)
    if len(token_set) >= 2:
        for content_words, group in _PHRASE_TOKEN_INDEX:
            if content_words.issubset(token_set):
                for syn in group:
                    _add(syn)

    # Limitar explosión manteniendo alta cobertura
    return variants[:40]


def significant_tokens(query: str) -> List[str]:
    return [tok for tok in tokenize_query(query) if len(tok) >= 3]


# Términos de esta longitud o menos ('res', 'pan', 'sal', 'gas', 'te') solo
# deben coincidir como palabra aislada, nunca como subcadena ('refresco', 'empanada', 'salsa').
SHORT_TERM_MAX_LEN = 4


def is_short_term(term: str) -> bool:
    """True si el término es lo bastante corto como para exigir límite de palabra."""
    return len((term or '').strip()) <= SHORT_TERM_MAX_LEN


_ACCENT_CLASSES = {
    'a': '[aáàä]', 'e': '[eéèë]', 'i': '[iíìï]', 'o': '[oóòö]', 'u': '[uúùü]', 'n': '[nñ]',
}


def accent_insensitive_pattern(term: str) -> str:
    """
    Patrón POSIX que ignora tildes y tolera espacios/guiones opcionales entre palabras
    y entre números y letras:
    - 'camara' y 'cámara' casan con 'Cámara' o 'Camara'
    - 'abre latas' casa con 'Abrelatas', 'Abre latas' y 'Abre-latas'
    - '128gb' y '128 gb' casan con '128GB', '128 GB' y '128-GB'
    """
    folded = _fold((term or '').strip())
    spaced = re.sub(r'(\d)([a-z])', r'\1 \2', folded)
    spaced = re.sub(r'([a-z])(\d)', r'\1 \2', spaced)
    parts = [
        ''.join(_ACCENT_CLASSES.get(ch, re.escape(ch)) for ch in chunk)
        for chunk in re.split(r'[\s\-]+', spaced)
        if chunk
    ]
    return r'[\s\-]*'.join(parts)


def substring_regex(term: str) -> str:
    """Regex (PostgreSQL ARE) de subcadena sin distinguir tildes, para `__iregex`."""
    return accent_insensitive_pattern(term)


def word_boundary_regex(term: str) -> str:
    """Regex POSIX (PostgreSQL ARE) con límite de palabra `\\y`, sin distinguir tildes, para `__iregex`."""
    return r'\y' + accent_insensitive_pattern(term) + r'\y'


def lexical_match(texts: Iterable[str], variants: Iterable[str]) -> bool:
    """
    Coincidencia léxica directa en memoria, espejo del filtro SQL:
    variantes cortas -> palabra aislada; variantes largas -> subcadena (incluyendo
    comparación colapsando espacios/guiones para compuestos como 'abrelatas' <-> 'abre latas'
    y '128gb' <-> '128 GB').
    """
    folded_texts = [_fold(text) for text in texts if text]
    if not folded_texts:
        return False
    collapsed_texts = [re.sub(r'[\s\-]+', '', text) for text in folded_texts]
    for variant in variants:
        folded_variant = _fold(variant)
        if len(folded_variant) < 2:
            continue
        if is_short_term(folded_variant):
            pattern = re.compile(r'\b' + re.escape(folded_variant) + r'\b')
            if any(pattern.search(text) for text in folded_texts):
                return True
        else:
            if any(folded_variant in text for text in folded_texts):
                return True
            collapsed_variant = re.sub(r'[\s\-]+', '', folded_variant)
            if len(collapsed_variant) >= 4 and any(collapsed_variant in ct for ct in collapsed_texts):
                return True
    return False
