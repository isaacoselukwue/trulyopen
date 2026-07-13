import { lazy, Suspense, useState } from "react";
import { FlaskConical, Loader2, ShieldCheck } from "lucide-react";
import { Toaster } from "sonner";
import { Badge } from "@/components/ui/badge";
import type { LocalModel } from "@/lib/types";

const DashboardView = lazy(() => import("@/views/DashboardView"));
const PlaygroundView = lazy(() => import("@/views/PlaygroundView"));

type AppState = { view: "dashboard" } | { view: "playground"; model: LocalModel };

export default function App() {
  const [state, setState] = useState<AppState>({ view: "dashboard" });

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-20 border-b bg-background/80 backdrop-blur">
        <div className="container mx-auto flex h-14 max-w-6xl items-center justify-between gap-3 px-4 sm:px-6">
          <div className="flex min-w-0 items-center gap-2.5">
            <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-linear-to-br from-violet-500 to-sky-500">
              <FlaskConical className="size-4 text-white" />
            </div>
            <span className="font-semibold">TrulyOpen</span>
            <span className="hidden truncate text-sm text-muted-foreground sm:block">
              Local AI Workbench
            </span>
          </div>
          <Badge variant="outline" className="shrink-0 gap-1.5">
            <ShieldCheck className="size-3.5 text-success" />
            <span className="hidden sm:inline">100% local · no accounts</span>
          </Badge>
        </div>
      </header>
      <main className="container mx-auto max-w-6xl px-4 py-6 sm:px-6">
        <Suspense
          fallback={
            <div className="flex justify-center py-20 text-muted-foreground">
              <Loader2 className="size-6 animate-spin" />
            </div>
          }
        >
          {state.view === "dashboard" ? (
            <DashboardView
              onOpenPlayground={(model) => setState({ view: "playground", model })}
            />
          ) : (
            <PlaygroundView
              model={state.model}
              onBack={() => setState({ view: "dashboard" })}
            />
          )}
        </Suspense>
      </main>
      <Toaster theme="dark" richColors position="bottom-right" />
    </div>
  );
}
