"""Carga inicial desde Excel o CSV (catálogo con stock y clientes)."""
import io
import unicodedata

import pandas as pd
from sqlalchemy import func, select

from ..constantes import TIPOS_CLIENTE
from ..models import Categoria, Cliente
from . import catalogo, clientes, proveedores

COLUMNAS_PRODUCTOS = ["nombre", "presentacion", "categoria", "tipo", "precio", "costo", "stock", "stock_minimo",
                      "ubicacion", "proveedor", "codigo", "unidad", "nombre_cientifico"]
EJEMPLO_PRODUCTOS = [
    {"nombre": "Potus", "presentacion": "Maceta 14", "categoria": "Plantas de interior", "tipo": "planta",
     "precio": 6500, "costo": 3000, "stock": 20, "stock_minimo": 5, "ubicacion": "Invernadero 1",
     "proveedor": "Vivero Mayorista Sur", "codigo": "", "unidad": "u", "nombre_cientifico": "Epipremnum aureum"},
    {"nombre": "Tierra fértil", "presentacion": "Bolsa 25 L", "categoria": "Tierra y sustratos", "tipo": "insumo",
     "precio": 5500, "costo": 2800, "stock": 30, "stock_minimo": 10, "ubicacion": "Depósito", "proveedor": "",
     "codigo": "", "unidad": "bolsa", "nombre_cientifico": ""},
]
COLUMNAS_CLIENTES = ["nombre", "telefono", "email", "direccion", "localidad", "tipo", "cuit_dni", "notas"]
EJEMPLO_CLIENTES = [{"nombre": "Ana Pérez", "telefono": "11 5555-1234", "email": "", "direccion": "", "localidad": "",
                     "tipo": "Particular", "cuit_dni": "", "notas": "Le gustan las suculentas"}]


def _norm(txt: str) -> str:
    txt = unicodedata.normalize("NFKD", str(txt)).encode("ascii", "ignore").decode()
    return "_".join(txt.strip().lower().split())


def plantilla(columnas: list[str], ejemplo: list[dict]) -> bytes:
    buf = io.BytesIO()
    pd.DataFrame(ejemplo, columns=columnas).to_excel(buf, index=False)
    return buf.getvalue()


def leer(archivo) -> pd.DataFrame:
    nombre = getattr(archivo, "name", "").lower()
    df = pd.read_csv(archivo, sep=None, engine="python", dtype=str) if nombre.endswith(".csv") \
        else pd.read_excel(archivo, dtype=str)
    df.columns = [_norm(c) for c in df.columns]
    return df.dropna(how="all").fillna("")


def _num(valor) -> float:
    txt = str(valor).strip().replace("$", "").replace(" ", "")
    if not txt:
        return 0.0
    if "," in txt:  # formato argentino: 1.234,50
        txt = txt.replace(".", "").replace(",", ".")
    try:
        return float(txt)
    except ValueError:
        raise ValueError(f"«{valor}» no es un número")


def _categoria(s, nombre: str, tipo: str) -> Categoria | None:
    if not nombre:
        return None
    c = s.scalar(select(Categoria).where(func.lower(Categoria.nombre) == nombre.lower()))
    return c or catalogo.guardar_categoria(s, nombre, tipo, 100)


def importar_productos(s, df: pd.DataFrame, usuario_id: int | None = None) -> tuple[int, list[str]]:
    creados, errores = 0, []
    for n, fila in enumerate(df.to_dict("records"), start=2):
        nombre = str(fila.get("nombre", "")).strip()
        if not nombre:
            continue
        try:
            tipo = "insumo" if _norm(fila.get("tipo", "")).startswith("insumo") else "planta"
            precio, costo = _num(fila.get("precio", "")), _num(fila.get("costo", ""))
            stock_inicial, minimo = _num(fila.get("stock", "")), _num(fila.get("stock_minimo", ""))
            cat = _categoria(s, str(fila.get("categoria", "")).strip(), tipo)
            tipo = cat.tipo if cat else tipo
            prov = str(fila.get("proveedor", "")).strip()
            planta = catalogo.buscar_o_crear_planta(s, nombre, cat.id if cat else None) if tipo == "planta" else None
            if planta and fila.get("nombre_cientifico") and not planta.nombre_cientifico:
                planta.nombre_cientifico = str(fila["nombre_cientifico"]).strip()
            catalogo.crear_producto(s, {
                "nombre": nombre, "presentacion": str(fila.get("presentacion", "")).strip(),
                "categoria_id": cat.id if cat else None, "planta_id": planta.id if planta else None,
                "proveedor_id": proveedores.buscar_o_crear(s, prov).id if prov else None,
                "precio": precio, "stock_minimo": minimo, "ubicacion": str(fila.get("ubicacion", "")).strip(),
                "codigo": str(fila.get("codigo", "")).strip(), "unidad": str(fila.get("unidad", "")).strip() or "u",
            }, stock_inicial=stock_inicial, costo=costo, usuario_id=usuario_id)
            creados += 1
        except ValueError as e:
            errores.append(f"Fila {n} ({nombre}): {e}")
    return creados, errores


def importar_clientes(s, df: pd.DataFrame) -> tuple[int, list[str]]:
    creados, errores = 0, []
    tipos = {_norm(t)[:6]: t for t in TIPOS_CLIENTE}
    for n, fila in enumerate(df.to_dict("records"), start=2):
        nombre = str(fila.get("nombre", "")).strip()
        if not nombre:
            continue
        if s.scalar(select(Cliente.id).where(func.lower(Cliente.nombre) == nombre.lower())):
            errores.append(f"Fila {n} ({nombre}): ya existía, no se cargó de nuevo")
            continue
        datos = {k: str(fila.get(k, "")).strip() for k in ("telefono", "email", "direccion", "localidad", "cuit_dni", "notas")}
        datos["tipo"] = tipos.get(_norm(fila.get("tipo", ""))[:6], "Particular")
        clientes.guardar(s, {"nombre": nombre, **datos})
        creados += 1
    return creados, errores
