"""Estadísticas de ventas y de plantas. Todo devuelve DataFrames listos para graficar."""
from datetime import date, datetime, time, timedelta

import pandas as pd
from sqlalchemy import func, select

from ..models import Categoria, Cliente, Lote, LoteEvento, MovimientoStock, Planta, Producto, Usuario, Venta, VentaItem
from ..tiempo import hoy
from .util import df_query, nombre_producto

DIAS_SEMANA = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def _rango(desde: date, hasta: date) -> list:
    return [Venta.estado == "confirmada", Venta.fecha >= datetime.combine(desde, time.min),
            Venta.fecha <= datetime.combine(hasta, time.max)]


def periodo_anterior(desde: date, hasta: date) -> tuple[date, date]:
    largo = (hasta - desde).days + 1
    return desde - timedelta(days=largo), desde - timedelta(days=1)


def ventas_df(s, desde: date, hasta: date) -> pd.DataFrame:
    """Una fila por venta confirmada."""
    df = df_query(s, select(Venta.id, Venta.fecha, Venta.cliente_id, Cliente.nombre.label("cliente"),
                            Cliente.tipo.label("tipo_cliente"), Venta.medio_pago, Venta.subtotal, Venta.descuento,
                            Venta.total, Usuario.nombre.label("usuario"))
                  .outerjoin(Cliente, Cliente.id == Venta.cliente_id).outerjoin(Usuario, Usuario.id == Venta.usuario_id)
                  .where(*_rango(desde, hasta)))
    df["fecha"] = pd.to_datetime(df["fecha"])
    df["cliente"] = df["cliente"].fillna("Consumidor final")
    df["tipo_cliente"] = df["tipo_cliente"].fillna("Consumidor final")
    df["usuario"] = df["usuario"].fillna("—")
    return df


def items_df(s, desde: date, hasta: date) -> pd.DataFrame:
    """Una fila por ítem vendido, con el descuento de la venta prorrateado y su costo."""
    df = df_query(s, select(VentaItem.venta_id, Venta.fecha, VentaItem.producto_id, VentaItem.descripcion,
                            VentaItem.cantidad, VentaItem.precio_unitario, VentaItem.costo_unitario, Venta.subtotal,
                            Venta.total, Producto.nombre, Producto.presentacion, Planta.nombre_comun.label("planta"),
                            Categoria.nombre.label("categoria"), Categoria.tipo.label("tipo_categoria"))
                  .join(Venta, Venta.id == VentaItem.venta_id)
                  .outerjoin(Producto, Producto.id == VentaItem.producto_id)
                  .outerjoin(Planta, Planta.id == Producto.planta_id)
                  .outerjoin(Categoria, Categoria.id == Producto.categoria_id)
                  .where(*_rango(desde, hasta)))
    df["fecha"] = pd.to_datetime(df["fecha"])
    factor = (df["total"] / df["subtotal"]).where(df["subtotal"] > 0, 1.0)
    df["importe"] = df["cantidad"] * df["precio_unitario"] * factor
    df["costo"] = df["cantidad"] * df["costo_unitario"]
    df["margen"] = df["importe"] - df["costo"]
    df["producto"] = [nombre_producto(n, p) if isinstance(n, str) else d
                      for n, p, d in zip(df["nombre"], df["presentacion"], df["descripcion"])]
    df["planta"] = df["planta"].fillna(df["nombre"]).fillna(df["descripcion"])  # insumos: por su nombre
    df["categoria"] = df["categoria"].fillna("Servicios y otros")
    return df


def kpis(ventas: pd.DataFrame, items: pd.DataFrame) -> dict:
    facturacion, n = float(ventas["total"].sum()), len(ventas)
    costo = float(items["costo"].sum())
    return {"facturacion": facturacion, "ventas": n, "ticket": facturacion / n if n else 0.0,
            "margen": facturacion - costo, "margen_pct": (facturacion - costo) / facturacion * 100 if facturacion else 0.0,
            "unidades": float(items.loc[items["producto_id"].notna(), "cantidad"].sum())}


def serie(ventas: pd.DataFrame, freq: str, desde: date | None = None, hasta: date | None = None) -> pd.DataFrame:
    """freq: D (día), W (semana) o M (mes). Con desde/hasta completa con cero los períodos sin ventas."""
    columnas = ["periodo", "facturacion", "ventas"]
    if ventas.empty:
        df = pd.DataFrame(columns=columnas)
    else:
        periodo = ventas["fecha"].dt.to_period(freq).dt.start_time
        df = (ventas.groupby(periodo).agg(facturacion=("total", "sum"), ventas=("id", "count"))
              .rename_axis("periodo").reset_index())
    if desde and hasta:
        todos = pd.period_range(desde, hasta, freq=freq).start_time
        df = (df.set_index("periodo").reindex(todos, fill_value=0).rename_axis("periodo").reset_index()
              .astype({"facturacion": float, "ventas": int}))
    return df


def comparativo_anual(s, ref: date | None = None) -> pd.DataFrame:
    """Facturación por mes de este año y del anterior."""
    ref = ref or hoy()
    v = ventas_df(s, date(ref.year - 1, 1, 1), ref)
    if v.empty:
        return pd.DataFrame(columns=["mes", "anio", "facturacion"])
    out = v.groupby([v["fecha"].dt.month.rename("mes"), v["fecha"].dt.year.rename("anio")])["total"].sum()
    out = out.rename("facturacion").reset_index()
    out["anio"] = out["anio"].astype(str)
    out["mes_nombre"] = out["mes"].map(lambda m: MESES[m - 1])
    return out


def por(df: pd.DataFrame, columna: str, valor: str = "total") -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=[columna, valor])
    return df.groupby(columna, as_index=False)[valor].sum().sort_values(valor, ascending=False)


def dia_hora(ventas: pd.DataFrame) -> pd.DataFrame:
    if ventas.empty:
        return pd.DataFrame(columns=["dia", "hora", "ventas", "facturacion"])
    df = ventas.assign(dia=ventas["fecha"].dt.dayofweek.map(lambda d: DIAS_SEMANA[d]), hora=ventas["fecha"].dt.hour)
    return df.groupby(["dia", "hora"], as_index=False).agg(ventas=("id", "count"), facturacion=("total", "sum"))


def clientes_resumen(s, ventas: pd.DataFrame, desde: date, dias_inactivo: int = 90, ref: date | None = None) -> dict:
    ref = ref or hoy()
    con_cliente = ventas[ventas["cliente_id"].notna()]
    top = (con_cliente.groupby("cliente", as_index=False).agg(total=("total", "sum"), compras=("id", "count"))
           .sort_values("total", ascending=False))
    historia = df_query(s, select(Venta.cliente_id, Cliente.nombre.label("cliente"), Cliente.telefono,
                                  func.min(Venta.fecha).label("primera"), func.max(Venta.fecha).label("ultima"),
                                  func.sum(Venta.total).label("total_historico"), func.count(Venta.id).label("compras"))
                        .join(Cliente, Cliente.id == Venta.cliente_id)
                        .where(Venta.estado == "confirmada", Cliente.activo.is_(True))
                        .group_by(Venta.cliente_id, Cliente.nombre, Cliente.telefono))
    historia["primera"], historia["ultima"] = pd.to_datetime(historia["primera"]), pd.to_datetime(historia["ultima"])
    ids = set(con_cliente["cliente_id"].astype(int))
    primeras = historia.set_index("cliente_id")["primera"]
    nuevos = sum(1 for i in ids if primeras.get(i) is not None and primeras[i].date() >= desde)
    limite = pd.Timestamp(ref - timedelta(days=dias_inactivo))
    inactivos = historia[historia["ultima"] < limite].sort_values("total_historico", ascending=False)
    inactivos = inactivos.assign(dias=(pd.Timestamp(ref) - inactivos["ultima"]).dt.days)
    return {"top": top, "nuevos": nuevos, "recurrentes": len(ids) - nuevos,
            "sin_cliente": int(ventas["cliente_id"].isna().sum()), "inactivos": inactivos}


# ---- Plantas / stock --------------------------------------------------------------------------

def ranking(items: pd.DataFrame, columna: str = "planta") -> pd.DataFrame:
    if items.empty:
        return pd.DataFrame(columns=[columna, "unidades", "importe", "margen", "margen_pct"])
    df = items.groupby(columna, as_index=False).agg(unidades=("cantidad", "sum"), importe=("importe", "sum"),
                                                    margen=("margen", "sum"))
    df["margen_pct"] = (df["margen"] / df["importe"] * 100).where(df["importe"] > 0, 0.0)
    return df.sort_values("importe", ascending=False)


def rotacion(s, df_productos: pd.DataFrame, items: pd.DataFrame, desde: date, hasta: date,
             ref: date | None = None) -> pd.DataFrame:
    """Por producto con stock: vendido en el período, días de cobertura y última venta."""
    ref = ref or hoy()
    ultima = dict(s.execute(select(VentaItem.producto_id, func.max(Venta.fecha)).join(Venta, Venta.id == VentaItem.venta_id)
                            .where(Venta.estado == "confirmada", VentaItem.producto_id.is_not(None))
                            .group_by(VentaItem.producto_id)).all())
    vendidas = items.groupby("producto_id")["cantidad"].sum() if not items.empty else pd.Series(dtype=float)
    dias = max((hasta - desde).days + 1, 1)
    df = df_productos[df_productos["stock"] > 0][["id", "producto", "categoria", "stock", "costo_promedio", "valor_costo"]].copy()
    df["vendidas"] = df["id"].map(vendidas).fillna(0.0)
    df["cobertura_dias"] = (df["stock"] / (df["vendidas"] / dias)).where(df["vendidas"] > 0)
    df["ultima_venta"] = pd.to_datetime(df["id"].map(ultima))
    df["dias_sin_venta"] = (pd.Timestamp(ref) - df["ultima_venta"]).dt.days
    return df


def mermas(s, desde: date, hasta: date) -> pd.DataFrame:
    df = df_query(s, select(MovimientoStock.fecha, MovimientoStock.producto_id, Producto.nombre, Producto.presentacion,
                            Planta.nombre_comun.label("planta"), Categoria.nombre.label("categoria"),
                            MovimientoStock.motivo, MovimientoStock.cantidad, MovimientoStock.costo_unitario)
                  .join(Producto, Producto.id == MovimientoStock.producto_id)
                  .outerjoin(Planta, Planta.id == Producto.planta_id)
                  .outerjoin(Categoria, Categoria.id == Producto.categoria_id)
                  .where(MovimientoStock.tipo == "merma", MovimientoStock.fecha >= datetime.combine(desde, time.min),
                         MovimientoStock.fecha <= datetime.combine(hasta, time.max)))
    df["unidades"] = -df["cantidad"]
    df["valor"] = df["unidades"] * df["costo_unitario"]
    df["producto"] = [nombre_producto(n, p) for n, p in zip(df["nombre"], df["presentacion"])]
    df["planta"] = df["planta"].fillna(df["nombre"])
    df["motivo"] = df["motivo"].replace("", "Sin motivo")
    return df


def valor_stock(df_productos: pd.DataFrame) -> dict:
    con_stock = df_productos[df_productos["stock"] > 0]
    return {"costo": float((con_stock["stock"] * con_stock["costo_promedio"]).sum()),
            "venta": float((con_stock["stock"] * con_stock["precio"]).sum()),
            "unidades": float(con_stock["stock"].sum()), "productos": len(con_stock)}


def estacionalidad(s, top: int = 15, meses: int = 24, ref: date | None = None) -> pd.DataFrame:
    """Unidades vendidas por planta y mes del año (últimos `meses` meses), para las más vendidas."""
    ref = ref or hoy()
    it = items_df(s, ref - timedelta(days=meses * 30), ref)
    it = it[it["producto_id"].notna()]
    if it.empty:
        return pd.DataFrame(columns=["planta", "mes", "mes_nombre", "unidades"])
    principales = it.groupby("planta")["cantidad"].sum().nlargest(top).index
    it = it[it["planta"].isin(principales)]
    df = it.groupby([it["planta"], it["fecha"].dt.month.rename("mes")])["cantidad"].sum().rename("unidades").reset_index()
    df["mes_nombre"] = df["mes"].map(lambda m: MESES[m - 1])
    return df


def alertas_temporada(s, ref: date | None = None, ventana: int = 30, maximo: int = 5) -> pd.DataFrame:
    """Productos que el año pasado se vendieron fuerte en las próximas semanas y hoy tienen poco stock."""
    ref = ref or hoy()
    columnas = ["producto_id", "producto", "vendido", "disponible"]
    primera = s.scalar(select(func.min(Venta.fecha)).where(Venta.estado == "confirmada"))
    if primera is None or primera.date() > ref - timedelta(days=365):
        return pd.DataFrame(columns=columnas)
    desde = ref - timedelta(days=365)
    it = items_df(s, desde, desde + timedelta(days=ventana))
    it = it[it["producto_id"].notna()]
    if it.empty:
        return pd.DataFrame(columns=columnas)
    vendido = it.groupby("producto_id")["cantidad"].sum()
    from . import stock
    prods = stock.tabla_productos(s).set_index("id")
    filas = [{"producto_id": pid, "producto": prods.at[pid, "producto"], "vendido": float(v),
              "disponible": float(prods.at[pid, "disponible"])}
             for pid, v in vendido.items() if pid in prods.index and v >= 5 and prods.at[pid, "disponible"] < v * 0.5]
    return pd.DataFrame(filas, columns=columnas).sort_values("vendido", ascending=False).head(maximo)


def produccion(s) -> pd.DataFrame:
    """Resultado de los lotes: % de éxito, días hasta pasar a stock y costo por planta."""
    lotes = df_query(s, select(Lote.id, Lote.metodo, Lote.fecha_inicio, Lote.cantidad_inicial, Lote.cantidad_actual,
                               Lote.costo_total, Lote.estado, Planta.nombre_comun.label("planta"))
                     .outerjoin(Planta, Planta.id == Lote.planta_id))
    if lotes.empty:
        return lotes.assign(a_stock=[], perdidas=[], exito_pct=[], dias_a_stock=[], costo_por_planta=[])
    ev = df_query(s, select(LoteEvento.lote_id, LoteEvento.tipo, LoteEvento.cantidad, LoteEvento.fecha))
    a_stock = ev[ev["tipo"] == "a_stock"].groupby("lote_id")["cantidad"].sum()
    perdidas = ev[ev["tipo"] == "perdida"].groupby("lote_id")["cantidad"].sum()
    primera_salida = pd.to_datetime(ev[ev["tipo"] == "a_stock"].groupby("lote_id")["fecha"].min())
    lotes["a_stock"] = lotes["id"].map(a_stock).fillna(0.0)
    lotes["perdidas"] = lotes["id"].map(perdidas).fillna(0.0)
    lotes["exito_pct"] = lotes["a_stock"] / lotes["cantidad_inicial"] * 100
    lotes["dias_a_stock"] = (lotes["id"].map(primera_salida) - pd.to_datetime(lotes["fecha_inicio"])).dt.days
    lotes["costo_por_planta"] = (lotes["costo_total"] / lotes["a_stock"]).where(lotes["a_stock"] > 0)
    lotes["planta"] = lotes["planta"].fillna("—")
    return lotes
