import streamlit as st

from core import auth, ui
from core.constantes import REPETICIONES
from core.services import recordatorios
from core.tiempo import hoy

st.title("⏰ Recordatorios y tareas")
ref = hoy()

with ui.sesion() as s:
    usuarios = {u.id: u.nombre for u in auth.usuarios(s)}

with st.expander("Nuevo recordatorio", expanded=True, icon="➕"):
    with st.form("nuevo_recordatorio", clear_on_submit=True):
        c = st.columns([4, 2])
        titulo = c[0].text_input("¿Qué hay que hacer?", placeholder="Ej.: fumigar el sector B, pagar la luz, llamar a Juan")
        fecha = c[1].date_input("¿Cuándo?", ref, format="DD/MM/YYYY")
        c = st.columns(2)
        para = c[0].selectbox("Para", [None, *usuarios], format_func=lambda u: "Los dos" if u is None else usuarios[u])
        repeticion = c[1].selectbox("Se repite", list(REPETICIONES), format_func=REPETICIONES.get)
        descripcion = st.text_input("Detalle (opcional)")
        if st.form_submit_button("Guardar", type="primary", icon="💾"):
            ui.ejecutar(recordatorios.crear, titulo, fecha, ui.uid(), para, repeticion, descripcion,
                        ok="Recordatorio guardado")

solo_mios = st.toggle("Solo los míos (y los de los dos)")
with ui.sesion() as s:
    pendientes = recordatorios.tabla(s, usuario_id=ui.uid() if solo_mios else None)
    hechos = recordatorios.tabla(s, hechos=True, limite=30)

grupos = [("🔴 Atrasados", pendientes[pendientes["fecha"] < ref]), ("📌 Hoy", pendientes[pendientes["fecha"] == ref]),
          ("🗓️ Próximos", pendientes[pendientes["fecha"] > ref])]
if pendientes.empty:
    st.success("No hay recordatorios pendientes.")
for titulo, grupo in grupos:
    if grupo.empty:
        continue
    st.subheader(titulo)
    for r in grupo.to_dict("records"):
        with st.container(border=True):
            c = st.columns([7, 1.4, 1.2], vertical_alignment="center")
            extra = [ui.fecha(r["fecha"]) + f" ({ui.cuando(r['fecha'])})", f"para {r['para']}"]
            if r["repeticion"] != "no":
                extra.append(f"🔁 {REPETICIONES[r['repeticion']].lower()}")
            c[0].markdown(f"**{r['titulo']}**  \n" + " · ".join(extra) + (f"  \n{r['descripcion']}" if r["descripcion"] else ""))
            if c[1].button("Hecho", key=f"hecho_{r['id']}", icon="✔️", width="stretch"):
                ui.ejecutar(recordatorios.completar, r["id"], ok="¡Listo!")
            if c[2].button("Borrar", key=f"borrar_{r['id']}", icon="🗑️", width="stretch"):
                ui.ejecutar(recordatorios.eliminar, r["id"], ok="Recordatorio borrado")

with st.expander("Hechos últimamente"):
    st.dataframe(hechos[["titulo", "fecha", "para", "hecho_en"]], hide_index=True,
                 column_config={"titulo": "Recordatorio", "fecha": ui.col_fecha("Fecha"), "para": "Para",
                                "hecho_en": ui.col_fecha_hora("Hecho el")})
