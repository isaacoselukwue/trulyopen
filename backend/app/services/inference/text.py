from __future__ import annotations

import base64
import io
import queue
import threading
import time
from typing import Any, Iterator

from app.schemas import ChatRequest
from app.services.inference.errors import GenerationError
from app.services.inference.manager import GGUFRunner, PeftRunner, Runner, TransformersRunner


def _decode_data_url(data_url: str) -> Any:
    from PIL import Image

    payload = data_url.split(",", 1)[1] if "," in data_url else data_url
    image = Image.open(io.BytesIO(base64.b64decode(payload)))
    return image.convert("RGB")


def _build_messages(req: ChatRequest) -> list[dict[str, str]]:
    messages = [{"role": m.role, "content": m.content} for m in req.messages]
    system_prompt = req.params.system_prompt
    if system_prompt and not any(m["role"] == "system" for m in messages):
        messages.insert(0, {"role": "system", "content": system_prompt})
    return messages


def _stream_gguf(runner: GGUFRunner, req: ChatRequest) -> Iterator[str]:
    params = req.params
    stream = runner.llama.create_chat_completion(
        messages=_build_messages(req),
        stream=True,
        temperature=params.temperature,
        top_p=params.top_p,
        top_k=params.top_k,
        repeat_penalty=params.repetition_penalty,
        max_tokens=params.max_tokens,
    )
    for chunk in stream:
        delta = chunk["choices"][0].get("delta", {})
        token = delta.get("content")
        if token:
            yield token


def _iterate_streamer(streamer: Any, thread: threading.Thread, errors: list[BaseException]) -> Iterator[str]:
    while True:
        try:
            text = next(streamer)
        except StopIteration:
            break
        except queue.Empty:
            if errors or not thread.is_alive():
                break
            continue
        if text:
            yield text
    thread.join()
    if errors:
        raise errors[0]


def _stream_transformers(runner: TransformersRunner, req: ChatRequest) -> Iterator[str]:
    from transformers import TextIteratorStreamer

    params = req.params
    if runner.is_vision:
        conversation = []
        system_prompt = params.system_prompt
        if system_prompt and not any(m.role == "system" for m in req.messages):
            conversation.append({"role": "system", "content": [{"type": "text", "text": system_prompt}]})
        for message in req.messages:
            content: list[dict[str, Any]] = []
            for image_url in message.images or []:
                content.append({"type": "image", "image": _decode_data_url(image_url)})
            if message.content:
                content.append({"type": "text", "text": message.content})
            conversation.append({"role": message.role, "content": content})
        inputs = runner.processor.apply_chat_template(
            conversation,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
        ).to(runner.model.device)
        tokenizer = runner.tokenizer or runner.processor
        model_inputs = dict(inputs)
    else:
        tokenizer = runner.tokenizer
        inputs = tokenizer.apply_chat_template(
            _build_messages(req),
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
        ).to(runner.model.device)
        model_inputs = dict(inputs)

    streamer = TextIteratorStreamer(
        tokenizer, skip_prompt=True, skip_special_tokens=True, timeout=1.0
    )
    generation_kwargs = {
        **model_inputs,
        "max_new_tokens": params.max_tokens,
        "do_sample": params.temperature > 0,
        "temperature": max(params.temperature, 1e-3),
        "top_p": params.top_p,
        "top_k": params.top_k,
        "repetition_penalty": params.repetition_penalty,
        "streamer": streamer,
    }
    errors: list[BaseException] = []

    def _generate() -> None:
        try:
            runner.model.generate(**generation_kwargs)
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=_generate, daemon=True)
    thread.start()
    yield from _iterate_streamer(streamer, thread, errors)


def stream_chat(runner: Runner, req: ChatRequest) -> Iterator[dict[str, Any]]:
    start = time.monotonic()
    token_count = 0
    if isinstance(runner, GGUFRunner):
        token_source = _stream_gguf(runner, req)
    elif isinstance(runner, (TransformersRunner, PeftRunner)):
        token_source = _stream_transformers(runner, req)
    else:
        raise GenerationError("This model does not support chat generation.")
    for token in token_source:
        token_count += 1
        yield {"type": "token", "token": token}
    yield {
        "type": "done",
        "tokens": token_count,
        "duration_seconds": round(time.monotonic() - start, 3),
    }
