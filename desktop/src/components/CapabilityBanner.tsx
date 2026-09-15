import "./CapabilityBanner.css";

interface CapabilityBannerProps {
  connected: boolean;
  llmConfigured: boolean;
  llmReachable: boolean;
}

export function CapabilityBanner({
  connected,
  llmConfigured,
  llmReachable,
}: CapabilityBannerProps) {
  if (!connected) {
    return (
      <section className="capability-banner danger" role="status" aria-live="polite">
        <strong>GrowWise 연결을 확인해 주세요.</strong>
        <span>저장된 데이터는 그대로 유지됩니다. 연결이 복구되면 다시 사용할 수 있습니다.</span>
      </section>
    );
  }

  if (!llmConfigured || !llmReachable) {
    return (
      <section className="capability-banner core-only" role="status" aria-live="polite">
        <strong>기본 기능은 정상적으로 사용할 수 있습니다.</strong>
        <span>
          AI 보강은 현재 사용할 수 없지만 기록, 검색, 성장 맵, 활동, 자료 관리와 부모 검토는 계속 동작합니다.
        </span>
      </section>
    );
  }

  return (
    <section className="capability-banner enhanced" role="status" aria-live="polite">
      <strong>AI 보강을 사용할 수 있습니다.</strong>
      <span>기록과 자료 관리는 AI 없이도 동작하며, AI는 검색·정리·생성을 선택적으로 보강합니다.</span>
    </section>
  );
}
