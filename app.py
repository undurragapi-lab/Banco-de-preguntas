import os
import re
import json
import random
import tempfile
from datetime import datetime
import streamlit as st
import pandas as pd
import pdfplumber
from PIL import Image
from pdf2image import convert_from_path
from google import genai
from google.genai import types

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="AeroStudio Pro - Simulador de Vuelo",
    page_icon="✈️️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- GESTIÓN DE ESTADOS DE SESIÓN ---
if "modo_oscuro" not in st.session_state:
    st.session_state.modo_oscuro = True
if "vista" not in st.session_state:
    st.session_state.vista = "home"
if "modo_estudio_data" not in st.session_state:
    st.session_state.modo_estudio_data = None

# --- CSS MEJORADO (DISEÑO UX/UI ORIGINAL) ---
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
        --bg-main: #09090b;
        --bg-card: #18181b;
        --accent-blue: #0ea5e9;
        --accent-hover: #0284c7;
        --text-main: #f4f4f5;
        --text-muted: #a1a1aa;
        --border-color: #27272a;
        --sidebar-bg: #09090b;
    }
"""

css_activo = css_dark if st.session_state.modo_oscuro else css_light

st.markdown(f"""
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
        box-shadow: 0 4px 12px rgba(2, 132, 199, 0.2);
        transition: all 0.2s ease-in-out;
    }}
    div.stButton > button:hover {{
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(14, 165, 233, 0.3);
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

# --- ALMACENAMIENTO ---
DATA_DIR = "data_bancos"
HISTORY_FILE = "historial_resultados.json"
USERS_FILE = "usuarios.json"
SESSION_FILE = "sesion_activa.json"

os.makedirs(DATA_DIR, exist_ok=True)

# --- GESTIÓN DE API KEY DE GEMINI (Nube / Secretos) ---
api_key_configurada = ""
try:
    if "GEMINI_API_KEY" in st.secrets:
        api_key_configurada = st.secrets["GEMINI_API_KEY"]
except Exception:
    pass

if "gemini_api_key" not in st.session_state:
    st.session_state["gemini_api_key"] = api_key_configurada

def cargar_usuarios():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
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
        except:
            return None
    return None

def guardar_sesion_persistida(email):
    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump({"usuario": email}, f, ensure_ascii=False, indent=4)

def eliminar_sesion_persistida():
    if os.path.exists(SESSION_FILE):
        try:
            os.remove(SESSION_FILE)
        except:
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
    if os.path.exists(ruta):
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                banco_antiguo = json.load(f)
            mapa_manuales = {
                q_ant["pregunta"].strip(): q_ant["correcta"]
                for q_ant in banco_antiguo.get("preguntas", [])
                if q_ant.get("correcta") is not None
            }
            for q_nueva in data.get("preguntas", []):
                p_text = q_nueva["pregunta"].strip()
                if p_text in mapa_manuales and q_nueva.get("correcta") is None:
                    q_nueva["correcta"] = mapa_manuales[p_text]
        except:
            pass

    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def cargar_banco(nombre_id):
    ruta = os.path.join(DATA_DIR, f"{nombre_id}.json")
    if os.path.exists(ruta):
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return None
    return None

def listar_bancos():
    if not os.path.exists(DATA_DIR):
        return []
    return [f.replace(".json", "") for f in os.listdir(DATA_DIR) if f.endswith(".json")]

# --- HISTORIAL ---
def guardar_resultado_historial(nombre_prueba, puntaje_pct, correctas, total):
    historial = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                historial = json.load(f)
        except:
            historial = []
    
    historial.append({
        "usuario": st.session_state.usuario_actual,
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "timestamp": datetime.now().timestamp(),
        "prueba": nombre_prueba,
        "puntaje": puntaje_pct,
        "correctas": correctas,
        "total": total
    })
    
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(historial, f, ensure_ascii=False, indent=4)

def obtener_historial_reciente():
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            historial = json.load(f)
    except:
        return []
    
    limite_tiempo = datetime.now().timestamp() - (20 * 24 * 60 * 60)
    filtrado = [h for h in historial if h.get("timestamp", 0) >= limite_tiempo and h.get("usuario") == st.session_state.usuario_actual]
    return sorted(filtrado, key=lambda x: x["timestamp"], reverse=True)

# --- MOTOR DE VISIÓN CON GEMINI (ACTUALIZADO A GEMINI-3.8-FLASH) ---
def procesar_pdf_con_vision(pdf_path, api_key):
    """Convierte el PDF temporal en imágenes y usa Gemini Flash para extraer preguntas y respuestas con total precisión."""
    try:
        client = genai.Client(api_key=api_key)
        
        with st.spinner("🔄 Convirtiendo páginas del documento para análisis visual con IA..."):
            imagenes = convert_from_path(pdf_path)
        
        todas_las_preguntas_parsed = []
        progress_bar = st.progress(0)
        total_paginas = len(imagenes)
        
        for i, img in enumerate(imagenes):
            progress_bar.progress((i + 1) / total_paginas, text=f"Analizando página {i+1} de {total_paginas} con Visión IA...")
            
            prompt = """
            Analiza esta página de un examen o banco de preguntas aeronáutico. 
            Extrae todas las preguntas, sus alternativas (A, B, C, D) y determina la respuesta correcta 
            (identificada por marcas, negritas, pautas o solucionarios).
            
            Devuelve estrictamente un objeto JSON válido con la siguiente estructura exacta, sin texto adicional:
            {
              "preguntas": [
                {
                  "pregunta": "Texto completo de la pregunta",
                  "opciones": ["Texto alternativa A", "Texto alternativa B", "Texto alternativa C", "Texto alternativa D"],
                  "respuesta_correcta": "A" 
                }
              ]
            }
            Nota: En "respuesta_correcta" coloca únicamente la letra ("A", "B", "C" o "D") de la alternativa correcta. Si no hay preguntas en esta página, devuelve {"preguntas": []}.
            """
            
            # Se utiliza el modelo actualizado gemini-3.8-flash
            response = client.models.generate_content(
                model='gemini-3.8-flash',
                contents=[img, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1
                ),
            )
            
            if response.text:
                data = json.loads(response.text)
                if "preguntas" in data:
                    for q in data["preguntas"]:
                        enunciado = q.get("pregunta", "")
                        opciones_textos = q.get("opciones", [])
                        letra_corr = str(q.get("respuesta_correcta", "A")).strip().upper()
                        
                        alternativas_formateadas = []
                        correcta_idx = None
                        
                        for idx_a, texto_alt in enumerate(opciones_textos[:4]):
                            letra_let = ['A', 'B', 'C', 'D'][idx_a]
                            es_correcta = (letra_let == letra_corr or letra_corr in texto_alt.upper())
                            if es_correcta:
                                correcta_idx = idx_a
                            alternativas_formateadas.append({
                                "letra": letra_let,
                                "texto": texto_alt,
                                "marcada": es_correcta
                            })
                        
                        if enunciado and len(alternativas_formateadas) >= 2:
                            todas_las_preguntas_parsed.append({
                                "pregunta": enunciado,
                                "alternativas": alternativas_formateadas,
                                "correcta": correcta_idx
                            })
                            
        progress_bar.empty()
        return todas_las_preguntas_parsed

    except Exception as e:
        st.error(f"Error al procesar con Visión IA: {e}")
        return None

# --- CONTROL DE ACCESO ---
if st.session_state.usuario_actual is None:
    st.markdown("<h2 style='text-align: center; color: var(--accent-blue); padding-top: 5vh;'>✈️ AeroStudio Pro</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: var(--text-muted); margin-bottom: 2rem;'>Plataforma avanzada de estudio y entrenamiento aeronáutico.</p>", unsafe_allow_html=True)
    
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
    st.markdown(f"### 👨‍✈ {datos_usuario['nombre']}")
    st.caption("Piloto en Entrenamiento")
    st.divider()
    
    texto_modo = "☀️ Cambiar a Modo Claro" if st.session_state.modo_oscuro else "🌙 Cambiar a Modo Oscuro"
    if st.button(texto_modo, use_container_width=True, type="secondary"):
        st.session_state.modo_oscuro = not st.session_state.modo_oscuro
        st.rerun()

    if not st.session_state["gemini_api_key"]:
        st.divider()
        user_input_key = st.text_input("Google Gemini API Key", type="password", help="Ingresa tu clave de AI Studio")
        if user_input_key:
            st.session_state["gemini_api_key"] = user_input_key
            st.success("¡API Key guardada!")

    st.divider()
    if st.button("👤 Perfil de Usuario", use_container_width=True):
        st.session_state.vista = "perfil"
        st.rerun()
    if st.button("🏠 Panel Principal", use_container_width=True):
        st.session_state.vista = "home"
        st.session_state.prueba_activa = None
        st.rerun()
    if st.button("📊 Historial de Rendimiento", use_container_width=True):
        st.session_state.vista = "historial"
        st.rerun()
        
    st.divider()
    st.info("💡 **Tip:** Si algún banco PDF tiene problemas de lectura, usa la opción de Visión IA o el engranaje ⚙️ durante la prueba.")
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
            nuevo_nombre = st.text_input("Nombre de usuario:", value=datos_usuario["nombre"])
            nuevo_email = st.text_input("Correo electrónico:", value=datos_usuario["email"])
            nueva_pass = st.text_input("Nueva contraseña:", value=datos_usuario["password"], type="password")
            st.write("")
            if st.form_submit_button("Guardar Cambios", type="primary"):
                email_viejo = st.session_state.usuario_actual
                nuevo_email_limpio = nuevo_email.strip().lower()
                if nuevo_email_limpio != email_viejo:
                    if nuevo_email_limpio in usuarios_db:
                        st.error("El correo ya está registrado.")
                    else:
                        usuarios_db[nuevo_email_limpio] = {"nombre": nuevo_nombre, "email": nuevo_email_limpio, "password": nueva_pass}
                        del usuarios_db[email_viejo]
                        guardar_usuarios(usuarios_db)
                        st.session_state.usuario_actual = nuevo_email_limpio
                        guardar_sesion_persistida(nuevo_email_limpio)
                        st.success("¡Perfil actualizado!")
                        st.rerun()
                else:
                    usuarios_db[email_viejo]["nombre"] = nuevo_nombre
                    usuarios_db[email_viejo]["password"] = nueva_pass
                    guardar_usuarios(usuarios_db)
                    st.success("¡Perfil actualizado!")
                    st.rerun()
    if st.button("⬅️ Volver al Inicio"):
        st.session_state.vista = "home"
        st.rerun()

# --- VISTA: HISTORIAL ---
elif st.session_state.vista == "historial":
    st.title("📊 Historial de Rendimiento")
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
        for h in historial:
            with st.container():
                col1, col2, col3 = st.columns([3, 2, 2])
                col1.markdown(f"**Prueba:** {h['prueba']}")
                col2.markdown(f"📅 {h['fecha']}")
                col3.markdown(f"🎯 **Puntaje:** {h['puntaje']}% `({h['correctas']}/{h['total']})`")
                st.divider()
    if st.button("⬅️ Regresar al Inicio"):
        st.session_state.vista = "home"
        st.rerun()

# --- VISTA: ESTUDIO (EXAMEN) ---
elif st.session_state.vista == "estudio" and st.session_state.modo_estudio_data:
    estudio = st.session_state.modo_estudio_data
    preguntas = estudio["preguntas"]
    idx_actual = estudio["idx_actual"]
    b_id_actual = estudio.get("b_id")
    
    if not preguntas:
        st.error("Este banco de preguntas está vacío.")
        if st.button("Volver al Menú Principal"):
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
    
    col_top1, col_top_gear, col_top2 = st.columns([4, 0.5, 2.5])
    with col_top1:
        st.markdown(f"**Q: {idx_actual + 1}/{total_preguntas}** &nbsp;|&nbsp; ✅ {respondidas_ok} &nbsp;|&nbsp; ❌ {respondidas_fail} &nbsp;|&nbsp; 📈 **{puntaje_porcentaje}%**")
    
    with col_top_gear:
        with st.popover("⚙", help="Editor rápido de la respuesta actual"):
            st.markdown("#### 🛠️ Ajuste de Respuesta Correcta")
            q_actual_pop = preguntas[idx_actual]
            opciones_textos_pop = [f"{alt['letra']}.- {alt['texto']}" for alt in q_actual_pop["alternativas"]]
            current_correct = q_actual_pop.get("correcta", 0)
            if current_correct is None or current_correct >= len(opciones_textos_pop):
                current_correct = 0
            
            nueva_corr_sel = st.selectbox(
                "Selecciona la respuesta correcta:", 
                options=range(len(opciones_textos_pop)), 
                format_func=lambda x: opciones_textos_pop[x],
                index=current_correct,
                key=f"pop_corr_{idx_actual}"
            )
            
            if st.button("Guardar Corrección", key=f"btn_pop_save_{idx_actual}", use_container_width=True):
                q_actual_pop["correcta"] = nueva_corr_sel
                if b_id_actual:
                    banco_data = cargar_banco(b_id_actual)
                    if banco_data:
                        banco_data["preguntas"] = preguntas
                        guardar_banco(b_id_actual, banco_data)
                st.success("¡Respuesta actualizada y guardada!")
                st.rerun()

    with col_top2:
        with st.popover("🔢 Cuadrícula de Preguntas", help="Ver estado de todas las preguntas"):
            cols_grid = st.columns(5)
            for i in range(total_preguntas):
                estado_q = resp_dict.get(i, {}).get("estado")
                label_btn = f"🔵 {i+1}" if i == idx_actual else (f"🟢 {i+1}" if estado_q == "correcta" else (f"🔴 {i+1}" if estado_q == "incorrecta" else (f"⚪ {i+1}" if estado_q == "omitida" else f"⚫ {i+1}")))
                with cols_grid[i % 5]:
                    if st.button(label_btn, key=f"grid_{i}", use_container_width=True):
                        estudio["idx_actual"] = i
                        st.rerun()

    st.progress((idx_actual + 1) / total_preguntas)
    st.divider()

    q_actual = preguntas[idx_actual]
    st.markdown(f"### {idx_actual + 1}.- {q_actual['pregunta']}")
    
    if idx_actual not in resp_dict:
        resp_dict[idx_actual] = {"elegida": None, "estado": None, "corregido": False}
    
    estado_actual_q = resp_dict[idx_actual]
    corregido = estado_actual_q.get("corregido", False)
    
    opciones_tuplas = [(-1, "Seleccione una alternativa...")] + [(i, f"{alt['letra']}.- {alt['texto']}") for i, alt in enumerate(q_actual["alternativas"])]
    
    seleccion_indice_actual = estado_actual_q.get("elegida", None)
    current_index = 0
    if seleccion_indice_actual is not None:
        for idx, (orig_i, _) in enumerate(opciones_tuplas):
            if orig_i == seleccion_indice_actual:
                current_index = idx
                break

    seleccion_tuple = st.radio(
        "Alternativas disponibles:",
        options=opciones_tuplas,
        format_func=lambda x: x[1],
        index=current_index,
        disabled=corregido,
        key=f"radio_alt_{idx_actual}"
    )
    
    seleccion_radio = seleccion_tuple[0]
    if not corregido:
        resp_dict[idx_actual]["elegida"] = seleccion_radio if seleccion_radio != -1 else None

    if q_actual.get("correcta") is None:
        st.warning("⚠️ Esta pregunta no tiene respuesta correcta detectada. Haz clic en el engranaje superior ⚙️ para asignarla.")

    if corregido:
        idx_correcta = q_actual.get("correcta")
        if idx_correcta is not None and idx_correcta < len(q_actual["alternativas"]):
            letra_correcta = q_actual["alternativas"][idx_correcta]["letra"]
            if estado_actual_q["estado"] == "correcta":
                st.success("🎯 ¡Correcto!")
            else:
                st.error(f"❌ Incorrecto. La respuesta correcta es la alternativa **{letra_correcta}**.")

    st.write("")
    col_bot1, col_bot2, col_bot3 = st.columns([2, 4, 2])
    with col_bot1:
        if st.button("⬅️ Omitir", type="secondary", use_container_width=True):
            resp_dict[idx_actual]["estado"] = "omitida"
            resp_dict[idx_actual]["corregido"] = True
            if idx_actual < total_preguntas - 1:
                estudio["idx_actual"] += 1
                st.rerun()
            else:
                st.warning("Has llegado al final de la prueba.")

    with col_bot3:
        texto_boton = "Siguiente ➡️" if corregido else "Validar Respuesta"
        if st.button(texto_boton, type="primary", use_container_width=True):
            if not corregido:
                idx_correcta = q_actual.get("correcta")
                seleccion_actual = resp_dict[idx_actual].get("elegida")
                if seleccion_actual is None:
                    st.warning("Selecciona una alternativa antes de continuar.")
                elif idx_correcta is None or idx_correcta >= len(q_actual["alternativas"]):
                    st.error("Asigna primero la respuesta correcta usando el engranaje ⚙.")
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
                    guardar_resultado_historial(estudio["nombre_prueba"], puntaje_final, respondidas_ok, total_preguntas)
                    st.success(f"🎉 ¡Simulación finalizada! Puntaje obtenido: {puntaje_final}% ({respondidas_ok}/{total_preguntas}). Guardado en historial.")
                    if st.button("Volver al Menú Principal", use_container_width=True):
                        st.session_state.vista = "home"
                        st.session_state.prueba_activa = None
                        st.session_state.modo_estudio_data = None
                        st.rerun()

# --- VISTA: HOME (CON OPCIÓN DE VISIÓN IA) ---
else:
    st.title("📚 AeroStudio Pro - Centro de Pruebas")
    st.markdown(f"Bienvenido de nuevo, **{datos_usuario['nombre']}**. Sube tus documentos en PDF o selecciona un banco guardado para iniciar tu entrenamiento.")
    st.divider()

    st.subheader("➕ Importar Nuevo Banco de Preguntas (PDF)")
    with st.container():
        uploaded_file = st.file_uploader("Sube tu documento oficial en PDF", type=["pdf"])
        nombre_nueva_prueba = st.text_input("Título descriptivo de la prueba:", placeholder="Ej. Fisiología de Vuelo PTLA")
        
        usar_vision_ia = st.checkbox("🧠 Utilizar Visión por IA (Recomendado para PDFs escaneados o complejos)", value=True)
        
        st.write("")
        if st.button("Procesar y Generar Banco", type="primary"):
            if uploaded_file and nombre_nueva_prueba:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                    tmp_file.write(uploaded_file.getvalue())
                    tmp_path = tmp_file.name

                preguntas_extraidas = []
                
                if usar_vision_ia:
                    if not st.session_state["gemini_api_key"]:
                        st.error("⚠️ Para usar la Visión por IA debes configurar tu API Key.")
                    else:
                        preguntas_extraidas = procesar_pdf_con_vision(tmp_path, st.session_state["gemini_api_key"])
                
                if preguntas_extraidas:
                    id_limpio = re.sub(r'[^a-zA-Z0-9_\-]', '_', nombre_nueva_prueba)
                    guardar_banco(id_limpio, {
                        "nombre": nombre_nueva_prueba,
                        "preguntas": preguntas_extraidas
                    })
                    st.success(f"¡Éxito! Se extrajeron {len(preguntas_extraidas)} preguntas correctamente.")
                    st.rerun()
                else:
                    st.error("No se pudieron extraer preguntas o el archivo requiere revisión.")
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
        
        with st.container():
            col1, col2, col3 = st.columns([3, 1.5, 1])
            with col1:
                st.markdown(f"**{banco_data.get('nombre', b_id)}**")
                st.caption(f"{len(banco_data.get('preguntas', []))} preguntas")
            with col2:
                modo_aleatorio = st.checkbox("🔀 Orden Aleatorio", key=f"rnd_{b_id}")
            with col3:
                st.write("")
                if st.button("🚀 Iniciar", key=f"start_{b_id}", use_container_width=True):
                    preg = list(banco_data.get("preguntas", []))
                    if modo_aleatorio:
                        random.shuffle(preg)
                    if preg:
                        st.session_state.modo_estudio_data = {
                            "preguntas": preg, 
                            "idx_actual": 0,
                            "b_id": b_id,
                            "nombre_prueba": banco_data.get('nombre', b_id),
                            "respuestas_usuario": {}
                        }
                        st.session_state.vista = "estudio"
                        st.rerun()
        st.divider()
