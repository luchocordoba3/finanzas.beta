from decimal import Decimal

import pandas as pd


def df_query(s, q) -> pd.DataFrame:
    """Ejecuta una consulta y devuelve un DataFrame (con columnas aunque no haya filas)."""
    res = s.execute(q)
    df = pd.DataFrame(res.all(), columns=list(res.keys()))
    for c in df.columns:  # Postgres devuelve Decimal en expresiones calculadas
        if df[c].dtype == object and df[c].map(lambda v: isinstance(v, Decimal)).any():
            df[c] = df[c].astype(float)
    return df


def nombre_producto(nombre: str, presentacion: str | None) -> str:
    return f"{nombre} · {presentacion}" if presentacion else nombre
