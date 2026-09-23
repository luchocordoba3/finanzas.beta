import altair as alt
import streamlit as st

from core import graficos, ui
from core.services import config, estadisticas, stock

st.title("🌿 Estadísticas de plantas")
desde, hasta = ui.selector_periodo("est_plantas", "Últimos 90 días")

with ui.sesion() as s:
    it = estadisticas.items_df(s, desde, hasta)
    productos = stock.tabla_productos(s)
    perdidas = estadisticas.mermas(s, desde, hasta)
    rot = estadisticas.rotacion(s, productos, it, desde, hasta)
    temporadas = estadisticas.estacionalidad(s)
    dias_sin_venta = config.entero(s, "dias_sin_venta")
    prod = estadisticas.produccion(s) if config.produccion_activa(s) else None

it = it[it["producto_id"].notna()]  # solo lo que está en el catálogo (sin servicios)
if not st.toggle("Incluir insumos y accesorios (tierra, macetas…)", key="est_insumos"):
    it = it[it["tipo_categoria"] != "insumo"]
valor = estadisticas.valor_stock(productos)
costo_vendido = it["costo"].sum()
m = st.columns(4)
m[0].metric("Unidades vendidas", ui.cant(it["cantidad"].sum()), border=True)
m[1].metric("Stock valorizado a costo", ui.pesos(valor["costo"], 0), f"{ui.pesos(valor['venta'], 0)} a precio de venta",
            delta_color="off", delta_arrow="off", border=True)
m[2].metric("Pérdidas del período", ui.pesos(perdidas["valor"].sum(), 0), f"{ui.cant(perdidas['unidades'].sum())} unidades",
            delta_color="off", delta_arrow="off", border=True)
m[3].metric("Pérdidas sobre lo vendido", f"{perdidas['valor'].sum() / costo_vendido * 100:.1f}%".replace(".", ",") if costo_vendido else "—",
            help="Costo de lo que se perdió dividido el costo de lo que se vendió.", border=True)

pestanias = ["Más vendidas", "Rotación y stock parado", "Pérdidas", "Temporadas"] + (["Producción propia"] if prod is not None else [])
tabs = st.tabs(pestanias)

with tabs[0]:
    c = st.columns(2)
    agrupar = c[0].segmented_control("Agrupar por", ["planta", "producto", "categoria"], default="planta", key="rk_por",
                                     format_func={"planta": "Planta", "producto": "Presentación", "categoria": "Categoría"}.get) or "planta"
    medida = c[1].segmented_control("Medir por", ["importe", "unidades", "margen"], default="importe", key="rk_medida",
                                    format_func={"importe": "Facturación", "unidades": "Unidades", "margen": "Margen"}.get) or "importe"
    ranking = estadisticas.ranking(it, agrupar)
    titulo = {"importe": "Facturación", "unidades": "Unidades", "margen": "Margen"}[medida]
    graficos.barras_h(ranking, agrupar, medida, titulo, formato=",.0f" if medida == "unidades" else graficos.PESOS)
    st.dataframe(ranking, hide_index=True, column_config={
        agrupar: agrupar.capitalize(), "unidades": ui.col_cant("Unidades"), "importe": ui.col_pesos("Facturación ($)"),
        "margen": ui.col_pesos("Margen ($)"), "margen_pct": st.column_config.NumberColumn("Margen %", format="%.0f%%")})

with tabs[1]:
    parado = rot[rot["dias_sin_venta"].isna() | (rot["dias_sin_venta"] >= dias_sin_venta)].sort_values("valor_costo", ascending=False)
    st.markdown(f"**Stock parado**: sin ventas en {dias_sin_venta} días o más · {len(parado)} productos · "
                f"{ui.pesos_md(parado['valor_costo'].sum())} inmovilizados a costo")
    st.dataframe(parado[["producto", "categoria", "stock", "valor_costo", "ultima_venta", "dias_sin_venta"]], hide_index=True,
                 column_config={"producto": "Producto", "categoria": "Categoría", "stock": ui.col_cant("Stock"),
                                "valor_costo": ui.col_pesos("Valor a costo ($)"), "ultima_venta": ui.col_fecha("Última venta"),
                                "dias_sin_venta": "Días sin vender"})
    st.markdown("**¿Para cuántos días alcanza el stock?** (al ritmo de venta del período) — lo que se acaba primero, arriba")
    cobertura = rot[rot["cobertura_dias"].notna()].sort_values("cobertura_dias")
    st.dataframe(cobertura[["producto", "stock", "vendidas", "cobertura_dias"]], hide_index=True,
                 column_config={"producto": "Producto", "stock": ui.col_cant("Stock"), "vendidas": ui.col_cant("Vendidas"),
                                "cobertura_dias": st.column_config.NumberColumn("Alcanza para (días)", format="%.0f")})

with tabs[2]:
    if perdidas.empty:
        st.success("No se registraron pérdidas en este período.")
    else:
        c = st.columns(2)
        with c[0]:
            st.markdown("**Por motivo**")
            graficos.barras_h(estadisticas.por(perdidas, "motivo", "valor"), "motivo", "valor", "Pérdida a costo")
        with c[1]:
            st.markdown("**Por planta**")
            graficos.barras_h(perdidas.groupby("planta", as_index=False).agg(valor=("valor", "sum"), unidades=("unidades", "sum")),
                              "planta", "valor", "Pérdida a costo", top=10,
                              extra_tooltip=[alt.Tooltip("unidades:Q", title="Unidades", format=",.0f")])
        st.dataframe(perdidas.sort_values("fecha", ascending=False)[["fecha", "producto", "motivo", "unidades", "valor"]],
                     hide_index=True, column_config={"fecha": ui.col_fecha_hora("Fecha"), "producto": "Producto",
                                                     "motivo": "Motivo", "unidades": ui.col_cant("Unidades"),
                                                     "valor": ui.col_pesos("Valor a costo ($)")})

with tabs[3]:
    st.markdown("**Qué se vende en cada mes** (unidades de los últimos 2 años, las 15 plantas más vendidas). "
                "Sirve para planificar las compras antes de cada temporada.")
    graficos.calor(temporadas, "mes_nombre", "planta", "unidades", "Unidades", orden_x=estadisticas.MESES)

if prod is not None:
    with tabs[4]:
        if prod.empty:
            st.caption("Todavía no hay lotes de producción.")
        else:
            resumen = (prod.groupby(["planta", "metodo"], as_index=False)
                       .agg(lotes=("id", "count"), iniciales=("cantidad_inicial", "sum"), logradas=("a_stock", "sum"),
                            perdidas=("perdidas", "sum"), dias=("dias_a_stock", "mean"), costo=("costo_total", "sum")))
            resumen["exito_pct"] = resumen["logradas"] / resumen["iniciales"] * 100
            resumen["costo_por_planta"] = (resumen["costo"] / resumen["logradas"]).where(resumen["logradas"] > 0)
            st.dataframe(resumen[["planta", "metodo", "lotes", "iniciales", "logradas", "exito_pct", "dias", "costo_por_planta"]],
                         hide_index=True, column_config={
                             "planta": "Planta", "metodo": "Método", "lotes": "Lotes", "iniciales": ui.col_cant("Iniciadas"),
                             "logradas": ui.col_cant("Pasaron a venta"),
                             "exito_pct": st.column_config.NumberColumn("Éxito", format="%.0f%%"),
                             "dias": st.column_config.NumberColumn("Días hasta la venta", format="%.0f"),
                             "costo_por_planta": ui.col_pesos("Costo por planta lograda ($)")})
