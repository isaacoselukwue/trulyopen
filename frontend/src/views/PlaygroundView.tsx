import { useState } from "react";
import { ArrowLeft, Settings2 } from "lucide-react";
import {
  DEFAULT_GENERATION_PARAMS,
  DEFAULT_IMAGE_PARAMS,
  type GenerationParams,
  type ImageParams,
  type LocalModel,
} from "@/lib/types";
import { ChatPanel } from "@/components/playground/ChatPanel";
import { ImageStudio } from "@/components/playground/ImageStudio";
import { ParamsSidebar } from "@/components/playground/ParamsSidebar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export default function PlaygroundView({
  model,
  onBack,
}: {
  model: LocalModel;
  onBack: () => void;
}) {
  const [params, setParams] = useState<GenerationParams>(DEFAULT_GENERATION_PARAMS);
  const [imageParams, setImageParams] = useState<ImageParams>(DEFAULT_IMAGE_PARAMS);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const hasSettings = model.modality !== "unsupported";

  return (
    <div className="flex flex-col">
      <div className="flex items-center gap-3 pb-4">
        <Button variant="ghost" size="icon" aria-label="Back" onClick={onBack}>
          <ArrowLeft />
        </Button>
        <div className="min-w-0 flex-1">
          <h1 className="truncate font-semibold">{model.name}</h1>
        </div>
        <Badge variant="secondary">{model.modality}</Badge>
        {hasSettings && (
          <Button
            variant="outline"
            size="icon"
            className="lg:hidden"
            aria-label="Generation settings"
            onClick={() => setSettingsOpen(true)}
          >
            <Settings2 />
          </Button>
        )}
      </div>
      <div className="flex h-[calc(100dvh-9.5rem)] overflow-hidden rounded-lg border">
        <div className="flex min-w-0 flex-1 flex-col">
          {model.modality === "chat" || model.modality === "vision-chat" ? (
            <ChatPanel model={model} params={params} />
          ) : model.modality === "image-gen" ? (
            <ImageStudio model={model} dims={imageParams} />
          ) : (
            <div className="flex flex-1 items-center justify-center p-6">
              <Card className="max-w-md">
                <CardContent className="py-8 text-center text-sm text-muted-foreground">
                  This model type can be downloaded but the playground does not support it yet.
                </CardContent>
              </Card>
            </div>
          )}
        </div>
        <ParamsSidebar
          modality={model.modality}
          params={params}
          onParamsChange={setParams}
          imageParams={imageParams}
          onImageParamsChange={setImageParams}
          open={settingsOpen}
          onClose={() => setSettingsOpen(false)}
        />
      </div>
    </div>
  );
}
