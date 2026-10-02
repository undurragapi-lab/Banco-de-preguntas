import streamlit as st
import fitz  # PyMuPDF para procesamiento de PDFs en memoria
import google.generativeai as genai
from PIL import Image
import json
import numpy as np
import cv2
import random

# Configuración inicial de la página
st.set_page_config(page_title="Simulador de Estudio OMR", layout="wide", page_icon="📚")

# Configurar API de Gemini mediante los secretos de Streamlit Cloud
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# ==========================================
# GESTIÓN DE ESTADOS DE SESIÓN
# ==========================================
if "banco_preguntas" not in st.session_state:
    st.session_state.banco_preguntas = []
if "indice_actual" not in st.session_state:
    st.session_state.indice_actual = 0
if "estados_preguntas" not in st.session_state:
    # Estados: 'blanco' (sin responder), 'correcta', 'incorrecta', 'omitida'
    st.session_state.estados_preguntas = {}
if "respuestas_usuario" not in st.session_state:
    st.session_state.respuestas_usuario = {}
if "buenas" not in st.session_state:
    st.session_state.buenas = 0
if "malas" not in st.session_state:
    st.session_state.malas = 0
if "modo_corregido" not in st.session_state:
    st.session_state.modo_corregido = False


def procesar_imagen_memoria(imagen_bytes):
    """Aplica CLAHE en memoria RAM para amplificar los trazos de lápiz grafito."""
    nparr = np.frombuffer(imagen_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    imagen_mejorada = clahe.apply(gris)
    img_rgb = cv2.cvtColor(imagen_mejorada, cv2.COLOR_GRAY2RGB)
    return Image.fromarray(img_rgb)


def extraer_banco_desde_pdf(bytes_pdf):
    """Extrae texto, alternativas y la marca física de lápiz utilizando Gemini 1.5 Pro."""
    doc = fitz.open(stream=bytes_pdf, filetype="pdf")
    modelo = genai.GenerativeModel('gemini-1.5-pro')
    preguntas_totales = []

    prompt = """
    Eres un sistema experto en OMR (Optical Mark Recognition) y OCR para cuestionarios.
    Analiza esta página del documento. Contiene preguntas, alternativas y respuestas marcadas a mano con lápiz grafito.
    Extrae cada pregunta con sus alternativas y detecta con precisión cuál alternativa tiene la marca física a lápiz (respuesta correcta del documento).
    Devuelve ÚNICAMENTE un arreglo JSON válido con esta estructura estricta, sin texto adicional ni markdown:
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

    barra = st.progress(0, text="Analizando documento y extrayendo marcas de lápiz...")
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
# INTERFAZ DE USUARIO
# ==========================================
st.title("📚 Simulador de Estudio Interactivo")

# Pantalla de Carga si no hay banco activo
if not st.session_state.banco_preguntas:
    st.info("Sube tu documento PDF con el banco de preguntas y alternativas marcadas para iniciar el estudio.")
    archivo_pdf = st.file_uploader("Cargar Banco de Preguntas (PDF)", type=["pdf"])
    
    if archivo_pdf is not None:
        if st.button("Generar Banco de Estudio Aleatorio", type="primary"):
            bytes_data = archivo_pdf.getvalue()
            with st.spinner("Procesando documento y detectando marcas de lápiz..."):
                banco_extraido = extraer_banco_desde_pdf(bytes_data)
                if banco_extraido:
                    random.shuffle(banco_extraido)
                    st.session_state.banco_preguntas = banco_extraido
                    for idx in range(len(banco_extraido)):
                        st.session_state.estados_preguntas[idx] = "blanco"
                    st.success(f"¡Se han estructurado {len(banco_extraido)} preguntas exitosamente!")
                    st.rerun()
                else:
                    st.error("No se pudieron extraer preguntas válidas del documento.")
else:
    # ==========================================
    # SIMULADOR ACTIVO
    # ==========================================
    total_preguntas = len(st.session_state.banco_preguntas)
    idx_actual = st.session_state.indice_actual

    # Estilos CSS inyectados para formatear visualmente los cuadrados numerados del mapa
    st.markdown("""
        <style>
        .grid-container { display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 10px; }
        </style>
    """, unsafe_allow_html=True)

    # Distribución Superior: Estadísticas a la izquierda, Mapa/Cuadrícula en la esquina superior derecha
    col_stats, col_grid_btn = st.columns([0.7, 0.3])
    
    with col_stats:
        st.markdown(
            f"### Pregunta {idx_actual + 1} de {total_preguntas} &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"✅ Buenas: **{st.session_state.buenas}** &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"❌ Malas: **{st.session_state.malas}**"
        )

    with col_grid_btn:
        with st.popover("📋 Mapa de Preguntas (Cuadrícula)"):
            st.markdown("**Leyenda de colores:**")
            st.caption("🔵 Actual | 🟩 Correcta | 🟥 Incorrecto | ⬛ Sin responder")
            
            # Cuadrícula interactiva de botones numerados
            cols_grid = st.columns(6)
            for i in range(total_preguntas):
                estado = st.session_state.estados_preguntas.get(i, "blanco")
                if i == idx_actual:
                    label = f"🔵 {i+1}"
                elif estado == "correcta":
                    label = f"🟩 {i+1}"
                elif estado == "incorrecta":
                    label = f"🟥 {i+1}"
                else:
                    label = f"⬛ {i+1}"
                
                with cols_grid[i % 6]:
                    if st.button(label, key=f"nav_{i}"):
                        st.session_state.indice_actual = i
                        st.session_state.modo_corregido = False
                        st.rerun()

    st.divider()

    # Obtener pregunta activa
    pregunta_actual = st.session_state.banco_preguntas[idx_actual]
    
    # Marcar como actual si estaba en blanco
    if st.session_state.estados_preguntas.get(idx_actual) == "blanco":
        st.session_state.estados_preguntas[idx_actual] = "actual"

    st.subheader(f"Pregunta {idx_actual + 1}:")
    st.write(pregunta_actual.get("pregunta", ""))

    alternativas = pregunta_actual.get("alternativas", {})
    respuesta_correcta_doc = pregunta_actual.get("respuesta_marcada")
    keys_alt = list(alternativas.keys())

    # Recuperar selección previa del usuario
    seleccion_previa = st.session_state.respuestas_usuario.get(idx_actual, keys_alt[0] if keys_alt else None)

    # Renderizado según el estado de corrección
    if st.session_state.modo_corregido:
        st.markdown("---")
        st.markdown("#### Resultado de la Evaluación:")
        for letra, texto in alternativas.items():
            decoracion = f"**{letra})** {texto}"
            if letra == respuesta_correcta_doc:
                decoracion += " &nbsp;&nbsp; **✅ [Correcta]**"
            elif letra == seleccion_previa and letra != respuesta_correcta_doc:
                decoracion += " &nbsp;&nbsp; **❌ [Tu respuesta errónea]**"
            st.markdown(decoracion)
        st.markdown("---")
        
        if respuesta_correcta_doc:
            if seleccion_previa == respuesta_correcta_doc:
                st.success("¡Respuesta correcta!")
            else:
                st.error(f"Respuesta incorrecta. La correcta según el documento original es la **{respuesta_correcta_doc}**.")
        else:
            st.warning("Esta pregunta no tiene una marca de respuesta definida en el documento original.")
    else:
        default_idx = keys_alt.index(seleccion_previa) if seleccion_previa in keys_alt else 0
        respuesta_seleccionada = st.radio(
            "Selecciona una alternativa:",
            options=keys_alt,
            format_func=lambda x: f"{x}) {alternativas[x]}",
            key=f"q_{idx_actual}",
            index=default_idx
        )
        st.session_state.respuestas_usuario[idx_actual] = respuesta_seleccionada

    st.markdown("<br>", unsafe_allow_html=True)

    # ==========================================
    # BOTONES INFERIORES
    # ==========================================
    col_izq, col_der = st.columns([1, 1])

    with col_izq:
        # Botón Omitir (Izquierda): Pasa sin calificar ni alterar el color del mapa principal
        if st.button("↩ Omitir Pregunta", use_container_width=True):
            st.session_state.estados_preguntas[idx_actual] = "blanco"  # Mantiene pendiente para volver más tarde
            st.session_state.modo_corregido = False
            if idx_actual < total_preguntas - 1:
                st.session_state.indice_actual += 1
            else:
                st.session_state.indice_actual = 0
            st.rerun()

    with col_der:
        # Botón de dos pasos: Primero Corrige/Valida, segundo Avanza
        texto_btn = "Corregir / Validar" if not st.session_state.modo_corregido else "Siguiente Pregunta ➡"
        if st.button(texto_btn, type="primary", use_container_width=True):
            if not st.session_state.modo_corregido:
                # PASO 1: Activar corrección, evaluar acierto y actualizar mapa de colores
                st.session_state.modo_corregido = True
                sel_usuario = st.session_state.respuestas_usuario.get(idx_actual)
                
                if respuesta_correcta_doc:
                    if sel_usuario == respuesta_correcta_doc:
                        if st.session_state.estados_preguntas[idx_actual] != "correcta":
                            st.session_state.buenas += 1
                        st.session_state.estados_preguntas[idx_actual] = "correcta"
                    else:
                        if st.session_state.estados_preguntas[idx_actual] != "incorrecta":
                            st.session_state.malas += 1
                        st.session_state.estados_preguntas[idx_actual] = "incorrecta"
                st.rerun()
            else:
                # PASO 2: Avanzar a la siguiente pregunta
                st.session_state.modo_corregido = False
                if idx_actual < total_preguntas - 1:
                    st.session_state.indice_actual += 1
                else:
                    st.session_state.indice_actual = 0
                st.rerun()

    st.divider()
    if st.button("🔄 Cargar un nuevo banco de preguntas"):
        st.session_state.banco_preguntas = []
        st.session_state.indice_actual = 0
        st.session_state.estados_preguntas = {}
        st.session_state.respuestas_usuario = {}
        st.session_state.buenas = 0
        st.session_state.malas = 0
        st.session_state.modo_corregido = False
        st.rerun()
