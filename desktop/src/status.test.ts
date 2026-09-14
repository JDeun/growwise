import { describe, expect, it } from "vitest";

import { modelReachabilityLabel, operationModeLabel } from "./status";

describe("desktop runtime status labels", () => {
  it("keeps Core-only mode explicit when AI is unavailable", () => {
    expect(operationModeLabel("core_only")).toBe("Core-only");
    expect(modelReachabilityLabel(true, false)).toBe("설정됨 · 현재 미도달");
  });

  it("describes configured and reachable AI without implying dependency", () => {
    expect(operationModeLabel("ai_enhanced_with_core_fallback")).toBe(
      "AI 보강 · Core fallback",
    );
    expect(modelReachabilityLabel(true, true)).toBe("모델 연결됨");
  });
});
