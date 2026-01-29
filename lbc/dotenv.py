from __future__ import annotations

from pathlib import Path
from typing import Optional

import os


def load_dotenv(path: str | Path = ".env", *, override: bool = False) -> bool:
    """
    Charge un fichier .env très simple (KEY=VALUE) dans os.environ.

    - Sans dépendances externes
    - Ignore les lignes vides et les commentaires (# ...)
    - Supporte des valeurs entourées de guillemets simples/doubles

    Returns:
        True si le fichier existe et a été lu, False sinon.
    """
    p = Path(path)
    if not p.is_absolute():
        p = Path.cwd() / p
    if not p.exists():
        return False

    for raw_line in p.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue

        # strip quotes
        if len(value) >= 2 and ((value[0] == value[-1]) and value[0] in ("'", '"')):
            value = value[1:-1]

        if not override and key in os.environ:
            continue
        os.environ[key] = value

    return True


def find_and_load_dotenv(
    *,
    filename: str = ".env",
    start_dir: str | Path | None = None,
    override: bool = False,
    max_depth: int = 5,
) -> Optional[Path]:
    """
    Remonte depuis start_dir (ou cwd) pour trouver un .env et le charger.
    Utile quand on lance un script depuis examples/.
    """
    base = Path(start_dir) if start_dir is not None else Path.cwd()
    base = base.resolve()

    cur = base
    for _ in range(max_depth + 1):
        candidate = cur / filename
        if candidate.exists():
            load_dotenv(candidate, override=override)
            return candidate
        if cur.parent == cur:
            break
        cur = cur.parent
    return None

