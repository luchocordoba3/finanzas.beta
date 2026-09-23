from core.db import normalizar_url, ocultar_clave


def test_normalizar_url_acepta_como_lo_copia_neon():
    esperado = "postgresql+psycopg://u:p@ep-x.neon.tech/neondb?sslmode=require"
    for pegado in ("postgresql://u:p@ep-x.neon.tech/neondb?sslmode=require",
                   "postgres://u:p@ep-x.neon.tech/neondb?sslmode=require",
                   "  'postgresql://u:p@ep-x.neon.tech/neondb?sslmode=require'  ",
                   "psql 'postgresql://u:p@ep-x.neon.tech/neondb?sslmode=require'"):
        assert normalizar_url(pegado) == esperado
    assert normalizar_url("sqlite:///vivero.db") == "sqlite:///vivero.db"


def test_ocultar_clave():
    assert ocultar_clave("falló postgresql+psycopg://u:secreto@host/db") == "falló postgresql+psycopg://u:****@host/db"
