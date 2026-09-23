"""Carga datos de ejemplo (un año de ventas, clientes, compras, pedidos, pérdidas…) para probar el sistema.

    python vivero/seed_demo.py              # base local vivero/vivero.db
    python vivero/seed_demo.py --forzar     # aunque ya haya ventas cargadas

Por seguridad no corre contra una base en la nube salvo que pases --permitir-remoto.
Usuarios de prueba: ana / vivero123 (día a día) y juan / vivero123 (administración).
"""
import argparse
import random
import sys
from datetime import datetime, time, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from core import auth  # noqa: E402
from core.constantes import CUENTA_CORRIENTE, MOTIVOS_MERMA  # noqa: E402
from core.db import crear_engine, database_url, init_db  # noqa: E402
from core.models import Categoria, Compra, Venta  # noqa: E402
from core.services import (catalogo, clientes, compras, config, pedidos, produccion, proveedores,  # noqa: E402
                           recordatorios, stock, ventas)
from core.tiempo import ahora, hoy  # noqa: E402

# nombre, científico, categoría, ambiente, mes pico (None = todo el año), [(presentación, precio, costo)], proveedor
PLANTAS = [
    ("Potus", "Epipremnum aureum", "Plantas de interior", "Interior", None, [("Maceta 12", 4500, 1800), ("Maceta 17", 9500, 4200)], 0),
    ("Monstera", "Monstera deliciosa", "Plantas de interior", "Interior", None, [("Maceta 20", 19000, 8500)], 0),
    ("Sansevieria", "Dracaena trifasciata", "Plantas de interior", "Interior", None, [("Maceta 14", 7500, 3200)], 0),
    ("Ficus lyrata", "Ficus lyrata", "Plantas de interior", "Interior", None, [("Maceta 24", 32000, 15000)], 0),
    ("Helecho", "Nephrolepis exaltata", "Plantas de interior", "Interior y exterior", 11, [("Maceta 17", 8500, 3500)], 0),
    ("Lavanda", "Lavandula angustifolia", "Aromáticas y huerta", "Exterior", 10, [("Maceta 12", 3800, 1500)], 1),
    ("Romero", "Salvia rosmarinus", "Aromáticas y huerta", "Exterior", 10, [("Maceta 12", 3500, 1300)], 1),
    ("Albahaca", "Ocimum basilicum", "Aromáticas y huerta", "Exterior", 11, [("Maceta 10", 2500, 900)], 1),
    ("Tomate", "Solanum lycopersicum", "Aromáticas y huerta", "Exterior", 10, [("Plantín", 900, 300)], 1),
    ("Lechuga", "Lactuca sativa", "Aromáticas y huerta", "Exterior", 4, [("Plantín", 700, 250)], 1),
    ("Limonero", "Citrus × limon", "Frutales", "Exterior", 8, [("Maceta 30", 36000, 17000)], 2),
    ("Arándano", "Vaccinium corymbosum", "Frutales", "Exterior", 8, [("Maceta 20", 16000, 7000)], 2),
    ("Echeveria", "Echeveria elegans", "Suculentas y cactus", "Interior y exterior", None, [("Maceta 8", 2500, 900)], 0),
    ("Cactus", "Cactaceae", "Suculentas y cactus", "Interior y exterior", None, [("Maceta 8", 2800, 1000), ("Maceta 14", 6500, 2600)], 0),
    ("Jacarandá", "Jacaranda mimosifolia", "Árboles", "Exterior", 9, [("Bolsa 10 L", 22000, 9000)], 2),
    ("Lapacho", "Handroanthus impetiginosus", "Árboles", "Exterior", 9, [("Bolsa 10 L", 24000, 10000)], 2),
    ("Hortensia", "Hydrangea macrophylla", "Arbustos", "Exterior", 11, [("Maceta 20", 14000, 6000)], 3),
    ("Jazmín", "Trachelospermum jasminoides", "Arbustos", "Exterior", 10, [("Maceta 17", 9000, 3800)], 3),
    ("Petunia", "Petunia × hybrida", "Florales de estación", "Exterior", 10, [("Maceta 12", 2800, 1000)], 3),
    ("Pensamiento", "Viola × wittrockiana", "Florales de estación", "Exterior", 6, [("Maceta 10", 2200, 800)], 3),
]
INSUMOS = [("Tierra fértil", "Bolsa 25 L", "Tierra y sustratos", "bolsa", 5500, 2600, 4),
           ("Sustrato para macetas", "Bolsa 50 L", "Tierra y sustratos", "bolsa", 11000, 5200, 4),
           ("Maceta plástica", "N° 14", "Macetas", "u", 1800, 700, 5),
           ("Maceta de barro", "N° 20", "Macetas", "u", 6500, 2800, 5),
           ("Fertilizante líquido", "1 L", "Fertilizantes y fitosanitarios", "u", 7800, 3900, 4),
           ("Insecticida orgánico", "500 ml", "Fertilizantes y fitosanitarios", "u", 6900, 3300, 4)]
PROVEEDORES = [("Vivero Mayorista Sur", "Plantas de interior y suculentas", "Martes"),
               ("Semillería La Huerta", "Aromáticas y plantines", "Lunes y jueves"),
               ("Frutales del Litoral", "Frutales y árboles", "Quincenal"),
               ("Flores Escobar", "Arbustos y florales", "Viernes"),
               ("Agro Insumos Norte", "Tierra, sustratos y fertilizantes", "Miércoles"),
               ("Macetas del Oeste", "Macetas", "A pedido")]
NOMBRES = ["Ana Pérez", "Carlos Gómez", "Lucía Fernández", "Martín Rodríguez", "Sofía López", "Diego Martínez",
           "Valentina García", "Javier Sánchez", "Camila Romero", "Pablo Díaz", "Florencia Álvarez", "Nicolás Torres",
           "Julieta Ruiz", "Tomás Ramírez", "Agustina Flores", "Mateo Acosta", "Paula Benítez", "Federico Medina",
           "Carolina Herrera", "Gonzalo Castro", "Mariana Vega", "Santiago Molina", "Rocío Ortiz", "Lucas Silva",
           "Jardines Verdes (paisajismo)", "Estudio Paisaje Norte", "Club Social Villa Rosa", "Colegio San Martín"]
FACTOR_MES = {1: .8, 2: .7, 3: .75, 4: .65, 5: .55, 6: .45, 7: .45, 8: .7, 9: 1.2, 10: 1.45, 11: 1.3, 12: 1.1}


def cantidad_ventas(dia) -> int:
    base = 6 * FACTOR_MES[dia.month] * (1.6 if dia.weekday() >= 5 else (0.6 if dia.weekday() == 0 else 1))
    return max(0, round(random.gauss(base, base * 0.3)))


def hora_venta(dia, limite: datetime | None = None) -> datetime:
    h = random.choice([9, 10, 10, 11, 11, 11, 12, 12, 15, 16, 16, 17, 17, 17, 18])
    momento = datetime.combine(dia, time(h, random.randint(0, 59)))
    return min(momento, limite) if limite else momento


def main() -> None:
    args = argparse.ArgumentParser()
    args.add_argument("--forzar", action="store_true")
    args.add_argument("--permitir-remoto", action="store_true")
    opciones = args.parse_args()
    url = database_url()
    if not url.startswith("sqlite") and not opciones.permitir_remoto:
        sys.exit("DATABASE_URL apunta a una base remota: agregá --permitir-remoto si de verdad querés datos de prueba ahí.")
    engine = crear_engine(url)
    init_db(engine)
    with Session(engine) as s:
        if s.scalar(select(func.count(Venta.id))) and not opciones.forzar:
            sys.exit("La base ya tiene ventas. Usá --forzar para agregar los datos de prueba igual.")
        cargar(s)
        s.commit()
    print("Listo. Usuarios: ana / vivero123 y juan / vivero123")


def cargar(s) -> None:
    random.seed(42)
    ref = hoy()
    inicio = ref - timedelta(days=365)
    t0 = datetime.combine(inicio - timedelta(days=1), time(8))
    if not auth.hay_usuarios(s):
        auth.crear_usuario(s, "Ana", "ana", "vivero123")
        auth.crear_usuario(s, "Juan", "juan", "vivero123")
    ana, juan = 1, 2
    config.guardar(s, {"nombre_vivero": "Vivero El Ceibo", "direccion": "Av. Siempreviva 742, Escobar",
                       "telefono": "11 4444-5555", "modulo_produccion": "1"})
    cats = {c.nombre: c.id for c in s.scalars(select(Categoria))}
    provs = [proveedores.guardar(s, {"nombre": n, "rubro": r, "dias_entrega": d, "telefono": f"11 5{i}00-12{i}4",
                                     "condiciones_pago": random.choice(["Contado", "15 días", "30 días"])})
             for i, (n, r, d) in enumerate(PROVEEDORES)]

    productos, pico, ubic = [], {}, ["Invernadero 1", "Invernadero 2", "Sector A", "Sector B", "Depósito"]
    for nombre, cientifico, cat, ambiente, mes, presentaciones, prov in PLANTAS:
        planta = catalogo.guardar_planta(s, {"nombre_comun": nombre, "nombre_cientifico": cientifico,
                                             "categoria_id": cats[cat], "ambiente": ambiente})
        for pres, precio, costo in presentaciones:
            p = catalogo.crear_producto(s, {"nombre": nombre, "presentacion": pres, "planta_id": planta.id,
                                            "proveedor_id": provs[prov].id, "precio": precio,
                                            "stock_minimo": random.choice([4, 5, 6, 8, 10]),
                                            "ubicacion": ubic[0 if ambiente == "Interior" else random.randint(1, 3)]})
            stock.mover(s, p.id, random.randint(25, 45), "inicial", ana, costo_unitario=costo, fecha=t0)
            productos.append(p)
            pico[p.id] = mes
    for nombre, pres, cat, unidad, precio, costo, prov in INSUMOS:
        p = catalogo.crear_producto(s, {"nombre": nombre, "presentacion": pres, "categoria_id": cats[cat], "unidad": unidad,
                                        "proveedor_id": provs[prov].id, "precio": precio, "stock_minimo": 10,
                                        "ubicacion": "Depósito"})
        stock.mover(s, p.id, 60, "inicial", ana, costo_unitario=costo, fecha=t0)
        productos.append(p)
        pico[p.id] = None
    costos = {p.id: p.costo_ultimo for p in productos}

    tipos = ["Particular"] * 24 + ["Paisajista", "Paisajista", "Empresa / institución", "Empresa / institución"]
    lista_clientes = [clientes.guardar(s, {"nombre": n, "tipo": t, "telefono": f"11 {random.randint(3000, 6999)}-{random.randint(1000, 9999)}",
                                           "localidad": random.choice(["Escobar", "Garín", "Maschwitz", "Pilar", "Tigre"])})
                      for n, t in zip(NOMBRES, tipos)]
    frecuentes = lista_clientes[:8] + lista_clientes[24:]

    def peso(p, dia):
        mes = pico[p.id]
        if mes is None:
            return 1.0
        distancia = min(abs(dia.month - mes), 12 - abs(dia.month - mes))
        return {0: 3.0, 1: 2.0, 2: 1.0}.get(distancia, 0.35)

    medios = ["Efectivo"] * 5 + ["Transferencia"] * 4 + ["Mercado Pago"] * 4 + ["Débito"] * 2 + ["Crédito"]
    ahora_ = ahora()
    for n_dia in range(366):
        dia = inicio + timedelta(days=n_dia)
        if dia.weekday() == 0 and n_dia:  # los lunes se repone lo que está bajo el mínimo
            for p in productos:
                if p.stock <= p.stock_minimo * 1.5:
                    compras.crear_compra(s, p.proveedor_id, [{"producto_id": p.id, "cantidad": p.stock_minimo * 4,
                                                              "precio": round(costos[p.id] * random.uniform(1.0, 1.08))}],
                                         juan, recibida=True, fecha=datetime.combine(dia, time(9)),
                                         fecha_venc_pago=dia + timedelta(days=15))
        if dia == ref and ahora_.hour < 9:
            break
        pesos = [peso(p, dia) for p in productos]
        for _ in range(cantidad_ventas(dia)):
            elegidos = {p.id: p for p in random.choices(productos, weights=pesos, k=random.choice([1, 1, 1, 2, 2, 3]))}
            items = [{"producto_id": p.id, "cantidad": random.choice([1, 1, 1, 2, 2, 3, 6] if p.precio < 5000 else [1, 1, 2]),
                      "precio": p.precio} for p in elegidos.values()]
            items = [i for i in items if elegidos[i["producto_id"]].stock >= i["cantidad"]]
            if not items:
                continue
            cliente = random.choice(frecuentes) if random.random() < 0.45 else None
            medio = random.choice(medios)
            if cliente and cliente.tipo != "Particular" and random.random() < 0.6:
                medio = CUENTA_CORRIENTE
            descuento = round(sum(i["cantidad"] * i["precio"] for i in items) * 0.1) if random.random() < 0.08 else 0
            ventas.crear_venta(s, items, medio, random.choice([ana, ana, juan]), cliente.id if cliente else None, descuento,
                               fecha=hora_venta(dia, ahora_ if dia == ref else None))
        if random.random() < 0.3:  # pérdidas (más en invierno)
            p = random.choice(productos[:-len(INSUMOS)])
            if p.stock > 3:
                motivo = "Helada / clima" if dia.month in (6, 7, 8) and random.random() < 0.5 else random.choice(MOTIVOS_MERMA[:5])
                stock.merma(s, p.id, random.randint(1, 3), motivo, ana, fecha=datetime.combine(dia, time(8, 30)))
        if dia.day == 5:  # los clientes con cuenta corriente pagan a principio de mes
            for cid, saldo in clientes.saldos(s).items():
                if saldo > 0 and dia < ref - timedelta(days=20):
                    clientes.registrar_cobro(s, cid, round(saldo * random.choice([1, 1, 0.5])), "Transferencia", juan,
                                             fecha=datetime.combine(dia, time(10)))

    # Pedidos abiertos: uno atrasado, dos para hoy, varios próximos y un encargo de algo que no hay
    olivo = catalogo.crear_producto(s, {"nombre": "Olivo", "presentacion": "Maceta 40", "categoria_id": cats["Árboles"],
                                        "proveedor_id": provs[2].id, "precio": 95000})
    olivo.costo_ultimo = 45000
    for dias, cli, items, estado in [(-1, 0, [(0, 2), (5, 3)], "pendiente"), (0, 3, [(1, 1)], "listo"),
                                     (0, 24, [(14, 4), (15, 2), (20, 5)], "pendiente"), (2, 5, [(16, 3)], "pendiente"),
                                     (5, 25, [(6, 10), (7, 10), (8, 20)], "pendiente")]:
        lineas = [{"producto_id": productos[i].id, "cantidad": c, "precio": productos[i].precio} for i, c in items]
        total = sum(x["cantidad"] * x["precio"] for x in lineas)
        ped = pedidos.crear_pedido(s, lista_clientes[cli].id, ref + timedelta(days=dias), lineas,
                                   ana, sena=round(total * random.choice([0, 0.3, 0.5]), -2), entrega="Envío" if cli >= 24 else "Retira",
                                   direccion="Ruta 25 km 12" if cli >= 24 else "")
        ped.estado = estado
    encargo = pedidos.crear_pedido(s, lista_clientes[2].id, ref + timedelta(days=12),
                                   [{"producto_id": None, "descripcion": "Olivo grande (maceta 40)", "cantidad": 1, "precio": 95000}],
                                   ana, sena=30000, notas="Lo quiere para el cumpleaños del marido")
    pedidos.encargar_item(s, encargo.items[0].id, ana, producto_id=olivo.id)

    # Compras en curso y pagos pendientes
    compras.crear_compra(s, provs[1].id, [{"producto_id": productos[6].id, "cantidad": 30, "precio": 1400},
                                              {"producto_id": productos[5].id, "cantidad": 30, "precio": 1600}],
                             juan, fecha_estimada=ref + timedelta(days=1))
    compras.agregar_a_lista(s, productos[-1].id, 12, ana)
    compras.agregar_a_lista(s, productos[-3].id, 40, ana)
    recibida = compras.crear_compra(s, provs[3].id, [{"producto_id": productos[19].id, "cantidad": 20, "precio": 3900}],
                                    juan, recibida=True, fecha=datetime.combine(ref - timedelta(days=3), time(9)),
                                    fecha_venc_pago=ref + timedelta(days=2))
    # Las compras automáticas del año quedan pagas, salvo las últimas
    for co in s.scalars(select(Compra).where(Compra.estado == "recibida", Compra.id != recibida.id)):
        if co.fecha_recepcion and co.fecha_recepcion < ref - timedelta(days=10):
            co.pagada, co.fecha_pago, co.medio_pago = True, co.fecha_venc_pago, "Transferencia"

    # Recordatorios
    recordatorios.crear(s, "Fertilizar el invernadero 1", ref, ana, ana, "semanal")
    recordatorios.crear(s, "Pagar la luz", ref + timedelta(days=2), ana, juan, "mensual")
    recordatorios.crear(s, "Revisar pulgones en rosales", ref - timedelta(days=1), juan, ana)
    recordatorios.crear(s, "Llamar a Frutales del Litoral por la lista de otoño", ref + timedelta(days=5), juan, juan)

    # Producción propia
    lav = next(p for p in productos if p.nombre == "Lavanda")
    lote = produccion.crear_lote(s, lav.planta_id, "Esqueje / estaca", 120, ref - timedelta(days=150), lav.id, 9000,
                                 ref - timedelta(days=30), "Invernadero 2", usuario_id=ana)
    produccion.registrar_perdida(s, lote.id, 18, "No enraizaron", ana)
    produccion.pasar_a_stock(s, lote.id, 102, lav.id, ana)
    tom = next(p for p in productos if p.nombre == "Tomate")
    lote = produccion.crear_lote(s, tom.planta_id, "Semilla", 200, ref - timedelta(days=25), tom.id, 6000,
                                 ref + timedelta(days=2), "Invernadero 2", usuario_id=ana)
    produccion.cambiar_etapa(s, lote.id, "Plantín", ana)
    produccion.registrar_perdida(s, lote.id, 14, "Damping-off", ana)
    alb = next(p for p in productos if p.nombre == "Albahaca")
    produccion.crear_lote(s, alb.planta_id, "Semilla", 150, ref - timedelta(days=5), alb.id, 3500, ref + timedelta(days=50),
                          "Invernadero 2", usuario_id=juan)


if __name__ == "__main__":
    main()
