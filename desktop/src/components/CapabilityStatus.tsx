import { useCallback, useEffect, useState } from "react";

import { getHealth, type HealthResponse } from "../api";
import { CapabilityBanner } from "./CapabilityBanner";

type CapabilityState =
  | { kind: "loading" }
  | { kind: "ready"; health: HealthResponse }
  | { kind: "offline" };

const REFRESH_INTERVAL_MS = 30_000;

export function CapabilityStatus() {
  const [state, setState] = useState<CapabilityState>({ kind: "loading" });

  const refresh = useCallback(async () => {
    try {
      const health = await getHealth();
      setState({ kind: "ready", health });
    } catch {
      setState({ kind: "offline" });
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), REFRESH_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [refresh]);

  if (state.kind === "loading") {
    return (
      <section className="capability-banner" role="status" aria-live="polite">
        <strong>GrowWise 상태를 확인하고 있습니다.</strong>
        <span>기록과 자료를 안전하게 불러올 준비를 하고 있습니다.</span>
      </section>
    );
  }

  if (state.kind === "offline") {
    return <CapabilityBanner connected={false} llmConfigured={false} llmReachable={false} />;
  }

  return (
    <CapabilityBanner
      connected
      llmConfigured={state.health.llm_configured}
      llmReachable={state.health.llm_reachable}
    />
  );
}
