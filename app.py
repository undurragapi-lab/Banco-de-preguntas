import os
import re
import json
import random
from datetime import datetime
import streamlit as st
import pandas as pd
import pdfplumber

# Configuración de la página
st.set_page_config(
    page_title="AeroStudio Pro - Simulador de Vuelo",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CAPA DE DISEÑO UI/UX DE ALTA GAMA (CUSTOM CSS) ---
st.markdown("""
<style>
    /* Variables de diseño y colores base */
    :root {
        --bg-main: #0f172a;
        --bg-card: #1e293b;
        --accent-blue: #38bdf8;
        --accent-hover: #0ea5e9;
        --text-main: #f8fafc;
        --text-muted: #94a3b8;
        --border-color: #334155;
    }

    /* Estilo general de la aplicación */
    .stApp {
        background-color: var(--bg-main);
        color: var(--text-main);
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* Ocultar elementos predeterminados molestos si se desea, manteniendo la limpieza */
    header {visibility: hidden;}
    
    /* Botones principales de alta gama */
    div.stButton > button {
        background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 0.6rem 1.2rem;
        font-weight: 600;
        letter-spacing: 0.3px;
        box-shadow: 0 4px 14px rgba(2, 132, 199, 0.3);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    div.stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(56, 189, 248, 0.4);
        background: linear-gradient(135deg, #0ea5e9 0%, #0284c7 100%);
    }

    /* Botones secundarios */
    div.stButton > button[kind="secondary"] {
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        color: var(--text-main);
        box-shadow: none;
    }
    div.stButton > button[kind="secondary"]:hover {
        border-color: var(--accent-blue);
        color: var(--accent-blue);
    }

    /* Campos de entrada refinados */
    .stTextInput input, .stSelectbox select, .stPasswordInput input {
        background-color: var(--bg-card) !important;
        color: var(--text-main) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 10px !important;
        padding: 0.5rem 0.75rem !important;
        transition: border-color 0.2s ease;
    }
    .stTextInput input:focus, .stSelectbox select:focus {
        border-color: var(--accent-blue) !important;
        box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.2);
    }

    /* Sidebar de alta gama */
    section[data-testid="stSidebar"] {
        background-color: #0b0f19;
        border-right: 1px solid var(--border-color);
    }

    /* Tarjetas y métricas */
    div[data-testid="metric-container"] {
        background-color: var(--bg-card);
        border: 1px solid var(--border-color);
        padding: 1rem;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }

    /* Barras de progreso elegantes */
    div[data-testid="stProgress"] > div > div {
        background: linear-gradient(90deg, #0ea5e9 0%, #38bdf8 100%);
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)

# Directorios y archivos de almacenamiento local
DATA_DIR = "data_bancos"
HISTORY_FILE = "historial_resultados.json"
USERS_FILE = "usuarios.json"
SESSION_FILE = "sesion_activa.json"

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# --- GESTIÓN DE USUARIOS Y AUTENTICACIÓN ---
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
                data = json.load(f)
                return data.get("usuario")
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

if "vista" not in st.session_state:
    st.session_state.vista = "home"
if "modo_estudio_data" not in st.session_state:
    st.session_state.modo_estudio_data = None

# --- FUNCIONES DE BANCOS DE PREGUNTAS ---
def guardar_banco(nombre_id, data):
    ruta = os.path.join(DATA_DIR, f"{nombre_id}.json")
    if os.path.exists(ruta):
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                banco_antiguo = json.load(f)
            
            mapa_manuales = {}
            for q_ant in banco_antiguo.get("preguntas", []):
                if q_ant.get("correcta") is not None:
                    mapa_manuales[q_ant["pregunta"].strip()] = q_ant["correcta"]
            
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
        with open(ruta, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def listar_bancos():
    if not os.path.exists(DATA_DIR):
        return []
    return [f.replace(".json", "") for f in os.listdir(DATA_DIR) if f.endswith(".json")]

def eliminar_banco(nombre_id):
    ruta = os.path.join(DATA_DIR, f"{nombre_id}.json")
    if os.path.exists(ruta):
        os.remove(ruta)

# --- HISTORIAL DE RESULTADOS ---
def guardar_resultado_historial(nombre_prueba, puntaje_pct, correctas, total):
    historial = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                historial = json.load(f)
        except:
            historial = []
    
    nuevo_registro = {
        "usuario": st.session_state.usuario_actual,
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "timestamp": datetime.now().timestamp(),
        "prueba": nombre_prueba,
        "puntaje": puntaje_pct,
        "correctas": correctas,
        "total": total
    }
    historial.append(nuevo_registro)
    
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
    # Corrección del error de sintaxis en el corchete de cierre de "usuario"
    filtrado = [h for h in historial if h.get("timestamp", 0) >= limite_tiempo and h.get("usuario") == st.session_state.usuario_actual]
    return sorted(filtrado, key=lambda x: x["timestamp"], reverse=True)

# --- PARSER ULTRA-EFICIENTE (MULTIPÁGINA Y VECTORIAL) ---
def extraer_preguntas_de_pdf(pdf_file):
    texto_completo = ""
    hojas_texto_estilo = []
    hojas_formas = []
    
    with pdfplumber.open(pdf_file) as pdf:
        for idx, pagina in enumerate(pdf.pages):
            t = pagina.extract_text(layout=False) or ""
            texto_completo += t + f"\n--- PAGINA {idx+1} ---\n"
            
            try:
                palabras = pagina.extract_words(extra_attrs=["fontname", "size", "x0", "top"])
                hojas_texto_estilo.append(palabras)
            except:
                hojas_texto_estilo.append([])
                
            try:
                formas = pagina.extract_rects() + pagina.extract_lines()
                hojas_formas.append(formas)
            except:
                hojas_formas.append([])

    mapa_claves_finales = {}
    lineas_doc = texto_completo.split('\n')
    en_seccion_claves = False
    
    for linea in lineas_doc:
        linea_lower = linea.lower()
        if any(kw in linea_lower for kw in ["clave", "respuestas correctas", "pauta de correccion", "answer key", "solucionario"]):
            en_seccion_claves = True
        
        if en_seccion_claves:
            matches_claves = re.findall(r'\b([0-9]{1,3})[\.\-\)\:]\s*([A-Da-d])\b', linea)
            for num_str, letra in matches_claves:
                mapa_claves_finales[int(num_str)] = letra.upper()

    bloques = re.split(r'\n(?=[0-9]{1,3}\.-\s)', texto_completo)
    if len(bloques) <= 1:
        bloques = re.split(r'(?=[0-9]{1,3}\.-\s)', texto_completo)

    preguntas_parsed = []
    patron_alt_inicio = re.compile(r'^[☑☒X✔✓xVv\[\]\(\)\*\-\s]*([A-Da-d])[\.\-\)]\s*', re.IGNORECASE)
    
    current_page = 0
    
    for bloque in bloques:
        bloque = bloque.strip()
        if len(bloque) < 10:
            continue
            
        match_pagina_tag = re.search(r'--- PAGINA ([0-9]+) ---', bloque)
        if match_pagina_tag:
            current_page = int(match_pagina_tag.group(1)) - 1
            bloque = re.sub(r'--- PAGINA [0-9]+ ---', '', bloque).strip()
            
        match_num = re.match(r'^([0-9]{1,3})\.-\s*(.*)', bloque, re.DOTALL)
        if not match_num:
            continue
            
        num_pregunta = int(match_num.group(1))
        cuerpo_bloque = match_num.group(2)
        lineas = [l.strip() for l in cuerpo_bloque.split('\n') if l.strip()]
        
        enunciado_lineas = []
        alternativas_crudas = []
        en_alternativas = False
        
        for linea in lineas:
            if patron_alt_inicio.match(linea) or re.match(r'^[☑☒X✔✓]', linea):
                en_alternativas = True
            
            if not en_alternativas:
                enunciado_lineas.append(linea)
            else:
                alternativas_crudas.append(linea)

        enunciado = " ".join(enunciado_lineas).strip()

        mapa_alts = {}
        alt_actual_letra = None
        alt_actual_texto = []
        alt_actual_marcada = False
        
        for linea in alternativas_crudas:
            match_alt = patron_alt_inicio.match(linea)
            
            if match_alt or re.match(r'^[☑☒X✔✓]\s*[\-\.]?\s*([A-Da-d])?[\.\-\)]?\s*(.*)', linea):
                if alt_actual_letra:
                    mapa_alts[alt_actual_letra] = {
                        "texto": " ".join(alt_actual_texto).strip(),
                        "marcada": alt_actual_marcada
                    }
                
                if match_alt:
                    letra_capturada = match_alt.group(1).upper()
                    alt_actual_letra = letra_capturada if letra_capturada in ['A', 'B', 'C', 'D'] else None
                else:
                    alt_actual_letra = None
                
                es_marcada = any(s in linea for s in ['☑', '☒', 'X', '✔', '✓', 'x', '[x]', '(X)', '[X]', 'V', '*', '★']) or ('correcta' in linea.lower())
                
                if not es_marcada and hojas_texto_estilo and current_page < len(hojas_texto_estilo):
                    for w in hojas_texto_estilo[current_page]:
                        if w["text"] in linea and any(b_kw in w.get("fontname", "").lower() for b_kw in ["bold", "negrita", "black", "bd"]):
                            es_marcada = True
                            break

                if not es_marcada and hojas_formas and current_page < len(hojas_formas):
                    if current_page < len(hojas_texto_estilo):
                        for w in hojas_texto_estilo[current_page]:
                            if w["text"] in linea:
                                wx, wy = w.get("x0", 0), w.get("top", 0)
                                for forma in hojas_formas[current_page]:
                                    fx = forma.get("x0", forma.get("x", 0))
                                    fy = forma.get("top", forma.get("y", 0))
                                    if abs(fx - wx) < 30 and abs(fy - wy) < 15:
                                        es_marcada = True
                                        break

                if not alt_actual_letra:
                    existentes = list(mapa_alts.keys())
                    for sig in ['A', 'B', 'C', 'D']:
                        if sig not in existentes:
                            alt_actual_letra = sig
                            break
                    if not alt_actual_letra:
                        alt_actual_letra = 'A'

                texto_limpio = patron_alt_inicio.sub('', linea)
                for s in ['☑', '☒', 'X', '✔', '✓', 'x', '[x]', '(X)', '[X]', 'V', '•', '(*)', '❌', '×', '*', '★']:
                    texto_limpio = texto_limpio.replace(s, "")
                texto_limpio = re.sub(r'^[\-\.\s]+', '', texto_limpio).strip()
                
                alt_actual_texto = [texto_limpio] if texto_limpio else []
                alt_actual_marcada = es_marcada
            else:
                if alt_actual_letra:
                    texto_cont = linea
                    for s in ['☑', '☒', 'X', '✔', '✓', 'x', '[x]', '(X)', '[X]', 'V', '•', '(*)', '❌', '×']:
                        texto_cont = texto_cont.replace(s, "")
                    texto_cont = re.sub(r'^[\-\.\s]+', '', texto_cont).strip()
                    if texto_cont:
                        alt_actual_texto.append(texto_cont)
                    if any(s in linea for s in ['☑', '☒', 'X', '✔', '✓', 'x', '[x]', '(X)', '[X]']) or ('correcta' in linea.lower()):
                        alt_actual_marcada = True

        if alt_actual_letra:
            mapa_alts[alt_actual_letra] = {
                "texto": " ".join(alt_actual_texto).strip(),
                "marcada": alt_actual_marcada
            }

        alternativas = []
        correcta_idx = None
        letras_ordenadas = ['A', 'B', 'C', 'D']
        
        for idx_a, l in enumerate(letras_ordenadas):
            if l in mapa_alts and mapa_alts[l]["texto"]:
                info = mapa_alts[l]
                if info["marcada"]:
                    correcta_idx = idx_a
                alternativas.append({
                    "letra": l,
                    "texto": info["texto"],
                    "marcada": info["marcada"]
                })

        if correcta_idx is None and num_pregunta in mapa_claves_finales:
            letra_clave = mapa_claves_finales[num_pregunta]
            for idx_a, alt in enumerate(alternativas):
                if alt["letra"] == letra_clave:
                    correcta_idx = idx_a
                    alt["marcada"] = True
                    break

        if enunciado and len(alternativas) >= 2:
            preguntas_parsed.append({
                "pregunta": enunciado,
                "alternativas": alternativas,
                "correcta": correcta_idx
            })

    return preguntas_parsed

# --- CONTROL DE ACCESO ---
if st.session_state.usuario_actual is None:
    st.markdown("<h2 style='text-align: center; color: #38bdf8;'>✈️ AeroStudio Pro - Acceso al Sistema</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #94a3b8; margin-bottom: 2rem;'>Plataforma avanzada de estudio y entrenamiento aeronáutico.</p>", unsafe_allow_html=True)
    
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
                    st.success("¡Acceso exitoso!")
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
                    usuarios_db[reg_email] = {
                        "nombre": reg_nombre,
                        "email": reg_email,
                        "password": reg_pass
                    }
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
    st.markdown(f"### 👨‍✈️ {datos_usuario['nombre']}")
    st.caption("Piloto en Entrenamiento")
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
    st.info("💡 **Consejo:** Utiliza el botón de engranaje (⚙️) durante tus exámenes para ajustar respuestas en tiempo real.")
    st.write("")
    if st.button("🚪 Cerrar Sesión", kind="secondary", use_container_width=True):
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
                        st.session_state.usuario_actual = nuevo_email_limpio
                        guardar_sesion_persistida(nuevo_email_limpio)
                        guardar_usuarios(usuarios_db)
                        st.success("¡Perfil actualizado con éxito!")
                        st.rerun()
                else:
                    usuarios_db[email_viejo]["nombre"] = nuevo_nombre
                    usuarios_db[email_viejo]["password"] = nueva_pass
                    guardar_usuarios(usuarios_db)
                    st.success("¡Perfil actualizado con éxito!")
                    st.rerun()
                    
    if st.button("⬅️ Volver al Inicio"):
        st.session_state.vista = "home"
        st.rerun()

# --- VISTA: HISTORIAL ---
elif st.session_state.vista == "historial":
    st.title("📊 Historial de Rendimiento (Últimos 20 días)")
    historial = obtener_historial_reciente()
    if not historial:
        st.info("No hay registros recientes en tu historial de vuelo/estudio.")
    else:
        df_hist = pd.DataFrame(historial)
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            st.metric(label="Promedio General de Aciertos", value=f"{df_hist['puntaje'].mean():.1f}%")
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

# --- VISTA: ESTUDIO ---
elif st.session_state.vista == "estudio" and st.session_state.modo_estudio_data:
    estudio = st.session_state.modo_estudio_data
    preguntas = estudio["preguntas"]
    idx_actual = estudio["idx_actual"]
    b_id_actual = estudio.get("b_id")
    
    if "respuestas_usuario" not in estudio:
        estudio["respuestas_usuario"] = {}
    resp_dict = estudio["respuestas_usuario"]

    total_preguntas = len(preguntas)
    respondidas_ok = sum(1 for k, v in resp_dict.items() if v.get("estado") == "correcta")
    respondidas_fail = sum(1 for k, v in resp_dict.items() if v.get("estado") in ["incorrecta", "omitida"])
    puntaje_porcentaje = int((respondidas_ok / total_preguntas) * 100) if total_preguntas > 0 else 0
    
    # Barra superior de navegación de estudio con botón de engranaje (⚙️) integrado
    col_top1, col_top_gear, col_top2 = st.columns([4, 0.6, 2.4])
    with col_top1:
        st.markdown(f"**Q: {idx_actual + 1}/{total_preguntas}** &nbsp;|&nbsp; ✅ {respondidas_ok} &nbsp;|&nbsp; ❌ {respondidas_fail} &nbsp;|&nbsp; 📈 **{puntaje_porcentaje}%**")
    
    with col_top_gear:
        with st.popover("⚙️️", help="Editor rápido de la pregunta actual"):
            st.markdown("#### 🛠️ Ajuste de Pregunta")
            q_actual_pop = preguntas[idx_actual]
            opciones_textos_pop = [f"{alt['letra']}.- {alt['texto']}" for alt in q_actual_pop["alternativas"]]
            current_correct = q_actual_pop.get("correcta", 0)
            if current_correct is None:
                current_correct = 0
            
            nueva_corr_sel = st.selectbox(
                "Respuesta Correcta:", 
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
                st.success("¡Actualizado con éxito!")
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
        if seleccion_radio != -1:
            resp_dict[idx_actual]["elegida"] = seleccion_radio
        else:
            resp_dict[idx_actual]["elegida"] = None

    if q_actual.get("correcta") is None:
        st.warning("⚠️️ Esta pregunta no tiene respuesta correcta automática. Haz clic en el engranaje superior ⚙️ para asignarla.")

    if corregido:
        idx_correcta = q_actual.get("correcta")
        if idx_correcta is not None:
            letra_correcta = q_actual["alternativas"][idx_correcta]["letra"]
            if estado_actual_q["estado"] == "correcta":
                st.success("🎯 ¡Correcto! Has acertado la respuesta.")
            else:
                st.error(f"❌ Incorrecto. La respuesta correcta es la alternativa **{letra_correcta}**.")
        else:
            st.warning("Esta pregunta aún no tiene respuesta asignada.")

    st.write("")
    col_bot1, col_bot2, col_bot3 = st.columns([2, 4, 2])

    with col_bot1:
        if st.button("⬅️ Omitir", kind="secondary", use_container_width=True):
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
                elif idx_correcta is None:
                    st.error("Asigna primero la respuesta correcta usando el engranaje ⚙️.")
                else:
                    es_correcta = (seleccion_actual == idx_correcta)
                    estado_str = "correcta" if es_correcta else "incorrecta"
                    resp_dict[idx_actual]["estado"] = estado_str
                    resp_dict[idx_actual]["corregido"] = True
                    st.rerun()
            else:
                if idx_actual < total_preguntas - 1:
                    estudio["idx_actual"] += 1
                    st.rerun()
                else:
                    puntaje_final = int((respondidas_ok / total_preguntas) * 100) if total_preguntas > 0 else 0
                    guardar_resultado_historial(estudio["nombre_prueba"], puntaje_final, respondidas_ok, total_preguntas)
                    st.success(f"🎉 ¡Simulación finalizada! Puntaje obtenido: {puntaje_final}% ({respondidas_ok}/{total_preguntas}). Guardado en tu historial.")
                    if st.button("Volver al Menú Principal", use_container_width=True):
                        st.session_state.vista = "home"
                        st.session_state.prueba_activa = None
                        st.session_state.modo_estudio_data = None
                        st.rerun()

# --- VISTA: HOME ---
else:
    st.title("📚 Centro de Pruebas y Bancos de Preguntas")
    st.markdown(f"Bienvenido de nuevo, **{datos_usuario['nombre']}**. Carga tus documentos normativos en PDF o selecciona un banco guardado para iniciar tu entrenamiento.")
    st.divider()

    st.subheader("➕ Importar Nuevo Banco de Preguntas (PDF)")
    with st.container():
        uploaded_file = st.file_uploader("Sube tu documento oficial en PDF", type=["pdf"])
        nombre_nueva_prueba = st.text_input("Título descriptivo de la prueba:", placeholder="Ej. Aerodinámica Avanzada PTLA")
        
        st.write("")
        if st.button("Procesar y Generar Banco", type="primary"):
            if uploaded_file and nombre_nueva_prueba:
                with st.spinner("Analizando estructuras vectoriales, estilos tipográficos y claves del PDF..."):
                    preguntas_extraidas = extraer_preguntas_de_pdf(uploaded_file)
                    if preguntas_extraidas:
                        id_limpio = re.sub(r'[^a-zA-Z0-9_\-]', '_', nombre_nueva_prueba)
                        guardar_banco(id_limpio, {
                            "nombre": nombre_nueva_prueba,
                            "preguntas": preguntas_extraidas
                        })
                        st.success(f"¡Banco '{nombre_nueva_prueba}' generado con éxito ({len(preguntas_extraidas)} preguntas detectadas)!")
                        st.rerun()
                    else:
                        st.error("No se pudieron extraer preguntas válidas del PDF.")
            else:
                st.warning("Por favor, adjunta un archivo PDF y asigna un nombre.")

    st.divider()
    st.subheader("📂 Tus Bancos Guardados")
    bancos = listar_bancos()

    if not bancos:
        st.info("No hay bancos de preguntas almacenados actualmente.")
    else:
        for b_id in bancos:
            datos_banco = cargar_banco(b_id)
            if not datos_banco:
                continue
            
            with st.container():
                col_h1, col_h2, col_h3, col_h4 = st.columns([3, 2, 2, 2])
                with col_h1:
                    nuevo_nombre = st.text_input(f"Editar {b_id}", value=datos_banco.get("nombre", b_id), key=f"edit_{b_id}", label_visibility="collapsed")
                    if nuevo_nombre != datos_banco.get("nombre", b_id):
                        datos_banco["nombre"] = nuevo_nombre
                        guardar_banco(b_id, datos_banco)
                with col_h2:
                    st.markdown(f"📋 **{len(datos_banco.get('preguntas', []))}** preguntas")
                with col_h3:
                    modo_aleatorio = st.checkbox("Modo Aleatorio", value=True, key=f"rnd_{b_id}")
                with col_h4:
                    subcol1, subcol2 = st.columns(2)
                    with subcol1:
                        if st.button("🚀 Iniciar", key=f"btn_start_{b_id}", use_container_width=True):
                            lista_q = datos_banco["preguntas"].copy()
                            if modo_aleatorio:
                                random.shuffle(lista_q)
                            st.session_state.modo_estudio_data = {
                                "b_id": b_id,
                                "nombre_prueba": datos_banco.get("nombre", b_id),
                                "preguntas": lista_q,
                                "idx_actual": 0,
                                "respuestas_usuario": {}
                            }
                            st.session_state.vista = "estudio"
                            st.rerun()
                    with subcol2:
                        if st.button("🗑️", key=f"btn_del_{b_id}", kind="secondary", use_container_width=True, help="Eliminar banco"):
                            eliminar_banco(b_id)
                            st.rerun()
                st.divider()
