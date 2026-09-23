import streamlit as st

from core import ui
from core.constantes import CUENTA_CORRIENTE
from core.services import clientes, config, stock, ventas

st.title("🛒 Vender")
ui.banner_ultima_venta()

with ui.sesion() as s:
    productos = stock.tabla_productos(s)
    df_clientes = clientes.tabla(s)
    medios = config.medios_pago(s)

if productos.empty:
    st.info("Todavía no hay productos cargados. Empezá por **Catálogo y precios**.")
    st.stop()

items = ui.editor_items("carrito", productos)
if not items:
    st.caption("Buscá un producto y tocá **Agregar**. Podés cambiar cantidades y precios en la lista.")
    st.stop()

st.divider()
subtotal = sum(i["cantidad"] * i["precio"] for i in items)
izq, der = st.columns(2, gap="large")
with izq:
    cliente_id = ui.selector_cliente(df_clientes, "venta_cliente")
    medio = st.pills("Medio de pago", medios, default=medios[0] if medios else None, key="venta_medio")
    notas = st.text_input("Notas (opcional)", key="venta_notas")
with der:
    tipo = st.segmented_control("Descuento en", ["%", "$"], default="%", key="venta_tipo_desc")
    valor = st.number_input("Descuento", min_value=0.0, step=5.0 if tipo == "%" else 100.0, key="venta_desc")
    descuento = round(subtotal * min(valor, 100) / 100, 2) if tipo == "%" else min(valor, subtotal)
    st.metric("Total a cobrar", ui.pesos(subtotal - descuento),
              f"{ui.pesos(descuento)} de descuento" if descuento else None, delta_color="off", delta_arrow="off")
    if medio == CUENTA_CORRIENTE and cliente_id:
        with ui.sesion() as s:
            st.caption(f"Saldo actual de la cuenta: {ui.pesos(clientes.saldo(s, cliente_id))}")
    if st.button("Confirmar venta", type="primary", icon="✅", width="stretch"):
        v = ui.ejecutar(ventas.crear_venta, items, medio, ui.uid(), cliente_id, descuento, notas, recargar=False)
        if v:
            ui.vaciar_items("carrito")
            for k in ("venta_cliente", "venta_notas", "venta_desc"):
                st.session_state.pop(k, None)
            st.session_state["ultima_venta"] = v.id
            st.rerun()
    if st.button("Vaciar", icon="🗑️", width="stretch"):
        ui.vaciar_items("carrito")
        st.rerun()

with st.expander("Ventas de hoy"):
    from core.tiempo import hoy
    with ui.sesion() as s:
        hoy_df = ventas.tabla_ventas(s, hoy(), hoy())
    if hoy_df.empty:
        st.caption("Todavía no hubo ventas hoy.")
    else:
        st.dataframe(hoy_df[["id", "fecha", "cliente", "detalle", "total", "medio_pago", "estado", "usuario"]],
                     hide_index=True, column_config={"id": "N°", "fecha": ui.col_fecha_hora("Hora"),
                                                     "total": ui.col_pesos("Total ($)"), "medio_pago": "Pago"})
        anular = st.selectbox("Anular una venta (devuelve el stock)", hoy_df.loc[hoy_df["estado"] == "confirmada", "id"],
                              index=None, placeholder="N° de venta", key="anular_id")
        if anular and st.button(f"Anular venta #{anular}", icon="↩️"):
            ui.ejecutar(ventas.anular_venta, int(anular), ui.uid(), ok=f"Venta #{anular} anulada")
