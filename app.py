import streamlit as st
import fitz  # PyMuPDF para procesar PDFs
import google.generativeai as genai
from PIL import Image
import json
import numpy as np
import cv2
import random

# Configuración de la página
st.set_page_config(page_title="AeroStudio Pro - Simulador", layout="wide", page_icon="✈️")

# Configurar API de Gemini utilizando los secretos de Streamlit
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# Inicializar Estados de la Sesión
if "banco_preguntas" not in st.session_state:
    st.session_state.banco_preguntas = []
if "indice_actual" not in st.session_state:
    st.session_state.indice_actual = 0
if "respuestas_usuario" not in st.session_state:
    st.session_state.respuestas_usuario = {}
if "estados_preguntas" not in st.session_state:
    # 'blanco', 'actual', 'correcta', 'incorrecta', 'omitida'
    st.session_state.estados_preguntas = {}
if "buenas" not in st.session_state:
    st.session_state.buenas = 0
if "malas" not in st.session_state:
    st.session_state.malas = 0
if "modo_corregido" not in st.session_state:
    st.session_state.modo_corregido = False


def procesar_imagen_memoria(imagen_bytes):
    """Aplica CLAHE para realzar trazos de lápiz grafito en la imagen escaneada."""
    nparr = np.frombuffer(imagen_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    imagen_mejorada = clahe.apply(gris)
    img_rgb = cv2.cvtColor(imagen_mejorada, cv2.COLOR_GRAY2RGB)
    return Image.fromarray(img_rgb)


def extraer_banco_desde_pdf(bytes_pdf):
    """Extrae texto, alternativas y la respuesta marcada a lápiz usando Gemini 1.5 Pro."""
    doc = fitz.open(stream=bytes_pdf, filetype="pdf")
    modelo = genai.GenerativeModel('gemini-1.5-pro')
    preguntas_totales = []

    prompt = """
    Eres un sistema experto en OMR (Optical Mark Recognition) y OCR para exámenes.
    Analiza esta página del documento. Contiene preguntas, alternativas y respuestas marcadas a mano con lápiz grafito.
    Extrae cada pregunta con sus alternativas y detecta con precisión cuál alternativa tiene la marca física a lápiz (respuesta correcta del documento).
    Devuelve ÚNICAMENTE un arreglo JSON válido con esta estructura estricta, sin markdown adicional:
    [
      {
        "numero": 1,
        "pregunta": "Texto de la pregunta",
        "alternativas": {
          "A": "Texto A",
          "B": "Texto B",
          "C": "Texto C"
        },
        "respuesta_marcada": "B"
      }
    ]
    Si no hay marca, asigna null a "respuesta_marcada".
    """
    configuracion = genai.GenerationConfig(response_mime_type="application/json")

    barra = st.progress(0, text="Analizando páginas del PDF y extrayendo marcas de lápiz...")
    total_paginas = len(doc)

    for i in range(total_paginas):
        pagina = doc.load_page(i)
        pix = pagina.get_pixmap(dpi=150)
        img_bytes = pix.tobytes("png")
        
        imagen_pil = procesar_imagen_memoria(img_bytes)
        
        respuesta = modelo.generate_content([prompt, imagen_pil], generation_config=configuracion)
        try:
            datos_pagina = json.loads(respuesta.text)
            if isinstance(datos_pagina, list):
                preguntas_totales.extend(datos_pagina)
        except Exception:
            pass
        
        barra.progress((i + 1) / total_paginas, text=f"Procesando página {i+1} de {total_paginas}...")

    barra.empty()
    return preguntas_totales


# ==========================================
# INTERFAZ PRINCIPAL
# ==========================================
st.title("✈️ AeroStudio Pro - Simulador de Exámenes")

# Si no hay un banco cargado, mostrar la pantalla de subida de PDF
if not st.session_state.banco_preguntas:
    st.info("Sube tu documento PDF con el banco de preguntas y alternativas marcadas para iniciar la sesión de estudio.")
    archivo_pdf = st.file_uploader("Cargar Banco de Preguntas (PDF)", type=["pdf"])
    
    if archivo_pdf is not None:
        if st.button("Generar Banco de Estudio Aleatorio", type="primary"):
            bytes_data = archivo_pdf.getvalue()
            with st.spinner("Procesando documento y extrayendo marcas de lápiz..."):
                banco_extraido = extraer_banco_desde_pdf(bytes_data)
                if banco_extraido:
                    # Barajar aleatoriamente el banco para simular el test
                    random.shuffle(banco_extraido)
                    st.session_state.banco_preguntas = banco_extraido
                    # Inicializar estados de los cuadrados
                    for idx in range(len(banco_extraido)):
                        st.session_state.estados_preguntas[idx] = "blanco"
                    st.success(f"¡Se han cargado y estructurado {len(banco_extraido)} preguntas exitosamente!")
                    st.rerun()
                else:
                    st.error("No se pudieron extraer preguntas válidas. Verifica el archivo.")
else:
    # ==========================================
    # ZONA DE SIMULADOR ACTIVO (TIPO DAYPO / PREPWARE)
    # ==========================================
    total_preguntas = len(st.session_state.banco_preguntas)
    idx_actual = st.session_state.indice_actual

    # Barra superior de estadísticas y botón de cuadrícula en esquina superior derecha
    col_stats, col_grid_btn = st.columns([0.8, 0.2])
    
    with col_stats:
        st.markdown(
            f"### Pregunta {idx_actual + 1} de {total_preguntas} &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"✅ Buenas: **{st.session_state.buenas}** &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"❌ Malas: **{st.session_state.malas}**"
        )

    with col_grid_btn:
        with st.popover("📋 Panel de Navegación"):
            st.write("**Mapa de Preguntas**")
            st.caption("Verde: Correcta | Rojo: Incorrecto | Azul: Actual | Negro: Sin responder")
            
            # Dibujar la cuadrícula de cuadrados con colores
            cols_grid = st.columns(6)
            for i in range(total_preguntas):
                estado = st.session_state.estados_preguntas.get(i, "blanco")
                if i == idx_actual:
                    color_badge = "🔵"  # Actual
                elif estado == "correcta":
                    color_badge = "🟩"  # Verde
                elif estado == "incorrecta":
                    color_badge = "🟥"  # Rojo
                elif estado == "omitida":
                    color_badge = "🟨"  # Omitida
                else:
                    color_badge = "⬛"  # Negro / Blanco
                
                with cols_grid[i % 6]:
                    if st.button(f"{i+1}", key=f"nav_{i}"):
                        st.session_state.indice_actual = i
                        st.session_state.modo_corregido = False
                        st.rerun()

    st.divider()

    # Obtener la pregunta actual
    pregunta_actual = st.session_state.banco_preguntas[idx_actual]
    
    # Marcar estado actual como 'actual' en el mapa si no está resuelta
    if st.session_state.estados_preguntas.get(idx_actual) == "blanco":
        st.session_state.estados_preguntas[idx_actual] = "actual"

    # Mostrar Pregunta
    st.subheader(f"Pregunta {idx_actual + 1}:")
    st.write(pregunta_actual.get("pregunta", ""))

    # Opciones de Alternativas
    alternativas = pregunta_actual.get("alternativas", {})
    respuesta_seleccionada = st.radio(
        "Selecciona una alternativa:",
        options=list(alternativas.keys()),
        format_func=lambda x: f"{x}) {alternativas[x]}",
        key=f"q_{idx_actual}"
    )

    respuesta_correcta_documento = pregunta_actual.get("respuesta_marcada")

    # Mostrar retroalimentación si ya se presionó "Siguiente / Corregir"
    if st.session_state.modo_corregido:
        if respuesta_correcta_documento:
            if respuesta_seleccionada == respuesta_correcta_documento:
                st.success(f"✔ ¡Correcto! La alternativa marcada en el documento es la {respuesta_correcta_documento}.")
            else:
                st.error(f"✖ Incorrecto. La respuesta correcta según el documento marcado es la **{respuesta_correcta_documento}**.")
        else:
            st.warning("⚠️ Esta pregunta no tenía una respuesta marcada explícitamente en el documento original.")

    st.markdown("<br>", unsafe_allow_html=True)

    # Botones inferiores: Omitir (Izquierda) y Siguiente/Corregir (Derecha)
    col_izq, col_der = st.columns([1, 1])

    with col_izq:
        if st.button("↩ Omitir Pregunta", use_container_width=True):
            # Omitir: no califica, no cambia a verde/rojo, solo pasa a la siguiente
            st.session_state.estados_preguntas[idx_actual] = "omitida"
            if idx_actual < total_preguntas - 1:
                st.session_state.indice_actual += 1
            else:
                st.session_state.indice_actual = 0
            st.session_state.modo_corregido = False
            st.rerun()

    with col_der:
        texto_boton = "Siguiente / Corregir" if not st.session_state.modo_corregido else "Siguiente Pregunta ➡"
        if st.button(texto_boton, type="primary", use_container_width=True):
            if not st.session_state.modo_corregido:
                # Activar corrección
                st.session_state.modo_corregido = True
                
                # Evaluar respuesta
                if respuesta_correcta_documento:
                    if respuesta_seleccionada == respuesta_correcta_documento:
                        if st.session_state.estados_preguntas[idx_actual] != "correcta":
                            st.session_state.buenas += 1
                        st.session_state.estados_preguntas[idx_actual] = "correcta"
                    else:
                        if st.session_state.estados_preguntas[idx_actual] != "incorrecta":
                            st.session_state.malas += 1
                        st.session_state.estados_preguntas[idx_actual] = "incorrecta"
                st.rerun()
            else:
                # Avanzar a la siguiente pregunta
                st.session_state.modo_corregido = False
                if idx_actual < total_preguntas - 1:
                    st.session_state.indice_actual += 1
                else:
                    st.session_state.indice_actual = 0  # Volver al inicio si llega al final
                st.rerun()

    # Botón para reiniciar el test completo
    st.divider()
    if st.button("🔄 Cargar un nuevo banco de preguntas"):
        st.session_state.banco_preguntas = []
        st.session_state.indice_actual = 0
        st.session_state.respuestas_usuario = {}
        st.session_state.estados_preguntas = {}
        st.session_state.buenas = 0
        st.session_state.malas = 0
        st.session_state.modo_corregido = False
        st.rerun()
