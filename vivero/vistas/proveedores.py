import streamlit as st

from core import ui
from core.constantes import ESTADOS_COMPRA
from core.models import Proveedor
from core.services import compras, proveedores, stock

st.title("🚚 Proveedores")


def formulario(key: str, datos: dict | None = None) -> dict | None:
    datos = datos or {}
    with st.form(key, clear_on_submit=not datos):
        c = st.columns(2)
        nuevo = {
            "nombre": c[0].text_input("Nombre *", datos.get("nombre", "")),
            "rubro": c[1].text_input("Rubro", datos.get("rubro", ""), placeholder="Plantas, macetas, tierra…"),
            "contacto": c[0].text_input("Persona de contacto", datos.get("contacto", "")),
            "telefono": c[1].text_input("Teléfono / WhatsApp", datos.get("telefono", "")),
            "email": c[0].text_input("Email", datos.get("email", "")),
            "direccion": c[1].text_input("Dirección", datos.get("direccion", "")),
            "dias_entrega": c[0].text_input("Días de entrega / visita", datos.get("dias_entrega", ""),
                                            placeholder="Ej.: martes y viernes"),
            "condiciones_pago": c[1].text_input("Condiciones de pago", datos.get("condiciones_pago", ""),
                                                placeholder="Ej.: 30 días, contado"),
            "cuit": c[0].text_input("CUIT", datos.get("cuit", "")),
            "notas": st.text_area("Notas", datos.get("notas", ""), height=70),
        }
        if datos:
            nuevo["activo"] = st.checkbox("Proveedor activo", datos.get("activo", True))
        return nuevo if st.form_submit_button("Guardar", type="primary", icon="💾") else None


tab_lista, tab_nuevo = st.tabs(["Proveedores", "Nuevo proveedor"])

with tab_lista:
    with ui.sesion() as s:
        df = proveedores.tabla(s, solo_activos=False)
    c = st.columns([4, 1.3], vertical_alignment="bottom")
    buscar = c[0].text_input("Buscar", placeholder="Nombre, rubro o contacto…")
    inactivos = c[1].toggle("Ver inactivos")
    vista = df if inactivos else df[df["activo"]]
    if buscar:
        texto = vista[["nombre", "rubro", "contacto", "telefono"]].astype(str).agg(" ".join, axis=1)
        vista = vista[texto.str.contains(buscar, case=False, regex=False)]
    ev = st.dataframe(vista[["nombre", "rubro", "contacto", "telefono", "dias_entrega", "total_comprado", "ultima_compra"]],
                      hide_index=True, on_select="rerun", selection_mode="single-row", key="tabla_proveedores",
                      column_config={"nombre": "Nombre", "rubro": "Rubro", "contacto": "Contacto",
                                     "telefono": "Teléfono", "dias_entrega": "Entrega",
                                     "total_comprado": ui.col_pesos("Comprado ($)"),
                                     "ultima_compra": ui.col_fecha("Última compra")})
    if not ev.selection.rows:
        st.caption("Tocá un proveedor para ver sus compras, sus productos y editar sus datos.")
    else:
        pid = int(vista.iloc[ev.selection.rows[0]]["id"])
        with ui.sesion() as s:
            p = s.get(Proveedor, pid)
            datos = {k: getattr(p, k) for k in proveedores.CAMPOS}
            hist = compras.tabla(s, proveedor_id=pid)
            prods = stock.tabla_productos(s)
        prods = prods[prods["proveedor_id"] == pid]
        st.divider()
        st.subheader(datos["nombre"])
        t_compras, t_prod, t_datos = st.tabs(["Compras", "Productos que provee", "Editar datos"])
        with t_compras:
            hist["estado"] = hist["estado"].map(ESTADOS_COMPRA)
            st.dataframe(hist[["id", "estado", "fecha_pedido", "fecha_recepcion", "total", "pagada", "detalle"]],
                         hide_index=True, column_config={"id": "N°", "estado": "Estado", "fecha_pedido": ui.col_fecha("Pedida"),
                                                         "fecha_recepcion": ui.col_fecha("Recibida"),
                                                         "total": ui.col_pesos("Total ($)"), "pagada": "Pagada",
                                                         "detalle": "Detalle"})
        with t_prod:
            st.dataframe(prods[["producto", "stock", "stock_minimo", "costo_ultimo", "precio"]], hide_index=True,
                         column_config={"producto": "Producto", "stock": ui.col_cant("Stock"),
                                        "stock_minimo": ui.col_cant("Mínimo"), "costo_ultimo": ui.col_pesos("Último costo ($)"),
                                        "precio": ui.col_pesos("Precio ($)")})
        with t_datos:
            nuevos = formulario(f"editar_prov_{pid}", datos)
            if nuevos:
                ui.ejecutar(proveedores.guardar, nuevos, pid, ok="Datos guardados")

with tab_nuevo:
    datos = formulario("nuevo_proveedor")
    if datos:
        ui.ejecutar(proveedores.guardar, datos, ok=f"Proveedor {datos['nombre']} creado")
