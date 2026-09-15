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
        <strong>GrowWise Core에 연결할 수 없습니다.</strong>
        <span>저장된 데이터는 변경하지 않습니다. 연결을 복구한 뒤 다시 시도해 주세요.</span>
      </section>
    );
  }

  if (!llmConfigured || !llmReachable) {
    return (
      <section className="capability-banner core-only" role="status" aria-live="polite">
        <strong>기본 기능 사용 가능</strong>
        <span>
          AI 보강은 현재 사용할 수 없지만 기록, 검색, 성장 맵, 활동, 자료 관리와 부모 검토는 계속 동작합니다.
        </span>
      </section>
    );
  }

  return (
    <section className="capability-banner enhanced" role="status" aria-live="polite">
      <strong>AI 보강 사용 가능</strong>
      <span>핵심 기능은 로컬 Core가 담당하며 AI는 검색·정리·생성을 선택적으로 보강합니다.</span>
    </section>
  );
}
