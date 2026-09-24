import base64
import json
import os

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from core import auth
from core.models import Dispositivo
from core.services import config, documentos, notificaciones, push


def navegador():
    """Claves como las que genera un navegador al suscribirse."""
    privada = ec.generate_private_key(ec.SECP256R1())
    return privada, push.b64url(push._punto(privada.public_key())), push.b64url(os.urandom(16))


def descifrar(cuerpo: bytes, privada, p256dh: str, auth_b64: str) -> bytes:
    """Lo que hace el navegador al recibir (RFC 8291), para comprobar el cifrado."""
    salt, largo = cuerpo[:16], cuerpo[20]
    emisor, cifrado = cuerpo[21:21 + largo], cuerpo[21 + largo:]
    compartido = privada.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), emisor))
    ikm = HKDF(hashes.SHA256(), 32, salt=push.de_b64url(auth_b64),
               info=b"WebPush: info\x00" + push.de_b64url(p256dh) + emisor).derive(compartido)
    clave = HKDF(hashes.SHA256(), 16, salt=salt, info=b"Content-Encoding: aes128gcm\x00").derive(ikm)
    nonce = HKDF(hashes.SHA256(), 12, salt=salt, info=b"Content-Encoding: nonce\x00").derive(ikm)
    plano = AESGCM(clave).decrypt(nonce, cifrado, None)
    assert plano.endswith(b"\x02")
    return plano[:-1]


def codigo_activacion(endpoint="https://fcm.googleapis.com/fcm/send/abc123", nombre="Android · Chrome"):
    _, p256dh, auth_b64 = navegador()
    datos = {"sub": {"endpoint": endpoint, "keys": {"p256dh": p256dh, "auth": auth_b64}}, "nombre": nombre}
    return base64.urlsafe_b64encode(json.dumps(datos).encode()).rstrip(b"=").decode()


class Respuesta:
    def __init__(self, status_code):
        self.status_code = status_code


def test_claves_se_generan_una_vez(s):
    privada, publica = push.claves(s)
    assert push.clave_publica(s) == publica
    assert len(push.de_b64url(publica)) == 65 and push.de_b64url(publica)[0] == 4


def test_cifrado_se_puede_descifrar(s):
    privada, p256dh, auth_b64 = navegador()
    mensaje = json.dumps({"title": "Vivero", "body": "Pedido nuevo #12 🌱"}, ensure_ascii=False).encode()
    assert descifrar(push.cifrar(mensaje, p256dh, auth_b64), privada, p256dh, auth_b64) == mensaje


def test_firma_vapid_valida(s):
    privada, _ = push.claves(s)
    cabecera, datos, firma = push.firma_vapid(privada, "https://web.push.apple.com/abc", "https://vivero.streamlit.app").split(".")
    crudo = push.de_b64url(firma)
    privada.public_key().verify(encode_dss_signature(int.from_bytes(crudo[:32], "big"), int.from_bytes(crudo[32:], "big")),
                                f"{cabecera}.{datos}".encode(), ec.ECDSA(hashes.SHA256()))
    assert json.loads(push.de_b64url(datos))["aud"] == "https://web.push.apple.com"


def test_registrar_dispositivo(s):
    ana, juan = auth.crear_usuario(s, "Ana", "ana", "123456"), auth.crear_usuario(s, "Juan", "juan", "123456")
    codigo = codigo_activacion()
    d = push.registrar(s, ana.id, codigo)
    assert d.nombre == "Android · Chrome" and push.dispositivos(s, ana.id) == [d]
    push.registrar(s, juan.id, codigo)  # mismo celular, otro usuario: se pasa, no se duplica
    assert push.dispositivos(s, ana.id) == [] and len(push.dispositivos(s)) == 1
    for malo in ("", "no-es-base64!!", codigo_activacion(endpoint="http://inseguro.com")):
        with pytest.raises(ValueError, match="incompleto"):
            push.registrar(s, ana.id, malo)


def test_enviar_y_limpiar_dispositivos_vencidos(s, monkeypatch):
    ana = auth.crear_usuario(s, "Ana", "ana", "123456")
    d = push.registrar(s, ana.id, codigo_activacion())
    config.guardar(s, {"url_app": "https://vivero-malen.streamlit.app", "nombre_vivero": "Vivero Malén"})
    llamadas = []

    def post(url, data, timeout, headers):
        llamadas.append((url, headers))
        return Respuesta(201)

    monkeypatch.setattr(push.requests, "post", post)
    assert push.enviar(s, d, "Vivero Malén", "Hola")
    url, cabeceras = llamadas[0]
    assert url == d.endpoint and cabeceras["Content-Encoding"] == "aes128gcm"
    assert cabeceras["Authorization"].startswith("vapid t=") and f"k={push.clave_publica(s)}" in cabeceras["Authorization"]
    assert push.probar(s, ana.id) == 1
    monkeypatch.setattr(push.requests, "post", lambda *a, **k: Respuesta(410))
    assert not push.enviar(s, d, "Vivero", "Hola")
    s.flush()
    assert s.get(Dispositivo, d.id) is None
    with pytest.raises(ValueError, match="Todavía no activaste"):
        push.probar(s, ana.id)


def test_avisos_y_resumen_llegan_como_notificacion(s, nuevo_producto, cliente, monkeypatch):
    from core.services import pedidos
    from core.tiempo import hoy
    ana, juan = auth.crear_usuario(s, "Ana", "ana", "123456"), auth.crear_usuario(s, "Juan", "juan", "123456")
    push.registrar(s, ana.id, codigo_activacion("https://fcm.googleapis.com/fcm/send/ana"))
    push.registrar(s, juan.id, codigo_activacion("https://fcm.googleapis.com/fcm/send/juan"))
    enviadas = []
    monkeypatch.setattr(push, "enviar", lambda s_, d, titulo, cuerpo, url="", etiqueta=None: enviadas.append((d.usuario_id, titulo, cuerpo)) or True)
    n = notificaciones.enviar_avisos(s, [{"texto": "📦 Pedido nuevo de <b>Ana &amp; Juan</b>", "para": None, "excepto": ana.id}])
    assert n == 1 and enviadas == [(juan.id, "Mi Vivero", "📦 Pedido nuevo de Ana & Juan")]
    enviadas.clear()
    pedidos.crear_pedido(s, cliente.id, hoy(), [{"producto_id": nuevo_producto().id, "cantidad": 1, "precio": 1}], ana.id)
    assert notificaciones.enviar_resumen_diario(s) == 2
    titulo, cuerpo = next((t, c) for u, t, c in enviadas if u == ana.id)
    assert titulo == "Buen día, Ana 🌱" and "Pedidos para entregar: 1" in cuerpo


def test_backup_no_incluye_la_clave_de_notificaciones(s):
    import io
    import pandas as pd
    push.claves(s)
    s.flush()
    hojas = pd.read_excel(io.BytesIO(documentos.backup_excel(s)), sheet_name=None)
    assert "PRIVATE KEY" not in hojas["config"].to_string()


def test_resumen_diario_deja_registro(tmp_path, monkeypatch):
    from sqlalchemy.orm import Session
    from conftest import base_limpia
    import resumen_diario
    url = f"sqlite:///{tmp_path / 'resumen.db'}"
    engine = base_limpia(url)
    monkeypatch.setenv("DATABASE_URL", url)
    resumen_diario.main()
    with Session(engine) as s:
        assert "(0 avisos)" in config.obtener(s, "ultimo_resumen")
