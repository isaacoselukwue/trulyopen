from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.schemas import DownloadJob, DownloadRequest, OkResponse
from app.services.download_manager import manager
from app.services.hf_hub import HfApiError, RepoGatedError, RepoNotFoundError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/downloads", tags=["downloads"])


@router.get("")
def list_downloads() -> list[DownloadJob]:
    return manager.list()


@router.post("")
def start_download(request: DownloadRequest) -> DownloadJob:
    try:
        return manager.start(request.repo_id, request.files)
    except RepoNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RepoGatedError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except HfApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/{job_id}/pause")
def pause_download(job_id: str) -> DownloadJob:
    return _mutate(job_id, "pause")


@router.post("/{job_id}/resume")
def resume_download(job_id: str) -> DownloadJob:
    return _mutate(job_id, "resume")


@router.post("/{job_id}/cancel")
def cancel_download(job_id: str) -> DownloadJob:
    return _mutate(job_id, "cancel")


@router.delete("/{job_id}")
def remove_download(job_id: str) -> OkResponse:
    try:
        manager.remove(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Download not found.")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return OkResponse()


def _mutate(job_id: str, action: str) -> DownloadJob:
    try:
        return getattr(manager, action)(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Download not found.")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
