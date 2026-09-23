from decimal import Decimal

import pandas as pd
from sqlalchemy import Boolean, Numeric


def df_query(s, q) -> pd.DataFrame:
    """Ejecuta una consulta y devuelve un DataFrame con columnas y tipos correctos aunque no haya filas
    (sin filas, pandas deja todo como `object` y un filtro por una columna booleana deja de funcionar)."""
    res = s.execute(q)
    df = pd.DataFrame(res.all(), columns=list(res.keys()))
    tipos = dict(zip(q.selected_columns.keys(), (c.type for c in q.selected_columns)))
    for c in df.columns:
        tipo = tipos.get(c)
        if isinstance(tipo, Boolean):
            df[c] = df[c].astype(object).where(df[c].notna(), False).astype(bool)
        elif isinstance(tipo, Numeric) or (df[c].dtype == object and df[c].map(lambda v: isinstance(v, Decimal)).any()):
            df[c] = pd.to_numeric(df[c], errors="coerce").astype(float)
    return df


def nombre_producto(nombre: str, presentacion: str | None) -> str:
    return f"{nombre} · {presentacion}" if presentacion else nombre
