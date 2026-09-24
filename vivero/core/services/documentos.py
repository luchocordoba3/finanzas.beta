"""Comprobante de venta en PDF y copia de seguridad en Excel."""
import io

import pandas as pd
from sqlalchemy import select

from ..models import Base, Venta
from .util import df_query


def _t(texto) -> str:  # las fuentes base del PDF solo tienen latin-1
    return str(texto).replace("—", "-").replace("·", "-").encode("latin-1", "replace").decode("latin-1")


def _pesos(v: float) -> str:
    return "$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def comprobante_venta(venta: Venta, cfg: dict) -> bytes:
    from fpdf import FPDF  # import diferido: solo se usa al imprimir

    pdf = FPDF(format="A5")
    pdf.set_margins(10, 10, 10)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 15)
    pdf.cell(0, 8, _t(cfg.get("nombre_vivero", "Vivero")), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    for extra in (cfg.get("direccion"), cfg.get("telefono")):
        if extra:
            pdf.cell(0, 5, _t(extra), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 6, _t(f"Comprobante de venta N° {venta.id:06d}"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    cliente = venta.cliente.nombre if venta.cliente else "Consumidor final"
    for linea in (f"Fecha: {venta.fecha:%d/%m/%Y %H:%M}", f"Cliente: {cliente}", f"Medio de pago: {venta.medio_pago}"):
        pdf.cell(0, 5, _t(linea), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    anchos = (14, 64, 25, 25)
    pdf.set_font("Helvetica", "B", 9)
    for ancho, titulo, alin in zip(anchos, ("Cant.", "Descripción", "P. unit.", "Subtotal"), "LLRR"):
        pdf.cell(ancho, 6, _t(titulo), border="B", align=alin)
    pdf.ln()
    pdf.set_font("Helvetica", "", 9)
    for it in venta.items:
        desc = _t(it.descripcion)
        while pdf.get_string_width(desc) > anchos[1] - 2:
            desc = desc[:-1]
        for ancho, valor, alin in zip(anchos, (f"{it.cantidad:g}", desc, _pesos(it.precio_unitario),
                                               _pesos(it.cantidad * it.precio_unitario)), "LLRR"):
            pdf.cell(ancho, 6, _t(valor), align=alin)
        pdf.ln()
    pdf.ln(2)
    filas = [("Subtotal", venta.subtotal)]
    if venta.descuento:
        filas.append(("Descuento", -venta.descuento))
    filas.append(("Total", venta.total))
    if venta.sena_aplicada:
        filas += [("Seña ya pagada", -venta.sena_aplicada), ("Saldo pagado", venta.total - venta.sena_aplicada)]
    for etiqueta, valor in filas:
        pdf.set_font("Helvetica", "B" if etiqueta in ("Total", "Saldo pagado") else "", 10)
        pdf.cell(sum(anchos[:3]), 6, _t(etiqueta), align="R")
        pdf.cell(anchos[3], 6, _t(_pesos(valor)), align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)
    pdf.set_font("Helvetica", "I", 8)
    pdf.cell(0, 5, _t("Documento no válido como factura. ¡Gracias por su compra!"), align="C")
    return bytes(pdf.output())


def backup_excel(s) -> bytes:
    """Todas las tablas en un Excel (una hoja por tabla), sin las contraseñas."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        for tabla in Base.metadata.sorted_tables:
            df = df_query(s, select(tabla))
            df = df.drop(columns=["password_hash"], errors="ignore")
            if tabla.name == "config":  # las claves (bot de Telegram, notificaciones) no van en la copia
                df = df[~df["clave"].isin(["telegram_token", "push_vapid_privada"])]
            df.to_excel(xw, sheet_name=tabla.name[:31], index=False)
    return buf.getvalue()
