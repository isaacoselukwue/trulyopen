export type Modality = "chat" | "vision-chat" | "image-gen" | "unsupported";
export type ModelFormat = "gguf" | "transformers" | "diffusers" | "peft" | "unknown";
export type CompatibilityLevel = "ok" | "warning" | "insufficient";
export type DownloadStatus =
  | "queued"
  | "downloading"
  | "paused"
  | "completed"
  | "error"
  | "cancelled";


export interface GPUInfo {
  name: string;
  vram_total_bytes: number;
  vram_free_bytes: number;
}

export interface BackendAvailability {
  torch_available: boolean;
  cuda_available: boolean;
  transformers_available: boolean;
  diffusers_available: boolean;
  llama_cpp_available: boolean;
}

export interface HardwareInfo {
  ram_total_bytes: number;
  ram_available_bytes: number;
  disk_total_bytes: number;
  disk_free_bytes: number;
  gpus: GPUInfo[];
  backends: BackendAvailability;
}


export interface RepoFile {
  path: string;
  size_bytes: number;
}

export interface CompatibilityCheck {
  level: CompatibilityLevel;
  disk_ok: boolean;
  required_disk_bytes: number;
  required_memory_bytes: number;
  messages: string[];
}

export interface ModelResolveResponse {
  repo_id: string;
  name: string;
  author: string | null;
  pipeline_tag: string | null;
  tags: string[];
  modality: Modality;
  format: ModelFormat;
  base_model: string | null;
  files: RepoFile[];
  total_size_bytes: number;
  download_size_bytes: number;
  gguf_options: RepoFile[] | null;
  gated: boolean;
  compatibility: CompatibilityCheck;
}


export interface DownloadJob {
  id: string;
  repo_id: string;
  status: DownloadStatus;
  total_bytes: number;
  downloaded_bytes: number;
  speed_bps: number;
  eta_seconds: number | null;
  current_file: string | null;
  files_done: number;
  files_total: number;
  error: string | null;
  model_id: string | null;
}


export interface LocalModel {
  id: string;
  repo_id: string;
  name: string;
  format: ModelFormat;
  modality: Modality;
  pipeline_tag: string | null;
  base_model: string | null;
  size_bytes: number;
  path: string;
  downloaded_at: string;
}

export interface LoadedModelInfo {
  model_id: string | null;
  device: string | null;
}

export interface DeleteResponse {
  ok: boolean;
  freed_bytes: number;
}

export interface OkResponse {
  ok: boolean;
}


export type ChatRole = "system" | "user" | "assistant";

export interface ChatMessage {
  role: ChatRole;
  content: string;
  images?: string[] | null;
}

export interface GenerationParams {
  temperature: number;
  top_p: number;
  top_k: number;
  repetition_penalty: number;
  max_tokens: number;
  system_prompt: string | null;
}

export const DEFAULT_GENERATION_PARAMS: GenerationParams = {
  temperature: 0.7,
  top_p: 0.95,
  top_k: 40,
  repetition_penalty: 1.1,
  max_tokens: 1024,
  system_prompt: null,
};

export interface ChatRequest {
  model_id: string;
  messages: ChatMessage[];
  params: GenerationParams;
}

export interface ImageGenRequest {
  model_id: string;
  prompt: string;
  negative_prompt: string | null;
  width: number;
  height: number;
  steps: number;
  guidance_scale: number;
  seed: number | null;
  num_images: number;
}

export interface ImageParams {
  width: number;
  height: number;
  steps: number;
  guidance_scale: number;
  seed: number | null;
  num_images: number;
}

export const DEFAULT_IMAGE_PARAMS: ImageParams = {
  width: 512,
  height: 512,
  steps: 25,
  guidance_scale: 7.0,
  seed: null,
  num_images: 1,
};

export interface GeneratedImage {
  b64_png: string;
  seed: number;
}

export interface ImageGenResponse {
  images: GeneratedImage[];
  duration_seconds: number;
}


export type ChatStreamEvent =
  | { type: "token"; token: string }
  | { type: "done"; tokens: number; duration_seconds: number }
  | { type: "error"; message: string };
