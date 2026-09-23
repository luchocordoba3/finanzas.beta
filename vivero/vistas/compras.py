from datetime import timedelta

import streamlit as st

from core import ui
from core.constantes import ESTADOS_COMPRA
from core.services import compras, config, proveedores, stock
from core.tiempo import hoy

st.title("🧾 Compras")

with ui.sesion() as s:
    productos = stock.tabla_productos(s)
    provs = {p.id: p.nombre for p in proveedores.listar(s)}
    listas = compras.tabla(s, estados=("lista",))
    abiertas = compras.tabla(s, estados=("pedida", "parcial"))
    recibidas = compras.tabla(s, estados=("parcial", "recibida"))
    it_listas = compras.items(s, listas["id"].tolist())
    it_abiertas = compras.items(s, abiertas["id"].tolist())
    en_curso = compras.productos_en_curso(s)
    medios = [m for m in config.medios_pago(s) if m != "Cuenta corriente"]
    nombre_vivero = config.obtener(s, "nombre_vivero")

reponer = stock.a_reponer(productos)
reponer = reponer[~reponer["id"].isin(en_curso)]
a_pagar = recibidas[~recibidas["pagada"].astype(bool) & (recibidas["total"] > 0)]
t_listas, t_recibir, t_pagos, t_directa, t_hist = st.tabs([
    f"Listas de compras ({len(listas)})", f"Por recibir ({len(abiertas)})", f"Pagos pendientes ({len(a_pagar)})",
    "Compra directa", "Historial"])


def _agregar_sugeridos(s, filas, usuario_id):
    for f in filas:
        compras.agregar_a_lista(s, f["id"], f["sugerido"], usuario_id)


def _guardar_lista(s, filas):
    for f in filas:
        if f["quitar"]:
            compras.quitar_item(s, int(f["id"]))
        else:
            compras.actualizar_item(s, int(f["id"]), float(f["cantidad"] or 0), float(f["costo_unitario"] or 0))


def _recibir_todo(s, compra_id, proveedor_id, usuario_id):
    c = compras.marcar_pedida(s, compra_id, proveedor_id)
    return compras.recibir(s, c.id, {i.id: (i.cantidad, i.costo_unitario) for i in c.items}, usuario_id)


with t_listas:
    st.caption("Lo que hay que comprar, agrupado por proveedor. Lo pueden anotar los dos; cuando se hace el pedido, "
               "se marca como pedida y queda esperando la entrega.")
    if not reponer.empty:
        c = st.columns([4, 2], vertical_alignment="center")
        c[0].info(f"Hay {len(reponer)} productos bajo el mínimo que todavía no están en ninguna lista.")
        if c[1].button("Agregar sugeridos", icon="➕", width="stretch"):
            ui.ejecutar(_agregar_sugeridos, reponer.to_dict("records"), ui.uid(), ok="Sugeridos agregados")
    with st.expander("Anotar un producto", icon="✏️"):
        with st.form("anotar", clear_on_submit=True):
            c = st.columns([4, 1.5, 2.5])
            pid = ui.selector_producto(productos, "anotar_prod", donde=c[0])
            cantidad = c[1].number_input("Cantidad", min_value=0.0, value=1.0, step=1.0, format="%g")
            prov = c[2].selectbox("Proveedor", [None, *provs],
                                  format_func=lambda p: "El habitual del producto" if p is None else provs[p])
            if st.form_submit_button("Anotar", type="primary") and pid:
                ui.ejecutar(compras.agregar_a_lista, pid, cantidad, ui.uid(), prov, ok="Anotado en la lista")
    if listas.empty:
        st.success("Las listas de compras están vacías.")
    for c in listas.to_dict("records"):
        cid = c["id"]
        items = it_listas[it_listas["compra_id"] == cid]
        with st.container(border=True):
            st.markdown(f"**{c['proveedor']}** · {len(items)} productos · estimado {ui.pesos(c['total'])}")
            editado = st.data_editor(
                items[["id", "producto", "cantidad", "costo_unitario"]].assign(quitar=False), key=f"ed_{cid}",
                hide_index=True, disabled=["id", "producto"],
                column_config={"id": None, "producto": "Producto",
                               "cantidad": st.column_config.NumberColumn("Cantidad", min_value=0.01, step=1),
                               "costo_unitario": st.column_config.NumberColumn("Costo unit. ($)", min_value=0, format="localized"),
                               "quitar": st.column_config.CheckboxColumn("Quitar")})
            b = st.columns(4)
            if b[0].button("Guardar cambios", key=f"guardar_{cid}", icon="💾", width="stretch"):
                ui.ejecutar(_guardar_lista, editado.to_dict("records"), ok="Lista actualizada")
            with b[1].popover("Texto para el proveedor", icon="💬", width="stretch"):
                lineas = "\n".join(f"- {f['cantidad']:g} × {f['producto']}" for f in items.to_dict("records"))
                st.caption("Copialo y mandalo por WhatsApp o mail:")
                st.code(f"Hola! Te paso el pedido de {nombre_vivero}:\n{lineas}\nGracias!", language=None)
            with b[2].popover("Marcar como pedida", icon="📨", width="stretch"):
                ids = list(provs)
                prov = st.selectbox("Proveedor", ids, format_func=provs.get, key=f"prov_{cid}",
                                    index=ids.index(c["proveedor_id"]) if c["proveedor_id"] in provs else None)
                llega = st.date_input("¿Cuándo llega?", hoy() + timedelta(days=3), format="DD/MM/YYYY", key=f"llega_{cid}")
                if st.button("Confirmar pedido", type="primary", key=f"pedir_{cid}"):
                    ui.ejecutar(compras.marcar_pedida, cid, prov, llega, ok="Compra marcada como pedida")
            with b[3].popover("Ya la compré", icon="📦", width="stretch"):
                st.caption("Para compras en el momento (mercado, corralón): suma todo al stock ahora.")
                ids = list(provs)
                prov = st.selectbox("Proveedor", ids, format_func=provs.get, key=f"provya_{cid}",
                                    index=ids.index(c["proveedor_id"]) if c["proveedor_id"] in provs else None)
                if st.button("Recibir todo", type="primary", key=f"ya_{cid}"):
                    ui.ejecutar(_recibir_todo, cid, prov, ui.uid(), ok="Compra recibida: el stock ya se actualizó")

with t_recibir:
    if abiertas.empty:
        st.success("No hay compras esperando entrega.")
    for c in abiertas.to_dict("records"):
        cid = c["id"]
        items = it_abiertas[it_abiertas["compra_id"] == cid]
        with st.container(border=True):
            llega = f"llega {ui.fecha(c['fecha_estimada'])} ({ui.cuando(c['fecha_estimada'])})" if c["fecha_estimada"] else "sin fecha"
            parcial = " :orange-badge[Recibida en parte]" if c["estado"] == "parcial" else ""
            st.markdown(f"**#{cid} · {c['proveedor']}**{parcial} · pedida {ui.fecha(c['fecha_pedido'])} · {llega}")
            editado = st.data_editor(
                items[["id", "producto", "cantidad", "cantidad_recibida", "costo_unitario"]].assign(recibo=items["pendiente"]),
                key=f"rec_{cid}", hide_index=True, disabled=["id", "producto", "cantidad", "cantidad_recibida"],
                column_config={"id": None, "producto": "Producto", "cantidad": ui.col_cant("Pedido"),
                               "cantidad_recibida": ui.col_cant("Ya llegó"),
                               "recibo": st.column_config.NumberColumn("Llega ahora", min_value=0, step=1),
                               "costo_unitario": st.column_config.NumberColumn("Costo unit. ($)", min_value=0, format="localized")})
            b = st.columns(3, vertical_alignment="bottom")
            venc = b[0].date_input("Vence el pago (opcional)", value=None, format="DD/MM/YYYY", key=f"venc_{cid}")
            if b[1].button("Registrar recepción", type="primary", key=f"recibir_{cid}", icon="📦", width="stretch"):
                recepciones = {int(f["id"]): (float(f["recibo"] or 0), float(f["costo_unitario"] or 0))
                               for f in editado.to_dict("records")}
                ui.ejecutar(compras.recibir, cid, recepciones, ui.uid(), None, venc,
                            ok="Recepción registrada: el stock ya se actualizó")
            if b[2].button("No llega más: cerrar", key=f"cerrar_{cid}", width="stretch"):
                ui.ejecutar(compras.cerrar, cid, ok="Compra cerrada")

with t_pagos:
    if a_pagar.empty:
        st.success("No hay pagos pendientes a proveedores.")
    else:
        vista = a_pagar.sort_values("fecha_venc_pago", na_position="last")
        st.metric("Total a pagar", ui.pesos(vista["total"].sum()))
        st.dataframe(vista[["id", "proveedor", "fecha_recepcion", "fecha_venc_pago", "total", "detalle"]], hide_index=True,
                     column_config={"id": "N°", "proveedor": "Proveedor", "fecha_recepcion": ui.col_fecha("Recibida"),
                                    "fecha_venc_pago": ui.col_fecha("Vence"), "total": ui.col_pesos("Total ($)"),
                                    "detalle": "Detalle"})
        with st.form("pago"):
            c = st.columns(3)
            etiquetas = {r.id: f"#{r.id} · {r.proveedor} · {ui.pesos(r.total)}" for r in vista.itertuples()}
            cid = c[0].selectbox("Compra", list(etiquetas), format_func=etiquetas.get)
            medio = c[1].selectbox("Medio de pago", medios)
            fecha = c[2].date_input("Fecha de pago", hoy(), format="DD/MM/YYYY")
            if st.form_submit_button("Registrar pago", type="primary", icon="💸"):
                ui.ejecutar(compras.registrar_pago, cid, medio, fecha, ok="Pago registrado")

with t_directa:
    st.caption("Para cargar de una una compra completa (por ejemplo, la factura de un proveedor).")
    prov = st.selectbox("Proveedor", list(provs), format_func=provs.get, index=None, key="cd_prov",
                        placeholder="Elegí el proveedor (si no está, crealo en Proveedores)")
    items = ui.editor_items("compra_items", productos, precio="costo_ultimo", etiqueta_precio="Costo", libre=False,
                            avisar_stock=False)
    c = st.columns(3)
    recibida = c[0].toggle("Ya la recibí (suma al stock)", value=True, key="cd_recibida")
    llega = c[1].date_input("Llega el", hoy() + timedelta(days=3), format="DD/MM/YYYY", key="cd_llega", disabled=recibida)
    venc = c[2].date_input("Vence el pago (opcional)", value=None, format="DD/MM/YYYY", key="cd_venc")
    notas = st.text_input("Notas", key="cd_notas")
    st.markdown(f"Total: **{ui.pesos(sum(i['cantidad'] * i['precio'] for i in items))}**")
    if st.button("Guardar compra", type="primary", icon="💾", disabled=not items):
        compra = ui.ejecutar(compras.crear_compra, prov, items, ui.uid(), None if recibida else llega, venc, notas,
                             recibida, recargar=False)
        if compra:
            ui.vaciar_items("compra_items")
            for k in ("cd_prov", "cd_notas", "cd_venc"):
                st.session_state.pop(k, None)
            ui.flash(f"Compra #{compra.id} guardada")
            st.rerun()

with t_hist:
    prov = st.selectbox("Proveedor", [None, *provs], format_func=lambda p: "Todos" if p is None else provs[p], key="h_prov")
    with ui.sesion() as s:
        hist = compras.tabla(s, estados=("parcial", "recibida", "cancelada"), proveedor_id=prov)
    hist["estado"] = hist["estado"].map(ESTADOS_COMPRA)
    st.dataframe(hist[["id", "proveedor", "estado", "fecha_pedido", "fecha_recepcion", "total", "pagada", "detalle"]],
                 hide_index=True, column_config={"id": "N°", "proveedor": "Proveedor", "estado": "Estado",
                                                 "fecha_pedido": ui.col_fecha("Pedida"),
                                                 "fecha_recepcion": ui.col_fecha("Recibida"),
                                                 "total": ui.col_pesos("Total ($)"), "pagada": "Pagada",
                                                 "detalle": "Detalle"})
