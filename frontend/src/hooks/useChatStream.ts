import { useCallback, useRef, useState } from "react";
import { toast } from "sonner";
import { streamChat } from "@/lib/api";
import type { ChatMessage, GenerationParams, LocalModel } from "@/lib/types";

export function useChatStream() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [streaming, setStreaming] = useState(false);
  const messagesRef = useRef<ChatMessage[]>([]);
  const abortRef = useRef<AbortController | null>(null);

  const setAll = useCallback((next: ChatMessage[]) => {
    messagesRef.current = next;
    setMessages(next);
  }, []);

  const appendToAssistant = useCallback((token: string) => {
    const next = [...messagesRef.current];
    const last = next[next.length - 1];
    if (last && last.role === "assistant") {
      next[next.length - 1] = { ...last, content: last.content + token };
      messagesRef.current = next;
      setMessages(next);
    }
  }, []);

  const dropEmptyAssistant = useCallback(() => {
    const next = [...messagesRef.current];
    const last = next[next.length - 1];
    if (last && last.role === "assistant" && last.content === "") {
      next.pop();
      messagesRef.current = next;
      setMessages(next);
    }
  }, []);

  const send = useCallback(
    (content: string, images: string[], model: LocalModel, params: GenerationParams) => {
      if (streaming || (!content.trim() && images.length === 0)) return;
      const userMessage: ChatMessage = {
        role: "user",
        content,
        images: images.length > 0 ? images : null,
      };
      const history = [...messagesRef.current, userMessage];
      setAll([...history, { role: "assistant", content: "" }]);
      setStreaming(true);
      const controller = new AbortController();
      abortRef.current = controller;
      void streamChat(
        { model_id: model.id, messages: history, params },
        {
          onToken: appendToAssistant,
          onDone: () => undefined,
          onError: (message) => {
            toast.error(message);
          },
        },
        controller.signal,
      ).finally(() => {
        setStreaming(false);
        abortRef.current = null;
        dropEmptyAssistant();
      });
    },
    [streaming, setAll, appendToAssistant, dropEmptyAssistant],
  );

  const stop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const clear = useCallback(() => {
    setAll([]);
  }, [setAll]);

  return { messages, streaming, send, stop, clear };
}
