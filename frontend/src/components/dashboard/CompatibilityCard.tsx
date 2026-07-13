import { useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, Download, XCircle } from "lucide-react";
import { formatBytes } from "@/lib/format";
import type { ModelResolveResponse } from "@/lib/types";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
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
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export function CompatibilityCard({
  resolved,
  onStartDownload,
}: {
  resolved: ModelResolveResponse;
  onStartDownload: (repoId: string, files?: string[]) => void;
}) {
  const ggufOptions = resolved.gguf_options ?? [];
  const defaultQuant = useMemo(
    () =>
      ggufOptions.length > 0
        ? ggufOptions.reduce((a, b) => (a.size_bytes <= b.size_bytes ? a : b)).path
        : null,
    [ggufOptions],
  );
  const [quant, setQuant] = useState<string | null>(defaultQuant);
  const selectedQuant = quant ?? defaultQuant;
  const { compatibility } = resolved;
  const runnable = resolved.format !== "unknown";

  return (
    <Card>
      <CardHeader>
        <CardTitle className="break-all">{resolved.name}</CardTitle>
        <CardDescription className="break-all">
          {resolved.author ? `${resolved.author} · ` : ""}
          {resolved.repo_id}
        </CardDescription>
        {resolved.format === "peft" && resolved.base_model && (
          <CardDescription className="break-all">
            LoRA adapter — needs base model {resolved.base_model}
          </CardDescription>
        )}
        <div className="flex flex-wrap gap-1.5 pt-1">
          {resolved.pipeline_tag && <Badge variant="secondary">{resolved.pipeline_tag}</Badge>}
          <Badge variant="secondary">{resolved.modality}</Badge>
          <Badge variant="outline">{resolved.format}</Badge>
          <Badge variant="outline">
            {formatBytes(resolved.download_size_bytes)} · {resolved.files.length} files
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {ggufOptions.length > 0 && (
          <div className="space-y-1.5">
            <Label>Quantisation</Label>
            <Select value={selectedQuant ?? undefined} onValueChange={setQuant}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Choose a GGUF file" />
              </SelectTrigger>
              <SelectContent>
                {ggufOptions.map((file) => (
                  <SelectItem key={file.path} value={file.path}>
                    {file.path.split("/").pop()} · {formatBytes(file.size_bytes)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}
        {!runnable && (
          <Alert variant="destructive">
            <XCircle />
            <AlertTitle>TrulyOpen cannot run this model</AlertTitle>
            <AlertDescription>
              {compatibility.messages.map((message) => (
                <p key={message}>{message}</p>
              ))}
            </AlertDescription>
          </Alert>
        )}
        {runnable && compatibility.level === "ok" && (
          <div className="space-y-2">
            <Badge variant="success">
              <CheckCircle2 />
              Compatible
            </Badge>
            <ul className="space-y-1 text-sm text-muted-foreground">
              {compatibility.messages.map((message) => (
                <li key={message}>{message}</li>
              ))}
            </ul>
          </div>
        )}
        {runnable && compatibility.level === "warning" && (
          <Alert variant="warning">
            <AlertTriangle />
            <AlertTitle>May run slowly</AlertTitle>
            <AlertDescription>
              {compatibility.messages.map((message) => (
                <p key={message}>{message}</p>
              ))}
            </AlertDescription>
          </Alert>
        )}
        {runnable && compatibility.level === "insufficient" && (
          <Alert variant="destructive">
            <XCircle />
            <AlertTitle>Not enough resources</AlertTitle>
            <AlertDescription>
              {compatibility.messages.map((message) => (
                <p key={message}>{message}</p>
              ))}
            </AlertDescription>
          </Alert>
        )}
      </CardContent>
      <CardFooter>
        <Button
          disabled={!runnable || !compatibility.disk_ok}
          onClick={() =>
            onStartDownload(
              resolved.repo_id,
              ggufOptions.length > 0 && selectedQuant ? [selectedQuant] : undefined,
            )
          }
        >
          <Download />
          {runnable ? "Download model" : "Cannot run this format"}
        </Button>
      </CardFooter>
    </Card>
  );
}
