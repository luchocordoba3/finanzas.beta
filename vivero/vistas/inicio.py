import streamlit as st

from core import ui
from core.services import alertas, compras, estadisticas, pedidos, recordatorios, stock
from core.tiempo import hoy

ICONOS = {"Pedidos atrasados": "🔴", "Pedidos para entregar": "📦", "Faltantes para pedidos": "🧩",
          "Encargos que llegaron": "📬", "Stock bajo mínimo": "📉", "Compras por recibir": "🚚",
          "Pagos a proveedores": "💸", "Cuentas corrientes": "💳", "Recordatorios": "⏰", "Producción": "🌾",
          "Temporada": "🌸"}
PAGINAS = {"pedidos": "vistas/pedidos.py", "compras": "vistas/compras.py", "stock": "vistas/stock.py",
           "clientes": "vistas/clientes.py", "recordatorios": "vistas/recordatorios.py",
           "produccion": "vistas/produccion.py"}
NIVEL = {"urgente": ":red-badge[Urgente]", "atencion": ":orange-badge[Atención]", "info": ":blue-badge[Info]"}

ref = hoy()
st.title(f"Hola, {ui.usuario()['nombre']} 👋")
st.caption(ui.fecha_larga(ref))

with ui.sesion() as s:
    lista = alertas.calcular(s, ui.uid(), ref)
    ventas_hoy = estadisticas.ventas_df(s, ref, ref)
    pedidos_hoy = pedidos.tabla(s, estados=("pendiente", "listo"), desde=ref, hasta=ref)
    en_curso = compras.productos_en_curso(s)
    reponer = stock.a_reponer(stock.tabla_productos(s))
    reponer = reponer[~reponer["id"].isin(en_curso)]

c = st.columns(4)
c[0].metric("Ventas de hoy", ui.pesos(ventas_hoy["total"].sum()), f"{len(ventas_hoy)} ventas", delta_color="off",
            delta_arrow="off", border=True)
c[1].metric("Pedidos para entregar hoy", len(pedidos_hoy), border=True)
c[2].metric("Alertas urgentes", sum(a.nivel == "urgente" for a in lista), border=True)
c[3].metric("Productos para reponer", len(reponer), border=True)

if not lista:
    st.success("Todo en orden: no hay nada pendiente. 🌿")

grupos: dict[str, list] = {}
for a in lista:  # vienen ordenadas por urgencia: los grupos más urgentes quedan arriba
    grupos.setdefault(a.grupo, []).append(a)

for grupo, items in grupos.items():
    abierto = any(a.nivel != "info" for a in items)
    with st.expander(f"{ICONOS.get(grupo, '•')} **{grupo}** ({len(items)})", expanded=abierto):
        for i, a in enumerate(items):
            col_txt, col_accion = st.columns([8, 2], vertical_alignment="center")
            col_txt.markdown(f"{NIVEL[a.nivel]} {a.texto}".replace("$", "\\$"))
            if grupo == "Recordatorios":
                if col_accion.button("Hecho", key=f"rec_{a.ref_id}", icon="✔️", width="stretch"):
                    ui.ejecutar(recordatorios.completar, a.ref_id, ok="Recordatorio completado")
            elif grupo == "Encargos que llegaron":
                if col_accion.button("Ya le avisé", key=f"enc_{a.ref_id}", width="stretch"):
                    ui.ejecutar(pedidos.cambiar_estado, a.ref_id, "listo", ok=f"Pedido #{a.ref_id} listo para entregar")
            elif grupo != "Stock bajo mínimo":
                col_accion.page_link(PAGINAS[a.pagina], label="Ir", icon="➡️", width="stretch")
        if grupo == "Stock bajo mínimo" and not reponer.empty:
            def _agregar(s, filas, usuario_id):
                for f in filas:
                    compras.agregar_a_lista(s, f["id"], f["sugerido"], usuario_id)

            if st.button("Agregar todo a las listas de compras", icon="🧾"):
                ui.ejecutar(_agregar, reponer.to_dict("records"), ui.uid(),
                            ok="Agregado a las listas de compras (en Compras podés ajustar cantidades)")
