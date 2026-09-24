from datetime import timedelta

import pandas as pd
import streamlit as st

from core import ui
from core.constantes import ESTADOS_PEDIDO, PEDIDO_ABIERTO
from core.services import clientes, config, pedidos, stock, whatsapp
from core.tiempo import hoy

st.title("📦 Pedidos y encargos")
ui.banner_ultima_venta()

with ui.sesion() as s:
    abiertos = pedidos.tabla(s, estados=PEDIDO_ABIERTO)
    faltan = pedidos.faltantes(s)
    productos = stock.tabla_productos(s)
    df_clientes = clientes.tabla(s)
    medios = config.medios_pago(s)
    cfg = config.todos(s)

tab_abiertos, tab_nuevo, tab_historial = st.tabs([f"Para entregar ({len(abiertos)})", "Nuevo pedido", "Historial"])

with tab_abiertos:
    filtro = st.segmented_control("Mostrar", ["Todos", "Atrasados y de hoy", "Próximos 7 días"], default="Todos",
                                  key="filtro_pedidos")
    vista = abiertos
    if filtro == "Atrasados y de hoy":
        vista = abiertos[abiertos["dias"] <= 0]
    elif filtro == "Próximos 7 días":
        vista = abiertos[abiertos["dias"] <= 7]
    if vista.empty:
        st.info("No hay pedidos para entregar.")
    for p in vista.to_dict("records"):
        pid = p["id"]
        falta_p = faltan[faltan["pedido_id"] == pid]
        color = "red" if p["dias"] < 0 else ("orange" if p["dias"] == 0 else "blue")
        estado = ":green-badge[Listo]" if p["estado"] == "listo" else ":gray-badge[Pendiente]"
        with st.container(border=True):
            izq, der = st.columns([5, 2])
            envio = f"Envío a {p['direccion']}" if p["entrega"] == "Envío" else "Retira"
            izq.markdown(f"**#{pid} · {p['cliente']}** {estado}  \n"
                         f":{color}[Entrega {ui.fecha(p['fecha_entrega'])} ({ui.cuando(p['fecha_entrega'])})] · {envio}"
                         + (f" · 📞 {p['telefono']}" if p["telefono"] else ""))
            izq.caption(p["detalle"] + (f" — {p['notas']}" if p["notas"] else ""))
            der.markdown(f"Total **{ui.pesos_md(p['total'])}**  \nSeña {ui.pesos_md(p['sena'])} · resta {ui.pesos_md(p['total'] - p['sena'])}")
            sin_encargar = falta_p[~falta_p["encargado"].astype(bool)]
            if not falta_p.empty:
                txt = ", ".join(f"{f['falta']:g}× {f['descripcion']}" + (" (encargado)" if f["encargado"] else "")
                                for f in falta_p.to_dict("records"))
                st.warning(f"Falta stock: {txt}", icon="🧩")
            a = st.columns(5)
            if p["estado"] == "pendiente" and a[0].button("Marcar listo", key=f"listo_{pid}", icon="📦", width="stretch"):
                ui.ejecutar(pedidos.cambiar_estado, pid, "listo", ok=f"Pedido #{pid} listo")
            with a[1].popover("WhatsApp", icon="💬", width="stretch"):
                if not p["telefono"]:
                    st.caption("El cliente no tiene teléfono cargado. Agregalo en Clientes.")
                else:
                    mensajes = {"listo": "Pedido listo", "recordatorio": "Recordar la entrega",
                                "encargo": "Llegó el encargo", "hola": "Mensaje libre"}
                    tipo = st.selectbox("Mensaje", list(mensajes), format_func=mensajes.get, key=f"wa_tipo_{pid}",
                                        index=0 if p["estado"] == "listo" else 1)
                    nombre = whatsapp.saludo(p["cliente"], p["tipo_cliente"])
                    texto = st.text_area("Texto (lo podés cambiar)", key=f"wa_txt_{pid}_{tipo}", height=150,
                                         value=whatsapp.mensaje(tipo, nombre, cfg["nombre_vivero"], p))
                    url = whatsapp.link(p["telefono"], texto, cfg["codigo_area"])
                    if url:
                        st.link_button("Abrir WhatsApp", url, icon="💬", type="primary", width="stretch")
                    else:
                        st.warning(f"No entiendo el número «{p['telefono']}». Corregilo en Clientes (ej.: 11 5555-1234).")
            with a[2].popover("Entregar", icon="✅", width="stretch"):
                medio = st.selectbox("Medio de pago del saldo", medios, key=f"medio_{pid}")
                desc = st.number_input("Descuento ($)", min_value=0.0, step=100.0, key=f"desc_{pid}")
                if st.button("Confirmar entrega", type="primary", key=f"entregar_{pid}"):
                    v = ui.ejecutar(pedidos.entregar, pid, medio, ui.uid(), desc, recargar=False)
                    if v:
                        st.session_state["ultima_venta"] = v.id
                        ui.flash(f"Pedido #{pid} entregado")
                        st.rerun()
            if not sin_encargar.empty:
                with a[3].popover("Encargar faltantes", icon="🧾", width="stretch"):
                    for f in sin_encargar.to_dict("records"):
                        k = f"{pid}_{f['pedido_item_id']}"
                        st.markdown(f"**{f['falta']:g}× {f['descripcion']}**")
                        prod_id = None
                        if pd.isna(f["producto_id"]):  # ítem libre: todavía no está en el catálogo
                            prod_id = ui.selector_producto(productos, f"enc_prod_{k}", "¿Qué producto del catálogo es?")
                            st.caption("Si no existe, crealo en Catálogo y precios.")
                        if st.button("Agregar a la lista de compras", key=f"enc_{k}"):
                            ui.ejecutar(pedidos.encargar_item, int(f["pedido_item_id"]), ui.uid(), producto_id=prod_id,
                                        cantidad=f["falta"], ok="Agregado a la lista de compras")
            with a[4].popover("Más", icon=":material/more_horiz:", width="stretch"):
                if p["estado"] == "listo" and st.button("Volver a pendiente", key=f"pend_{pid}"):
                    ui.ejecutar(pedidos.cambiar_estado, pid, "pendiente", ok="Pedido vuelto a pendiente")
                seguro = st.checkbox("Sí, cancelar este pedido", key=f"seg_{pid}")
                if st.button("Cancelar pedido", key=f"cancelar_{pid}", disabled=not seguro):
                    ui.ejecutar(pedidos.cambiar_estado, pid, "cancelado", ok=f"Pedido #{pid} cancelado")

with tab_nuevo:
    cliente_id = ui.selector_cliente(df_clientes, "pedido_cliente", permitir_ninguno=False)
    c = st.columns(3)
    fecha_entrega = c[0].date_input("Fecha de entrega", value=hoy() + timedelta(days=1), format="DD/MM/YYYY",
                                    key="pedido_fecha")
    entrega = c[1].segmented_control("Entrega", ["Retira", "Envío"], default="Retira", key="pedido_entrega")
    sena = c[2].number_input("Seña cobrada ($)", min_value=0.0, step=1000.0, key="pedido_sena")
    direccion = st.text_input("Dirección de envío", key="pedido_dir") if entrega == "Envío" else ""
    st.markdown("**Productos** — si algo no está en el catálogo, cargalo como ítem libre y después encargalo.")
    items = ui.editor_items("pedido_items", productos)
    notas = st.text_area("Notas", key="pedido_notas", height=70)
    total = sum(i["cantidad"] * i["precio"] for i in items)
    st.markdown(f"Total del pedido: **{ui.pesos_md(total)}** · resta cobrar {ui.pesos_md(total - sena)}")
    if st.button("Guardar pedido", type="primary", icon="💾", disabled=not items):
        ped = ui.ejecutar(pedidos.crear_pedido, cliente_id, fecha_entrega, items, ui.uid(), entrega or "Retira",
                          direccion, sena, notas, recargar=False)
        if ped:
            ui.vaciar_items("pedido_items")
            for k in ("pedido_cliente", "pedido_sena", "pedido_dir", "pedido_notas"):
                st.session_state.pop(k, None)
            ui.flash(f"Pedido #{ped.id} guardado")
            st.rerun()

with tab_historial:
    desde, hasta = ui.selector_periodo("hist_pedidos", "Últimos 30 días")
    with ui.sesion() as s:
        hist = pedidos.tabla(s, estados=("entregado", "cancelado"), desde=desde, hasta=hasta)
    hist["estado"] = hist["estado"].map(ESTADOS_PEDIDO)
    st.dataframe(hist[["id", "fecha_entrega", "cliente", "detalle", "total", "sena", "estado"]], hide_index=True,
                 column_config={"id": "N°", "fecha_entrega": ui.col_fecha("Entrega"), "total": ui.col_pesos("Total ($)"),
                                "sena": ui.col_pesos("Seña ($)")})
