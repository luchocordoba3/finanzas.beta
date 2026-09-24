"""Notificaciones propias del sistema (Web Push): llegan como las de cualquier app, con el nombre y el ícono
del vivero, sin servicios de terceros. Las entregan gratis los navegadores (Google, Apple, Mozilla).
Cifrado aes128gcm (RFC 8291) y firma VAPID (RFC 8292) hechos con `cryptography`."""
import base64
import json
import os
import time
from urllib.parse import urlsplit

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from sqlalchemy import select

from ..models import Dispositivo
from . import config

CONTACTO = "https://github.com/luchocordoba3/finanzas.beta"


def b64url(datos: bytes) -> str:
    return base64.urlsafe_b64encode(datos).rstrip(b"=").decode()


def de_b64url(texto: str) -> bytes:
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


def _punto(publica: ec.EllipticCurvePublicKey) -> bytes:
    return publica.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)


def claves(s) -> tuple[ec.EllipticCurvePrivateKey, str]:
    """Clave VAPID del vivero: se genera sola la primera vez y queda guardada en la base."""
    pem = config.obtener(s, "push_vapid_privada")
    if not pem:
        nueva = ec.generate_private_key(ec.SECP256R1())
        pem = nueva.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                  serialization.NoEncryption()).decode()
        config.guardar(s, {"push_vapid_privada": pem})
    privada = serialization.load_pem_private_key(pem.encode(), password=None)
    return privada, b64url(_punto(privada.public_key()))


def clave_publica(s) -> str:
    return claves(s)[1]


def cifrar(mensaje: bytes, p256dh: str, auth: str, salt: bytes | None = None,
           emisor: ec.EllipticCurvePrivateKey | None = None) -> bytes:
    """Cifra el mensaje para un navegador (RFC 8291, aes128gcm, un solo registro)."""
    receptor = de_b64url(p256dh)
    emisor = emisor or ec.generate_private_key(ec.SECP256R1())
    publica_emisor = _punto(emisor.public_key())
    compartido = emisor.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), receptor))
    ikm = HKDF(hashes.SHA256(), 32, salt=de_b64url(auth),
               info=b"WebPush: info\x00" + receptor + publica_emisor).derive(compartido)
    salt = salt or os.urandom(16)
    clave = HKDF(hashes.SHA256(), 16, salt=salt, info=b"Content-Encoding: aes128gcm\x00").derive(ikm)
    nonce = HKDF(hashes.SHA256(), 12, salt=salt, info=b"Content-Encoding: nonce\x00").derive(ikm)
    cifrado = AESGCM(clave).encrypt(nonce, mensaje + b"\x02", None)
    return salt + (4096).to_bytes(4, "big") + bytes([len(publica_emisor)]) + publica_emisor + cifrado


def firma_vapid(privada: ec.EllipticCurvePrivateKey, endpoint: str, contacto: str) -> str:
    """JWT ES256 que identifica al vivero ante el servicio de notificaciones (RFC 8292)."""
    destino = urlsplit(endpoint)
    partes = [b64url(json.dumps(x, separators=(",", ":")).encode()) for x in (
        {"typ": "JWT", "alg": "ES256"},
        {"aud": f"{destino.scheme}://{destino.netloc}", "exp": int(time.time()) + 12 * 3600, "sub": contacto})]
    r, s_ = decode_dss_signature(privada.sign(".".join(partes).encode(), ec.ECDSA(hashes.SHA256())))
    return ".".join(partes + [b64url(r.to_bytes(32, "big") + s_.to_bytes(32, "big"))])


def registrar(s, usuario_id: int, codigo: str) -> Dispositivo:
    """Guarda el dispositivo que activó las notificaciones (el código viene de la página de activación)."""
    try:
        datos = json.loads(de_b64url(codigo.strip()).decode())
        suscripcion = datos.get("sub", datos)
        endpoint, p256dh, auth = (suscripcion["endpoint"], suscripcion["keys"]["p256dh"],
                                  suscripcion["keys"]["auth"])
        valido = endpoint.startswith("https://") and len(de_b64url(p256dh)) == 65 and len(de_b64url(auth)) >= 16
    except (ValueError, KeyError, TypeError, AttributeError):
        valido = False
    if not valido:
        raise ValueError("El link de activación llegó incompleto. Volvé a tocar «Activar en este dispositivo».")
    d = s.scalar(select(Dispositivo).where(Dispositivo.endpoint == endpoint)) or Dispositivo(endpoint=endpoint)
    d.usuario_id, d.p256dh, d.auth = usuario_id, p256dh, auth
    d.nombre = str(datos.get("nombre") or "Dispositivo")[:80]
    s.add(d)
    s.flush()
    return d


def dispositivos(s, usuario_id: int | None = None) -> list[Dispositivo]:
    q = select(Dispositivo).order_by(Dispositivo.creado_en)
    return list(s.scalars(q.where(Dispositivo.usuario_id == usuario_id) if usuario_id else q))


def por_usuario(s) -> dict[int, list[Dispositivo]]:
    out: dict[int, list[Dispositivo]] = {}
    for d in dispositivos(s):
        out.setdefault(d.usuario_id, []).append(d)
    return out


def quitar(s, dispositivo_id: int) -> None:
    d = s.get(Dispositivo, dispositivo_id)
    if d:
        s.delete(d)


def enviar(s, dispositivo: Dispositivo, titulo: str, cuerpo: str, url: str = "", etiqueta: str | None = None) -> bool:
    """Manda una notificación. Si el navegador la dio de baja (404/410), borra el dispositivo."""
    privada, publica = claves(s)
    url_app = config.obtener(s, "url_app")
    contacto = url_app if url_app.startswith("https://") else CONTACTO
    datos = json.dumps({"title": titulo, "body": cuerpo[:1000], "url": url or url_app, "tag": etiqueta},
                       ensure_ascii=False).encode()
    try:
        r = requests.post(dispositivo.endpoint, data=cifrar(datos, dispositivo.p256dh, dispositivo.auth), timeout=10,
                          headers={"Content-Encoding": "aes128gcm", "Content-Type": "application/octet-stream",
                                   "TTL": "86400", "Urgency": "normal",
                                   "Authorization": f"vapid t={firma_vapid(privada, dispositivo.endpoint, contacto)}, k={publica}"})
    except requests.RequestException:
        return False
    if r.status_code in (404, 410):
        s.delete(dispositivo)
        return False
    return r.status_code < 300


def enviar_bienvenida(s, dispositivo_id: int) -> bool:
    d = s.get(Dispositivo, dispositivo_id)
    return bool(d) and enviar(s, d, config.obtener(s, "nombre_vivero"),
                              "✅ Listo: las notificaciones del vivero llegan a este dispositivo.")


def probar(s, usuario_id: int) -> int:
    equipos = dispositivos(s, usuario_id)
    if not equipos:
        raise ValueError("Todavía no activaste las notificaciones en ningún dispositivo.")
    enviados = sum(enviar(s, d, config.obtener(s, "nombre_vivero"), "🔔 Prueba: así te llegan los avisos del vivero.")
                   for d in equipos)
    if not enviados:
        raise ValueError("No se pudo entregar la prueba. Volvé a activar las notificaciones en el dispositivo.")
    return enviados
