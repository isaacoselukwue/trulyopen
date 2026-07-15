import { useState } from "react";
import { Download, Loader2, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { generateImage } from "@/lib/api";
import { formatDuration } from "@/lib/format";
import type { GeneratedImage, ImageParams, LocalModel } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";

interface GalleryItem extends GeneratedImage {
  key: string;
  prompt: string;
}

export function ImageStudio({ model, dims }: { model: LocalModel; dims: ImageParams }) {
  const [prompt, setPrompt] = useState("");
  const [negativePrompt, setNegativePrompt] = useState("");
  const [pending, setPending] = useState(false);
  const [duration, setDuration] = useState<number | null>(null);
  const [gallery, setGallery] = useState<GalleryItem[]>([]);

  const generate = async () => {
    if (!prompt.trim() || pending) return;
    setPending(true);
    setDuration(null);
    try {
      const response = await generateImage({
        model_id: model.id,
        prompt: prompt.trim(),
        negative_prompt: negativePrompt.trim() || null,
        ...dims,
      });
      setDuration(response.duration_seconds);
      const items = response.images.map((image, index) => ({
        ...image,
        key: `${image.seed}-${index}-${response.duration_seconds}`,
        prompt: prompt.trim(),
      }));
      setGallery((prev) => [...items, ...prev]);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Image generation failed.");
    } finally {
      setPending(false);
    }
  };

  const aspect = dims.width / dims.height;

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto p-4">
      <div className="space-y-3">
        <div className="space-y-1.5">
          <Label htmlFor="prompt">Prompt</Label>
          <Textarea
            id="prompt"
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            placeholder="A serene mountain lake at sunrise, photorealistic, golden hour"
            rows={3}
            className="text-base"
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="negative-prompt">Negative prompt</Label>
          <Textarea
            id="negative-prompt"
            value={negativePrompt}
            onChange={(event) => setNegativePrompt(event.target.value)}
            placeholder="blurry, low quality, distorted"
            rows={2}
            className="text-base"
          />
        </div>
        <div className="flex items-center gap-3">
          <Button onClick={() => void generate()} disabled={pending || !prompt.trim()}>
            {pending ? <Loader2 className="animate-spin" /> : <Sparkles />}
            Generate
          </Button>
          {duration !== null && (
            <span className="text-sm text-muted-foreground">
              Generated in {formatDuration(duration)}
            </span>
          )}
        </div>
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {pending &&
          Array.from({ length: dims.num_images }, (_, index) => (
            <Skeleton key={`pending-${index}`} className="w-full" style={{ aspectRatio: aspect }} />
          ))}
        {gallery.map((item) => (
          <figure key={item.key} className="group relative overflow-hidden rounded-lg border">
            <img
              src={`data:image/png;base64,${item.b64_png}`}
              alt={item.prompt}
              className="w-full object-cover"
            />
            <figcaption className="absolute inset-x-0 bottom-0 flex items-center justify-between gap-2 bg-black/60 px-3 py-1.5 text-xs text-white opacity-0 transition-opacity group-hover:opacity-100">
              <span>seed {item.seed}</span>
              <a
                href={`data:image/png;base64,${item.b64_png}`}
                download={`trulyopen-${item.seed}.png`}
                className="inline-flex items-center gap-1 hover:underline"
              >
                <Download className="size-3.5" />
                Save
              </a>
            </figcaption>
          </figure>
        ))}
      </div>
      {!pending && gallery.length === 0 && (
        <div className="flex flex-1 items-center justify-center text-center text-sm text-muted-foreground">
          <p>Describe an image and press Generate to create it locally.</p>
        </div>
      )}
    </div>
  );
}
