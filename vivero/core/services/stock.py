"""Stock: todo cambio pasa por `mover`, que actualiza el producto y deja el movimiento registrado."""
from datetime import date, datetime, time

import pandas as pd
from sqlalchemy import func, select

from ..constantes import PEDIDO_ABIERTO
from ..models import Categoria, MovimientoStock, Pedido, PedidoItem, Producto, Proveedor, Usuario
from ..tiempo import ahora
from .util import df_query, nombre_producto

ENTRADAS_CON_COSTO = {"inicial", "compra", "produccion"}  # recalculan el costo promedio


def mover(s, producto_id: int, cantidad: float, tipo: str, usuario_id: int | None = None,
          costo_unitario: float | None = None, motivo: str = "", ref_tipo: str = "",
          ref_id: int | None = None, notas: str = "", fecha: datetime | None = None) -> MovimientoStock:
    # FOR UPDATE: si los dos cargan algo a la vez sobre el mismo producto, no se pisan (Postgres).
    p = s.get(Producto, producto_id, with_for_update=True, populate_existing=True)
    if p is None:
        raise ValueError("El producto no existe.")
    cantidad = round(float(cantidad), 2)
    if cantidad == 0:
        raise ValueError("La cantidad no puede ser cero.")
    if tipo in ENTRADAS_CON_COSTO and costo_unitario is not None and cantidad > 0:
        base = max(p.stock, 0)
        p.costo_promedio = round((base * p.costo_promedio + cantidad * costo_unitario) / (base + cantidad), 2)
        p.costo_ultimo = costo_unitario
    costo = p.costo_promedio if costo_unitario is None else costo_unitario
    p.stock = round(p.stock + cantidad, 2)
    m = MovimientoStock(producto_id=p.id, fecha=fecha or ahora(), tipo=tipo, cantidad=cantidad, costo_unitario=costo,
                        motivo=motivo, ref_tipo=ref_tipo, ref_id=ref_id, usuario_id=usuario_id, notas=notas)
    s.add(m)
    return m


def merma(s, producto_id: int, cantidad: float, motivo: str, usuario_id: int | None = None,
          notas: str = "", fecha: datetime | None = None) -> MovimientoStock:
    if cantidad <= 0:
        raise ValueError("La cantidad perdida tiene que ser mayor a cero.")
    return mover(s, producto_id, -cantidad, "merma", usuario_id, motivo=motivo, notas=notas, fecha=fecha)


def ajustar_a(s, producto_id: int, stock_real: float, usuario_id: int | None = None, notas: str = ""):
    """Ajuste por conteo: deja el stock en lo que realmente hay."""
    if stock_real < 0:
        raise ValueError("El stock contado no puede ser negativo.")
    diferencia = round(stock_real - s.get(Producto, producto_id).stock, 2)
    if diferencia == 0:
        return None
    return mover(s, producto_id, diferencia, "ajuste", usuario_id, motivo="Conteo de inventario", notas=notas)


def comprometido(s) -> dict[int, float]:
    """Unidades reservadas por pedidos abiertos, por producto."""
    q = (select(PedidoItem.producto_id, func.sum(PedidoItem.cantidad))
         .join(Pedido, Pedido.id == PedidoItem.pedido_id)
         .where(Pedido.estado.in_(PEDIDO_ABIERTO), PedidoItem.producto_id.is_not(None))
         .group_by(PedidoItem.producto_id))
    return {pid: float(c) for pid, c in s.execute(q)}


def tabla_productos(s, solo_activos: bool = True) -> pd.DataFrame:
    q = (select(Producto.id, Producto.codigo, Producto.nombre, Producto.presentacion, Producto.unidad,
                Producto.categoria_id, Categoria.nombre.label("categoria"), Categoria.tipo.label("tipo"),
                Categoria.margen_objetivo, Producto.planta_id, Producto.proveedor_id,
                Proveedor.nombre.label("proveedor"), Producto.precio, Producto.costo_promedio,
                Producto.costo_ultimo, Producto.stock, Producto.stock_minimo, Producto.ubicacion, Producto.activo)
         .outerjoin(Categoria, Producto.categoria_id == Categoria.id)
         .outerjoin(Proveedor, Producto.proveedor_id == Proveedor.id)
         .order_by(Producto.nombre, Producto.presentacion))
    if solo_activos:
        q = q.where(Producto.activo.is_(True))
    df = df_query(s, q)
    df["producto"] = [nombre_producto(n, p) for n, p in zip(df["nombre"], df["presentacion"])]
    df["categoria"] = df["categoria"].fillna("Sin categoría")
    df["proveedor"] = df["proveedor"].fillna("")
    df["comprometido"] = df["id"].map(comprometido(s)).fillna(0.0).astype(float)
    df["disponible"] = df["stock"] - df["comprometido"]
    df["bajo_minimo"] = (df["stock_minimo"] > 0) & (df["disponible"] <= df["stock_minimo"])
    df["valor_costo"] = df["stock"].clip(lower=0) * df["costo_promedio"]
    return df


def a_reponer(df_productos: pd.DataFrame) -> pd.DataFrame:
    """Productos bajo el mínimo, con una cantidad sugerida (llevar al doble del mínimo)."""
    df = df_productos[df_productos["bajo_minimo"]].copy()
    df["sugerido"] = (2 * df["stock_minimo"] - df["disponible"]).clip(lower=1).round(0)
    return df


def movimientos(s, producto_id: int | None = None, desde: date | None = None, hasta: date | None = None,
                tipos: list[str] | None = None, limite: int = 300) -> pd.DataFrame:
    q = (select(MovimientoStock.fecha, MovimientoStock.tipo, Producto.nombre, Producto.presentacion,
                MovimientoStock.cantidad, MovimientoStock.costo_unitario, MovimientoStock.motivo,
                MovimientoStock.notas, Usuario.nombre.label("usuario"), MovimientoStock.producto_id)
         .join(Producto, Producto.id == MovimientoStock.producto_id)
         .outerjoin(Usuario, Usuario.id == MovimientoStock.usuario_id)
         .order_by(MovimientoStock.fecha.desc(), MovimientoStock.id.desc()).limit(limite))
    if producto_id:
        q = q.where(MovimientoStock.producto_id == producto_id)
    if desde:
        q = q.where(MovimientoStock.fecha >= datetime.combine(desde, time.min))
    if hasta:
        q = q.where(MovimientoStock.fecha <= datetime.combine(hasta, time.max))
    if tipos:
        q = q.where(MovimientoStock.tipo.in_(tipos))
    df = df_query(s, q)
    df["producto"] = [nombre_producto(n, p) for n, p in zip(df["nombre"], df["presentacion"])]
    return df
