"""Gráficos Altair con un solo estilo: una serie = azul; dos series = azul y naranja; magnitud = rampa de azules.
Paleta de referencia validada (skill dataviz). Montos con formato argentino."""
import altair as alt
import pandas as pd
import streamlit as st

AZUL, NARANJA = "#2a78d6", "#eb6834"
RAMPA = ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]  # secuencial: poco → mucho

LOCALE = {
    "number": {"decimal": ",", "thousands": ".", "grouping": [3], "currency": ["$ ", ""]},
    "time": {"dateTime": "%A %e de %B de %Y %X", "date": "%d/%m/%Y", "time": "%H:%M:%S", "periods": ["AM", "PM"],
             "days": ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"],
             "shortDays": ["dom", "lun", "mar", "mié", "jue", "vie", "sáb"],
             "months": ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
                        "octubre", "noviembre", "diciembre"],
             "shortMonths": ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]},
}
PESOS = "$,.0f"


def _mostrar(chart: alt.Chart, vacio: bool) -> None:
    if vacio:
        st.caption("Sin datos para este período.")
        return
    st.altair_chart(chart.configure(locale=LOCALE).configure_view(stroke=None), width="stretch")


MESES_CORTOS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def barras_tiempo(df: pd.DataFrame, x: str, y: str, titulo_y: str, freq: str = "D", formato=PESOS) -> None:
    """Una serie en el tiempo: barras finas con extremo redondeado y tooltip. freq: D, W o M."""
    if freq == "M":
        etiquetas = [f"{MESES_CORTOS[t.month - 1]} {t:%y}" for t in df[x]]
        detalle = [f"{MESES_CORTOS[t.month - 1]} {t:%Y}" for t in df[x]]
    else:
        etiquetas = [f"{t:%d/%m}" for t in df[x]]
        detalle = [("Semana del " if freq == "W" else "") + f"{t:%d/%m/%Y}" for t in df[x]]
    df = df.assign(_etiqueta=etiquetas, _detalle=detalle)
    chart = alt.Chart(df).mark_bar(color=AZUL, cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
        x=alt.X("_etiqueta:O", sort=None, title=None, axis=alt.Axis(labelAngle=0 if len(df) <= 14 else -45)),
        y=alt.Y(f"{y}:Q", title=titulo_y, axis=alt.Axis(format=formato)),
        tooltip=[alt.Tooltip("_detalle:N", title="Período"), alt.Tooltip(f"{y}:Q", title=titulo_y, format=formato)],
    ).properties(height=280)
    _mostrar(chart, df.empty or not df[y].any())


def barras_h(df: pd.DataFrame, cat: str, val: str, titulo_val: str, formato=PESOS, top: int = 15,
             extra_tooltip: list | None = None) -> None:
    """Ranking horizontal de una sola serie (el largo es la magnitud; la categoría va en el eje)."""
    df = df.nlargest(top, val) if len(df) > top else df
    chart = alt.Chart(df).mark_bar(color=AZUL, cornerRadiusTopRight=4, cornerRadiusBottomRight=4, height={"band": 0.7}).encode(
        y=alt.Y(f"{cat}:N", sort="-x", title=None, axis=alt.Axis(labelLimit=220)),
        x=alt.X(f"{val}:Q", title=titulo_val, axis=alt.Axis(format=formato)),
        tooltip=[alt.Tooltip(f"{cat}:N", title=" "), alt.Tooltip(f"{val}:Q", title=titulo_val, format=formato),
                 *(extra_tooltip or [])],
    ).properties(height=max(120, 26 * len(df)))
    _mostrar(chart, df.empty)


def comparativo_anual(df: pd.DataFrame, anio_actual: str) -> None:
    """Este año vs el anterior, mes a mes (dos series: azul = este año, naranja = anterior)."""
    anios = sorted(df["anio"].unique())
    orden = [anio_actual] + [a for a in anios if a != anio_actual]
    colores = [AZUL, NARANJA][:len(orden)]
    base = alt.Chart(df).encode(
        x=alt.X("mes_nombre:N", sort=["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"],
                title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("facturacion:Q", title="Facturación", axis=alt.Axis(format=PESOS)),
        color=alt.Color("anio:N", title="Año", scale=alt.Scale(domain=orden, range=colores),
                        legend=alt.Legend(orient="top")),
        tooltip=[alt.Tooltip("anio:N", title="Año"), alt.Tooltip("mes_nombre:N", title="Mes"),
                 alt.Tooltip("facturacion:Q", title="Facturación", format=PESOS)],
    )
    chart = (base.mark_line(strokeWidth=2) + base.mark_point(filled=True, size=64)).properties(height=280)
    _mostrar(chart, df.empty)


def calor(df: pd.DataFrame, x: str, y: str, val: str, titulo_val: str, orden_x=None, orden_y=None,
          formato: str = ",.0f") -> None:
    """Mapa de calor con rampa de un solo tono (más oscuro = más)."""
    chart = alt.Chart(df).mark_rect(cornerRadius=2, stroke="white", strokeWidth=1).encode(
        x=alt.X(f"{x}:O", sort=orden_x, title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y(f"{y}:O", sort=orden_y, title=None, axis=alt.Axis(labelLimit=200)),
        color=alt.Color(f"{val}:Q", title=titulo_val, scale=alt.Scale(range=RAMPA), legend=alt.Legend(orient="top")),
        tooltip=[alt.Tooltip(f"{y}:O", title=" "), alt.Tooltip(f"{x}:O", title="  "),
                 alt.Tooltip(f"{val}:Q", title=titulo_val, format=formato)],
    ).properties(height=max(160, 24 * df[y].nunique()))
    _mostrar(chart, df.empty)
