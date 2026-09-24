"""Panel de alertas: se calcula en el momento a partir de los datos, no se guarda."""
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select

from ..constantes import PEDIDO_ABIERTO
from ..models import Lote
from ..tiempo import hoy
from . import clientes, compras, config, pedidos, recordatorios, stock

NIVELES = {"urgente": 0, "atencion": 1, "info": 2}
ICONOS = {"Pedidos atrasados": "🔴", "Pedidos para entregar": "📦", "Faltantes para pedidos": "🧩",
          "Encargos que llegaron": "📬", "Stock bajo mínimo": "📉", "Compras por recibir": "🚚",
          "Pagos a proveedores": "💸", "Cuentas corrientes": "💳", "Recordatorios": "⏰", "Producción": "🌾",
          "Temporada": "🌸"}


@dataclass
class Alerta:
    nivel: str   # urgente | atencion | info
    grupo: str   # para agrupar en el panel
    texto: str
    pagina: str  # vista donde se resuelve
    ref_id: int | None = None
    fecha: date | None = None


def _cuando(f: date, ref: date) -> str:
    dias = (f - ref).days
    if dias == 0:
        return "hoy"
    if dias == 1:
        return "mañana"
    if dias == -1:
        return "ayer"
    return f"hace {-dias} días" if dias < 0 else f"en {dias} días"


def calcular(s, usuario_id: int | None = None, ref: date | None = None) -> list[Alerta]:
    ref = ref or hoy()
    cfg = config.todos(s)
    aviso = timedelta(days=int(cfg["dias_aviso"] or 3))
    out: list[Alerta] = []

    # Pedidos por entregar
    ped = pedidos.tabla(s, estados=PEDIDO_ABIERTO, hasta=ref + aviso)
    for p in ped.to_dict("records"):
        nivel = "urgente" if p["fecha_entrega"] <= ref else "info"
        estado = "listo" if p["estado"] == "listo" else "sin preparar"
        texto = f"Pedido #{p['id']} de {p['cliente']}: entrega {_cuando(p['fecha_entrega'], ref)} ({estado}) · {p['detalle']}"
        grupo = "Pedidos atrasados" if p["fecha_entrega"] < ref else "Pedidos para entregar"
        out.append(Alerta(nivel, grupo, texto, "pedidos", p["id"], p["fecha_entrega"]))

    # Faltantes para pedidos
    for f in pedidos.faltantes(s).to_dict("records"):
        if f["encargado"]:
            texto = f"Pedido #{f['pedido_id']} ({f['cliente']}): {f['falta']:g}× {f['descripcion']} ya encargado, falta que llegue"
            out.append(Alerta("info", "Faltantes para pedidos", texto, "compras", f["pedido_id"], f["fecha_entrega"]))
        else:
            nivel = "urgente" if f["fecha_entrega"] <= ref + aviso else "atencion"
            texto = (f"Pedido #{f['pedido_id']} ({f['cliente']}, entrega {_cuando(f['fecha_entrega'], ref)}): "
                     f"faltan {f['falta']:g}× {f['descripcion']} → encargar")
            out.append(Alerta(nivel, "Faltantes para pedidos", texto, "pedidos", f["pedido_id"], f["fecha_entrega"]))

    for e in encargos_recibidos_agrupados(s):
        out.append(Alerta("atencion", "Encargos que llegaron", e[1], "pedidos", e[0]))

    # Stock bajo mínimo
    en_curso = compras.productos_en_curso(s)
    for p in stock.a_reponer(stock.tabla_productos(s)).to_dict("records"):
        if p["id"] in en_curso:  # ya se está comprando
            continue
        texto = (f"{p['producto']}: quedan {p['disponible']:g} (mínimo {p['stock_minimo']:g})"
                 + (f" · proveedor {p['proveedor']}" if p["proveedor"] else ""))
        out.append(Alerta("atencion", "Stock bajo mínimo", texto, "stock", p["id"]))

    # Compras por recibir y pagos a proveedores
    for c in compras.tabla(s, estados=("pedida", "parcial")).to_dict("records"):
        if c["fecha_estimada"] and c["fecha_estimada"] <= ref + aviso:
            nivel = "atencion" if c["fecha_estimada"] < ref else "info"
            texto = f"Compra #{c['id']} a {c['proveedor']}: llega {_cuando(c['fecha_estimada'], ref)} · {c['detalle']}"
            out.append(Alerta(nivel, "Compras por recibir", texto, "compras", c["id"], c["fecha_estimada"]))
    for c in compras.tabla(s, estados=("parcial", "recibida")).to_dict("records"):
        if not c["pagada"] and c["fecha_venc_pago"] and c["fecha_venc_pago"] <= ref + aviso and c["total"] > 0:
            nivel = "urgente" if c["fecha_venc_pago"] < ref else "atencion"
            texto = f"Pagar compra #{c['id']} a {c['proveedor']}: $ {c['total']:,.0f} vence {_cuando(c['fecha_venc_pago'], ref)}"
            out.append(Alerta(nivel, "Pagos a proveedores", texto.replace(",", "."), "compras", c["id"], c["fecha_venc_pago"]))

    # Clientes que deben hace tiempo
    dias_deuda = int(cfg["dias_deuda"] or 30)
    for d in clientes.deudores(s, ref).to_dict("records"):
        if d["dias"] >= dias_deuda:
            texto = f"{d['cliente']} debe $ {d['saldo']:,.0f} desde hace {d['dias']} días".replace(",", ".")
            out.append(Alerta("atencion", "Cuentas corrientes", texto, "clientes", d["cliente_id"]))

    # Recordatorios / tareas
    for r in recordatorios.tabla(s, usuario_id=usuario_id, hasta=ref + aviso).to_dict("records"):
        nivel = "urgente" if r["fecha"] < ref else ("atencion" if r["fecha"] == ref else "info")
        para = "" if r["para"] == "Los dos" else f" (para {r['para']})"
        out.append(Alerta(nivel, "Recordatorios", f"{r['titulo']}{para}: {_cuando(r['fecha'], ref)}",
                          "recordatorios", r["id"], r["fecha"]))

    # Producción propia
    if cfg["modulo_produccion"] == "1":
        for lote in s.scalars(select(Lote).where(Lote.estado == "activo", Lote.fecha_estimada.is_not(None),
                                                 Lote.fecha_estimada <= ref + aviso)):
            nombre = lote.planta.nombre_comun if lote.planta else (lote.producto.nombre_completo if lote.producto else "")
            texto = f"Lote #{lote.id} de {nombre} ({lote.cantidad_actual:g} u.): listo {_cuando(lote.fecha_estimada, ref)}"
            out.append(Alerta("info", "Producción", texto, "produccion", lote.id, lote.fecha_estimada))

    # Temporada (según lo vendido el año pasado)
    from . import estadisticas
    for t in estadisticas.alertas_temporada(s, ref).to_dict("records"):
        texto = (f"Se viene la temporada de {t['producto']}: el año pasado en estas semanas vendiste {t['vendido']:g} "
                 f"y hoy tenés {t['disponible']:g}")
        out.append(Alerta("info", "Temporada", texto, "stock", int(t["producto_id"])))

    return sorted(out, key=lambda a: (NIVELES[a.nivel], a.fecha or ref))


def encargos_recibidos_agrupados(s) -> list[tuple[int, str]]:
    df = pedidos.encargos_recibidos(s)
    out = []
    for pid, g in df.groupby("pedido_id", sort=False):
        cliente, tel = g["cliente"].iloc[0], g["telefono"].iloc[0]
        cosas = ", ".join(g["descripcion"])
        out.append((int(pid), f"Llegó lo encargado para el pedido #{pid} de {cliente} ({cosas}): avisale"
                              + (f" al {tel}" if tel else "") + " y marcalo como listo"))
    return out


def contar(alertas: list[Alerta]) -> int:
    return sum(1 for a in alertas if a.nivel != "info")
