"""Conexión a la base: Postgres en la nube si hay DATABASE_URL, si no SQLite local."""
import os
from pathlib import Path

from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session

DB_LOCAL = Path(__file__).resolve().parent.parent / "vivero.db"


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        try:
            import streamlit as st
            url = st.secrets.get("DATABASE_URL")
        except Exception:  # sin secrets.toml
            url = None
    if not url:
        return f"sqlite:///{DB_LOCAL}"
    # Neon/Supabase entregan "postgres://" o "postgresql://": usar el driver psycopg 3.
    for prefijo in ("postgres://", "postgresql://"):
        if url.startswith(prefijo):
            return "postgresql+psycopg://" + url[len(prefijo):]
    return url


def crear_engine(url: str):
    if url.startswith("sqlite"):
        engine = create_engine(url, connect_args={"check_same_thread": False})

        @event.listens_for(engine, "connect")
        def _claves_foraneas(conn, _):
            conn.execute("PRAGMA foreign_keys=ON")
        return engine
    # pool_pre_ping: Neon corta las conexiones inactivas.
    return create_engine(url, pool_pre_ping=True, pool_recycle=300)


def init_db(engine) -> None:
    from .constantes import CATEGORIAS_INICIALES
    from .models import Base, Categoria

    Base.metadata.create_all(engine)
    with Session(engine) as s:
        if not s.scalar(select(func.count(Categoria.id))):
            s.add_all(Categoria(nombre=n, tipo=t) for n, t in CATEGORIAS_INICIALES)
            s.commit()
