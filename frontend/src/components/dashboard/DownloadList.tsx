import { Pause, Play, Trash2, X } from "lucide-react";
import { formatBytes, formatEta, formatPercent, formatSpeed } from "@/lib/format";
import type { DownloadJob, DownloadStatus } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";

const STATUS_VARIANTS: Record<
  DownloadStatus,
  "default" | "secondary" | "destructive" | "outline" | "success" | "warning"
> = {
  queued: "secondary",
  downloading: "default",
  paused: "warning",
  completed: "success",
  error: "destructive",
  cancelled: "outline",
};

export function DownloadList({
  downloads,
  onPause,
  onResume,
  onCancel,
  onRemove,
}: {
  downloads: DownloadJob[];
  onPause: (id: string) => void;
  onResume: (id: string) => void;
  onCancel: (id: string) => void;
  onRemove: (id: string) => void;
}) {
  if (downloads.length === 0) {
    return <p className="text-sm text-muted-foreground">No downloads yet.</p>;
  }

  return (
    <div className="space-y-4">
      {downloads.map((job) => {
        const active = job.status === "queued" || job.status === "downloading";
        const percent = formatPercent(job.downloaded_bytes, job.total_bytes);
        return (
          <div key={job.id} className="space-y-2 rounded-lg border p-3">
            <div className="flex items-center justify-between gap-2">
              <span className="min-w-0 truncate text-sm font-medium">{job.repo_id}</span>
              <Badge variant={STATUS_VARIANTS[job.status]}>{job.status}</Badge>
            </div>
            {(active || job.status === "paused" || job.status === "error") && (
              <>
                <Progress value={percent} />
                <div className="flex flex-wrap justify-between gap-x-3 gap-y-1 text-xs text-muted-foreground">
                  <span>
                    {formatBytes(job.downloaded_bytes)} / {formatBytes(job.total_bytes)} (
                    {percent.toFixed(0)}%)
                  </span>
                  {job.status === "downloading" && (
                    <span>
                      {formatSpeed(job.speed_bps)} · ETA {formatEta(job.eta_seconds)}
                    </span>
                  )}
                </div>
                {job.current_file && job.status === "downloading" && (
                  <p className="truncate text-xs text-muted-foreground">
                    {job.files_done + 1}/{job.files_total} · {job.current_file}
                  </p>
                )}
              </>
            )}
            {job.error && <p className="text-xs text-destructive">{job.error}</p>}
            <div className="flex gap-1">
              {job.status === "downloading" && (
                <Button variant="ghost" size="icon" aria-label="Pause" onClick={() => onPause(job.id)}>
                  <Pause />
                </Button>
              )}
              {(job.status === "paused" || job.status === "error") && (
                <Button variant="ghost" size="icon" aria-label="Resume" onClick={() => onResume(job.id)}>
                  <Play />
                </Button>
              )}
              {(active || job.status === "paused" || job.status === "error") && (
                <Button variant="ghost" size="icon" aria-label="Cancel" onClick={() => onCancel(job.id)}>
                  <X />
                </Button>
              )}
              {!active && job.status !== "paused" && job.status !== "error" && (
                <Button variant="ghost" size="icon" aria-label="Remove" onClick={() => onRemove(job.id)}>
                  <Trash2 />
                </Button>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
