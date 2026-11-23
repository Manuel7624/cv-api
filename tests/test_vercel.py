"""Despliegue en Vercel: usa app/main.py directamente (preset de FastAPI). En Vercel
la base del CV va a /tmp, el único sitio escribible. Render no depende de esto."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run_python(code: str, **env) -> subprocess.CompletedProcess:
    base = {k: v for k, v in os.environ.items() if k not in ("DATABASE_URL", "STATS_DATABASE_URL", "VERCEL")}
    return subprocess.run(
        [sys.executable, "-c", code], cwd=ROOT, env={**base, **env},
        capture_output=True, text=True, timeout=60,
    )


def test_vercel_json_configures_the_main_function():
    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    assert "rewrites" not in config  # Vercel enruta solo, hacia app/main.py
    assert config["functions"]["app/main.py"]["includeFiles"] == "app/**"
    assert not (ROOT / "api").exists()  # un segundo punto de entrada confundiría a Vercel


def test_database_goes_to_tmp_on_vercel_and_stays_local_elsewhere():
    code = "from app.database import DATABASE_URL; print('URL', DATABASE_URL)"
    assert "URL sqlite:////tmp/cv.db" in run_python(code, VERCEL="1").stdout
    assert "URL sqlite:///./cv.db" in run_python(code).stdout
    # Si se define DATABASE_URL, manda sobre el valor por defecto.
    assert "URL sqlite:///otra.db" in run_python(code, VERCEL="1", DATABASE_URL="sqlite:///otra.db").stdout


def test_app_starts_and_seeds_the_cv_on_vercel(tmp_path):
    code = (
        "from app.main import startup\n"
        "from app.database import SessionLocal\n"
        "from app import crud\n"
        "startup()\n"
        "with SessionLocal() as s:\n"
        "    print('PROFILE', crud.get_profile(s).name)\n"
    )
    result = run_python(code, VERCEL="1", DATABASE_URL=f"sqlite:///{tmp_path / 'cv.db'}")
    assert result.returncode == 0, result.stderr
    assert "PROFILE Manuel" in result.stdout
