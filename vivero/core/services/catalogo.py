"""Catálogo: productos, fichas de plantas, categorías y precios."""
import math

import pandas as pd
from sqlalchemy import func, select

from ..models import Categoria, Planta, Producto
from . import stock

CAMPOS_PRODUCTO = ("codigo", "nombre", "presentacion", "unidad", "categoria_id", "planta_id", "proveedor_id",
                   "precio", "stock_minimo", "ubicacion", "activo")


def _limpiar(datos: dict, campos) -> dict:
    limpio = {k: (v.strip() if isinstance(v, str) else v) for k, v in datos.items() if k in campos}
    if "nombre" in limpio and not limpio["nombre"]:
        raise ValueError("El nombre es obligatorio.")
    for k in ("precio", "stock_minimo"):
        if k in limpio and (limpio[k] or 0) < 0:
            raise ValueError("Los precios y cantidades no pueden ser negativos.")
    return limpio


def crear_producto(s, datos: dict, stock_inicial: float = 0, costo: float = 0,
                   usuario_id: int | None = None) -> Producto:
    datos = _limpiar(datos, CAMPOS_PRODUCTO)
    if datos.get("planta_id") and not datos.get("categoria_id"):
        datos["categoria_id"] = s.get(Planta, datos["planta_id"]).categoria_id
    duplicado = s.scalar(select(Producto).where(func.lower(Producto.nombre) == datos["nombre"].lower(),
                                                func.lower(Producto.presentacion) == datos.get("presentacion", "").lower(),
                                                Producto.activo.is_(True)))
    if duplicado:
        raise ValueError(f"Ya existe «{duplicado.nombre_completo}».")
    p = Producto(**datos, costo_promedio=costo or 0, costo_ultimo=costo or 0)
    s.add(p)
    s.flush()
    if stock_inicial:
        stock.mover(s, p.id, stock_inicial, "inicial", usuario_id, costo_unitario=costo or None)
    return p


def actualizar_producto(s, producto_id: int, datos: dict) -> Producto:
    p = s.get(Producto, producto_id)
    for k, v in _limpiar(datos, CAMPOS_PRODUCTO + ("costo_promedio",)).items():
        setattr(p, k, v)
    return p


def categorias(s, tipo: str | None = None, solo_activas: bool = True) -> list[Categoria]:
    q = select(Categoria).order_by(Categoria.nombre)
    if tipo:
        q = q.where(Categoria.tipo == tipo)
    if solo_activas:
        q = q.where(Categoria.activo.is_(True))
    return list(s.scalars(q))


def guardar_categoria(s, nombre: str, tipo: str, margen: float, categoria_id: int | None = None,
                      activo: bool = True) -> Categoria:
    nombre = nombre.strip()
    if not nombre:
        raise ValueError("Poné un nombre para la categoría.")
    otra = s.scalar(select(Categoria).where(func.lower(Categoria.nombre) == nombre.lower()))
    if otra and otra.id != categoria_id:
        raise ValueError("Ya existe una categoría con ese nombre.")
    c = s.get(Categoria, categoria_id) if categoria_id else Categoria()
    c.nombre, c.tipo, c.margen_objetivo, c.activo = nombre, tipo, margen, activo
    s.add(c)
    s.flush()
    return c


def plantas(s, solo_activas: bool = True) -> list[Planta]:
    q = select(Planta).order_by(Planta.nombre_comun)
    if solo_activas:
        q = q.where(Planta.activo.is_(True))
    return list(s.scalars(q))


def guardar_planta(s, datos: dict, planta_id: int | None = None) -> Planta:
    datos = {k: (v.strip() if isinstance(v, str) else v) for k, v in datos.items()}
    if not datos.get("nombre_comun"):
        raise ValueError("El nombre común es obligatorio.")
    p = s.get(Planta, planta_id) if planta_id else Planta()
    nombre_anterior = p.nombre_comun
    for k, v in datos.items():
        setattr(p, k, v)
    s.add(p)
    s.flush()
    if planta_id:  # mantener alineados los productos de esta planta
        for prod in s.scalars(select(Producto).where(Producto.planta_id == p.id)):
            prod.categoria_id = p.categoria_id
            if prod.nombre == nombre_anterior:
                prod.nombre = p.nombre_comun
    return p


def buscar_o_crear_planta(s, nombre: str, categoria_id: int | None) -> Planta:
    p = s.scalar(select(Planta).where(func.lower(Planta.nombre_comun) == nombre.strip().lower()))
    return p or guardar_planta(s, {"nombre_comun": nombre, "categoria_id": categoria_id})


# ---- Precios ---------------------------------------------------------------------------------

def redondear(valor: float, paso: float) -> float:
    """Redondea hacia arriba al múltiplo de `paso` (ej.: 100 → $ 12.340 pasa a $ 12.400)."""
    if paso <= 1:
        return round(valor, 2)
    return math.ceil(round(valor / paso, 6)) * paso


def precio_sugerido(costo: float, margen: float) -> float:
    return round(costo * (1 + (margen or 0) / 100), 2)


def vista_previa_aumento(df: pd.DataFrame, porcentaje: float, paso: float) -> pd.DataFrame:
    out = df[["id", "producto", "categoria", "proveedor", "precio"]].copy()
    out["nuevo"] = [redondear(p * (1 + porcentaje / 100), paso) for p in out["precio"]]
    return out


def aplicar_precios(s, nuevos: dict[int, float]) -> int:
    for pid, precio in nuevos.items():
        if precio < 0:
            raise ValueError("Hay precios negativos.")
        s.get(Producto, int(pid)).precio = float(precio)
    return len(nuevos)
