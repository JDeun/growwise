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
  const mode = connected ? connection.health.operation_mode : null;

  return (
    <section className="status-grid" aria-label="시스템 상태">
      <article className="status-card primary-card">
        <div className="card-heading">
          <span className={`status-dot ${connected ? "ok" : "warning"}`} />
          <h2>GrowWise Core</h2>
        </div>
        {connection.kind === "loading" && <p>확인 중입니다.</p>}
        {connection.kind === "offline" && <p className="muted">{connection.message}</p>}
        {connection.kind === "connected" && (
          <>
            <p className="status-title">정상 연결</p>
            <p className="muted">
              {connection.runtime.started_by_desktop
                ? "Desktop이 Core를 자동 기동했습니다."
                : "실행 중인 Core에 연결했습니다."}
            </p>
          </>
        )}
      </article>
      <article className="status-card">
        <p className="card-label">운영 모드</p>
        <p className="status-title">
          {mode === "ai_enhanced_with_core_fallback"
            ? "AI 보강 + Core fallback"
            : mode === "core_only"
              ? "Core-only"
              : "확인 대기"}
        </p>
        {connection.kind === "connected" && (
          <p className="muted">
            {connection.health.llm_configured
              ? connection.health.llm_reachable
                ? `${connection.health.model_provider} 연결됨`
                : `${connection.health.model_provider} 설정됨 · 현재 미도달`
              : "LLM 기능 꺼짐"}
          </p>
        )}
      </article>
      <article className="status-card">
        <p className="card-label">현재 아이</p>
        <p className="status-title">{activeChild?.nickname ?? "선택 안 됨"}</p>
        <p className="muted">저장된 아이 {childrenCount}명 · child scope를 엄격히 분리합니다.</p>
      </article>
    </section>
  );
}
