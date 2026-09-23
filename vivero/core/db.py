"""Conexión a la base: Postgres en la nube si hay DATABASE_URL, si no SQLite local."""
import os
import re
from pathlib import Path

from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session

DB_LOCAL = Path(__file__).resolve().parent.parent / "vivero.db"


def normalizar_url(url: str) -> str:
    """Acepta la dirección tal como la copia Neon/Supabase (incluso con `psql '...'` o comillas de más)
    y la adapta al driver psycopg 3."""
    url = url.strip()
    encontrada = re.search(r"postgres(?:ql)?(?:\+\w+)?://[^\s'\"]+", url)
    if encontrada:
        url = encontrada.group(0)
    return re.sub(r"^postgres(?:ql)?://", "postgresql+psycopg://", url)


def url_configurada() -> str | None:
    url = os.environ.get("DATABASE_URL")
    if not url:
        try:
            import streamlit as st
            url = st.secrets.get("DATABASE_URL")
        except Exception:  # sin secrets.toml
            url = None
    return normalizar_url(url) if url else None


def database_url() -> str:
    return url_configurada() or f"sqlite:///{DB_LOCAL}"


def en_streamlit_cloud() -> bool:
    """Streamlit Community Cloud clona el repo en /mount/src: ahí el disco se borra en cada reinicio."""
    return Path(__file__).resolve().as_posix().startswith("/mount/src/")


def ocultar_clave(texto: str) -> str:
    return re.sub(r"(://[^:/@\s]+):[^@\s]+@", r"\1:****@", str(texto))


def crear_engine(url: str):
    url = normalizar_url(url)
    if url.startswith("sqlite"):
        engine = create_engine(url, connect_args={"check_same_thread": False})

        @event.listens_for(engine, "connect")
        def _claves_foraneas(conn, _):
            conn.execute("PRAGMA foreign_keys=ON")
        return engine
    # pool_pre_ping: Neon corta las conexiones inactivas.
    # prepare_threshold=None: sin sentencias preparadas, así anda también con el pool de conexiones de Neon/Supabase.
    return create_engine(url, pool_pre_ping=True, pool_recycle=300, connect_args={"prepare_threshold": None})


def init_db(engine) -> None:
    from .constantes import CATEGORIAS_INICIALES
    from .models import Base, Categoria

    Base.metadata.create_all(engine)
    with Session(engine) as s:
        if not s.scalar(select(func.count(Categoria.id))):
            s.add_all(Categoria(nombre=n, tipo=t) for n, t in CATEGORIAS_INICIALES)
            s.commit()
