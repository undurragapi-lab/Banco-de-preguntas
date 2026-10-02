import cv2
import google.generativeai as genai
from PIL import Image
import json
import os

# 1. Configuración de la API (Asegúrate de configurar tu variable de entorno)
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

def preprocesar_imagen(ruta_imagen):
    """
    Maximiza el contraste del lápiz grafito frente al papel y la tinta impresa.
    """
    # Leer la imagen original
    img = cv2.imread(ruta_imagen)
    if img is None:
        raise FileNotFoundError(f"No se pudo encontrar la imagen en {ruta_imagen}")

    # Convertir a escala de grises
    gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Aplicar CLAHE (Contrast Limited Adaptive Histogram Equalization)
    # Esto oscurece los trazos débiles de grafito sin quemar el resto del documento
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    imagen_mejorada = clahe.apply(gris)

    # Guardar imagen optimizada temporalmente para enviarla a la API
    ruta_temp = "temp_optimizada.jpg"
    cv2.imwrite(ruta_temp, imagen_mejorada)
    
    return ruta_temp

def extraer_cuestionario(ruta_imagen):
    """
    Envía la imagen preprocesada al modelo multimodal solicitando un JSON estricto.
    """
    ruta_lista = preprocesar_imagen(ruta_imagen)
    imagen_pil = Image.open(ruta_lista)

    # Instanciar el modelo (gemini-1.5-pro es recomendado para documentos densos y OCR)
    modelo = genai.GenerativeModel('gemini-1.5-pro')

    # Prompt de extracción estructurada
    prompt = """
    Eres un sistema experto en OMR (Optical Mark Recognition) y OCR.
    Analiza la imagen adjunta, que es una página de un examen de aviación de la DGAC.
    Las respuestas correctas han sido marcadas a mano con lápiz (pueden ser cruces, círculos, rayas o marcas de verificación sobre o junto a la letra).
    
    Tu tarea es extraer el texto exacto y detectar la marca física.
    Devuelve ÚNICAMENTE un arreglo JSON válido con la siguiente estructura, sin texto adicional ni formato markdown:
    [
      {
        "numero": 1,
        "pregunta": "Texto de la pregunta...",
        "alternativas": {
          "A": "Texto alternativa A",
          "B": "Texto alternativa B",
          "C": "Texto alternativa C"
        },
        "respuesta_marcada": "C" 
      }
    ]
    Si no hay marca en una pregunta, asigna null a "respuesta_marcada".
    """

    # Configurar la generación para forzar formato JSON (requerido para integración en apps)
    configuracion = genai.GenerationConfig(
        response_mime_type="application/json"
    )

    respuesta = modelo.generate_content(
        [prompt, imagen_pil],
        generation_config=configuracion
    )
    
    # Limpiar archivo temporal
    if os.path.exists(ruta_lista):
        os.remove(ruta_lista)

    # Retornar el objeto JSON parseado
    return json.loads(respuesta.text)

# Ejecución de prueba
if __name__ == "__main__":
    archivo_prueba = "pagina_examen_escaneada.jpg" # Reemplaza con tu archivo de imagen real
    
    try:
        print("Procesando imagen y extrayendo datos...")
        datos_examen = extraer_cuestionario(archivo_prueba)
        
        # Imprimir el resultado estructurado
        print(json.dumps(datos_examen, indent=4, ensure_ascii=False))
        
    except Exception as e:
        print(f"Error en la ejecución: {e}")
