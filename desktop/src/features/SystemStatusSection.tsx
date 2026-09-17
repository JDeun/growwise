import type { ChildProfile, CoreRuntimeStatus, HealthResponse } from "../api";

type ConnectionState =
  | { kind: "loading" }
  | { kind: "connected"; health: HealthResponse; runtime: CoreRuntimeStatus }
  | { kind: "offline"; message: string };

interface SystemStatusSectionProps {
  connection: ConnectionState;
  activeChild: ChildProfile | null;
  childrenCount: number;
}

export function SystemStatusSection({
  connection,
  activeChild,
  childrenCount,
}: SystemStatusSectionProps) {
  const connected = connection.kind === "connected";
  const aiReady = connected && connection.health.llm_features_enabled;

  return (
    <section className="status-grid" aria-label="앱 상태">
      <article className="status-card primary-card">
        <div className="card-heading">
          <span className={`status-dot ${connected ? "ok" : "warning"}`} />
          <h2>앱 상태</h2>
        </div>
        {connection.kind === "loading" && <p>앱을 준비하고 있습니다.</p>}
        {connection.kind === "offline" && (
          <>
            <p className="status-title">연결을 확인해 주세요</p>
            <p className="muted">{connection.message}</p>
          </>
        )}
        {connection.kind === "connected" && (
          <>
            <p className="status-title">정상</p>
            <p className="muted">기록, 검색, 활동과 자료 관리를 사용할 수 있습니다.</p>
          </>
        )}
      </article>

      <article className="status-card">
        <p className="card-label">AI 보조 기능</p>
        <p className="status-title">
          {!connected ? "확인 대기" : aiReady ? "사용 가능" : "선택 기능 미사용"}
        </p>
        <p className="muted">
          {aiReady
            ? "필요할 때 기록 정리와 검색, 자료 만들기를 보조합니다."
            : "AI 없이도 필수 기록과 관리 기능은 그대로 사용할 수 있습니다."}
        </p>
        {connection.kind === "connected" && (
          <details className="technical-details">
            <summary>고급 진단 정보</summary>
            <dl>
              <div><dt>실행 방식</dt><dd>{connection.runtime.started_by_desktop ? "데스크톱에서 자동 시작" : "기존 로컬 서비스 사용"}</dd></div>
              <div><dt>동작 모드</dt><dd>{connection.health.operation_mode}</dd></div>
              <div><dt>AI 공급자</dt><dd>{connection.health.model_provider}</dd></div>
              <div><dt>AI 연결</dt><dd>{connection.health.llm_reachable ? "연결됨" : "연결 안 됨"}</dd></div>
            </dl>
          </details>
        )}
      </article>

      <article className="status-card">
        <p className="card-label">현재 아이</p>
        <p className="status-title">{activeChild?.nickname ?? "선택 안 됨"}</p>
        <p className="muted">저장된 아이 {childrenCount}명 · 아이별 기록을 분리해 표시합니다.</p>
      </article>
    </section>
  );
}
