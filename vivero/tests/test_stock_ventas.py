import pytest

from core.constantes import CUENTA_CORRIENTE
from core.models import MovimientoStock
from core.services import catalogo, clientes, stock, ventas


def test_venta_descuenta_stock_y_anulacion_repone(s, nuevo_producto):
    p = nuevo_producto(stock=10)
    v = ventas.crear_venta(s, [{"producto_id": p.id, "cantidad": 3, "precio": 1000},
                               {"producto_id": None, "descripcion": "Envío", "cantidad": 1, "precio": 500}],
                           "Efectivo", descuento=500)
    assert (v.subtotal, v.total) == (3500, 3000)
    assert p.stock == 7
    assert v.items[0].costo_unitario == 400
    ventas.anular_venta(s, v.id)
    assert p.stock == 10 and v.estado == "anulada"
    with pytest.raises(ValueError):
        ventas.anular_venta(s, v.id)


def test_validaciones_de_venta(s, nuevo_producto):
    p = nuevo_producto()
    with pytest.raises(ValueError, match="cuenta corriente"):
        ventas.crear_venta(s, [{"producto_id": p.id, "cantidad": 1, "precio": 10}], CUENTA_CORRIENTE)
    with pytest.raises(ValueError, match="descuento"):
        ventas.crear_venta(s, [{"producto_id": p.id, "cantidad": 1, "precio": 10}], "Efectivo", descuento=50)
    with pytest.raises(ValueError, match="no tiene productos"):
        ventas.crear_venta(s, [], "Efectivo")


def test_compra_recalcula_costo_promedio(s, nuevo_producto):
    p = nuevo_producto(stock=10, costo=400)
    stock.mover(s, p.id, 10, "compra", costo_unitario=600)
    assert p.stock == 20 and p.costo_promedio == 500 and p.costo_ultimo == 600


def test_merma_y_ajuste(s, nuevo_producto):
    p = nuevo_producto(stock=10)
    stock.merma(s, p.id, 2, "Helada / clima")
    assert p.stock == 8
    m = s.query(MovimientoStock).filter_by(tipo="merma").one()
    assert m.cantidad == -2 and m.costo_unitario == 400 and m.motivo == "Helada / clima"
    stock.ajustar_a(s, p.id, 5)
    assert p.stock == 5
    assert stock.ajustar_a(s, p.id, 5) is None
    with pytest.raises(ValueError):
        stock.merma(s, p.id, 0, "Otro")


def test_tabla_productos_y_reposicion(s, nuevo_producto, cliente):
    from core.services import pedidos
    from core.tiempo import hoy
    p = nuevo_producto(stock=5, minimo=3)
    nuevo_producto(nombre="Tierra", stock=50, minimo=10)
    pedidos.crear_pedido(s, cliente.id, hoy(), [{"producto_id": p.id, "cantidad": 3, "precio": 1000}])
    df = stock.tabla_productos(s).set_index("nombre")
    assert df.at["Potus", "comprometido"] == 3 and df.at["Potus", "disponible"] == 2
    assert bool(df.at["Potus", "bajo_minimo"]) and not bool(df.at["Tierra", "bajo_minimo"])
    rep = stock.a_reponer(stock.tabla_productos(s))
    assert rep["sugerido"].tolist() == [4]


def test_producto_duplicado_y_precios(s, nuevo_producto):
    p = nuevo_producto(precio=1234)
    with pytest.raises(ValueError, match="Ya existe"):
        nuevo_producto()
    assert catalogo.redondear(1234 * 1.1, 100) == 1400
    prev = catalogo.vista_previa_aumento(stock.tabla_productos(s), 10, 100)
    catalogo.aplicar_precios(s, dict(zip(prev["id"], prev["nuevo"])))
    assert p.precio == 1400


def test_cuenta_corriente_y_deudores(s, nuevo_producto, cliente):
    from datetime import datetime
    p = nuevo_producto()
    ventas.crear_venta(s, [{"producto_id": p.id, "cantidad": 1, "precio": 1000}], CUENTA_CORRIENTE,
                       cliente_id=cliente.id, fecha=datetime(2026, 1, 10, 10))
    ventas.crear_venta(s, [{"producto_id": p.id, "cantidad": 2, "precio": 1000}], CUENTA_CORRIENTE,
                       cliente_id=cliente.id, fecha=datetime(2026, 2, 10, 10))
    assert clientes.saldo(s, cliente.id) == 3000
    clientes.registrar_cobro(s, cliente.id, 1500, "Efectivo")
    assert clientes.saldo(s, cliente.id) == 1500
    d = clientes.deudores(s).iloc[0]
    assert d["saldo"] == 1500 and str(d["desde"]) == "2026-02-10"  # lo de enero ya quedó pago
    t = clientes.tabla(s).iloc[0]
    assert t["compras"] == 2 and t["total_comprado"] == 3000 and t["saldo"] == 1500
