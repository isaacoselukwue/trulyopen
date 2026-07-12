from __future__ import annotations

import base64
import io
import os
import time

from app.schemas import GeneratedImage, ImageGenRequest, ImageGenResponse
from app.services.inference.errors import GenerationError
from app.services.inference.manager import DiffusersRunner, Runner


def generate_images(runner: Runner, req: ImageGenRequest) -> ImageGenResponse:
    if not isinstance(runner, DiffusersRunner):
        raise GenerationError("This model does not support image generation.")
    import torch

    start = time.monotonic()
    seed_base = req.seed if req.seed is not None else int.from_bytes(os.urandom(4), "little")
    images: list[GeneratedImage] = []
    for index in range(req.num_images):
        seed = seed_base + index
        generator = torch.Generator(runner.device).manual_seed(seed)
        result = runner.pipe(
            prompt=req.prompt,
            negative_prompt=req.negative_prompt or None,
            width=req.width,
            height=req.height,
            num_inference_steps=req.steps,
            guidance_scale=req.guidance_scale,
            generator=generator,
        )
        pil_image = result.images[0]
        buffer = io.BytesIO()
        pil_image.save(buffer, format="PNG")
        images.append(
            GeneratedImage(
                b64_png=base64.b64encode(buffer.getvalue()).decode("ascii"),
                seed=seed,
            )
        )
    return ImageGenResponse(
        images=images,
        duration_seconds=round(time.monotonic() - start, 3),
    )
