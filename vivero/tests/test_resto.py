from datetime import datetime, timedelta

import pandas as pd
import pytest

from core.services import (alertas, clientes, compras, config, documentos, estadisticas, importar, pedidos,
                           produccion, proveedores, recordatorios, stock, ventas)
from core.constantes import CUENTA_CORRIENTE
from core.tiempo import hoy


def test_alertas_del_panel(s, nuevo_producto, cliente):
    ref = hoy()
    p = nuevo_producto(stock=2, minimo=5)
    pedidos.crear_pedido(s, cliente.id, ref - timedelta(days=1), [{"producto_id": p.id, "cantidad": 1, "precio": 1}])
    pedidos.crear_pedido(s, cliente.id, ref, [{"producto_id": p.id, "cantidad": 3, "precio": 1}])
    recordatorios.crear(s, "Regar el sector B", ref)
    prov = proveedores.guardar(s, {"nombre": "Mayorista"})
    c = compras.crear_compra(s, prov.id, [{"producto_id": p.id, "cantidad": 1, "precio": 100}], recibida=True,
                             fecha_venc_pago=ref + timedelta(days=1))
    c.fecha_venc_pago = ref + timedelta(days=1)
    ventas.crear_venta(s, [{"producto_id": p.id, "cantidad": 1, "precio": 500}], CUENTA_CORRIENTE,
                       cliente_id=cliente.id, fecha=datetime.combine(ref - timedelta(days=40), datetime.min.time()))
    todas = alertas.calcular(s)
    grupos = {a.grupo for a in todas}
    assert {"Pedidos atrasados", "Pedidos para entregar", "Faltantes para pedidos", "Stock bajo mínimo",
            "Recordatorios", "Pagos a proveedores", "Cuentas corrientes"} <= grupos
    assert todas[0].nivel == "urgente"
    assert alertas.contar(todas) >= 5


def test_recordatorio_que_se_repite(s):
    r = recordatorios.crear(s, "Fertilizar", hoy() - timedelta(days=10), repeticion="semanal")
    proximo = recordatorios.completar(s, r.id)
    assert r.hecho and proximo.fecha > hoy() and proximo.fecha - r.fecha == timedelta(days=14)
    assert recordatorios.tabla(s)["titulo"].tolist() == ["Fertilizar"]


def test_estadisticas_de_ventas_y_plantas(s, nuevo_producto, cliente):
    potus = nuevo_producto(stock=50, costo=400, precio=1000)
    tierra = nuevo_producto(nombre="Tierra", stock=50, costo=100, precio=300)
    d = datetime(2026, 3, 2, 11)  # lunes
    ventas.crear_venta(s, [{"producto_id": potus.id, "cantidad": 2, "precio": 1000}], "Efectivo", fecha=d)
    ventas.crear_venta(s, [{"producto_id": tierra.id, "cantidad": 1, "precio": 300},
                           {"producto_id": potus.id, "cantidad": 1, "precio": 1000}], "Transferencia",
                       cliente_id=cliente.id, descuento=130, fecha=d + timedelta(days=1))
    stock.merma(s, potus.id, 3, "Plaga", fecha=d)
    desde, hasta = d.date(), d.date() + timedelta(days=30)
    v, it = estadisticas.ventas_df(s, desde, hasta), estadisticas.items_df(s, desde, hasta)
    k = estadisticas.kpis(v, it)
    assert k["facturacion"] == 3170 and k["ventas"] == 2 and k["ticket"] == 1585
    assert k["margen"] == 3170 - (3 * 400 + 100)
    assert it["importe"].sum() == pytest.approx(3170)
    r = estadisticas.ranking(it)
    assert r.iloc[0]["planta"] == "Potus" and r.iloc[0]["unidades"] == 3
    assert estadisticas.serie(v, "M")["facturacion"].tolist() == [3170]
    m = estadisticas.mermas(s, desde, hasta)
    assert m["valor"].sum() == 1200 and m.iloc[0]["motivo"] == "Plaga"
    cr = estadisticas.clientes_resumen(s, v, desde, ref=hasta)
    assert cr["nuevos"] == 1 and cr["sin_cliente"] == 1
    rot = estadisticas.rotacion(s, stock.tabla_productos(s), it, desde, hasta, ref=hasta).set_index("producto")
    assert rot.at["Potus", "vendidas"] == 3
    assert estadisticas.valor_stock(stock.tabla_productos(s))["unidades"] == 44 + 49
    assert not estadisticas.dia_hora(v).empty
    assert set(estadisticas.estacionalidad(s, ref=hasta)["planta"]) == {"Potus", "Tierra"}


def test_alerta_de_temporada(s, nuevo_producto):
    p = nuevo_producto(stock=100)
    ref = hoy()
    hace_un_anio = datetime.combine(ref - timedelta(days=360), datetime.min.time())
    ventas.crear_venta(s, [{"producto_id": p.id, "cantidad": 1, "precio": 1}], "Efectivo",
                       fecha=hace_un_anio - timedelta(days=30))
    ventas.crear_venta(s, [{"producto_id": p.id, "cantidad": 20, "precio": 1}], "Efectivo", fecha=hace_un_anio)
    stock.ajustar_a(s, p.id, 4)
    t = estadisticas.alertas_temporada(s, ref)
    assert t.iloc[0]["vendido"] == 20 and t.iloc[0]["disponible"] == 4


def test_importar_productos_y_clientes(s):
    df = pd.DataFrame([{"nombre": "Lavanda", "presentacion": "Maceta 12", "categoria": "Aromáticas y huerta",
                        "precio": "1.234,50", "costo": "600", "stock": "12", "stock_minimo": "4",
                        "proveedor": "Vivero Sur", "tipo": ""},
                       {"nombre": "Maceta plástica", "presentacion": "N° 14", "categoria": "Nueva categoría",
                        "tipo": "Insumo", "precio": "abc"},
                       {"nombre": "Lavanda", "presentacion": "Maceta 12", "precio": "1"}])
    creados, errores = importar.importar_productos(s, df)
    assert creados == 1 and len(errores) == 2
    p = stock.tabla_productos(s).iloc[0]
    assert (p["precio"], p["stock"], p["proveedor"], p["costo_promedio"]) == (1234.5, 12, "Vivero Sur", 600)
    assert p["planta_id"] is not None and not pd.isna(p["planta_id"])
    creados, errores = importar.importar_clientes(s, pd.DataFrame([{"nombre": "Juan", "tipo": "paisajista"},
                                                                   {"nombre": "juan"}]))
    assert creados == 1 and len(errores) == 1
    assert clientes.tabla(s).iloc[0]["tipo"] == "Paisajista"
    assert importar.plantilla(importar.COLUMNAS_CLIENTES, importar.EJEMPLO_CLIENTES)[:2] == b"PK"


def test_produccion_propia(s, nuevo_producto):
    from core.services import catalogo
    planta = catalogo.guardar_planta(s, {"nombre_comun": "Salvia"})
    prod = nuevo_producto(nombre="Salvia", presentacion="Plantín", stock=0, costo=0, planta_id=planta.id)
    lote = produccion.crear_lote(s, planta.id, "Esqueje / estaca", 100, costo_total=5000)
    produccion.registrar_perdida(s, lote.id, 10, "Hongos")
    produccion.pasar_a_stock(s, lote.id, 50, producto_id=prod.id)
    assert prod.stock == 50 and prod.costo_promedio == 50 and lote.cantidad_actual == 40
    with pytest.raises(ValueError):
        produccion.pasar_a_stock(s, lote.id, 41)
    produccion.terminar(s, lote.id)
    st = estadisticas.produccion(s).iloc[0]
    assert lote.estado == "terminado" and st["exito_pct"] == 50 and st["perdidas"] == 50
    assert st["costo_por_planta"] == 100


def test_documentos_y_config(s, nuevo_producto, cliente):
    p = nuevo_producto(nombre="Jazmín del país — especial")
    v = ventas.crear_venta(s, [{"producto_id": p.id, "cantidad": 1, "precio": 1000}], "Efectivo", cliente_id=cliente.id)
    assert documentos.comprobante_venta(v, config.todos(s))[:4] == b"%PDF"
    assert documentos.backup_excel(s)[:2] == b"PK"
    config.guardar(s, {"dias_aviso": "7", "modulo_produccion": "1"})
    assert config.entero(s, "dias_aviso") == 7 and config.produccion_activa(s)
    assert "Cuenta corriente" in config.medios_pago(s)
