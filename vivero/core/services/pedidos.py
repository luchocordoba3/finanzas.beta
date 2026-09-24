"""Pedidos y encargos de clientes: pendiente → listo → entregado (se convierte en venta)."""
from datetime import date, datetime

import pandas as pd
from sqlalchemy import case, select

from ..constantes import PEDIDO_ABIERTO
from ..models import Cliente, Compra, CompraItem, Pedido, PedidoItem, Producto
from ..tiempo import hoy
from . import avisos, compras, ventas
from .util import df_query


def crear_pedido(s, cliente_id: int, fecha_entrega: date, items: list[dict], usuario_id: int | None = None,
                 entrega: str = "Retira", direccion: str = "", sena: float = 0, notas: str = "") -> Pedido:
    if not cliente_id:
        raise ValueError("Elegí el cliente del pedido.")
    items = [i for i in items if float(i.get("cantidad") or 0) > 0]
    if not items:
        raise ValueError("El pedido no tiene productos.")
    if sena < 0:
        raise ValueError("La seña no puede ser negativa.")
    p = Pedido(cliente_id=cliente_id, fecha_entrega=fecha_entrega, entrega=entrega, direccion=direccion.strip(),
               sena=round(sena, 2), notas=notas.strip(), usuario_id=usuario_id)
    for i in items:
        pid = int(i["producto_id"]) if i.get("producto_id") else None
        descripcion = str(i.get("descripcion") or "").strip() or (s.get(Producto, pid).nombre_completo if pid else "")
        if not descripcion:
            raise ValueError("Hay un ítem sin descripción.")
        p.items.append(PedidoItem(producto_id=pid, descripcion=descripcion, cantidad=float(i["cantidad"]),
                                  precio_unitario=float(i.get("precio") or 0)))
    if p.sena > p.total:
        raise ValueError("La seña no puede superar el total del pedido.")
    s.add(p)
    s.flush()
    detalle = ", ".join(f"{i.cantidad:g}× {i.descripcion}" for i in p.items)
    avisos.encolar(s, f"📦 Pedido nuevo #{p.id} de <b>{avisos.e(s.get(Cliente, cliente_id).nombre)}</b> para el "
                      f"{fecha_entrega:%d/%m}: {avisos.e(detalle)}", excepto=usuario_id)
    return p


def cambiar_estado(s, pedido_id: int, estado: str) -> Pedido:
    p = s.get(Pedido, pedido_id)
    if estado not in ("pendiente", "listo", "cancelado"):
        raise ValueError("Estado inválido.")
    if p.estado not in PEDIDO_ABIERTO:
        raise ValueError("El pedido ya está cerrado.")
    p.estado = estado
    return p


def entregar(s, pedido_id: int, medio_pago: str, usuario_id: int | None = None, descuento: float = 0,
             fecha: datetime | None = None):
    """Entrega el pedido: genera la venta (descuenta stock) aplicando la seña ya cobrada."""
    p = s.get(Pedido, pedido_id)
    if p.estado not in PEDIDO_ABIERTO:
        raise ValueError("El pedido no está abierto.")
    items = [{"producto_id": i.producto_id, "descripcion": i.descripcion, "cantidad": i.cantidad,
              "precio": i.precio_unitario} for i in p.items]
    v = ventas.crear_venta(s, items, medio_pago, usuario_id, p.cliente_id, descuento, notas=f"Pedido #{p.id}",
                           pedido_id=p.id, sena_aplicada=p.sena, fecha=fecha)
    p.estado = "entregado"
    return v


def encargar_item(s, pedido_item_id: int, usuario_id: int | None = None, producto_id: int | None = None,
                  proveedor_id: int | None = None, cantidad: float | None = None) -> CompraItem:
    """Manda un ítem del pedido a la lista de compras. Si no estaba en el catálogo, se vincula al producto elegido."""
    it = s.get(PedidoItem, pedido_item_id)
    if it.producto_id is None:
        if not producto_id:
            raise ValueError("Elegí (o creá) el producto del catálogo que vas a encargar.")
        it.producto_id = producto_id
    return compras.agregar_a_lista(s, it.producto_id, cantidad or it.cantidad, usuario_id,
                                   proveedor_id=proveedor_id, pedido_item_id=it.id)


def tabla(s, estados: tuple[str, ...] | None = None, desde: date | None = None, hasta: date | None = None,
          cliente_id: int | None = None) -> pd.DataFrame:
    q = (select(Pedido.id, Pedido.cliente_id, Cliente.nombre.label("cliente"), Cliente.telefono,
                Cliente.tipo.label("tipo_cliente"), Pedido.creado_en,
                Pedido.fecha_entrega, Pedido.estado, Pedido.entrega, Pedido.direccion, Pedido.sena, Pedido.notas)
         .join(Cliente, Cliente.id == Pedido.cliente_id).order_by(Pedido.fecha_entrega, Pedido.id))
    if estados:
        q = q.where(Pedido.estado.in_(estados))
    if desde:
        q = q.where(Pedido.fecha_entrega >= desde)
    if hasta:
        q = q.where(Pedido.fecha_entrega <= hasta)
    if cliente_id:
        q = q.where(Pedido.cliente_id == cliente_id)
    df = df_query(s, q)
    it = df_query(s, select(PedidoItem.pedido_id, PedidoItem.descripcion, PedidoItem.cantidad, PedidoItem.precio_unitario)
                  .where(PedidoItem.pedido_id.in_(df["id"].tolist())))
    it["importe"] = it["cantidad"] * it["precio_unitario"]
    it["txt"] = [f"{c:g}× {d}" for c, d in zip(it["cantidad"], it["descripcion"])]
    df["total"] = df["id"].map(it.groupby("pedido_id")["importe"].sum()).fillna(0.0).astype(float)
    df["detalle"] = df["id"].map(it.groupby("pedido_id")["txt"].agg(", ".join)).fillna("")
    df["dias"] = [(f - hoy()).days for f in df["fecha_entrega"]]
    return df


def faltantes(s) -> pd.DataFrame:
    """Ítems de pedidos abiertos que no se cubren con el stock actual.
    El stock se reparte primero a los pedidos listos y después por fecha de entrega."""
    q = (select(PedidoItem.id.label("pedido_item_id"), PedidoItem.pedido_id, PedidoItem.producto_id,
                PedidoItem.descripcion, PedidoItem.cantidad, Pedido.fecha_entrega, Pedido.estado,
                Cliente.nombre.label("cliente"))
         .join(Pedido, Pedido.id == PedidoItem.pedido_id).join(Cliente, Cliente.id == Pedido.cliente_id)
         .where(Pedido.estado.in_(PEDIDO_ABIERTO))
         .order_by(case((Pedido.estado == "listo", 0), else_=1), Pedido.fecha_entrega, Pedido.id))
    it = df_query(s, q)
    columnas = list(it.columns) + ["falta", "encargado"]
    if it.empty:
        return pd.DataFrame(columns=columnas)
    ids = [int(i) for i in it["producto_id"].dropna().unique()]
    disponible = {pid: max(float(st), 0) for pid, st in s.execute(select(Producto.id, Producto.stock).where(Producto.id.in_(ids)))}
    encargados = set(s.scalars(select(CompraItem.pedido_item_id).join(Compra, Compra.id == CompraItem.compra_id)
                               .where(CompraItem.pedido_item_id.in_(it["pedido_item_id"].tolist()),
                                      Compra.estado.in_(compras.ABIERTAS))))
    filas = []
    for fila in it.to_dict("records"):
        pid = fila["producto_id"]
        if pd.isna(pid):
            falta = fila["cantidad"]
        else:
            usa = min(disponible[int(pid)], fila["cantidad"])
            disponible[int(pid)] -= usa
            falta = round(fila["cantidad"] - usa, 2)
        if falta > 0:
            filas.append({**fila, "falta": falta, "encargado": fila["pedido_item_id"] in encargados})
    return pd.DataFrame(filas, columns=columnas)


def encargos_recibidos(s) -> pd.DataFrame:
    """Pedidos pendientes cuya mercadería encargada ya llegó: hay que avisarle al cliente."""
    return df_query(s, select(Pedido.id.label("pedido_id"), Cliente.nombre.label("cliente"), Cliente.telefono,
                              Cliente.tipo.label("tipo_cliente"), PedidoItem.descripcion, Pedido.fecha_entrega)
                    .join(PedidoItem, PedidoItem.pedido_id == Pedido.id)
                    .join(CompraItem, CompraItem.pedido_item_id == PedidoItem.id)
                    .join(Cliente, Cliente.id == Pedido.cliente_id)
                    .where(Pedido.estado == "pendiente", CompraItem.cantidad_recibida > 0)
                    .distinct().order_by(Pedido.fecha_entrega))


def detalle(s, pedido_id: int) -> Pedido:
    return s.get(Pedido, pedido_id)
