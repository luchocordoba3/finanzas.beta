from datetime import date

import pandas as pd
from dateutil.relativedelta import relativedelta
from sqlalchemy import or_, select
from sqlalchemy.orm import aliased

from ..models import Recordatorio, Usuario
from ..tiempo import ahora, hoy
from . import avisos
from .util import df_query

PASOS = {"semanal": relativedelta(weeks=1), "mensual": relativedelta(months=1)}


def crear(s, titulo: str, fecha: date, creado_por: int | None = None, asignado_a: int | None = None,
          repeticion: str = "no", descripcion: str = "") -> Recordatorio:
    if not titulo.strip():
        raise ValueError("Escribí qué hay que recordar.")
    r = Recordatorio(titulo=titulo.strip(), fecha=fecha, creado_por=creado_por, asignado_a=asignado_a,
                     repeticion=repeticion, descripcion=descripcion.strip())
    s.add(r)
    s.flush()
    if asignado_a and asignado_a != creado_por:
        quien = s.get(Usuario, creado_por).nombre if creado_por else "Alguien"
        avisos.encolar(s, f"⏰ {avisos.e(quien)} te dejó un recordatorio para el {fecha:%d/%m}: "
                          f"<b>{avisos.e(r.titulo)}</b>", para=[asignado_a])
    return r


def completar(s, recordatorio_id: int) -> Recordatorio | None:
    """Marca como hecho. Si se repite, crea el próximo y lo devuelve."""
    r = s.get(Recordatorio, recordatorio_id)
    r.hecho, r.hecho_en = True, ahora()
    if r.repeticion not in PASOS:
        return None
    proxima = r.fecha + PASOS[r.repeticion]
    while proxima <= hoy():
        proxima += PASOS[r.repeticion]
    return crear(s, r.titulo, proxima, r.creado_por, r.asignado_a, r.repeticion, r.descripcion)


def eliminar(s, recordatorio_id: int) -> None:
    s.delete(s.get(Recordatorio, recordatorio_id))


def tabla(s, hechos: bool = False, usuario_id: int | None = None, hasta: date | None = None,
          limite: int = 200) -> pd.DataFrame:
    asignado = aliased(Usuario)
    q = (select(Recordatorio.id, Recordatorio.titulo, Recordatorio.descripcion, Recordatorio.fecha,
                Recordatorio.asignado_a, asignado.nombre.label("para"), Recordatorio.repeticion, Recordatorio.hecho_en)
         .outerjoin(asignado, asignado.id == Recordatorio.asignado_a)
         .where(Recordatorio.hecho.is_(hechos)).limit(limite))
    q = q.order_by(Recordatorio.hecho_en.desc()) if hechos else q.order_by(Recordatorio.fecha, Recordatorio.id)
    if usuario_id:  # los míos + los de los dos
        q = q.where(or_(Recordatorio.asignado_a == usuario_id, Recordatorio.asignado_a.is_(None)))
    if hasta:
        q = q.where(Recordatorio.fecha <= hasta)
    df = df_query(s, q)
    df["para"] = df["para"].fillna("Los dos")
    return df
