import altair as alt
import streamlit as st

from core import graficos, ui
from core.services import clientes, estadisticas, ventas
from core.tiempo import hoy

st.title("📈 Estadísticas de ventas")
desde, hasta = ui.selector_periodo("est_ventas", "Este mes")
ant_desde, ant_hasta = estadisticas.periodo_anterior(desde, hasta)

with ui.sesion() as s:
    v, it = estadisticas.ventas_df(s, desde, hasta), estadisticas.items_df(s, desde, hasta)
    va, ita = estadisticas.ventas_df(s, ant_desde, ant_hasta), estadisticas.items_df(s, ant_desde, ant_hasta)
    comparativo = estadisticas.comparativo_anual(s)
    cli = estadisticas.clientes_resumen(s, v, desde)
    deuda = sum(x for x in clientes.saldos(s).values() if x > 0)
    listado = ventas.tabla_ventas(s, desde, hasta)

k, ka = estadisticas.kpis(v, it), estadisticas.kpis(va, ita)


def variacion(actual: float, anterior: float) -> str | None:
    return f"{(actual - anterior) / anterior * 100:+.0f}% vs. período anterior" if anterior else None


m = st.columns(4)
m[0].metric("Facturación", ui.pesos(k["facturacion"], 0), variacion(k["facturacion"], ka["facturacion"]), border=True)
m[1].metric("Cantidad de ventas", k["ventas"], variacion(k["ventas"], ka["ventas"]), border=True)
m[2].metric("Ticket promedio", ui.pesos(k["ticket"], 0), variacion(k["ticket"], ka["ticket"]), border=True)
m[3].metric("Margen bruto", ui.pesos(k["margen"], 0), f"{k['margen_pct']:.0f}% de lo facturado", delta_color="off",
            delta_arrow="off", border=True)
st.caption(f"Período anterior para comparar: del {ui.fecha(ant_desde)} al {ui.fecha(ant_hasta)}. "
           "El margen usa el costo promedio de cada producto al momento de venderlo.")

t_evol, t_mix, t_cli, t_lista = st.tabs(["Evolución", "Cómo se vende", "Clientes", "Listado de ventas"])

with t_evol:
    dias = (hasta - desde).days + 1
    freq = "D" if dias <= 45 else ("W" if dias <= 200 else "M")
    st.markdown(f"**Facturación por {({'D': 'día', 'W': 'semana', 'M': 'mes'})[freq]}**")
    graficos.barras_tiempo(estadisticas.serie(v, freq, desde, hasta), "periodo", "facturacion", "Facturación", freq)
    st.markdown(f"**{hoy().year} contra {hoy().year - 1}, mes a mes**")
    graficos.comparativo_anual(comparativo, str(hoy().year))

with t_mix:
    c = st.columns(2)
    with c[0]:
        st.markdown("**Por medio de pago**")
        graficos.barras_h(estadisticas.por(v, "medio_pago"), "medio_pago", "total", "Facturación")
    with c[1]:
        st.markdown("**Por categoría**")
        graficos.barras_h(estadisticas.por(it, "categoria", "importe"), "categoria", "importe", "Facturación")
    c = st.columns(2)
    with c[0]:
        st.markdown("**Por tipo de cliente**")
        graficos.barras_h(estadisticas.por(v, "tipo_cliente"), "tipo_cliente", "total", "Facturación")
    with c[1]:
        st.markdown("**Por quién vendió**")
        graficos.barras_h(estadisticas.por(v, "usuario"), "usuario", "total", "Facturación")
    st.markdown("**¿Qué días y a qué hora se vende más?** (cantidad de ventas)")
    graficos.calor(estadisticas.dia_hora(v), "hora", "dia", "ventas", "Ventas", orden_y=estadisticas.DIAS_SEMANA)

with t_cli:
    c = st.columns(4)
    c[0].metric("Clientes que compraron", cli["nuevos"] + cli["recurrentes"], border=True)
    c[1].metric("Nuevos", cli["nuevos"], border=True)
    c[2].metric("Ventas sin cliente cargado", cli["sin_cliente"], border=True)
    c[3].metric("Deuda total en cuentas corrientes", ui.pesos(deuda), border=True)
    st.markdown("**Los que más compraron en el período**")
    graficos.barras_h(cli["top"], "cliente", "total", "Compró", top=10,
                      extra_tooltip=[alt.Tooltip("compras:Q", title="Compras")])
    st.markdown("**Hace más de 90 días que no compran** — buenos para llamar u ofrecerles algo")
    st.dataframe(cli["inactivos"][["cliente", "telefono", "ultima", "dias", "compras", "total_historico"]], hide_index=True,
                 column_config={"cliente": "Cliente", "telefono": "Teléfono", "ultima": ui.col_fecha("Última compra"),
                                "dias": "Días", "compras": "Compras", "total_historico": ui.col_pesos("Compró en total ($)")})

with t_lista:
    st.dataframe(listado[["id", "fecha", "cliente", "detalle", "descuento", "total", "medio_pago", "estado", "usuario"]],
                 hide_index=True, column_config={"id": "N°", "fecha": ui.col_fecha_hora("Fecha"), "cliente": "Cliente",
                                                 "detalle": "Detalle", "descuento": ui.col_pesos("Desc. ($)"),
                                                 "total": ui.col_pesos("Total ($)"), "medio_pago": "Pago",
                                                 "estado": "Estado", "usuario": "Vendió"})
    confirmadas = listado.loc[listado["estado"] == "confirmada", "id"].tolist()
    c = st.columns([2, 3], vertical_alignment="bottom")
    anular = c[0].selectbox("Anular una venta", confirmadas, index=None, placeholder="N° de venta", key="est_anular")
    motivo = c[1].text_input("Motivo", key="est_motivo")
    if anular and st.button(f"Anular venta #{anular} (devuelve el stock)", icon="↩️"):
        ui.ejecutar(ventas.anular_venta, int(anular), ui.uid(), motivo, ok=f"Venta #{anular} anulada")
