import type {
  ChatRequest,
  ChatStreamEvent,
  DeleteResponse,
  DownloadJob,
  HardwareInfo,
  ImageGenRequest,
  ImageGenResponse,
  LoadedModelInfo,
  LocalModel,
  ModelResolveResponse,
  OkResponse,
} from "./types";

const API_BASE: string = import.meta.env.VITE_API_BASE ?? "";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch {
    throw new ApiError(0, "Cannot reach the local backend. Is it running on port 8000?");
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}


export function getHardware(): Promise<HardwareInfo> {
  return request<HardwareInfo>("/api/system/hardware");
}


export function resolveModel(repoId: string): Promise<ModelResolveResponse> {
  return request<ModelResolveResponse>(
    `/api/models/resolve?repo_id=${encodeURIComponent(repoId)}`,
  );
}


export function listDownloads(): Promise<DownloadJob[]> {
  return request<DownloadJob[]>("/api/downloads");
}

export function startDownload(repoId: string, files?: string[]): Promise<DownloadJob> {
  return request<DownloadJob>("/api/downloads", {
    method: "POST",
    body: JSON.stringify({ repo_id: repoId, files: files ?? null }),
  });
}

export function pauseDownload(jobId: string): Promise<DownloadJob> {
  return request<DownloadJob>(`/api/downloads/${jobId}/pause`, { method: "POST" });
}

export function resumeDownload(jobId: string): Promise<DownloadJob> {
  return request<DownloadJob>(`/api/downloads/${jobId}/resume`, { method: "POST" });
}

export function cancelDownload(jobId: string): Promise<DownloadJob> {
  return request<DownloadJob>(`/api/downloads/${jobId}/cancel`, { method: "POST" });
}

export function removeDownload(jobId: string): Promise<OkResponse> {
  return request<OkResponse>(`/api/downloads/${jobId}`, { method: "DELETE" });
}


export function listLibrary(): Promise<LocalModel[]> {
  return request<LocalModel[]>("/api/library");
}

export function deleteModel(modelId: string): Promise<DeleteResponse> {
  return request<DeleteResponse>(`/api/library/${modelId}`, { method: "DELETE" });
}

export function getLoaded(): Promise<LoadedModelInfo> {
  return request<LoadedModelInfo>("/api/library/loaded");
}

export function loadModel(modelId: string): Promise<LoadedModelInfo> {
  return request<LoadedModelInfo>(`/api/library/${modelId}/load`, { method: "POST" });
}

export function unloadModel(): Promise<OkResponse> {
  return request<OkResponse>("/api/library/unload", { method: "POST" });
}


export function generateImage(req: ImageGenRequest): Promise<ImageGenResponse> {
  return request<ImageGenResponse>("/api/generate/image", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export interface ChatStreamHandlers {
  onToken: (token: string) => void;
  onDone: (event: Extract<ChatStreamEvent, { type: "done" }>) => void;
  onError: (message: string) => void;
}

export async function streamChat(
  req: ChatRequest,
  handlers: ChatStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/generate/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
      signal,
    });
  } catch (err) {
    if ((err as Error).name === "AbortError") return;
    handlers.onError("Cannot reach the local backend. Is it running on port 8000?");
    return;
  }

  if (!res.ok || !res.body) {
    let detail = `Generation failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
    }
    handlers.onError(detail);
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const frames = buffer.split("\n\n");
      buffer = frames.pop() ?? "";
      for (const frame of frames) {
        const line = frame.split("\n").find((l) => l.startsWith("data: "));
        if (!line) continue;
        let event: ChatStreamEvent;
        try {
          event = JSON.parse(line.slice(6)) as ChatStreamEvent;
        } catch {
          continue;
        }
        if (event.type === "token") handlers.onToken(event.token);
        else if (event.type === "done") handlers.onDone(event);
        else if (event.type === "error") handlers.onError(event.message);
      }
    }
  } catch (err) {
    if ((err as Error).name !== "AbortError") {
      handlers.onError("The response stream was interrupted.");
    }
  }
}
