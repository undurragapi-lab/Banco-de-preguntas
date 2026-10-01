import os
import re
import json
import random
from datetime import datetime, timedelta
import streamlit as st
import pandas as pd
from pypdf import PdfReader

# Configuración de la página
st.set_page_config(
    page_title="App de Estudio - Piloto",
    page_icon="✈️",
    layout="wide"
)

# Directorios y archivos de almacenamiento local
DATA_DIR = "data_bancos"
HISTORY_FILE = "historial_resultados.json"
USERS_FILE = "usuarios.json"

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

if "usuario_actual" not in st.session_state:
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
    filtrado = [h for h in historial if h.get("timestamp", 0) >= limite_tiempo and h.get("usuario") == st.session_state.usuario_actual]
    return sorted(filtrado, key=lambda x: x["timestamp"], reverse=True)

# --- PARSER DE PDF ---
def extraer_preguntas_de_pdf(pdf_file):
    reader = PdfReader(pdf_file)
    texto_completo = ""
    for pagina in reader.pages:
        t = pagina.extract_text()
        if t:
            texto_completo += t + "\n"
        if "/Annots" in pagina:
            try:
                for annot in pagina["/Annots"]:
                    obj = annot.get_object()
                    if "/Contents" in obj:
                        texto_completo += str(obj["/Contents"]) + "\n"
            except:
                pass

    texto_completo = re.sub(r'\r\n', '\n', texto_completo)
    bloques = re.split(r'\n(?=[0-9]{1,3}\.-\s)', texto_completo)
    if len(bloques) <= 1:
        bloques = re.split(r'(?=[0-9]{1,3}\.-\s)', texto_completo)

    preguntas_parsed = []
    
    for bloque in bloques:
        bloque = bloque.strip()
        if len(bloque) < 15:
            continue
            
        match_num = re.match(r'^([0-9]{1,3})\.-\s*(.*)', bloque, re.DOTALL)
        if not match_num:
            continue
            
        cuerpo_bloque = match_num.group(2)
        lineas = [l.strip() for l in cuerpo_bloque.split('\n') if l.strip()]
        
        enunciado_lineas = []
        lineas_alts = []
        en_alternativas = False
        
        for linea in lineas:
            if re.match(r'^([☑☒X✔✓xVv]\s*[A-Da-d])[\.\-\)]', linea) or re.match(r'^[☑☒X✔✓xVv]\s*[\-\.]?', linea) or en_alternativas:
                en_alternativas = True
                lineas_alts.append(linea)
            else:
                if not en_alternativas:
                    enunciado_lineas.append(linea)
                else:
                    lineas_alts.append(linea)

        enunciado = " ".join(enunciado_lineas).strip()
        enunciado = re.sub(r'Materia\s*:.*?Cantidad de Preguntas\s*:\s*[0-9]+', '', enunciado).strip()

        alternativas = []
        correcta_idx = None
        texto_completo_alts = "\n".join(lineas_alts)
        fragmentos = re.split(r'(?=[☑☒X✔✓xVv]?\s*[A-Da-d][\.\-\)])', texto_completo_alts)
        
        mapa_alts = {}
        for frag in fragmentos:
            frag = frag.strip()
            if not frag:
                continue
                
            match_alt = re.match(r'^([☑☒X✔✓xVv]?)\s*([A-Da-d])[\.\-\)]\s*(.*)', frag, re.DOTALL)
            if match_alt:
                marca_simbolo = match_alt.group(1)
                letra = match_alt.group(2).upper()
                texto = match_alt.group(3).strip()
                
                es_marcada = bool(marca_simbolo) or any(s in frag[:12] for s in ['☑', '☒', 'X', '✔', '✓', 'x', '[x]', '(X)', '[X]', 'V'])
                for s in ['☑', '☒', 'X', '✔', '✓', 'x', '[x]', '(X)', '[X]', 'V', '•', '(*)', '❌', '×']:
                    texto = texto.replace(s, "")
                texto = " ".join(texto.split()).strip()
                
                mapa_alts[letra] = {"texto": texto, "marcada": es_marcada}
            else:
                if mapa_alts:
                    ultima_letra = list(mapa_alts.keys())[-1]
                    es_marcada_flotante = any(s in frag for s in ['☑', '☒', 'X', '✔', '✓', 'x', '[x]', '(X)', '[X]'])
                    for s in ['☑', '☒', 'X', '✔', '✓', 'x', '[x]', '(X)', '[X]', 'V', '•', '(*)', '❌', '×']:
                        frag = frag.replace(s, "")
                    frag = " ".join(frag.split()).strip()
                    if frag:
                        mapa_alts[ultima_letra]["texto"] += " " + frag
                    if es_marcada_flotante:
                        mapa_alts[ultima_letra]["marcada"] = True

        letras_ordenadas = ['A', 'B', 'C', 'D']
        for idx_a, l in enumerate(letras_ordenadas):
            if l in mapa_alts:
                info = mapa_alts[l]
                if info["marcada"]:
                    correcta_idx = idx_a
                alternativas.append({
                    "letra": l,
                    "texto": info["texto"],
                    "marcada": info["marcada"]
                })

        if correcta_idx is None and alternativas:
            correcta_idx = None # Deja en blanco si no viene marcado en el documento

        if enunciado and len(alternativas) >= 2:
            preguntas_parsed.append({
                "pregunta": enunciado,
                "alternativas": alternativas,
                "correcta": correcta_idx
            })

    return preguntas_parsed

# --- CONTROL DE ACCESO ---
if st.session_state.usuario_actual is None:
    st.title("🔐 Acceso a la Aplicación de Estudio")
    st.markdown("Por favor, inicia sesión o regístrate con tu correo y contraseña para continuar.")
    
    tab_login, tab_registro = st.tabs(["Iniciar Sesión", "Registrarse"])
    usuarios_db = cargar_usuarios()
    
    with tab_login:
        email_ingreso = st.text_input("Correo electrónico:", key="login_email")
        pass_ingreso = st.text_input("Contraseña:", type="password", key="login_pass")
        
        if st.button("Entrar", type="primary"):
            email_ingreso = email_ingreso.strip().lower()
            if email_ingreso in usuarios_db and usuarios_db[email_ingreso]["password"] == pass_ingreso:
                st.session_state.usuario_actual = email_ingreso
                st.success("¡Acceso exitoso!")
                st.rerun()
            else:
                st.error("Correo o contraseña incorrectos.")
                
    with tab_registro:
        reg_nombre = st.text_input("Nombre de usuario:", key="reg_name")
        reg_email = st.text_input("Correo electrónico:", key="reg_email")
        reg_pass = st.text_input("Contraseña:", type="password", key="reg_pass")
        
        if st.button("Crear Cuenta"):
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
                st.success("¡Cuenta creada con éxito!")
                st.rerun()
    st.stop()

usuarios_db = cargar_usuarios()
datos_usuario = usuarios_db.get(st.session_state.usuario_actual, {"nombre": "Administrador", "email": st.session_state.usuario_actual, "password": ""})

# --- BARRA LATERAL ---
with st.sidebar:
    st.markdown("### 🛠️ Menú de Herramientas")
    if st.button(f"👤 Perfil: {datos_usuario['nombre']}", use_container_width=True):
        st.session_state.vista = "perfil"
        st.rerun()
        
    st.divider()
    if st.button("🏠 Volver al Inicio / Pruebas", use_container_width=True):
        st.session_state.vista = "home"
        st.session_state.prueba_activa = None
        st.rerun()
        
    if st.button("📊 Historial de Pruebas (Últimos 20 días)", use_container_width=True):
        st.session_state.vista = "historial"
        st.rerun()
        
    st.divider()
    st.markdown("### ✈️ Panel de Control")
    st.info("Respuestas obtenidas exclusivamente del documento cargado o asignación de administrador.")

    st.write("")
    st.write("")
    if st.button("🚪 Cerrar Sesión", type="secondary", use_container_width=True):
        st.session_state.usuario_actual = None
        st.session_state.vista = "home"
        st.session_state.modo_estudio_data = None
        st.rerun()

# --- VISTA: PERFIL ---
if st.session_state.vista == "perfil":
    st.title("👤 Configuración de Perfil y Cuenta")
    with st.form("form_perfil"):
        nuevo_nombre = st.text_input("Nombre de usuario:", value=datos_usuario["nombre"])
        nuevo_email = st.text_input("Correo electrónico:", value=datos_usuario["email"])
        nueva_pass = st.text_input("Contraseña:", value=datos_usuario["password"], type="password")
        
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
                    guardar_usuarios(usuarios_db)
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
    st.title("📊 Historial de Rendimiento (Últimos 20 días)")
    historial = obtener_historial_reciente()
    if not historial:
        st.warning("No hay registros recientes.")
    else:
        df_hist = pd.DataFrame(historial)
        st.metric(label="Promedio General", value=f"{df_hist['puntaje'].mean():.1f}%")
        st.divider()
        for h in historial:
            col1, col2, col3 = st.columns([3, 2, 2])
            col1.markdown(f"**Prueba:** {h['prueba']}")
            col2.markdown(f"Fecha: {h['fecha']}")
            col3.markdown(f"**Puntaje:** {h['puntaje']}% ({h['correctas']}/{h['total']})")
            st.divider()
    if st.button("⬅️ Regresar al Inicio"):
        st.session_state.vista = "home"
        st.rerun()

# --- VISTA: ESTUDIO (CON MANEJO SEGURO DE SELECCIÓN EN st.radio) ---
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
    
    col_top1, col_top2 = st.columns([5, 2])
    with col_top1:
        st.markdown(f"### 📋 Q: {idx_actual + 1}/{total_preguntas} &nbsp;|&nbsp; ✅ {respondidas_ok} &nbsp;|&nbsp; ❌ {respondidas_fail} &nbsp;|&nbsp; 📈 **{puntaje_porcentaje}%**")
    
    with col_top2:
        with st.popover("🔢 Cuadrícula de Preguntas"):
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
    st.markdown(f"#### {idx_actual + 1}.- {q_actual['pregunta']}")
    
    if idx_actual not in resp_dict:
        resp_dict[idx_actual] = {"elegida": None, "estado": None, "corregido": False}
    
    estado_actual_q = resp_dict[idx_actual]
    corregido = estado_actual_q.get("corregido", False)
    
    # Construcción de opciones incluyendo marcador de posición para evitar selección por defecto
    opciones_tuplas = [(-1, "Seleccione una alternativa...")] + [(i, f"{alt['letra']}.- {alt['texto']}") for i, alt in enumerate(q_actual["alternativas"])]
    
    seleccion_indice_actual = estado_actual_q.get("elegida", None)
    current_index = 0
    if seleccion_indice_actual is not None:
        for idx, (orig_i, _) in enumerate(opciones_tuplas):
            if orig_i == seleccion_indice_actual:
                current_index = idx
                break

    seleccion_tuple = st.radio(
        "Seleccione su alternativa:",
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

    # Selector manual de administrador si el PDF no traía la respuesta marcada
    if q_actual.get("correcta") is None:
        st.warning("⚠️ Esta pregunta NO tiene respuesta correcta detectada automáticamente. Como administrador, asígnala aquí para guardarla permanentemente:")
        col_m1, col_m2 = st.columns([3, 1])
        with col_m1:
            opciones_textos_manual = [f"{alt['letra']}.- {alt['texto']}" for alt in q_actual["alternativas"]]
            alt_correcta_manual = st.selectbox("Selecciona la alternativa correcta:", options=range(len(opciones_textos_manual)), format_func=lambda x: opciones_textos_manual[x], key=f"man_corr_{idx_actual}")
        with col_m2:
            if st.button("Guardar Respuesta Correcta", key=f"btn_save_corr_{idx_actual}"):
                q_actual["correcta"] = alt_correcta_manual
                if b_id_actual:
                    banco_data = cargar_banco(b_id_actual)
                    if banco_data:
                        banco_data["preguntas"] = preguntas
                        guardar_banco(b_id_actual, banco_data)
                st.success("¡Respuesta guardada y persistida!")
                st.rerun()

    if corregido:
        idx_correcta = q_actual.get("correcta")
        if idx_correcta is not None:
            letra_correcta = q_actual["alternativas"][idx_correcta]["letra"]
            if estado_actual_q["estado"] == "correcta":
                st.success("¡Correcto! Respuesta acertada.")
            else:
                st.error(f"Incorrecto. La respuesta correcta es la alternativa **{letra_correcta}**.")
        else:
            st.warning("Esta pregunta aún no tiene respuesta correcta asignada.")

    st.write("")
    col_bot1, col_bot2, col_bot3 = st.columns([2, 4, 2])

    with col_bot1:
        if st.button("⬅️ Omitir", use_container_width=True):
            resp_dict[idx_actual]["estado"] = "omitida"
            resp_dict[idx_actual]["corregido"] = True
            if idx_actual < total_preguntas - 1:
                estudio["idx_actual"] += 1
                st.rerun()
            else:
                st.warning("Has llegado al final de la prueba.")

    with col_bot3:
        texto_boton = "Siguiente ➡️" if corregido else "Contestar / Corregir"
        if st.button(texto_boton, type="primary", use_container_width=True):
            if not corregido:
                idx_correcta = q_actual.get("correcta")
                seleccion_actual = resp_dict[idx_actual].get("elegida")
                if seleccion_actual is None:
                    st.warning("Por favor, selecciona una alternativa antes de continuar.")
                elif idx_correcta is None:
                    st.error("Asigne primero la respuesta correcta en el selector superior antes de corregir.")
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
                    st.success(f"🎉 ¡Examen finalizado! Puntaje: {puntaje_final}% ({respondidas_ok}/{total_preguntas}). Guardado en historial.")
                    if st.button("Volver al Inicio"):
                        st.session_state.vista = "home"
                        st.session_state.prueba_activa = None
                        st.session_state.modo_estudio_data = None
                        st.rerun()

# --- VISTA: HOME ---
else:
    st.title("📚 Banco de Preguntas y Simulador de Estudio")
    st.markdown(f"Bienvenido, **{datos_usuario['nombre']}**. Sube tus documentos PDF oficiales o estudia de tus bancos guardados.")
    st.divider()

    st.subheader("➕ Crear Nueva Prueba desde PDF")
    uploaded_file = st.file_uploader("Sube tu archivo PDF con preguntas", type=["pdf"])
    nombre_nueva_prueba = st.text_input("Nombre de la prueba:", placeholder="Ej. Fisiología PTLA Avión")
    
    if st.button("Procesar y Crear Banco de Preguntas", type="primary"):
        if uploaded_file and nombre_nueva_prueba:
            with st.spinner("Leyendo PDF y extrayendo respuestas del documento..."):
                preguntas_extraidas = extraer_preguntas_de_pdf(uploaded_file)
                if preguntas_extraidas:
                    id_limpio = re.sub(r'[^a-zA-Z0-9_\-]', '_', nombre_nueva_prueba)
                    guardar_banco(id_limpio, {
                        "nombre": nombre_nueva_prueba,
                        "preguntas": preguntas_extraidas
                    })
                    st.success(f"¡Prueba '{nombre_nueva_prueba}' creada con éxito con {len(preguntas_extraidas)} preguntas!")
                    st.rerun()
                else:
                    st.error("No se pudieron detectar preguntas en el PDF.")
        else:
            st.warning("Sube un PDF y escribe un nombre.")

    st.divider()
    st.subheader("📂 Tus Pruebas Guardadas")
    bancos = listar_bancos()

    if not bancos:
        st.info("No hay pruebas guardadas todavía.")
    else:
        for b_id in bancos:
            datos_banco = cargar_banco(b_id)
            if not datos_banco:
                continue
            
            col_h1, col_h2, col_h3, col_h4 = st.columns([3, 2, 2, 2])
            with col_h1:
                nuevo_nombre = st.text_input(f"Editar {b_id}", value=datos_banco.get("nombre", b_id), key=f"edit_{b_id}", label_visibility="collapsed")
                if nuevo_nombre != datos_banco.get("nombre", b_id):
                    datos_banco["nombre"] = nuevo_nombre
                    guardar_banco(b_id, datos_banco)
            with col_h2:
                st.markdown(f"**Preguntas:** {len(datos_banco.get('preguntas', []))}")
            with col_h3:
                modo_aleatorio = st.checkbox("Modo Aleatorio", value=True, key=f"rnd_{b_id}")
            with col_h4:
                if st.button("🚀 Iniciar Estudio", key=f"btn_start_{b_id}", use_container_width=True):
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
                if st.button("🗑️ Eliminar", key=f"btn_del_{b_id}", use_container_width=True):
                    eliminar_banco(b_id)
                    st.rerun()
            st.divider()
