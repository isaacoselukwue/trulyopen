import { formatBytes } from "@/lib/format";
import type { HardwareInfo } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

function Meter({ label, used, total }: { label: string; used: number; total: number }) {
  const percent = total > 0 ? (used / total) * 100 : 0;
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="font-medium">{label}</span>
        <span className="text-muted-foreground">
          {formatBytes(used)} / {formatBytes(total)}
        </span>
      </div>
      <Progress value={percent} />
    </div>
  );
}

function BackendBadge({ label, available }: { label: string; available: boolean }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Badge variant={available ? "success" : "outline"}>{label}</Badge>
      </TooltipTrigger>
      <TooltipContent>
        {available
          ? `${label} is available for local inference.`
          : "Install requirements-ml.txt to enable local inference."}
      </TooltipContent>
    </Tooltip>
  );
}

export function HardwareBar({ hardware }: { hardware: HardwareInfo | null }) {
  if (!hardware) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-8 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <Meter
        label="RAM"
        used={hardware.ram_total_bytes - hardware.ram_available_bytes}
        total={hardware.ram_total_bytes}
      />
      <Meter
        label="Disk"
        used={hardware.disk_total_bytes - hardware.disk_free_bytes}
        total={hardware.disk_total_bytes}
      />
      {hardware.gpus.map((gpu) => (
        <Meter
          key={gpu.name}
          label={gpu.name}
          used={gpu.vram_total_bytes - gpu.vram_free_bytes}
          total={gpu.vram_total_bytes}
        />
      ))}
      {hardware.gpus.length === 0 && (
        <p className="text-xs text-muted-foreground">No GPU detected — models will run on the CPU.</p>
      )}
      <div className="flex flex-wrap gap-1.5 pt-1">
        <BackendBadge label="torch" available={hardware.backends.torch_available} />
        <BackendBadge label="CUDA" available={hardware.backends.cuda_available} />
        <BackendBadge label="transformers" available={hardware.backends.transformers_available} />
        <BackendBadge label="diffusers" available={hardware.backends.diffusers_available} />
        <BackendBadge label="llama.cpp" available={hardware.backends.llama_cpp_available} />
      </div>
    </div>
  );
}
