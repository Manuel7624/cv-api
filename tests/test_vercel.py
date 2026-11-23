"""Despliegue en Vercel: api/index.py arranca la app al importarla, con la base en
una ruta escribible, y la configuración es válida. Render no depende de esto."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_vercel_json_sends_everything_to_the_function():
    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    assert config["rewrites"] == [{"source": "/(.*)", "destination": "/api/index"}]
    assert config["functions"]["api/index.py"]["includeFiles"] == "app/**"


def test_vercel_entry_point_starts_the_app_and_seeds_the_cv(tmp_path):
    code = (
        "from api.index import app\n"
        "from app.database import SessionLocal\n"
        "from app import crud\n"
        "with SessionLocal() as s:\n"
        "    print('PROFILE', crud.get_profile(s).name)\n"
        "print('ROUTES', sorted(r.path for r in app.routes if hasattr(r, 'path'))[:3])\n"
    )
    env = {**os.environ, "VERCEL": "1", "DATABASE_URL": f"sqlite:///{tmp_path / 'cv.db'}"}
    env.pop("STATS_DATABASE_URL", None)
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True, timeout=60
    )
    assert result.returncode == 0, result.stderr
    assert "PROFILE Manuel" in result.stdout
    assert (tmp_path / "cv.db").exists()
