"""Cada pantalla carga sin errores con la base de ejemplo, y el flujo de venta funciona de punta a punta."""
import os

import pytest
import streamlit as st
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from streamlit.testing.v1 import AppTest

from conftest import base_limpia
from core.models import Producto, Venta

VISTAS = ["vender", "pedidos", "clientes", "stock", "recordatorios", "compras", "proveedores", "catalogo",
          "est_ventas", "est_plantas", "produccion", "configuracion"]


@pytest.fixture(scope="module")
def base_demo(tmp_path_factory):
    url = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{tmp_path_factory.mktemp('db') / 'demo.db'}"
    os.environ["DATABASE_URL"] = url
    import seed_demo
    engine = base_limpia(url)
    with Session(engine) as s:
        seed_demo.cargar(s)
        s.commit()
    yield engine
    del os.environ["DATABASE_URL"]


def _app(ruta: str) -> AppTest:
    st.cache_resource.clear()
    st.cache_data.clear()
    at = AppTest.from_file(ruta, default_timeout=60)
    at.session_state["usuario"] = {"id": 1, "nombre": "Ana"}
    return at


def test_inicio_con_navegacion(base_demo):
    at = _app("../app.py").run()
    assert not at.exception, at.exception
    assert at.title[0].value.startswith("Hola, Ana")
    assert len(at.expander) >= 5  # grupos de alertas


def test_ingreso_pide_usuario(base_demo):
    st.cache_resource.clear()
    at = AppTest.from_file("../app.py", default_timeout=60).run()
    assert not at.exception
    at.text_input[0].input("ana")
    at.text_input[1].input("vivero123")
    at.button[0].click().run()
    assert at.session_state["usuario"]["nombre"] == "Ana"


@pytest.mark.parametrize("vista", VISTAS)
def test_vista_carga_sin_errores(base_demo, vista):
    at = _app(f"../vistas/{vista}.py").run()
    assert not at.exception, at.exception


def test_venta_de_punta_a_punta(base_demo):
    with Session(base_demo) as s:
        antes = s.scalar(select(func.count(Venta.id)))
        producto_id = s.scalar(select(Producto.id).where(Producto.stock > 0))
    at = _app("../vistas/vender.py").run()
    at.selectbox[0].set_value(producto_id)
    at.button[0].click().run()  # "Agregar"
    assert len(at.session_state["carrito"]) == 1
    confirmar = next(b for b in at.button if b.label == "Confirmar venta")
    confirmar.click().run()
    assert not at.exception, at.exception
    with Session(base_demo) as s:
        assert s.scalar(select(func.count(Venta.id))) == antes + 1
    assert at.session_state["ultima_venta"]


def test_en_la_nube_sin_base_no_usa_sqlite(monkeypatch):
    from core import db
    monkeypatch.setattr(db, "en_streamlit_cloud", lambda: True)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    st.cache_resource.clear()
    at = AppTest.from_file("../app.py", default_timeout=30).run()
    assert not at.exception
    assert "Falta conectar la base de datos" in at.error[0].value
    assert not at.text_input  # no llega a la pantalla de ingreso


def test_base_mal_configurada_muestra_aviso_sin_la_clave(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://vivero:clave-secreta@127.0.0.1:1/neondb")
    st.cache_resource.clear()
    at = AppTest.from_file("../app.py", default_timeout=30).run()
    assert not at.exception
    assert "No se pudo conectar" in at.error[0].value
    assert "clave-secreta" not in "".join(c.value for c in at.code)


@pytest.fixture
def base_vacia(tmp_path, monkeypatch):
    """Como queda recién publicada: sin clientes, productos ni ventas; solo el primer usuario."""
    url = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{tmp_path / 'vacia.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    engine = base_limpia(url)
    from core import auth
    with Session(engine) as s:
        auth.crear_usuario(s, "Malena", "malena", "clave123")
        s.commit()
    yield engine
    engine.dispose()


@pytest.mark.parametrize("vista", VISTAS)
def test_vista_con_base_vacia(base_vacia, vista):
    at = _app(f"../vistas/{vista}.py").run()
    assert not at.exception, at.exception


def test_inicio_con_base_vacia(base_vacia):
    at = _app("../app.py").run()
    assert not at.exception, at.exception


def test_vuelve_de_activar_notificaciones(base_vacia, monkeypatch):
    from test_push import Respuesta, codigo_activacion
    from core.services import push
    monkeypatch.setattr(push.requests, "post", lambda *a, **k: Respuesta(201))  # la bienvenida no sale a internet
    at = _app("../app.py")
    at.query_params["push"] = codigo_activacion()
    at.run()
    assert not at.exception, at.exception
    with Session(base_vacia) as s:
        equipos = push.dispositivos(s)
    assert len(equipos) == 1 and equipos[0].nombre == "Android · Chrome"
