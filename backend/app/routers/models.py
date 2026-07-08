from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.schemas import ModelResolveResponse
from app.services import hf_hub
from app.services.hf_hub import HfApiError, RepoGatedError, RepoNotFoundError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/models", tags=["models"])


@router.get("/resolve")
def resolve_repository(repo_id: str) -> ModelResolveResponse:
    try:
        normalized = hf_hub.normalize_repo_id(repo_id)
        return hf_hub.resolve_model(normalized)
    except RepoNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RepoGatedError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except HfApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
