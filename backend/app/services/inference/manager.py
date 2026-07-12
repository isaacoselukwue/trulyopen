from __future__ import annotations

import gc
import importlib.util
import json
import logging
import os
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.config import model_dir_name
from app.schemas import LoadedModelInfo, LocalModel, Modality, ModelFormat
from app.services import registry
from app.services.inference.errors import ModelLoadError, OutOfMemoryError

logger = logging.getLogger(__name__)

ML_INSTALL_HINT = "run: pip install -r requirements-ml.txt"


def oom_message(model_id: str) -> str:
    return (
        f"Out of memory while running {model_id}. The model has been unloaded and "
        "GPU/CPU memory freed. Try a smaller model, lower max tokens, or smaller "
        "image dimensions."
    )


def _cuda_available() -> bool:
    if importlib.util.find_spec("torch") is None:
        return False
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        return False


def looks_like_oom(exc: BaseException) -> bool:
    if isinstance(exc, MemoryError):
        return True
    if type(exc).__name__ == "OutOfMemoryError":
        return True
    if isinstance(exc, (RuntimeError, ValueError)):
        return "out of memory" in str(exc).lower()
    return False


class GGUFRunner:
    def __init__(self, model: LocalModel) -> None:
        try:
            from llama_cpp import Llama
        except ImportError as exc:
            raise ModelLoadError(f"llama-cpp-python is not installed — {ML_INSTALL_HINT}") from exc
        gguf_files = sorted(Path(model.path).rglob("*.gguf"))
        if not gguf_files:
            raise ModelLoadError("No GGUF file was found in this model's folder.")
        n_gpu_layers = -1 if _cuda_available() else 0
        self.llama = Llama(
            model_path=str(gguf_files[0]),
            n_ctx=4096,
            n_gpu_layers=n_gpu_layers,
            verbose=False,
        )
        self.device = "cuda" if n_gpu_layers == -1 else "cpu"


def _require_modules(label: str, *names: str) -> None:
    for name in names:
        if importlib.util.find_spec(name) is None:
            raise ModelLoadError(f"{label} are not installed — {ML_INSTALL_HINT}")


def _register_optional_quantizers(path: str) -> None:
    config = _read_json(Path(path) / "config.json")
    quant = config.get("quantization_config") if isinstance(config, dict) else None
    method = str(quant.get("quant_method", "")).lower() if isinstance(quant, dict) else ""
    try:
        from sdnq import SDNQConfig

        _ = SDNQConfig
    except ImportError as exc:
        if method == "sdnq":
            raise ModelLoadError(f"This model is quantised with SDNQ — {ML_INSTALL_HINT}") from exc


def _load_transformers_model(path: str, is_vision: bool):
    _register_optional_quantizers(path)
    if is_vision:
        from transformers import AutoModelForImageTextToText, AutoProcessor

        processor = AutoProcessor.from_pretrained(path, trust_remote_code=True)
        mdl = AutoModelForImageTextToText.from_pretrained(
            path, torch_dtype="auto", device_map="auto", trust_remote_code=True
        )
        return mdl, getattr(processor, "tokenizer", None), processor
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(path, trust_remote_code=True)
    mdl = AutoModelForCausalLM.from_pretrained(
        path, torch_dtype="auto", device_map="auto", trust_remote_code=True
    )
    return mdl, tokenizer, None


def _resolve_base_model_path(base_ref: str) -> str:
    if os.path.isdir(base_ref):
        return base_ref
    local = registry.get_model(model_dir_name(base_ref))
    if local is not None:
        return local.path
    return base_ref


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


class TransformersRunner:
    def __init__(self, model: LocalModel) -> None:
        _require_modules("transformers/torch", "torch", "transformers")
        self.is_vision = model.modality is Modality.VISION_CHAT
        self.model, self.tokenizer, self.processor = _load_transformers_model(
            model.path, self.is_vision
        )
        self.device = str(next(self.model.parameters()).device)


class PeftRunner:
    def __init__(self, model: LocalModel) -> None:
        _require_modules("peft/transformers/torch", "torch", "transformers", "peft")
        from peft import PeftModel

        adapter_config = _read_json(Path(model.path) / "adapter_config.json")
        base_ref = model.base_model
        if not base_ref and adapter_config:
            base_ref = adapter_config.get("base_model_name_or_path")
        if not isinstance(base_ref, str) or not base_ref:
            raise ModelLoadError("This adapter does not record a base model, so it cannot be loaded.")
        self.is_vision = model.modality is Modality.VISION_CHAT
        base_path = _resolve_base_model_path(base_ref)
        try:
            base_model, self.tokenizer, self.processor = _load_transformers_model(
                base_path, self.is_vision
            )
        except Exception as exc:
            if looks_like_oom(exc):
                raise
            raise ModelLoadError(
                f"Could not load the base model '{base_ref}' this adapter needs. "
                "If it is gated or private, download an ungated base into your library first, "
                "then load the adapter."
            ) from exc
        self.model = PeftModel.from_pretrained(base_model, model.path)
        self.device = str(next(self.model.parameters()).device)


class DiffusersRunner:
    def __init__(self, model: LocalModel) -> None:
        try:
            import torch
            from diffusers import DiffusionPipeline
        except ImportError as exc:
            raise ModelLoadError(f"diffusers/torch are not installed — {ML_INSTALL_HINT}") from exc
        _register_optional_quantizers(model.path)
        cuda = _cuda_available()
        dtype = torch.float16 if cuda else torch.float32
        self.pipe = DiffusionPipeline.from_pretrained(
            model.path,
            torch_dtype=dtype,
            safety_checker=None,
            requires_safety_checker=False,
            trust_remote_code=True,
        )
        if cuda:
            self.pipe = self.pipe.to("cuda")
        try:
            self.pipe.enable_attention_slicing()
        except Exception:
            logger.debug("Attention slicing is not supported by this pipeline")
        self.device = "cuda" if cuda else "cpu"


Runner = GGUFRunner | TransformersRunner | PeftRunner | DiffusersRunner


class InferenceManager:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._runner: Runner | None = None
        self._model_id: str | None = None
        self._device: str | None = None
        self.generation_lock = threading.Lock()

    def loaded_info(self) -> LoadedModelInfo:
        with self._lock:
            return LoadedModelInfo(model_id=self._model_id, device=self._device)

    def load(self, model_id: str) -> LoadedModelInfo:
        with self._lock:
            if self._model_id == model_id and self._runner is not None:
                return self.loaded_info()
            model = registry.get_model(model_id)
            if model is None:
                raise KeyError(model_id)
            self.unload()
            try:
                with self.oom_guard(model_id):
                    runner = self._build_runner(model)
            except (OutOfMemoryError, ModelLoadError):
                raise
            except Exception as exc:
                logger.exception("Failed to load %s", model_id)
                raise ModelLoadError(
                    f"Could not load '{model.name}'. It may use an architecture or quantisation "
                    f"that this build of Transformers/Diffusers cannot load ({type(exc).__name__}: "
                    f"{str(exc).splitlines()[0][:200] if str(exc).strip() else 'no detail'})."
                ) from exc
            self._runner = runner
            self._model_id = model_id
            self._device = runner.device
            logger.info("Loaded %s on %s", model_id, runner.device)
            return self.loaded_info()

    def unload(self) -> None:
        with self._lock:
            self._runner = None
            self._model_id = None
            self._device = None
        self._release_memory()

    def free_all(self) -> None:
        self.unload()

    def get_runner(self, model_id: str) -> Runner:
        with self._lock:
            if self._model_id != model_id or self._runner is None:
                self.load(model_id)
            assert self._runner is not None
            return self._runner

    @contextmanager
    def oom_guard(self, model_id: str) -> Iterator[None]:
        try:
            yield
        except OutOfMemoryError:
            raise
        except BaseException as exc:
            if looks_like_oom(exc):
                logger.warning("Out of memory while running %s; freeing resources", model_id)
                self.free_all()
                raise OutOfMemoryError(oom_message(model_id)) from exc
            raise

    def _build_runner(self, model: LocalModel) -> Runner:
        if model.format is ModelFormat.GGUF:
            return GGUFRunner(model)
        if model.format is ModelFormat.TRANSFORMERS:
            return TransformersRunner(model)
        if model.format is ModelFormat.PEFT:
            return PeftRunner(model)
        if model.format is ModelFormat.DIFFUSERS:
            return DiffusersRunner(model)
        raise ModelLoadError(
            "This model uses a custom or unrecognised format that is not one of the "
            "types TrulyOpen can run (GGUF, Transformers, Diffusers or PEFT adapters)."
        )

    def _release_memory(self) -> None:
        gc.collect()
        if importlib.util.find_spec("torch") is not None:
            try:
                import torch

                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                logger.debug("Could not empty the CUDA cache")


manager = InferenceManager()
