from __future__ import annotations

import json
import logging
from typing import Iterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.schemas import ChatRequest, ImageGenRequest, ImageGenResponse, Modality
from app.services import registry
from app.services.inference import image as image_service
from app.services.inference import text as text_service
from app.services.inference.errors import GenerationError, ModelLoadError, OutOfMemoryError
from app.services.inference.manager import looks_like_oom, manager, oom_message

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/generate", tags=["generate"])

SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


def _reject_unless(model_id: str, allowed: set[Modality], rejection: str) -> None:
    model = registry.get_model(model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found in your library.")
    if model.modality not in allowed:
        raise HTTPException(status_code=400, detail=rejection)


@router.post("/chat")
def generate_chat(request: ChatRequest) -> StreamingResponse:
    _reject_unless(
        request.model_id,
        {Modality.CHAT, Modality.VISION_CHAT},
        "This model does not support chat generation.",
    )

    def event_stream() -> Iterator[str]:
        with manager.generation_lock:
            error: str | None = None
            oom = False
            runner = None
            try:
                runner = manager.get_runner(request.model_id)
                for event in text_service.stream_chat(runner, request):
                    yield f"data: {json.dumps(event)}\n\n"
            except ModelLoadError as exc:
                error = str(exc)
            except Exception as exc:
                oom = looks_like_oom(exc)
                if not oom:
                    logger.exception("Chat generation failed for %s", request.model_id)
                    error = f"Generation failed: {exc or type(exc).__name__}"
            if oom:
                runner = None
                manager.free_all()
                error = oom_message(request.model_id)
            if error is not None:
                yield f"data: {json.dumps({'type': 'error', 'message': error})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=SSE_HEADERS)


@router.post("/image")
def generate_image(request: ImageGenRequest) -> ImageGenResponse:
    _reject_unless(
        request.model_id,
        {Modality.IMAGE_GEN},
        "This model does not support image generation.",
    )
    with manager.generation_lock:
        runner = None
        oom = False
        try:
            runner = manager.get_runner(request.model_id)
            return image_service.generate_images(runner, request)
        except ModelLoadError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except GenerationError as exc:
            raise HTTPException(status_code=500, detail=str(exc))
        except OutOfMemoryError:
            oom = True
        except BaseException as exc:
            if not looks_like_oom(exc):
                raise
            oom = True
        if oom:
            runner = None
            manager.free_all()
            raise HTTPException(status_code=507, detail=oom_message(request.model_id))
