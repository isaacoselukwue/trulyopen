import { useEffect, useRef, useState } from "react";
import { Cpu, DownloadCloud, Library } from "lucide-react";
import type { LocalModel, ModelResolveResponse } from "@/lib/types";
import { useDownloads } from "@/hooks/useDownloads";
import { useHardware } from "@/hooks/useHardware";
import { useLibrary } from "@/hooks/useLibrary";
import { CompatibilityCard } from "@/components/dashboard/CompatibilityCard";
import { DownloadList } from "@/components/dashboard/DownloadList";
import { HardwareBar } from "@/components/dashboard/HardwareBar";
import { LibraryList } from "@/components/dashboard/LibraryList";
import { ModelSearchBar } from "@/components/dashboard/ModelSearchBar";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function DashboardView({
  onOpenPlayground,
}: {
  onOpenPlayground: (model: LocalModel) => void;
}) {
  const { hardware } = useHardware();
  const downloadsState = useDownloads();
  const library = useLibrary();
  const [resolved, setResolved] = useState<ModelResolveResponse | null>(null);
  const knownCompleted = useRef<Set<string>>(new Set());

  useEffect(() => {
    for (const job of downloadsState.downloads) {
      if (job.status === "completed" && job.model_id && !knownCompleted.current.has(job.id)) {
        knownCompleted.current.add(job.id);
        void library.refresh();
      }
    }
  }, [downloadsState.downloads, library]);

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_340px]">
      <div className="min-w-0 space-y-6">
        <ModelSearchBar onResolved={setResolved} />
        {resolved && (
          <CompatibilityCard
            key={resolved.repo_id}
            resolved={resolved}
            onStartDownload={(repoId, files) => void downloadsState.start(repoId, files)}
          />
        )}
        <section className="space-y-3">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-muted-foreground">
            <Library className="size-4" />
            Local library
          </h2>
          <LibraryList
            models={library.models}
            loaded={library.loaded}
            onOpen={onOpenPlayground}
            onDelete={(model) => void library.deleteModel(model)}
            onLoad={(model) => void library.loadModel(model)}
            onUnload={() => void library.unloadModel()}
          />
        </section>
      </div>
      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm">
              <Cpu className="size-4" />
              System
            </CardTitle>
          </CardHeader>
          <CardContent>
            <HardwareBar hardware={hardware} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm">
              <DownloadCloud className="size-4" />
              Downloads
            </CardTitle>
          </CardHeader>
          <CardContent>
            <DownloadList
              downloads={downloadsState.downloads}
              onPause={(id) => void downloadsState.pause(id)}
              onResume={(id) => void downloadsState.resume(id)}
              onCancel={(id) => void downloadsState.cancel(id)}
              onRemove={(id) => void downloadsState.remove(id)}
            />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
