import { Info, SlidersHorizontal, X } from "lucide-react";
import type { GenerationParams, ImageParams, Modality } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

function InfoHint({ text }: { text: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button type="button" className="text-muted-foreground" aria-label="More information">
          <Info className="size-3.5" />
        </button>
      </TooltipTrigger>
      <TooltipContent>{text}</TooltipContent>
    </Tooltip>
  );
}

function SliderRow({
  label,
  hint,
  value,
  min,
  max,
  step,
  format,
  onChange,
}: {
  label: string;
  hint: string;
  value: number;
  min: number;
  max: number;
  step: number;
  format?: (value: number) => string;
  onChange: (value: number) => void;
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <Label>{label}</Label>
          <InfoHint text={hint} />
        </div>
        <span className="text-sm tabular-nums text-muted-foreground">
          {format ? format(value) : value}
        </span>
      </div>
      <Slider
        min={min}
        max={max}
        step={step}
        value={[value]}
        onValueChange={([next]) => onChange(next)}
      />
    </div>
  );
}

const DIMENSIONS = [512, 768, 1024];

export function ParamsSidebar({
  modality,
  params,
  onParamsChange,
  imageParams,
  onImageParamsChange,
  open,
  onClose,
}: {
  modality: Modality;
  params: GenerationParams;
  onParamsChange: (params: GenerationParams) => void;
  imageParams: ImageParams;
  onImageParamsChange: (params: ImageParams) => void;
  open: boolean;
  onClose: () => void;
}) {
  if (modality === "unsupported") return null;

  const isText = modality === "chat" || modality === "vision-chat";

  const body = (
    <div className="flex h-full flex-col gap-5 overflow-y-auto p-4">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-sm font-semibold">
          <SlidersHorizontal className="size-4" />
          Generation settings
        </h2>
        <Button
          variant="ghost"
          size="icon"
          className="lg:hidden"
          aria-label="Close settings"
          onClick={onClose}
        >
          <X />
        </Button>
      </div>

      {isText && (
        <>
          <SliderRow
            label="Temperature"
            hint="Higher values make replies more creative; lower values make them more focused and deterministic."
            value={params.temperature}
            min={0}
            max={2}
            step={0.05}
            format={(v) => v.toFixed(2)}
            onChange={(temperature) => onParamsChange({ ...params, temperature })}
          />
          <SliderRow
            label="Top-p"
            hint="Nucleus sampling — the model considers only the most likely tokens whose probabilities sum to this value."
            value={params.top_p}
            min={0}
            max={1}
            step={0.01}
            format={(v) => v.toFixed(2)}
            onChange={(top_p) => onParamsChange({ ...params, top_p })}
          />
          <SliderRow
            label="Top-k"
            hint="Limits sampling to the k most likely next tokens. Lower values keep output more predictable."
            value={params.top_k}
            min={1}
            max={100}
            step={1}
            onChange={(top_k) => onParamsChange({ ...params, top_k })}
          />
          <SliderRow
            label="Repetition penalty"
            hint="Discourages the model from repeating itself. Higher values reduce repeated phrases."
            value={params.repetition_penalty}
            min={1}
            max={2}
            step={0.05}
            format={(v) => v.toFixed(2)}
            onChange={(repetition_penalty) => onParamsChange({ ...params, repetition_penalty })}
          />
          <SliderRow
            label="Max tokens"
            hint="The maximum length of the model's reply, measured in tokens."
            value={params.max_tokens}
            min={16}
            max={4096}
            step={16}
            onChange={(max_tokens) => onParamsChange({ ...params, max_tokens })}
          />
          <div className="space-y-1.5">
            <div className="flex items-center gap-1.5">
              <Label htmlFor="system-prompt">System prompt</Label>
              <InfoHint text="Override the model's default behaviour with your own instructions." />
            </div>
            <Textarea
              id="system-prompt"
              value={params.system_prompt ?? ""}
              onChange={(event) =>
                onParamsChange({ ...params, system_prompt: event.target.value || null })
              }
              placeholder="You are a helpful assistant."
              rows={4}
            />
          </div>
        </>
      )}

      {modality === "image-gen" && (
        <>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label>Width</Label>
              <Select
                value={String(imageParams.width)}
                onValueChange={(value) =>
                  onImageParamsChange({ ...imageParams, width: Number(value) })
                }
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {DIMENSIONS.map((size) => (
                    <SelectItem key={size} value={String(size)}>
                      {size}px
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Height</Label>
              <Select
                value={String(imageParams.height)}
                onValueChange={(value) =>
                  onImageParamsChange({ ...imageParams, height: Number(value) })
                }
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {DIMENSIONS.map((size) => (
                    <SelectItem key={size} value={String(size)}>
                      {size}px
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <SliderRow
            label="Steps"
            hint="More denoising steps can improve quality but take longer to generate."
            value={imageParams.steps}
            min={1}
            max={100}
            step={1}
            onChange={(steps) => onImageParamsChange({ ...imageParams, steps })}
          />
          <SliderRow
            label="Guidance scale"
            hint="How closely the image should follow your prompt. Higher values stick to the prompt more strictly."
            value={imageParams.guidance_scale}
            min={0}
            max={20}
            step={0.5}
            format={(v) => v.toFixed(1)}
            onChange={(guidance_scale) => onImageParamsChange({ ...imageParams, guidance_scale })}
          />
          <SliderRow
            label="Images"
            hint="How many images to generate in one batch."
            value={imageParams.num_images}
            min={1}
            max={4}
            step={1}
            onChange={(num_images) => onImageParamsChange({ ...imageParams, num_images })}
          />
          <div className="space-y-1.5">
            <div className="flex items-center gap-1.5">
              <Label htmlFor="seed">Seed</Label>
              <InfoHint text="Leave blank for a random seed. Set a fixed number to reproduce the same image." />
            </div>
            <Input
              id="seed"
              type="number"
              value={imageParams.seed ?? ""}
              placeholder="Random"
              onChange={(event) =>
                onImageParamsChange({
                  ...imageParams,
                  seed: event.target.value === "" ? null : Number(event.target.value),
                })
              }
            />
          </div>
        </>
      )}
    </div>
  );

  return (
    <>
      <aside className="hidden w-72 shrink-0 border-l lg:block">{body}</aside>
      {open && (
        <>
          <button
            type="button"
            aria-label="Close settings"
            className="fixed inset-0 z-30 bg-black/60 lg:hidden"
            onClick={onClose}
          />
          <aside
            className={cn(
              "fixed inset-y-0 right-0 z-40 w-80 max-w-[85vw] border-l bg-card shadow-xl lg:hidden",
            )}
          >
            {body}
          </aside>
        </>
      )}
    </>
  );
}
