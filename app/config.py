import os
from pathlib import Path


def load_env_files() -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    workspace_dir = backend_dir.parent

    for env_file in (workspace_dir / ".env", backend_dir / ".env"):
        if not env_file.exists():
            continue
        for line in env_file.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
