"""Versiones en las URLs de los archivos estáticos y su caché.

Cada referencia a /static/ en el HTML lleva ?v=<hash del contenido> (por ejemplo,
/static/styles.css?v=3f2a9c1b7d). El hash cambia solo cuando cambia el archivo, así
que al publicar una actualización el navegador pide la versión nueva sin tener que
borrar la caché, y mientras no cambia puede guardarla todo un año.

- HTML (la web y /admin/stats): no se guarda en caché, para que siempre lleve las
  versiones al día.
- Estáticos con ?v=: un año, sin volver a preguntar (immutable).
- Estáticos sin ?v= (las fuentes, que se piden desde el CSS, y cualquier acceso
  directo): se guardan, pero el navegador pregunta cada vez si han cambiado.

Las fuentes no llevan versión porque el CSS las pide sin ella: si la llevaran en el
HTML (precarga) y no en el CSS, el navegador las descargaría dos veces.
"""
import hashlib
import re
from functools import lru_cache
from pathlib import Path

STATIC_DIR = Path(__file__).parent / "static"
HASH_LENGTH = 10

# Carpetas que no se versionan (ver arriba).
UNVERSIONED_PREFIXES = ("fonts/",)

HTML_CACHE = "no-store"
VERSIONED_CACHE = "public, max-age=31536000, immutable"
UNVERSIONED_CACHE = "no-cache"

# href="/static/...", src="/static/..." y content="{{BASE_URL}}/static/..." (imagen
# para compartir), sin una versión ya puesta.
STATIC_REFERENCE = re.compile(
    r'(?P<start>(?:href|src|content)="(?:\{\{BASE_URL\}\})?/static/)(?P<path>[^"?#]+)"'
)


@lru_cache(maxsize=None)
def file_version(path: str, static_dir: Path = STATIC_DIR) -> str | None:
    """Hash corto del contenido del archivo, o None si no existe."""
    file = (static_dir / path).resolve()
    if not file.is_file() or static_dir.resolve() not in file.parents:
        return None
    return hashlib.sha256(file.read_bytes()).hexdigest()[:HASH_LENGTH]


def add_versions(html: str, static_dir: Path = STATIC_DIR) -> str:
    """Añade ?v=<hash> a cada referencia a /static/ del HTML (salvo las fuentes)."""

    def replace(match: re.Match) -> str:
        path = match["path"]
        version = None if path.startswith(UNVERSIONED_PREFIXES) else file_version(path, static_dir)
        if version is None:
            return match[0]
        return f'{match["start"]}{path}?v={version}"'

    return STATIC_REFERENCE.sub(replace, html)


def cache_control(path: str, query: str) -> str | None:
    """Cache-Control para los archivos estáticos (None si no es un estático)."""
    if not path.startswith("/static/"):
        return None
    if any(part.startswith("v=") for part in query.split("&")):
        return VERSIONED_CACHE
    return UNVERSIONED_CACHE
