import streamlit as st
import json
import os
from datetime import datetime

st.set_page_config(page_title="Respuestas de Marca", layout="wide")

RESPUESTAS_DIR = "respuestas_marca"
ADMIN_PIN = "1234"  # Cambiá este PIN en producción

st.markdown("""
<style>
  .stApp { background: #f5f7fa; }
  .card {
    background: white;
    border-radius: 12px;
    padding: 24px 28px;
    margin-bottom: 20px;
    border: 1px solid #e2e8f0;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
  }
  .card-header { font-size: 18px; font-weight: 800; color: #0d1b2a; margin-bottom: 4px; }
  .card-sub { font-size: 13px; color: #6b7a8d; margin-bottom: 16px; }
  .tag { background: #1b3a5c; color: #fff; font-size: 12px; font-weight: 600; padding: 4px 12px; border-radius: 20px; display: inline-block; margin: 2px; }
  .section-lbl { font-size: 11px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; color: #4a9fd4; margin: 16px 0 6px; }
  .answer { background: #f7fafc; border-left: 3px solid #1b3a5c; border-radius: 6px; padding: 10px 14px; font-size: 14px; color: #2d3748; line-height: 1.6; }
</style>
""", unsafe_allow_html=True)

st.title("📁 Respuestas del Cuestionario de Marca")

if "admin_ok" not in st.session_state:
    st.session_state.admin_ok = False

if not st.session_state.admin_ok:
    st.markdown("Esta sección es privada.")
    pin = st.text_input("PIN de acceso", type="password", max_chars=4)
    if st.button("Acceder"):
        if pin == ADMIN_PIN:
            st.session_state.admin_ok = True
            st.rerun()
        else:
            st.error("PIN incorrecto.")
    st.stop()

# ── Listar archivos ──────────────────────────────────────────────────────────
if not os.path.exists(RESPUESTAS_DIR):
    st.info("Todavía no hay respuestas enviadas.")
    st.stop()

archivos = sorted(
    [f for f in os.listdir(RESPUESTAS_DIR) if f.endswith(".json")],
    reverse=True
)

if not archivos:
    st.info("Todavía no hay respuestas enviadas.")
    st.stop()

st.markdown(f"**{len(archivos)} respuesta(s) recibida(s)**")
st.markdown("---")

for archivo in archivos:
    ruta = os.path.join(RESPUESTAS_DIR, archivo)
    with open(ruta, "r", encoding="utf-8") as f:
        d = json.load(f)

    meta = d.get("meta", {})
    n1   = d.get("01_tu_negocio", {})
    n2   = d.get("02_tus_clientes", {})
    n3   = d.get("03_personalidad", {})
    n4   = d.get("04_referentes", {})
    n5   = d.get("05_visual", {})
    n6   = d.get("06_objetivos", {})

    ts_str = meta.get("timestamp", "")
    try:
        ts_fmt = datetime.fromisoformat(ts_str).strftime("%d/%m/%Y %H:%M")
    except Exception:
        ts_fmt = ts_str

    with st.expander(f"🏢 {meta.get('para', archivo)}  ·  {ts_fmt}", expanded=False):

        col_a, col_b = st.columns(2)

        with col_a:
            st.markdown('<div class="section-lbl">01 — Tu negocio</div>', unsafe_allow_html=True)
            st.markdown(f'**Nombre:** {n1.get("nombre", "—")}')
            st.markdown(f'**A qué se dedica:** {n1.get("dedicacion", "—")}')
            st.markdown(f'**Antigüedad:** {n1.get("antiguedad", "—")}  ·  **Ubicación:** {n1.get("ubicacion", "—")}')

            st.markdown('<div class="section-lbl">02 — Tus clientes</div>', unsafe_allow_html=True)
            st.markdown(f'**Cliente ideal:** {n2.get("cliente_ideal", "—")}')
            st.markdown(f'**Problema que resuelve:** {n2.get("problema", "—")}')
            st.markdown(f'**Por qué lo eligen:** {n2.get("diferencial_cliente", "—")}')

            st.markdown('<div class="section-lbl">03 — Personalidad</div>', unsafe_allow_html=True)
            palabras = n3.get("palabras", [])
            if palabras:
                st.markdown(" ".join(f'<span class="tag">{p}</span>' for p in palabras), unsafe_allow_html=True)
            st.markdown(f'**Cómo habla:** {n3.get("como_habla", "—")}')
            st.markdown(f'**Sensación al verla:** {n3.get("sensacion", "—")}')

        with col_b:
            st.markdown('<div class="section-lbl">04 — Referentes y competencia</div>', unsafe_allow_html=True)
            st.markdown(f'**Marcas que admira:** {n4.get("referentes", "—")}')
            st.markdown(f'**Diferencial:** {n4.get("diferencial_competencia", "—")}')

            st.markdown('<div class="section-lbl">05 — Lo visual</div>', unsafe_allow_html=True)
            st.markdown(f'**Colores sí:** {n5.get("colores_si", "—")}')
            st.markdown(f'**Colores no:** {n5.get("colores_no", "—")}')
            st.markdown(f'**Logo:** {n5.get("logo", "—")}')
            st.markdown(f'**Estilos:** {n5.get("estilos", "—")}')

            st.markdown('<div class="section-lbl">06 — Objetivos</div>', unsafe_allow_html=True)
            st.markdown(f'**Objetivo:** {n6.get("objetivo", "—")}')
            st.markdown(f'**Visión a 1 año:** {n6.get("vision", "—")}')
            st.markdown(f'**Extra:** {n6.get("extra", "—")}')

        st.markdown("---")
        with open(ruta, "r", encoding="utf-8") as f:
            raw = f.read()
        st.download_button(
            "⬇️ Descargar JSON",
            data=raw.encode("utf-8"),
            file_name=archivo,
            mime="application/json",
            key=f"dl_{archivo}"
        )
