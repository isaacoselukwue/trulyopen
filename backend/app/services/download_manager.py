from __future__ import annotations

import json
import logging
import os
import shutil
import threading
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests

from app.config import (
    DOWNLOADS_STATE_PATH,
    DOWNLOAD_CHUNK_BYTES,
    HF_API_BASE,
    MODELS_DIR,
    SPEED_WINDOW_SECONDS,
    model_dir_name,
)
from app.schemas import DownloadJob, DownloadStatus, LocalModel, RepoFile
from app.services import hf_hub, registry

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = {DownloadStatus.QUEUED, DownloadStatus.DOWNLOADING, DownloadStatus.PAUSED}
RUNNING_STATUSES = {DownloadStatus.QUEUED, DownloadStatus.DOWNLOADING}
CONNECTION_LOST_MESSAGE = "Connection to Hugging Face was lost — resume the download to retry."


class _JobContext:
    def __init__(self, job: DownloadJob, plan: list[RepoFile], meta: dict[str, str | None]) -> None:
        self.job = job
        self.plan = plan
        self.meta = meta
        self.pause_event = threading.Event()
        self.cancel_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.samples: deque[tuple[float, int]] = deque()


class DownloadManager:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._contexts: dict[str, _JobContext] = {}
        self._rehydrate()

    def _assert_startable(self, normalized: str, model_id: str) -> None:
        for ctx in self._contexts.values():
            if ctx.job.repo_id != normalized:
                continue
            if ctx.job.status in ACTIVE_STATUSES:
                raise ValueError(f"{normalized} is already downloading.")
            if ctx.thread is not None and ctx.thread.is_alive():
                raise ValueError(f"{normalized} is still winding down — try again in a moment.")
        if registry.get_model(model_id) is not None:
            raise ValueError(f"{normalized} is already in your library.")

    def start(self, repo_id: str, files: list[str] | None) -> DownloadJob:
        normalized = hf_hub.normalize_repo_id(repo_id)
        model_id = model_dir_name(normalized)
        with self._lock:
            self._assert_startable(normalized, model_id)
        resolved = hf_hub.resolve_model(normalized, files)
        plan = hf_hub.plan_download(resolved.files, resolved.format, files)
        if not plan:
            raise ValueError("This repository has no downloadable model files.")
        job = DownloadJob(
            id=uuid.uuid4().hex[:12],
            repo_id=normalized,
            status=DownloadStatus.QUEUED,
            total_bytes=sum(f.size_bytes for f in plan),
            downloaded_bytes=0,
            files_total=len(plan),
        )
        meta = {
            "modality": resolved.modality.value,
            "format": resolved.format.value,
            "pipeline_tag": resolved.pipeline_tag,
            "name": resolved.name,
            "base_model": resolved.base_model,
        }
        ctx = _JobContext(job, plan, meta)
        with self._lock:
            self._assert_startable(normalized, model_id)
            self._contexts[job.id] = ctx
            self._persist()
        self._spawn(ctx)
        return job.model_copy()

    def list(self) -> list[DownloadJob]:
        with self._lock:
            return [ctx.job.model_copy() for ctx in self._contexts.values()]

    def get(self, job_id: str) -> DownloadJob | None:
        with self._lock:
            ctx = self._contexts.get(job_id)
            return ctx.job.model_copy() if ctx else None

    def pause(self, job_id: str) -> DownloadJob:
        with self._lock:
            ctx = self._require(job_id)
            if ctx.job.status not in RUNNING_STATUSES:
                raise ValueError("Only an active download can be paused.")
            ctx.pause_event.set()
            ctx.job.status = DownloadStatus.PAUSED
            ctx.job.speed_bps = 0.0
            ctx.job.eta_seconds = None
            self._persist()
            return ctx.job.model_copy()

    def resume(self, job_id: str) -> DownloadJob:
        with self._lock:
            ctx = self._require(job_id)
            if ctx.job.status not in {DownloadStatus.PAUSED, DownloadStatus.ERROR}:
                raise ValueError("Only a paused or failed download can be resumed.")
            if ctx.thread is not None and ctx.thread.is_alive():
                raise ValueError("This download is still winding down — try again in a moment.")
            ctx.pause_event.clear()
            ctx.cancel_event.clear()
            ctx.job.error = None
            ctx.job.status = DownloadStatus.QUEUED
            ctx.job.downloaded_bytes = self._bytes_on_disk(ctx)
            ctx.samples.clear()
            self._persist()
            self._spawn(ctx)
            return ctx.job.model_copy()

    def cancel(self, job_id: str) -> DownloadJob:
        with self._lock:
            ctx = self._require(job_id)
            if ctx.job.status not in ACTIVE_STATUSES and ctx.job.status is not DownloadStatus.ERROR:
                raise ValueError("This download has already finished.")
            ctx.cancel_event.set()
            worker_running = ctx.thread is not None and ctx.thread.is_alive()
            ctx.job.status = DownloadStatus.CANCELLED
            ctx.job.speed_bps = 0.0
            ctx.job.eta_seconds = None
            if not worker_running:
                self._delete_partial(ctx)
            self._persist()
            return ctx.job.model_copy()

    def remove(self, job_id: str) -> None:
        with self._lock:
            ctx = self._require(job_id)
            if ctx.job.status in ACTIVE_STATUSES:
                raise ValueError("Cancel the download before removing it from the list.")
            del self._contexts[job_id]
            self._persist()

    def _require(self, job_id: str) -> _JobContext:
        ctx = self._contexts.get(job_id)
        if ctx is None:
            raise KeyError(job_id)
        return ctx

    def _target_dir(self, ctx: _JobContext) -> Path:
        return MODELS_DIR / model_dir_name(ctx.job.repo_id)

    def _bytes_on_disk(self, ctx: _JobContext) -> int:
        target = self._target_dir(ctx)
        total = 0
        for repo_file in ctx.plan:
            dest = target / repo_file.path
            if dest.exists():
                total += dest.stat().st_size
        return total

    def _delete_partial(self, ctx: _JobContext) -> None:
        shutil.rmtree(self._target_dir(ctx), ignore_errors=True)

    def _spawn(self, ctx: _JobContext) -> None:
        thread = threading.Thread(target=self._worker, args=(ctx,), daemon=True)
        ctx.thread = thread
        thread.start()

    def _record_progress(self, ctx: _JobContext, chunk_size: int, base_bytes: int, file_bytes: int) -> None:
        now = time.monotonic()
        with self._lock:
            ctx.samples.append((now, chunk_size))
            while ctx.samples and now - ctx.samples[0][0] > SPEED_WINDOW_SECONDS:
                ctx.samples.popleft()
            window_bytes = sum(size for _, size in ctx.samples)
            window_span = now - ctx.samples[0][0] if len(ctx.samples) > 1 else 0.0
            speed = window_bytes / window_span if window_span > 0 else 0.0
            ctx.job.downloaded_bytes = base_bytes + file_bytes
            ctx.job.speed_bps = round(speed, 1)
            remaining = ctx.job.total_bytes - ctx.job.downloaded_bytes
            ctx.job.eta_seconds = round(remaining / speed, 1) if speed > 0 and remaining > 0 else None

    def _worker(self, ctx: _JobContext) -> None:
        job = ctx.job
        target = self._target_dir(ctx)
        try:
            with self._lock:
                job.status = DownloadStatus.DOWNLOADING
                self._persist()
            base_bytes = 0
            files_done = 0
            for repo_file in ctx.plan:
                if ctx.cancel_event.is_set():
                    self._finish_cancel(ctx)
                    return
                if ctx.pause_event.is_set():
                    self._finish_pause(ctx)
                    return
                dest = target / repo_file.path
                dest.parent.mkdir(parents=True, exist_ok=True)
                existing = dest.stat().st_size if dest.exists() else 0
                if repo_file.size_bytes > 0 and existing >= repo_file.size_bytes:
                    base_bytes += existing
                    files_done += 1
                    with self._lock:
                        job.files_done = files_done
                        job.downloaded_bytes = base_bytes
                    continue
                with self._lock:
                    job.current_file = repo_file.path
                    self._persist()
                outcome = self._download_file(ctx, repo_file, dest, existing, base_bytes)
                if outcome == "cancelled":
                    self._finish_cancel(ctx)
                    return
                if outcome == "paused":
                    self._finish_pause(ctx)
                    return
                base_bytes += dest.stat().st_size if dest.exists() else 0
                files_done += 1
                with self._lock:
                    job.files_done = files_done
                    job.downloaded_bytes = base_bytes
            self._finish_complete(ctx)
        except requests.RequestException:
            logger.exception("Download %s failed with a network error", job.id)
            self._finish_error(ctx, CONNECTION_LOST_MESSAGE)
        except Exception as exc:
            logger.exception("Download %s failed", job.id)
            self._finish_error(ctx, f"Download failed: {exc}")

    def _download_file(
        self,
        ctx: _JobContext,
        repo_file: RepoFile,
        dest: Path,
        existing: int,
        base_bytes: int,
    ) -> str:
        url = f"{HF_API_BASE}/{ctx.job.repo_id}/resolve/main/{quote(repo_file.path)}"
        headers = {"Range": f"bytes={existing}-"} if existing > 0 else {}
        with requests.get(url, headers=headers, stream=True, timeout=(10, 30)) as response:
            if response.status_code == 200 and existing > 0:
                dest.unlink(missing_ok=True)
                existing = 0
            elif response.status_code not in (200, 206):
                raise requests.HTTPError(f"HTTP {response.status_code} for {repo_file.path}")
            file_bytes = existing
            with open(dest, "ab") as handle:
                for chunk in response.iter_content(chunk_size=DOWNLOAD_CHUNK_BYTES):
                    if ctx.cancel_event.is_set():
                        return "cancelled"
                    if ctx.pause_event.is_set():
                        return "paused"
                    if not chunk:
                        continue
                    handle.write(chunk)
                    file_bytes += len(chunk)
                    self._record_progress(ctx, len(chunk), base_bytes, file_bytes)
        return "done"

    def _finish_pause(self, ctx: _JobContext) -> None:
        with self._lock:
            pending_cancel = ctx.cancel_event.is_set()
            if not pending_cancel:
                ctx.job.status = DownloadStatus.PAUSED
                ctx.job.speed_bps = 0.0
                ctx.job.eta_seconds = None
                ctx.samples.clear()
                self._persist()
        if pending_cancel:
            self._finish_cancel(ctx)

    def _finish_cancel(self, ctx: _JobContext) -> None:
        self._delete_partial(ctx)
        with self._lock:
            ctx.job.status = DownloadStatus.CANCELLED
            ctx.job.speed_bps = 0.0
            ctx.job.eta_seconds = None
            ctx.samples.clear()
            self._persist()

    def _finish_error(self, ctx: _JobContext, message: str) -> None:
        with self._lock:
            pending_cancel = ctx.cancel_event.is_set()
            if not pending_cancel:
                ctx.job.status = DownloadStatus.ERROR
                ctx.job.error = message
                ctx.job.speed_bps = 0.0
                ctx.job.eta_seconds = None
                ctx.samples.clear()
                self._persist()
        if pending_cancel:
            self._finish_cancel(ctx)

    def _finish_complete(self, ctx: _JobContext) -> None:
        job = ctx.job
        target = self._target_dir(ctx)
        size_bytes = 0
        for root, _, filenames in os.walk(target):
            for filename in filenames:
                size_bytes += (Path(root) / filename).stat().st_size
        model = LocalModel(
            id=model_dir_name(job.repo_id),
            repo_id=job.repo_id,
            name=str(ctx.meta.get("name") or job.repo_id.split("/", 1)[1]),
            format=str(ctx.meta.get("format") or "unknown"),
            modality=str(ctx.meta.get("modality") or "unsupported"),
            pipeline_tag=ctx.meta.get("pipeline_tag"),
            base_model=ctx.meta.get("base_model"),
            size_bytes=size_bytes,
            path=str(target),
            downloaded_at=datetime.now(timezone.utc).isoformat(),
        )
        with self._lock:
            pending_cancel = ctx.cancel_event.is_set()
            if not pending_cancel:
                registry.add_model(model)
                job.status = DownloadStatus.COMPLETED
                job.model_id = model.id
                job.downloaded_bytes = job.total_bytes
                job.speed_bps = 0.0
                job.eta_seconds = None
                job.current_file = None
                ctx.samples.clear()
                self._persist()
        if pending_cancel:
            self._finish_cancel(ctx)

    def _persist(self) -> None:
        DOWNLOADS_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = [
            {
                "job": ctx.job.model_dump(mode="json"),
                "plan": [f.model_dump(mode="json") for f in ctx.plan],
                "meta": ctx.meta,
            }
            for ctx in self._contexts.values()
        ]
        temp_path = DOWNLOADS_STATE_PATH.with_name(DOWNLOADS_STATE_PATH.name + ".tmp")
        temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(temp_path, DOWNLOADS_STATE_PATH)

    def _rehydrate(self) -> None:
        if not DOWNLOADS_STATE_PATH.exists():
            return
        try:
            payload = json.loads(DOWNLOADS_STATE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning("Download state at %s is unreadable; starting fresh", DOWNLOADS_STATE_PATH)
            return
        if not isinstance(payload, list):
            return
        for entry in payload:
            try:
                job = DownloadJob.model_validate(entry["job"])
                plan = [RepoFile.model_validate(f) for f in entry.get("plan", [])]
                meta = dict(entry.get("meta", {}))
            except Exception:
                logger.warning("Skipping an invalid download-state entry")
                continue
            if job.status in RUNNING_STATUSES:
                job.status = DownloadStatus.PAUSED
            job.speed_bps = 0.0
            job.eta_seconds = None
            self._contexts[job.id] = _JobContext(job, plan, meta)


manager = DownloadManager()
