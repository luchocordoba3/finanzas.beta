from urllib.parse import quote

import streamlit as st

from core import auth, db, ui
from core.models import Usuario
from core.services import config, documentos, notificaciones, push

st.title("⚙️ Configuración")

with ui.sesion() as s:
    cfg = config.todos(s)
    usuarios = [(u.id, u.nombre, u.usuario, u.activo) for u in auth.usuarios(s, solo_activos=False)]

t_vivero, t_param, t_notif, t_usuarios, t_backup = st.tabs(
    ["Datos del vivero", "Avisos y opciones", "Notificaciones", "Usuarios", "Copia de seguridad"])

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

with t_notif:
    with ui.sesion() as s:
        publica = push.clave_publica(s)  # se genera sola la primera vez
        if ui.url_app().startswith("https://") and cfg.get("url_app") != ui.url_app():
            config.guardar(s, {"url_app": ui.url_app()})
        mis_equipos = [(d.id, d.nombre, d.creado_en) for d in push.dispositivos(s, ui.uid())]
        con_push = {uid: len(lista) for uid, lista in push.por_usuario(s).items()}
        bot = notificaciones.bot(s)
        mi_chat = notificaciones.chat(s, ui.uid())
        conectados = notificaciones.conectados(s)
        link = notificaciones.link_conexion(s, ui.uid()) if bot else ""
    url_app = ui.url_app() or cfg.get("url_app", "")
    activar = f"{cfg['url_avisos']}?app={quote(url_app, safe='')}&k={publica}&n={quote(cfg['nombre_vivero'], safe='')}"

    st.markdown("#### 🔔 Notificaciones en el celular y la PC")
    st.markdown("Aparecen en la pantalla como las de cualquier app, con el nombre y el ícono del vivero, aunque el "
                "sistema esté cerrado: **pedido nuevo, encargo que llegó, producto que se agota, recordatorio que te "
                "dejaron** y un **resumen a las 8 de la mañana**. Se activan una vez en cada dispositivo de cada socio.")
    if not ui.pagina_publicada(cfg["url_avisos"]):
        st.warning("La página de activación todavía no está publicada. En GitHub: **Settings → Pages** → *Source*: "
                   "**Deploy from a branch** → *Branch*: **main** y carpeta **/docs** → **Save**. Tarda un par de minutos.",
                   icon="⏳")
    st.link_button("Activar en este dispositivo", activar, type="primary", icon="🔔")
    with st.expander("¿Tenés iPhone?"):
        st.markdown("Apple pide instalar la app primero (iPhone con iOS 16.4 o más nuevo):\n"
                    "1. Tocá **Activar en este dispositivo**: se abre la página en Safari.\n"
                    "2. Tocá **Compartir** (el cuadrado con la flecha) → **Agregar a inicio**.\n"
                    "3. Abrí **Vivero** desde el ícono nuevo y tocá **Activar notificaciones**.")
    if mis_equipos:
        st.markdown("**Tus dispositivos**")
        for did, nombre_equipo, creado in mis_equipos:
            c = st.columns([5, 1.4], vertical_alignment="center")
            c[0].markdown(f"📱 {nombre_equipo} · activado el {ui.fecha(creado)}")
            if c[1].button("Quitar", key=f"quitar_disp_{did}", width="stretch"):
                ui.ejecutar(push.quitar, did, ok="Dispositivo quitado")
        if st.button("Mandarme una notificación de prueba", icon="🔔"):
            enviadas = ui.ejecutar(push.probar, ui.uid(), recargar=False)
            if enviadas:
                st.toast(f"Prueba enviada a {enviadas} dispositivo(s)", icon="📲")
    st.caption("Tienen notificaciones: " + (", ".join(f"{n} ({con_push[i]})" for i, n, _, _ in usuarios if i in con_push)
                                            or "nadie todavía"))

    st.markdown("#### ⏰ Resumen de las 8 de la mañana")
    st.markdown("Lo manda GitHub todos los días, aunque nadie abra el sistema. Necesita, una sola vez, la dirección de "
                "la base:\n\n"
                "1. Entrá a [este link de tu repositorio](https://github.com/luchocordoba3/finanzas.beta/settings/secrets/actions/new).\n"
                "2. En **Name** poné `DATABASE_URL`.\n"
                "3. En **Secret** pegá la dirección de Neon (la que empieza con `postgresql://`, sin comillas).\n"
                "4. Tocá **Add secret**.")

    with st.expander("📨 Telegram (opcional, para quien lo use)"):
        if bot:
            st.success(f"Bot conectado: **@{bot}**", icon="🤖")
        else:
            st.markdown(
                "1. En Telegram buscá **@BotFather** (tiene tilde azul) y tocá **Iniciar**.\n"
                "2. Mandale `/newbot`, poné un nombre (por ejemplo *Vivero Malén*) y un usuario que termine en *bot*.\n"
                "3. Te contesta con un **token**: copialo y pegalo acá.")
            with st.form("telegram_token", clear_on_submit=True):
                token = st.text_input("Token del bot", type="password")
                if st.form_submit_button("Guardar", type="primary"):
                    ui.ejecutar(notificaciones.configurar_bot, token, ui.url_app(), ok="Bot conectado")
        if bot and mi_chat:
            st.success("Los avisos también te llegan por Telegram.", icon="✅")
            c = st.columns(3)
            if c[0].button("Mandarme una prueba", icon="🔔", width="stretch", key="tg_prueba"):
                if ui.ejecutar(notificaciones.enviar_prueba, ui.uid(), recargar=False):
                    st.toast("Mensaje enviado: fijate en Telegram", icon="📲")
            if c[1].button("Mandarme el resumen de hoy", icon="📋", width="stretch"):
                if ui.ejecutar(notificaciones.enviar_resumen, ui.uid(), recargar=False):
                    st.toast("Resumen enviado: fijate en Telegram", icon="📲")
            if c[2].button("Desconectar", width="stretch"):
                ui.ejecutar(notificaciones.desconectar, ui.uid(), ok="Telegram desconectado")
        elif bot:
            st.markdown("Tocá el botón: se abre el bot en Telegram. Ahí tocá **Iniciar** y después volvé acá.")
            c = st.columns(2)
            c[0].link_button("Abrir el bot en Telegram", link, icon="📲", width="stretch")
            if c[1].button("Ya toqué Iniciar", width="stretch"):
                conectado = ui.ejecutar(notificaciones.confirmar_conexion, ui.uid(), recargar=False)
                if conectado:
                    ui.flash("¡Listo! Te llegó un mensaje de bienvenida a Telegram")
                    st.rerun()
                elif conectado is not None:
                    st.warning("Todavía no veo tu mensaje. Tocá **Iniciar** en el bot y probá de nuevo.")
        if bot:
            st.caption("Reciben por Telegram: " + (", ".join(n for i, n, _, _ in usuarios if i in conectados) or "nadie todavía"))

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
