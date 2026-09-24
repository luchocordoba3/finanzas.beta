import streamlit as st

from core import auth, db, ui
from core.models import Usuario
from core.services import config, documentos, notificaciones

st.title("⚙️ Configuración")

with ui.sesion() as s:
    cfg = config.todos(s)
    usuarios = [(u.id, u.nombre, u.usuario, u.activo) for u in auth.usuarios(s, solo_activos=False)]

t_vivero, t_param, t_telegram, t_usuarios, t_backup = st.tabs(
    ["Datos del vivero", "Avisos y opciones", "Avisos por Telegram", "Usuarios", "Copia de seguridad"])

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
        c = st.columns([3, 1])
        medios = c[0].text_input("Medios de pago (separados por coma)", cfg["medios_pago"])
        codigo_area = c[1].text_input("Código de área", cfg["codigo_area"],
                                      help="Se usa para los números de WhatsApp cargados sin código de área (ej.: 11).")
        produccion = st.toggle("Usar el módulo de producción propia (semillas, esquejes, lotes)",
                               cfg["modulo_produccion"] == "1")
        if st.form_submit_button("Guardar", type="primary", icon="💾"):
            ui.ejecutar(config.guardar, {"dias_aviso": dias_aviso, "dias_deuda": dias_deuda,
                                         "dias_sin_venta": dias_sin_venta, "medios_pago": medios,
                                         "modulo_produccion": "1" if produccion else "0",
                                         "codigo_area": "".join(ch for ch in codigo_area if ch.isdigit()) or "11"},
                        ok="Opciones guardadas")

with t_telegram:
    with ui.sesion() as s:
        bot = notificaciones.bot(s)
        mi_chat = notificaciones.chat(s, ui.uid())
        conectados = notificaciones.conectados(s)
        link = notificaciones.link_conexion(s, ui.uid()) if bot else ""
    st.markdown("Te llegan al celular el **resumen del día a las 8 de la mañana** y **avisos en el momento**: pedido "
                "nuevo, encargo que llegó, producto que se agota y recordatorio que te dejó tu socio.")

    st.markdown("#### 1. El bot del vivero")
    if bot:
        st.success(f"Bot conectado: **@{bot}**", icon="🤖")
    with st.expander("Cómo crear el bot (lo hace uno de los dos, una sola vez)", expanded=not bot):
        st.markdown(
            "1. En Telegram buscá **@BotFather** (tiene tilde azul) y tocá **Iniciar**.\n"
            "2. Mandale `/newbot`.\n"
            "3. Te pide un nombre: por ejemplo *Vivero Malén*.\n"
            "4. Te pide un usuario que termine en *bot*: por ejemplo *vivero_malen_bot*.\n"
            "5. Te contesta con un **token** (una línea larga con números, letras y dos puntos). Copialo y pegalo acá.")
        with st.form("telegram_token", clear_on_submit=True):
            token = st.text_input("Token del bot", type="password")
            if st.form_submit_button("Guardar", type="primary"):
                ui.ejecutar(notificaciones.configurar_bot, token, ui.url_app(), ok="Bot conectado")

    if bot:
        st.markdown("#### 2. Tu Telegram (cada uno con su usuario)")
        if mi_chat:
            st.success("Los avisos te llegan a tu Telegram.", icon="✅")
            c = st.columns(3)
            if c[0].button("Mandarme una prueba", icon="🔔", width="stretch"):
                if ui.ejecutar(notificaciones.enviar_prueba, ui.uid(), recargar=False):
                    st.toast("Mensaje enviado: fijate en Telegram", icon="📲")
            if c[1].button("Mandarme el resumen de hoy", icon="📋", width="stretch"):
                if ui.ejecutar(notificaciones.enviar_resumen, ui.uid(), recargar=False):
                    st.toast("Resumen enviado: fijate en Telegram", icon="📲")
            if c[2].button("Desconectar", width="stretch"):
                ui.ejecutar(notificaciones.desconectar, ui.uid(), ok="Telegram desconectado")
        else:
            st.markdown("Tocá el botón: se abre el bot en Telegram. Ahí tocá **Iniciar** y después volvé acá.")
            c = st.columns(2)
            c[0].link_button("Abrir el bot en Telegram", link, icon="📲", type="primary", width="stretch")
            if c[1].button("Ya toqué Iniciar", width="stretch"):
                conectado = ui.ejecutar(notificaciones.confirmar_conexion, ui.uid(), recargar=False)
                if conectado:
                    ui.flash("¡Listo! Te llegó un mensaje de bienvenida a Telegram")
                    st.rerun()
                elif conectado is not None:
                    st.warning("Todavía no veo tu mensaje. Tocá **Iniciar** en el bot (o mandale cualquier cosa "
                               "después de abrir el link) y probá de nuevo.")
        st.caption("Reciben avisos: " + (", ".join(n for i, n, _, _ in usuarios if i in conectados) or "nadie todavía"))
        st.markdown("#### 3. Resumen de las 8 de la mañana")
        st.markdown("Lo manda GitHub todos los días, aunque nadie abra la app. Necesita la misma dirección de la base "
                    "que pusiste en Streamlit (una sola vez):\n\n"
                    "1. Entrá a [este link de tu repositorio](https://github.com/luchocordoba3/finanzas.beta/settings/secrets/actions/new).\n"
                    "2. En **Name** poné `DATABASE_URL`.\n"
                    "3. En **Secret** pegá la dirección de Neon (la que empieza con `postgresql://`, sin comillas).\n"
                    "4. Tocá **Add secret**.")

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
    if db.database_url().startswith("sqlite"):
        st.warning("Base de datos **local**: los datos están solo en el archivo `vivero.db` de esta computadora.",
                   icon="💻")
    else:
        st.success("Base de datos **en la nube** (Postgres): los datos quedan guardados aunque la app se reinicie.",
                   icon="☁️")
    st.markdown("Descargá todos los datos en un Excel (una hoja por tabla). Conviene hacerlo una vez por semana.")
    if st.button("Preparar copia de seguridad", icon="🗄️"):
        with ui.sesion() as s:
            st.session_state["_backup"] = documentos.backup_excel(s)
    if "_backup" in st.session_state:
        from core.tiempo import hoy
        st.download_button("Descargar Excel", st.session_state["_backup"], f"vivero_backup_{hoy():%Y%m%d}.xlsx",
                           icon="📥", type="primary")
