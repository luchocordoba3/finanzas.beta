import streamlit as st

from core import auth, ui
from core.models import Usuario
from core.services import config, documentos

st.title("⚙️ Configuración")

with ui.sesion() as s:
    cfg = config.todos(s)
    usuarios = [(u.id, u.nombre, u.usuario, u.activo) for u in auth.usuarios(s, solo_activos=False)]

t_vivero, t_param, t_usuarios, t_backup = st.tabs(["Datos del vivero", "Avisos y opciones", "Usuarios", "Copia de seguridad"])

with t_vivero:
    with st.form("datos_vivero"):
        nombre = st.text_input("Nombre del vivero", cfg["nombre_vivero"])
        direccion = st.text_input("Dirección", cfg["direccion"])
        telefono = st.text_input("Teléfono / WhatsApp", cfg["telefono"])
        st.caption("Se usan en el comprobante de venta.")
        if st.form_submit_button("Guardar", type="primary", icon="💾"):
            ui.ejecutar(config.guardar, {"nombre_vivero": nombre.strip() or "Mi Vivero", "direccion": direccion,
                                         "telefono": telefono}, ok="Datos guardados")

with t_param:
    with st.form("parametros"):
        c = st.columns(3)
        dias_aviso = c[0].number_input("Avisar pedidos, compras y pagos con (días) de anticipación", 0, 30,
                                       int(cfg["dias_aviso"]))
        dias_deuda = c[1].number_input("Avisar deudas de clientes de más de (días)", 1, 365, int(cfg["dias_deuda"]))
        dias_sin_venta = c[2].number_input("Considerar sin movimiento un producto sin ventas en (días)", 7, 365,
                                           int(cfg["dias_sin_venta"]))
        medios = st.text_input("Medios de pago (separados por coma)", cfg["medios_pago"])
        produccion = st.toggle("Usar el módulo de producción propia (semillas, esquejes, lotes)",
                               cfg["modulo_produccion"] == "1")
        if st.form_submit_button("Guardar", type="primary", icon="💾"):
            ui.ejecutar(config.guardar, {"dias_aviso": dias_aviso, "dias_deuda": dias_deuda,
                                         "dias_sin_venta": dias_sin_venta, "medios_pago": medios,
                                         "modulo_produccion": "1" if produccion else "0"}, ok="Opciones guardadas")

with t_usuarios:
    st.caption("Cada socio entra con su usuario; el sistema registra quién cargó cada venta, pedido, compra o ajuste.")
    for uid_, nombre, usuario, activo in usuarios:
        c = st.columns([4, 2], vertical_alignment="center")
        c[0].markdown(f"**{nombre}** · usuario `{usuario}`" + ("" if activo else " · :gray-badge[Inactivo]"))
        if uid_ != ui.uid():
            def _activar(s, i, valor):
                s.get(Usuario, i).activo = valor

            if c[1].button("Desactivar" if activo else "Reactivar", key=f"act_{uid_}", width="stretch"):
                ui.ejecutar(_activar, uid_, not activo, ok="Usuario actualizado")
    c = st.columns(2)
    with c[0].form("nuevo_usuario", clear_on_submit=True):
        st.markdown("**Agregar usuario**")
        nombre = st.text_input("Nombre")
        usuario = st.text_input("Usuario")
        clave = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Crear usuario", type="primary"):
            ui.ejecutar(auth.crear_usuario, nombre, usuario, clave, ok="Usuario creado")
    with c[1].form("cambiar_clave", clear_on_submit=True):
        st.markdown("**Cambiar mi contraseña**")
        nueva = st.text_input("Nueva contraseña", type="password")
        nueva2 = st.text_input("Repetila", type="password")
        if st.form_submit_button("Cambiar"):
            if nueva != nueva2:
                st.error("Las contraseñas no coinciden.")
            else:
                ui.ejecutar(auth.cambiar_password, ui.uid(), nueva, ok="Contraseña cambiada")

with t_backup:
    st.markdown("Descargá todos los datos en un Excel (una hoja por tabla). Conviene hacerlo una vez por semana.")
    if st.button("Preparar copia de seguridad", icon="🗄️"):
        with ui.sesion() as s:
            st.session_state["_backup"] = documentos.backup_excel(s)
    if "_backup" in st.session_state:
        from core.tiempo import hoy
        st.download_button("Descargar Excel", st.session_state["_backup"], f"vivero_backup_{hoy():%Y%m%d}.xlsx",
                           icon="📥", type="primary")
