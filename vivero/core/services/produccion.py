"""Producción propia: lotes (semillas, esquejes…) con sus etapas, pérdidas y pase a stock."""
from datetime import date

import pandas as pd
from sqlalchemy import select

from ..constantes import ETAPAS_LOTE
from ..models import Lote, LoteEvento, Planta, Producto
from ..tiempo import hoy
from . import stock
from .util import df_query, nombre_producto


def _evento(lote: Lote, tipo: str, cantidad: float = 0, detalle: str = "", usuario_id: int | None = None) -> None:
    lote.eventos.append(LoteEvento(tipo=tipo, cantidad=cantidad, detalle=detalle, usuario_id=usuario_id))


def _abierto(s, lote_id: int) -> Lote:
    lote = s.get(Lote, lote_id)
    if lote is None or lote.estado != "activo":
        raise ValueError("El lote no existe o ya está terminado.")
    return lote


def crear_lote(s, planta_id: int | None, metodo: str, cantidad: float, fecha_inicio: date | None = None,
               producto_id: int | None = None, costo_total: float = 0, fecha_estimada: date | None = None,
               ubicacion: str = "", notas: str = "", usuario_id: int | None = None) -> Lote:
    if not planta_id:
        raise ValueError("Elegí la planta que se está produciendo.")
    if cantidad <= 0:
        raise ValueError("La cantidad inicial tiene que ser mayor a cero.")
    lote = Lote(planta_id=planta_id, producto_id=producto_id, metodo=metodo, fecha_inicio=fecha_inicio or hoy(),
                cantidad_inicial=cantidad, cantidad_actual=cantidad, etapa=ETAPAS_LOTE[0], ubicacion=ubicacion.strip(),
                costo_total=costo_total or 0, fecha_estimada=fecha_estimada, notas=notas.strip(), usuario_id=usuario_id)
    s.add(lote)
    _evento(lote, "etapa", detalle=ETAPAS_LOTE[0], usuario_id=usuario_id)
    s.flush()
    return lote


def registrar_perdida(s, lote_id: int, cantidad: float, detalle: str = "", usuario_id: int | None = None) -> Lote:
    lote = _abierto(s, lote_id)
    if not 0 < cantidad <= lote.cantidad_actual:
        raise ValueError(f"La pérdida tiene que estar entre 1 y {lote.cantidad_actual:g}.")
    lote.cantidad_actual = round(lote.cantidad_actual - cantidad, 2)
    _evento(lote, "perdida", cantidad, detalle, usuario_id)
    if lote.cantidad_actual <= 0:
        lote.estado = "terminado"
    return lote


def cambiar_etapa(s, lote_id: int, etapa: str, usuario_id: int | None = None) -> Lote:
    lote = _abierto(s, lote_id)
    lote.etapa = etapa
    _evento(lote, "etapa", detalle=etapa, usuario_id=usuario_id)
    return lote


def pasar_a_stock(s, lote_id: int, cantidad: float, producto_id: int | None = None,
                  usuario_id: int | None = None) -> Lote:
    """Las plantas listas entran al stock del producto, con el costo del lote prorrateado."""
    lote = _abierto(s, lote_id)
    pid = producto_id or lote.producto_id
    if not pid:
        raise ValueError("Elegí el producto del catálogo en el que entran estas plantas.")
    if not 0 < cantidad <= lote.cantidad_actual:
        raise ValueError(f"La cantidad tiene que estar entre 1 y {lote.cantidad_actual:g}.")
    costo = round(lote.costo_total / lote.cantidad_inicial, 2) if lote.cantidad_inicial else 0
    stock.mover(s, pid, cantidad, "produccion", usuario_id, costo_unitario=costo, ref_tipo="lote", ref_id=lote.id)
    lote.producto_id, lote.cantidad_actual = pid, round(lote.cantidad_actual - cantidad, 2)
    _evento(lote, "a_stock", cantidad, s.get(Producto, pid).nombre_completo, usuario_id)
    if lote.cantidad_actual <= 0:
        lote.estado = "terminado"
    return lote


def terminar(s, lote_id: int, usuario_id: int | None = None) -> Lote:
    """Cierra el lote; lo que quedaba se cuenta como pérdida."""
    lote = _abierto(s, lote_id)
    if lote.cantidad_actual > 0:
        _evento(lote, "perdida", lote.cantidad_actual, "Cierre del lote", usuario_id)
        lote.cantidad_actual = 0
    lote.estado = "terminado"
    return lote


def tabla(s, estado: str | None = "activo") -> pd.DataFrame:
    q = (select(Lote.id, Planta.nombre_comun.label("planta"), Lote.metodo, Lote.etapa, Lote.fecha_inicio,
                Lote.fecha_estimada, Lote.cantidad_inicial, Lote.cantidad_actual, Lote.costo_total, Lote.ubicacion,
                Lote.estado, Lote.producto_id, Producto.nombre, Producto.presentacion, Lote.notas)
         .outerjoin(Planta, Planta.id == Lote.planta_id).outerjoin(Producto, Producto.id == Lote.producto_id)
         .order_by(Lote.fecha_estimada, Lote.id))
    if estado:
        q = q.where(Lote.estado == estado)
    df = df_query(s, q)
    df["producto"] = [nombre_producto(n, p) if isinstance(n, str) else "" for n, p in zip(df["nombre"], df["presentacion"])]
    return df


def eventos(s, lote_id: int) -> pd.DataFrame:
    return df_query(s, select(LoteEvento.fecha, LoteEvento.tipo, LoteEvento.cantidad, LoteEvento.detalle)
                    .where(LoteEvento.lote_id == lote_id).order_by(LoteEvento.fecha.desc(), LoteEvento.id.desc()))
