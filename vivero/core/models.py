"""Modelo de datos del vivero (SQLAlchemy 2.0). Funciona igual en SQLite (local) y Postgres (nube)."""
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from .tiempo import ahora

# Exactos en la base, float en Python (pandas y Altair no se llevan bien con Decimal).
Dinero = Numeric(14, 2, asdecimal=False)
Cantidad = Numeric(12, 2, asdecimal=False)


class Base(DeclarativeBase):
    pass


def _texto(largo: int | None = None):
    return mapped_column(String(largo) if largo else Text, default="")


class Usuario(Base):
    __tablename__ = "usuarios"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(80))
    usuario: Mapped[str] = mapped_column(String(40), unique=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=ahora)


class Config(Base):
    __tablename__ = "config"
    clave: Mapped[str] = mapped_column(String(50), primary_key=True)
    valor: Mapped[str] = mapped_column(Text, default="")


class Categoria(Base):
    __tablename__ = "categorias"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(60), unique=True)
    tipo: Mapped[str] = mapped_column(String(10), default="planta")  # planta | insumo
    margen_objetivo: Mapped[float] = mapped_column(Numeric(7, 2, asdecimal=False), default=100)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class Planta(Base):
    """Ficha de la especie. Cada presentación que se vende (maceta 14, plantín…) es un Producto."""
    __tablename__ = "plantas"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre_comun: Mapped[str] = mapped_column(String(80))
    nombre_cientifico: Mapped[str] = _texto(120)
    categoria_id: Mapped[int | None] = mapped_column(ForeignKey("categorias.id"))
    ambiente: Mapped[str] = _texto(30)
    cuidados: Mapped[str] = _texto()
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    categoria: Mapped[Categoria | None] = relationship()


class Proveedor(Base):
    __tablename__ = "proveedores"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100))
    contacto: Mapped[str] = _texto(80)
    telefono: Mapped[str] = _texto(40)
    email: Mapped[str] = _texto(100)
    direccion: Mapped[str] = _texto(150)
    rubro: Mapped[str] = _texto(60)
    dias_entrega: Mapped[str] = _texto(60)
    condiciones_pago: Mapped[str] = _texto(100)
    cuit: Mapped[str] = _texto(20)
    notas: Mapped[str] = _texto()
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=ahora)


class Producto(Base):
    __tablename__ = "productos"
    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = _texto(40)
    nombre: Mapped[str] = mapped_column(String(100))
    presentacion: Mapped[str] = _texto(60)
    unidad: Mapped[str] = mapped_column(String(10), default="u")
    categoria_id: Mapped[int | None] = mapped_column(ForeignKey("categorias.id"))
    planta_id: Mapped[int | None] = mapped_column(ForeignKey("plantas.id"))
    proveedor_id: Mapped[int | None] = mapped_column(ForeignKey("proveedores.id"))
    precio: Mapped[float] = mapped_column(Dinero, default=0)
    costo_promedio: Mapped[float] = mapped_column(Dinero, default=0)
    costo_ultimo: Mapped[float] = mapped_column(Dinero, default=0)
    stock: Mapped[float] = mapped_column(Cantidad, default=0)
    stock_minimo: Mapped[float] = mapped_column(Cantidad, default=0)
    ubicacion: Mapped[str] = _texto(60)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    categoria: Mapped[Categoria | None] = relationship()
    planta: Mapped[Planta | None] = relationship()
    proveedor: Mapped[Proveedor | None] = relationship()

    @property
    def nombre_completo(self) -> str:
        return f"{self.nombre} · {self.presentacion}" if self.presentacion else self.nombre


class MovimientoStock(Base):
    __tablename__ = "movimientos_stock"
    id: Mapped[int] = mapped_column(primary_key=True)
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.id"), index=True)
    fecha: Mapped[datetime] = mapped_column(DateTime, default=ahora, index=True)
    tipo: Mapped[str] = mapped_column(String(15))  # ver constantes.TIPOS_MOVIMIENTO
    cantidad: Mapped[float] = mapped_column(Cantidad)
    costo_unitario: Mapped[float] = mapped_column(Dinero, default=0)
    motivo: Mapped[str] = _texto(60)
    ref_tipo: Mapped[str] = _texto(15)
    ref_id: Mapped[int | None] = mapped_column()
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    notas: Mapped[str] = _texto()


class Cliente(Base):
    __tablename__ = "clientes"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100))
    telefono: Mapped[str] = _texto(40)
    email: Mapped[str] = _texto(100)
    direccion: Mapped[str] = _texto(150)
    localidad: Mapped[str] = _texto(80)
    tipo: Mapped[str] = mapped_column(String(30), default="Particular")
    cuit_dni: Mapped[str] = _texto(20)
    notas: Mapped[str] = _texto()
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=ahora)


class Cobro(Base):
    """Pago de un cliente a su cuenta corriente."""
    __tablename__ = "cobros"
    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id"), index=True)
    fecha: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    monto: Mapped[float] = mapped_column(Dinero)
    medio_pago: Mapped[str] = mapped_column(String(30))
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    notas: Mapped[str] = _texto()


class Pedido(Base):
    __tablename__ = "pedidos"
    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id"), index=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    fecha_entrega: Mapped[date] = mapped_column(Date, index=True)
    estado: Mapped[str] = mapped_column(String(12), default="pendiente")
    entrega: Mapped[str] = mapped_column(String(10), default="Retira")  # Retira | Envío
    direccion: Mapped[str] = _texto(150)
    sena: Mapped[float] = mapped_column(Dinero, default=0)
    notas: Mapped[str] = _texto()
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    cliente: Mapped[Cliente] = relationship()
    items: Mapped[list["PedidoItem"]] = relationship(back_populates="pedido", cascade="all, delete-orphan")

    @property
    def total(self) -> float:
        return round(sum(i.cantidad * i.precio_unitario for i in self.items), 2)


class PedidoItem(Base):
    __tablename__ = "pedido_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    pedido_id: Mapped[int] = mapped_column(ForeignKey("pedidos.id"), index=True)
    producto_id: Mapped[int | None] = mapped_column(ForeignKey("productos.id"))  # vacío = encargo sin catalogar
    descripcion: Mapped[str] = mapped_column(String(160))
    cantidad: Mapped[float] = mapped_column(Cantidad)
    precio_unitario: Mapped[float] = mapped_column(Dinero, default=0)
    pedido: Mapped[Pedido] = relationship(back_populates="items")
    producto: Mapped[Producto | None] = relationship()


class Venta(Base):
    __tablename__ = "ventas"
    id: Mapped[int] = mapped_column(primary_key=True)
    fecha: Mapped[datetime] = mapped_column(DateTime, default=ahora, index=True)
    cliente_id: Mapped[int | None] = mapped_column(ForeignKey("clientes.id"), index=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    medio_pago: Mapped[str] = mapped_column(String(30))
    subtotal: Mapped[float] = mapped_column(Dinero)
    descuento: Mapped[float] = mapped_column(Dinero, default=0)
    total: Mapped[float] = mapped_column(Dinero)
    sena_aplicada: Mapped[float] = mapped_column(Dinero, default=0)
    estado: Mapped[str] = mapped_column(String(12), default="confirmada")  # confirmada | anulada
    pedido_id: Mapped[int | None] = mapped_column(ForeignKey("pedidos.id"))
    notas: Mapped[str] = _texto()
    anulada_en: Mapped[datetime | None] = mapped_column(DateTime)
    anulada_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    cliente: Mapped[Cliente | None] = relationship()
    items: Mapped[list["VentaItem"]] = relationship(back_populates="venta", cascade="all, delete-orphan")


class VentaItem(Base):
    __tablename__ = "venta_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    venta_id: Mapped[int] = mapped_column(ForeignKey("ventas.id"), index=True)
    producto_id: Mapped[int | None] = mapped_column(ForeignKey("productos.id"), index=True)  # vacío = servicio / ítem libre
    descripcion: Mapped[str] = mapped_column(String(160))
    cantidad: Mapped[float] = mapped_column(Cantidad)
    precio_unitario: Mapped[float] = mapped_column(Dinero)
    costo_unitario: Mapped[float] = mapped_column(Dinero, default=0)  # costo al momento de vender (para el margen)
    venta: Mapped[Venta] = relationship(back_populates="items")


class Compra(Base):
    __tablename__ = "compras"
    id: Mapped[int] = mapped_column(primary_key=True)
    proveedor_id: Mapped[int | None] = mapped_column(ForeignKey("proveedores.id"), index=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    estado: Mapped[str] = mapped_column(String(12), default="lista")  # ver constantes.ESTADOS_COMPRA
    fecha_pedido: Mapped[date | None] = mapped_column(Date)
    fecha_estimada: Mapped[date | None] = mapped_column(Date)
    fecha_recepcion: Mapped[date | None] = mapped_column(Date)
    fecha_venc_pago: Mapped[date | None] = mapped_column(Date)
    pagada: Mapped[bool] = mapped_column(Boolean, default=False)
    fecha_pago: Mapped[date | None] = mapped_column(Date)
    medio_pago: Mapped[str] = _texto(30)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    notas: Mapped[str] = _texto()
    proveedor: Mapped[Proveedor | None] = relationship()
    items: Mapped[list["CompraItem"]] = relationship(back_populates="compra", cascade="all, delete-orphan")

    @property
    def total(self) -> float:
        recibida = self.estado in ("parcial", "recibida")
        return round(sum((i.cantidad_recibida if recibida else i.cantidad) * i.costo_unitario for i in self.items), 2)


class CompraItem(Base):
    __tablename__ = "compra_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    compra_id: Mapped[int] = mapped_column(ForeignKey("compras.id"), index=True)
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.id"))
    cantidad: Mapped[float] = mapped_column(Cantidad)
    cantidad_recibida: Mapped[float] = mapped_column(Cantidad, default=0)
    costo_unitario: Mapped[float] = mapped_column(Dinero, default=0)
    pedido_item_id: Mapped[int | None] = mapped_column(ForeignKey("pedido_items.id"))  # encargo de un cliente
    compra: Mapped[Compra] = relationship(back_populates="items")
    producto: Mapped[Producto] = relationship()


class Recordatorio(Base):
    __tablename__ = "recordatorios"
    id: Mapped[int] = mapped_column(primary_key=True)
    titulo: Mapped[str] = mapped_column(String(150))
    descripcion: Mapped[str] = _texto()
    fecha: Mapped[date] = mapped_column(Date, index=True)
    asignado_a: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))  # vacío = los dos
    repeticion: Mapped[str] = mapped_column(String(10), default="no")
    hecho: Mapped[bool] = mapped_column(Boolean, default=False)
    hecho_en: Mapped[datetime | None] = mapped_column(DateTime)
    creado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=ahora)


class Lote(Base):
    """Lote de producción propia (semillas, esquejes…) hasta que pasa a stock."""
    __tablename__ = "lotes"
    id: Mapped[int] = mapped_column(primary_key=True)
    planta_id: Mapped[int | None] = mapped_column(ForeignKey("plantas.id"))
    producto_id: Mapped[int | None] = mapped_column(ForeignKey("productos.id"))
    metodo: Mapped[str] = mapped_column(String(30))
    fecha_inicio: Mapped[date] = mapped_column(Date)
    cantidad_inicial: Mapped[float] = mapped_column(Cantidad)
    cantidad_actual: Mapped[float] = mapped_column(Cantidad)
    etapa: Mapped[str] = mapped_column(String(40))
    ubicacion: Mapped[str] = _texto(60)
    costo_total: Mapped[float] = mapped_column(Dinero, default=0)
    fecha_estimada: Mapped[date | None] = mapped_column(Date)
    estado: Mapped[str] = mapped_column(String(12), default="activo")  # activo | terminado
    notas: Mapped[str] = _texto()
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    planta: Mapped[Planta | None] = relationship()
    producto: Mapped[Producto | None] = relationship()
    eventos: Mapped[list["LoteEvento"]] = relationship(back_populates="lote", cascade="all, delete-orphan")


class LoteEvento(Base):
    __tablename__ = "lote_eventos"
    id: Mapped[int] = mapped_column(primary_key=True)
    lote_id: Mapped[int] = mapped_column(ForeignKey("lotes.id"), index=True)
    fecha: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    tipo: Mapped[str] = mapped_column(String(15))  # perdida | etapa | a_stock | nota
    cantidad: Mapped[float] = mapped_column(Cantidad, default=0)
    detalle: Mapped[str] = _texto(200)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    lote: Mapped[Lote] = relationship(back_populates="eventos")
