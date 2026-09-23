import streamlit as st

from core import ui
from core.constantes import MOTIVOS_MERMA, TIPOS_MOVIMIENTO
from core.models import Producto
from core.services import compras, stock

st.title("🌱 Stock")

with ui.sesion() as s:
    df = stock.tabla_productos(s)
    en_curso = compras.productos_en_curso(s)

if df.empty:
    st.info("Todavía no hay productos. Cargalos en **Catálogo y precios** (uno por uno o desde Excel).")
    st.stop()

m = st.columns(4)
m[0].metric("Productos activos", len(df), border=True)
m[1].metric("Unidades en stock", ui.cant(df["stock"].clip(lower=0).sum()), border=True)
m[2].metric("Valor a costo", ui.pesos(df["valor_costo"].sum()), border=True)
m[3].metric("Bajo el mínimo", int(df["bajo_minimo"].sum()), border=True)

c = st.columns([3, 2, 2, 1.3, 1.3], vertical_alignment="bottom")
buscar = c[0].text_input("Buscar", placeholder="Nombre, presentación o código…")
categorias = c[1].multiselect("Categorías", sorted(df["categoria"].unique()), placeholder="Todas")
ubicaciones = c[2].multiselect("Ubicación", sorted(u for u in df["ubicacion"].unique() if u), placeholder="Todas")
solo_bajo = c[3].toggle("Bajo mínimo")
solo_con = c[4].toggle("Con stock")
vista = df
if buscar:
    vista = vista[(vista["producto"] + " " + vista["codigo"]).str.contains(buscar, case=False, regex=False)]
if categorias:
    vista = vista[vista["categoria"].isin(categorias)]
if ubicaciones:
    vista = vista[vista["ubicacion"].isin(ubicaciones)]
if solo_bajo:
    vista = vista[vista["bajo_minimo"]]
if solo_con:
    vista = vista[vista["stock"] > 0]
vista = vista.assign(estado=[("🧾 En compra" if i in en_curso else "⚠️ Reponer") if b else ""
                             for i, b in zip(vista["id"], vista["bajo_minimo"])])
st.dataframe(vista[["producto", "categoria", "ubicacion", "stock", "comprometido", "disponible", "stock_minimo",
                    "estado", "precio", "valor_costo"]], hide_index=True,
             column_config={"producto": "Producto", "categoria": "Categoría", "ubicacion": "Ubicación",
                            "stock": ui.col_cant("Stock"), "comprometido": ui.col_cant("En pedidos"),
                            "disponible": ui.col_cant("Disponible"), "stock_minimo": ui.col_cant("Mínimo"),
                            "estado": "Estado", "precio": ui.col_pesos("Precio ($)"),
                            "valor_costo": ui.col_pesos("Valor a costo ($)")})

st.subheader("Registrar")
t_merma, t_conteo, t_faltante, t_ubic, t_mov = st.tabs(["Pérdida / merma", "Conteo de inventario", "Anotar faltante",
                                                        "Cambiar ubicación", "Movimientos"])
with t_merma:
    st.caption("Plantas que se secaron, se rompieron, se robaron, etc. Descuenta stock y queda en las estadísticas.")
    with st.form("merma", clear_on_submit=True):
        c = st.columns([4, 1.4, 2.2])
        pid = ui.selector_producto(df, "merma_prod", donde=c[0])
        cantidad = c[1].number_input("Cantidad perdida", min_value=0.0, step=1.0, format="%g")
        motivo = c[2].selectbox("Motivo", MOTIVOS_MERMA)
        notas = st.text_input("Detalle (opcional)")
        if st.form_submit_button("Registrar pérdida", type="primary") and pid:
            ui.ejecutar(stock.merma, pid, cantidad, motivo, ui.uid(), notas, ok="Pérdida registrada")
with t_conteo:
    st.caption("Contaste lo que hay físicamente: el sistema ajusta la diferencia.")
    with st.form("conteo", clear_on_submit=True):
        c = st.columns([4, 2])
        pid = ui.selector_producto(df, "conteo_prod", donde=c[0])
        real = c[1].number_input("Cantidad contada", min_value=0.0, step=1.0, format="%g")
        if st.form_submit_button("Ajustar stock", type="primary") and pid:
            ui.ejecutar(stock.ajustar_a, pid, real, ui.uid(), ok="Stock ajustado")
with t_faltante:
    st.caption("Queda anotado en la lista de compras de su proveedor habitual.")
    with st.form("faltante", clear_on_submit=True):
        c = st.columns([4, 2])
        pid = ui.selector_producto(df, "falt_prod", donde=c[0])
        cantidad = c[1].number_input("Cantidad a comprar", min_value=0.0, value=1.0, step=1.0, format="%g")
        if st.form_submit_button("Anotar en la lista de compras", type="primary") and pid:
            ui.ejecutar(compras.agregar_a_lista, pid, cantidad, ui.uid(), ok="Anotado en la lista de compras")
with t_ubic:
    with st.form("ubicacion", clear_on_submit=True):
        c = st.columns([4, 2])
        pid = ui.selector_producto(df, "ubic_prod", donde=c[0])
        opciones = sorted(u for u in df["ubicacion"].unique() if u)
        nueva = c[1].selectbox("Nueva ubicación", opciones, index=None, accept_new_options=True,
                               placeholder="Elegí o escribí una nueva")

        def _mover(s, producto_id, ubicacion):
            s.get(Producto, producto_id).ubicacion = (ubicacion or "").strip()

        if st.form_submit_button("Guardar ubicación", type="primary") and pid:
            ui.ejecutar(_mover, pid, nueva, ok="Ubicación actualizada")
with t_mov:
    c = st.columns([3, 3])
    pid = ui.selector_producto(df, "mov_prod", "Filtrar por producto", donde=c[0])
    tipos = c[1].multiselect("Tipos", list(TIPOS_MOVIMIENTO), format_func=TIPOS_MOVIMIENTO.get, placeholder="Todos")
    with ui.sesion() as s:
        mov = stock.movimientos(s, producto_id=pid, tipos=tipos)
    mov["tipo"] = mov["tipo"].map(TIPOS_MOVIMIENTO)
    st.dataframe(mov[["fecha", "producto", "tipo", "cantidad", "motivo", "notas", "usuario"]], hide_index=True,
                 column_config={"fecha": ui.col_fecha_hora("Fecha"), "producto": "Producto", "tipo": "Movimiento",
                                "cantidad": ui.col_cant("Cantidad"), "motivo": "Motivo", "notas": "Notas",
                                "usuario": "Usuario"})
