from datetime import date, datetime, time

import pandas as pd
from sqlalchemy import select

from ..constantes import CUENTA_CORRIENTE
from ..models import Cliente, Pedido, Producto, Usuario, Venta, VentaItem
from ..tiempo import ahora
from . import stock
from .util import df_query


def crear_venta(s, items: list[dict], medio_pago: str, usuario_id: int | None = None, cliente_id: int | None = None,
                descuento: float = 0, notas: str = "", pedido_id: int | None = None, sena_aplicada: float = 0,
                fecha: datetime | None = None) -> Venta:
    """items: dicts con producto_id (o None para servicios/ítems libres), descripcion, cantidad y precio."""
    items = [i for i in items if float(i.get("cantidad") or 0) > 0]
    if not items:
        raise ValueError("La venta no tiene productos.")
    if not medio_pago:
        raise ValueError("Elegí el medio de pago.")
    if medio_pago == CUENTA_CORRIENTE and not cliente_id:
        raise ValueError("Para vender a cuenta corriente elegí un cliente.")
    for i in items:
        if float(i.get("precio") or 0) < 0:
            raise ValueError("Hay precios negativos.")
        if not i.get("producto_id") and not str(i.get("descripcion") or "").strip():
            raise ValueError("Hay un ítem sin descripción.")
    subtotal = round(sum(float(i["cantidad"]) * float(i["precio"]) for i in items), 2)
    descuento = round(float(descuento or 0), 2)
    if not 0 <= descuento <= subtotal:
        raise ValueError("El descuento no puede ser negativo ni mayor al total.")
    total = round(subtotal - descuento, 2)
    if sena_aplicada > total:
        raise ValueError("La seña es mayor que el total a cobrar.")
    fecha = fecha or ahora()
    v = Venta(fecha=fecha, cliente_id=cliente_id, usuario_id=usuario_id, medio_pago=medio_pago, subtotal=subtotal,
              descuento=descuento, total=total, sena_aplicada=round(float(sena_aplicada or 0), 2),
              pedido_id=pedido_id, notas=notas)
    s.add(v)
    s.flush()
    for i in items:
        pid, costo, descripcion = i.get("producto_id"), 0.0, str(i.get("descripcion") or "").strip()
        if pid:
            p = s.get(Producto, int(pid))
            costo, descripcion = p.costo_promedio, descripcion or p.nombre_completo
            stock.mover(s, p.id, -float(i["cantidad"]), "venta", usuario_id, ref_tipo="venta", ref_id=v.id, fecha=fecha)
        v.items.append(VentaItem(producto_id=int(pid) if pid else None, descripcion=descripcion,
                                 cantidad=float(i["cantidad"]), precio_unitario=float(i["precio"]), costo_unitario=costo))
    s.flush()
    return v


def anular_venta(s, venta_id: int, usuario_id: int | None = None, motivo: str = "") -> Venta:
    v = s.get(Venta, venta_id)
    if v is None or v.estado == "anulada":
        raise ValueError("La venta no existe o ya estaba anulada.")
    for it in v.items:
        if it.producto_id:
            stock.mover(s, it.producto_id, it.cantidad, "anulacion", usuario_id, costo_unitario=it.costo_unitario,
                        ref_tipo="venta", ref_id=v.id, notas=motivo)
    v.estado, v.anulada_en, v.anulada_por = "anulada", ahora(), usuario_id
    if v.pedido_id:  # el pedido vuelve a quedar para entregar
        pedido = s.get(Pedido, v.pedido_id)
        if pedido.estado == "entregado":
            pedido.estado = "listo"
    return v


def _filtros(desde: date | None, hasta: date | None, cliente_id: int | None) -> list:
    f = []
    if desde:
        f.append(Venta.fecha >= datetime.combine(desde, time.min))
    if hasta:
        f.append(Venta.fecha <= datetime.combine(hasta, time.max))
    if cliente_id:
        f.append(Venta.cliente_id == cliente_id)
    return f


def tabla_ventas(s, desde: date | None = None, hasta: date | None = None, cliente_id: int | None = None) -> pd.DataFrame:
    filtros = _filtros(desde, hasta, cliente_id)
    df = df_query(s, select(Venta.id, Venta.fecha, Cliente.nombre.label("cliente"), Venta.medio_pago, Venta.subtotal,
                            Venta.descuento, Venta.total, Venta.sena_aplicada, Venta.estado, Venta.pedido_id,
                            Usuario.nombre.label("usuario"), Venta.notas)
                  .outerjoin(Cliente, Cliente.id == Venta.cliente_id)
                  .outerjoin(Usuario, Usuario.id == Venta.usuario_id)
                  .where(*filtros).order_by(Venta.fecha.desc(), Venta.id.desc()))
    df["cliente"] = df["cliente"].fillna("Consumidor final")
    items = df_query(s, select(VentaItem.venta_id, VentaItem.descripcion, VentaItem.cantidad)
                     .join(Venta, Venta.id == VentaItem.venta_id).where(*filtros))
    if not items.empty:
        items["txt"] = [f"{c:g}× {d}" for c, d in zip(items["cantidad"], items["descripcion"])]
        df["detalle"] = df["id"].map(items.groupby("venta_id")["txt"].agg(", ".join)).fillna("")
    else:
        df["detalle"] = ""
    return df


def detalle(s, venta_id: int) -> Venta:
    return s.get(Venta, venta_id)
