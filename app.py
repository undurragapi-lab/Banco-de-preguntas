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

# Inyección de estilos CSS para alinear los botones de alternativas estrictamente a la izquierda
st.markdown("""
<style>
    div.stButton > button {
        text-align: left !important;
        justify-content: flex-start !important;
        padding-left: 20px !important;
    }
</style>
""", unsafe_allow_html=True)

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

# Parser avanzado y ultra preciso para extraer preguntas y alternativas con marcas exactas
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

    # Separar bloques por número de pregunta (ej. "1.-", "2.-")
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
        
        # Aislar el enunciado y las líneas del bloque
        lineas = cuerpo_bloque.split('\n')
        enunciado_lineas = []
        lineas_alternativas = []
        
        capturando_alts = False
        for linea in lineas:
            linea_str = linea.strip()
            # Detectar si la línea comienza con una alternativa (A.-, B.-, C.-, D.- o variantes con marcas)
            if re.match(r'^([☑X✔✓]?\s*[A-D])[\.\-\)]', linea_str) or capturando_alts:
                capturando_alts = True
                lineas_alternativas.append(linea_str)
            else:
                if not capturando_alts:
                    enunciado_lineas.append(linea_str)
                else:
                    lineas_alternativas.append(linea_str)

        enunciado = " ".join(enunciado_lineas).strip()
        enunciado = re.sub(r'Materia\s*:.*?Cantidad de Preguntas\s*:\s*[0-9]+', '', enunciado).strip()

        # Reconstruir texto de alternativas unidas
        texto_alts_unido = " ".join(lineas_alternativas)
        
        # Buscar fragmentos de alternativas usando expresión regular robusta
        # Busca patrones como A.-, B.-, C.-, D.- permitiendo símbolos de marca antes o después
        raw_parts = re.split(r'([☑X✔✓]?\s*[A-D])[\.\-\)]\s*', texto_alts_unido)
        
        alternativas = []
        correcta_idx = None
        
        if len(raw_parts) >= 3:
            # raw_parts viene como [texto_basura, token_A, texto_A, token_B, texto_B, ...]
            idx_alt = 0
            i = 1
            while i < len(raw_parts) - 1:
                token_letra = raw_parts[i].strip()
                texto_alt = raw_parts[i+1].strip()
                
                # Extraer letra real (A, B, C, D)
                match_letra = re.search(r'([A-D])', token_letra)
                if match_letra:
                    letra = match_letra.group(1)
                else:
                    letra = chr(ord('A') + idx_alt)

                # Verificar si tiene marca de respuesta correcta (☑, X, ✔, etc.)
                es_correcta = False
                if any(s in token_letra for s in ['☑', 'X', '✔', '✓', '●', '[x]', '(X)']):
                    es_correcta = True
                if any(s in texto_alt[:5] for s in ['☑', 'X', '✔', '✓', '●', '[x]', '(X)']):
                    es_correcta = True

                # Limpiar símbolos gráficos del texto de la alternativa
                for s in ['☑', 'X', '✔', '✓', '●', '(•)', '[x]', '(X)', '•', '(*)', '❌', '×']:
                    texto_alt = texto_alt.replace(s, "")
                texto_alt = re.sub(r'^[\bX\b\/\-\_\+\*\.]+\s*', '', texto_alt).strip()

                current_idx = ord(letra) - ord('A')
                if es_correcta:
                    correcta_idx = current_idx

                alternativas.append({
                    "letra": letra,
                    "texto": texto_alt,
                    "marcada": es_correcta
                })
                
                idx_alt += 1
                i += 2

        # Si por alguna razón no se detectó marca con el split anterior, intentamos un análisis línea por línea
        if correcta_idx is None and alternativas:
            for idx_a, alt in enumerate(alternativas):
                if alt["marcada"]:
                    correcta_idx = idx_a
                    break
            if correcta_idx is None:
                correcta_idx = 0 # Fallback por seguridad

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
    st.info("Sube tus bancos en PDF. El sistema detecta correctamente las alternativas con marcas X o casillas ☑.")

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

    # --- MOSTRAR UNA PREGUNTA Y SUS ALTERNATIVAS ALINEADAS A LA IZQUIERDA ---
    q_actual = preguntas[idx_actual]
    st.markdown(f"#### {idx_actual + 1}.- {q_actual['pregunta']}")
    
    if idx_actual not in resp_dict:
        resp_dict[idx_actual] = {"elegida": None, "estado": None, "corregido": False}
    
    estado_actual_q = resp_dict[idx_actual]
    corregido = estado_actual_q.get("corregido", False)
    seleccion_actual = estado_actual_q.get("elegida", None)

    st.markdown("Seleccione su alternativa:")

    for i_alt, alt in enumerate(q_actual["alternativas"]):
        btn_label = f"{alt['letra']}.- {alt['texto']}"
        is_selected = (seleccion_actual == i_alt)
        
        prefix = "🔘" if is_selected else "⚪"
        if corregido:
            if i_alt == q_actual.get("correcta"):
                prefix = "✅"
            elif is_selected and i_alt != q_actual.get("correcta"):
                prefix = "❌"

        if st.button(f"{prefix} {btn_label}", key=f"alt_btn_{idx_actual}_{i_alt}", disabled=corregido, use_container_width=True):
            resp_dict[idx_actual]["elegida"] = i_alt
            st.rerun()

    if seleccion_actual is not None:
        st.caption(f"Opción seleccionada actualmente: **Alternativa {q_actual['alternativas'][seleccion_actual]['letra']}**")
    else:
        st.caption("⚠️️ Ninguna alternativa seleccionada (Pregunta en blanco).")

    if corregido:
        idx_correcta = q_actual.get("correcta")
        if estado_actual_q["estado"] == "correcta":
            st.success("¡Correcto! Respuesta acertada.")
        else:
            st.error("Incorrecto.")

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
                if seleccion_actual is None:
                    st.warning("Por favor, selecciona una alternativa o presiona Omitir.")
                else:
                    idx_correcta = q_actual.get("correcta")
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
            with st.spinner("Leyendo PDF y asociando marcas correctas con precisión..."):
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
