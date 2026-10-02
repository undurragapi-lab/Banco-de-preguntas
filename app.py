import streamlit as st
import cv2
import google.generativeai as genai
from PIL import Image
import json
import numpy as np
import fitz  # PyMuPDF para manejo de PDFs

# Configuración de API
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

st.set_page_config(page_title="AeroStudio Pro", layout="centered", page_icon="✈️")

st.title("✈ AeroStudio Pro")
st.subheader("Lector OMR de Cuestionarios DGAC")
st.write("Sube tu banco de preguntas en PDF o una página en imagen. El motor optimizará el contraste del grafito y extraerá todas las alternativas en formato estructurado.")

def procesar_imagen_memoria(imagen_bytes):
    """
    Decodifica la imagen, aplica filtro de alto contraste (CLAHE) para el grafito y retorna un objeto PIL.
    """
    nparr = np.frombuffer(imagen_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    imagen_mejorada = clahe.apply(gris)
    
    img_rgb = cv2.cvtColor(imagen_mejorada, cv2.COLOR_GRAY2RGB)
    return Image.fromarray(img_rgb)

def extraer_cuestionario(imagen_pil):
    """
    Extrae texto y marcas de lápiz estructuradas usando Gemini 1.5 Pro.
    """
    modelo = genai.GenerativeModel('gemini-1.5-pro')
    prompt = """
    Eres un sistema experto en OMR (Optical Mark Recognition) y OCR diseñado para procesar exámenes de aviación.
    Analiza la imagen adjunta. Las respuestas correctas han sido marcadas a mano con lápiz grafito.
    
    Devuelve ÚNICAMENTE un arreglo JSON válido con la siguiente estructura:
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

# Interfaz de carga: Ahora incluye PDF
archivo_subido = st.file_uploader("Adjunta tu documento (PDF, JPG, PNG)", type=["pdf", "jpg", "jpeg", "png"])

if archivo_subido is not None:
    bytes_data = archivo_subido.getvalue()
    tipo_archivo = archivo_subido.name.split('.')[-1].lower()
    
    if st.button("Analizar Documento", type="primary", use_container_width=True):
        resultados_totales = []
        
        with st.spinner("Procesando documento en el motor de visión..."):
            try:
                # FLUJO PARA PDF
                if tipo_archivo == 'pdf':
                    doc = fitz.open(stream=bytes_data, filetype="pdf")
                    barra_progreso = st.progress(0)
                    
                    for i in range(len(doc)):
                        # Extraer página como imagen (resolución de 150 DPI para buen balance OCR/rendimiento)
                        pagina = doc.load_page(i)
                        pix = pagina.get_pixmap(dpi=150)
                        bytes_img = pix.tobytes("png")
                        
                        # Procesar la imagen de la página
                        imagen_procesada = procesar_imagen_memoria(bytes_img)
                        datos_pagina = extraer_cuestionario(imagen_procesada)
                        
                        if isinstance(datos_pagina, list):
                            resultados_totales.extend(datos_pagina)
                            
                        # Actualizar barra de progreso
                        barra_progreso.progress((i + 1) / len(doc))
                        
                    st.success(f"¡Lectura exitosa de {len(doc)} páginas!")
                
                # FLUJO PARA IMAGEN INDIVIDUAL (JPG/PNG)
                else:
                    st.image(bytes_data, caption="Documento Original", use_column_width=True)
                    imagen_procesada = procesar_imagen_memoria(bytes_data)
                    resultados_totales = extraer_cuestionario(imagen_procesada)
                    st.success("¡Lectura de marcas exitosa!")

                # Desplegar JSON final consolidado
                st.json(resultados_totales)
                
            except Exception as e:
                st.error(f"Ocurrió un error en el procesamiento: {e}")
