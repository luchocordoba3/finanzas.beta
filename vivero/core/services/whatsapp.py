"""Links de WhatsApp (wa.me) con el mensaje ya escrito: gratis y sin API, el mensaje lo manda el usuario."""
import re
from urllib.parse import quote

from .util import pesos


def normalizar_telefono(telefono: str | None, codigo_area: str = "11") -> str | None:
    """Número argentino en formato internacional para celulares (549 + área + número), o None si no se entiende."""
    d = re.sub(r"\D", "", telefono or "")
    if d.startswith("00"):
        d = d[2:]
    if d.startswith("54"):
        d = d[2:].removeprefix("9")
    d = d.lstrip("0")
    if len(d) == 12:  # área (2 a 4 dígitos) + 15 + número
        for i in (2, 3, 4):
            if d[i:i + 2] == "15":
                d = d[:i] + d[i + 2:]
                break
    area = re.sub(r"\D", "", codigo_area or "")
    if d.startswith("15") and len(area) + len(d) - 2 == 10:  # 15 + número, sin código de área
        d = area + d[2:]
    elif len(d) < 10 and len(area) + len(d) == 10:  # número sin código de área
        d = area + d
    return "549" + d if len(d) == 10 else None


def link(telefono: str | None, texto: str, codigo_area: str = "11") -> str | None:
    numero = normalizar_telefono(telefono, codigo_area)
    return f"https://wa.me/{numero}?text={quote(texto)}" if numero else None


def saludo(nombre: str, tipo: str = "Particular") -> str:
    """Nombre de pila para particulares; el nombre completo para empresas y paisajistas."""
    return nombre.split()[0] if tipo == "Particular" and nombre.strip() else nombre


def mensaje(tipo: str, nombre: str, vivero: str, pedido: dict | None = None, saldo: float = 0) -> str:
    """tipo: listo | recordatorio | encargo | saldo | hola. pedido: id, total, sena, entrega, direccion, fecha_entrega, detalle."""
    p = pedido or {}
    if tipo == "listo":
        resta = p.get("total", 0) - p.get("sena", 0)
        donde = (f"y sale para {p['direccion']}" if p.get("entrega") == "Envío" and p.get("direccion")
                 else "para retirar")
        cuenta = f" Total {pesos(p.get('total'))}" + (f", ya pagaste {pesos(p['sena'])} de seña: resta {pesos(resta)}."
                                                     if p.get("sena") else ".")
        return f"¡Hola {nombre}! 🌱 Te escribimos de {vivero}: tu pedido ya está listo {donde}.{cuenta} ¡Gracias!"
    if tipo == "recordatorio":
        fecha = p["fecha_entrega"].strftime("%d/%m") if p.get("fecha_entrega") else ""
        return (f"¡Hola {nombre}! Te escribimos de {vivero} para recordarte tu pedido para el {fecha}: "
                f"{p.get('detalle', '')}. Cualquier cambio, avisanos. ¡Gracias!")
    if tipo == "encargo":
        return (f"¡Hola {nombre}! 🌿 Te escribimos de {vivero}: llegó lo que nos encargaste ({p.get('detalle', '')}). "
                "Cuando quieras pasás a buscarlo. ¡Gracias!")
    if tipo == "saldo":
        return (f"¡Hola {nombre}! ¿Cómo estás? Te escribimos de {vivero}: te quedó un saldo de {pesos(saldo)} "
                "en tu cuenta. Cuando puedas, lo vemos. ¡Gracias!")
    return f"¡Hola {nombre}! Te escribimos de {vivero}. "
