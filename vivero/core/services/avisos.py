"""Avisos al instante (por Telegram). Los servicios los encolan durante la operación y se mandan recién
después de guardar: si la operación falla, no sale ningún aviso."""
import html


def encolar(s, texto: str, para: list[int] | None = None, excepto: int | None = None) -> None:
    """para=None: a todos los que tengan Telegram conectado. excepto: el que hizo la operación."""
    s.info.setdefault("avisos", []).append({"texto": texto, "para": para, "excepto": excepto})


def pendientes(s) -> list[dict]:
    return list(s.info.get("avisos", []))


def e(texto) -> str:
    """Escapa datos para meterlos en un mensaje con formato HTML de Telegram."""
    return html.escape(str(texto), quote=False)
