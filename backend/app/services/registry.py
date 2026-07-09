from __future__ import annotations

import json
import logging
import os
import shutil
import threading
from pathlib import Path

from app.config import REGISTRY_PATH
from app.schemas import LocalModel, Modality, ModelFormat

logger = logging.getLogger(__name__)

_lock = threading.Lock()


def _read_models() -> list[LocalModel]:
    if not REGISTRY_PATH.exists():
        return []
    try:
        raw = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("Registry at %s is unreadable; treating it as empty", REGISTRY_PATH)
        return []
    if not isinstance(raw, list):
        logger.warning("Registry at %s is not a list; treating it as empty", REGISTRY_PATH)
        return []
    models: list[LocalModel] = []
    for entry in raw:
        try:
            models.append(LocalModel.model_validate(entry))
        except Exception:
            logger.warning("Skipping an invalid registry entry: %r", entry)
    return models


def _write_models(models: list[LocalModel]) -> None:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps([model.model_dump(mode="json") for model in models], indent=2)
    temp_path = REGISTRY_PATH.with_name(REGISTRY_PATH.name + ".tmp")
    temp_path.write_text(payload, encoding="utf-8")
    os.replace(temp_path, REGISTRY_PATH)


def list_models() -> list[LocalModel]:
    with _lock:
        return _read_models()


def get_model(model_id: str) -> LocalModel | None:
    with _lock:
        for model in _read_models():
            if model.id == model_id:
                return model
    return None


def add_model(model: LocalModel) -> None:
    with _lock:
        models = [m for m in _read_models() if m.id != model.id]
        models.append(model)
        _write_models(models)


def remove_model(model_id: str) -> int:
    with _lock:
        models = _read_models()
        target = next((m for m in models if m.id == model_id), None)
        if target is None:
            raise KeyError(model_id)
        shutil.rmtree(target.path, ignore_errors=True)
        _write_models([m for m in models if m.id != model_id])
    return target.size_bytes


def _local_repo_files(path: str):
    from app.schemas import RepoFile

    root = Path(path)
    files = []
    for current, _, filenames in os.walk(root):
        for filename in filenames:
            full = Path(current) / filename
            try:
                size = full.stat().st_size
            except OSError:
                size = 0
            files.append(RepoFile(path=str(full.relative_to(root)), size_bytes=size))
    return files


def _read_local_json(path: str, name: str) -> dict | None:
    try:
        return json.loads((Path(path) / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def rescan() -> None:
    from app.services import hf_hub

    with _lock:
        models = _read_models()
        updated: list[LocalModel] = []
        changed = False
        for model in models:
            if not os.path.isdir(model.path):
                updated.append(model)
                continue
            files = _local_repo_files(model.path)
            fmt = hf_hub.detect_format(files)
            config = _read_local_json(model.path, "config.json") if fmt is ModelFormat.TRANSFORMERS else None
            adapter = _read_local_json(model.path, "adapter_config.json") if fmt is ModelFormat.PEFT else None
            if config is not None and hf_hub.unsupported_quant_reason(config):
                fmt = ModelFormat.UNKNOWN
            modality = hf_hub.detect_modality(model.pipeline_tag, [], fmt, config, adapter)
            if modality is Modality.IMAGE_GEN and fmt is not ModelFormat.DIFFUSERS:
                fmt = ModelFormat.UNKNOWN
                modality = Modality.UNSUPPORTED
            base_model = model.base_model
            if fmt is ModelFormat.PEFT and not base_model and adapter:
                candidate = adapter.get("base_model_name_or_path")
                base_model = candidate if isinstance(candidate, str) and candidate else None
            if (model.format, model.modality, model.base_model) != (fmt, modality, base_model):
                model = model.model_copy(
                    update={"format": fmt, "modality": modality, "base_model": base_model}
                )
                changed = True
            updated.append(model)
        if changed:
            _write_models(updated)
            logger.info("Re-scanned local library and updated model classifications")
