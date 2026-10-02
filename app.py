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

# --- CONFIGURACIÓN PWA INLINE ---
manifest_dict = {
    "name": "AeroStudio Pro",
    "short_name": "AeroStudio",
    "start_url": "/",
    "display": "standalone",
    "background_color": "#1e293b",
    "theme_color": "#1e293b",
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
    st.session_state.modo_oscuro = False
if "vista" not in st.session_state:
    st.session_state.vista = "home"
if "modo_estudio_data" not in st.session_state:
    st.session_state.modo_estudio_data = None
if "usuario_actual" not in st.session_state:
    st.session_state.usuario_actual = None

# --- CSS: ESTILO UI EJECUTIVO IDÉNTICO A REFERENCIA ---
css_light = """
    :root {
        --bg-main: #f8fafc;
        --bg-card: #ffffff;
        --sidebar-bg: #1e293b;
        --sidebar-text: #94a3b8;
        --sidebar-text-hover: #ffffff;
        --accent-blue: #2563eb;
        --accent-hover: #1d4ed8;
        --text-main: #0f172a;
        --text-muted: #64748b;
        --border-color: #e2e8f0;
        --card-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05), 0 8px 10px -6px rgba(0, 0, 0, 0.05);
    }
"""

css_dark = """
    :root {
        --bg-main: #0b0f19;
        --bg-card: #1e293b;
        --sidebar-bg: #090d16;
        --sidebar-text: #94a3b8;
        --sidebar-text-hover: #ffffff;
        --accent-blue: #3b82f6;
        --accent-hover: #2563eb;
        --text-main: #f8fafc;
        --text-muted: #94a3b8;
        --border-color: #334155;
        --card-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
    }
"""

css_activo = css_dark if st.session_state.modo_oscuro else css_light

st.markdown(f"""
<link rel="manifest" href="{manifest_data_uri}">
<meta name="theme-color" content="#1e293b">
<style>
    {css_activo}
    .stApp {{
        background-color: var(--bg-main);
        color: var(--text-main);
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }}
    header[data-testid="stHeader"] {{
        background-color: transparent !important;
        z-index: 99999;
    }}
    
    /* --- BARRA LATERAL LIMPIA SIN BARRAS BLANCAS --- */
    section[data-testid="stSidebar"] {{
        background-color: var(--sidebar-bg) !important;
        border-right: 1px solid var(--border-color);
        padding-top: 1rem;
    }}
    section[data-testid="stSidebar"] .stMarkdown, section[data-testid="stSidebar"] span, section[data-testid="stSidebar"] p {{
        color: var(--sidebar-text) !important;
    }}
    
    /* Convertir botones de navegación del sidebar en enlaces minimalistas tipo app */
    section[data-testid="stSidebar"] div.stButton > button {{
        background: transparent !important;
        color: var(--sidebar-text) !important;
        border: none !important;
        border-radius: 8px !important;
        text-align: left !important;
        padding: 0.6rem 1rem !important;
        font-weight: 500 !important;
        box-shadow: none !important;
        width: 100% !important;
        transition: all 0.2s ease;
    }}
    section[data-testid="stSidebar"] div.stButton > button:hover {{
        background: rgba(255, 255, 255, 0.08) !important;
        color: var(--sidebar-text-hover) !important;
        transform: none !important;
        box-shadow: none !important;
    }}

    /* Botones principales de acción */
    div.stButton > button {{
        background: linear-gradient(135deg, var(--accent-blue) 0%, var(--accent-hover) 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.55rem 1.2rem;
        font-weight: 600;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.2);
        transition: all 0.2s ease-in-out;
    }}
    div.stButton > button:hover {{
        transform: translateY(-1px);
        box-shadow: 0 6px 16px rgba(37, 99, 235, 0.3);
    }}
    
    /* Campos de entrada estilizados */
    .stTextInput input, .stSelectbox select, .stPasswordInput input {{
        background-color: var(--bg-card) !important;
        color: var(--text-main) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 8px !important;
        padding: 0.6rem 1rem !important;
    }}
    
    /* Métricas con diseño corporativo */
    div[data-testid="metric-container"] {{
        background-color: var(--bg-card);
        border: 1px solid var(--border-color);
        padding: 1.2rem;
        border-radius: 12px;
        box-shadow: var(--card-shadow);
    }}
</style>
""", unsafe_allow_html=True)

# --- ALMACENAMIENTO Y DIRECTORIOS ---
DATA_DIR = "data_bancos"
HISTORY_FILE = "historial_resultados.json"
USERS_FILE = "usuarios.json"
SESSION_FILE = "sesion_activa.json"

os.makedirs(DATA_DIR, exist_ok=True)

# --- CONFIGURACIÓN DE GEMINI ---
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
            response = client.models.generate_content(model=modelo, contents=contents_payload, config=config)
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

if st.session_state.usuario_actual is None:
    saved_user = cargar_sesion_persistida()
    usuarios_db_temp = cargar_usuarios()
    if saved_user and saved_user in usuarios_db_temp:
        st.session_state.usuario_actual = saved_user

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
    if not banco_data: return
    if "falladas" not in banco_data: banco_data["falladas"] = {}
    usuario = st.session_state.usuario_actual or "default"
    set_falladas = set(banco_data["falladas"].get(usuario, []))
    set_falladas.update(preguntas_falladas_orig_indices)
    banco_data["falladas"][usuario] = list(set_falladas)
    guardar_banco(nombre_id, banco_data)

def limpiar_falladas_resueltas(nombre_id, preguntas_resueltas_orig_ok):
    banco_data = cargar_banco(nombre_id)
    if not banco_data or "falladas" not in banco_data: return
    usuario = st.session_state.usuario_actual or "default"
    actuales = set(banco_data["falladas"].get(usuario, []))
    actuales.difference_update(preguntas_resueltas_orig_ok)
    banco_data["falladas"][usuario] = list(actuales)
    guardar_banco(nombre_id, banco_data)

# --- HISTORIAL Y ESTADÍSTICAS ---
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
    if not os.path.exists(HISTORY_FILE): return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            historial = json.load(f)
    except (json.JSONDecodeError, IOError):
        return []
    limite_tiempo = datetime.now().timestamp() - (30 * 24 * 60 * 60)
    filtrado = [h for h in historial if h.get("timestamp", 0) >= limite_tiempo and h.get("usuario") == st.session_state.usuario_actual]
    return sorted(filtrado, key=lambda x: x["timestamp"], reverse=True)

# --- PROCESAMIENTO CON GOOGLE FILE API ---
def limpiar_respuesta_json(texto_raw):
    texto_limpio = re.sub(r"^```json\s*", "", texto_raw.strip(), flags=re.MULTILINE)
    texto_limpio = re.sub(r"^```\s*", "", texto_limpio, flags=re.MULTILINE)
    texto_limpio = re.sub(r"```$", "", texto_limpio, flags=re.MULTILINE)
    return texto_limpio.strip()

def procesar_documento_multimodal(file_path, api_key, modelo_preferido, file_extension):
    archivo_subido = None
    client = None
    try:
        if not api_key or not api_key.strip():
            st.error("⚠️ Ingrese una API Key válida antes de procesar.")
            return None
        client = genai.Client(api_key=api_key.strip())
        ext = file_extension.lower().replace(".", "")
        mime_type = "application/pdf"
        if ext == "png": mime_type = "image/png"
        elif ext in ["jpg", "jpeg"]: mime_type = "image/jpeg"

        with st.spinner(f"📤 Subiendo archivo ({ext.upper()}) a Google File API..."):
            archivo_subido = client.files.upload(file=file_path, config={"mime_type": mime_type})

        with st.spinner("👁 Analizando documento con visión IA..."):
            prompt = """
            Eres un sistema experto en análisis de exámenes aeronáuticos. Extrae todas las preguntas, sus alternativas (A, B, C, D),
            la respuesta correcta marcada visualmente y clasifícala por materia aeronáutica ("Reglamentación y Normativa", "Meteorología Aeronáutica", 
            "Navegación y Planificación", "Fisiología y Factores Humanos", "Aerodinámica y Performance", "Sistemas y Motores", "Procedimientos Operativos").
            Devuelve ÚNICAMENTE un JSON válido con esta estructura:
            {
              "preguntas": [
                {
                  "pregunta": "Texto",
                  "opciones": ["Alt A", "Alt B", "Alt C", "Alt D"],
                  "respuesta_correcta": "A",
                  "categoria": "Fisiología y Factores Humanos"
                }
              ]
            }
            """
            config = types.GenerateContentConfig(response_mime_type="application/json", temperature=0.0)
            response, _ = ejecutar_gemini_con_fallback(
                client=client, contents_payload=[archivo_subido, prompt], config=config, modelo_preferido=modelo_preferido
            )

        preguntas_finales = []
        if response and response.text:
            data = json.loads(limpiar_respuesta_json(response.text))
            for idx_q, q in enumerate(data.get("preguntas", [])):
                enunciado = q.get("pregunta", "")
                opciones_textos = q.get("opciones", [])
                letra_corr = str(q.get("respuesta_correcta", "A")).strip().upper()
                categoria_q = q.get("categoria", "General").strip()
                alternativas_formateadas = []
                correcta_idx = None
                for idx_a, texto_alt in enumerate(opciones_textos[:4]):
                    letra_let = ['A', 'B', 'C', 'D'][idx_a]
                    es_correcta = (letra_let == letra_corr)
                    if es_correcta: correcta_idx = idx_a
                    alternativas_formateadas.append({"letra": letra_let, "texto": texto_alt, "marcada": es_correcta})
                if enunciado and len(alternativas_formateadas) >= 2:
                    preguntas_finales.append({
                        "idx_original": idx_q, "pregunta": enunciado, "alternativas": alternativas_formateadas,
                        "correcta": correcta_idx, "categoria": categoria_q
                    })
        return preguntas_finales
    except Exception as e:
        st.error(f"Error durante el procesamiento: {e}")
        return None
    finally:
        if client and archivo_subido:
            try: client.files.delete(name=archivo_subido.name)
            except Exception: pass

def obtener_explicacion_ia(pregunta_text, alternativas, idx_correcta, idx_elegida, api_key, modelo_preferido):
    try:
        client = genai.Client(api_key=api_key.strip())
        alt_corr_text = alternativas[idx_correcta]['texto'] if idx_correcta is not None and 0 <= idx_correcta < len(alternativas) else "N/A"
        alt_eleg_text = alternativas[idx_elegida]['texto'] if idx_elegida is not None and 0 <= idx_elegida < len(alternativas) else "Ninguna"
        prompt = f"""
        Como instructor de vuelo, explica brevemente el fundamento técnico de esta pregunta:
        Pregunta: "{pregunta_text}"
        Respuesta Correcta: "{alt_corr_text}"
        Respuesta Alumno: "{alt_eleg_text}"
        Explica la razón aeronáutica y da un consejo para recordarlo.
        """
        config = types.GenerateContentConfig(temperature=0.3)
        response, _ = ejecutar_gemini_con_fallback(client=client, contents_payload=[prompt], config=config, modelo_preferido=modelo_preferido)
        return response.text if response else "No disponible."
    except Exception as e:
        return f"Error: {e}"

# --- AUTENTICACIÓN ---
if st.session_state.usuario_actual is None:
    st.markdown("<h2 style='text-align: center; color: var(--accent-blue); padding-top: 5vh;'>✈️ AeroStudio Pro</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: var(--text-muted); margin-bottom: 2rem;'>Plataforma ejecutiva de entrenamiento aeronáutico con IA.</p>", unsafe_allow_html=True)
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
                    st.error("Credenciales incorrectas.")
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
                    st.error("El correo ya está registrado.")
                else:
                    usuarios_db[reg_email] = {"nombre": reg_nombre, "email": reg_email, "password": reg_pass}
                    guardar_usuarios(usuarios_db)
                    st.session_state.usuario_actual = reg_email
                    guardar_sesion_persistida(reg_email)
                    st.rerun()
    st.stop()

usuarios_db = cargar_usuarios()
datos_usuario = usuarios_db.get(st.session_state.usuario_actual, {"nombre": "Piloto", "email": st.session_state.usuario_actual, "password": ""})

# --- BARRA LATERAL (ESTILO EJECUTIVO IDÉNTICO A LA REFERENCIA) ---
with st.sidebar:
    st.markdown("""
    <div style="display: flex; align-items: center; gap: 12px; padding: 0.5rem 0.5rem 1.5rem 0.5rem;">
        <span style="font-size: 26px;">🛩️</span>
        <span style="font-size: 20px; font-weight: 700; color: #ffffff; letter-spacing: -0.5px;">AeroStudio</span>
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("👤 Perfil", use_container_width=True):
        st.session_state.vista = "perfil"
        st.rerun()
    if st.button("🏠 Panel Principal", use_container_width=True):
        st.session_state.vista = "home"
        st.session_state.modo_estudio_data = None
        st.rerun()
    if st.button("📊 Historial", use_container_width=True):
        st.session_state.vista = "historial"
        st.rerun()
        
    st.markdown("<div style='margin: 1.5rem 0; border-top: 1px solid rgba(255,255,255,0.1);'></div>", unsafe_allow_html=True)
    st.markdown("<p style='font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: #64748b; padding-left: 10px;'>Configuración IA</p>", unsafe_allow_html=True)
    
    if not st.session_state["gemini_api_key"]:
        user_input_key = st.text_input("Gemini API Key", type="password")
        if user_input_key:
            st.session_state["gemini_api_key"] = user_input_key.strip()
            st.success("¡Guardada!")

    texto_modo = "🌙 Modo Nocturno" if not st.session_state.modo_oscuro else "☀️ Modo Claro"
    if st.button(texto_modo, use_container_width=True):
        st.session_state.modo_oscuro = not st.session_state.modo_oscuro
        st.rerun()

    st.markdown("<div style='margin: 1.5rem 0; border-top: 1px solid rgba(255,255,255,0.1);'></div>", unsafe_allow_html=True)
    st.caption(f"Conectado: {datos_usuario['nombre']}")
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.usuario_actual = None
        eliminar_sesion_persistida()
        st.session_state.vista = "home"
        st.session_state.modo_estudio_data = None
        st.rerun()

# --- VISTA: PERFIL ---
if st.session_state.vista == "perfil":
    st.title("👤 Configuración de Perfil")
    col1, col2 = st.columns([2, 1])
    with col1:
        with st.form("form_perfil"):
            nuevo_nombre = st.text_input("Nombre de usuario:", value=datos_usuario["nombre"])
            nuevo_email = st.text_input("Correo electrónico:", value=datos_usuario["email"])
            nueva_pass = st.text_input("Contraseña:", value=datos_usuario["password"], type="password")
            st.write("")
            if st.form_submit_button("Guardar Cambios", type="primary"):
                email_viejo = st.session_state.usuario_actual
                nuevo_email_limpio = nuevo_email.strip().lower()
                usuarios_db[email_viejo]["nombre"] = nuevo_nombre
                usuarios_db[email_viejo]["password"] = nueva_pass
                if nuevo_email_limpio != email_viejo:
                    usuarios_db[nuevo_email_limpio] = usuarios_db.pop(email_viejo)
                    st.session_state.usuario_actual = nuevo_email_limpio
                    guardar_sesion_persistida(nuevo_email_limpio)
                guardar_usuarios(usuarios_db)
                st.success("¡Actualizado con éxito!")
                st.rerun()
    if st.button("⬅ Volver"):
        st.session_state.vista = "home"
        st.rerun()

# --- VISTA: HISTORIAL Y DIAGNÓSTICO ---
elif st.session_state.vista == "historial":
    st.title("📊 Historial y Diagnóstico por Materias")
    historial = obtener_historial_reciente()
    if not historial:
        st.info("Aún no hay registros en tu historial.")
    else:
        df_hist = pd.DataFrame(historial)
        col1, col2 = st.columns(2)
        with col1:
            st.metric(label="Promedio General de Aciertos", value=f"{df_hist['puntaje'].mean():.1f}%")
        with col2:
            st.metric(label="Total de Pruebas", value=len(df_hist))
        
        st.divider()
        st.subheader("📜 Registro de Evaluaciones")
        for h in historial:
            with st.container():
                c1, c2, c3 = st.columns([3, 2, 2])
                c1.markdown(f"**Prueba:** {h['prueba']}")
                c2.markdown(f"📅 {h['fecha']}")
                c3.markdown(f"🎯 **Puntaje:** {h['puntaje']}% `({h['correctas']}/{h['total']})`")
                st.divider()
    if st.button("⬅️ Regresar al Inicio"):
        st.session_state.vista = "home"
        st.rerun()

# --- VISTA: ESTUDIO (EXAMEN INTERACTIVO CON LIMPIEZA DE ALTERNATIVAS) ---
elif st.session_state.vista == "estudio" and st.session_state.modo_estudio_data:
    estudio = st.session_state.modo_estudio_data
    preguntas = estudio["preguntas"]
    idx_actual = estudio["idx_actual"]
    b_id_actual = estudio.get("b_id")
    
    if not preguntas:
        st.error("No hay preguntas disponibles.")
        if st.button("Volver"):
            st.session_state.vista = "home"
            st.rerun()
        st.stop()
        
    if "respuestas_usuario" not in estudio:
        estudio["respuestas_usuario"] = {}
    resp_dict = estudio["respuestas_usuario"]

    total_preguntas = len(preguntas)
    respondidas_ok = sum(1 for k, v in resp_dict.items() if v.get("estado") == "correcta")
    
    q_actual = preguntas[idx_actual]
    
    # Contenedor Tarjeta Flotante Principal Estilo UI Examen
    st.markdown(f"""
    <div style="background-color: var(--bg-card); padding: 2rem; border-radius: 16px; border: 1px solid var(--border-color); box-shadow: var(--card-shadow); margin-bottom: 1.5rem;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
            <span style="font-weight: 600; font-size: 1.1rem; color: var(--text-main);">{estudio['nombre_prueba']}</span>
            <span style="font-weight: 600; color: var(--text-muted); background: var(--bg-main); padding: 4px 12px; border-radius: 20px; font-size: 0.9rem;">Q {idx_actual + 1}/{total_preguntas}</span>
        </div>
        <div style="width: 100%; background-color: var(--border-color); height: 6px; border-radius: 3px; margin-bottom: 1.5rem; overflow: hidden;">
            <div style="width: {int(((idx_actual + 1) / total_preguntas) * 100)}%; background-color: var(--accent-blue); height: 100%; transition: width 0.3s ease;"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    col_ctrl1, col_ctrl2 = st.columns([1, 1])
    with col_ctrl1:
        with st.popover("⚙️️ Ajustar Respuesta Correcta", help="Modifica la respuesta correcta si el documento tiene un error"):
            st.markdown("#### Corrección Manual")
            opciones_textos_pop = [f"{alt['letra']}.- {alt['texto']}" for alt in q_actual["alternativas"]]
            current_correct = q_actual.get("correcta", 0)
            if current_correct is None or current_correct >= len(opciones_textos_pop): current_correct = 0
            nueva_corr_sel = st.selectbox("Correcta:", options=range(len(opciones_textos_pop)), format_func=lambda x: opciones_textos_pop[x], index=current_correct, key=f"pop_corr_{idx_actual}")
            if st.button("Guardar Corrección", key=f"btn_save_{idx_actual}"):
                q_actual["correcta"] = nueva_corr_sel
                if b_id_actual: actualizar_pregunta_individual(b_id_actual, q_actual.get("idx_original", idx_actual), nueva_corr_sel)
                st.success("¡Guardado!")
                st.rerun()
    with col_ctrl2:
        with st.popover("🔢 Ir a Pregunta (Cuadrícula)", help="Salto rápido a cualquier número de pregunta"):
            cols_grid = st.columns(5)
            for i in range(total_preguntas):
                st_q = resp_dict.get(i, {}).get("estado")
                lbl = f"🔵 {i+1}" if i == idx_actual else (f"🟢 {i+1}" if st_q == "correcta" else (f"🔴 {i+1}" if st_q == "incorrecta" else f"⚪ {i+1}"))
                with cols_grid[i % 5]:
                    if st.button(lbl, key=f"grid_{i}", use_container_width=True):
                        estudio["idx_actual"] = i
                        st.rerun()

    st.markdown(f"### {idx_actual + 1}.- {q_actual['pregunta']}")
    
    if idx_actual not in resp_dict:
        resp_dict[idx_actual] = {"elegida": None, "estado": None, "corregido": False}
    
    estado_actual_q = resp_dict[idx_actual]
    corregido = estado_actual_q.get("corregido", False)
    opciones_tuplas = [(i, f"{alt['letra']}.- {alt['texto']}") for i, alt in enumerate(q_actual["alternativas"])]
    
    seleccion_indice_actual = estado_actual_q.get("elegida", None)
    
    # --- RADIO SIN OPCIÓN POR DEFECTO NI ETIQUETA ---
    seleccion_tuple = st.radio(
        "Alternativas:",
        options=opciones_tuplas,
        format_func=lambda x: x[1],
        disabled=corregido,
        index=seleccion_indice_actual if seleccion_indice_actual is not None else None,
        key=f"radio_alt_{idx_actual}",
        label_visibility="collapsed"
    )
    
    if seleccion_tuple is not None and not corregido:
        resp_dict[idx_actual]["elegida"] = seleccion_tuple[0]

    if corregido:
        idx_correcta = q_actual.get("correcta")
        if idx_correcta is not None and idx_correcta < len(q_actual["alternativas"]):
            letra_correcta = q_actual["alternativas"][idx_correcta]["letra"]
            if estado_actual_q["estado"] == "correcta":
                st.success("🎯 ¡Respuesta Correcta!")
            else:
                st.error(f"❌ Incorrecto. La respuesta correcta era la **{letra_correcta}**.")

        with st.expander("💡 Explicación del Instructor IA"):
            if st.button("Consultar Fundamento Aeronáutico", key=f"btn_ia_{idx_actual}"):
                if not st.session_state["gemini_api_key"]:
                    st.error("Configura tu API Key en la barra lateral.")
                else:
                    with st.spinner("Generando explicación..."):
                        expl = obtener_explicacion_ia(q_actual["pregunta"], q_actual["alternativas"], idx_correcta, estado_actual_q.get("elegida"), st.session_state["gemini_api_key"], st.session_state["gemini_modelo"])
                        st.info(expl)

    st.write("")
    c_btn1, c_btn2 = st.columns([1, 1])
    with c_btn1:
        if not corregido:
            if st.button("Validar Respuesta", key=f"val_{idx_actual}", use_container_width=True):
                sel = resp_dict[idx_actual].get("elegida")
                corr = q_actual.get("correcta")
                if sel is None:
                    st.warning("Selecciona una alternativa.")
                elif corr is None:
                    st.error("Asigna una respuesta correcta con el engranaje ⚙️.")
                else:
                    resp_dict[idx_actual]["estado"] = "correcta" if sel == corr else "incorrecta"
                    resp_dict[idx_actual]["corregido"] = True
                    st.rerun()
        else:
            if st.button("⬅️ Anterior", use_container_width=True):
                if idx_actual > 0:
                    estudio["idx_actual"] -= 1
                    st.rerun()
    with c_btn2:
        if st.button("Siguiente ➡", key=f"next_{idx_actual}", use_container_width=True):
            if idx_actual < total_preguntas - 1:
                estudio["idx_actual"] += 1
                st.rerun()
            else:
                puntaje_final = int((respondidas_ok / total_preguntas) * 100) if total_preguntas > 0 else 0
                desglose_cat, falladas_orig, ok_orig = {}, [], []
                for i_q, q_item in enumerate(preguntas):
                    cat = q_item.get("categoria", "General")
                    if cat not in desglose_cat: desglose_cat[cat] = {"ok": 0, "total": 0}
                    desglose_cat[cat]["total"] += 1
                    orig_idx = q_item.get("idx_original", i_q)
                    if resp_dict.get(i_q, {}).get("estado") == "correcta":
                        desglose_cat[cat]["ok"] += 1
                        ok_orig.append(orig_idx)
                    else:
                        falladas_orig.append(orig_idx)
                if b_id_actual:
                    registrar_preguntas_falladas(b_id_actual, falladas_orig)
                    limpiar_falladas_resueltas(b_id_actual, ok_orig)
                guardar_resultado_historial(estudio["nombre_prueba"], puntaje_final, respondidas_ok, total_preguntas, desglose_cat)
                st.success(f"🎉 Examen finalizado. Nota: {puntaje_final}%")
                if st.button("Volver al Inicio", use_container_width=True):
                    st.session_state.vista = "home"
                    st.session_state.modo_estudio_data = None
                    st.rerun()

# --- VISTA: HOME (PANEL PRINCIPAL) ---
else:
    st.title("📚 Panel Principal - Bancos de Preguntas")
    st.markdown(f"Bienvenido, **{datos_usuario['nombre']}**. Selecciona o importa tus bancos de preguntas.")
    st.divider()

    with st.container():
        st.subheader("➕ Importar Nuevo Banco")
        uploaded_file = st.file_uploader("Sube tu examen en PDF o imagen escaneada", type=["pdf", "png", "jpg", "jpeg"])
        nombre_nueva_prueba = st.text_input("Título descriptivo:", placeholder="Ej. Examen de Fisiología")
        if st.button("Procesar y Generar", type="primary"):
            if uploaded_file and nombre_nueva_prueba:
                tmp_path = None
                try:
                    ext = os.path.splitext(uploaded_file.name)[1]
                    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp_file:
                        tmp_file.write(uploaded_file.getvalue())
                        tmp_path = tmp_file.name
                    preguntas_extraidas = procesar_documento_multimodal(tmp_path, st.session_state["gemini_api_key"], st.session_state["gemini_modelo"], ext)
                    if preguntas_extraidas:
                        id_limpio = re.sub(r'[^a-zA-Z0-9_\-]', '_', nombre_nueva_prueba)
                        guardar_banco(id_limpio, {"nombre": nombre_nueva_prueba, "preguntas": preguntas_extraidas})
                        st.success(f"¡Éxito! {len(preguntas_extraidas)} preguntas procesadas.")
                        st.rerun()
                    else:
                        st.error("No se pudieron extraer preguntas.")
                finally:
                    if tmp_path and os.path.exists(tmp_path): os.unlink(tmp_path)
            else:
                st.warning("Completa los campos obligatorios.")

    st.divider()
    st.subheader("Bancos Disponibles")
    bancos = listar_bancos()
    if not bancos:
        st.info("No hay bancos cargados.")
    
    for b_id in bancos:
        banco_data = cargar_banco(b_id)
        if not banco_data: continue
        todas_preguntas = list(banco_data.get("preguntas", []))
        usuario_actual = st.session_state.usuario_actual or "default"
        num_falladas = len(banco_data.get("falladas", {}).get(usuario_actual, []))

        with st.container():
            c1, c2, c3, c4 = st.columns([3, 1.2, 1.8, 0.5])
            c1.markdown(f"**{banco_data.get('nombre', b_id)}**")
            c1.caption(f"Total: {len(todas_preguntas)} preguntas | 🔴 Falladas: {num_falladas}")
            modo_rnd = c2.checkbox("🔀 Aleatorio", key=f"rnd_{b_id}")
            
            with c3:
                cb1, cb2 = st.columns(2)
                if cb1.button("🚀 Iniciar", key=f"start_{b_id}", use_container_width=True):
                    limpiar_radios_session()
                    preg = list(todas_preguntas)
                    if modo_rnd: random.shuffle(preg)
                    if preg:
                        st.session_state.modo_estudio_data = {"preguntas": preg, "idx_actual": 0, "b_id": b_id, "nombre_prueba": banco_data.get('nombre', b_id), "respuestas_usuario": {}}
                        st.session_state.vista = "estudio"
                        st.rerun()
                if cb2.button("🔴 Repaso", key=f"repaso_{b_id}", disabled=(num_falladas == 0), use_container_width=True):
                    limpiar_radios_session()
                    preg_rep = [q for q in todas_preguntas if q.get("idx_original") in banco_data.get("falladas", {}).get(usuario_actual, [])]
                    if modo_rnd: random.shuffle(preg_rep)
                    if preg_rep:
                        st.session_state.modo_estudio_data = {"preguntas": preg_rep, "idx_actual": 0, "b_id": b_id, "nombre_prueba": f"{banco_data.get('nombre', b_id)} (Repaso)", "respuestas_usuario": {}}
                        st.session_state.vista = "estudio"
                        st.rerun()
            with c4:
                if st.button("🗑️", key=f"del_{b_id}", help="Eliminar banco"):
                    if eliminar_banco(b_id):
                        st.toast("Banco eliminado.")
                        time.sleep(0.5)
                        st.rerun()
        st.divider()
