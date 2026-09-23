CUENTA_CORRIENTE = "Cuenta corriente"

MOTIVOS_MERMA = ["Se secó / murió", "Enfermedad", "Plaga", "Helada / clima", "Rotura",
                 "Robo / faltante", "Uso interno", "Otro"]
TIPOS_CLIENTE = ["Particular", "Paisajista", "Mayorista / revendedor", "Empresa / institución"]
AMBIENTES = ["", "Interior", "Exterior", "Interior y exterior"]
UNIDADES = ["u", "kg", "L", "m", "bolsa", "bandeja"]
TIPOS_CATEGORIA = {"planta": "Plantas", "insumo": "Insumos y accesorios"}

ESTADOS_PEDIDO = {"pendiente": "Pendiente", "listo": "Listo para entregar",
                  "entregado": "Entregado", "cancelado": "Cancelado"}
PEDIDO_ABIERTO = ("pendiente", "listo")
ESTADOS_COMPRA = {"lista": "Lista de compras", "pedida": "Pedida", "parcial": "Recibida parcial",
                  "recibida": "Recibida", "cancelada": "Cancelada"}
REPETICIONES = {"no": "No se repite", "semanal": "Cada semana", "mensual": "Cada mes"}

METODOS_PRODUCCION = ["Semilla", "Esqueje / estaca", "División", "Injerto", "Acodo", "Otro"]
ETAPAS_LOTE = ["Siembra / estaca", "Germinación / enraizado", "Plantín", "Repique / trasplante",
               "Crecimiento", "Lista para venta"]

TIPOS_MOVIMIENTO = {"inicial": "Stock inicial", "compra": "Compra", "venta": "Venta", "anulacion": "Anulación de venta",
                    "ajuste": "Ajuste de inventario", "merma": "Merma / pérdida", "produccion": "Producción propia"}

CATEGORIAS_INICIALES = [
    ("Plantas de interior", "planta"), ("Plantas de exterior", "planta"), ("Aromáticas y huerta", "planta"),
    ("Frutales", "planta"), ("Suculentas y cactus", "planta"), ("Árboles", "planta"), ("Arbustos", "planta"),
    ("Florales de estación", "planta"), ("Macetas", "insumo"), ("Tierra y sustratos", "insumo"),
    ("Fertilizantes y fitosanitarios", "insumo"), ("Herramientas y accesorios", "insumo"),
]
