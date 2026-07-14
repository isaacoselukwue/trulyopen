import { useEffect, useRef, useState } from "react";
import { Eraser, ImagePlus, Send, Square, X } from "lucide-react";
import type { GenerationParams, LocalModel } from "@/lib/types";
import { useChatStream } from "@/hooks/useChatStream";
import { Markdown } from "@/components/playground/Markdown";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

export function ChatPanel({ model, params }: { model: LocalModel; params: GenerationParams }) {
  const { messages, streaming, send, stop, clear } = useChatStream();
  const [draft, setDraft] = useState("");
  const [attachments, setAttachments] = useState<string[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const isVision = model.modality === "vision-chat";

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 160;
    if (nearBottom) el.scrollTop = el.scrollHeight;
  }, [messages]);

  const submit = () => {
    if (streaming) return;
    send(draft, attachments, model, params);
    setDraft("");
    setAttachments([]);
  };

  const attachFiles = (files: FileList | null) => {
    if (!files) return;
    for (const file of Array.from(files)) {
      const reader = new FileReader();
      reader.onload = () => {
        if (typeof reader.result === "string") {
          setAttachments((prev) => [...prev, reader.result as string]);
        }
      };
      reader.readAsDataURL(file);
    }
  };

  return (
    <div className="flex h-full min-w-0 flex-1 flex-col">
      <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto p-4">
        {messages.length === 0 && (
          <div className="flex h-full items-center justify-center">
            <div className="text-center text-muted-foreground">
              <p className="font-medium text-foreground">{model.name}</p>
              <p className="text-sm">Send a message to begin.</p>
            </div>
          </div>
        )}
        {messages.map((message, index) => (
          <div key={index} className={message.role === "user" ? "flex justify-end" : ""}>
            {message.role === "user" ? (
              <div className="max-w-[85%] space-y-2 rounded-2xl bg-primary px-4 py-2.5 text-primary-foreground">
                {message.images && message.images.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {message.images.map((image, imageIndex) => (
                      <img
                        key={imageIndex}
                        src={image}
                        alt="Attached"
                        className="h-20 rounded-lg object-cover"
                      />
                    ))}
                  </div>
                )}
                <p className="whitespace-pre-wrap text-sm">{message.content}</p>
              </div>
            ) : (
              <div className="max-w-full">
                {message.content === "" && streaming && index === messages.length - 1 ? (
                  <span className="inline-block size-2.5 animate-pulse rounded-full bg-foreground/60" />
                ) : (
                  <Markdown content={message.content} />
                )}
              </div>
            )}
          </div>
        ))}
      </div>
      <div className="border-t p-3">
        {attachments.length > 0 && (
          <div className="mb-2 flex flex-wrap gap-2">
            {attachments.map((image, index) => (
              <div key={index} className="relative">
                <img src={image} alt="Preview" className="h-16 rounded-lg object-cover" />
                <button
                  type="button"
                  aria-label="Remove image"
                  className="absolute -right-1.5 -top-1.5 rounded-full border bg-background p-0.5"
                  onClick={() => setAttachments((prev) => prev.filter((_, i) => i !== index))}
                >
                  <X className="size-3" />
                </button>
              </div>
            ))}
          </div>
        )}
        <div className="flex items-end gap-2">
          {isVision && (
            <>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                multiple
                className="hidden"
                onChange={(event) => {
                  attachFiles(event.target.files);
                  event.target.value = "";
                }}
              />
              <Button
                variant="outline"
                size="icon"
                aria-label="Attach image"
                onClick={() => fileInputRef.current?.click()}
              >
                <ImagePlus />
              </Button>
            </>
          )}
          <Textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                submit();
              }
            }}
            placeholder={`Message ${model.name}…`}
            rows={1}
            className="max-h-40 min-h-9 flex-1 resize-none text-base"
          />
          {streaming ? (
            <Button variant="outline" size="icon" aria-label="Stop" onClick={stop}>
              <Square />
            </Button>
          ) : (
            <Button
              size="icon"
              aria-label="Send"
              onClick={submit}
              disabled={!draft.trim() && attachments.length === 0}
            >
              <Send />
            </Button>
          )}
          <Button
            variant="ghost"
            size="icon"
            aria-label="Clear conversation"
            onClick={clear}
            disabled={messages.length === 0 || streaming}
          >
            <Eraser />
          </Button>
        </div>
      </div>
    </div>
  );
}
