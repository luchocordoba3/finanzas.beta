"""Manda por Telegram el resumen del día a cada socio que conectó su Telegram.
Lo corre GitHub Actions todos los días a las 8 (ver .github/workflows/vivero-resumen-diario.yml).
Necesita la variable DATABASE_URL (secreto del repositorio en GitHub)."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy.orm import Session  # noqa: E402

from core.db import crear_engine  # noqa: E402
from core.services import notificaciones  # noqa: E402


def main() -> None:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        print("Falta el secreto DATABASE_URL en GitHub: no se manda nada.")
        return
    with Session(crear_engine(url)) as s:
        if not notificaciones.token(s):
            print("Todavía no hay bot de Telegram configurado (Configuración → Avisos por Telegram).")
            return
        print(f"Resúmenes enviados: {notificaciones.enviar_resumen_diario(s)}")


if __name__ == "__main__":
    main()
