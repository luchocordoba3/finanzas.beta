"""Compras a proveedores: lista de compras → pedida → recibida (suma stock) → pagada."""
from datetime import date, datetime

import pandas as pd
from sqlalchemy import select

from ..models import Compra, CompraItem, Producto, Proveedor
from ..tiempo import hoy
from . import stock
from .util import df_query, nombre_producto

ABIERTAS = ("lista", "pedida", "parcial")


def _lista_de(s, proveedor_id: int | None, usuario_id: int | None) -> Compra:
    filtro = Compra.proveedor_id == proveedor_id if proveedor_id else Compra.proveedor_id.is_(None)
    compra = s.scalar(select(Compra).where(Compra.estado == "lista", filtro).order_by(Compra.id))
    if not compra:
        compra = Compra(proveedor_id=proveedor_id, estado="lista", usuario_id=usuario_id)
        s.add(compra)
        s.flush()
    return compra


def agregar_a_lista(s, producto_id: int, cantidad: float, usuario_id: int | None = None,
                    proveedor_id: int | None = None, costo_unitario: float | None = None,
                    pedido_item_id: int | None = None) -> CompraItem:
    """Anota un faltante en la lista de compras del proveedor (el habitual del producto si no se indica)."""
    if cantidad <= 0:
        raise ValueError("La cantidad tiene que ser mayor a cero.")
    p = s.get(Producto, producto_id)
    compra = _lista_de(s, proveedor_id or p.proveedor_id, usuario_id)
    costo = costo_unitario if costo_unitario is not None else (p.costo_ultimo or p.costo_promedio)
    if pedido_item_id is None:
        existente = next((i for i in compra.items if i.producto_id == producto_id and i.pedido_item_id is None), None)
        if existente:
            existente.cantidad = round(existente.cantidad + cantidad, 2)
            return existente
    item = CompraItem(producto_id=producto_id, cantidad=round(cantidad, 2), costo_unitario=costo,
                      pedido_item_id=pedido_item_id)
    compra.items.append(item)
    s.flush()
    return item


def productos_en_curso(s) -> set[int]:
    """Productos que ya están en una lista de compras o pedidos a un proveedor y todavía no llegaron."""
    return set(s.scalars(select(CompraItem.producto_id).join(Compra, Compra.id == CompraItem.compra_id)
                         .where(Compra.estado.in_(ABIERTAS), CompraItem.cantidad_recibida < CompraItem.cantidad)))


def crear_compra(s, proveedor_id: int | None, items: list[dict], usuario_id: int | None = None,
                 fecha_estimada: date | None = None, fecha_venc_pago: date | None = None, notas: str = "",
                 recibida: bool = False, fecha: datetime | None = None) -> Compra:
    """Compra directa. items: dicts con producto_id, cantidad y precio (costo unitario)."""
    items = [i for i in items if i.get("producto_id") and float(i.get("cantidad") or 0) > 0]
    if not items:
        raise ValueError("La compra no tiene productos del catálogo.")
    if not proveedor_id:
        raise ValueError("Elegí el proveedor.")
    c = Compra(proveedor_id=proveedor_id, estado="pedida", usuario_id=usuario_id, fecha_pedido=(fecha.date() if fecha else hoy()),
               fecha_estimada=fecha_estimada, fecha_venc_pago=fecha_venc_pago, notas=notas)
    for i in items:
        c.items.append(CompraItem(producto_id=int(i["producto_id"]), cantidad=float(i["cantidad"]),
                                  costo_unitario=float(i.get("precio") or 0)))
    s.add(c)
    s.flush()
    if recibida:
        recibir(s, c.id, {it.id: (it.cantidad, it.costo_unitario) for it in c.items}, usuario_id, fecha=fecha)
    return c


def actualizar_item(s, item_id: int, cantidad: float, costo_unitario: float) -> None:
    it = s.get(CompraItem, item_id)
    if it.compra.estado != "lista":
        raise ValueError("Solo se pueden editar las listas de compras.")
    if cantidad <= 0 or costo_unitario < 0:
        raise ValueError("Revisá la cantidad y el costo.")
    it.cantidad, it.costo_unitario = cantidad, costo_unitario


def quitar_item(s, item_id: int) -> None:
    it = s.get(CompraItem, item_id)
    compra = it.compra
    if compra.estado != "lista":
        raise ValueError("Solo se pueden quitar productos de una lista de compras.")
    compra.items.remove(it)
    if not compra.items:
        s.delete(compra)


def marcar_pedida(s, compra_id: int, proveedor_id: int | None = None, fecha_estimada: date | None = None) -> Compra:
    c = s.get(Compra, compra_id)
    if c.estado != "lista":
        raise ValueError("Esta compra ya fue pedida.")
    c.proveedor_id = proveedor_id or c.proveedor_id
    if not c.proveedor_id:
        raise ValueError("Elegí a qué proveedor se le pide.")
    if not c.items:
        raise ValueError("La lista está vacía.")
    otra = s.scalar(select(Compra).where(Compra.estado == "lista", Compra.proveedor_id == c.proveedor_id, Compra.id != c.id))
    if otra:  # se juntan las listas del mismo proveedor
        for it in list(otra.items):
            otra.items.remove(it)
            c.items.append(it)
        s.delete(otra)
    c.estado, c.fecha_pedido, c.fecha_estimada = "pedida", hoy(), fecha_estimada
    return c


def recibir(s, compra_id: int, recepciones: dict[int, tuple[float, float]], usuario_id: int | None = None,
            fecha: datetime | None = None, fecha_venc_pago: date | None = None) -> Compra:
    """recepciones: {item_id: (cantidad recibida ahora, costo unitario)}."""
    c = s.get(Compra, compra_id)
    if c.estado not in ABIERTAS:
        raise ValueError("Esta compra ya está cerrada.")
    recibido = 0.0
    for it in c.items:
        cantidad, costo = recepciones.get(it.id, (0, it.costo_unitario))
        if cantidad < 0 or costo < 0:
            raise ValueError("Las cantidades y costos no pueden ser negativos.")
        if cantidad == 0:
            continue
        it.cantidad_recibida, it.costo_unitario = round(it.cantidad_recibida + cantidad, 2), costo
        stock.mover(s, it.producto_id, cantidad, "compra", usuario_id, costo_unitario=costo,
                    ref_tipo="compra", ref_id=c.id, fecha=fecha)
        recibido += cantidad
    if not recibido:
        raise ValueError("No cargaste ninguna cantidad recibida.")
    c.estado = "recibida" if all(i.cantidad_recibida >= i.cantidad for i in c.items) else "parcial"
    c.fecha_recepcion = fecha.date() if fecha else hoy()
    c.fecha_pedido = c.fecha_pedido or c.fecha_recepcion
    c.fecha_venc_pago = fecha_venc_pago or c.fecha_venc_pago
    return c


def cerrar(s, compra_id: int) -> Compra:
    """Da por terminada una compra: si no llegó nada se cancela, si llegó una parte queda como recibida."""
    c = s.get(Compra, compra_id)
    if c.estado not in ABIERTAS:
        raise ValueError("Esta compra ya está cerrada.")
    c.estado = "recibida" if any(i.cantidad_recibida > 0 for i in c.items) else "cancelada"
    return c


def registrar_pago(s, compra_id: int, medio_pago: str, fecha_pago: date | None = None) -> Compra:
    c = s.get(Compra, compra_id)
    c.pagada, c.fecha_pago, c.medio_pago = True, fecha_pago or hoy(), medio_pago
    return c


def tabla(s, estados: tuple[str, ...] | None = None, proveedor_id: int | None = None) -> pd.DataFrame:
    q = (select(Compra.id, Compra.proveedor_id, Proveedor.nombre.label("proveedor"), Compra.estado, Compra.creado_en,
                Compra.fecha_pedido, Compra.fecha_estimada, Compra.fecha_recepcion, Compra.fecha_venc_pago,
                Compra.pagada, Compra.fecha_pago, Compra.medio_pago, Compra.notas)
         .outerjoin(Proveedor, Proveedor.id == Compra.proveedor_id).order_by(Compra.id.desc()))
    if estados:
        q = q.where(Compra.estado.in_(estados))
    if proveedor_id:
        q = q.where(Compra.proveedor_id == proveedor_id)
    df = df_query(s, q)
    df["proveedor"] = df["proveedor"].fillna("Sin proveedor asignado")
    it = items(s, df["id"].tolist())
    if it.empty:
        df["total"], df["detalle"] = 0.0, ""
        return df
    tot = it.groupby("compra_id")["importe"].sum()
    det = it.groupby("compra_id")["txt"].agg(", ".join)
    df["total"] = df["id"].map(tot).fillna(0.0)
    df["detalle"] = df["id"].map(det).fillna("")
    return df


def items(s, compra_ids: list[int]) -> pd.DataFrame:
    df = df_query(s, select(CompraItem.id, CompraItem.compra_id, CompraItem.producto_id, Producto.nombre,
                            Producto.presentacion, CompraItem.cantidad, CompraItem.cantidad_recibida,
                            CompraItem.costo_unitario, CompraItem.pedido_item_id, Compra.estado)
                  .join(Producto, Producto.id == CompraItem.producto_id).join(Compra, Compra.id == CompraItem.compra_id)
                  .where(CompraItem.compra_id.in_(compra_ids)).order_by(CompraItem.id))
    df["producto"] = [nombre_producto(n, p) for n, p in zip(df["nombre"], df["presentacion"])]
    recibida = df["estado"].isin(["parcial", "recibida"])
    df["importe"] = df["costo_unitario"] * df["cantidad_recibida"].where(recibida, df["cantidad"])
    df["pendiente"] = (df["cantidad"] - df["cantidad_recibida"]).clip(lower=0)
    df["txt"] = [f"{c:g}× {p}" for c, p in zip(df["cantidad"], df["producto"])]
    return df
