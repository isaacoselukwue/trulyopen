from __future__ import annotations

import logging
import re

import requests

from app.config import HF_API_BASE, HF_REQUEST_TIMEOUT
from app.schemas import Modality, ModelFormat, ModelResolveResponse, RepoFile
from app.services import hardware

logger = logging.getLogger(__name__)

REPO_ID_ERROR = "Enter a repository id like owner/model-name"
REPO_NOT_FOUND_MESSAGE = "Repository not found on Hugging Face. Check the id and try again."
REPO_GATED_MESSAGE = (
    "This repository is gated and needs a Hugging Face licence agreement — "
    "gated models are not supported."
)

REPO_SEGMENT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
WEIGHT_EXTENSIONS = (".gguf", ".safetensors", ".bin", ".pt", ".ckpt")
GGUF_SHARD_PATTERN = re.compile(r"^(.*)-\d{5}-of-\d{5}\.gguf$", re.IGNORECASE)
AUX_ARTEFACT_NAMES = {
    "optimizer.pt",
    "scheduler.pt",
    "scaler.pt",
    "training_args.bin",
    "trainer_state.json",
    "rng_state.pth",
}
NON_TRANSFORMERS_EXTENSIONS = (
    ".onnx",
    ".onnx_data",
    ".h5",
    ".msgpack",
    ".mlmodel",
    ".tflite",
    ".ot",
    ".pt",
    ".ckpt",
    ".pth",
)

CHAT_PIPELINES = {"text-generation", "text2text-generation", "conversational"}
VISION_CHAT_PIPELINES = {
    "image-text-to-text",
    "visual-question-answering",
    "image-to-text",
    "any-to-any",
}
IMAGE_GEN_PIPELINES = {"text-to-image"}
CAUSAL_TASK_TYPES = {"CAUSAL_LM", "SEQ_2_SEQ_LM"}
UNSUPPORTED_QUANT_METHODS: set[str] = set()
IMAGE_COMPONENT_REASON = (
    "This is tagged text-to-image but is not a complete Diffusers pipeline (no "
    "model_index.json) — it looks like a single component such as a text encoder, which "
    "cannot generate images on its own. Look for the full pipeline repository instead."
)


class RepoNotFoundError(Exception):
    pass


class RepoGatedError(Exception):
    pass


class HfApiError(Exception):
    pass


def normalize_repo_id(raw: str) -> str:
    value = (raw or "").strip()
    value = value.split("?", 1)[0].split("#", 1)[0]
    value = re.sub(r"^https?://", "", value, flags=re.IGNORECASE)
    lowered = value.lower()
    for prefix in ("www.huggingface.co/", "huggingface.co/"):
        if lowered.startswith(prefix):
            value = value[len(prefix):]
            break
    segments = [segment for segment in value.split("/") if segment]
    if len(segments) < 2:
        raise ValueError(REPO_ID_ERROR)
    owner, name = segments[0], segments[1]
    if not REPO_SEGMENT_PATTERN.match(owner) or not REPO_SEGMENT_PATTERN.match(name):
        raise ValueError(REPO_ID_ERROR)
    return f"{owner}/{name}"


def _get(url: str, params: dict[str, str] | None = None) -> requests.Response:
    try:
        response = requests.get(url, params=params, timeout=HF_REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        raise HfApiError(
            "Could not reach Hugging Face. Check your internet connection and try again."
        ) from exc
    if response.status_code in (401, 404):
        raise RepoNotFoundError(REPO_NOT_FOUND_MESSAGE)
    if response.status_code != 200:
        raise HfApiError(
            f"Hugging Face returned an unexpected response (HTTP {response.status_code}). "
            "Try again in a moment."
        )
    return response


def fetch_repo_info(repo_id: str) -> dict:
    response = _get(f"{HF_API_BASE}/api/models/{repo_id}")
    info = response.json()
    if info.get("gated"):
        raise RepoGatedError(REPO_GATED_MESSAGE)
    return info


def fetch_json_file(repo_id: str, path: str) -> dict | None:
    try:
        response = requests.get(
            f"{HF_API_BASE}/{repo_id}/resolve/main/{path}",
            timeout=HF_REQUEST_TIMEOUT,
            allow_redirects=True,
        )
    except requests.RequestException:
        return None
    if response.status_code != 200:
        return None
    try:
        parsed = response.json()
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


def fetch_repo_files(repo_id: str) -> list[RepoFile]:
    url: str | None = f"{HF_API_BASE}/api/models/{repo_id}/tree/main"
    params: dict[str, str] | None = {"recursive": "true"}
    files: list[RepoFile] = []
    while url:
        response = _get(url, params=params)
        for item in response.json():
            if item.get("type") != "file":
                continue
            lfs = item.get("lfs")
            size = lfs.get("size", 0) if isinstance(lfs, dict) else item.get("size", 0)
            files.append(RepoFile(path=item["path"], size_bytes=int(size or 0)))
        url = response.links.get("next", {}).get("url")
        params = None
    return files


def detect_format(files: list[RepoFile]) -> ModelFormat:
    names = [f.path.split("/")[-1] for f in files]
    paths = [f.path for f in files]
    if any(p.lower().endswith(".gguf") for p in paths):
        return ModelFormat.GGUF
    if "model_index.json" in names:
        return ModelFormat.DIFFUSERS
    has_adapter_weights = any(
        p.split("/")[-1].startswith("adapter_model.") and p.lower().endswith((".safetensors", ".bin"))
        for p in paths
    )
    if "adapter_config.json" in names and has_adapter_weights:
        return ModelFormat.PEFT
    has_config = "config.json" in names
    has_weights = any(p.lower().endswith((".safetensors", ".bin")) for p in paths)
    if has_config and has_weights:
        return ModelFormat.TRANSFORMERS
    return ModelFormat.UNKNOWN


def _classify_tag(tag: str) -> Modality | None:
    if tag in VISION_CHAT_PIPELINES:
        return Modality.VISION_CHAT
    if tag in CHAT_PIPELINES:
        return Modality.CHAT
    if tag in IMAGE_GEN_PIPELINES:
        return Modality.IMAGE_GEN
    return None


def _modality_from_config(config: dict | None) -> Modality | None:
    if not config:
        return None
    architectures = config.get("architectures") or []
    arch_text = " ".join(a for a in architectures if isinstance(a, str)).lower()
    has_vision = (
        "vision_config" in config or "vision" in arch_text or "imagetext" in arch_text
    )
    if has_vision:
        return Modality.VISION_CHAT
    if any(key in arch_text for key in ("causallm", "conditionalgeneration", "seq2seqlm")):
        return Modality.CHAT
    return None


def detect_modality(
    pipeline_tag: str | None,
    tags: list[str],
    fmt: ModelFormat = ModelFormat.UNKNOWN,
    config: dict | None = None,
    adapter_config: dict | None = None,
) -> Modality:
    if pipeline_tag:
        modality = _classify_tag(pipeline_tag)
        if modality is not None:
            return modality
    for tag in tags:
        modality = _classify_tag(tag)
        if modality is not None:
            return modality
    from_config = _modality_from_config(config)
    if from_config is not None:
        return from_config
    if adapter_config and adapter_config.get("task_type") in CAUSAL_TASK_TYPES:
        return Modality.CHAT
    if fmt in (ModelFormat.TRANSFORMERS, ModelFormat.PEFT):
        return Modality.CHAT
    return Modality.UNSUPPORTED


def unsupported_quant_reason(config: dict | None) -> str | None:
    if not config:
        return None
    quant = config.get("quantization_config")
    if not isinstance(quant, dict):
        return None
    method = str(quant.get("quant_method", "")).lower()
    if method in UNSUPPORTED_QUANT_METHODS:
        return (
            f"This model is quantised with '{method}', which needs the {method.upper()} runtime "
            "that TrulyOpen does not bundle. Use an unquantised version or a GGUF build instead."
        )
    return None


def describe_unsupported_format(files: list[RepoFile]) -> str:
    exts = {"." + f.path.rsplit(".", 1)[-1].lower() for f in files if "." in f.path.split("/")[-1]}
    if exts & {".litertlm", ".tflite", ".task"}:
        return (
            "This is an on-device LiteRT/MediaPipe model (.litertlm/.tflite), which needs "
            "Google's LiteRT runtime. TrulyOpen runs PyTorch, GGUF and Diffusers models, not "
            "mobile on-device formats."
        )
    if exts & {".mlmodel", ".mlpackage"}:
        return "This is a Core ML model, which needs Apple's Core ML runtime rather than PyTorch."
    if ".onnx" in exts and not (exts & {".safetensors", ".bin", ".gguf"}):
        return (
            "This repository ships only ONNX weights, which need an ONNX runtime that TrulyOpen "
            "does not bundle."
        )
    return (
        "This model uses a custom architecture or format that is not one of the types TrulyOpen "
        "can run (GGUF, Transformers, Diffusers or PEFT adapters)."
    )


def _gguf_group_key(path: str) -> str:
    match = GGUF_SHARD_PATTERN.match(path)
    return match.group(1) if match else path


def _parent_dir(path: str) -> str:
    return path.rsplit("/", 1)[0] if "/" in path else ""


def plan_download(
    files: list[RepoFile], fmt: ModelFormat, selected: list[str] | None
) -> list[RepoFile]:
    candidates = [
        f
        for f in files
        if f.path != ".gitattributes" and not f.path.startswith(".git/")
    ]
    if fmt is ModelFormat.GGUF:
        ggufs = [f for f in candidates if f.path.lower().endswith(".gguf")]
        if not ggufs:
            return []
        groups: dict[str, list[RepoFile]] = {}
        for f in ggufs:
            groups.setdefault(_gguf_group_key(f.path), []).append(f)
        if selected:
            wanted = set(selected)
            chosen_keys = {_gguf_group_key(f.path) for f in ggufs if f.path in wanted}
            if chosen_keys:
                return [f for f in ggufs if _gguf_group_key(f.path) in chosen_keys]
        return min(groups.values(), key=lambda g: sum(f.size_bytes for f in g))
    if fmt in (ModelFormat.TRANSFORMERS, ModelFormat.PEFT):
        candidates = [
            f
            for f in candidates
            if f.path.split("/")[-1] not in AUX_ARTEFACT_NAMES
            and not f.path.lower().endswith(NON_TRANSFORMERS_EXTENSIONS)
        ]
    if fmt in (ModelFormat.TRANSFORMERS, ModelFormat.DIFFUSERS):
        safetensors_dirs = {
            _parent_dir(f.path) for f in candidates if f.path.lower().endswith(".safetensors")
        }
        candidates = [
            f
            for f in candidates
            if not (f.path.lower().endswith(".bin") and _parent_dir(f.path) in safetensors_dirs)
        ]
    return candidates


def resolve_model(repo_id: str, selected_files: list[str] | None = None) -> ModelResolveResponse:
    normalized = normalize_repo_id(repo_id)
    info = fetch_repo_info(normalized)
    files = fetch_repo_files(normalized)
    fmt = detect_format(files)
    pipeline_tag = info.get("pipeline_tag")
    tags = [tag for tag in info.get("tags", []) if isinstance(tag, str)]
    config: dict | None = None
    adapter_config: dict | None = None
    base_model: str | None = None
    if fmt is ModelFormat.TRANSFORMERS:
        config = fetch_json_file(normalized, "config.json")
    elif fmt is ModelFormat.PEFT:
        adapter_config = fetch_json_file(normalized, "adapter_config.json")
        if adapter_config:
            base = adapter_config.get("base_model_name_or_path")
            base_model = base if isinstance(base, str) and base else None
    quant_reason = unsupported_quant_reason(config)
    if quant_reason:
        fmt = ModelFormat.UNKNOWN
    modality = detect_modality(pipeline_tag, tags, fmt, config, adapter_config)
    component_reason = None
    if modality is Modality.IMAGE_GEN and fmt is not ModelFormat.DIFFUSERS:
        fmt = ModelFormat.UNKNOWN
        modality = Modality.UNSUPPORTED
        component_reason = IMAGE_COMPONENT_REASON
    plan = plan_download(files, fmt, selected_files)
    download_size_bytes = sum(f.size_bytes for f in plan)
    total_size_bytes = sum(f.size_bytes for f in files)
    weights_bytes = sum(
        f.size_bytes for f in plan if f.path.lower().endswith(WEIGHT_EXTENSIONS)
    )
    compatibility = hardware.check_compatibility(download_size_bytes, weights_bytes)
    if fmt is ModelFormat.UNKNOWN:
        reason = quant_reason or component_reason or describe_unsupported_format(files)
        compatibility.messages = [reason, *compatibility.messages]
    gguf_options: list[RepoFile] | None = None
    if fmt is ModelFormat.GGUF:
        groups: dict[str, list[RepoFile]] = {}
        for f in files:
            if f.path.lower().endswith(".gguf"):
                groups.setdefault(_gguf_group_key(f.path), []).append(f)
        options = [
            RepoFile(
                path=sorted(shards, key=lambda f: f.path)[0].path,
                size_bytes=sum(f.size_bytes for f in shards),
            )
            for shards in groups.values()
        ]
        gguf_options = sorted(options, key=lambda f: f.size_bytes)
    owner, name = normalized.split("/", 1)
    return ModelResolveResponse(
        repo_id=normalized,
        name=name,
        author=info.get("author") or owner,
        pipeline_tag=pipeline_tag,
        tags=tags,
        modality=modality,
        format=fmt,
        base_model=base_model,
        files=files,
        total_size_bytes=total_size_bytes,
        download_size_bytes=download_size_bytes,
        gguf_options=gguf_options,
        gated=False,
        compatibility=compatibility,
    )
