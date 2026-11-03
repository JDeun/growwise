import type { GeneratedMaterial } from "./api";

export function materialAiPending(material: Pick<GeneratedMaterial, "ai_status">): boolean {
  return material.ai_status === "queued" || material.ai_status === "running";
}

export function materialAiCompletionNotice(materials: GeneratedMaterial[]): string {
  const enhanced = materials.filter((material) => material.generator_mode === "llm_enhanced");
  if (enhanced.length === materials.length) return "AI 학습 자료가 준비됐습니다. 내용을 확인해 주세요.";
  if (enhanced.length > 0) return "AI 학습 자료가 준비됐습니다. 일부 자료는 기본 템플릿을 유지했습니다.";
  return "AI 결과가 적용되지 않아 기본 템플릿을 유지했습니다. 자료 내용을 확인해 주세요.";
}

export function startMaterialAiPolling({
  childId,
  pendingIds,
  inFlight,
  isCurrent,
  load,
  onUpdate,
  onFinished,
}: {
  childId: string;
  pendingIds: string[];
  inFlight: { current: boolean };
  isCurrent: () => boolean;
  load: (childId: string) => Promise<GeneratedMaterial[]>;
  onUpdate: (materials: GeneratedMaterial[]) => void;
  onFinished: (materials: GeneratedMaterial[]) => void;
}): () => void {
  const waiting = new Set(pendingIds);
  let cancelled = false;
  let timer: ReturnType<typeof setTimeout>;
  const schedule = () => { timer = setTimeout(() => { void poll(); }, 1500); };

  async function poll() {
    if (cancelled || !isCurrent()) return;
    if (inFlight.current) { schedule(); return; }
    inFlight.current = true;
    let pending = true;
    try {
      const materials = await load(childId);
      if (cancelled || !isCurrent()) return;
      const finished = materials.filter((material) =>
        waiting.has(material.id) && !materialAiPending(material),
      );
      for (const material of finished) waiting.delete(material.id);
      onUpdate(materials);
      if (finished.length > 0) onFinished(finished);
      pending = materials.some(materialAiPending);
    } catch {
      // Preserve the visible draft and retry transient status failures without overlapping requests.
    } finally {
      inFlight.current = false;
    }
    if (pending && !cancelled && isCurrent()) schedule();
  }

  if (waiting.size > 0) schedule();
  return () => { cancelled = true; clearTimeout(timer); };
}
