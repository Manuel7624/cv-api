"""Punto de entrada de Vercel (Vercel Functions con Python).

Vercel busca aquí una variable `app` (ASGI). La web, la API y el chat son la misma
aplicación FastAPI de siempre (app/main.py); solo cambia cómo arranca:

- El disco de Vercel es de solo lectura salvo /tmp: la SQLite del CV se crea ahí y
  se rellena desde app/seed.py en cada arranque en frío (tarda unos segundos como mucho).
  DATABASE_URL se puede cambiar desde el panel de Vercel si se quiere otra base.
- No se confía en el "lifespan" de la app: se arranca aquí, al importar, y se anula el
  del arranque normal para no hacerlo dos veces.
- Render no usa este archivo (su Dockerfile solo copia la carpeta app).
"""
import os
from contextlib import asynccontextmanager

# Antes de importar la app: app/database.py lee DATABASE_URL al importarse.
os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/cv.db")

from app.main import app, startup  # noqa: E402

startup()


@asynccontextmanager
async def _no_lifespan(_app):
    yield


app.router.lifespan_context = _no_lifespan
