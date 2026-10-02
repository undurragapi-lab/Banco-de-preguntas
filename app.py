import streamlit as st
import cv2
import google.generativeai as genai
from PIL import Image
import json
import numpy as np

# Configuración de API conectada a los secretos de Streamlit Cloud
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# Configuración de la interfaz visual
st.set_page_config(page_title="AeroStudio Pro", layout="centered", page_icon="✈️")

st.title("✈️️ AeroStudio Pro")
st.subheader("Lector OMR de Cuestionarios DGAC")
st.write("Sube una página escaneada. El motor de visión optimizará el contraste del grafito y extraerá la alternativa marcada en formato estructurado.")

def procesar_imagen_memoria(imagen_bytes):
    """
    Decodifica la imagen subida a la web directamente en memoria RAM,
    aplica el filtro de alto contraste para grafito y la convierte a formato PIL.
    """
    # Convertir bytes a un arreglo de numpy
    nparr = np.frombuffer(imagen_bytes, np.uint8)
    
    # Decodificar imagen a formato OpenCV (BGR)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    # Convertir a escala de grises
    gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Aplicar CLAHE (Contrast Limited Adaptive Histogram Equalization)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    imagen_mejorada = clahe.apply(gris)

    # Convertir de vuelta a espacio de color RGB para compatibilidad con PIL/Gemini
    img_rgb = cv2.cvtColor(imagen_mejorada, cv2.COLOR_GRAY2RGB)
    
    # Retornar objeto de imagen nativo, sin guardar archivos temporales
    return Image.fromarray(img_rgb)

def extraer_cuestionario(imagen_pil):
    """
    Inyecta la imagen procesada al modelo multimodal y fuerza una salida JSON estricta.
    """
    modelo = genai.GenerativeModel('gemini-1.5-pro')

    prompt = """
    Eres un sistema experto en OMR (Optical Mark Recognition) y OCR diseñado para procesar exámenes de aviación.
    Analiza la imagen adjunta. Las respuestas correctas han sido marcadas a mano con lápiz grafito (cruces, círculos, rayas o marcas de verificación sobre o junto a la letra).
    
    Extrae el texto exacto y detecta la marca física.
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
    
    return json.loads(respuesta.text)

# Zona de carga de archivos en la interfaz
archivo_subido = st.file_uploader("Adjunta tu imagen (JPG, PNG)", type=["jpg", "jpeg", "png"])

if archivo_subido is not None:
    # Capturar la imagen subida en bytes
    bytes_data = archivo_subido.getvalue()
    
    # Mostrar vista previa en la plataforma
    st.image(bytes_data, caption="Documento Original", use_column_width=True)
    
    # Botón de ejecución
    if st.button("Analizar Respuestas", type="primary", use_container_width=True):
        with st.spinner("Optimizando trazos de lápiz y ejecutando análisis estructural..."):
            try:
                # 1. Aumentar contraste del grafito en memoria
                imagen_procesada_pil = procesar_imagen_memoria(bytes_data)
                
                # 2. Extraer datos con IA
                datos_json = extraer_cuestionario(imagen_procesada_pil)
                
                # 3. Desplegar resultados
                st.success("¡Lectura de marcas exitosa!")
                st.json(datos_json)
                
            except Exception as e:
                st.error(f"Ocurrió un error en el procesamiento: {e}")
