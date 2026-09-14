import { useCallback, useEffect, useState } from "react";

import { CoreApiError, getHealth, type HealthResponse } from "./api";

type ConnectionState =
  | { kind: "loading" }
  | { kind: "connected"; health: HealthResponse }
  | { kind: "offline"; message: string };

function App() {
  const [connection, setConnection] = useState<ConnectionState>({ kind: "loading" });

  const refresh = useCallback(async () => {
    setConnection({ kind: "loading" });
    try {
      const health = await getHealth();
      setConnection({ kind: "connected", health });
    } catch (error) {
      const message =
        error instanceof CoreApiError || error instanceof Error
          ? error.message
          : "GrowWise Core 상태를 확인할 수 없습니다.";
      setConnection({ kind: "offline", message });
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const isConnected = connection.kind === "connected";
  const mode = isConnected ? connection.health.operation_mode : null;

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark" aria-hidden="true">
            <span className="leaf leaf-left" />
            <span className="leaf leaf-right" />
            <span className="stem" />
          </div>
          <div>
            <strong>GrowWise</strong>
            <span>Personal Education OS</span>
          </div>
        </div>
        <button className="quiet-button" type="button" onClick={() => void refresh()}>
          상태 새로고침
        </button>
      </header>

      <section className="hero" aria-labelledby="home-title">
        <p className="eyebrow">LOCAL-FIRST · PARENT-LED</p>
        <h1 id="home-title">아이의 배움을 기록하고, 필요한 맥락을 연결합니다.</h1>
        <p className="hero-copy">
          GrowWise의 핵심 기록·검색·자료 관리는 AI 없이도 동작합니다. 로컬 모델이 준비되면
          정리, 검색 보강, 자료 생성을 선택적으로 더합니다.
        </p>
      </section>

      <section className="status-grid" aria-label="시스템 상태">
        <article className="status-card primary-card">
          <div className="card-heading">
            <span className={`status-dot ${isConnected ? "ok" : "warning"}`} />
            <h2>GrowWise Core</h2>
          </div>
          {connection.kind === "loading" && <p>로컬 코어 상태를 확인하고 있습니다.</p>}
          {connection.kind === "offline" && (
            <>
              <p className="status-title">연결되지 않음</p>
              <p className="muted">{connection.message}</p>
            </>
          )}
          {connection.kind === "connected" && (
            <>
              <p className="status-title">정상 연결</p>
              <p className="muted">Python/FastAPI core가 로컬에서 응답 중입니다.</p>
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
          <p className="muted">LLM 장애가 기록·검색·자료 관리의 중단으로 이어지지 않습니다.</p>
        </article>

        <article className="status-card">
          <p className="card-label">로컬 모델</p>
          <p className="status-title">
            {isConnected && connection.health.llm_features_enabled
              ? connection.health.model_provider
              : "선택 사항"}
          </p>
          <p className="muted">
            임베딩과 생성 기능은 선택적으로 활성화되며 deterministic path를 대체하지 않습니다.
          </p>
        </article>
      </section>

      <section className="workspace">
        <div className="section-heading">
          <div>
            <p className="eyebrow">WORKSPACE</p>
            <h2>첫 walking skeleton</h2>
          </div>
          <span className="badge">Pre-alpha</span>
        </div>
        <div className="workspace-grid">
          <article className="feature-card">
            <span className="feature-index">01</span>
            <h3>관찰 기록</h3>
            <p>원본 관찰을 보존하고 경험 축과 검색 메타데이터를 연결합니다.</p>
          </article>
          <article className="feature-card">
            <span className="feature-index">02</span>
            <h3>자료 지식베이스</h3>
            <p>책·교육과정·노트를 provenance와 함께 로컬에 축적합니다.</p>
          </article>
          <article className="feature-card">
            <span className="feature-index">03</span>
            <h3>성장 맥락</h3>
            <p>점수 대신 최근 경험의 반복과 관찰 범위를 질적으로 보여줍니다.</p>
          </article>
          <article className="feature-card">
            <span className="feature-index">04</span>
            <h3>자료 생성</h3>
            <p>템플릿 또는 LLM 보강으로 초안을 만들고 부모 검토 후 사용합니다.</p>
          </article>
        </div>
      </section>
    </main>
  );
}

export default App;
