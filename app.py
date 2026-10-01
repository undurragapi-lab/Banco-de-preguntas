import streamlit as st
import json
import os
import hashlib

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="AeroStudio Pro", page_icon="✈️", layout="wide")

# --- FUNCIONES DE SEGURIDAD Y BASE DE DATOS ---
DB_FILE = "usuarios.json"

def hash_password(password):
    """Encripta la contraseña usando SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def cargar_usuarios():
    """Carga la base de datos de usuarios desde el archivo JSON"""
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def guardar_usuarios(usuarios_db):
    """Guarda la base de datos de usuarios en el archivo JSON"""
    with open(DB_FILE, "w") as f:
        json.dump(usuarios_db, f, indent=4)

# --- INICIALIZACIÓN DE SESIÓN ---
if "usuario_actual" not in st.session_state:
    st.session_state.usuario_actual = None

usuarios_db = cargar_usuarios()

# --- CONTROL DE ACCESO (LOGIN / REGISTRO) ---
if st.session_state.usuario_actual is None:
    # Diseño del encabezado
    st.markdown("<h1 style='text-align: center;'>✈️ AeroStudio Pro</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>Plataforma de entrenamiento aeronáutico</p>", unsafe_allow_html=True)
    st.write("---")
    
    # Centrar los formularios
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        tab1, tab2 = st.tabs(["Iniciar Sesión", "Crear Cuenta"])
        
        with tab1:
            email_in = st.text_input("Correo electrónico:", key="login_email")
            pass_in = st.text_input("Contraseña:", type="password", key="login_pass")
            
            if st.button("Ingresar", use_container_width=True):
                if email_in in usuarios_db:
                    db_pass = usuarios_db[email_in].get("password", "")
                    pass_in_hashed = hash_password(pass_in)
                    
                    # MAGIA AQUÍ: Verifica si la contraseña coincide con el hash nuevo o con el texto plano antiguo
                    if db_pass == pass_in_hashed or db_pass == pass_in:
                        # Si era la contraseña antigua (texto plano), la actualiza al formato seguro
                        if db_pass == pass_in:
                            usuarios_db[email_in]["password"] = pass_in_hashed
                            guardar_usuarios(usuarios_db)
                            
                        st.session_state.usuario_actual = email_in
                        st.rerun()
                    else:
                        st.error("Credenciales incorrectas.")
                else:
                    st.error("El usuario no existe. Ve a 'Crear Cuenta'.")

        with tab2:
            new_email = st.text_input("Correo electrónico:", key="reg_email")
            new_pass = st.text_input("Contraseña nueva:", type="password", key="reg_pass")
            new_pass_confirm = st.text_input("Confirmar contraseña:", type="password", key="reg_pass_confirm")
            
            if st.button("Crear Cuenta", use_container_width=True):
                if not new_email or not new_pass:
                    st.warning("Por favor, completa todos los campos.")
                elif new_email in usuarios_db:
                    st.warning("Este correo ya está registrado. Intenta iniciar sesión.")
                elif new_pass != new_pass_confirm:
                    st.error("Las contraseñas no coinciden.")
                elif len(new_pass) < 6:
                    st.error("La contraseña debe tener al menos 6 caracteres por seguridad.")
                else:
                    # Guardar nuevo usuario con contraseña encriptada
                    usuarios_db[new_email] = {
                        "password": hash_password(new_pass),
                        # Aquí puedes agregar más datos iniciales del perfil si los necesitas
                    }
                    guardar_usuarios(usuarios_db)
                    st.success("Cuenta creada exitosamente. Ahora puedes iniciar sesión arriba.")

# --- APLICACIÓN PRINCIPAL (AeroStudio Pro) ---
else:
    # Sidebar con el perfil y cierre de sesión
    st.sidebar.title("👨‍✈️ Perfil")
    st.sidebar.write(f"**Usuario:** {st.session_state.usuario_actual}")
    
    if st.sidebar.button("Cerrar Sesión", use_container_width=True):
        st.session_state.usuario_actual = None
        st.rerun()
        
    st.title("Bienvenido a AeroStudio Pro ✈️")
    
    # =====================================================================
    # PEGA AQUÍ EL RESTO DE TU CÓDIGO (Parser de PDF, Simulador, Modo Oscuro, etc.)
    # =====================================================================
    st.info("El sistema de acceso está funcionando. Inserta el código de los módulos de estudio aquí.")
