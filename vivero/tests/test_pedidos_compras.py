from datetime import timedelta

import pytest

from core.services import compras, pedidos, proveedores
from core.tiempo import hoy


def test_entregar_pedido_genera_venta_con_sena(s, nuevo_producto, cliente):
    p = nuevo_producto(stock=10)
    ped = pedidos.crear_pedido(s, cliente.id, hoy(), [{"producto_id": p.id, "cantidad": 2, "precio": 1000}], sena=500)
    v = pedidos.entregar(s, ped.id, "Efectivo")
    assert ped.estado == "entregado" and v.total == 2000 and v.sena_aplicada == 500 and v.pedido_id == ped.id
    assert p.stock == 8
    from core.services import ventas
    ventas.anular_venta(s, v.id)
    assert ped.estado == "listo" and p.stock == 10
    with pytest.raises(ValueError):
        pedidos.crear_pedido(s, cliente.id, hoy(), [{"producto_id": p.id, "cantidad": 1, "precio": 100}], sena=500)


def test_faltantes_reparte_stock_por_fecha(s, nuevo_producto, cliente):
    p = nuevo_producto(stock=3)
    tarde = pedidos.crear_pedido(s, cliente.id, hoy() + timedelta(days=5), [{"producto_id": p.id, "cantidad": 2, "precio": 1}])
    pedidos.crear_pedido(s, cliente.id, hoy() + timedelta(days=1), [{"producto_id": p.id, "cantidad": 2, "precio": 1}])
    f = pedidos.faltantes(s)
    assert len(f) == 1 and f.iloc[0]["pedido_id"] == tarde.id and f.iloc[0]["falta"] == 1


def test_encargo_de_item_libre_hasta_que_llega(s, nuevo_producto, cliente):
    prov = proveedores.guardar(s, {"nombre": "Mayorista"})
    ped = pedidos.crear_pedido(s, cliente.id, hoy() + timedelta(days=10),
                               [{"producto_id": None, "descripcion": "Olivo 2 m", "cantidad": 1, "precio": 90000}])
    item = ped.items[0]
    assert pedidos.faltantes(s).iloc[0]["encargado"] == False  # noqa: E712
    with pytest.raises(ValueError, match="catálogo"):
        pedidos.encargar_item(s, item.id)
    olivo = nuevo_producto(nombre="Olivo", presentacion="2 m", stock=0, costo=40000, proveedor_id=prov.id)
    ci = pedidos.encargar_item(s, item.id, producto_id=olivo.id)
    assert item.producto_id == olivo.id and ci.compra.proveedor_id == prov.id and ci.compra.estado == "lista"
    assert bool(pedidos.faltantes(s).iloc[0]["encargado"])
    compras.marcar_pedida(s, ci.compra.id, fecha_estimada=hoy())
    compras.recibir(s, ci.compra.id, {ci.id: (1, 42000)})
    assert olivo.stock == 1 and ci.compra.estado == "recibida"
    assert pedidos.faltantes(s).empty
    assert pedidos.encargos_recibidos(s).iloc[0]["pedido_id"] == ped.id


def test_lista_de_compras_recepcion_parcial_y_pago(s, nuevo_producto):
    p = nuevo_producto(stock=0, costo=100)
    i1 = compras.agregar_a_lista(s, p.id, 5)
    compras.agregar_a_lista(s, p.id, 5)
    assert i1.cantidad == 10 and i1.compra.proveedor_id is None
    with pytest.raises(ValueError, match="proveedor"):
        compras.marcar_pedida(s, i1.compra.id)
    prov = proveedores.guardar(s, {"nombre": "Semillería"})
    c = compras.marcar_pedida(s, i1.compra.id, proveedor_id=prov.id)
    compras.recibir(s, c.id, {i1.id: (6, 120)})
    assert c.estado == "parcial" and p.stock == 6 and c.total == 720
    compras.cerrar(s, c.id)
    assert c.estado == "recibida"
    compras.registrar_pago(s, c.id, "Transferencia")
    t = compras.tabla(s).iloc[0]
    assert bool(t["pagada"]) and t["total"] == 720


def test_compra_directa_recibida(s, nuevo_producto):
    p = nuevo_producto(stock=0, costo=0)
    prov = proveedores.guardar(s, {"nombre": "Mercado"})
    c = compras.crear_compra(s, prov.id, [{"producto_id": p.id, "cantidad": 4, "precio": 250}], recibida=True)
    assert c.estado == "recibida" and p.stock == 4 and p.costo_promedio == 250
    assert proveedores.tabla(s).iloc[0]["total_comprado"] == 1000
