from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.schemas import DeleteResponse, LoadedModelInfo, LocalModel, OkResponse
from app.services import registry
from app.services.inference.errors import ModelLoadError, OutOfMemoryError
from app.services.inference.manager import manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/library", tags=["library"])


@router.get("")
def list_library() -> list[LocalModel]:
    return registry.list_models()


@router.get("/loaded")
def get_loaded() -> LoadedModelInfo:
    return manager.loaded_info()


@router.post("/unload")
def unload_model() -> OkResponse:
    with manager.generation_lock:
        manager.unload()
    return OkResponse()


@router.delete("/{model_id}")
def delete_model(model_id: str) -> DeleteResponse:
    with manager.generation_lock:
        if manager.loaded_info().model_id == model_id:
            manager.unload()
    try:
        freed_bytes = registry.remove_model(model_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Model not found in your library.")
    return DeleteResponse(freed_bytes=freed_bytes)


@router.post("/{model_id}/load")
def load_model(model_id: str) -> LoadedModelInfo:
    try:
        with manager.generation_lock:
            return manager.load(model_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Model not found in your library.")
    except ModelLoadError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except OutOfMemoryError as exc:
        raise HTTPException(status_code=507, detail=str(exc))
