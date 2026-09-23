import pandas as pd
from sqlalchemy import func, select

from ..models import Compra, CompraItem, Proveedor
from .util import df_query

CAMPOS = ("nombre", "contacto", "telefono", "email", "direccion", "rubro", "dias_entrega", "condiciones_pago",
          "cuit", "notas", "activo")


def guardar(s, datos: dict, proveedor_id: int | None = None) -> Proveedor:
    datos = {k: (v.strip() if isinstance(v, str) else v) for k, v in datos.items() if k in CAMPOS}
    if not datos.get("nombre", "sin cambio" if proveedor_id else ""):
        raise ValueError("El nombre del proveedor es obligatorio.")
    p = s.get(Proveedor, proveedor_id) if proveedor_id else Proveedor()
    for k, v in datos.items():
        setattr(p, k, v)
    s.add(p)
    s.flush()
    return p


def listar(s, solo_activos: bool = True) -> list[Proveedor]:
    q = select(Proveedor).order_by(Proveedor.nombre)
    if solo_activos:
        q = q.where(Proveedor.activo.is_(True))
    return list(s.scalars(q))


def buscar_o_crear(s, nombre: str) -> Proveedor:
    p = s.scalar(select(Proveedor).where(func.lower(Proveedor.nombre) == nombre.strip().lower()))
    return p or guardar(s, {"nombre": nombre})


def tabla(s, solo_activos: bool = True) -> pd.DataFrame:
    q = select(Proveedor.id, Proveedor.nombre, Proveedor.contacto, Proveedor.telefono, Proveedor.email, Proveedor.rubro,
               Proveedor.dias_entrega, Proveedor.condiciones_pago, Proveedor.activo).order_by(Proveedor.nombre)
    df = df_query(s, q.where(Proveedor.activo.is_(True)) if solo_activos else q)
    compras = df_query(s, select(Compra.proveedor_id, Compra.fecha_recepcion,
                                 (CompraItem.cantidad_recibida * CompraItem.costo_unitario).label("importe"))
                       .join(CompraItem, CompraItem.compra_id == Compra.id)
                       .where(Compra.estado.in_(("parcial", "recibida"))))
    tot = compras.groupby("proveedor_id").agg(total_comprado=("importe", "sum"), ultima_compra=("fecha_recepcion", "max"))
    return df.merge(tot, left_on="id", right_index=True, how="left").fillna({"total_comprado": 0.0})
