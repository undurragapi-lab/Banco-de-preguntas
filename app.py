import streamlit as st
import fitz  # PyMuPDF para procesamiento de PDFs en memoria
import google.generativeai as genai
from PIL import Image
import json
import re
import numpy as np
import cv2
import random

# Configuración inicial de la página
st.set_page_config(page_title="AeroStudio Pro - Simulador de Estudio", layout="wide", page_icon="📚")

# Configurar API de Gemini mediante los secretos de Streamlit Cloud
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# ==========================================
# ESTILOS CSS PERSONALIZADOS (DISEÑO VISUAL)
# ==========================================
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stats-container {
        background: #ffffff;
        padding: 15px 20px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        font-weight: bold;
        color: #2c3e50;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .question-card {
        background: #ffffff;
        padding: 25px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        margin-bottom: 20px;
        border-left: 5px solid #3498db;
    }
    .feedback-correct {
        background-color: #d4edda;
        color: #155724;
        padding: 10px 15px;
        border-radius: 6px;
        border-left: 4px solid #28a745;
        margin-top: 10px;
    }
    .feedback-incorrect {
        background-color: #f8d7da;
        color: #721c24;
        padding: 10px 15px;
        border-radius: 6px;
        border-left: 4px solid #dc3545;
        margin-top: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# GESTIÓN DE ESTADOS DE SESIÓN
# ==========================================
if "banco_preguntas" not in st.session_state:
    st.session_state.banco_preguntas = []
if "indice_actual" not in st.session_state:
    st.session_state.indice_actual = 0
if "estados_preguntas" not in st.session_state:
    st.session_state.estados_preguntas = {}
if "respuestas_usuario" not in st.session_state:
    st.session_state.respuestas_usuario = {}
if "buenas" not in st.session_state:
    st.session_state.buenas = 0
if "malas" not in st.session_state:
    st.session_state.malas = 0
if "modo_corregido" not in st.session_state:
    st.session_state.modo_corregido = False


def obtener_modelo_gemini():
    """Selecciona de forma dinámica cualquier versión disponible de Gemini con soporte multimodal."""
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                if any(ver in m.name for ver in ['flash', 'pro', '2.0', '1.5']):
                    return genai.GenerativeModel(m.name)
    except Exception:
        pass
    
    # Lista de respaldo robusta multi-versión
    for modelo_nombre in ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-pro']:
        try:
            return genai.GenerativeModel(modelo_nombre)
        except Exception:
            continue
            
    return genai.GenerativeModel('gemini-1.5-flash')


def procesar_imagen_memoria(imagen_bytes):
    """Aplica CLAHE en memoria RAM para amplificar los trazos de lápiz grafito."""
    nparr = np.frombuffer(imagen_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return Image.frombytes("RGB", (100, 100), (255, 255, 255))
    gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    imagen_mejorada = clahe.apply(gris)
    img_rgb = cv2.cvtColor(imagen_mejorada, cv2.COLOR_GRAY2RGB)
    return Image.fromarray(img_rgb)


def limpiar_y_parsear_json(texto_respuesta):
    """Limpia etiquetas de markdown y extrae un JSON válido de manera segura."""
    if not texto_respuesta:
        return []
    try:
        # Remover bloques de código markdown
        texto_limpio = re.sub(r'```(?:json)?\s*|\s*```', '', texto_respuesta).strip()
        return json.loads(texto_limpio)
    except Exception:
        # Intento alternativo buscando corchetes de arreglo JSON
        match = re.search(r'\[\s*\{.*\}\s*\]', texto_respuesta, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
        return []


def extraer_banco_desde_pdf(bytes_pdf):
    """Extrae texto, alternativas y marcas de lápiz usando cualquier versión compatible de Gemini."""
    doc = fitz.open(stream=bytes_pdf, filetype="pdf")
    modelo = obtener_modelo_gemini()
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
        try:
            respuesta = modelo.generate_content([prompt, imagen_pil], generation_config=configuracion)
            datos_pagina = limpiar_y_parsear_json(respuesta.text)
            if isinstance(datos_pagina, list):
                preguntas_totales.extend(datos_pagina)
        except Exception:
            pass
        
        barra.progress((i + 1) / total_paginas, text=f"Procesando página {i+1} de {total_paginas}...")

    barra.empty()
    return preguntas_totales


# ==========================================
# INTERFAZ DE USUARIO PRINCIPAL
# ==========================================
st.title("📚 AeroStudio Pro — Simulador de Estudio")

if not st.session_state.banco_preguntas:
    st.markdown("### 🚀 Bienvenido al entorno de estudio interactivo")
    st.info("Sube tu documento PDF que contenga el banco de preguntas y alternativas marcadas a lápiz para iniciar.")
    archivo_pdf = st.file_uploader("Cargar Banco de Preguntas (PDF)", type=["pdf"])
    
    if archivo_pdf is not None:
        if st.button("Generar Banco de Estudio Aleatorio", type="primary"):
            bytes_data = archivo_pdf.getvalue()
            with st.spinner("Procesando documento con Gemini..."):
                banco_extraido = extraer_banco_desde_pdf(bytes_data)
                if banco_extraido:
                    random.shuffle(banco_extraido)
                    st.session_state.banco_preguntas = banco_extraido
                    st.session_state.estados_preguntas = {idx: "blanco" for idx in range(len(banco_extraido))}
                    st.session_state.indice_actual = 0
                    st.success(f"¡Se han estructurado {len(banco_extraido)} preguntas exitosamente!")
                    st.rerun()
                else:
                    st.error("No se pudieron extraer preguntas válidas del documento. Intenta nuevamente.")
else:
    total_preguntas = len(st.session_state.banco_preguntas)
    
    # Validación de seguridad de índices
    if st.session_state.indice_actual >= total_preguntas:
        st.session_state.indice_actual = 0
    idx_actual = st.session_state.indice_actual

    # Distribución Superior: Estadísticas y Mapa de Preguntas
    col_stats, col_grid_btn = st.columns([0.65, 0.35])
    
    with col_stats:
        st.markdown(
            f"""
            <div class="stats-container">
                <span>Pregunta {idx_actual + 1} de {total_preguntas}</span>
                <span style="color: #27ae60;">✅ Buenas: {st.session_state.buenas}</span>
                <span style="color: #c0392b;">❌ Malas: {st.session_state.malas}</span>
            </div>
            """,
            unsafe_allow_html=True
        )

    with col_grid_btn:
        with st.popover("📋 Mapa de Preguntas (Cuadrícula)"):
            st.markdown("**Leyenda de estados:**")
            st.caption("🔵 Actual | 🟩 Correcta | 🟥 Incorrecto | ⬛ Sin responder")
            
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

    st.markdown("<br>", unsafe_allow_html=True)

    # Obtener pregunta activa con seguridad
    pregunta_actual = st.session_state.banco_preguntas[idx_actual]
    
    if st.session_state.estados_preguntas.get(idx_actual) == "blanco":
        st.session_state.estados_preguntas[idx_actual] = "actual"

    # Tarjeta Principal de la Pregunta
    st.markdown(
        f"""
        <div class="question-card">
            <h4>Pregunta {idx_actual + 1}</h4>
            <p style="font-size: 1.1rem; color: #2c3e50;">{pregunta_actual.get("pregunta", "")}</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    alternativas = pregunta_actual.get("alternativas", {})
    respuesta_correcta_doc = pregunta_actual.get("respuesta_marcada")
    keys_alt = list(alternativas.keys())

    if not keys_alt:
        st.error("Esta pregunta no contiene alternativas válidas.")
    else:
        seleccion_previa = st.session_state.respuestas_usuario.get(idx_actual, keys_alt[0])

        if st.session_state.modo_corregido:
            st.markdown("---")
            st.markdown("#### Resultado de la Evaluación:")
            for letra, texto in alternativas.items():
                decoracion = f"**{letra})** {texto}"
                if letra == respuesta_correcta_doc:
                    decoracion += " &nbsp;&nbsp; **✅ [Respuesta Correcta]**"
                elif letra == seleccion_previa and letra != respuesta_correcta_doc:
                    decoracion += " &nbsp;&nbsp; **❌ [Tu Respuesta Errónea]**"
                st.markdown(decoracion)
            st.markdown("---")
            
            if respuesta_correcta_doc:
                if seleccion_previa == respuesta_correcta_doc:
                    st.markdown('<div class="feedback-correct">✔ ¡Excelente! Tu respuesta coincide con la marca del documento.</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="feedback-incorrect">✖ Incorrecto. La alternativa correcta marcada en el documento original era la <b>{respuesta_correcta_doc}</b>.</div>', unsafe_allow_html=True)
            else:
                st.warning("⚠️ Esta pregunta no tiene una marca de respuesta definida en el documento original.")
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
        if st.button("↩ Omitir Pregunta", use_container_width=True):
            st.session_state.estados_preguntas[idx_actual] = "blanco"
            st.session_state.modo_corregido = False
            st.session_state.indice_actual = (idx_actual + 1) % total_preguntas
            st.rerun()

    with col_der:
        texto_btn = "Corregir / Validar" if not st.session_state.modo_corregido else "Siguiente Pregunta ➡"
        if st.button(texto_btn, type="primary", use_container_width=True):
            if not st.session_state.modo_corregido:
                st.session_state.modo_corregido = True
                sel_usuario = st.session_state.respuestas_usuario.get(idx_actual)
                
                if respuesta_correcta_doc:
                    if sel_usuario == respuesta_correcta_doc:
                        if st.session_state.estados_preguntas.get(idx_actual) != "correcta":
                            st.session_state.buenas += 1
                        st.session_state.estados_preguntas[idx_actual] = "correcta"
                    else:
                        if st.session_state.estados_preguntas.get(idx_actual) != "incorrecta":
                            st.session_state.malas += 1
                        st.session_state.estados_preguntas[idx_actual] = "incorrecta"
                st.rerun()
            else:
                st.session_state.modo_corregido = False
                st.session_state.indice_actual = (idx_actual + 1) % total_preguntas
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
