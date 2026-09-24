"""Ayudas de interfaz compartidas por todas las pantallas."""
import threading
import uuid
from contextlib import contextmanager
from urllib.parse import urlsplit
from datetime import date, timedelta

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.orm import Session

from . import db
from .db import crear_engine, database_url, init_db
from .services import avisos
from .services.util import pesos  # noqa: F401  (las vistas lo usan como ui.pesos)
from .tiempo import DIAS, hoy


# ---- Base de datos ---------------------------------------------------------------------------

@st.cache_resource
def get_engine():
    engine = crear_engine(database_url())
    init_db(engine)
    return engine


@contextmanager
def sesion():
    """Sesión para leer. Para escribir usar `ejecutar`, que confirma antes de recargar la página."""
    s = Session(get_engine(), expire_on_commit=False)
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def ejecutar(funcion, *args, ok: str | None = None, recargar: bool = True, **kwargs):
    """Corre `funcion(s, *args)` en su propia transacción. Si el dato es inválido muestra el error;
    si sale bien avisa y recarga (st.rerun corta la ejecución, por eso se confirma antes)."""
    try:
        with sesion() as s:
            resultado = funcion(s, *args, **kwargs)
            pendientes = avisos.pendientes(s)
    except ValueError as e:
        st.error(str(e), icon="⚠️")
        return None
    if pendientes:
        mandar_avisos(pendientes)
    contar_alertas.clear()
    if ok:
        flash(ok)
    if recargar:
        st.rerun()
    return resultado


def en_segundo_plano(funcion, *args) -> None:
    """Corre `funcion(s, *args)` en otro hilo con su propia sesión (para mandar avisos sin demorar la pantalla)."""
    engine = get_engine()

    def tarea():
        try:
            with Session(engine) as s:
                funcion(s, *args)
                s.commit()  # por ejemplo, dispositivos dados de baja
        except Exception:  # un aviso que no sale nunca frena el trabajo
            pass

    threading.Thread(target=tarea, daemon=True).start()


def mandar_avisos(pendientes: list[dict]) -> None:
    from .services import notificaciones
    en_segundo_plano(notificaciones.enviar_avisos, pendientes)


@st.cache_data(ttl=600, show_spinner=False)
def pagina_publicada(url: str) -> bool:
    """¿Está publicada la página de activación de notificaciones (GitHub Pages)?"""
    import requests
    try:
        return requests.get(url.rstrip("/") + "/sw.js", timeout=4).status_code == 200
    except requests.RequestException:
        return False


def url_app() -> str:
    try:
        partes = urlsplit(st.context.url)
        return f"{partes.scheme}://{partes.netloc}"
    except Exception:
        return ""


def problema_base() -> tuple[str, str] | None:
    """None si la base responde. Si no: ("falta", "") o ("error", detalle sin la contraseña)."""
    if st.session_state.get("_base_ok"):
        return None
    if db.en_streamlit_cloud() and not db.url_configurada():
        return "falta", ""  # en la nube, SQLite se borraría en cada reinicio
    try:
        with get_engine().connect() as conexion:
            conexion.execute(text("SELECT 1"))
    except Exception as e:
        return "error", db.ocultar_clave(e)
    st.session_state["_base_ok"] = True
    return None


def pantalla_problema_base(tipo: str, detalle: str) -> None:
    st.title("🌱 Falta un paso")
    pasos = ("En **share.streamlit.io**, en tu app tocá **⋮ → Settings → Secrets** y dejá esta línea, con la "
             "dirección que te dio Neon (empieza con `postgresql://`) entre comillas:")
    if tipo == "falta":
        st.error("Falta conectar la base de datos. Sin eso, los datos se borrarían cada vez que la app se reinicia.")
    else:
        st.error("No se pudo conectar a la base de datos. Revisá que la dirección esté bien copiada, completa "
                 "y sin espacios.")
    st.markdown(pasos)
    st.code('DATABASE_URL = "postgresql://usuario:clave@servidor/neondb?sslmode=require"', language="toml")
    st.markdown("Después tocá **Save**: la app se reinicia sola en un minuto.")
    if detalle:
        with st.expander("Detalle técnico"):
            st.code(detalle, language=None)


@st.cache_data(ttl=300, show_spinner=False)
def contar_alertas(usuario_id: int | None) -> int:
    from .services import alertas
    with sesion() as s:
        return alertas.contar(alertas.calcular(s, usuario_id))


# ---- Sesión del usuario y avisos -------------------------------------------------------------

def usuario() -> dict:
    return st.session_state.get("usuario") or {}


def uid() -> int | None:
    return usuario().get("id")


def flash(mensaje: str, icono: str = "✅") -> None:
    """Aviso que se muestra después de recargar la página."""
    st.session_state.setdefault("_flash", []).append((mensaje, icono))


def mostrar_flash() -> None:
    for mensaje, icono in st.session_state.pop("_flash", []):
        st.toast(mensaje, icon=icono)


# ---- Formatos --------------------------------------------------------------------------------

def pesos_md(valor, decimales: int | None = None) -> str:
    """Igual que `pesos` pero para textos con markdown (ahí el signo $ abre una fórmula)."""
    return pesos(valor, decimales).replace("$", "\\$")


def cant(valor) -> str:
    v = float(valor or 0)
    return f"{v:,.0f}".replace(",", ".") if v.is_integer() else f"{v:.2f}".rstrip("0").replace(".", ",")


def fecha(d) -> str:
    if d is None or (not isinstance(d, date) and pd.isna(d)):
        return "—"
    return d.strftime("%d/%m/%Y")


def cuando(d: date) -> str:
    dias = (d - hoy()).days
    return {0: "hoy", 1: "mañana", -1: "ayer"}.get(dias, f"hace {-dias} días" if dias < 0 else f"en {dias} días")


def fecha_larga(d: date) -> str:
    return f"{DIAS[d.weekday()].capitalize()} {d:%d/%m/%Y}"


def col_pesos(titulo: str):
    return st.column_config.NumberColumn(titulo, format="localized")


def col_cant(titulo: str):
    return st.column_config.NumberColumn(titulo, format="localized")


def col_fecha(titulo: str):
    return st.column_config.DateColumn(titulo, format="DD/MM/YYYY")


def col_fecha_hora(titulo: str):
    return st.column_config.DatetimeColumn(titulo, format="DD/MM/YYYY HH:mm")


# ---- Selectores ------------------------------------------------------------------------------

PERIODOS = ["Hoy", "Últimos 7 días", "Este mes", "Mes anterior", "Últimos 30 días", "Últimos 90 días",
            "Este año", "Últimos 12 meses", "Personalizado"]


def selector_periodo(key: str, defecto: str = "Este mes") -> tuple[date, date]:
    ref = hoy()
    c1, c2 = st.columns([1, 2], vertical_alignment="bottom")
    opcion = c1.selectbox("Período", PERIODOS, index=PERIODOS.index(defecto), key=f"{key}_periodo")
    inicio_mes = ref.replace(day=1)
    rangos = {"Hoy": (ref, ref), "Últimos 7 días": (ref - timedelta(days=6), ref), "Este mes": (inicio_mes, ref),
              "Mes anterior": ((inicio_mes - timedelta(days=1)).replace(day=1), inicio_mes - timedelta(days=1)),
              "Últimos 30 días": (ref - timedelta(days=29), ref), "Últimos 90 días": (ref - timedelta(days=89), ref),
              "Este año": (date(ref.year, 1, 1), ref), "Últimos 12 meses": (ref - timedelta(days=364), ref)}
    if opcion in rangos:
        desde, hasta = rangos[opcion]
        c2.caption(f"Del {fecha(desde)} al {fecha(hasta)}")
        return desde, hasta
    rango = c2.date_input("Desde / hasta", (inicio_mes, ref), format="DD/MM/YYYY", key=f"{key}_rango")
    return (rango[0], rango[-1]) if rango else (ref, ref)


def etiquetas_productos(df: pd.DataFrame) -> dict[int, str]:
    return {int(r.id): f"{r.producto} — {pesos(r.precio)} · stock {cant(r.disponible)}" for r in df.itertuples()}


def selector_producto(df: pd.DataFrame, key: str, etiqueta: str = "Producto", donde=None, **kwargs) -> int | None:
    opciones = etiquetas_productos(df)
    return (donde or st).selectbox(etiqueta, list(opciones), format_func=opciones.get, index=None,
                        placeholder="Escribí para buscar…", key=key, **kwargs)


def selector_cliente(df_clientes: pd.DataFrame, key: str, permitir_ninguno: bool = True) -> int | None:
    """Selector de cliente con alta rápida (nombre y teléfono)."""
    from .services import clientes

    with st.popover("Cliente nuevo", icon="➕"):
        with st.form(f"{key}_alta", clear_on_submit=True, border=False):
            nombre = st.text_input("Nombre")
            telefono = st.text_input("Teléfono")
            if st.form_submit_button("Crear cliente", type="primary"):
                c = ejecutar(clientes.guardar, {"nombre": nombre, "telefono": telefono}, recargar=False)
                if c:
                    st.session_state[key] = c.id
                    flash(f"Cliente {c.nombre} creado")
                    st.rerun()
    activos = df_clientes[df_clientes["activo"]] if "activo" in df_clientes else df_clientes
    opciones = {int(r.id): r.nombre + (f" · {r.telefono}" if r.telefono else "") for r in activos.itertuples()}
    if permitir_ninguno:
        opciones = {0: "Consumidor final", **opciones}
    if st.session_state.get(key) not in opciones:
        st.session_state.pop(key, None)
    valor = st.selectbox("Cliente", list(opciones), format_func=opciones.get, key=key,
                         index=0 if permitir_ninguno else None, placeholder="Buscá el cliente…")
    return valor or None


# ---- Lista editable de ítems (carrito, pedido, compra) ------------------------------------------

def editor_items(key: str, productos: pd.DataFrame, precio: str = "precio", etiqueta_precio: str = "Precio",
                 libre: bool = True, avisar_stock: bool = True) -> list[dict]:
    items: list[dict] = st.session_state.setdefault(key, [])
    opciones = etiquetas_productos(productos)
    with st.form(f"{key}_form", clear_on_submit=True, border=False):
        c1, c2, c3 = st.columns([6, 1.6, 1.6], vertical_alignment="bottom")
        pid = c1.selectbox("Producto", list(opciones), format_func=opciones.get, index=None,
                           placeholder="Escribí para buscar…")
        cantidad = c2.number_input("Cantidad", min_value=0.0, value=1.0, step=1.0, format="%g")
        agregar = c3.form_submit_button("Agregar", icon="➕", width="stretch")
    if agregar and pid is not None and cantidad > 0:
        fila = productos.loc[productos["id"] == pid].iloc[0]
        existente = next((i for i in items if i["producto_id"] == pid), None)
        if existente:
            existente["cantidad"] += cantidad
            st.session_state[f"{key}_c_{existente['uid']}"] = existente["cantidad"]
        else:
            items.append({"uid": uuid.uuid4().hex[:8], "producto_id": int(pid), "descripcion": fila["producto"],
                          "cantidad": float(cantidad), "precio": float(fila[precio]),
                          "stock": float(fila["disponible"]) if avisar_stock else None})
    if libre:
        with st.expander("Ítem libre: servicio, envío o algo que no está en el catálogo"):
            with st.form(f"{key}_libre", clear_on_submit=True, border=False):
                c1, c2, c3, c4 = st.columns([4, 1.4, 1.8, 1.6], vertical_alignment="bottom")
                descripcion = c1.text_input("Descripción")
                n = c2.number_input("Cantidad", min_value=0.0, value=1.0, step=1.0, format="%g")
                valor = c3.number_input(etiqueta_precio, min_value=0.0, step=100.0, format="%.2f")
                if c4.form_submit_button("Agregar", width="stretch") and descripcion.strip() and n > 0:
                    items.append({"uid": uuid.uuid4().hex[:8], "producto_id": None, "descripcion": descripcion.strip(),
                                  "cantidad": float(n), "precio": float(valor), "stock": None})
    for it in list(items):
        kc, kp = f"{key}_c_{it['uid']}", f"{key}_p_{it['uid']}"
        st.session_state.setdefault(kc, float(it["cantidad"]))
        st.session_state.setdefault(kp, float(it["precio"]))
        c = st.columns([5, 1.6, 1.9, 1.7, 0.7], vertical_alignment="center")
        it["cantidad"] = c[1].number_input("Cantidad", min_value=0.0, step=1.0, format="%g", key=kc,
                                           label_visibility="collapsed")
        it["precio"] = c[2].number_input(etiqueta_precio, min_value=0.0, step=100.0, format="%.2f", key=kp,
                                         label_visibility="collapsed")
        aviso = ""
        if it["stock"] is not None and it["cantidad"] > it["stock"]:
            aviso = f" :orange[(hay {cant(max(it['stock'], 0))})]"
        c[0].markdown(f"**{it['descripcion']}**{aviso}")
        c[3].markdown(pesos_md(it["cantidad"] * it["precio"]))
        if c[4].button("✕", key=f"{key}_x_{it['uid']}", help="Quitar"):
            items.remove(it)
            st.rerun()
    return items


def vaciar_items(key: str) -> None:
    for it in st.session_state.get(key, []):
        for pref in ("c", "p"):
            st.session_state.pop(f"{key}_{pref}_{it['uid']}", None)
    st.session_state[key] = []


def banner_ultima_venta() -> None:
    """Después de vender o entregar un pedido: aviso con el comprobante para descargar."""
    from .services import config, documentos, ventas

    venta_id = st.session_state.get("ultima_venta")
    if not venta_id:
        return
    with sesion() as s:
        v = ventas.detalle(s, venta_id)
        pdf, total = documentos.comprobante_venta(v, config.todos(s)), v.total
    c = st.columns([4, 1.6, 0.8], vertical_alignment="center")
    c[0].success(f"Venta #{venta_id} registrada por {pesos_md(total)}.")
    c[1].download_button("Comprobante PDF", pdf, f"comprobante_{venta_id}.pdf", "application/pdf", icon="🧾",
                         width="stretch")
    if c[2].button("Cerrar", key="cerrar_banner", width="stretch"):
        del st.session_state["ultima_venta"]
        st.rerun()


def importador(key: str, columnas: list[str], ejemplo: list[dict], funcion, **kwargs) -> None:
    """Carga masiva desde Excel/CSV con plantilla descargable y vista previa."""
    from .services import importar

    st.download_button("Descargar plantilla Excel", importar.plantilla(columnas, ejemplo), f"plantilla_{key}.xlsx",
                       icon="📥", key=f"{key}_plantilla")
    archivo = st.file_uploader("Subí el archivo completo (Excel o CSV)", type=["xlsx", "xls", "csv"], key=f"{key}_archivo")
    if not archivo:
        return
    try:
        df = importar.leer(archivo)
    except Exception as e:  # archivo dañado o formato raro
        st.error(f"No se pudo leer el archivo: {e}")
        return
    faltan = [c for c in columnas[:1] if c not in df.columns]
    if faltan:
        st.error("Falta la columna «nombre». Usá la plantilla como guía.")
        return
    st.dataframe(df.head(50), hide_index=True)
    st.caption(f"{len(df)} filas. Se muestran las primeras 50.")
    if st.button(f"Importar {len(df)} filas", type="primary", key=f"{key}_importar"):
        res = ejecutar(funcion, df, recargar=False, **kwargs)
        if res:
            creados, errores = res
            st.success(f"Se cargaron {creados} registros.")
            for e in errores:
                st.warning(e)
