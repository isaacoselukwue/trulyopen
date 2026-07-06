from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = Path(os.environ.get("WORKBENCH_DATA_DIR", BASE_DIR / "data"))
MODELS_DIR = Path(os.environ.get("WORKBENCH_MODELS_DIR", DATA_DIR / "models"))
REGISTRY_PATH = DATA_DIR / "registry.json"
DOWNLOADS_STATE_PATH = DATA_DIR / "downloads.json"

HF_API_BASE = "https://huggingface.co"
HF_REQUEST_TIMEOUT = 20

DOWNLOAD_CHUNK_BYTES = 1024 * 1024
SPEED_WINDOW_SECONDS = 5.0

DISK_SAFETY_FACTOR = 1.05
MEMORY_SAFETY_FACTOR = 1.15
MEMORY_OVERHEAD_BYTES = int(1.5 * 1024**3)

FRONTEND_DIST = BASE_DIR.parent / "frontend" / "dist"

CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    *[o.strip() for o in os.environ.get("WORKBENCH_CORS_ORIGINS", "").split(",") if o.strip()],
]


def model_dir_name(repo_id: str) -> str:
    return repo_id.strip().replace("/", "__")


def ensure_dirs() -> None:
    for d in (DATA_DIR, MODELS_DIR):
        d.mkdir(parents=True, exist_ok=True)
