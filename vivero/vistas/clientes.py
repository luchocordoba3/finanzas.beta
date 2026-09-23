import streamlit as st

from core import ui
from core.constantes import ESTADOS_PEDIDO, TIPOS_CLIENTE
from core.models import Cliente
from core.services import clientes, config, importar, pedidos, ventas

st.title("👥 Clientes")


def formulario(key: str, datos: dict | None = None) -> dict | None:
    datos = datos or {}
    with st.form(key, clear_on_submit=not datos):
        c = st.columns(2)
        nuevo = {
            "nombre": c[0].text_input("Nombre *", datos.get("nombre", "")),
            "telefono": c[1].text_input("Teléfono / WhatsApp", datos.get("telefono", "")),
            "email": c[0].text_input("Email", datos.get("email", "")),
            "tipo": c[1].selectbox("Tipo de cliente", TIPOS_CLIENTE,
                                   index=TIPOS_CLIENTE.index(datos["tipo"]) if datos.get("tipo") in TIPOS_CLIENTE else 0),
            "direccion": c[0].text_input("Dirección", datos.get("direccion", "")),
            "localidad": c[1].text_input("Localidad", datos.get("localidad", "")),
            "cuit_dni": c[0].text_input("CUIT / DNI", datos.get("cuit_dni", "")),
            "notas": st.text_area("Notas (gustos, preferencias, datos útiles)", datos.get("notas", ""), height=80),
        }
        if datos:
            nuevo["activo"] = st.checkbox("Cliente activo", datos.get("activo", True))
        return nuevo if st.form_submit_button("Guardar", type="primary", icon="💾") else None


def ficha(cliente_id: int) -> None:
    with ui.sesion() as s:
        c = s.get(Cliente, cliente_id)
        datos = {k: getattr(c, k) for k in clientes.CAMPOS}
        saldo = clientes.saldo(s, cliente_id)
        historial = ventas.tabla_ventas(s, cliente_id=cliente_id)
        cobros = clientes.cobros(s, cliente_id)
        peds = pedidos.tabla(s, cliente_id=cliente_id)
        medios = [m for m in config.medios_pago(s) if m != "Cuenta corriente"]
    confirmadas = historial[historial["estado"] == "confirmada"]
    st.subheader(f"{datos['nombre']}")
    st.caption(" · ".join(x for x in (datos["tipo"], datos["telefono"], datos["email"], datos["localidad"]) if x))
    m = st.columns(4)
    m[0].metric("Total comprado", ui.pesos(confirmadas["total"].sum()), border=True)
    m[1].metric("Compras", len(confirmadas), border=True)
    m[2].metric("Última compra", ui.fecha(confirmadas["fecha"].max()) if not confirmadas.empty else "—", border=True)
    m[3].metric("Saldo cuenta corriente", ui.pesos(saldo), border=True)
    t_compras, t_cc, t_pedidos, t_datos = st.tabs(["Compras", "Cuenta corriente", "Pedidos", "Editar datos"])
    with t_compras:
        st.dataframe(historial[["fecha", "detalle", "total", "medio_pago", "estado"]], hide_index=True,
                     column_config={"fecha": ui.col_fecha_hora("Fecha"), "total": ui.col_pesos("Total ($)"),
                                    "medio_pago": "Pago"})
    with t_cc:
        if saldo > 0:
            with st.form(f"cobro_{cliente_id}", clear_on_submit=True):
                c = st.columns(3)
                monto = c[0].number_input("Monto cobrado", min_value=0.0, value=float(saldo), step=1000.0)
                medio = c[1].selectbox("Medio", medios)
                notas = c[2].text_input("Notas")
                if st.form_submit_button("Registrar cobro", type="primary", icon="💵"):
                    ui.ejecutar(clientes.registrar_cobro, cliente_id, monto, medio, ui.uid(), notas, ok="Cobro registrado")
        else:
            st.caption("No tiene deuda.")
        st.markdown("**Cobros**")
        st.dataframe(cobros, hide_index=True, column_config={"fecha": ui.col_fecha_hora("Fecha"),
                                                             "monto": ui.col_pesos("Monto ($)"), "medio_pago": "Medio"})
        st.markdown("**Compras a cuenta**")
        cc = confirmadas[confirmadas["medio_pago"] == "Cuenta corriente"]
        st.dataframe(cc[["fecha", "detalle", "total", "sena_aplicada"]], hide_index=True,
                     column_config={"fecha": ui.col_fecha_hora("Fecha"), "total": ui.col_pesos("Total ($)"),
                                    "sena_aplicada": ui.col_pesos("Seña ($)")})
    with t_pedidos:
        peds["estado"] = peds["estado"].map(ESTADOS_PEDIDO)
        st.dataframe(peds[["id", "fecha_entrega", "detalle", "total", "sena", "estado"]], hide_index=True,
                     column_config={"id": "N°", "fecha_entrega": ui.col_fecha("Entrega"),
                                    "total": ui.col_pesos("Total ($)"), "sena": ui.col_pesos("Seña ($)")})
    with t_datos:
        nuevos = formulario(f"editar_{cliente_id}", datos)
        if nuevos:
            ui.ejecutar(clientes.guardar, nuevos, cliente_id, ok="Datos guardados")


tab_lista, tab_nuevo, tab_importar = st.tabs(["Clientes", "Nuevo cliente", "Importar"])

with tab_lista:
    with ui.sesion() as s:
        df = clientes.tabla(s, solo_activos=False)
    c = st.columns([3, 1.6, 1.2, 1.2], vertical_alignment="bottom")
    buscar = c[0].text_input("Buscar", placeholder="Nombre, teléfono o localidad…")
    tipo = c[1].selectbox("Tipo", ["Todos"] + TIPOS_CLIENTE)
    con_deuda = c[2].toggle("Con deuda")
    inactivos = c[3].toggle("Ver inactivos")
    vista = df if inactivos else df[df["activo"]]
    if buscar:
        texto = vista[["nombre", "telefono", "localidad", "email"]].astype(str).agg(" ".join, axis=1)
        vista = vista[texto.str.contains(buscar, case=False, regex=False)]
    if tipo != "Todos":
        vista = vista[vista["tipo"] == tipo]
    if con_deuda:
        vista = vista[vista["saldo"] > 0]
    st.caption(f"{len(vista)} clientes · deuda total {ui.pesos(vista['saldo'].clip(lower=0).sum())}")
    ev = st.dataframe(vista[["nombre", "telefono", "tipo", "localidad", "compras", "total_comprado", "ultima_compra", "saldo"]],
                      hide_index=True, on_select="rerun", selection_mode="single-row", key="tabla_clientes",
                      column_config={"nombre": "Nombre", "telefono": "Teléfono", "tipo": "Tipo", "localidad": "Localidad",
                                     "compras": "Compras", "total_comprado": ui.col_pesos("Total comprado ($)"),
                                     "ultima_compra": ui.col_fecha("Última compra"), "saldo": ui.col_pesos("Saldo ($)")})
    if ev.selection.rows:
        st.divider()
        ficha(int(vista.iloc[ev.selection.rows[0]]["id"]))
    else:
        st.caption("Tocá un cliente de la tabla para ver su ficha, su cuenta corriente y registrar cobros.")

with tab_nuevo:
    datos = formulario("nuevo_cliente")
    if datos:
        ui.ejecutar(clientes.guardar, datos, ok=f"Cliente {datos['nombre']} creado")

with tab_importar:
    st.markdown("Cargá tu lista de clientes de una vez desde Excel. Columna obligatoria: **nombre**.")
    ui.importador("clientes", importar.COLUMNAS_CLIENTES, importar.EJEMPLO_CLIENTES, importar.importar_clientes)
