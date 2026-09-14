export function operationModeLabel(mode: string): string {
  if (mode === "ai_enhanced_with_core_fallback") {
    return "AI 보강 · Core fallback";
  }
  if (mode === "core_only") {
    return "Core-only";
  }
  return mode;
}

export function modelReachabilityLabel(configured: boolean, reachable: boolean): string {
  if (!configured) {
    return "모델 미설정";
  }
  return reachable ? "모델 연결됨" : "설정됨 · 현재 미도달";
}
