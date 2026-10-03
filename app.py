import streamlit as st
import json
import os
import hashlib

# Configuración de la página
st.set_page_config(
    page_title="AeroStudio Pro - Panel",
    page_icon="✈️",
    layout="centered"
)

USERS_FILE = "usuarios.json"

# Función para cargar usuarios desde el archivo JSON
def cargar_usuarios():
    if not os.path.exists(USERS_FILE):
        # Crear archivo inicial por defecto si no existe
        datos_iniciales = {
            "usuarios": [
                {
                    "correo": "pablo@aerudio.local",
                    "contrasena": hashlib.sha256("123456".encode()).hexdigest()
                }
            ]
        }
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(datos_iniciales, f, indent=4, ensure_ascii=False)
        return datos_iniciales["usuarios"]
    
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("usuarios", [])
    except Exception:
        return []

# Función para registrar un nuevo usuario
def registrar_usuario(correo, contrasena):
    usuarios = cargar_usuarios()
    
    # Verificar si el correo ya está registrado
    for u in usuarios:
        if u["correo"].lower() == correo.lower():
            return False, "El correo electrónico ya se encuentra registrado."
    
    # Hashear contraseña
    hashed_pw = hashlib.sha256(contrasena.encode()).hexdigest()
    usuarios.append({"correo": correo.lower(), "contrasena": hashed_pw})
    
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump({"usuarios": usuarios}, f, indent=4, ensure_ascii=False)
    
    return True, "¡Registro exitoso! Ya puedes iniciar sesión."

# Función para verificar las credenciales de acceso
def verificar_login(correo, contrasena):
    usuarios = cargar_usuarios()
    hashed_pw = hashlib.sha256(contrasena.encode()).hexdigest()
    
    for u in usuarios:
        if u["correo"].lower() == correo.lower() and u["contrasena"] == hashed_pw:
            return True
    return False

# Control de estado de sesión
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
if "usuario_actual" not in st.session_state:
    st.session_state.usuario_actual = ""

# Interfaz principal de autenticación
if not st.session_state.autenticado:
    st.title("🔐 AeroStudio Pro - Acceso")
    st.markdown("Por favor, inicia sesión o regístrate para continuar.")
    
    tab_login, tab_registro = st.tabs(["Iniciar Sesión", "Registrarse"])
    
    with tab_login:
        st.subheader("Acceso a tu cuenta")
        with st.form("form_login"):
            correo_ingreso = st.text_input("Correo electrónico")
            pass_ingreso = st.text_input("Contraseña", type="password")
            submit_login = st.form_submit_button("Entrar")
            
            if submit_login:
                if verificar_login(correo_ingreso, pass_ingreso):
                    st.session_state.autenticado = True
                    st.session_state.usuario_actual = correo_ingreso
                    st.success("¡Inicio de sesión exitoso!")
                    st.rerun()
                else:
                    st.error("Correo o contraseña incorrectos. Verifica tus datos o regístrate.")
                    
    with tab_registro:
        st.subheader("Crear una cuenta nueva")
        with st.form("form_registro"):
            correo_nuevo = st.text_input("Correo electrónico nuevo")
            pass_nuevo = st.text_input("Contraseña nueva", type="password")
            pass_confirmar = st.text_input("Confirmar contraseña", type="password")
            submit_registro = st.form_submit_button("Registrarse")
            
            if submit_registro:
                if not correo_nuevo or not pass_nuevo:
                    st.warning("Por favor, completa todos los campos.")
                elif pass_nuevo != pass_confirmar:
                    st.error("Las contraseñas no coinciden.")
                else:
                    exito, mensaje = registrar_usuario(correo_nuevo, pass_nuevo)
                    if exito:
                        st.success(mensaje)
                    else:
                        st.error(mensaje)

else:
    # --- PANEL PRINCIPAL (Una vez autenticado) ---
    st.sidebar.title("Navegación")
    st.sidebar.write(f"Conectado como: **{st.session_state.usuario_actual}**")
    
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.autenticado = False
        st.session_state.usuario_actual = ""
        st.rerun()
        
    st.title("✈️ AeroStudio Pro - Panel Principal")
    st.markdown("¡Bienvenido al sistema! Has iniciado sesión correctamente.")
    
    # Aquí puedes agregar el contenido de tu aplicación
    st.info("Este es tu espacio de trabajo principal. Puedes añadir aquí tus módulos de cálculo, gestión o reportes.")
