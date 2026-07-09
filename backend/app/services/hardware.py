from __future__ import annotations

import importlib.util
import logging
import shutil
import subprocess
from pathlib import Path

import psutil

from app.config import (
    DISK_SAFETY_FACTOR,
    MEMORY_OVERHEAD_BYTES,
    MEMORY_SAFETY_FACTOR,
    MODELS_DIR,
)
from app.schemas import (
    BackendAvailability,
    CompatibilityCheck,
    CompatibilityLevel,
    GPUInfo,
    HardwareInfo,
)

logger = logging.getLogger(__name__)

MIB = 1024 * 1024


def _format_gb(size_bytes: int) -> str:
    return f"{size_bytes / 1024 ** 3:.1f} GB"


def _existing_disk_target() -> Path:
    path = MODELS_DIR
    while not path.exists() and path != path.parent:
        path = path.parent
    return path


def _gpus_via_pynvml() -> list[GPUInfo]:
    import pynvml

    pynvml.nvmlInit()
    try:
        gpus: list[GPUInfo] = []
        for index in range(pynvml.nvmlDeviceGetCount()):
            handle = pynvml.nvmlDeviceGetHandleByIndex(index)
            name = pynvml.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):
                name = name.decode("utf-8", errors="replace")
            memory = pynvml.nvmlDeviceGetMemoryInfo(handle)
            gpus.append(
                GPUInfo(
                    name=str(name),
                    vram_total_bytes=int(memory.total),
                    vram_free_bytes=int(memory.free),
                )
            )
        return gpus
    finally:
        pynvml.nvmlShutdown()


def _gpus_via_nvidia_smi() -> list[GPUInfo]:
    result = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total,memory.free",
            "--format=csv,noheader,nounits",
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        return []
    gpus: list[GPUInfo] = []
    for line in result.stdout.strip().splitlines():
        parts = [part.strip() for part in line.rsplit(",", 2)]
        if len(parts) != 3:
            continue
        try:
            total_mib = float(parts[1])
            free_mib = float(parts[2])
        except ValueError:
            continue
        gpus.append(
            GPUInfo(
                name=parts[0],
                vram_total_bytes=int(total_mib * MIB),
                vram_free_bytes=int(free_mib * MIB),
            )
        )
    return gpus


def _detect_gpus() -> list[GPUInfo]:
    try:
        return _gpus_via_pynvml()
    except Exception:
        logger.debug("pynvml probe failed; falling back to nvidia-smi")
    try:
        return _gpus_via_nvidia_smi()
    except Exception:
        logger.debug("nvidia-smi probe failed; assuming no GPUs")
        return []


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def _detect_backends() -> BackendAvailability:
    torch_available = _module_available("torch")
    cuda_available = False
    if torch_available:
        try:
            import torch

            cuda_available = bool(torch.cuda.is_available())
        except Exception:
            cuda_available = False
    return BackendAvailability(
        torch_available=torch_available,
        cuda_available=cuda_available,
        transformers_available=_module_available("transformers"),
        diffusers_available=_module_available("diffusers"),
        llama_cpp_available=_module_available("llama_cpp"),
    )


def get_hardware_info() -> HardwareInfo:
    memory = psutil.virtual_memory()
    disk = shutil.disk_usage(_existing_disk_target())
    return HardwareInfo(
        ram_total_bytes=int(memory.total),
        ram_available_bytes=int(memory.available),
        disk_total_bytes=int(disk.total),
        disk_free_bytes=int(disk.free),
        gpus=_detect_gpus(),
        backends=_detect_backends(),
    )


def check_compatibility(download_size_bytes: int, weights_bytes: int) -> CompatibilityCheck:
    info = get_hardware_info()
    required_disk_bytes = int(download_size_bytes * DISK_SAFETY_FACTOR)
    required_memory_bytes = int(weights_bytes * MEMORY_SAFETY_FACTOR) + MEMORY_OVERHEAD_BYTES
    messages: list[str] = []

    disk_ok = info.disk_free_bytes >= required_disk_bytes
    if disk_ok:
        messages.append(
            f"Needs about {_format_gb(required_disk_bytes)} of disk space and "
            f"{_format_gb(info.disk_free_bytes)} is free."
        )
    else:
        messages.append(
            f"Needs about {_format_gb(required_disk_bytes)} of disk space but only "
            f"{_format_gb(info.disk_free_bytes)} is free — clear some space before downloading."
        )

    largest_vram_bytes = max((gpu.vram_total_bytes for gpu in info.gpus), default=0)
    if largest_vram_bytes >= required_memory_bytes:
        level = CompatibilityLevel.OK
        messages.append(
            f"Fits in GPU memory (est. {_format_gb(required_memory_bytes)} of "
            f"{_format_gb(largest_vram_bytes)} VRAM)."
        )
    elif info.ram_total_bytes >= required_memory_bytes:
        level = CompatibilityLevel.WARNING
        if info.gpus:
            messages.append(
                f"Needs an estimated {_format_gb(required_memory_bytes)} of memory but this "
                f"machine has {_format_gb(largest_vram_bytes)} of VRAM — it will fall back to "
                "CPU/RAM and run slowly."
            )
        else:
            messages.append(
                f"No GPU detected — needs an estimated {_format_gb(required_memory_bytes)} of "
                f"memory and will run on the CPU using {_format_gb(info.ram_total_bytes)} of "
                "RAM, which will be slow."
            )
    else:
        level = CompatibilityLevel.INSUFFICIENT
        messages.append(
            f"Needs an estimated {_format_gb(required_memory_bytes)} of memory but this machine "
            f"only has {_format_gb(info.ram_total_bytes)} of RAM — it is unlikely to run at all."
        )

    if not disk_ok:
        level = CompatibilityLevel.INSUFFICIENT

    return CompatibilityCheck(
        level=level,
        disk_ok=disk_ok,
        required_disk_bytes=required_disk_bytes,
        required_memory_bytes=required_memory_bytes,
        messages=messages,
    )
