"""Sistema de gestión del vivero.  Correr con:  streamlit run vivero/app.py"""
import time

import streamlit as st

from core import auth, ui
from core.services import config

st.set_page_config(page_title="Vivero", page_icon="🌱", layout="wide")

problema = ui.problema_base()
if problema:
    ui.pantalla_problema_base(*problema)
    st.stop()


def _entrar(u) -> None:
    st.session_state.usuario = {"id": u.id, "nombre": u.nombre}
    st.rerun()


def pantalla_ingreso() -> None:
    with ui.sesion() as s:
        primera_vez = not auth.hay_usuarios(s)
        nombre = config.obtener(s, "nombre_vivero")
    _, centro, _ = st.columns([1, 2, 1])
    with centro:
        st.title(f"🌱 {nombre}")
        if primera_vez:
            st.info("Primera vez: creá tu usuario. El de tu socio/a lo agregás después desde **Configuración**.")
            with st.form("primer_usuario"):
                nombre = st.text_input("Tu nombre")
                usuario = st.text_input("Usuario para ingresar")
                clave = st.text_input("Contraseña (mínimo 6 caracteres)", type="password")
                clave2 = st.text_input("Repetí la contraseña", type="password")
                if st.form_submit_button("Crear usuario y entrar", type="primary", width="stretch"):
                    if clave != clave2:
                        st.error("Las contraseñas no coinciden.")
                    else:
                        u = ui.ejecutar(auth.crear_usuario, nombre, usuario, clave, recargar=False)
                        if u:
                            _entrar(u)
        else:
            with st.form("ingreso"):
                usuario = st.text_input("Usuario")
                clave = st.text_input("Contraseña", type="password")
                if st.form_submit_button("Ingresar", type="primary", width="stretch"):
                    with ui.sesion() as s:
                        u = auth.autenticar(s, usuario, clave)
                    if u:
                        _entrar(u)
                    time.sleep(1)  # frena intentos a ciegas
                    st.error("Usuario o contraseña incorrectos.")


if not ui.usuario():
    st.navigation([st.Page(pantalla_ingreso, title="Ingresar", icon="🔐")]).run()
    st.stop()

usuario = ui.usuario()
with ui.sesion() as s:
    cfg = config.todos(s)
n_alertas = ui.contar_alertas(usuario["id"])

administracion = [
    st.Page("vistas/compras.py", title="Compras", icon="🧾"),
    st.Page("vistas/proveedores.py", title="Proveedores", icon="🚚"),
    st.Page("vistas/catalogo.py", title="Catálogo y precios", icon="🏷️"),
    st.Page("vistas/est_ventas.py", title="Estadísticas de ventas", icon="📈"),
    st.Page("vistas/est_plantas.py", title="Estadísticas de plantas", icon="🌿"),
    st.Page("vistas/configuracion.py", title="Configuración", icon="⚙️"),
]
if cfg["modulo_produccion"] == "1":
    administracion.insert(5, st.Page("vistas/produccion.py", title="Producción propia", icon="🌾"))

pagina = st.navigation({
    "Día a día": [
        st.Page("vistas/inicio.py", title=f"Inicio ({n_alertas})" if n_alertas else "Inicio", icon="🏠", default=True),
        st.Page("vistas/vender.py", title="Vender", icon="🛒"),
        st.Page("vistas/pedidos.py", title="Pedidos", icon="📦"),
        st.Page("vistas/clientes.py", title="Clientes", icon="👥"),
        st.Page("vistas/stock.py", title="Stock", icon="🌱"),
        st.Page("vistas/recordatorios.py", title="Recordatorios", icon="⏰"),
    ],
    "Administración": administracion,
}, expanded=True)

with st.sidebar:
    st.caption(f"🌱 {cfg['nombre_vivero']} · sesión de **{usuario['nombre']}**")
    if st.button("Cerrar sesión", icon="🔒", width="stretch"):
        st.session_state.clear()
        st.rerun()

ui.mostrar_flash()
pagina.run()
