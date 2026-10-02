import streamlit as st
import cv2
import google.generativeai as genai
from PIL import Image
import json
import os
import numpy as np

# Configuración de la API usando los secretos de Streamlit
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

st.set_page_config(page_title="Lector DGAC", layout="centered")
st.title("✈️ Lector de Cuestionarios DGAC")
st.write("Sube una foto de la página del examen para extraer el texto y detectar la alternativa marcada a lápiz.")

def procesar_imagen_memoria(imagen_bytes):
    """
    Convierte el archivo web subido a una imagen de OpenCV y mejora el contraste.
    """
    # Convertir bytes a formato legible por OpenCV
    nparr = np.frombuffer(imagen_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    # Convertir a escala de grises y aplicar contraste (CLAHE)
    gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    imagen_mejorada = clahe.apply(gris)

    # Guardar temporalmente para pasarla a Gemini
    ruta_temp = "temp_optimizada.jpg"
    cv2.imwrite(ruta_temp, imagen_mejorada)
    return ruta_temp

def extraer_cuestionario(ruta_imagen):
    """
    Analiza la imagen procesada usando el modelo multimodal.
    """
    imagen_pil = Image.open(ruta_imagen)
    modelo = genai.GenerativeModel('gemini-1.5-pro')

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
    configuracion = genai.GenerationConfig(response_mime_type="application/json")
    respuesta = modelo.generate_content([prompt, imagen_pil], generation_config=configuracion)
    
    # Limpieza del archivo temporal
    if os.path.exists(ruta_imagen):
        os.remove(ruta_imagen)

    return json.loads(respuesta.text)

# Interfaz de usuario para cargar archivos
archivo_subido = st.file_uploader("Adjunta tu imagen (JPG, PNG)", type=["jpg", "jpeg", "png"])

if archivo_subido is not None:
    # Mostrar vista previa de la imagen cargada
    st.image(archivo_subido, caption="Vista previa del documento", use_column_width=True)
    
    if st.button("Analizar Respuestas", type="primary"):
        with st.spinner("Procesando contraste y leyendo documento..."):
            try:
                # Leer los bytes del archivo cargado en la web
                bytes_data = archivo_subido.getvalue()
                
                # Ejecutar el flujo de procesamiento
                ruta_procesada = procesar_imagen_memoria(bytes_data)
                datos_json = extraer_cuestionario(ruta_procesada)
                
                # Mostrar resultados
                st.success("¡Extracción exitosa!")
                st.json(datos_json)
                
            except Exception as e:
                st.error(f"Ocurrió un error: {e}")
