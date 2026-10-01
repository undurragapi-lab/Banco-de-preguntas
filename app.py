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

# Directorio para almacenar las pruebas y el historial localmente
DATA_DIR = "data_bancos"
HISTORY_FILE = "historial_resultados.json"

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# Funciones de almacenamiento y carga de bancos de preguntas
def guardar_banco(nombre_id, data):
    ruta = os.path.join(DATA_DIR, f"{nombre_id}.json")
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

# Funciones para el historial de resultados (últimos 20 días)
def guardar_resultado_historial(nombre_prueba, puntaje_pct, correctas, total):
    historial = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                historial = json.load(f)
        except:
            historial = []
    
    nuevo_registro = {
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
    filtrado = [h for h in historial if h.get("timestamp", 0) >= limite_tiempo]
    return sorted(filtrado, key=lambda x: x["timestamp"], reverse=True)

# Parser avanzado y preciso de PDF basado en tus reglas de marcas, tiquets y X
def extraer_preguntas_de_pdf(pdf_file):
    reader = PdfReader(pdf_file)
    texto_completo = ""
    for pagina in reader.pages:
        t = pagina.extract_text()
        if t:
            texto_completo += t + "\n"

    texto_completo = re.sub(r'\r\n', '\n', texto_completo)

    # Fraccionar por la numeración de preguntas (ej. "1.-", "2.-")
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
        
        # Dividir el bloque por las alternativas A.-, B.-, C.-, D.-
        partes_alt = re.split(r'\b([A-D])\.-\s*', cuerpo_bloque)
        
        if len(partes_alt) < 3:
            continue
            
        enunciado = partes_alt[0].strip()
        enunciado = re.sub(r'Materia\s*:.*?Cantidad de Preguntas\s*:\s*[0-9]+', '', enunciado).strip()
        
        alternativas = []
        candidatas_correctas = []
        
        i = 1
        while i < len(partes_alt) - 1:
            letra = partes_alt[i].upper()
            texto_alt = partes_alt[i+1].strip()
            
            texto_alt = re.sub(r'\s+[0-9]{1,3}\.-.*$', '', texto_alt)
            
            idx = ord(letra) - ord('A')
            
            tiene_marca_general = any(s in texto_alt or s in partes_alt[i] for s in ["●", "(•)", "[x]", "(X)", "•", "(*)", "✓", "✔", "√"])
            tiene_tiquet = any(s in texto_alt or s in partes_alt[i] for s in ["✓", "✔", "√"])
            tiene_x = any(s in texto_alt or s in partes_alt[i] for s in ["X", "❌", "×"])
            
            if tiene_tiquet:
                candidatas_correctas = [idx]
            elif tiene_marca_general and not tiene_x:
                candidatas_correctas.append(idx)
                
            for simbolo in ["●", "(•)", "[x]", "(X)", "•", "(*)", "✓", "✔", "√", "X", "❌", "×"]:
                texto_alt = texto_alt.replace(simbolo, "")
            texto_alt = texto_alt.strip()

            alternativas.append({
                "letra": letra,
                "texto": texto_alt,
                "marcada": tiene_marca_general
            })
            i += 2

        correcta_idx = None
        if candidatas_correctas:
            correcta_idx = candidatas_correctas[0]

        if enunciado and len(alternativas) >= 2:
            preguntas_parsed.append({
                "pregunta": enunciado,
                "alternativas": alternativas,
                "correcta": correcta_idx
            })

    return preguntas_parsed

# --- GESTIÓN DE ESTADOS EN STREAMLIT ---
if "vista" not in st.session_state:
    st.session_state.vista = "home"
if "prueba_activa" not in st.session_state:
    st.session_state.prueba_activa = None
if "modo_estudio_data" not in st.session_state:
    st.session_state.modo_estudio_data = None

# ==================== BARRA LATERAL / MENÚ DE HERRAMIENTAS ====================
with st.sidebar:
    st.markdown("### 🛠️ Menú de Herramientas")
    if st.button("🏠 Volver al Inicio / Pruebas", use_container_width=True):
        st.session_state.vista = "home"
        st.session_state.prueba_activa = None
        st.rerun()
        
    if st.button("📊 Historial de Pruebas (Últimos 20 días)", use_container_width=True):
        st.session_state.vista = "historial"
        st.rerun()
        
    st.divider()
    st.markdown("### ✈️ Panel de Control")
    st.info("Sube tus bancos en PDF. El sistema detecta tiquets de corrección y marcas automáticamente.")

# ==================== VISTA: HISTORIAL ====================
if st.session_state.vista == "historial":
    st.title("📊 Historial de Rendimiento (Últimos 20 días)")
    historial = obtener_historial_reciente()
    
    if not historial:
        st.warning("No hay registros de exámenes realizados en los últimos 20 días.")
    else:
        df_hist = pd.DataFrame(historial)
        promedio_general = df_hist["puntaje"].mean()
        st.metric(label="Promedio General de Rendimiento", value=f"{promedio_general:.1f}%")
        
        st.divider()
        st.subheader("Desglose por Examen")
        for h in historial:
            with st.container():
                col1, col2, col3 = st.columns([3, 2, 2])
                col1.markdown(f"**Prueba:** {h['prueba']}")
                col2.markdown(f"Fecha: {h['fecha']}")
                col3.markdown(f"**Puntaje:** {h['puntaje']}% ({h['correctas']}/{h['total']} correctas)")
                st.divider()
                
    if st.button("⬅️ Regresar al Inicio"):
        st.session_state.vista = "home"
        st.rerun()

# ==================== VISTA: MODO ESTUDIO (UNA PREGUNTA POR PÁGINA) ====================
elif st.session_state.vista == "estudio" and st.session_state.modo_estudio_data:
    estudio = st.session_state.modo_estudio_data
    preguntas = estudio["preguntas"]
    idx_actual = estudio["idx_actual"]
    
    if "respuestas_usuario" not in estudio:
        estudio["respuestas_usuario"] = {}
    
    resp_dict = estudio["respuestas_usuario"]

    total_preguntas = len(preguntas)
    respondidas_ok = sum(1 for k, v in resp_dict.items() if v.get("estado") == "correcta")
    respondidas_fail = sum(1 for k, v in resp_dict.items() if v.get("estado") in ["incorrecta", "omitida"])
    
    # Cálculo del porcentaje considerando preguntas en blanco/omitidas como incorrectas
    puntaje_porcentaje = int((respondidas_ok / total_preguntas) * 100) if total_preguntas > 0 else 0
    
    # --- BARRA SUPERIOR Y CUADRÍCULA (ESQUINA SUPERIOR DERECHA) ---
    col_top1, col_top2 = st.columns([5, 2])
    with col_top1:
        st.markdown(f"### 📋 Q: {idx_actual + 1}/{total_preguntas} &nbsp;|&nbsp; ✅ {respondidas_ok} &nbsp;|&nbsp; ❌ {respondidas_fail} &nbsp;|&nbsp; 📈 **{puntaje_porcentaje}%**")
    
    with col_top2:
        with st.popover("🔢 Cuadrícula de Preguntas"):
            st.markdown("#### Selector de Preguntas")
            st.caption("🔵 Actual | 🟢 Correcta | 🔴 Incorrecta | ⚪ Omitida | ⚫ Sin responder")
            cols_grid = st.columns(5)
            for i in range(total_preguntas):
                estado_q = resp_dict.get(i, {}).get("estado")
                if i == idx_actual:
                    label_btn = f"🔵 {i+1}"
                elif estado_q == "correcta":
                    label_btn = f"🟢 {i+1}"
                elif estado_q == "incorrecta":
                    label_btn = f"🔴 {i+1}"
                elif estado_q == "omitida":
                    label_btn = f"⚪ {i+1}"
                else:
                    label_btn = f"⚫ {i+1}"
                
                with cols_grid[i % 5]:
                    if st.button(label_btn, key=f"grid_{i}", use_container_width=True):
                        estudio["idx_actual"] = i
                        st.rerun()

    st.progress((idx_actual + 1) / total_preguntas)
    st.divider()

    # --- MOSTRAR UNA PREGUNTA Y SUS ALTERNATIVAS ---
    q_actual = preguntas[idx_actual]
    st.markdown(f"#### {idx_actual + 1}.- {q_actual['pregunta']}")
    
    estado_actual_q = resp_dict.get(idx_actual, {})
    corregido = estado_actual_q.get("corregido", False)
    seleccion_previa = estado_actual_q.get("elegida", None)
    
    opciones_textos = [f"{alt['letra']}.- {alt['texto']}" for alt in q_actual["alternativas"]]
    
    default_radio_idx = seleccion_previa if seleccion_previa is not None else 0
    seleccion = st.radio(
        "Seleccione su alternativa:",
        options=range(len(opciones_textos)),
        format_func=lambda x: opciones_textos[x],
        index=default_radio_idx,
        key=f"radio_q_{idx_actual}",
        disabled=corregido
    )

    if idx_actual not in resp_dict:
        resp_dict[idx_actual] = {"elegida": None, "estado": None, "corregido": False}

    if q_actual.get("correcta") is None:
        st.info("ℹ️ Esta pregunta no tiene una respuesta correcta marcada con tiquet en el documento original.")
        col_m1, col_m2 = st.columns([3, 1])
        with col_m1:
            alt_correcta_manual = st.selectbox("Selecciona la alternativa correcta:", options=range(len(opciones_textos)), format_func=lambda x: opciones_textos[x], key=f"man_corr_{idx_actual}")
        with col_m2:
            if st.button("Guardar Respuesta", key=f"btn_save_corr_{idx_actual}"):
                q_actual["correcta"] = alt_correcta_manual
                st.success("¡Respuesta correcta guardada!")
                st.rerun()

    if corregido:
        idx_correcta = q_actual.get("correcta")
        if estado_actual_q["estado"] == "correcta":
            st.success("¡Correcto! Respuesta acertada.")
        else:
            st.error("Incorrecto.")
            
        for i_alt, alt in enumerate(q_actual["alternativas"]):
            if i_alt == idx_correcta:
                st.markdown(f"✅ **{alt['letra']}.- {alt['texto']}** (Respuesta Correcta)")
            elif i_alt == seleccion_previa and i_alt != idx_correcta:
                st.markdown(f"❌ **{alt['letra']}.- {alt['texto']}** (Tu respuesta errónea)")

    st.write("")
    col_bot1, col_bot2, col_bot3 = st.columns([2, 4, 2])

    with col_bot1:
        if st.button("⬅️ Omitir", use_container_width=True):
            resp_dict[idx_actual] = {"elegida": seleccion, "estado": "omitida", "corregido": True}
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
                if idx_correcta is None:
                    st.warning("Por favor, asigna la alternativa correcta para esta pregunta antes de continuar.")
                else:
                    es_correcta = (seleccion == idx_correcta)
                    estado_str = "correcta" if es_correcta else "incorrecta"
                    resp_dict[idx_actual] = {
                        "elegida": seleccion,
                        "estado": estado_str,
                        "corregido": True
                    }
                    st.rerun()
            else:
                if idx_actual < total_preguntas - 1:
                    estudio["idx_actual"] += 1
                    st.rerun()
                else:
                    puntaje_final = int((respondidas_ok / total_preguntas) * 100) if total_preguntas > 0 else 0
                    guardar_resultado_historial(estudio["nombre_prueba"], puntaje_final, respondidas_ok, total_preguntas)
                    st.success(f"🎉 ¡Examen finalizado! Tu puntaje fue de {puntaje_final}% ({respondidas_ok}/{total_preguntas} correctas). Guardado en el historial.")
                    if st.button("Finalizar y volver al Inicio"):
                        st.session_state.vista = "home"
                        st.session_state.prueba_activa = None
                        st.session_state.modo_estudio_data = None
                        st.rerun()

# ==================== VISTA: HOME (PÁGINA PRINCIPAL) ====================
else:
    st.title("📚 Banco de Preguntas y Simulador de Estudio")
    st.markdown("Carga tus documentos PDF con preguntas y alternativas para comenzar a estudiar de forma interactiva.")
    
    st.divider()

    st.subheader("➕ Crear Nueva Prueba desde PDF")
    uploaded_file = st.file_uploader("Sube tu archivo PDF con preguntas", type=["pdf"])
    nombre_nueva_prueba = st.text_input("Nombre de la prueba:", placeholder="Ej. Reglamentación PTLA Avión")
    
    if st.button("Procesar y Crear Banco de Preguntas", type="primary"):
        if uploaded_file and nombre_nueva_prueba:
            with st.spinner("Leyendo PDF, buscando tiquets y detectando alternativas marcadas..."):
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
                    st.error("No se pudieron detectar preguntas con alternativas válidas en el PDF.")
        else:
            st.warning("Por favor, sube un archivo PDF y escribe un nombre para la prueba.")

    st.divider()

    st.subheader("📂 Tus Pruebas Guardadas")
    bancos = listar_bancos()

    if not bancos:
        st.info("No hay pruebas guardadas todavía. Sube un PDF arriba para empezar.")
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
