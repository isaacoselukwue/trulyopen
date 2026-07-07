from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


class Modality(str, Enum):
    CHAT = "chat"
    VISION_CHAT = "vision-chat"
    IMAGE_GEN = "image-gen"
    UNSUPPORTED = "unsupported"


class ModelFormat(str, Enum):
    GGUF = "gguf"
    TRANSFORMERS = "transformers"
    DIFFUSERS = "diffusers"
    PEFT = "peft"
    UNKNOWN = "unknown"


class CompatibilityLevel(str, Enum):
    OK = "ok"
    WARNING = "warning"
    INSUFFICIENT = "insufficient"


class DownloadStatus(str, Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


class GPUInfo(BaseModel):
    name: str
    vram_total_bytes: int
    vram_free_bytes: int


class BackendAvailability(BaseModel):
    torch_available: bool
    cuda_available: bool
    transformers_available: bool
    diffusers_available: bool
    llama_cpp_available: bool


class HardwareInfo(BaseModel):
    ram_total_bytes: int
    ram_available_bytes: int
    disk_total_bytes: int
    disk_free_bytes: int
    gpus: list[GPUInfo]
    backends: BackendAvailability


class RepoFile(BaseModel):
    path: str
    size_bytes: int


class CompatibilityCheck(BaseModel):
    level: CompatibilityLevel
    disk_ok: bool
    required_disk_bytes: int
    required_memory_bytes: int
    messages: list[str]


class ModelResolveResponse(BaseModel):
    repo_id: str
    name: str
    author: Optional[str] = None
    pipeline_tag: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    modality: Modality
    format: ModelFormat
    base_model: Optional[str] = None
    files: list[RepoFile]
    total_size_bytes: int
    download_size_bytes: int
    gguf_options: Optional[list[RepoFile]] = None
    gated: bool = False
    compatibility: CompatibilityCheck


class DownloadRequest(BaseModel):
    repo_id: str
    files: Optional[list[str]] = None


class DownloadJob(BaseModel):
    id: str
    repo_id: str
    status: DownloadStatus
    total_bytes: int
    downloaded_bytes: int
    speed_bps: float = 0.0
    eta_seconds: Optional[float] = None
    current_file: Optional[str] = None
    files_done: int = 0
    files_total: int = 0
    error: Optional[str] = None
    model_id: Optional[str] = None


class LocalModel(BaseModel):
    id: str
    repo_id: str
    name: str
    format: ModelFormat
    modality: Modality
    pipeline_tag: Optional[str] = None
    base_model: Optional[str] = None
    size_bytes: int
    path: str
    downloaded_at: str


class LoadedModelInfo(BaseModel):
    model_id: Optional[str] = None
    device: Optional[str] = None


class DeleteResponse(BaseModel):
    ok: bool = True
    freed_bytes: int = 0


class OkResponse(BaseModel):
    ok: bool = True


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str
    images: Optional[list[str]] = None


class GenerationParams(BaseModel):
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    top_p: float = Field(default=0.95, ge=0.0, le=1.0)
    top_k: int = Field(default=40, ge=1, le=200)
    repetition_penalty: float = Field(default=1.1, ge=1.0, le=2.0)
    max_tokens: int = Field(default=1024, ge=16, le=8192)
    system_prompt: Optional[str] = None


class ChatRequest(BaseModel):
    model_id: str
    messages: list[ChatMessage]
    params: GenerationParams = Field(default_factory=GenerationParams)


class ImageGenRequest(BaseModel):
    model_id: str
    prompt: str
    negative_prompt: Optional[str] = None
    width: int = Field(default=512, ge=256, le=2048)
    height: int = Field(default=512, ge=256, le=2048)
    steps: int = Field(default=25, ge=1, le=150)
    guidance_scale: float = Field(default=7.0, ge=0.0, le=30.0)
    seed: Optional[int] = None
    num_images: int = Field(default=1, ge=1, le=4)


class GeneratedImage(BaseModel):
    b64_png: str
    seed: int


class ImageGenResponse(BaseModel):
    images: list[GeneratedImage]
    duration_seconds: float
