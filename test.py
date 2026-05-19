import os
from PIL import Image, ImageFilter

def redimensionar_comprimidas_con_enfoque(directorio_entrada, directorio_salida, tamaño_final=(540, 960)):
    if not os.path.exists(directorio_salida):
        os.makedirs(directorio_salida)

    for nombre_archivo in os.listdir(directorio_entrada):
        if nombre_archivo.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
            ruta_imagen = os.path.join(directorio_entrada, nombre_archivo)
            
            try:
                with Image.open(ruta_imagen) as img:
                    if img.mode in ("RGBA", "P"):
                        img = img.convert("RGB")
                    
                    # --- TRUCO: REDUCCIÓN EN CASCADA PARA SALVAR CALIDAD ---
                    # Paso 1: Reducir a la mitad (aprox 2000x3000)
                    ancho_medio1 = int(img.width * 0.5)
                    alto_medio1 = int(img.height * 0.5)
                    img_paso1 = img.resize((ancho_medio1, alto_medio1), Image.Resampling.LANCZOS)
                    
                    # Paso 2: Reducir a un tamaño intermedio (aprox 1080x1920)
                    ancho_medio2 = int(tamaño_final[0] * 2)
                    alto_medio2 = int(tamaño_final[1] * 2)
                    img_paso2 = img_paso1.resize((ancho_medio2, alto_medio2), Image.Resampling.LANCZOS)
                    
                    # Paso 3: Reducir al tamaño final real (540x960)
                    img_final = img_paso2.resize(tamaño_final, Image.Resampling.LANCZOS)
                    
                    # --- FILTRO DE ENFOQUE SUTIL ---
                    # Esto recupera el contraste en los bordes que se pierde al achicar imágenes comprimidas
                    img_final = img_final.filter(ImageFilter.SHARPEN)
                    
                    # Guardar con alta calidad para no volver a romperla
                    ruta_salida = os.path.join(directorio_salida, nombre_archivo)
                    img_final.save(ruta_salida, "JPEG", quality=90, optimize=True)
                    
                    print(f"✨ Optimizada con éxito: {nombre_archivo}")
                    
            except Exception as e:
                print(f"❌ Error al procesar {nombre_archivo}: {e}")

# ==========================================
# CONFIGURACIÓN
# ==========================================
carpeta_actual = './imagenes_categorias/'
carpeta_salida_hd = './imagenes_finales_fijas'

print("Procesando imágenes comprimidas con algoritmo de rescate...")
redimensionar_comprimidas_con_enfoque(carpeta_actual, carpeta_salida_hd)
print("¡Listo! Revisa la carpeta de salida.")