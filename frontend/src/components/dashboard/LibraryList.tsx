import { useState } from "react";
import { CircleDot, PlayCircle, Trash2 } from "lucide-react";
import { formatBytes } from "@/lib/format";
import type { LoadedModelInfo, LocalModel } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

export function LibraryList({
  models,
  loaded,
  onOpen,
  onDelete,
  onLoad,
  onUnload,
}: {
  models: LocalModel[];
  loaded: LoadedModelInfo | null;
  onOpen: (model: LocalModel) => void;
  onDelete: (model: LocalModel) => void;
  onLoad: (model: LocalModel) => void;
  onUnload: () => void;
}) {
  const [pendingDelete, setPendingDelete] = useState<LocalModel | null>(null);

  if (models.length === 0) {
    return (
      <Card>
        <CardContent className="py-10 text-center text-sm text-muted-foreground">
          Your library is empty — search a model above to get started.
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {models.map((model) => {
          const isLoaded = loaded?.model_id === model.id;
          const runnable = model.format !== "unknown";
          const openable = runnable && model.modality !== "unsupported";
          const blockedReason =
            model.format === "unknown"
              ? "This model uses a custom format TrulyOpen cannot run (only GGUF, Transformers, Diffusers and PEFT adapters are supported)."
              : "The playground does not support this model type yet.";
          return (
            <Card key={model.id} className="flex flex-col">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 break-all text-base">
                  {model.name}
                  {isLoaded && <CircleDot className="size-4 shrink-0 text-success" />}
                </CardTitle>
                <CardDescription className="break-all">{model.repo_id}</CardDescription>
                {model.format === "peft" && model.base_model && (
                  <CardDescription className="break-all">
                    LoRA adapter for {model.base_model}
                  </CardDescription>
                )}
                <div className="flex flex-wrap gap-1.5 pt-1">
                  <Badge variant="outline">{model.format}</Badge>
                  <Badge variant="secondary">{model.modality}</Badge>
                  <Badge variant="outline">{formatBytes(model.size_bytes)}</Badge>
                </div>
              </CardHeader>
              <CardFooter className="mt-auto flex flex-wrap gap-2">
                {openable ? (
                  <Button size="sm" onClick={() => onOpen(model)}>
                    <PlayCircle />
                    Open in playground
                  </Button>
                ) : (
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <span tabIndex={0}>
                        <Button size="sm" disabled className="pointer-events-none">
                          <PlayCircle />
                          Open in playground
                        </Button>
                      </span>
                    </TooltipTrigger>
                    <TooltipContent>{blockedReason}</TooltipContent>
                  </Tooltip>
                )}
                {runnable && (
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => (isLoaded ? onUnload() : onLoad(model))}
                  >
                    {isLoaded ? "Unload" : "Load"}
                  </Button>
                )}
                <Button
                  size="sm"
                  variant="outline"
                  className="ml-auto text-destructive hover:text-destructive"
                  onClick={() => setPendingDelete(model)}
                >
                  <Trash2 />
                  Delete
                </Button>
              </CardFooter>
            </Card>
          );
        })}
      </div>
      <Dialog open={pendingDelete !== null} onOpenChange={(open) => !open && setPendingDelete(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete {pendingDelete?.name}?</DialogTitle>
            <DialogDescription>
              This will permanently remove{" "}
              {pendingDelete ? formatBytes(pendingDelete.size_bytes) : ""} from disk. This cannot
              be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPendingDelete(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                if (pendingDelete) onDelete(pendingDelete);
                setPendingDelete(null);
              }}
            >
              <Trash2 />
              Delete model
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
