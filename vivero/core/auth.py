import hashlib
import hmac
import secrets

from sqlalchemy import func, select

from .models import Usuario

ITERACIONES = 240_000


def hash_password(password: str) -> str:
    sal = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(sal), ITERACIONES).hex()
    return f"pbkdf2_sha256${ITERACIONES}${sal}${h}"


def verificar(password: str, guardado: str) -> bool:
    try:
        _, iteraciones, sal, h = guardado.split("$")
        calculado = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(sal), int(iteraciones)).hex()
    except ValueError:
        return False
    return hmac.compare_digest(calculado, h)


def hay_usuarios(s) -> bool:
    return bool(s.scalar(select(func.count(Usuario.id))))


def _validar_password(password: str) -> None:
    if len(password) < 6:
        raise ValueError("La contraseña tiene que tener al menos 6 caracteres.")


def crear_usuario(s, nombre: str, usuario: str, password: str) -> Usuario:
    nombre, usuario = nombre.strip(), usuario.strip().lower()
    if not nombre or not usuario:
        raise ValueError("Completá el nombre y el usuario.")
    _validar_password(password)
    if s.scalar(select(Usuario).where(Usuario.usuario == usuario)):
        raise ValueError("Ese usuario ya existe.")
    u = Usuario(nombre=nombre, usuario=usuario, password_hash=hash_password(password))
    s.add(u)
    s.flush()
    return u


def autenticar(s, usuario: str, password: str) -> Usuario | None:
    u = s.scalar(select(Usuario).where(Usuario.usuario == usuario.strip().lower(), Usuario.activo.is_(True)))
    return u if u and verificar(password, u.password_hash) else None


def cambiar_password(s, usuario_id: int, nueva: str) -> None:
    _validar_password(nueva)
    s.get(Usuario, usuario_id).password_hash = hash_password(nueva)


def usuarios(s, solo_activos: bool = True) -> list[Usuario]:
    q = select(Usuario).order_by(Usuario.nombre)
    if solo_activos:
        q = q.where(Usuario.activo.is_(True))
    return list(s.scalars(q))
