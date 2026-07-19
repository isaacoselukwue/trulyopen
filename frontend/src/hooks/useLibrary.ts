import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import {
  deleteModel as apiDeleteModel,
  getLoaded,
  listLibrary,
  loadModel as apiLoadModel,
  unloadModel as apiUnloadModel,
} from "@/lib/api";
import { formatBytes } from "@/lib/format";
import type { LoadedModelInfo, LocalModel } from "@/lib/types";

export function useLibrary() {
  const [models, setModels] = useState<LocalModel[]>([]);
  const [loaded, setLoaded] = useState<LoadedModelInfo | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [libraryModels, loadedInfo] = await Promise.all([listLibrary(), getLoaded()]);
      setModels(libraryModels);
      setLoaded(loadedInfo);
    } catch {
      return;
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const deleteModel = useCallback(
    async (model: LocalModel) => {
      try {
        const result = await apiDeleteModel(model.id);
        toast.success(`Deleted ${model.name}`, {
          description: `Freed ${formatBytes(result.freed_bytes)} of disk space.`,
        });
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Could not delete the model.");
      } finally {
        void refresh();
      }
    },
    [refresh],
  );

  const loadModel = useCallback(
    async (model: LocalModel) => {
      try {
        const info = await apiLoadModel(model.id);
        setLoaded(info);
        toast.success(`Loaded ${model.name}`, {
          description: info.device ? `Running on ${info.device}.` : undefined,
        });
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Could not load the model.");
      } finally {
        void refresh();
      }
    },
    [refresh],
  );

  const unloadModel = useCallback(async () => {
    try {
      await apiUnloadModel();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not unload the model.");
    } finally {
      void refresh();
    }
  }, [refresh]);

  return { models, loaded, refresh, deleteModel, loadModel, unloadModel };
}
