import pytest
from sqlalchemy.orm import Session

from core.db import crear_engine, init_db
from core.services import catalogo, clientes


@pytest.fixture
def s():
    engine = crear_engine("sqlite://")
    init_db(engine)
    with Session(engine) as sesion:
        yield sesion


@pytest.fixture
def nuevo_producto(s):
    def crear(nombre="Potus", precio=1000.0, costo=400.0, stock=10, minimo=0, **extra):
        return catalogo.crear_producto(s, {"nombre": nombre, "precio": precio, "stock_minimo": minimo, **extra},
                                       stock_inicial=stock, costo=costo)
    return crear


@pytest.fixture
def cliente(s):
    return clientes.guardar(s, {"nombre": "Ana Pérez", "telefono": "11 5555-1234"})
