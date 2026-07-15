import { useState } from "react";
import { Loader2, Search } from "lucide-react";
import { toast } from "sonner";
import { resolveModel } from "@/lib/api";
import type { ModelResolveResponse } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function ModelSearchBar({
  onResolved,
}: {
  onResolved: (resolved: ModelResolveResponse) => void;
}) {
  const [query, setQuery] = useState("");
  const [pending, setPending] = useState(false);

  const submit = async () => {
    const trimmed = query.trim();
    if (!trimmed || pending) return;
    setPending(true);
    try {
      onResolved(await resolveModel(trimmed));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not check that repository.");
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="flex gap-2">
      <Input
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter") void submit();
        }}
        placeholder='Paste any Hugging Face repo id, e.g. "Qwen/Qwen2.5-7B-Instruct-GGUF"'
        className="h-11 text-base"
        spellCheck={false}
      />
      <Button className="h-11 px-5" onClick={() => void submit()} disabled={pending || !query.trim()}>
        {pending ? <Loader2 className="animate-spin" /> : <Search />}
        <span className="hidden sm:inline">Check model</span>
      </Button>
    </div>
  );
}
