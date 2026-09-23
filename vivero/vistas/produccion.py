from datetime import timedelta

import streamlit as st

from core import ui
from core.constantes import ETAPAS_LOTE, METODOS_PRODUCCION
from core.services import catalogo, estadisticas, produccion, stock
from core.tiempo import hoy

st.title("🌾 Producción propia")

with ui.sesion() as s:
    activos = produccion.tabla(s, "activo")
    plantas = {p.id: p.nombre_comun for p in catalogo.plantas(s)}
    productos = stock.tabla_productos(s)
    resultados = estadisticas.produccion(s)

t_curso, t_nuevo, t_result = st.tabs([f"Lotes en curso ({len(activos)})", "Nuevo lote", "Resultados"])

with t_curso:
    if activos.empty:
        st.info("No hay lotes en curso. Cargá uno en **Nuevo lote** cuando siembres o hagas esquejes.")
    for lote in activos.to_dict("records"):
        lid = lote["id"]
        with st.container(border=True):
            listo = f" · listo {ui.fecha(lote['fecha_estimada'])} ({ui.cuando(lote['fecha_estimada'])})" if lote["fecha_estimada"] else ""
            st.markdown(f"**#{lid} · {lote['planta']}** · {lote['metodo']} · :blue-badge[{lote['etapa']}]  \n"
                        f"{ui.cant(lote['cantidad_actual'])} de {ui.cant(lote['cantidad_inicial'])} plantas · "
                        f"desde {ui.fecha(lote['fecha_inicio'])}{listo}"
                        + (f" · 📍 {lote['ubicacion']}" if lote["ubicacion"] else ""))
            a = st.columns(4)
            with a[0].popover("Cambiar etapa", icon="🔄", width="stretch"):
                etapa = st.selectbox("Etapa", ETAPAS_LOTE, index=ETAPAS_LOTE.index(lote["etapa"]) if lote["etapa"] in ETAPAS_LOTE else 0,
                                     key=f"etapa_{lid}")
                if st.button("Guardar", key=f"g_etapa_{lid}", type="primary"):
                    ui.ejecutar(produccion.cambiar_etapa, lid, etapa, ui.uid(), ok="Etapa actualizada")
            with a[1].popover("Registrar pérdida", icon="🥀", width="stretch"):
                n = st.number_input("Plantas perdidas", min_value=0.0, max_value=float(lote["cantidad_actual"]), step=1.0,
                                    format="%g", key=f"perd_{lid}")
                detalle = st.text_input("Motivo", key=f"perd_det_{lid}")
                if st.button("Registrar", key=f"g_perd_{lid}", type="primary"):
                    ui.ejecutar(produccion.registrar_perdida, lid, n, detalle, ui.uid(), ok="Pérdida registrada")
            with a[2].popover("Pasar a stock", icon="🌱", width="stretch"):
                opciones = productos[productos["nombre"] == lote["planta"]]  # presentaciones de esa planta
                opciones = opciones if not opciones.empty else productos
                prod_id = ui.selector_producto(opciones, f"dest_{lid}", "Entra al stock de")
                n = st.number_input("Cantidad lista para vender", min_value=0.0, max_value=float(lote["cantidad_actual"]),
                                    value=float(lote["cantidad_actual"]), step=1.0, format="%g", key=f"stock_{lid}")
                if st.button("Pasar a stock", key=f"g_stock_{lid}", type="primary"):
                    ui.ejecutar(produccion.pasar_a_stock, lid, n, prod_id, ui.uid(), ok="Plantas pasadas al stock")
            with a[3].popover("Terminar lote", icon="🏁", width="stretch"):
                st.caption(f"Las {ui.cant(lote['cantidad_actual'])} plantas que quedan se cuentan como pérdida.")
                if st.button("Terminar", key=f"fin_{lid}"):
                    ui.ejecutar(produccion.terminar, lid, ui.uid(), ok="Lote terminado")
            with st.expander("Historial del lote"):
                with ui.sesion() as s:
                    ev = produccion.eventos(s, lid)
                st.dataframe(ev, hide_index=True, column_config={"fecha": ui.col_fecha_hora("Fecha"), "tipo": "Tipo",
                                                                 "cantidad": ui.col_cant("Cantidad"), "detalle": "Detalle"})

with t_nuevo:
    if not plantas:
        st.info("Primero creá la ficha de la planta en **Catálogo y precios → Fichas de plantas**.")
    with st.form("nuevo_lote", clear_on_submit=True):
        c = st.columns(3)
        planta = c[0].selectbox("Planta", list(plantas), format_func=plantas.get, index=None)
        metodo = c[1].selectbox("Método", METODOS_PRODUCCION)
        cantidad = c[2].number_input("Cantidad inicial", min_value=0.0, step=10.0, format="%g")
        c = st.columns(3)
        inicio = c[0].date_input("Fecha de inicio", hoy(), format="DD/MM/YYYY")
        estimada = c[1].date_input("¿Cuándo estaría lista?", hoy() + timedelta(days=90), format="DD/MM/YYYY")
        costo = c[2].number_input("Costo total ($)", min_value=0.0, step=500.0,
                                  help="Semillas, sustrato, bandejas… Se reparte entre las plantas que pasen a stock.")
        c = st.columns(2)
        ubicacion = c[0].text_input("Ubicación", placeholder="Invernadero 2, mesada 3…")
        notas = c[1].text_input("Notas")
        if st.form_submit_button("Crear lote", type="primary", icon="🌱"):
            ui.ejecutar(produccion.crear_lote, planta, metodo, cantidad, inicio, None, costo, estimada, ubicacion, notas,
                        ui.uid(), ok="Lote creado")

with t_result:
    if resultados.empty:
        st.caption("Todavía no hay lotes.")
    else:
        st.dataframe(resultados[["id", "planta", "metodo", "fecha_inicio", "cantidad_inicial", "a_stock", "perdidas",
                                 "exito_pct", "dias_a_stock", "costo_por_planta", "estado"]], hide_index=True,
                     column_config={"id": "Lote", "planta": "Planta", "metodo": "Método", "fecha_inicio": ui.col_fecha("Inicio"),
                                    "cantidad_inicial": ui.col_cant("Iniciadas"), "a_stock": ui.col_cant("A la venta"),
                                    "perdidas": ui.col_cant("Perdidas"),
                                    "exito_pct": st.column_config.NumberColumn("Éxito", format="%.0f%%"),
                                    "dias_a_stock": "Días hasta la venta",
                                    "costo_por_planta": ui.col_pesos("Costo por planta ($)"), "estado": "Estado"})
