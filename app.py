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
    page_title="AeroStudio Pro - Simulador de Vuelo",
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
    "background_color": "#141c2b",
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
    st.session_state.modo_oscuro = True
if "vista" not in st.session_state:
    st.session_state.vista = "home"
if "modo_estudio_data" not in st.session_state:
    st.session_state.modo_estudio_data = None


# --- ESTILOS CSS (MODO CLARO Y MODO LECTURA NOCTURNA AZUL MARINO / DORADO) ---
css_light = """
    :root {
        --bg-main: #f8fafc;
        --bg-card: #ffffff;
        --bg-card-hover: #f1f5f9;
        --bg-sidebar: #ffffff;
        --accent-blue: #0284c7;
        --accent-hover: #0369a1;
        --accent-gold: #d97706;
        --text-main: #0f172a;
        --text-muted: #64748b;
        --border-color: #e2e8f0;
        --sidebar-bg: #f8fafc;
    }
"""

css_dark = """
    :root {
        --bg-main: #141c2b;
        --bg-card: #1d273a;
        --bg-card-hover: #243147;
        --bg-sidebar: #101622;
        --accent-blue: #d97706;
        --accent-hover: #f59e0b;
        --accent-gold: #f59e0b;
        --text-main: #f8fafc;
        --text-muted: #94a3b8;
        --border-color: #2b3952;
        --sidebar-bg: #101622;
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
        background-color: var(--bg-main) !important;
        color: var(--text-main) !important;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
    }}
    header[data-testid="stHeader"] {{
        background-color: transparent !important;
        z-index: 99999;
    }}
    button[data-testid="stSidebarCollapseButton"], button[data-testid="baseButton-header"] {{
        color: var(--text-main) !important;
        background-color: var(--bg-card) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 8px !important;
    }}
    div.stButton > button {{
        background: linear-gradient(135deg, var(--accent-blue) 0%, var(--accent-hover) 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 0.6rem 1.2rem !important;
        font-weight: 600 !important;
        box-shadow: 0 4px 12px rgba(217, 119, 6, 0.15) !important;
        transition: all 0.2s ease-in-out !important;
    }}
    div.stButton > button:hover {{
        transform: translateY(-2px) !important;
    }}
    div.stButton > button[kind="secondary"] {{
        background: var(--bg-card) !important;
        border: 1px solid var(--border-color) !important;
        color: var(--text-main) !important;
        box-shadow: none !important;
    }}
    div.stButton > button[kind="secondary"]:hover {{
        border-color: var(--accent-gold) !important;
        color: var(--accent-gold) !important;
    }}
    .stTextInput input, .stSelectbox select, .stPasswordInput input {{
        background-color: var(--bg-card) !important;
        color: var(--text-main) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 8px !important;
        padding: 0.6rem 1rem !important;
    }}
    section[data-testid="stSidebar"] {{
        background-color: var(--sidebar-bg) !important;
        border-right: 1px solid var(--border-color) !important;
    }}
    div[data-testid="metric-container"] {{
        background-color: var(--bg-card) !important;
        border: 1px solid var(--border-color) !important;
        padding: 1.2rem !important;
        border-radius: 10px !important;
    }}
    .stRadio label {{
        padding: 12px 16px !important;
        border-radius: 8px !important;
        background-color: var(--bg-card) !important;
        border: 1px solid var(--border-color) !important;
        transition: background 0.2s !important;
        width: 100% !important;
        margin-bottom: 6px !important;
    }}
    .stRadio label:hover {{
        border-color: var(--accent-gold) !important;
        background-color: var(--bg-card-hover) !important;
    }}
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
    }}
    .user-info-name {{
        font-weight: 700;
        font-size: 0.95rem;
        color: var(--text-main);
    }}
    .user-info-role {{
        font-size: 0.78rem;
        color: var(--text-muted);
    }}
    .study-overlay-card {{
        background-color: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.25);
        margin-top: 10px;
    }}
</style>
""", unsafe_allow_html=True)


# --- ALMACENAMIENTO LOCAL DE BANCOS Y USUARIOS ---
DATA_DIR = "data_bancos"
HISTORY_FILE = "historial_resultados.json"
USERS_FILE = "usuarios.json"
SESSION_FILE = "sesion_activa.json"

os.makedirs(DATA_DIR, exist_ok=True)


# --- CONFIGURACIÓN Y DESCUBRIMIENTO DINÁMICO DE GEMINI ---
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
        raise ImportError("La librería google-genai no está disponible en el servidor. Asegúrate de incluir `google-genai` en el archivo `requirements.txt`.")

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
                data = json.load(f)
                return data.get("usuario")
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


# --- OPERACIONES CON ARCHIVOS JSON DE BANCOS ---
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


def procesar_documento_multimodal(file_path, api_key, modelo_preferido, file_extension):
    if not GENAI_DISPONIBLE:
        st.error("⚠️ La librería `google-genai` no está instalada en el servidor. Asegúrate de incluir `google-genai` en el archivo `requirements.txt`.")
        return None

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

        with st.spinner("👁 Analizando documento visualmente con Gemini (Extrayendo preguntas, pautas y asignando materias)..."):
            prompt = """
            Eres un sistema experto en análisis de documentos aeronáuticos de evaluación.
            Analiza este documento e identifica todas las preguntas de selección múltiple, sus alternativas,
            la respuesta correcta asignada en la pauta o marcación, y asigna a cada una una categoría temática aeronáutica.

            FORMATO DE SALIDA JSON STRICTO:
            {
              "preguntas": [
                {
                  "pregunta": "Enunciado de la pregunta...",
                  "opciones": ["Opcion A", "Opcion B", "Opcion C", "Opcion D"],
                  "respuesta_correcta": "A",
                  "categoria": "Materia Temática"
                }
              ]
            }
            """

            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.0
            )

            response, _ = ejecutar_gemini_con_fallback(
                client=client,
                contents_payload=[archivo_subido, prompt],
                config=config,
                modelo_preferido=modelo_preferido
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

    except Exception as e:
        st.error(f"Error durante el procesamiento con Gemini: {e}")
        return None
    finally:
        if client and archivo_subido:
            try:
                client.files.delete(name=archivo_subido.name)
            except Exception:
                pass


def obtener_explicacion_ia(pregunta_text, alternativas, idx_correcta, idx_elegida, api_key, modelo_preferido):
    if not GENAI_DISPONIBLE:
        return "⚠️ La librería `google-genai` no está disponible."

    try:
        client = genai.Client(api_key=api_key.strip())

        alt_corr_text = alternativas[idx_correcta]['texto'] if (idx_correcta is not None and 0 <= idx_correcta < len(alternativas)) else "N/A"
        alt_eleg_text = alternativas[idx_elegida]['texto'] if (idx_elegida is not None and 0 <= idx_elegida < len(alternativas)) else "Ninguna"

        prompt = f"""
        Eres un instructor de vuelo y pedagogo aeronáutico experto.
        Explica brevemente y de forma didáctica el fundamento de esta pregunta:

        Pregunta: "{pregunta_text}"
        Respuesta Correcta Oficial: "{alt_corr_text}"
        Respuesta Seleccionada por el Alumno: "{alt_eleg_text}"
        """

        config = types.GenerateContentConfig(temperature=0.3)
        response, _ = ejecutar_gemini_con_fallback(
            client=client,
            contents_payload=[prompt],
            config=config,
            modelo_preferido=modelo_preferido
        )
        return response.text if response else "No se pudo generar la explicación."
    except Exception as e:
        return f"Error al consultar al instructor IA: {e}"


# --- INICIO DE SESIÓN / CONTROL DE ACCESO ---
if st.session_state.usuario_actual is None:
    st.markdown("<h2 style='text-align: center; color: var(--accent-gold); padding-top: 5vh;'>✈️ AeroStudio Pro</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: var(--text-muted); margin-bottom: 2rem;'>Centro de entrenamiento e instrucción aeronáutica.</p>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        tab_login, tab_registro = st.tabs(["Iniciar Sesión", "Registrarse"])

        with tab_login:
            with st.form("form_login"):
                email_ingreso = st.text_input("Correo electrónico:", key="login_email")
                pass_ingreso = st.text_input("Contraseña:", type="password", key="login_pass")
                st.write("")
                btn_login = st.form_submit_button("Entrar al Sistema", type="primary", use_container_width=True)

                if btn_login:
                    exito, mensaje = autenticar_usuario(email_ingreso, pass_ingreso)
                    if exito:
                        email_clean = email_ingreso.strip().lower()
                        st.session_state.usuario_actual = email_clean
                        guardar_sesion_persistida(email_clean)
                        st.success(mensaje)
                        st.rerun()
                    else:
                        st.error(mensaje)

        with tab_registro:
            with st.form("form_registro"):
                reg_nombre = st.text_input("Nombre completo:", key="reg_name")
                reg_email = st.text_input("Correo electrónico:", key="reg_email")
                reg_pass = st.text_input("Contraseña:", type="password", key="reg_pass")
                st.write("")
                btn_reg = st.form_submit_button("Crear Cuenta", type="primary", use_container_width=True)

                if btn_reg:
                    reg_email_clean = reg_email.strip().lower()
                    reg_pass_clean = reg_pass.strip()
                    reg_nombre_clean = reg_nombre.strip()

                    if not reg_email_clean or not reg_pass_clean or not reg_nombre_clean:
                        st.warning("Completa todos los campos.")
                    else:
                        usuarios_db = inicializar_usuarios()
                        if reg_email_clean in usuarios_db:
                            st.error("Este correo ya está registrado.")
                        else:
                            usuarios_db[reg_email_clean] = {
                                "nombre": reg_nombre_clean,
                                "email": reg_email_clean,
                                "password": reg_pass_clean,
                                "rol": "user"
                            }
                            guardar_usuarios(usuarios_db)
                            st.session_state.usuarios_db = usuarios_db
                            st.session_state.usuario_actual = reg_email_clean
                            guardar_sesion_persistida(reg_email_clean)
                            st.success("¡Cuenta creada con éxito!")
                            st.rerun()
    st.stop()


usuarios_db = inicializar_usuarios()
datos_usuario = usuarios_db.get(st.session_state.usuario_actual, {"nombre": "Piloto", "email": st.session_state.usuario_actual, "password": ""})


# --- BARRA LATERAL ---
with st.sidebar:
    st.markdown(f"""
        <div class="user-profile-badge">
            <div class="user-avatar">👨‍✈️</div>
            <div>
                <div class="user-info-name">{datos_usuario.get('nombre', 'Piloto')}</div>
                <div class="user-info-role">Piloto en Entrenamiento</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    st.divider()

    if st.button("👤 Perfil de Usuario", use_container_width=True):
        st.session_state.vista = "perfil"
        st.rerun()
    if st.button("🏠 Panel Principal", use_container_width=True):
        st.session_state.vista = "home"
        st.session_state.modo_estudio_data = None
        st.rerun()
    if st.button("📊 Historial y Diagnóstico", use_container_width=True):
        st.session_state.vista = "historial"
        st.rerun()

    st.divider()

    texto_modo = "☀️ Cambiar a Modo Claro" if st.session_state.modo_oscuro else "🌙 Activar Modo Lectura Nocturna (Filtro Cálido)"
    if st.button(texto_modo, use_container_width=True, type="secondary"):
        st.session_state.modo_oscuro = not st.session_state.modo_oscuro
        st.rerun()

    st.divider()
    st.markdown("### ⚙️ Configuración de IA")

    if not GENAI_DISPONIBLE:
        st.warning("⚠️ Módulo `google-genai` no detectado.")

    if not st.session_state["gemini_api_key"]:
        user_input_key = st.text_input("Google Gemini API Key", type="password", help="Ingresa tu clave de AI Studio")
        if user_input_key:
            st.session_state["gemini_api_key"] = user_input_key.strip()
            st.success("¡API Key guardada!")

    estado_genai = f"`{st.session_state['gemini_modelo']}`" if GENAI_DISPONIBLE else "`GenAI Pendiente`"
    st.info(f"🟢 **Estado Conexión:** {estado_genai}")

    st.write("")
    if st.button("🚪 Cerrar Sesión", type="secondary", use_container_width=True):
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
            nuevo_nombre = st.text_input("Nombre de usuario:", value=datos_usuario.get("nombre", ""))
            nuevo_email = st.text_input("Correo electrónico:", value=datos_usuario.get("email", ""))
            nueva_pass = st.text_input("Nueva contraseña:", value=datos_usuario.get("password", ""), type="password")
            st.write("")
            if st.form_submit_button("Guardar Cambios", type="primary"):
                email_viejo = st.session_state.usuario_actual
                nuevo_email_limpio = nuevo_email.strip().lower()
                nueva_pass_limpia = nueva_pass.strip()
                nuevo_nombre_limpio = nuevo_nombre.strip()

                usuarios_db = inicializar_usuarios()

                if nuevo_email_limpio != email_viejo:
                    if nuevo_email_limpio in usuarios_db:
                        st.error("El correo ya está registrado por otro usuario.")
                    else:
                        rol_actual = usuarios_db.get(email_viejo, {}).get("rol", "user")
                        usuarios_db[nuevo_email_limpio] = {
                            "nombre": nuevo_nombre_limpio,
                            "email": nuevo_email_limpio,
                            "password": nueva_pass_limpia,
                            "rol": rol_actual
                        }
                        if email_viejo in usuarios_db:
                            del usuarios_db[email_viejo]
                        guardar_usuarios(usuarios_db)
                        st.session_state.usuarios_db = usuarios_db
                        st.session_state.usuario_actual = nuevo_email_limpio
                        guardar_sesion_persistida(nuevo_email_limpio)
                        st.success("¡Perfil actualizado!")
                        st.rerun()
                else:
                    usuarios_db[email_viejo]["nombre"] = nuevo_nombre_limpio
                    usuarios_db[email_viejo]["password"] = nueva_pass_limpia
                    guardar_usuarios(usuarios_db)
                    st.session_state.usuarios_db = usuarios_db
                    st.success("¡Perfil actualizado!")
                    st.rerun()
    if st.button("⬅ Volver al Inicio", type="secondary"):
        st.session_state.vista = "home"
        st.rerun()


# --- VISTA: HISTORIAL ---
elif st.session_state.vista == "historial":
    st.title("📊 Historial de Rendimiento y Diagnóstico")
    historial = obtener_historial_reciente()
    if not historial:
        st.info("No hay registros recientes en tu historial.")
    else:
        df_hist = pd.DataFrame(historial)
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            promedio = df_hist['puntaje'].mean()
            st.metric(label="Promedio General de Aciertos", value=f"{promedio:.1f}%")
        with col_m2:
            st.metric(label="Pruebas Realizadas", value=len(df_hist))

        st.divider()
        st.subheader("🎯 Rendimiento Acumulado por Área Temática")

        cat_stats = {}
        for reg in historial:
            for cat, stats in reg.get("desglose_categorias", {}).items():
                if cat not in cat_stats:
                    cat_stats[cat] = {"ok": 0, "total": 0}
                cat_stats[cat]["ok"] += stats.get("ok", 0)
                cat_stats[cat]["total"] += stats.get("total", 0)

        if cat_stats:
            cat_rows = []
            for cat, data in cat_stats.items():
                pct = int((data["ok"] / data["total"]) * 100) if data["total"] > 0 else 0
                cat_rows.append({
                    "Materia Aeronáutica": cat,
                    "Aciertos": f"{data['ok']}/{data['total']}",
                    "Porcentaje de Dominio": f"{pct}%"
                })
            df_cat = pd.DataFrame(cat_rows)
            st.dataframe(df_cat, use_container_width=True)

        st.divider()
        st.subheader("📜 Registro de Pruebas")
        for h in historial:
            with st.container():
                col1, col2, col3 = st.columns([3, 2, 2])
                col1.markdown(f"**Prueba:** {h['prueba']}")
                col2.markdown(f"📅 {h['fecha']}")
                col3.markdown(f"🎯 **Puntaje:** {h['puntaje']}% `({h['correctas']}/{h['total']})`")
                st.divider()
    if st.button("⬅️ Regresar al Inicio", type="secondary"):
        st.session_state.vista = "home"
        st.rerun()


# --- VISTA: ESTUDIO ---
elif st.session_state.vista == "estudio" and st.session_state.modo_estudio_data:
    estudio = st.session_state.modo_estudio_data
    preguntas = estudio["preguntas"]
    idx_actual = estudio["idx_actual"]
    b_id_actual = estudio.get("b_id")

    if not preguntas:
        st.error("Este banco de preguntas no contiene elementos válidos.")
        if st.button("Volver al Menú Principal", type="secondary"):
            st.session_state.vista = "home"
            st.rerun()
        st.stop()

    if "respuestas_usuario" not in estudio:
        estudio["respuestas_usuario"] = {}
    resp_dict = estudio["respuestas_usuario"]

    total_preguntas = len(preguntas)
    respondidas_ok = sum(1 for k, v in resp_dict.items() if v.get("estado") == "correcta")
    respondidas_fail = sum(1 for k, v in resp_dict.items() if v.get("estado") in ["incorrecta", "omitida"])
    puntaje_porcentaje = int((respondidas_ok / total_preguntas) * 100) if total_preguntas > 0 else 0

    col_centered = st.columns([0.1, 0.8, 0.1])[1]

    with col_centered:
        st.markdown('<div class="study-overlay-card">', unsafe_allow_html=True)

        col_top1, col_top_gear, col_top2 = st.columns([4, 0.6, 2.5])
        with col_top1:
            st.markdown(f"⏱️ **Q: {idx_actual + 1}/{total_preguntas}** &nbsp;|&nbsp; ✅ {respondidas_ok} &nbsp;|&nbsp; ❌ {respondidas_fail} &nbsp;|&nbsp; 📈 **{puntaje_porcentaje}%**")

        with col_top_gear:
            with st.popover("⚙️", help="Ajustar respuesta correcta"):
                st.markdown("#### 🛠 Corrección Manual")
                q_actual_pop = preguntas[idx_actual]
                opciones_textos_pop = [f"{alt['letra']}.- {alt['texto']}" for alt in q_actual_pop["alternativas"]]
                current_correct = q_actual_pop.get("correcta", 0)
                if current_correct is None or current_correct >= len(opciones_textos_pop):
                    current_correct = 0

                nueva_corr_sel = st.selectbox(
                    "Respuesta correcta:",
                    options=range(len(opciones_textos_pop)),
                    format_func=lambda x: opciones_textos_pop[x],
                    index=current_correct,
                    key=f"pop_corr_{idx_actual}"
                )

                if st.button("Guardar Corrección", key=f"btn_pop_save_{idx_actual}", type="primary", use_container_width=True):
                    q_actual_pop["correcta"] = nueva_corr_sel
                    idx_orig = q_actual_pop.get("idx_original", idx_actual)
                    if b_id_actual:
                        actualizar_pregunta_individual(b_id_actual, idx_orig, nueva_corr_sel)
                    st.success("¡Respuesta actualizada!")
                    st.rerun()

        with col_top2:
            with st.popover("🔢 Cuadrícula", help="Navegador de preguntas"):
                cols_grid = st.columns(5)
                for i in range(total_preguntas):
                    estado_q = resp_dict.get(i, {}).get("estado")
                    label_btn = f"🔵 {i+1}" if i == idx_actual else (f"🟢 {i+1}" if estado_q == "correcta" else (f"🔴 {i+1}" if estado_q == "incorrecta" else (f"⚪ {i+1}" if estado_q == "omitida" else f"⚫ {i+1}")))
                    with cols_grid[i % 5]:
                        if st.button(label_btn, key=f"grid_q_{i}", use_container_width=True):
                            estudio["idx_actual"] = i
                            st.rerun()

        st.progress((idx_actual + 1) / total_preguntas)
        st.write("")

        q_actual = preguntas[idx_actual]
        cat_tag = q_actual.get("categoria", "Fisiología y Factores Humanos")
        st.caption(f"📌 Categoría: **{cat_tag}**")
        st.markdown(f"#### **{idx_actual + 1}.- {q_actual['pregunta']}**")

        if idx_actual not in resp_dict:
            resp_dict[idx_actual] = {"elegida": None, "estado": None, "corregido": False}

        estado_actual_q = resp_dict[idx_actual]
        corregido = estado_actual_q.get("corregido", False)

        opciones_tuplas = [(i, f"{alt['letra']}.- {alt['texto']}") for i, alt in enumerate(q_actual["alternativas"])]

        radio_key = f"radio_alt_{idx_actual}"
        seleccion_indice_actual = estado_actual_q.get("elegida", None)

        current_index = None
        if seleccion_indice_actual is not None and 0 <= seleccion_indice_actual < len(opciones_tuplas):
            current_index = seleccion_indice_actual

        seleccion_tuple = st.radio(
            "Alternativas disponibles:",
            options=opciones_tuplas,
            format_func=lambda x: x[1],
            disabled=corregido,
            index=current_index,
            key=radio_key,
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
                    st.error(f"❌ Respuesta Incorrecta. La opción correcta es la **{letra_correcta}**.")

            with st.expander("💡 Explicación del Instructor IA"):
                if st.button("🤖 Solicitar Explicación Aeronáutica", key=f"btn_exp_ia_{idx_actual}", type="secondary"):
                    if not st.session_state["gemini_api_key"]:
                        st.error("Configura tu API Key en la barra lateral.")
                    else:
                        with st.spinner("Analizando concepto técnico..."):
                            explicacion = obtener_explicacion_ia(
                                q_actual["pregunta"],
                                q_actual["alternativas"],
                                idx_correcta,
                                estado_actual_q.get("elegida"),
                                st.session_state["gemini_api_key"],
                                st.session_state["gemini_modelo"]
                            )
                            st.info(explicacion)

        st.write("")
        col_bot1, col_bot2, col_bot3 = st.columns([2.5, 2, 3.5])
        with col_bot1:
            if st.button("⬅ Omitir", key=f"btn_omitir_{idx_actual}", type="secondary", use_container_width=True):
                resp_dict[idx_actual]["estado"] = "omitida"
                resp_dict[idx_actual]["corregido"] = True
                if idx_actual < total_preguntas - 1:
                    estudio["idx_actual"] += 1
                    st.rerun()
                else:
                    st.warning("Has llegado al final de la prueba.")

        with col_bot3:
            texto_boton = "Siguiente ➡" if corregido else "Validar Respuesta"
            if st.button(texto_boton, key=f"btn_validar_{idx_actual}", type="primary", use_container_width=True):
                if not corregido:
                    idx_correcta = q_actual.get("correcta")
                    seleccion_actual = resp_dict[idx_actual].get("elegida")
                    if seleccion_actual is None:
                        st.warning("Selecciona una alternativa antes de continuar.")
                    elif idx_correcta is None or idx_correcta >= len(q_actual["alternativas"]):
                        st.error("Asigna la respuesta correcta usando ⚙️.")
                    else:
                        es_correcta = (seleccion_actual == idx_correcta)
                        resp_dict[idx_actual]["estado"] = "correcta" if es_correcta else "incorrecta"
                        resp_dict[idx_actual]["corregido"] = True
                        st.rerun()
                else:
                    if idx_actual < total_preguntas - 1:
                        estudio["idx_actual"] += 1
                        st.rerun()
                    else:
                        puntaje_final = int((respondidas_ok / total_preguntas) * 100) if total_preguntas > 0 else 0

                        desglose_cat = {}
                        indices_falladas_orig = []
                        indices_ok_orig = []

                        for i_q, q_item in enumerate(preguntas):
                            cat = q_item.get("categoria", "General")
                            if cat not in desglose_cat:
                                desglose_cat[cat] = {"ok": 0, "total": 0}
                            desglose_cat[cat]["total"] += 1

                            orig_idx = q_item.get("idx_original", i_q)
                            st_q = resp_dict.get(i_q, {}).get("estado")
                            if st_q == "correcta":
                                desglose_cat[cat]["ok"] += 1
                                indices_ok_orig.append(orig_idx)
                            else:
                                indices_falladas_orig.append(orig_idx)

                        if b_id_actual:
                            registrar_preguntas_falladas(b_id_actual, indices_falladas_orig)
                            limpiar_falladas_resueltas(b_id_actual, indices_ok_orig)

                        guardar_resultado_historial(estudio["nombre_prueba"], puntaje_final, respondidas_ok, total_preguntas, desglose_cat)
                        st.success(f"🎉 Simulación finalizada con {puntaje_final}% de aciertos.")
                        if st.button("Volver al Menú Principal", key="btn_fin_menu", type="primary", use_container_width=True):
                            st.session_state.vista = "home"
                            st.session_state.modo_estudio_data = None
                            st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)


# --- VISTA: PANEL PRINCIPAL ---
else:
    st.title("📚 AeroStudio Pro - Centro de Pruebas")
    st.markdown(f"Bienvenido de nuevo, **{datos_usuario.get('nombre', 'Pablo Undurraga')}**. Sube tus documentos en PDF o imágenes escaneadas para iniciar tu entrenamiento.")
    st.write("")

    st.subheader("➕ Importar Nuevo Banco de Preguntas (PDF o Imágenes Escaneadas)")
    with st.container():
        uploaded_file = st.file_uploader("Sube tu documento en PDF o imagen escaneada", type=["pdf", "png", "jpg", "jpeg"])
        nombre_nueva_prueba = st.text_input("Título descriptivo de la prueba:", placeholder="Ej. Fisiología de Vuelo PTLA")

        usar_ia_pauta = st.checkbox("👁 Analizar documento con Google File API + Visión IA (Clasificación por materias y pauta)", value=True)

        st.write("")
        if st.button("Procesar y Generar Banco", type="primary"):
            if uploaded_file and nombre_nueva_prueba:
                tmp_path = None
                try:
                    ext = os.path.splitext(uploaded_file.name)[1]
                    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp_file:
                        tmp_file.write(uploaded_file.getvalue())
                        tmp_path = tmp_file.name

                    preguntas_extraidas = []

                    if usar_ia_pauta:
                        if not GENAI_DISPONIBLE:
                            st.error("⚠️ La librería `google-genai` no está instalada en el servidor.")
                        elif not st.session_state["gemini_api_key"]:
                            st.error("⚠️️ Para usar el análisis con IA debes configurar tu API Key de Gemini.")
                        else:
                            preguntas_extraidas = procesar_documento_multimodal(
                                tmp_path,
                                st.session_state["gemini_api_key"],
                                st.session_state["gemini_modelo"],
                                ext
                            )

                    if preguntas_extraidas:
                        id_limpio = re.sub(r'[^a-zA-Z0-9_\-]', '_', nombre_nueva_prueba)
                        guardar_banco(id_limpio, {
                            "nombre": nombre_nueva_prueba,
                            "preguntas": preguntas_extraidas
                        })
                        st.success(f"¡Éxito! Se estructuraron {len(preguntas_extraidas)} preguntas correctamente.")
                        st.rerun()
                    else:
                        st.error("No se pudieron extraer preguntas o el archivo requiere revisión.")
                finally:
                    if tmp_path and os.path.exists(tmp_path):
                        os.unlink(tmp_path)
            else:
                st.warning("Falta adjuntar el documento o ingresar el título de la prueba.")

    st.divider()
    st.subheader("Bancos Disponibles")
    bancos = listar_bancos()

    if not bancos:
        st.info("Aún no has cargado ningún banco de preguntas.")

    for b_id in bancos:
        banco_data = cargar_banco(b_id)
        if not banco_data: continue

        todas_preguntas = list
