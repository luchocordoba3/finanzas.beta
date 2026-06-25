import streamlit as st
import json
import os
from datetime import date, datetime

st.set_page_config(page_title="Cuestionario de Marca", layout="centered")

RESPUESTAS_DIR = "respuestas_marca"
os.makedirs(RESPUESTAS_DIR, exist_ok=True)

# ── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  /* Fondo general */
  .stApp { background: #f5f7fa; }

  /* Hero header */
  .hero {
    background: linear-gradient(135deg, #0d1b2a 0%, #1b3a5c 100%);
    border-radius: 16px;
    padding: 48px 40px 40px;
    margin-bottom: 32px;
    position: relative;
    overflow: hidden;
  }
  .hero::before {
    content: "";
    position: absolute;
    top: -60px; right: -60px;
    width: 200px; height: 200px;
    border-radius: 50%;
    background: rgba(255,255,255,0.06);
  }
  .hero::after {
    content: "";
    position: absolute;
    bottom: -40px; right: 80px;
    width: 120px; height: 120px;
    border-radius: 50%;
    background: rgba(255,255,255,0.04);
  }
  .hero-label {
    color: #4a9fd4;
    font-size: 11px;
    letter-spacing: 3px;
    font-weight: 600;
    text-transform: uppercase;
    margin-bottom: 12px;
  }
  .hero h1 {
    color: #ffffff;
    font-size: 48px;
    font-weight: 800;
    margin: 0 0 16px;
    line-height: 1.1;
  }
  .hero p {
    color: #b0c4d8;
    font-size: 18px;
    line-height: 1.6;
    max-width: 540px;
    margin: 0;
  }

  /* Info box */
  .info-box {
    background: #eef2f7;
    border-radius: 12px;
    padding: 24px 28px;
    margin-bottom: 36px;
  }
  .info-box .info-title {
    color: #1b3a5c;
    font-size: 11px;
    letter-spacing: 3px;
    font-weight: 700;
    text-transform: uppercase;
    margin-bottom: 10px;
  }
  .info-box p { color: #4a5568; font-size: 15px; line-height: 1.7; margin: 0; }
  .info-box strong { color: #1b3a5c; }

  /* Section headers */
  .section-header {
    display: flex;
    align-items: center;
    gap: 14px;
    margin: 40px 0 20px;
  }
  .section-num {
    background: #1b3a5c;
    color: white;
    font-weight: 800;
    font-size: 16px;
    width: 40px; height: 40px;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
  }
  .section-title { font-size: 26px; font-weight: 800; color: #0d1b2a; margin: 0; }

  /* Question labels */
  .q-label { font-size: 16px; font-weight: 700; color: #0d1b2a; margin: 24px 0 4px; }
  .q-hint  { font-size: 13px; color: #6b7a8d; font-style: italic; margin-bottom: 8px; }

  /* Divider */
  hr.section-div { border: none; border-top: 1px solid #d0dae6; margin: 12px 0 0; }

  /* Submit button */
  div.stButton > button {
    background: linear-gradient(135deg, #1b3a5c, #2a5885);
    color: white;
    font-weight: 700;
    font-size: 16px;
    padding: 14px 40px;
    border: none;
    border-radius: 10px;
    width: 100%;
    cursor: pointer;
    margin-top: 16px;
  }
  div.stButton > button:hover { opacity: 0.9; }

  /* Success card */
  .success-card {
    background: #e8f5e9;
    border: 1px solid #a5d6a7;
    border-radius: 12px;
    padding: 28px 32px;
    text-align: center;
    margin-top: 24px;
  }
  .success-card h3 { color: #1b5e20; font-size: 22px; margin: 0 0 8px; }
  .success-card p  { color: #2e7d32; margin: 0; }
</style>
""", unsafe_allow_html=True)

# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
  <div class="hero-label">Estudio de Diseño Digital</div>
  <h1>Cuestionario<br>de Marca</h1>
  <p>Contanos sobre tu negocio para diseñar una marca que sea realmente tuya.
     No hay respuestas correctas: escribí lo que se te venga a la cabeza.</p>
</div>
""", unsafe_allow_html=True)

# ── Info box ──────────────────────────────────────────────────────────────────
st.markdown("""
<div class="info-box">
  <div class="info-title">Cómo completarlo</div>
  <p>Completá los campos directamente acá. Son seis bloques cortos: tu negocio, tus clientes,
  la personalidad de tu marca, tus referentes, lo visual y tus objetivos.
  Cuando termines, tocá <strong>Enviar cuestionario</strong> y tus respuestas quedan guardadas.</p>
</div>
""", unsafe_allow_html=True)

# ── Para / Fecha ──────────────────────────────────────────────────────────────
col_para, col_fecha = st.columns(2)
with col_para:
    st.markdown('<p class="q-label">PARA</p>', unsafe_allow_html=True)
    nombre_negocio_header = st.text_input("nombre_header", placeholder="Tu nombre o negocio",
                                          label_visibility="collapsed", key="para_header")
with col_fecha:
    st.markdown('<p class="q-label">FECHA</p>', unsafe_allow_html=True)
    fecha_hoy = st.date_input("fecha_header", value=date.today(),
                              label_visibility="collapsed", key="fecha_header")

st.markdown("---")

# ═══════════════════════════════════════════════════════════
# 01 - TU NEGOCIO
# ═══════════════════════════════════════════════════════════
st.markdown("""
<div class="section-header">
  <div class="section-num">01</div>
  <p class="section-title">Tu negocio</p>
</div>
""", unsafe_allow_html=True)

st.markdown('<p class="q-label">¿Cómo se llama tu negocio?</p>', unsafe_allow_html=True)
st.markdown('<hr class="section-div">', unsafe_allow_html=True)
nombre_negocio = st.text_input("nombre_neg", placeholder="Nombre de tu negocio o marca",
                                label_visibility="collapsed", key="nombre_neg")

st.markdown('<p class="q-label">¿A qué te dedicás?</p>', unsafe_allow_html=True)
st.markdown('<p class="q-hint">Tus servicios o productos principales.</p>', unsafe_allow_html=True)
dedicacion = st.text_area("dedicacion", placeholder="Describí tus servicios o productos...",
                           height=100, label_visibility="collapsed", key="dedicacion")

col_tiempo, col_lugar = st.columns(2)
with col_tiempo:
    st.markdown('<p class="q-label">¿Hace cuánto que existe?</p>', unsafe_allow_html=True)
    st.markdown('<hr class="section-div">', unsafe_allow_html=True)
    antiguedad = st.text_input("antiguedad", placeholder="Ej: 2 años",
                                label_visibility="collapsed", key="antiguedad")
with col_lugar:
    st.markdown('<p class="q-label">¿Dónde estás? (zona u online)</p>', unsafe_allow_html=True)
    st.markdown('<hr class="section-div">', unsafe_allow_html=True)
    ubicacion = st.text_input("ubicacion", placeholder="Ej: Buenos Aires / Online",
                               label_visibility="collapsed", key="ubicacion")

# ═══════════════════════════════════════════════════════════
# 02 - TUS CLIENTES
# ═══════════════════════════════════════════════════════════
st.markdown("""
<div class="section-header">
  <div class="section-num">02</div>
  <p class="section-title">Tus clientes</p>
</div>
""", unsafe_allow_html=True)

st.markdown('<p class="q-label">¿Cómo es tu cliente ideal?</p>', unsafe_allow_html=True)
st.markdown('<p class="q-hint">Edad, gustos, momento de vida. Imaginá a una persona concreta.</p>', unsafe_allow_html=True)
cliente_ideal = st.text_area("cliente_ideal", placeholder="Describí a tu cliente ideal...",
                              height=100, label_visibility="collapsed", key="cliente_ideal")

st.markdown('<p class="q-label">¿Qué problema le resolvés?</p>', unsafe_allow_html=True)
problema = st.text_area("problema", placeholder="¿Cuál es el dolor o necesidad que atendés?",
                         height=100, label_visibility="collapsed", key="problema")

st.markdown('<p class="q-label">¿Por qué te eligen a vos y no a otro?</p>', unsafe_allow_html=True)
diferencial_cliente = st.text_area("diferencial_cliente", placeholder="Tu ventaja desde la mirada del cliente...",
                                    height=100, label_visibility="collapsed", key="diferencial_cliente")

# ═══════════════════════════════════════════════════════════
# 03 - PERSONALIDAD DE TU MARCA
# ═══════════════════════════════════════════════════════════
st.markdown("""
<div class="section-header">
  <div class="section-num">03</div>
  <p class="section-title">La personalidad de tu marca</p>
</div>
""", unsafe_allow_html=True)

st.markdown('<p class="q-label">Elegí de 3 a 5 palabras que describan tu marca</p>', unsafe_allow_html=True)
st.markdown('<p class="q-hint">Marcá las que sientas más tuyas.</p>', unsafe_allow_html=True)

PALABRAS = ["Cercana", "Profesional", "Moderna", "Clásica",
            "Divertida", "Elegante", "Minimalista", "Audaz",
            "Cálida", "Confiable", "Premium", "Simple"]

col1, col2, col3, col4 = st.columns(4)
palabras_cols = [col1, col2, col3, col4]
palabras_elegidas = []
for i, palabra in enumerate(PALABRAS):
    with palabras_cols[i % 4]:
        if st.checkbox(palabra, key=f"pal_{palabra}"):
            palabras_elegidas.append(palabra)

st.markdown('<p class="q-label">Si tu marca fuera una persona, ¿cómo hablaría?</p>', unsafe_allow_html=True)
st.markdown('<p class="q-hint">Cercana y de vos, formal y de usted, con humor, directa…</p>', unsafe_allow_html=True)
como_habla = st.text_area("como_habla", placeholder="Describí el tono de voz de tu marca...",
                           height=100, label_visibility="collapsed", key="como_habla")

st.markdown('<p class="q-label">¿Cómo querés que se sienta alguien al verte?</p>', unsafe_allow_html=True)
st.markdown('<hr class="section-div">', unsafe_allow_html=True)
sensacion = st.text_input("sensacion", placeholder="Ej: Confiado, inspirado, tranquilo...",
                           label_visibility="collapsed", key="sensacion")

# ═══════════════════════════════════════════════════════════
# 04 - REFERENTES Y COMPETENCIA
# ═══════════════════════════════════════════════════════════
st.markdown("""
<div class="section-header">
  <div class="section-num">04</div>
  <p class="section-title">Referentes y competencia</p>
</div>
""", unsafe_allow_html=True)

st.markdown('<p class="q-label">Marcas que admirás (de tu rubro o no)</p>', unsafe_allow_html=True)
st.markdown('<p class="q-hint">¿Qué te gusta de cada una?</p>', unsafe_allow_html=True)
referentes = st.text_area("referentes", placeholder="Ej: Apple (diseño limpio), Netflix (comunicación directa)...",
                           height=100, label_visibility="collapsed", key="referentes")

st.markdown('<p class="q-label">¿Qué te diferencia de tu competencia?</p>', unsafe_allow_html=True)
diferencial_competencia = st.text_area("diferencial_competencia",
                                        placeholder="Lo que te hace único frente a otros del mismo rubro...",
                                        height=100, label_visibility="collapsed", key="diferencial_comp")

# ═══════════════════════════════════════════════════════════
# 05 - LO VISUAL
# ═══════════════════════════════════════════════════════════
st.markdown("""
<div class="section-header">
  <div class="section-num">05</div>
  <p class="section-title">Lo visual</p>
</div>
""", unsafe_allow_html=True)

col_col1, col_col2 = st.columns(2)
with col_col1:
    st.markdown('<p class="q-label">Colores con los que te identificás</p>', unsafe_allow_html=True)
    colores_si = st.text_area("colores_si", placeholder="Ej: Azul marino, dorado, blanco...",
                               height=80, label_visibility="collapsed", key="colores_si")
with col_col2:
    st.markdown('<p class="q-label">Colores que querés evitar</p>', unsafe_allow_html=True)
    colores_no = st.text_area("colores_no", placeholder="Ej: Rojo intenso, flúo...",
                               height=80, label_visibility="collapsed", key="colores_no")

st.markdown('<p class="q-label">¿Tenés logo actual? ¿Lo querés mantener, ajustar o rehacer?</p>', unsafe_allow_html=True)
logo_opcion = st.radio("logo_radio",
                        ["No tengo", "Mantener", "Ajustar", "Rehacer"],
                        horizontal=True, label_visibility="collapsed", key="logo_radio")

st.markdown('<p class="q-label">Estilos que te gustan</p>', unsafe_allow_html=True)
st.markdown('<p class="q-hint">Minimalista, colorido, elegante, retro… contanos con tus palabras.</p>', unsafe_allow_html=True)
estilos = st.text_area("estilos", placeholder="Describí la estética que imaginás para tu marca...",
                        height=100, label_visibility="collapsed", key="estilos")

# ═══════════════════════════════════════════════════════════
# 06 - TUS OBJETIVOS
# ═══════════════════════════════════════════════════════════
st.markdown("""
<div class="section-header">
  <div class="section-num">06</div>
  <p class="section-title">Tus objetivos</p>
</div>
""", unsafe_allow_html=True)

st.markdown('<p class="q-label">¿Qué querés lograr con esto?</p>', unsafe_allow_html=True)
st.markdown('<p class="q-hint">Más turnos, vender online, verte más profesional…</p>', unsafe_allow_html=True)
objetivo = st.text_area("objetivo", placeholder="Contanos qué esperás de este proceso...",
                         height=100, label_visibility="collapsed", key="objetivo")

st.markdown('<p class="q-label">¿Dónde te imaginás el negocio en un año?</p>', unsafe_allow_html=True)
vision = st.text_area("vision", placeholder="Tu visión a futuro...",
                       height=100, label_visibility="collapsed", key="vision")

st.markdown('<p class="q-label">Algo más que quieras contarnos</p>', unsafe_allow_html=True)
extra = st.text_area("extra", placeholder="Cualquier detalle extra que sientas importante...",
                      height=100, label_visibility="collapsed", key="extra")

st.markdown("---")

# ═══════════════════════════════════════════════════════════
# ENVIAR
# ═══════════════════════════════════════════════════════════
if st.button("✅ Enviar cuestionario"):
    if not nombre_negocio_header.strip():
        st.error("Por favor completá el campo 'PARA' con tu nombre o negocio antes de enviar.")
    else:
        datos = {
            "meta": {
                "para": nombre_negocio_header.strip(),
                "fecha": str(fecha_hoy),
                "timestamp": datetime.now().isoformat()
            },
            "01_tu_negocio": {
                "nombre": nombre_negocio,
                "dedicacion": dedicacion,
                "antiguedad": antiguedad,
                "ubicacion": ubicacion
            },
            "02_tus_clientes": {
                "cliente_ideal": cliente_ideal,
                "problema": problema,
                "diferencial_cliente": diferencial_cliente
            },
            "03_personalidad": {
                "palabras": palabras_elegidas,
                "como_habla": como_habla,
                "sensacion": sensacion
            },
            "04_referentes": {
                "referentes": referentes,
                "diferencial_competencia": diferencial_competencia
            },
            "05_visual": {
                "colores_si": colores_si,
                "colores_no": colores_no,
                "logo": logo_opcion,
                "estilos": estilos
            },
            "06_objetivos": {
                "objetivo": objetivo,
                "vision": vision,
                "extra": extra
            }
        }

        slug = nombre_negocio_header.strip().lower().replace(" ", "_").replace("/", "-")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        archivo = os.path.join(RESPUESTAS_DIR, f"{slug}_{ts}.json")
        with open(archivo, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)

        # Generar HTML descargable
        palabras_str = ", ".join(palabras_elegidas) if palabras_elegidas else "—"
        html_doc = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Cuestionario de Marca – {nombre_negocio_header}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Inter', sans-serif; background: #fff; color: #0d1b2a; padding: 0; }}

  .hero {{
    background: linear-gradient(135deg, #0d1b2a 0%, #1b3a5c 100%);
    padding: 56px 60px 48px;
    position: relative;
    overflow: hidden;
  }}
  .hero::before {{
    content: "";
    position: absolute;
    top: -70px; right: -70px;
    width: 220px; height: 220px;
    border-radius: 50%;
    background: rgba(255,255,255,0.07);
  }}
  .hero::after {{
    content: "";
    position: absolute;
    bottom: -50px; right: 100px;
    width: 130px; height: 130px;
    border-radius: 50%;
    background: rgba(255,255,255,0.04);
  }}
  .hero-label {{ color: #4a9fd4; font-size: 11px; letter-spacing: 3px; font-weight: 700; text-transform: uppercase; margin-bottom: 14px; }}
  .hero h1 {{ color: #fff; font-size: 52px; font-weight: 800; line-height: 1.1; margin-bottom: 18px; }}
  .hero-meta {{ display: flex; gap: 40px; margin-top: 20px; }}
  .hero-meta-item {{ background: rgba(255,255,255,0.08); border-radius: 10px; padding: 14px 22px; }}
  .hero-meta-item .label {{ color: #4a9fd4; font-size: 10px; letter-spacing: 2px; font-weight: 700; text-transform: uppercase; margin-bottom: 4px; }}
  .hero-meta-item .value {{ color: #fff; font-size: 16px; font-weight: 600; }}

  .body {{ padding: 48px 60px; max-width: 900px; margin: 0 auto; }}

  .section {{ margin-bottom: 48px; page-break-inside: avoid; }}
  .section-header {{ display: flex; align-items: center; gap: 16px; margin-bottom: 28px; padding-bottom: 14px; border-bottom: 2px solid #e2e8f0; }}
  .section-num {{ background: #1b3a5c; color: #fff; font-weight: 800; font-size: 16px; width: 42px; height: 42px; border-radius: 50%; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }}
  .section-title {{ font-size: 26px; font-weight: 800; color: #0d1b2a; }}

  .field {{ margin-bottom: 24px; }}
  .field-label {{ font-size: 13px; font-weight: 700; color: #1b3a5c; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px; }}
  .field-value {{ font-size: 15px; color: #2d3748; line-height: 1.7; background: #f7fafc; border-radius: 8px; padding: 14px 18px; border-left: 3px solid #1b3a5c; min-height: 44px; }}
  .field-value.empty {{ color: #a0aec0; font-style: italic; }}

  .two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}

  .tags {{ display: flex; flex-wrap: wrap; gap: 8px; }}
  .tag {{ background: #1b3a5c; color: #fff; font-size: 13px; font-weight: 600; padding: 6px 14px; border-radius: 20px; }}

  .footer {{ background: #0d1b2a; padding: 28px 60px; display: flex; justify-content: space-between; align-items: center; margin-top: 48px; }}
  .footer-brand {{ color: #4a9fd4; font-size: 11px; letter-spacing: 3px; font-weight: 700; text-transform: uppercase; }}
  .footer-msg {{ color: #b0c4d8; font-size: 14px; }}

  @media print {{
    body {{ padding: 0; }}
    .body {{ padding: 32px 48px; }}
    .hero {{ padding: 48px; }}
  }}
</style>
</head>
<body>

<div class="hero">
  <div class="hero-label">Estudio de Diseño Digital</div>
  <h1>Cuestionario<br>de Marca</h1>
  <div class="hero-meta">
    <div class="hero-meta-item">
      <div class="label">Para</div>
      <div class="value">{nombre_negocio_header}</div>
    </div>
    <div class="hero-meta-item">
      <div class="label">Fecha</div>
      <div class="value">{fecha_hoy.strftime("%d / %m / %Y")}</div>
    </div>
  </div>
</div>

<div class="body">

  <!-- 01 -->
  <div class="section">
    <div class="section-header">
      <div class="section-num">01</div>
      <div class="section-title">Tu negocio</div>
    </div>
    <div class="field">
      <div class="field-label">¿Cómo se llama tu negocio?</div>
      <div class="field-value {'empty' if not nombre_negocio else ''}">{nombre_negocio or 'Sin completar'}</div>
    </div>
    <div class="field">
      <div class="field-label">¿A qué te dedicás?</div>
      <div class="field-value {'empty' if not dedicacion else ''}">{dedicacion.replace(chr(10), '<br>') if dedicacion else 'Sin completar'}</div>
    </div>
    <div class="two-col">
      <div class="field">
        <div class="field-label">¿Hace cuánto que existe?</div>
        <div class="field-value {'empty' if not antiguedad else ''}">{antiguedad or 'Sin completar'}</div>
      </div>
      <div class="field">
        <div class="field-label">¿Dónde estás?</div>
        <div class="field-value {'empty' if not ubicacion else ''}">{ubicacion or 'Sin completar'}</div>
      </div>
    </div>
  </div>

  <!-- 02 -->
  <div class="section">
    <div class="section-header">
      <div class="section-num">02</div>
      <div class="section-title">Tus clientes</div>
    </div>
    <div class="field">
      <div class="field-label">¿Cómo es tu cliente ideal?</div>
      <div class="field-value {'empty' if not cliente_ideal else ''}">{cliente_ideal.replace(chr(10), '<br>') if cliente_ideal else 'Sin completar'}</div>
    </div>
    <div class="field">
      <div class="field-label">¿Qué problema le resolvés?</div>
      <div class="field-value {'empty' if not problema else ''}">{problema.replace(chr(10), '<br>') if problema else 'Sin completar'}</div>
    </div>
    <div class="field">
      <div class="field-label">¿Por qué te eligen a vos y no a otro?</div>
      <div class="field-value {'empty' if not diferencial_cliente else ''}">{diferencial_cliente.replace(chr(10), '<br>') if diferencial_cliente else 'Sin completar'}</div>
    </div>
  </div>

  <!-- 03 -->
  <div class="section">
    <div class="section-header">
      <div class="section-num">03</div>
      <div class="section-title">La personalidad de tu marca</div>
    </div>
    <div class="field">
      <div class="field-label">Palabras que describen tu marca</div>
      <div class="field-value">
        {'<div class="tags">' + ''.join(f'<span class="tag">{p}</span>' for p in palabras_elegidas) + '</div>' if palabras_elegidas else '<span style="color:#a0aec0;font-style:italic">Sin seleccionar</span>'}
      </div>
    </div>
    <div class="field">
      <div class="field-label">Si tu marca fuera una persona, ¿cómo hablaría?</div>
      <div class="field-value {'empty' if not como_habla else ''}">{como_habla.replace(chr(10), '<br>') if como_habla else 'Sin completar'}</div>
    </div>
    <div class="field">
      <div class="field-label">¿Cómo querés que se sienta alguien al verte?</div>
      <div class="field-value {'empty' if not sensacion else ''}">{sensacion or 'Sin completar'}</div>
    </div>
  </div>

  <!-- 04 -->
  <div class="section">
    <div class="section-header">
      <div class="section-num">04</div>
      <div class="section-title">Referentes y competencia</div>
    </div>
    <div class="field">
      <div class="field-label">Marcas que admirás</div>
      <div class="field-value {'empty' if not referentes else ''}">{referentes.replace(chr(10), '<br>') if referentes else 'Sin completar'}</div>
    </div>
    <div class="field">
      <div class="field-label">¿Qué te diferencia de tu competencia?</div>
      <div class="field-value {'empty' if not diferencial_competencia else ''}">{diferencial_competencia.replace(chr(10), '<br>') if diferencial_competencia else 'Sin completar'}</div>
    </div>
  </div>

  <!-- 05 -->
  <div class="section">
    <div class="section-header">
      <div class="section-num">05</div>
      <div class="section-title">Lo visual</div>
    </div>
    <div class="two-col">
      <div class="field">
        <div class="field-label">Colores con los que te identificás</div>
        <div class="field-value {'empty' if not colores_si else ''}">{colores_si.replace(chr(10), '<br>') if colores_si else 'Sin completar'}</div>
      </div>
      <div class="field">
        <div class="field-label">Colores que querés evitar</div>
        <div class="field-value {'empty' if not colores_no else ''}">{colores_no.replace(chr(10), '<br>') if colores_no else 'Sin completar'}</div>
      </div>
    </div>
    <div class="field">
      <div class="field-label">¿Logo actual?</div>
      <div class="field-value">{logo_opcion}</div>
    </div>
    <div class="field">
      <div class="field-label">Estilos que te gustan</div>
      <div class="field-value {'empty' if not estilos else ''}">{estilos.replace(chr(10), '<br>') if estilos else 'Sin completar'}</div>
    </div>
  </div>

  <!-- 06 -->
  <div class="section">
    <div class="section-header">
      <div class="section-num">06</div>
      <div class="section-title">Tus objetivos</div>
    </div>
    <div class="field">
      <div class="field-label">¿Qué querés lograr con esto?</div>
      <div class="field-value {'empty' if not objetivo else ''}">{objetivo.replace(chr(10), '<br>') if objetivo else 'Sin completar'}</div>
    </div>
    <div class="field">
      <div class="field-label">¿Dónde te imaginás el negocio en un año?</div>
      <div class="field-value {'empty' if not vision else ''}">{vision.replace(chr(10), '<br>') if vision else 'Sin completar'}</div>
    </div>
    <div class="field">
      <div class="field-label">Algo más que quieras contarnos</div>
      <div class="field-value {'empty' if not extra else ''}">{extra.replace(chr(10), '<br>') if extra else 'Sin completar'}</div>
    </div>
  </div>

</div>

<div class="footer">
  <div class="footer-brand">Estudio de Diseño Digital</div>
  <div class="footer-msg">¡Gracias! Con esto arrancamos.</div>
</div>

</body>
</html>"""

        st.markdown("""
<div class="success-card">
  <h3>¡Gracias! Con esto arrancamos.</h3>
  <p>Tus respuestas fueron guardadas correctamente. Ya podés descargar el documento.</p>
</div>
""", unsafe_allow_html=True)

        st.download_button(
            label="⬇️ Descargar documento de marca (HTML → imprimir como PDF)",
            data=html_doc.encode("utf-8"),
            file_name=f"cuestionario_marca_{slug}.html",
            mime="text/html"
        )

        st.info("**Tip:** Abrí el archivo descargado en tu navegador y usá Ctrl+P → Guardar como PDF para tener el documento final.")
