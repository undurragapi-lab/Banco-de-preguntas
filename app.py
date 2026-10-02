import os
import re
import json
import random
import time
import tempfile
import base64
from datetime import datetime
import streamlit as st
import pandas as pd
from google import genai
from google.genai import types

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="AeroStudio Pro - Simulador de Vuelo",
    page_icon="✈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CONFIGURACIÓN PWA INLINE (COMPATIBILIDAD CON CHROME MOBILE) ---
manifest_dict = {
    "name": "AeroStudio Pro",
    "short_name": "AeroStudio",
    "start_url": "/",
    "display": "standalone",
    "background_color": "#171514",
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

# --- GESTIÓN DE ESTADOS DE SESIÓN (MODO CLARO POR DEFECTO) ---
if "modo_oscuro" not in st.session_state:
    st.session_state.modo_oscuro = False
if "vista" not in st.session_state:
    st.session_state.vista = "home"
if "modo_estudio_data" not in st.session_state:
    st.session_state.modo_estudio_data = None

# --- CSS: MODO CLARO Y MODO LECTURA NOCTURNA (FILTRO LUZ AZUL) ---
css_light = """
    :root {
        --bg-main: #f8fafc;
        --bg-card: #ffffff;
        --accent-blue: #0284c7;
        --accent-hover: #0369a1;
        --text-main: #0f172a;
        --text-muted: #64748b;
        --border-color: #e2e8f0;
        --sidebar-bg: #f1f5f9;
    }
"""

css_dark = """
    :root {
        --bg-main: #171514;
        --bg-card: #23201e;
        --accent-blue: #d97706;
        --accent-hover: #b45309;
        --text-main: #f5efe6;
        --text-muted: #a8a29e;
        --border-color: #3f3835;
        --sidebar-bg: #1c1917;
    }
"""

css_activo = css_dark if st.session_state.modo_oscuro else css_light

st.markdown(f"""
<link rel="manifest" href="{manifest_data_uri}">
<meta name="theme-color" content="#d97706">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<style>
    {css_activo}
    .stApp {{
        background-color: var(--bg-main);
        color: var(--text-main);
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }}
    header {{visibility: hidden;}}
    div.stButton > button {{
        background: linear-gradient(135deg, var(--accent-blue) 0%, var(--accent-hover) 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.6rem 1.2rem;
        font-weight: 600;
        box-shadow: 0 4px 12px rgba(217, 119, 6, 0.15);
        transition: all 0.2s ease-in-out;
    }}
    div.stButton > button:hover {{
        transform: translateY(-2px);
    }}
    div.stButton > button[kind="secondary"] {{
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        color: var(--text-main);
        box-shadow: none;
    }}
    .stTextInput input, .stSelectbox select, .stPasswordInput input {{
        background-color: var(--bg-card) !important;
        color: var(--text-main) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 8px !important;
        padding: 0.6rem 1rem !important;
    }}
    section[data-testid="stSidebar"] {{
        background-color: var(--sidebar-bg);
        border-right: 1px solid var(--border-color);
    }}
    div[data-testid="metric-container"] {{
        background-color: var(--bg-card);
        border: 1px solid var(--border-color);
        padding: 1.2rem;
        border-radius: 10px;
    }}
    .stRadio label {{
        padding: 10px;
        border-radius: 8px;
        transition: background 0.2s;
    }}
    .stRadio label:hover {{
        background-color: var(--border-color);
    }}
</style>
""", unsafe_allow_html=True)

# --- ALMACENAMIENTO LOCAL DE BANCOS Y USUARIOS ---
DATA_DIR = "data_bancos"
HISTORY_FILE = "historial_resultados.json"
USERS_FILE = "usuarios.json"
SESSION_FILE = "sesion_activa.json"

os.makedirs(DATA_DIR, exist_ok=True)

# --- CONFIGURACIÓN Y MODELOS GEMINI ---
api_key_configurada = ""
try:
    if "GEMINI_API_KEY" in st.secrets:
        api_key_configurada = st.secrets["GEMINI_API_KEY"]
except Exception:
    pass

if "gemini_api_key" not in st.session_state:
    st.session_state["gemini_api_key"] = api_key_configurada

# Modelos soportados y válidos
modelos_disponibles = [
    "gemini-2.0-flash",
    "gemini-2.5-flash",
    "gemini-2.5-pro"
]

if "gemini_modelo" not in st.session_state or st.session_state["gemini_modelo"] not in modelos_disponibles:
    st.session_state["gemini_modelo"] = "gemini-2.0-flash"

def limpiar_radios_session():
    """Limpia las selecciones previas de radio buttons para evitar selecciones fantasma."""
    keys_a_borrar = [k for k in st.session_state.keys() if k.startswith("radio_alt_")]
    for k in keys_a_borrar:
        del st.session_state[k]

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
    usuarios_db_temp = cargar_usuarios()
    if saved_user and saved_user in usuarios_db_temp:
        st.session_state.usuario_actual = saved_user
    else:
        st.session_state.usuario_actual = None

# --- BANCOS DE PREGUNTAS ---
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
    """Actualiza una sola pregunta en el banco persistido por su idx_original."""
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
    """Elimina el banco de preguntas guardado en disco."""
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
    """Guarda el historial de preguntas falladas usando los índices originales."""
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
    """Elimina de la lista de falladas las preguntas respondidas correctamente."""
    banco_data = cargar_banco(nombre_id)
    if not banco_data or "falladas" not in banco_data:
        return
    usuario = st.session_state.usuario_actual or "default"
    actuales = set(banco_data["falladas"].get(usuario, []))
    actuales.difference_update(preguntas_resueltas_orig_ok)
    banco_data["falladas"][usuario] = list(actuales)
    guardar_banco(nombre_id, banco_data)

# --- HISTORIAL Y DIAGNÓSTICO POR ÁREAS TEMÁTICAS ---
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

# --- PROCESAMIENTO CON GOOGLE FILE API Y DIAGNÓSTICO TEMÁTICO ---
def limpiar_respuesta_json(texto_raw):
    """Limpia etiquetas Markdown de bloques JSON devueltos por la IA."""
    texto_limpio = re.sub(r"^```json\s*", "", texto_raw.strip(), flags=re.MULTILINE)
    texto_limpio = re.sub(r"^```\s*", "", texto_limpio, flags=re.MULTILINE)
    texto_limpio = re.sub(r"```$", "", texto_limpio, flags=re.MULTILINE)
    return texto_limpio.strip()

def procesar_documento_multimodal(file_path, api_key, modelo, file_extension):
    """
    Analiza documentos/imágenes con Google File API y visión de Gemini.
    Soporta archivos grandes (>20MB) y clasifica preguntas en áreas temáticas.
    """
    archivo_subido = None
    client = None
    try:
        if not api_key or not api_key.strip():
            st.error("⚠️ Ingrese una API Key válida antes de procesar.")
            return None

        client = genai.Client(api_key=api_key.strip())

        ext = file_extension.lower().replace(".", "")
        mime_type = "application/pdf"
        if ext == "png":
            mime_type = "image/png"
        elif ext in ["jpg", "jpeg"]:
            mime_type = "image/jpeg"

        with st.spinner(f"📤 Subiendo archivo ({ext.upper()}) a Google File API..."):
            archivo_subido = client.files.upload(
                file=file_path,
                config={"mime_type": mime_type}
            )

        with st.spinner(f"👁️ Gemini ({modelo}) está analizando el documento y clasificando por materias..."):
            prompt = """
            Eres un sistema experto en visión artificial, análisis de exámenes y pedagogía aeronáutica.
            Tu tarea es analizar VISUALMENTE este documento completo y extraer todas las preguntas, sus alternativas,
            la respuesta correcta asignada y clasificar cada pregunta por materia/categoría técnica.

            EVALUACIÓN VISUAL, PAUTA Y CATEGORIZACIÓN:
            1. Examina cada página del documento.
            2. Identifica la pregunta y sus alternativas (A, B, C, D).
            3. BUSCA MARCAS VISUALES DE RESPUESTA:
               - Marcas a mano o lápiz (círculos, cruces, subrayados, vistos).
               - Marcas de editor de PDF (resaltados amarillos/verdes, círculos rojos, texto en color/negrita).
               - Pautas impresas en el documento original.
            4. Registra en 'respuesta_correcta' exactamente la alternativa marcada visualmente en el documento, sin corregir errores del texto original.
            5. CLASIFICA LA MATERIA en 'categoria': Asigna una categoría aeronáutica oficial a cada pregunta, por ejemplo:
               - "Reglamentación y Normativa"
               - "Meteorología Aeronáutica"
               - "Navegación y Planificación"
               - "Fisiología y Factores Humanos"
               - "Aerodinámica y Performance"
               - "Sistemas y Motores"
               - "Procedimientos Operativos"

            FORMATO DE SALIDA ESTRICTO (JSON):
            Devuelve ÚNICAMENTE un objeto JSON válido con la siguiente estructura exacta:
            {
              "preguntas": [
                {
                  "pregunta": "Texto de la pregunta",
                  "opciones": ["Alternativa A", "Alternativa B", "Alternativa C", "Alternativa D"],
                  "respuesta_correcta": "A",
                  "categoria": "Meteorología Aeronáutica"
                }
              ]
            }
            En "respuesta_correcta" indica únicamente la letra ("A", "B", "C" o "D").
            """

            response = client.models.generate_content(
                model=modelo,
                contents=[archivo_subido, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.0
                )
            )

        preguntas_finales = []
        if response and response.text:
            json_limpio = limpiar_respuesta_json(response.text)
            data = json.loads(json_limpio)
            
            if "preguntas" in data:
                for idx_q, q in enumerate(data["preguntas"]):
                    enunciado = q.get("pregunta", "")
                    opciones_textos = q.get("opciones", [])
                    letra_corr = str(q.get("respuesta_correcta", "A")).strip().upper()
                    categoria_q = q.get("categoria", "General").strip()
                    
                    alternativas_formateadas = []
                    correcta_idx = None
                    
                    for idx_a, texto_alt in enumerate(opciones_textos[:4]):
                        letra_let = ['A', 'B', 'C', 'D'][idx_a]
                        match_prefijo = bool(re.match(rf"^{letra_corr}[\.\)\-\s]", texto_alt.strip(), re.IGNORECASE))
                        es_correcta = (letra_let == letra_corr) or match_prefijo
                        
                        if es_correcta:
                            correcta_idx = idx_a
                        
                        alternativas_formateadas.append({
                            "letra": letra_let,
                            "texto": texto_alt,
                            "marcada": es_correcta
                        })
                    
                    if enunciado and len(alternativas_formateadas) >= 2:
                        preguntas_finales.append({
                            "idx_original": idx_q,
                            "pregunta": enunciado,
                            "alternativas": alternativas_formateadas,
                            "correcta": correcta_idx,
                            "categoria": categoria_q
                        })
                        
        return preguntas_finales

    except json.JSONDecodeError as e:
        st.error(f"Error al decodificar la respuesta JSON del modelo: {e}")
        return None
    except Exception as e:
        st.error(f"Error durante el análisis visual con File API: {e}")
        return None
    finally:
        if client and archivo_subido:
            try:
                client.files.delete(name=archivo_subido.name)
            except Exception:
                pass

# --- EXPLICACIÓN TÉCNICA PEDAGÓGICA (IA) ---
def obtener_explicacion_ia(pregunta_text, alternativas, idx_correcta, idx_elegida, api_key, modelo):
    """Genera una explicación pedagógica basada en conceptos aeronáuticos oficiales."""
    try:
        client = genai.Client(api_key=api_key.strip())
        
        alt_corr_text = "N/A"
        if idx_correcta is not None and isinstance(idx_correcta, int) and 0 <= idx_correcta < len(alternativas):
            alt_corr_text = alternativas[idx_correcta]['texto']
        
        alt_eleg_text = "Ninguna"
        if idx_elegida is not None and isinstance(idx_elegida, int) and 0 <= idx_elegida < len(alternativas):
            alt_eleg_text = alternativas[idx_elegida]['texto']
        
        prompt = f"""
        Eres un instructor de vuelo y experto pedagogo en aviación civil.
        Explica brevemente y de forma didáctica (máximo 3 párrafos cortos) el fundamento técnico de esta pregunta de examen:

        Pregunta: "{pregunta_text}"
        Respuesta Correcta Oficial: "{alt_corr_text}"
        Respuesta Seleccionada por el Alumno: "{alt_eleg_text}"

        Explicación requerida:
        1. Explica por qué la respuesta oficial es la correcta según los reglamentos (FAR, DAN), principios aerodinámicos, meteorológicos o de CRM.
        2. Si el alumno respondió incorrectamente, aclara de forma amable cuál fue la confusión o el error común.
        3. Da un consejo rápido para recordar este concepto en el examen.
        """
        response = client.models.generate_content(
            model=modelo,
            contents=[prompt],
            config=types.GenerateContentConfig(temperature=0.3)
        )
        return response.text if response else "No se pudo generar la explicación en este momento."
    except Exception as e:
        return f"Error al consultar el instructor de IA: {e}"

# --- CONTROL DE ACCESO ---
if st.session_state.usuario_actual is None:
    st.markdown("<h2 style='text-align: center; color: var(--accent-blue); padding-top: 5vh;'>✈️ AeroStudio Pro</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: var(--text-muted); margin-bottom: 2rem;'>Plataforma avanzada de estudio y entrenamiento aeronáutico con IA integrada.</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        tab_login, tab_registro = st.tabs(["Iniciar Sesión", "Registrarse"])
        usuarios_db = cargar_usuarios()
        
        with tab_login:
            email_ingreso = st.text_input("Correo electrónico:", key="login_email")
            pass_ingreso = st.text_input("Contraseña:", type="password", key="login_pass")
            st.write("")
            if st.button("Entrar al Sistema", use_container_width=True):
                email_ingreso = email_ingreso.strip().lower()
                if email_ingreso in usuarios_db and usuarios_db[email_ingreso]["password"] == pass_ingreso:
                    st.session_state.usuario_actual = email_ingreso
                    guardar_sesion_persistida(email_ingreso)
                    st.rerun()
                else:
                    st.error("Correo o contraseña incorrectos.")
                    
        with tab_registro:
            reg_nombre = st.text_input("Nombre completo:", key="reg_name")
            reg_email = st.text_input("Correo electrónico:", key="reg_email")
            reg_pass = st.text_input("Contraseña:", type="password", key="reg_pass")
            st.write("")
            if st.button("Crear Cuenta", use_container_width=True):
                reg_email = reg_email.strip().lower()
                if not reg_email or not reg_pass or not reg_nombre:
                    st.warning("Completa todos los campos.")
                elif reg_email in usuarios_db:
                    st.error("Este correo ya está registrado.")
                else:
                    usuarios_db[reg_email] = {"nombre": reg_nombre, "email": reg_email, "password": reg_pass}
                    guardar_usuarios(usuarios_db)
                    st.session_state.usuario_actual = reg_email
                    guardar_sesion_persistida(reg_email)
                    st.success("¡Cuenta creada con éxito!")
                    st.rerun()
    st.stop()

usuarios_db = cargar_usuarios()
datos_usuario = usuarios_db.get(st.session_state.usuario_actual, {"nombre": "Piloto", "email": st.session_state.usuario_actual, "password": ""})

# --- BARRA LATERAL ---
with st.sidebar:
    st.markdown(f"### 👨‍✈️️ {datos_usuario['nombre']}")
    st.caption("Piloto en Entrenamiento")
    st.divider()
    
    texto_modo = "🌙 Activar Modo Lectura Nocturna (Filtro Cálido)" if not st.session_state.modo_oscuro else "☀️ Cambiar a Modo Claro"
    if st.button(texto_modo, use_container_width=True, type="secondary"):
        st.session_state.modo_oscuro = not st.session_state.modo_oscuro
        st.rerun()

    st.divider()
    st.markdown("### ⚙️ Configuración de IA")
    
    if not st.session_state["gemini_api_key"]:
        user_input_key = st.text_input("Google Gemini API Key", type="password", help="Ingresa tu clave de AI Studio")
        if user_input_key:
            st.session_state["gemini_api_key"] = user_input_key.strip()
            st.success("¡API Key guardada!")

    modelo_seleccionado = st.selectbox(
        "Modelo de Gemini:",
        options=modelos_disponibles,
        index=modelos_disponibles.index(st.session_state["gemini_modelo"]) if st.session_state["gemini_modelo"] in modelos_disponibles else 0,
        help="Selecciona el modelo que prefieras usar."
    )
    st.session_state["gemini_modelo"] = modelo_seleccionado

    st.divider()
    if st.button("👤 Perfil de Usuario", use_container_width=True):
        st.session_state.vista = "perfil"
        st.rer
