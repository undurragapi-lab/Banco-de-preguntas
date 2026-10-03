import os
import re
import json
import random
import time
import tempfile
import base64
import hashlib
from datetime import datetime
import streamlit as st
import pandas as pd


# --- IMPORTACIÓN BLINDADA DE GEMINI ---
GENAI_DISPONIBLE = False
genai = None
types = None

try:
    from google import genai
    from google.genai import types
    GENAI_DISPONIBLE = True
except ImportError:
    GENAI_DISPONIBLE = False


# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="AeroStudio Pro - Centro de Pruebas",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded"
)


# --- CONFIGURACIÓN PWA INLINE ---
manifest_dict = {
    "name": "AeroStudio Pro",
    "short_name": "AeroStudio",
    "start_url": "/",
    "display": "standalone",
    "background_color": "#162032",
    "theme_color": "#d97706",
    "icons": [
        {
            "src": "https://img.icons8.com/color/512/airplane-take-off.png",
            "sizes": "512x512",
            "type": "image/png"
        }
    ]
}
manifest_bytes = json.dumps(manifest_dict).encode("utf-8")
manifest_b64 = base64.b64encode(manifest_bytes).decode("utf-8")
manifest_data_uri = f"data:application/manifest+json;base64,{manifest_b64}"


# --- GESTIÓN DE ESTADOS DE SESIÓN ---
if "modo_oscuro" not in st.session_state:
    st.session_state.modo_oscuro = True  # Modo oscuro por defecto con azul marino y dorado
if "vista" not in st.session_state:
    st.session_state.vista = "home"
if "modo_estudio_data" not in st.session_state:
    st.session_state.modo_estudio_data = None


# --- ESTILOS CSS REFINADOS (MODO CLARO Y MODO OSCURO AZUL MARINO + DORADO) ---
css_light = """
    :root {
        --bg-main: #f8fafc;
        --bg-card: #ffffff;
        --bg-card-hover: #f1f5f9;
        --bg-sidebar: #ffffff;
        --accent-primary: #0284c7;
        --accent-hover: #0369a1;
        --accent-gold: #d97706;
        --accent-gold-hover: #b45309;
        --text-main: #0f172a;
        --text-muted: #64748b;
        --border-color: #e2e8f0;
        --border-gold: rgba(217, 119, 6, 0.3);
        --shadow-subtle: 0 4px 12px rgba(0, 0, 0, 0.04);
        --input-bg: #ffffff;
    }
"""

# Azul marino equilibrado (más claro y elegante que el negro) con detalles dorados
css_dark = """
    :root {
        --bg-main: #141c2b;
        --bg-card: #1d273a;
        --bg-card-hover: #243147;
        --bg-sidebar: #101622;
        --accent-primary: #d97706;
        --accent-hover: #f59e0b;
        --accent-gold: #f59e0b;
        --accent-gold-hover: #d97706;
        --text-main: #f8fafc;
        --text-muted: #94a3b8;
        --border-color: #2b3952;
        --border-gold: rgba(245, 158, 11, 0.4);
        --shadow-subtle: 0 6px 20px rgba(0, 0, 0, 0.25);
        --input-bg: #162032;
    }
"""

css_activo = css_dark if st.session_state.modo_oscuro else css_light

st.markdown(f"""
<link rel="manifest" href="{manifest_data_uri}">
<meta name="theme-color" content="#d97706">
<style>
    {css_activo}
    
    /* General Application Styling */
    .stApp {{
        background-color: var(--bg-main) !important;
        color: var(--text-main) !important;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }}
    
    header[data-testid="stHeader"] {{
        background-color: transparent !important;
        z-index: 99999;
    }}
    
    /* Sidebar styling */
    section[data-testid="stSidebar"] {{
        background-color: var(--bg-sidebar) !important;
        border-right: 1px solid var(--border-color) !important;
    }}
    
    section[data-testid="stSidebar"] .stButton > button {{
        width: 100%;
        background-color: transparent !important;
        color: var(--text-main) !important;
        border: 1px solid transparent !important;
        text-align: left !important;
        justify-content: flex-start !important;
        padding: 0.6rem 1rem !important;
        border-radius: 8px !important;
        font-weight: 500 !important;
    }}
    
    section[data-testid="stSidebar"] .stButton > button:hover {{
        background-color: var(--bg-card-hover) !important;
        border-color: var(--border-color) !important;
        color: var(--accent-gold) !important;
    }}

    /* User Profile Header in Sidebar */
    .user-profile-badge {{
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 8px 4px;
        margin-bottom: 12px;
    }}
    .user-avatar {{
        width: 40px;
        height: 40px;
        border-radius: 50%;
        background: linear-gradient(135deg, #d97706, #f59e0b);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 20px;
        color: white;
        box-shadow: 0 2px 8px rgba(217, 119, 6, 0.3);
    }}
    .user-info-name {{
        font-weight: 700;
        font-size: 0.95rem;
        color: var(--text-main);
        line-height: 1.2;
    }}
    .user-info-role {{
        font-size: 0.78rem;
        color: var(--text-muted);
    }}

    /* Card Containers */
    div[data-testid="stVerticalBlock"] > div.element-container > div.stMarkdown > div.card-box,
    .stCard {{
        background-color: var(--bg-card) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 12px !important;
        padding: 1.25rem !important;
        box-shadow: var(--shadow-subtle) !important;
        margin-bottom: 1rem !important;
    }}

    /* Custom Cards for Questions & Tests */
    .test-card {{
        background-color: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 1rem 1.25rem;
        margin-bottom: 0.8rem;
        transition: all 0.2s ease-in-out;
    }}
    .test-card:hover {{
        border-color: var(--border-gold);
        box-shadow: 0 4px 14px rgba(217, 119, 6, 0.12);
    }}

    /* Buttons Styling */
    div.stButton > button[kind="primary"], div.stFormSubmitButton > button[kind="primary"] {{
        background: linear-gradient(135deg, var(--accent-gold) 0%, var(--accent-gold-hover) 100%) !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 0.55rem 1.2rem !important;
        font-weight: 600 !important;
        box-shadow: 0 3px 10px rgba(217, 119, 6, 0.25) !important;
        transition: all 0.2s ease;
    }}
    div.stButton > button[kind="primary"]:hover, div.stFormSubmitButton > button[kind="primary"]:hover {{
        transform: translateY(-1px);
        box-shadow: 0 5px 15px rgba(217, 119, 6, 0.35) !important;
    }}

    div.stButton > button[kind="secondary"], div.stFormSubmitButton > button[kind="secondary"] {{
        background-color: var(--bg-card) !important;
        border: 1px solid var(--border-color) !important;
        color: var(--text-main) !important;
        border-radius: 8px !important;
        padding: 0.55rem 1.2rem !important;
        font-weight: 500 !important;
        transition: all 0.2s ease;
    }}
    div.stButton > button[kind="secondary"]:hover {{
        border-color: var(--accent-gold) !important;
        color: var(--accent-gold) !important;
    }}

    /* Inputs, Selectboxes & File Uploader */
    .stTextInput input, .stSelectbox select, .stPasswordInput input, div[data-baseweb="input"] input {{
        background-color: var(--input-bg) !important;
        color: var(--text-main) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 8px !important;
    }}
    .stTextInput input:focus, .stSelectbox select:focus {{
        border-color: var(--accent-gold) !important;
    }}

    /* Radio buttons styling for questions */
    .stRadio > div {{
        gap: 8px;
    }}
    .stRadio label {{
        background-color: var(--bg-card) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 10px !important;
        padding: 12px 16px !important;
        width: 100% !important;
        transition: all 0.15s ease-in-out !important;
        cursor: pointer !important;
    }}
    .stRadio label:hover {{
        border-color: var(--accent-gold) !important;
        background-color: var(--bg-card-hover) !important;
    }}
    
    /* Progress bar */
    .stProgress > div > div > div > div {{
        background-color: var(--accent-gold) !important;
    }}

    /* Metrics */
    div[data-testid="metric-container"] {{
        background-color: var(--bg-card) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 10px !important;
        padding: 1rem !important;
    }}

    /* Modal card overlay style for study mode */
    .study-overlay-card {{
        background-color: var(--bg-card);
        border: 1px solid var(--border-gold);
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        margin-top: 10px;
    }}

    /* Title headers */
    h1, h2, h3, h4 {{
        color: var(--text-main) !important;
        font-weight: 700 !important;
    }}
</style>
""", unsafe_allow_html=True)


# --- ALMACENAMIENTO LOCAL Y ARCHIVOS ---
DATA_DIR = "data_bancos"
HISTORY_FILE = "historial_resultados.json"
USERS_FILE = "usuarios.json"
SESSION_FILE = "sesion_activa.json"

os.makedirs(DATA_DIR, exist_ok=True)


# --- CONFIGURACIÓN DE GEMINI API ---
api_key_configurada = ""
try:
    if "GEMINI_API_KEY" in st.secrets:
        api_key_configurada = st.secrets["GEMINI_API_KEY"]
except Exception:
    pass

if "gemini_api_key" not in st.session_state:
    st.session_state["gemini_api_key"] = api_key_configurada

if "gemini_modelo" not in st.session_state:
    st.session_state["gemini_modelo"] = "Auto-Seleccionar Modelo Activo"


def obtener_modelos_activos_live(client):
    modelos_encontrados = []
    if not GENAI_DISPONIBLE or client is None:
        return ["gemini-2.5-flash", "gemini-3.1-pro-preview", "gemini-1.5-flash"]
        
    try:
        lista_api = client.models.list()
        for m in lista_api:
            nombre = getattr(m, 'name', '') or str(m)
            nombre_limpio = nombre.replace("models/", "")
            if "gemini" in nombre_limpio.lower() and not any(x in nombre_limpio.lower() for x in ["embedding", "imagen", "tts", "stt", "bison"]):
                modelos_encontrados.append(nombre_limpio)
    except Exception:
        pass
    
    respaldos = ["gemini-2.5-flash", "gemini-3.1-pro-preview", "gemini-1.5-flash"]
    for r in respaldos:
        if r not in modelos_encontrados:
            modelos_encontrados.append(r)
            
    return modelos_encontrados


def ejecutar_gemini_con_fallback(client, contents_payload, config, modelo_preferido):
    if not GENAI_DISPONIBLE or client is None:
        raise ImportError("La librería google-genai no está disponible en el servidor.")

    modelos_disponibles_live = obtener_modelos_activos_live(client)
    
    candidatos = []
    if modelo_preferido and modelo_preferido != "Auto-Seleccionar Modelo Activo" and modelo_preferido in modelos_disponibles_live:
        candidatos.append(modelo_preferido)
    
    for m in modelos_disponibles_live:
        if m not in candidatos:
            candidatos.append(m)

    ultimo_error = None
    errores_tolerados = ["404", "503", "429", "500", "not_found", "not found", "unavailable", "overloaded", "quota", "resource_exhausted"]

    for modelo in candidatos:
        try:
            response = client.models.generate_content(
                model=modelo,
                contents=contents_payload,
                config=config
            )
            st.session_state["gemini_modelo"] = modelo
            return response, modelo
        except Exception as e:
            err_str = str(e).lower()
            if any(k in err_str for k in errores_tolerados):
                ultimo_error = e
                time.sleep(0.5)
                continue
            else:
                raise e
                
    raise ultimo_error


def limpiar_radios_session():
    keys_a_borrar = [k for k in st.session_state.keys() if k.startswith("radio_alt_")]
    for k in keys_a_borrar:
        del st.session_state[k]


# --- GESTIÓN DE USUARIOS Y AUTENTICACIÓN ---
def cargar_usuarios():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def guardar_usuarios(usuarios):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(usuarios, f, ensure_ascii=False, indent=4)


def inicializar_usuarios():
    usuarios = cargar_usuarios()
    if "undurragapi@gmail.com" not in usuarios:
        usuarios["undurragapi@gmail.com"] = {
            "nombre": "Pablo Undurraga",
            "email": "undurragapi@gmail.com",
            "password": "pablo9596",
            "rol": "admin"
        }
        guardar_usuarios(usuarios)
    
    st.session_state.usuarios_db = usuarios
    return usuarios


def autenticar_usuario(email_input, password_input):
    usuarios_db = inicializar_usuarios()
    
    if not email_input or not password_input:
        return False, "Por favor ingresa tu correo y contraseña."

    email_clean = email_input.strip().lower()
    pass_clean = password_input.strip()
    
    if email_clean not in usuarios_db:
        return False, "Correo o contraseña incorrectos."
    
    usuario = usuarios_db[email_clean]
    pass_guardada = str(usuario.get("password", ""))
    pass_hash_input = hashlib.sha256(pass_clean.encode()).hexdigest()
    
    if pass_clean == pass_guardada or pass_hash_input == pass_guardada:
        return True, f"¡Bienvenido, {usuario.get('nombre', 'Usuario')}!"
    
    return False, "Correo o contraseña incorrectos."


def cargar_sesion_persistida():
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, "r", encoding="utf-8") as f:
                return json.load(f).get("usuario")
        except (json.JSONDecodeError, IOError):
            return None
    return None


def guardar_sesion_persistida(email):
    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump({"usuario": email}, f, ensure_ascii=False, indent=4)


def eliminar_sesion_persistida():
    if os.path.exists(SESSION_FILE):
        try:
            os.remove(SESSION_FILE)
        except OSError:
            pass


if "usuario_actual" not in st.session_state:
    saved_user = cargar_sesion_persistida()
    usuarios_db_temp = inicializar_usuarios()
    if saved_user and saved_user in usuarios_db_temp:
        st.session_state.usuario_actual = saved_user
    else:
        st.session_state.usuario_actual = None


# --- OPERACIONES DE BANCOS DE PREGUNTAS ---
def guardar_banco(nombre_id, data):
    ruta = os.path.join(DATA_DIR, f"{nombre_id}.json")
    
    for idx, q in enumerate(data.get("preguntas", [])):
        if "idx_original" not in q:
            q["idx_original"] = idx

    if os.path.exists(ruta):
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                banco_antiguo = json.load(f)
            
            mapa_manuales = {}
            for idx_ant, q_ant in enumerate(banco_antiguo.get("preguntas", [])):
                if q_ant.get("correcta") is not None:
                    key_m = f"{q_ant.get('idx_original', idx_ant)}_{q_ant['pregunta'].strip()}"
                    mapa_manuales[key_m] = q_ant["correcta"]
            
            data["falladas"] = banco_antiguo.get("falladas", {})

            for idx_n, q_nueva in enumerate(data.get("preguntas", [])):
                key_n = f"{q_nueva.get('idx_original', idx_n)}_{q_nueva['pregunta'].strip()}"
                if key_n in mapa_manuales and q_nueva.get("correcta") is None:
                    q_nueva["correcta"] = mapa_manuales[key_n]
        except (json.JSONDecodeError, IOError, KeyError):
            pass

    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def actualizar_pregunta_individual(nombre_id, idx_original, nueva_correcta):
    banco_data = cargar_banco(nombre_id)
    if banco_data and "preguntas" in banco_data:
        for q in banco_data["preguntas"]:
            if q.get("idx_original") == idx_original:
                q["correcta"] = nueva_correcta
                break
        guardar_banco(nombre_id, banco_data)


def cargar_banco(nombre_id):
    ruta = os.path.join(DATA_DIR, f"{nombre_id}.json")
    if os.path.exists(ruta):
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None
    return None


def eliminar_banco(nombre_id):
    ruta = os.path.join(DATA_DIR, f"{nombre_id}.json")
    if os.path.exists(ruta):
        try:
            os.remove(ruta)
            return True
        except OSError:
            return False
    return False


def listar_bancos():
    if not os.path.exists(DATA_DIR):
        return []
    return [f.replace(".json", "") for f in os.listdir(DATA_DIR) if f.endswith(".json")]


def registrar_preguntas_falladas(nombre_id, preguntas_falladas_orig_indices):
    banco_data = cargar_banco(nombre_id)
    if not banco_data:
        return
    if "falladas" not in banco_data:
        banco_data["falladas"] = {}
    
    usuario = st.session_state.usuario_actual or "default"
    set_falladas = set(banco_data["falladas"].get(usuario, []))
    set_falladas.update(preguntas_falladas_orig_indices)
    banco_data["falladas"][usuario] = list(set_falladas)
    
    guardar_banco(nombre_id, banco_data)


def limpiar_falladas_resueltas(nombre_id, preguntas_resueltas_orig_ok):
    banco_data = cargar_banco(nombre_id)
    if not banco_data or "falladas" not in banco_data:
        return
    usuario = st.session_state.usuario_actual or "default"
    actuales = set(banco_data["falladas"].get(usuario, []))
    actuales.difference_update(preguntas_resueltas_orig_ok)
    banco_data["falladas"][usuario] = list(actuales)
    guardar_banco(nombre_id, banco_data)


# --- HISTORIAL Y DIAGNÓSTICO ---
def guardar_resultado_historial(nombre_prueba, puntaje_pct, correctas, total, desglose_categorias=None):
    historial = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                historial = json.load(f)
        except (json.JSONDecodeError, IOError):
            historial = []
    
    historial.append({
        "usuario": st.session_state.usuario_actual,
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "timestamp": datetime.now().timestamp(),
        "prueba": nombre_prueba,
        "puntaje": puntaje_pct,
        "correctas": correctas,
        "total": total,
        "desglose_categorias": desglose_categorias or {}
    })
    
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(historial, f, ensure_ascii=False, indent=4)


def obtener_historial_reciente():
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            historial = json.load(f)
    except (json.JSONDecodeError, IOError):
        return []
    
    limite_tiempo = datetime.now().timestamp() - (20 * 24 * 60 * 60)
    filtrado = [h for h in historial if h.get("timestamp", 0) >= limite_tiempo and h.get("usuario") == st.session_state.usuario_actual]
    return sorted(filtrado, key=lambda x: x["timestamp"], reverse=True)


# --- IA PROCESAMIENTO MULTIMODAL & EXPLICACIONES ---
def limpiar_respuesta_json(texto_raw):
    texto_limpio = re.sub(r"^```json\s*", "", texto_raw.strip(), flags=re.MULTILINE)
    texto_limpio = re.sub(r"^```\s*", "", texto_limpio, flags=re.MULTILINE)
    texto_limpio = re.sub(r"```$", "", texto_limpio, flags=re.MULTILINE)
    return texto_limpio.strip()


def procesar_documento_multimodal(file_path, api_key, mod
