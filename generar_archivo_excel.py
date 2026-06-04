import pandas as pd
import random

# Lista de productos base para el ecosistema de CartMaker (Venezuela)
productos_base = [
    {"name": "Harina Pan Refinada 1kg", "desc": "Harina de maíz blanco precocida. Ideal para arepas tradicionales venezolanas."},
    {"name": "Arroz Primor Grano Entero 1kg", "desc": "Arroz tipo de primera calidad. Libre de impurezas, cocción perfecta."},
    {"name": "Pasta Al結a Spaghetti 1kg", "desc": "Pasta de sémola de trigo duro. Excelente consistencia al dente."},
    {"name": "Aceite Vegetal Vatel 1L", "desc": "Aceite 100% puro de soya. Libre de colesterol, ideal para freír o aderezar."},
    {"name": "Café Fama de América 500g", "desc": "Café tostado y molido puro. Aroma intenso y sabor tradicional."},
    {"name": "Azúcar Montalbán Refinada 1kg", "desc": "Azúcar blanca refinada de alta pureza. Ideal para repostería y endulzar bebidas."},
    {"name": "Leche en Polvo La Campiña 400g", "desc": "Leche completa instantánea enriquecida con Vitaminas A y D."},
    {"name": "Margarina Mavesa Con Sal 500g", "desc": "Margarina untable clásica. Sabor casero inconfundible."},
    {"name": "Salsa de Tomate Pampero 397g", "desc": "Salsa estilo kétchup hecha con tomates seleccionados de calidad superior."},
    {"name": "Mayonesa Kraft Real 445g", "desc": "Mayonesa clásica con un toque de limón. Textura cremosa."},
    {"name": "Caraotas Negras Pantera 500g", "desc": "Granos seleccionados limpios. Tradición en el pabellón criollo Venezolano."},
    {"name": "Atún Margarita en Aceite 140g", "desc": "Lomitos de atún blanco en aceite vegetal. Alto contenido de Omega 3."},
    {"name": "Jabón Las Llaves Azul 250g", "desc": "Jabón en barra multiuso para lavado de ropa y limpieza profunda."},
    {"name": "Detergente ACE Limpieza Feliz 1kg", "desc": "Detergente en polvo multiacción para ropa blanca y de color."},
    {"name": "Chavito Harina de Trigo Robin Hood 1kg", "desc": "Harina con leudante especial para tortas y bizcochos esponjosos."},
    {"name": "Refresco Coca-Cola Sabor Original 2L", "desc": "Bebida gaseosa refrescante familiar. Servir bien fría."},
    {"name": "Queso Blanco Llanero Duro 1kg", "desc": "Queso rallar típico venezolano, punto perfecto de sal y maduración."},
    {"name": "Mortadela Especial Plumrose 1kg", "desc": "Embutido de carne seleccionada sazonado con especias finas."},
    {"name": "Galletas Club Social Original (Pack 6)", "desc": "Galletas saladas crujientes con un toque de mantequilla."},
    {"name": "Chocolate Toronto Savoy (Bolsa 12 u)", "desc": "Bombón de avellana tostada cubierto de chocolate de leche premium."}
]

# Vamos a inflar la lista a 45 productos duplicando con ligeras variantes de empaque/peso
data_rows = []
for i in range(45):
    base = productos_base[i % len(productos_base)]
    suffix = f" (Lote {random.randint(100,999)})" if i >= len(productos_base) else ""
    
    # Precios lógicos estimados en USD del mercado venezolano
    precio_venta = round(random.uniform(1.2, 18.5), 2)
    costo_compra = round(precio_venta * 0.7, 2)
    
    data_rows.append({
        "Código Interno": f"SKU-{10000 + i}",
        "Producto / Artículo": f"{base['name']}{suffix}",
        "Descripción Detallada": base["desc"],
        "Precio de Venta (USD)": precio_venta,
        "Costo de Proveedor": costo_compra,
        "Stock Actual (Ignorar)": random.randint(5, 120),
        "Proveedor Principal": random.choice(["Alimentos Polar", "Nestlé Venezuela", "Distribuidora El Carmen", "Sigo S.A."]),
        "Pasillo Almacén": f"Pasillo {random.randint(1, 10)}"
    })

# Crear DataFrame y exportar a Excel
df = pd.DataFrame(data_rows)
output_filename = "productos_prueba_cartmaker.xlsx"
df.to_excel(output_filename, index=False, sheet_name="Inventario General")

print(f"¡Archivo de prueba de {len(df)} productos generado con éxito: {output_filename}")