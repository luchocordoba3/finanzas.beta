from sqlalchemy import select

from ..models import Config

DEFAULTS = {
    "nombre_vivero": "Mi Vivero",
    "direccion": "",
    "telefono": "",
    "dias_aviso": "3",
    "dias_deuda": "30",
    "dias_sin_venta": "60",
    "modulo_produccion": "0",
    "codigo_area": "11",
    "medios_pago": "Efectivo, Transferencia, Mercado Pago, Débito, Crédito, Cuenta corriente",
}


def obtener(s, clave: str) -> str:
    fila = s.get(Config, clave)
    return fila.valor if fila else DEFAULTS.get(clave, "")


def todos(s) -> dict:
    datos = dict(DEFAULTS)
    datos.update({c.clave: c.valor for c in s.scalars(select(Config))})
    return datos


def guardar(s, valores: dict) -> None:
    for clave, valor in valores.items():
        fila = s.get(Config, clave)
        if fila:
            fila.valor = str(valor)
        else:
            s.add(Config(clave=clave, valor=str(valor)))


def entero(s, clave: str) -> int:
    try:
        return int(obtener(s, clave))
    except ValueError:
        return int(DEFAULTS[clave])


def medios_pago(s) -> list[str]:
    return [m.strip() for m in obtener(s, "medios_pago").split(",") if m.strip()]


def produccion_activa(s) -> bool:
    return obtener(s, "modulo_produccion") == "1"
