import os
import re
import json
import random
import hashlib
from datetime import datetime
import streamlit as st
import pandas as pd
import pdfplumber

# --- CONFIGURACIÓN DE PÁGINA (Debe ser el primer comando) ---
st.set_page_config(
    page_title="AeroStudio Pro - Simulador de Vuelo",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- INICIALIZACIÓN DE ESTADOS ---
if "modo_oscuro" not in st.session_state:
    st.session_state.modo_oscuro = False
if "vista" not in st.session_state:
    st.session_state.vista = "home"
if "modo_estudio_data" not in st.session_state:
    st.session_state.modo_estudio_data = None
if "usuario_actual" not in st.session_state:
    st.session_state.usuario_actual = None

# --- ESTILOS CSS ---
css_light = """
    :root {
        --bg-main: #f8fafc;
        --bg-card: #ffffff;
        --accent-blue: #0284c7;
        --accent-hover: #0369a1;
        --text-main: #0f172a;
        --text-muted: #64748b;
        --border-color: #cbd5e1;
        --sidebar-bg: #f1f5f9;
    }
"""
css_dark = """
    :root {
        --bg-main: #121212;
        --bg-card: #1e1e1e;
        --accent-blue: #d97706; 
        --accent-hover: #b45309;
        --text-main: #f5f5f5;
        --text-muted: #a3a3a3;
        --border-color: #333333;
        --sidebar-bg: #1a1a1a;
    }
"""

css_activo = css_dark if st.session_state.modo_oscuro else css_light

st.markdown(f"""
<style>
    {css_activo}
    .stApp {{
        background-color: var(--bg-main);
        color: var(--text-main);
        font-family: 'Inter', sans-serif;
    }}
    header {{visibility: hidden;}}
    div.stButton > button {{
        background: linear-gradient(135deg, var(--accent-blue) 0%, var(--accent-hover) 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.6rem;
        font-weight: 600;
        transition: 0.3s;
    }}
    div.stButton > button[kind="secondary"] {{
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        color: var(--text-main);
    }}
    .stTextInput input, .stSelectbox select, .stPasswordInput input {{
        background-color: var(--bg-card) !important;
        color: var(--text-main) !important;
        border: 1px solid var(--border-color) !important;
    }}
    section[data-testid="stSidebar"] {{
        background-color: var(--sidebar-bg);
        border-right: 1px solid var(--border-color);
    }}
</style>
""", unsafe_allow_html=True)

# --- ALMACENAMIENTO Y UTILIDADES ---
DATA_DIR = "data_bancos"
HISTORY_FILE = "historial_resultados.json"
USERS_FILE = "usuarios.json"
os.makedirs(DATA_DIR, exist_ok=True)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def cargar_usuarios():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
    return {}

def guardar_usuarios(usuarios):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(usuarios, f, ensure_ascii=False, indent=4)

def cargar_banco(nombre_id):
    ruta = os.path.join(DATA_DIR, f"{nombre_id}.json")
    if os.path.exists(ruta):
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None

def guardar_banco(nombre_id, data):
    ruta = os.path.join(DATA_DIR, f"{nombre_id}.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def listar_bancos():
    if not os.path.exists(DATA_DIR):
        return []
    return [f.replace(".json", "") for f in os.listdir(DATA_DIR) if f.endswith(".json")]

def eliminar_banco(nombre_id):
    ruta = os.path.join(DATA_DIR, f"{nombre_id}.json")
    if os.path.exists(ruta):
        os.remove(ruta)

# --- NUEVO MOTOR DE EXTRACCIÓN DE PDF ---
def extraer_preguntas_de_pdf(pdf_file):
    texto_completo = ""
    with pdfplumber.open(pdf_file) as pdf:
        for pagina in pdf.pages:
            t = pagina.extract_text(layout=True)
            if t:
                texto_completo += t + "\n"

    mapa_claves_finales = {}
    patron_pauta = re.compile(r'\b(\d{1,4})[\.\-\:\)]?\s*([A-D])\b', re.IGNORECASE)
    
    for linea in texto_completo.split('\n'):
        linea = linea.strip()
        if len(linea) < 50 and patron_pauta.search(linea):
            for num, letra in patron_pauta.findall(linea):
                mapa_claves_finales[int(num)] = letra.upper()

    bloques = re.split(r'\n(?=\d{1,4}[\.\-\)]\s)', texto_completo)
    preguntas_parsed = []
    patron_alt = re.compile(r'^[\*\-\>\s]*([A-D])[\.\-\)]\s*(.*)', re.IGNORECASE | re.DOTALL)
    patrones_correcta_inline = [r'\*', r'\(x\)', r'\[x\]', r'->', r'respuesta:', r'correcta:']

    for bloque in bloques:
        bloque = bloque.strip()
        if not bloque: continue
            
        match_num = re.match(r'^(\d{1,4})[\.\-\)]\s*(.*)', bloque, re.DOTALL)
        if not match_num: continue
            
        num_pregunta = int(match_num.group(1))
        lineas = match_num.group(2).split('\n')
        enunciado_lineas, alternativas = [], []
        alt_actual = None
        
        for linea in lineas:
            linea_limpia = linea.strip()
            if not linea_limpia: continue
                
            match_alt = patron_alt.match(linea_limpia)
            if match_alt:
                if alt_actual: alternativas.append(alt_actual)
                es_marcada = any(re.search(p, linea_limpia, re.IGNORECASE) for p in patrones_correcta_inline)
                alt_actual = {"letra": match_alt.group(1).upper(), "texto": match_alt.group(2).strip(), "marcada": es_marcada}
            else:
                if alt_actual:
                    if any(re.search(p, linea_limpia, re.IGNORECASE) for p in patrones_correcta_inline):
                        alt_actual["marcada"] = True
                    else:
                        alt_actual["texto"] += " " + linea_limpia
                else:
                    enunciado_lineas.append(linea_limpia)
                    
        if alt_actual: alternativas.append(alt_actual)

        correcta_idx = None
        if num_pregunta in mapa_claves_finales:
            letra_clave = mapa_claves_finales[num_pregunta]
            for idx, alt in enumerate(alternativas):
                if alt["letra"] == letra_clave:
                    correcta_idx, alt["marcada"] = idx, True
                    break
                    
        if correcta_idx is None:
            for idx, alt in enumerate(alternativas):
                if alt["marcada"]:
                    correcta_idx = idx
                    break

        for alt in alternativas:
            alt["texto"] = re.sub(r'^\s*[\*\-\>]\s*', '', alt["texto"])

        if " ".join(enunciado_lineas).strip() and len(alternativas) >= 2:
            preguntas_parsed.append({
                "pregunta": " ".join(enunciado_lineas).strip(),
                "alternativas": alternativas,
                "correcta": correcta_idx
            })

    return preguntas_parsed

# --- CONTROL DE ACCESO (LOGIN/REGISTRO) ---
if st.session_state.usuario_actual is None:
    st.markdown("<h2 style='text-align: center; color: var(--accent-blue); padding-top: 50px;'>✈️ AeroStudio Pro</h2>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        tab_login, tab_registro = st.tabs(["Iniciar Sesión", "Crear Cuenta"])
        usuarios_db = cargar_usuarios()
        
        with tab_login:
            email_in = st.text_input("Correo electrónico:", key="l_email")
            pass_in = st.text_input("Contraseña:", type="password", key="l_pass")
            if st.button("Ingresar", use_container_width=True):
                email_in = email_in.strip().lower()
                if email_in in usuarios_db and usuarios_db[email_in]["password"] == hash_password(pass_in):
                    st.session_state.usuario_actual = email_in
                    st.rerun()
                else:
                    st.error("Credenciales incorrectas.")
                    
        with tab_registro:
            reg_nom = st.text_input("Nombre completo:", key="r_nom")
            reg_email = st.text_input("Correo:", key="r_email")
            reg_pass = st.text_input("Contraseña:", type="password", key="r_pass")
            if st.button("Registrarse", use_container_width=True):
                reg_email = reg_email.strip().lower()
                if reg_email in usuarios_db:
                    st.error("El correo ya existe.")
                elif reg_email and reg_pass:
                    usuarios_db[reg_email] = {"nombre": reg_nom, "password": hash_password(reg_pass)}
                    guardar_usuarios(usuarios_db)
                    st.session_state.usuario_actual = reg_email
                    st.success("Cuenta creada.")
                    st.rerun()
    st.stop()

# --- BARRA LATERAL ---
usuarios_db = cargar_usuarios()
nombre_usuario = usuarios_db.get(st.session_state.usuario_actual, {}).get("nombre", "Piloto")

with st.sidebar:
    st.markdown(f"### 👨‍✈ {nombre_usuario}")
    st.divider()
    if st.button("🌙 Modo Nocturno" if not st.session_state.modo_oscuro else "☀️ Modo Diurno", use_container_width=True):
        st.session_state.modo_oscuro = not st.session_state.modo_oscuro
        st.rerun()
    
    if st.button("🏠 Inicio", use_container_width=True):
        st.session_state.vista = "home"
        st.rerun()
        
    st.divider()
    if st.button("🚪 Salir", type="secondary", use_container_width=True):
        st.session_state.usuario_actual = None
        st.session_state.modo_estudio_data = None
        st.rerun()

# --- VISTA: ESTUDIO ---
if st.session_state.vista == "estudio" and st.session_state.modo_estudio_data:
    estudio = st.session_state.modo_estudio_data
    preguntas = estudio["preguntas"]
    idx_actual = estudio["idx_actual"]
    
    if "resp_dict" not in st.session_state:
        st.session_state.resp_dict = {}
        
    resp_dict = st.session_state.resp_dict
    q_actual = preguntas[idx_actual]
    total = len(preguntas)
    
    st.progress((idx_actual + 1) / total)
    st.markdown(f"**Pregunta {idx_actual + 1} de {total}**")
    st.markdown(f"### {q_actual['pregunta']}")
    
    estado_q = resp_dict.get(idx_actual, {"corregido": False, "elegida": -1})
    opciones = [(-1, "Selecciona una alternativa...")] + [(i, f"{alt['letra']}.- {alt['texto']}") for i, alt in enumerate(q_actual["alternativas"])]
    
    current_index = 0
    for idx, (orig_i, _) in enumerate(opciones):
        if orig_i == estado_q["elegida"]:
            current_index = idx
            break

    seleccion = st.radio("Alternativas:", options=opciones, format_func=lambda x: x[1], index=current_index, disabled=estado_q["corregido"])
    
    if q_actual.get("correcta") is None:
        st.warning("⚠️ Pregunta sin respuesta en la pauta original.")
        
    if estado_q["corregido"]:
        idx_correcta = q_actual.get("correcta")
        if idx_correcta == estado_q["elegida"]:
            st.success("🎯 ¡Correcto!")
        else:
            letra_ok = q_actual["alternativas"][idx_correcta]["letra"] if idx_correcta is not None else "?"
            st.error(f"❌ Incorrecto. La correcta era la **{letra_ok}**.")
            
    col1, col2 = st.columns(2)
    with col1:
        if not estado_q["corregido"] and st.button("Validar Respuesta", type="primary", use_container_width=True):
            if seleccion[0] != -1:
                st.session_state.resp_dict[idx_actual] = {"corregido": True, "elegida": seleccion[0]}
                st.rerun()
            else:
                st.warning("Selecciona una opción primero.")
                
    with col2:
        if st.button("Siguiente ➡️" if estado_q["corregido"] else "Omitir", use_container_width=True):
            if idx_actual < total - 1:
                st.session_state.modo_estudio_data["idx_actual"] += 1
                st.rerun()
            else:
                st.session_state.vista = "home"
                st.success("¡Prueba finalizada!")
                st.rerun()

# --- VISTA: HOME ---
elif st.session_state.vista == "home":
    st.title("📚 Centro de Entrenamiento")
    st.divider()

    uploaded_file = st.file_uploader("Procesar nuevo manual (PDF)", type=["pdf"])
    nombre_prueba = st.text_input("Nombre del Banco de Preguntas:")
    
    if st.button("Extraer Banco de Preguntas", type="primary"):
        if uploaded_file and nombre_prueba:
            with st.spinner("Analizando pautas y cruzando datos..."):
                preguntas_extraidas = extraer_preguntas_de_pdf(uploaded_file)
                if preguntas_extraidas:
                    id_limpio = re.sub(r'[^a-zA-Z0-9_\-]', '_', nombre_prueba)
                    guardar_banco(id_limpio, {"nombre": nombre_prueba, "preguntas": preguntas_extraidas})
                    st.success(f"¡Éxito! {len(preguntas_extraidas)} preguntas extraídas.")
                    st.rerun()
                else:
                    st.error("No se detectó un formato válido de preguntas.")
        else:
            st.warning("Falta el PDF o el nombre.")

    st.subheader("Bancos Disponibles")
    bancos = listar_bancos()
    for b_id in bancos:
        banco_data = cargar_banco(b_id)
        if not banco_data: continue
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown(f"**{banco_data.get('nombre', b_id)}** — {len(banco_data.get('preguntas', []))} preguntas")
        with col2:
            if st.button("🚀 Iniciar", key=f"start_{b_id}", use_container_width=True):
                preg = banco_data.get("preguntas", [])
                if preg:
                    st.session_state.resp_dict = {}
                    st.session_state.modo_estudio_data = {"preguntas": preg, "idx_actual": 0}
                    st.session_state.vista = "estudio"
                    st.rerun()
        st.divider()
