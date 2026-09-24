from datetime import timedelta

import pytest

from core import auth
from core.services import (avisos, compras, config, documentos, notificaciones, pedidos, proveedores,
                           recordatorios, ventas, whatsapp)
from core.tiempo import hoy


@pytest.mark.parametrize("telefono, esperado", [
    ("11 5555-1234", "5491155551234"),
    ("011 15 5555-1234", "5491155551234"),
    ("+54 9 11 5555-1234", "5491155551234"),
    ("+54 11 5555 1234", "5491155551234"),
    ("15 5555-1234", "5491155551234"),
    ("5555-1234", "5491155551234"),
    ("351 15 612-3456", "5493516123456"),
    ("2944 15 123456", "5492944123456"),
    ("", None),
    ("123", None),
])
def test_whatsapp_entiende_numeros_argentinos(telefono, esperado):
    assert whatsapp.normalizar_telefono(telefono, "11") == esperado


def test_whatsapp_link_y_mensajes():
    url = whatsapp.link("11 5555-1234", "¡Hola Ana! Tu pedido está listo 🌱", "11")
    assert url.startswith("https://wa.me/5491155551234?text=%C2%A1Hola%20Ana")
    pedido = {"total": 30000, "sena": 10000, "entrega": "Retira", "detalle": "2× Potus"}
    texto = whatsapp.mensaje("listo", "Ana", "Vivero Malén", pedido)
    assert "listo para retirar" in texto and "$ 20.000" in texto
    assert "$ 5.500" in whatsapp.mensaje("saldo", "Ana", "Vivero Malén", saldo=5500)
    assert whatsapp.saludo("Ana Pérez") == "Ana"
    assert whatsapp.saludo("Jardines Verdes", "Paisajista") == "Jardines Verdes"


def test_los_servicios_encolan_avisos(s, nuevo_producto, cliente):
    ana, juan = auth.crear_usuario(s, "Ana", "ana", "123456"), auth.crear_usuario(s, "Juan", "juan", "123456")
    p = nuevo_producto(stock=6, minimo=5)
    ventas.crear_venta(s, [{"producto_id": p.id, "cantidad": 2, "precio": 1}], "Efectivo", ana.id)
    ventas.crear_venta(s, [{"producto_id": p.id, "cantidad": 4, "precio": 1}], "Efectivo", ana.id)
    ped = pedidos.crear_pedido(s, cliente.id, hoy() + timedelta(days=3),
                               [{"producto_id": None, "descripcion": "Olivo <grande>", "cantidad": 1, "precio": 1}], ana.id)
    recordatorios.crear(s, "Pagar la luz", hoy(), ana.id, juan.id)
    recordatorios.crear(s, "Regar", hoy(), ana.id, ana.id)  # uno para uno mismo: no avisa
    olivo = nuevo_producto(nombre="Olivo", stock=0, proveedor_id=proveedores.guardar(s, {"nombre": "Mayorista"}).id)
    item = pedidos.encargar_item(s, ped.items[0].id, ana.id, producto_id=olivo.id)
    compras.marcar_pedida(s, item.compra.id)
    compras.recibir(s, item.compra.id, {item.id: (1, 100)})
    lista = avisos.pendientes(s)
    textos = [a["texto"] for a in lista]
    assert any("quedan 4" in t for t in textos) and any("Se agotó" in t for t in textos)
    nuevo = next(a for a in lista if "Pedido nuevo" in a["texto"])
    assert nuevo["excepto"] == ana.id and "Olivo &lt;grande&gt;" in nuevo["texto"]  # datos escapados
    luz = next(a for a in lista if "Pagar la luz" in a["texto"])
    assert luz["para"] == [juan.id] and "Ana te dejó" in luz["texto"]
    assert not any("Regar" in t for t in textos)
    assert any("Llegó lo encargado para el pedido" in t for t in textos)


def test_enviar_avisos_a_quien_corresponde(s, monkeypatch):
    ana, juan = auth.crear_usuario(s, "Ana", "ana", "123456"), auth.crear_usuario(s, "Juan", "juan", "123456")
    enviados = []
    monkeypatch.setattr(notificaciones, "enviar", lambda token, chat, texto: enviados.append((chat, texto)))
    assert notificaciones.enviar_avisos(s, [{"texto": "hola", "para": None, "excepto": None}]) == 0  # sin bot
    config.guardar(s, {"telegram_token": "123:abc", f"telegram_chat_{ana.id}": "111", f"telegram_chat_{juan.id}": "222"})
    n = notificaciones.enviar_avisos(s, [{"texto": "a todos", "para": None, "excepto": None},
                                         {"texto": "menos Ana", "para": None, "excepto": ana.id},
                                         {"texto": "solo Juan", "para": [juan.id], "excepto": None}])
    assert n == 4
    assert sorted(enviados) == [("111", "a todos"), ("222", "a todos"), ("222", "menos Ana"), ("222", "solo Juan")]


def test_conectar_bot_y_usuario(s, monkeypatch):
    ana = auth.crear_usuario(s, "Ana", "ana", "123456")
    llamadas = []

    def falso(token, metodo, **params):
        llamadas.append(metodo)
        if token == "malo":
            raise notificaciones.ErrorTelegram("Unauthorized")
        if metodo == "getMe":
            return {"username": "vivero_malen_bot"}
        if metodo == "getUpdates":
            codigo = config.obtener(s, f"telegram_codigo_{ana.id}")
            return [{"message": {"text": "hola", "chat": {"id": 1}}},
                    {"message": {"text": f"/start {codigo}", "chat": {"id": 999}}}]
        return {}

    monkeypatch.setattr(notificaciones, "_llamar", falso)
    with pytest.raises(ValueError, match="no reconoce ese token"):
        notificaciones.configurar_bot(s, "malo")
    assert notificaciones.configurar_bot(s, " 123:abc ", "https://vivero-malen.streamlit.app") == "vivero_malen_bot"
    assert notificaciones.token(s) == "123:abc" and config.obtener(s, "url_app") == "https://vivero-malen.streamlit.app"
    link = notificaciones.link_conexion(s, ana.id)
    assert link.startswith("https://t.me/vivero_malen_bot?start=")
    assert notificaciones.link_conexion(s, ana.id) == link  # el código no cambia
    assert notificaciones.confirmar_conexion(s, ana.id)
    assert notificaciones.chat(s, ana.id) == "999" and "sendMessage" in llamadas
    notificaciones.desconectar(s, ana.id)
    assert notificaciones.conectados(s) == {}


def test_resumen_diario(s, nuevo_producto, cliente, monkeypatch):
    ana = auth.crear_usuario(s, "Ana", "ana", "123456")
    p = nuevo_producto(stock=10)
    for i in range(8):
        pedidos.crear_pedido(s, cliente.id, hoy(), [{"producto_id": p.id, "cantidad": 1, "precio": 1}], ana.id)
    config.guardar(s, {"url_app": "https://vivero-malen.streamlit.app"})
    texto = notificaciones.resumen(s, ana.id)
    assert texto.startswith("🌱 <b>Buen día, Ana</b>") and "Pedidos para entregar</b> (8)" in texto
    assert "… y 4 más" in texto and texto.endswith("https://vivero-malen.streamlit.app")
    enviados = []
    monkeypatch.setattr(notificaciones, "enviar", lambda token, chat, texto: enviados.append(chat))
    assert notificaciones.enviar_resumen_diario(s) == 0  # sin bot
    config.guardar(s, {"telegram_token": "123:abc", f"telegram_chat_{ana.id}": "111"})
    assert notificaciones.enviar_resumen_diario(s) == 1 and enviados == ["111"]


def test_mensaje_largo_se_recorta(monkeypatch):
    enviado = {}
    monkeypatch.setattr(notificaciones, "_llamar", lambda token, metodo, **p: enviado.update(p))
    notificaciones.enviar("t", "1", "\n".join(f"linea {i}" for i in range(2000)))
    assert len(enviado["text"]) <= 4096 and enviado["text"].endswith("…")


def test_backup_no_incluye_el_token(s):
    import io
    import pandas as pd
    config.guardar(s, {"telegram_token": "secreto", "nombre_vivero": "Vivero"})
    s.flush()
    hojas = pd.read_excel(io.BytesIO(documentos.backup_excel(s)), sheet_name=None)
    assert "secreto" not in hojas["config"].to_string() and "Vivero" in hojas["config"].to_string()
