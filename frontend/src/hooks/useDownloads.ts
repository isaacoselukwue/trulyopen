import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import {
  cancelDownload,
  listDownloads,
  pauseDownload,
  removeDownload,
  resumeDownload,
  startDownload,
} from "@/lib/api";
import type { DownloadJob, DownloadStatus } from "@/lib/types";

export function useDownloads() {
  const [downloads, setDownloads] = useState<DownloadJob[]>([]);
  const previousStatuses = useRef<Map<string, DownloadStatus>>(new Map());

  const refresh = useCallback(async () => {
    try {
      const jobs = await listDownloads();
      const previous = previousStatuses.current;
      for (const job of jobs) {
        const before = previous.get(job.id);
        if (before && before !== job.status) {
          if (job.status === "completed") {
            toast.success("Model downloaded", { description: job.repo_id });
          } else if (job.status === "error") {
            toast.error("Download failed", { description: job.error ?? job.repo_id });
          }
        }
        previous.set(job.id, job.status);
      }
      setDownloads(jobs);
    } catch {
      return;
    }
  }, []);

  const anyActive = downloads.some(
    (job) => job.status === "queued" || job.status === "downloading",
  );

  useEffect(() => {
    void refresh();
    const interval = setInterval(() => void refresh(), anyActive ? 1000 : 5000);
    return () => clearInterval(interval);
  }, [refresh, anyActive]);

  const runAction = useCallback(
    async (action: () => Promise<unknown>) => {
      try {
        await action();
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Something went wrong.");
      } finally {
        void refresh();
      }
    },
    [refresh],
  );

  const start = useCallback(
    (repoId: string, files?: string[]) => runAction(() => startDownload(repoId, files)),
    [runAction],
  );
  const pause = useCallback((id: string) => runAction(() => pauseDownload(id)), [runAction]);
  const resume = useCallback((id: string) => runAction(() => resumeDownload(id)), [runAction]);
  const cancel = useCallback((id: string) => runAction(() => cancelDownload(id)), [runAction]);
  const remove = useCallback((id: string) => runAction(() => removeDownload(id)), [runAction]);

  return { downloads, start, pause, resume, cancel, remove, refresh };
}
