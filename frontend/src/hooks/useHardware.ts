import { useCallback, useEffect, useState } from "react";
import { getHardware } from "@/lib/api";
import type { HardwareInfo } from "@/lib/types";

export function useHardware() {
  const [hardware, setHardware] = useState<HardwareInfo | null>(null);

  const refresh = useCallback(() => {
    getHardware()
      .then(setHardware)
      .catch(() => {});
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { hardware, refresh };
}
