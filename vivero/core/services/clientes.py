from datetime import date, datetime

import pandas as pd
from sqlalchemy import func, select

from ..constantes import CUENTA_CORRIENTE
from ..models import Cliente, Cobro, Usuario, Venta
from ..tiempo import ahora, hoy
from .util import df_query

CAMPOS = ("nombre", "telefono", "email", "direccion", "localidad", "tipo", "cuit_dni", "notas", "activo")


def guardar(s, datos: dict, cliente_id: int | None = None) -> Cliente:
    datos = {k: (v.strip() if isinstance(v, str) else v) for k, v in datos.items() if k in CAMPOS}
    if not datos.get("nombre", "sin cambio" if cliente_id else ""):
        raise ValueError("El nombre del cliente es obligatorio.")
    c = s.get(Cliente, cliente_id) if cliente_id else Cliente()
    for k, v in datos.items():
        setattr(c, k, v)
    s.add(c)
    s.flush()
    return c


def _saldos(s, cliente_id: int | None = None) -> dict[int, float]:
    q_deuda = (select(Venta.cliente_id, func.sum(Venta.total - Venta.sena_aplicada))
               .where(Venta.estado == "confirmada", Venta.medio_pago == CUENTA_CORRIENTE, Venta.cliente_id.is_not(None))
               .group_by(Venta.cliente_id))
    q_pagos = select(Cobro.cliente_id, func.sum(Cobro.monto)).group_by(Cobro.cliente_id)
    if cliente_id:
        q_deuda, q_pagos = q_deuda.where(Venta.cliente_id == cliente_id), q_pagos.where(Cobro.cliente_id == cliente_id)
    deuda, pagos = dict(s.execute(q_deuda).all()), dict(s.execute(q_pagos).all())
    return {i: round(float(deuda.get(i) or 0) - float(pagos.get(i) or 0), 2) for i in set(deuda) | set(pagos)}


def saldos(s) -> dict[int, float]:
    """Saldo de cuenta corriente por cliente (positivo = nos debe)."""
    return _saldos(s)


def saldo(s, cliente_id: int) -> float:
    return _saldos(s, cliente_id).get(cliente_id, 0.0)


def tabla(s, solo_activos: bool = True) -> pd.DataFrame:
    compras = (select(Venta.cliente_id, func.count(Venta.id).label("compras"),
                      func.sum(Venta.total).label("total_comprado"), func.max(Venta.fecha).label("ultima_compra"))
               .where(Venta.estado == "confirmada", Venta.cliente_id.is_not(None))
               .group_by(Venta.cliente_id).subquery())
    q = (select(Cliente.id, Cliente.nombre, Cliente.telefono, Cliente.email, Cliente.direccion, Cliente.localidad,
                Cliente.tipo, Cliente.activo, compras.c.compras, compras.c.total_comprado, compras.c.ultima_compra)
         .outerjoin(compras, compras.c.cliente_id == Cliente.id).order_by(Cliente.nombre))
    if solo_activos:
        q = q.where(Cliente.activo.is_(True))
    df = df_query(s, q)
    df["compras"] = df["compras"].fillna(0).astype(int)
    df["total_comprado"] = df["total_comprado"].fillna(0.0).astype(float)
    df["ultima_compra"] = pd.to_datetime(df["ultima_compra"])
    df["saldo"] = df["id"].map(saldos(s)).fillna(0.0).astype(float)
    return df


def deudores(s, referencia: date | None = None) -> pd.DataFrame:
    """Clientes que deben, con la fecha de la venta impaga más vieja (los cobros cancelan primero lo más viejo)."""
    referencia = referencia or hoy()
    filas = []
    for cid, deuda in saldos(s).items():
        if deuda <= 0.009:
            continue
        ventas_cc = s.execute(select(Venta.fecha, Venta.total - Venta.sena_aplicada)
                              .where(Venta.cliente_id == cid, Venta.estado == "confirmada",
                                     Venta.medio_pago == CUENTA_CORRIENTE)
                              .order_by(Venta.fecha.desc())).all()
        resto, desde = deuda, None
        for fecha, monto in ventas_cc:
            desde, resto = fecha, resto - float(monto)
            if resto <= 0.009:
                break
        c = s.get(Cliente, cid)
        desde = desde.date() if desde else referencia
        filas.append({"cliente_id": cid, "cliente": c.nombre, "telefono": c.telefono, "tipo": c.tipo, "saldo": deuda,
                      "desde": desde, "dias": (referencia - desde).days})
    return pd.DataFrame(filas, columns=["cliente_id", "cliente", "telefono", "tipo", "saldo", "desde", "dias"])


def registrar_cobro(s, cliente_id: int, monto: float, medio_pago: str, usuario_id: int | None = None,
                    notas: str = "", fecha: datetime | None = None) -> Cobro:
    if not cliente_id:
        raise ValueError("Elegí el cliente.")
    if monto <= 0:
        raise ValueError("El monto cobrado tiene que ser mayor a cero.")
    if medio_pago == CUENTA_CORRIENTE:
        raise ValueError("Elegí con qué pagó (efectivo, transferencia…).")
    c = Cobro(cliente_id=cliente_id, monto=round(monto, 2), medio_pago=medio_pago, usuario_id=usuario_id,
              notas=notas, fecha=fecha or ahora())
    s.add(c)
    s.flush()
    return c


def cobros(s, cliente_id: int) -> pd.DataFrame:
    return df_query(s, select(Cobro.fecha, Cobro.monto, Cobro.medio_pago, Cobro.notas, Usuario.nombre.label("usuario"))
                    .outerjoin(Usuario, Usuario.id == Cobro.usuario_id)
                    .where(Cobro.cliente_id == cliente_id).order_by(Cobro.fecha.desc()))
