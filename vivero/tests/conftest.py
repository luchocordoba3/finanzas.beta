import os

import pytest
from sqlalchemy.orm import Session

from core.db import crear_engine, init_db
from core.models import Base
from core.services import catalogo, clientes

# Por defecto SQLite en memoria. Para probar contra Postgres (como Neon):
#   TEST_DATABASE_URL=postgresql://usuario@host:puerto/base python -m pytest vivero
URL_PRUEBAS = os.environ.get("TEST_DATABASE_URL", "sqlite://")


def base_limpia(url: str = URL_PRUEBAS):
    engine = crear_engine(url)
    Base.metadata.drop_all(engine)
    init_db(engine)
    return engine


@pytest.fixture
def s():
    engine = base_limpia()
    with Session(engine) as sesion:
        yield sesion
    engine.dispose()


@pytest.fixture
def nuevo_producto(s):
    def crear(nombre="Potus", precio=1000.0, costo=400.0, stock=10, minimo=0, **extra):
        return catalogo.crear_producto(s, {"nombre": nombre, "precio": precio, "stock_minimo": minimo, **extra},
                                       stock_inicial=stock, costo=costo)
    return crear


@pytest.fixture
def cliente(s):
    return clientes.guardar(s, {"nombre": "Ana Pérez", "telefono": "11 5555-1234"})
