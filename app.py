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

# Parser de PDF para extraer preguntas, alternativas y respuesta correcta marcada
def extraer_preguntas_de_pdf(pdf_file):
    reader = PdfReader(pdf_file)
    texto_completo = ""
    for pagina in reader.pages:
        t = pagina.extract_text()
        if t:
            texto_completo += t + "\n"

    # Expresión regular orientada a detectar preguntas tipo formato aeronáutico/Daypo
    # Busca patrones como "1.- Pregunta..." o "Pregunta..." y sus alternativas A, B, C, D con marcas (ej. o, •, [x], (*))
    bloques = re.split(r'\n(?=[0-9]{1,3}[\.\-]\s|Pregunta\s+[0-9]+)', texto_completo)
    
    preguntas_parsed = []
    
    for bloque in bloques:
        if len(bloque.strip()) < 10:
            continue
            
        lineas = bloque.strip().split('\n')
        enunciado_lineas = []
        alternativas = []
        correcta_idx = None
        
        capturando_alt = False
        for linea in lineas:
            # Detectar alternativas (ej. A.-, A), a), etc.)
            match_alt = re.match(r'^([A-D])[\.\-\)]\s*(.*)', linea.strip(), re.IGNORECASE)
            if match_alt:
                capturando_alt = True
                letra = match_alt.group(1).upper()
                texto_alt = match_alt.group(2)
                
                # Detectar si la alternativa está marcada como respuesta correcta
                # Buscamos símbolos comunes de selección en texto extraído (•, (*), [x], o círculos rellenos)
                es_correcta = False
                if any(simbolo in linea for simbolo in ["(•)", "[x]", "(X)", "•", "(*)"]):
                    es_correcta = True
                
                idx = ord(letra) - ord('A')
                if es_correcta:
                    correcta_idx = idx
                
                alternativas.append({"letra": letra, "texto": texto_alt, "marcada": es_correcta})
            else:
                if not capturando_alt:
                    enunciado_lineas.append(linea)
                else:
                    # Si ya empezamos alternativas pero hay líneas largas continuas
                    if alternativas:
                        alternativas[-1]["texto"] += " " + linea.strip()

        enunciado = " ".join(enunciado_lineas).strip()
        # Limpiar numeración inicial del enunciado si la trae
        enunciado = re.sub(r'^[0-9]{1,3}[\.\-]\s*', '', enunciado)

        if enunciado and len(alternativas) >= 2:
            # Si no se detectó marca explícita por caracteres, asumimos la primera por defecto o 0
            if correcta_idx is None:
                correcta_idx = 0 
            preguntas_parsed.append({
                "pregunta": enunciado,
                "alternativas": alternativas,
                "correcta": correcta_idx
            })
            
    # Si el parser por bloques estrictos no arrojó resultados, aplicamos un parser de respaldo genérico
    if not preguntas_parsed:
        # Generador de prueba genérico para estructurar el contenido si el PDF tiene otro formato
        parrafos = texto_completo.split('\n\n')
        temp_alts = [{"letra": "A", "texto": "Opción Verdadera", "marcada": True}, {"letra": "B", "texto": "Opción Falsa", "marcada": False}]
        for i, p in enumerate(parrafos[:20]): # Máximo 20 de respaldo si es muy plano
            if len(p.strip()) > 15:
                preguntas_parsed.append({
                    "pregunta": p.strip(),
                    "alternativas": temp_alts,
                    "correcta": 0
                })

    return preguntas_parsed

# --- GESTIÓN DE ESTADOS EN STREAMLIT ---
if "vista" not in st.session_state:
    st.session_state.vista = "home" # "home", "estudio", "historial"
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
    st.info("Sube tus bancos en PDF, selecciona aleatoriedad y estudia como en Daypo / Prepware.")

# ==================== VISTA: HISTORIAL ====================
if st.session_state.vista == "historial":
    st.title("📊 Historial de Rendimiento (Últimos 20 días)")
    historial = obtener_historial_reciente()
    
    if not historial:
        st.warning("No hay registros de exámenes realizados en los últimos 20 días.")
    else:
        df_hist = pd.DataFrame(historial)
        
        # Calcular promedio general de los últimos 20 días
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

# ==================== VISTA: MODO ESTUDIO ====================
elif st.session_state.vista == "estudio" and st.session_state.modo_estudio_data:
    estudio = st.session_state.modo_estudio_data
    preguntas = estudio["preguntas"]
    idx_actual = estudio["idx_actual"]
    
    # Inicializar estados de respuestas si no existen
    if "respuestas_usuario" not in estudio:
        estudio["respuestas_usuario"] = {} # {idx: {"elegida": int, "estado": "correcta"/"incorrecta"/"omitida", "corregido": bool}}
    
    resp_dict = estudio["respuestas_usuario"]

    # --- BARRA SUPERIOR DE ESTADÍSTICAS ---
    total_preguntas = len(preguntas)
    respondidas_ok = sum(1 for k, v in resp_dict.items() if v.get("estado") == "correcta")
    respondidas_fail = sum(1 for k, v in resp_dict.items() if v.get("estado") == "incorrecta")
    
    col_top1, col_top2 = st.columns([6, 1])
    with col_top1:
        st.markdown(f"### 📋 Pregunta {idx_actual + 1} de {total_preguntas} &nbsp;&nbsp;|&nbsp;&nbsp; ✅ Buenas: {respondidas_ok} &nbsp;&nbsp;|&nbsp;&nbsp; ❌ Malas: {respondidas_fail}")
    
    with col_top2:
        # Botón superior derecho para desplegar cuadrícula de números
        with st.popover("🔢 Índice"):
            st.markdown("#### Selector de Preguntas")
            cols_grid = st.columns(5)
            for i in range(total_preguntas):
                # Determinar color/estado del borde
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

    # --- PREGUNTA Y ALTERNATIVAS ACTUALES ---
    q_actual = preguntas[idx_actual]
    st.markdown(f"#### {idx_actual + 1}.- {q_actual['pregunta']}")
    
    # Estado actual de esta pregunta
    estado_actual_q = resp_dict.get(idx_actual, {})
    corregido = estado_actual_q.get("corregido", False)
    seleccion_previa = estado_actual_q.get("elegida", None)
    
    # Formulario interactivo de alternativas
    opciones_textos = [f"{alt['letra']}.- {alt['texto']}" for alt in q_actual["alternativas"]]
    
    default_selection = seleccion_previa if seleccion_previa is not None else 0
    
    seleccion = st.radio(
        "Seleccione su alternativa:",
        options=range(len(opciones_textos)),
        format_func=lambda x: opciones_textos[x],
        index=default_selection,
        key=f"radio_q_{idx_actual}",
        disabled=corregido
    )
    
    # Guardar selección temporal del usuario
    if idx_actual not in resp_dict:
        resp_dict[idx_actual] = {"elegida": seleccion, "estado": None, "corregido": False}
    else:
        resp_dict[idx_actual]["elegida"] = seleccion

    # Mostrar retroalimentación visual si ya fue corregido (Siguiente presionado)
    if corregido:
        idx_correcta = q_actual["correcta"]
        if estado_actual_q["estado"] == "correcta":
            st.success("¡Correcto! Tiquet verde en la respuesta.")
        else:
            st.error("Incorrecto. Marcado con equis roja en tu respuesta y tiquet verde en la correcta.")
            
        for i_alt, alt in enumerate(q_actual["alternativas"]):
            if i_alt == idx_correcta:
                st.markdown(f"✅ **{alt['letra']}.- {alt['texto']}** (Respuesta Correcta)")
            elif i_alt == seleccion_previa and i_alt != idx_correcta:
                st.markdown(f"❌ **{alt['letra']}.- {alt['texto']}** (Tu respuesta errónea)")

    st.write("")
    col_bot1, col_bot2, col_bot3 = st.columns([2, 4, 2])

    # Parte inferior izquierda: Botón Omitir
    with col_bot1:
        if st.button("⬅️ Omitir", use_container_width=True):
            resp_dict[idx_actual] = {"elegida": seleccion, "estado": "omitida", "corregido": True}
            if idx_actual < total_preguntas - 1:
                estudio["idx_actual"] += 1
                st.rerun()
            else:
                st.warning("Has llegado al final de la prueba.")

    # Parte inferior derecha: Botón Siguiente / Corregir
    with col_bot3:
        texto_boton = "Siguiente ➡️" if corregido else "Contestar / Corregir"
        if st.button(texto_boton, type="primary", use_container_width=True):
            if not corregido:
                # Corregir
                idx_correcta = q_actual["correcta"]
                es_correcta = (seleccion == idx_correcta)
                estado_str = "correcta" if es_correcta else "incorrecta"
                resp_dict[idx_actual] = {
                    "elegida": seleccion,
                    "estado": estado_str,
                    "corregido": True
                }
                st.rerun()
            else:
                # Pasar a la siguiente pregunta
                if idx_actual < total_preguntas - 1:
                    estudio["idx_actual"] += 1
                    st.rerun()
                else:
                    # Fin del examen, guardar en historial
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

    # Sección superior: Cargar documentos PDF y crear nuevas pruebas
    st.subheader("➕ Crear Nueva Prueba desde PDF")
    uploaded_file = st.file_uploader("Sube tu archivo PDF con preguntas", type=["pdf"])
    nombre_nueva_prueba = st.text_input("Nombre de la prueba:", placeholder="Ej. Reglamentación PTLA Avión")
    
    if st.button("Procesar y Crear Banco de Preguntas", type="primary"):
        if uploaded_file and nombre_nueva_prueba:
            with st.spinner("Leyendo PDF y extrayendo preguntas y alternativas..."):
                preguntas_extraidas = extraer_preguntas_de_pdf(uploaded_file)
                if preguntas_extraidas:
                    # Guardar banco
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

    # Listado de todas las pruebas guardadas
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
                # Edición de nombres de pruebas
                nuevo_nombre = st.text_input(f"Editar {b_id}", value=datos_banco.get("nombre", b_id), key=f"edit_{b_id}", label_visibility="collapsed")
                if nuevo_nombre != datos_banco.get("nombre", b_id):
                    datos_banco["nombre"] = nuevo_nombre
                    guardar_banco(b_id, datos_banco)

            with col_h2:
                st.markdown(f"**Preguntas:** {len(datos_banco.get('preguntas', []))}")

            with col_h3:
                # Opción de modo aleatorio
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
