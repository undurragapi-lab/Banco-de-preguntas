import os
import json
import tempfile
import streamlit as st
from PIL import Image
from pdf2image import convert_from_path
from google import genai
from google.genai import types

# Configuración de la página
st.set_page_config(page_title="Lector Inteligente de Exámenes Aeronáuticos", page_icon="✈️", layout="wide")

st.title("✈️ Sistema de Carga y Lectura de Exámenes (Con Visión IA)")

# ==========================================
# GESTIÓN DE LA API KEY (Sin pedirla a cada rato)
# ==========================================
st.sidebar.header("🔑 Configuración de IA")

# 1. Intentar cargar la key desde los secrets de Streamlit si existen (.streamlit/secrets.toml)
default_api_key = st.secrets.get("GEMINI_API_KEY", "")

# 2. Si no está en secrets, usar lo que esté guardado en la sesión del usuario
if "gemini_api_key" not in st.session_state:
    st.session_state["gemini_api_key"] = default_api_key

# Campo en la barra lateral para ingresar la clave si no está configurada
user_api_key = st.sidebar.text_input(
    "Google Gemini API Key",
    value=st.session_state["gemini_api_key"],
    type="password",
    help="Obtén tu clave gratuita en Google AI Studio. Una vez ingresada, quedará guardada en tu sesión."
)

# Actualizar el session_state para que no se pierda al navegar o interactuar
if user_api_key:
    st.session_state["gemini_api_key"] = user_api_key
    st.sidebar.success("API Key cargada correctamente en la sesión.", icon="✅")
else:
    st.sidebar.warning("Por favor, ingresa tu API Key para habilitar la lectura visual por IA.")

# ==========================================
# FUNCIÓN DE VISIÓN CON GEMINI (SDK Oficial)
# ==========================================
def procesar_pdf_con_vision(pdf_path, api_key):
    """Convierte el PDF en imágenes y usa Gemini para extraer preguntas y respuestas."""
    try:
        # Inicializar el cliente de Gemini con la API Key del usuario
        client = genai.Client(api_key=api_key)
        
        with st.spinner("🔄 Convirtiendo PDF a imágenes para análisis visual..."):
            # Convertir todas las páginas del PDF a imágenes PIL
            imagenes = convert_from_path(pdf_path)
        
        todas_las_preguntas = []
        
        # Procesar las páginas (puedes limitar o iterar sobre todas)
        progress_bar = st.progress(0)
        total_paginas = len(imagenes)
        
        for i, img in enumerate(imagenes):
            # Actualizar barra de progreso
            progress_bar.progress((i + 1) / total_paginas, text=f"Analizando página {i+1} de {total_paginas} con IA...")
            
            # Prompt estructurado para forzar un JSON exacto
            prompt = """
            Analiza esta página de un examen o banco de preguntas aeronáutico. 
            Extrae todas las preguntas, sus alternativas (A, B, C, D u otras) y la respuesta correcta 
            (identificada visualmente por marcas de selección, negritas, pautas o resaltados).
            
            Debes devolver estrictamente un objeto JSON válido con la siguiente estructura, sin texto adicional antes ni después:
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
            
            # Llamada al modelo multimodal (Gemini 2.5 Flash o Pro)
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[img, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1
                ),
            )
            
            # Parsear el resultado JSON devuelto por la IA
            if response.text:
                data = json.loads(response.text)
                if "preguntas" in data:
                    todas_las_preguntas.extend(data["preguntas"])
                    
        progress_bar.empty()
        return todas_las_preguntas

    except Exception as e:
        st.error(f"Error al procesar con la IA: {e}")
        return None

# ==========================================
# INTERFAZ PRINCIPAL DE CARGA
# ==========================================
st.subheader("📂 Sube tu Banco de Preguntas (PDF)")
archivo_subido = st.file_uploader("Selecciona el archivo PDF del examen", type=["pdf"])

if archivo_subido is not None:
    # Guardar temporalmente el PDF subido para que la librería pueda leerlo
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(archivo_subido.getvalue())
        tmp_path = tmp_file.name

    st.info(f"Archivo cargado: **{archivo_subido.name}**")

    # Botón para activar el motor de visión
    if st.button("🚀 Extraer Preguntas con Visión IA"):
        if not st.session_state["gemini_api_key"]:
            st.error("⚠️ Debes configurar tu API Key en la barra lateral antes de usar la visión artificial.")
        else:
            resultados = procesar_pdf_con_vision(tmp_path, st.session_state["gemini_api_key"])
            
            if resultados:
                st.success(f"¡Se han extraído exitosamente {len(resultados)} preguntas con sus respuestas!")
                
                # Mostrar un preview de las primeras preguntas extraídas
                st.write("### Vista previa de preguntas detectadas:")
                for idx, q in enumerate(resultados[:5]): # Mostrar las primeras 5
                    st.markdown(f"**{idx+1}. {q.get('pregunta')}**")
                    for op in q.get('opciones', []):
                        st.text(f"   - {op}")
                    st.markdown(f"✅ *Respuesta correcta:* **{q.get('respuesta_correcta')}**")
                    st.divider()
                
                # Guardar en session_state o descargar como JSON para tu app
                st.session_state["preguntas_extraidas"] = resultados
