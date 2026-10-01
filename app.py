import os
import json
import tempfile
import streamlit as st
from PIL import Image
from pdf2image import convert_from_path
from google import genai
from google.genai import types

# Configuración de la interfaz
st.set_page_config(page_title="Lector Inteligente de Exámenes", page_icon="✈️", layout="wide")

st.title("✈️ Sistema de Lectura de Exámenes Aeronáuticos (Cloud + Visión IA)")

# ==========================================
# GESTIÓN DE LA API KEY EN LA NUBE (Sin pedirla)
# ==========================================
# 1. Intentar cargar la key automáticamente desde los secretos seguros de la plataforma online
api_key_configurada = ""
try:
    if "GEMINI_API_KEY" in st.secrets:
        api_key_configurada = st.secrets["GEMINI_API_KEY"]
except Exception:
    pass  # Si no hay secretos configurados localmente o en la nube, continúa

# 2. Gestionar mediante session_state para que el usuario no tenga que reingresarla
if "gemini_api_key" not in st.session_state:
    st.session_state["gemini_api_key"] = api_key_configurada

# Si la clave sigue vacía (por si olvidaste ponerla en los secrets de la nube), 
# se habilitará un campo en la barra lateral solo como respaldo de emergencia.
if not st.session_state["gemini_api_key"]:
    st.sidebar.warning("⚠️ No se detectó una API Key preconfigurada en el sistema.")
    user_input_key = st.sidebar.text_input("Ingresa tu Google Gemini API Key", type="password")
    if user_input_key:
        st.session_state["gemini_api_key"] = user_input_key
        st.sidebar.success("¡Clave guardada para esta sesión!")
else:
    st.sidebar.success("🔒 API Key cargada de forma segura desde la nube.", icon="✅")

# ==========================================
# FUNCIÓN DE VISIÓN CON GEMINI (En la nube)
# ==========================================
def procesar_pdf_con_vision(pdf_path, api_key):
    """Convierte el PDF temporal en imágenes y usa Gemini Flash para extraer preguntas y respuestas."""
    try:
        client = genai.Client(api_key=api_key)
        
        with st.spinner("🔄 Procesando páginas del documento en la nube..."):
            imagenes = convert_from_path(pdf_path)
        
        todas_las_preguntas = []
        progress_bar = st.progress(0)
        total_paginas = len(imagenes)
        
        for i, img in enumerate(imagenes):
            progress_bar.progress((i + 1) / total_paginas, text=f"Analizando página {i+1} de {total_paginas} con Visión IA...")
            
            prompt = """
            Analiza esta página de un examen o banco de preguntas aeronáutico. 
            Extrae todas las preguntas, sus alternativas (A, B, C, D) y la respuesta correcta 
            (identificada visualmente por marcas de selección, negritas, pautas o resaltados).
            
            Devuelve estrictamente un objeto JSON válido con la siguiente estructura, sin texto adicional:
            {
              "preguntas": [
                {
                  "pregunta": "Texto de la pregunta",
                  "opciones": ["Opción A", "Opción B", "Opción C", "Opción D"],
                  "respuesta_correcta": "La letra exacta o texto de la opción correcta"
                }
              ]
            }
            Si no hay preguntas en esta página, devuelve {"preguntas": []}.
            """
            
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[img, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1
                ),
            )
            
            if response.text:
                data = json.loads(response.text)
                if "preguntas" in data:
                    todas_las_preguntas.extend(data["preguntas"])
                    
        progress_bar.empty()
        return todas_las_preguntas

    except Exception as e:
        st.error(f"Error al procesar el archivo en la nube: {e}")
        return None

# ==========================================
# INTERFAZ PRINCIPAL
# ==========================================
st.subheader("📂 Sube tu Banco de Preguntas en PDF")
archivo_subido = st.file_uploader("Selecciona el archivo PDF", type=["pdf"])

if archivo_subido is not None:
    # Crear archivo temporal en el entorno online para procesarlo
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(archivo_subido.getvalue())
        tmp_path = tmp_file.name

    st.info(f"Archivo listo para análisis: **{archivo_subido.name}**")

    if st.button("🚀 Extraer Preguntas con Visión IA"):
        if not st.session_state["gemini_api_key"]:
            st.error("⚠️ Configura tu API Key para continuar.")
        else:
            resultados = procesar_pdf_con_vision(tmp_path, st.session_state["gemini_api_key"])
            
            if resultados:
                st.success(f"¡Se han extraído exitosamente {len(resultados)} preguntas!")
                st.session_state["preguntas_extraidas"] = resultados
                
                # Vista previa rápida
                for idx, q in enumerate(resultados[:5]):
                    st.markdown(f"**{idx+1}. {q.get('pregunta')}**")
                    for op in q.get('opciones', []):
                        st.text(f"   - {op}")
                    st.markdown(f"✅ *Respuesta correcta:* **{q.get('respuesta_correcta')}**")
                    st.divider()
