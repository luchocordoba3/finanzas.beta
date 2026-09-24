"""Fecha y hora de Argentina. Streamlit Cloud corre en UTC: nunca usar date.today() directo."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Argentina/Buenos_Aires")
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def ahora() -> datetime:
    """Hora local sin tzinfo (así se guarda en la base)."""
    return datetime.now(TZ).replace(tzinfo=None, microsecond=0)


def hoy() -> date:
    return ahora().date()
