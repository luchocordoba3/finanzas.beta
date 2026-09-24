"""Envío de avisos: notificaciones propias del sistema (push) y Telegram (opcional).
Incluye la conexión del bot de Telegram, los avisos al instante y el resumen del día."""
import html
import re
import secrets
from datetime import date

import requests
from sqlalchemy import select

from ..models import Usuario
from ..tiempo import DIAS, hoy
from . import alertas, config, push
from .avisos import e

API = "https://api.telegram.org/bot{token}/{metodo}"
MAX_TEXTO = 3900  # Telegram corta en 4096 caracteres


class ErrorTelegram(ValueError):
    pass


def _llamar(token: str, metodo: str, **params):
    try:
        r = requests.post(API.format(token=token, metodo=metodo), json=params, timeout=10)
        datos = r.json()
    except (requests.RequestException, ValueError) as ex:
        raise ErrorTelegram("No se pudo conectar con Telegram. Probá de nuevo en un rato.") from ex
    if not datos.get("ok"):
        raise ErrorTelegram(datos.get("description") or "Telegram rechazó el pedido.")
    return datos["result"]


def token(s) -> str:
    return config.obtener(s, "telegram_token").strip()


def bot(s) -> str:
    return config.obtener(s, "telegram_bot")


def chat(s, usuario_id: int) -> str:
    return config.obtener(s, f"telegram_chat_{usuario_id}")


def configurar_bot(s, token_nuevo: str, url_app: str = "") -> str:
    """Valida el token que da BotFather y lo guarda. Devuelve el usuario del bot."""
    token_nuevo = token_nuevo.strip()
    if not token_nuevo:
        raise ValueError("Pegá el token que te dio BotFather.")
    try:
        datos = _llamar(token_nuevo, "getMe")
    except ErrorTelegram as ex:
        if "Unauthorized" in str(ex) or "Not Found" in str(ex):
            raise ValueError("Telegram no reconoce ese token: copialo de nuevo desde BotFather, completo.") from ex
        raise
    valores = {"telegram_token": token_nuevo, "telegram_bot": datos["username"]}
    if url_app:
        valores["url_app"] = url_app
    config.guardar(s, valores)
    return datos["username"]


def link_conexion(s, usuario_id: int) -> str:
    """Link al bot con un código propio de cada usuario, para saber a quién pertenece cada chat."""
    clave = f"telegram_codigo_{usuario_id}"
    codigo = config.obtener(s, clave)
    if not codigo:
        codigo = secrets.token_hex(4)
        config.guardar(s, {clave: codigo})
    return f"https://t.me/{bot(s)}?start={codigo}"


def confirmar_conexion(s, usuario_id: int) -> bool:
    """Busca el /start con el código del usuario entre los últimos mensajes que recibió el bot."""
    codigo = config.obtener(s, f"telegram_codigo_{usuario_id}")
    if not codigo or not token(s):
        raise ValueError("Primero configurá el bot.")
    for update in reversed(_llamar(token(s), "getUpdates")):
        mensaje = update.get("message") or {}
        if (mensaje.get("text") or "").strip() == f"/start {codigo}":
            chat_id = str(mensaje["chat"]["id"])
            config.guardar(s, {f"telegram_chat_{usuario_id}": chat_id})
            nombre = s.get(Usuario, usuario_id).nombre
            enviar(token(s), chat_id, f"✅ Listo, {e(nombre)}: desde ahora te llegan acá los avisos del vivero 🌱")
            return True
    return False


def desconectar(s, usuario_id: int) -> None:
    config.guardar(s, {f"telegram_chat_{usuario_id}": ""})


def enviar(token_bot: str, chat_id: str, texto: str) -> None:
    if len(texto) > MAX_TEXTO:
        texto = texto[:MAX_TEXTO].rsplit("\n", 1)[0] + "\n…"
    _llamar(token_bot, "sendMessage", chat_id=chat_id, text=texto, parse_mode="HTML", disable_web_page_preview=True)


def conectados(s) -> dict[int, str]:
    usuarios = s.scalars(select(Usuario.id).where(Usuario.activo.is_(True)))
    return {uid: c for uid in usuarios if (c := chat(s, uid))}


def texto_plano(texto: str) -> str:
    """Saca el formato de Telegram para usar el texto en una notificación."""
    return html.unescape(re.sub(r"<[^>]+>", "", texto))


def activos(s) -> list[int]:
    return list(s.scalars(select(Usuario.id).where(Usuario.activo.is_(True))))


def enviar_avisos(s, avisos: list[dict]) -> int:
    """Manda los avisos encolados por todos los canales que tenga cada usuario (notificaciones del
    sistema y/o Telegram). Un aviso que no sale nunca frena el trabajo: se ignora."""
    if not avisos:
        return 0
    token_bot = token(s)
    chats = conectados(s) if token_bot else {}
    equipos = push.por_usuario(s)
    titulo, usuarios, enviados = config.obtener(s, "nombre_vivero"), activos(s), 0
    for aviso in avisos:
        for uid in aviso["para"] or usuarios:
            if uid == aviso["excepto"]:
                continue
            if uid in chats:
                try:
                    enviar(token_bot, chats[uid], aviso["texto"])
                    enviados += 1
                except ErrorTelegram:
                    pass
            for d in equipos.get(uid, []):
                enviados += push.enviar(s, d, titulo, texto_plano(aviso["texto"]))
    return enviados


def enviar_prueba(s, usuario_id: int) -> bool:
    enviar(token(s), chat(s, usuario_id), "🔔 Prueba: así te van a llegar los avisos del vivero.")
    return True


def resumen(s, usuario_id: int, ref: date | None = None, por_grupo: int = 4) -> str:
    ref = ref or hoy()
    nombre = s.get(Usuario, usuario_id).nombre
    lineas = [f"🌱 <b>Buen día, {e(nombre)}</b> · {DIAS[ref.weekday()]} {ref:%d/%m}"]
    grupos: dict[str, list] = {}
    for a in alertas.calcular(s, usuario_id, ref):
        grupos.setdefault(a.grupo, []).append(a)
    if not grupos:
        lineas.append("\nHoy no hay nada pendiente. ¡Buen día! 🌿")
    for grupo, items in grupos.items():
        lineas.append(f"\n{alertas.ICONOS.get(grupo, '•')} <b>{e(grupo)}</b> ({len(items)})")
        lineas += [f"• {e(a.texto)}" for a in items[:por_grupo]]
        if len(items) > por_grupo:
            lineas.append(f"• … y {len(items) - por_grupo} más")
    url = config.obtener(s, "url_app")
    if url:
        lineas.append(f"\n👉 {url}")
    return "\n".join(lineas)


def resumen_corto(s, usuario_id: int, ref: date | None = None) -> tuple[str, str]:
    """Título y texto para la notificación de la mañana (entra en la pantalla bloqueada)."""
    cantidades: dict[str, int] = {}
    for a in alertas.calcular(s, usuario_id, ref or hoy()):
        cantidades[a.grupo] = cantidades.get(a.grupo, 0) + 1
    titulo = f"Buen día, {s.get(Usuario, usuario_id).nombre} 🌱"
    cuerpo = " · ".join(f"{alertas.ICONOS.get(g, '')} {g}: {n}" for g, n in cantidades.items())
    return titulo, cuerpo or "Hoy no hay nada pendiente. ¡Buen día! 🌿"


def enviar_resumen(s, usuario_id: int, ref: date | None = None) -> bool:
    enviar(token(s), chat(s, usuario_id), resumen(s, usuario_id, ref))
    return True


def enviar_resumen_diario(s, ref: date | None = None) -> int:
    """Resumen de la mañana por todos los canales de cada socio."""
    chats = conectados(s) if token(s) else {}
    equipos, enviados = push.por_usuario(s), 0
    for uid in activos(s):
        if uid in chats:
            try:
                enviar_resumen(s, uid, ref)
                enviados += 1
            except ErrorTelegram:
                pass
        if equipos.get(uid):
            titulo, cuerpo = resumen_corto(s, uid, ref)
            enviados += sum(push.enviar(s, d, titulo, cuerpo, etiqueta="resumen") for d in equipos[uid])
    return enviados
