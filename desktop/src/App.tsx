import { FormEvent, useCallback, useEffect, useState } from "react";

import {
  CoreApiError,
  createChild,
  getCoreRuntimeStatus,
  getGrowthMap,
  getHealth,
  type ChildProfile,
  type CoreRuntimeStatus,
  type GrowthMap,
  type HealthResponse,
} from "./api";

type ConnectionState =
  | { kind: "loading" }
  | { kind: "connected"; health: HealthResponse; runtime: CoreRuntimeStatus }
  | { kind: "offline"; message: string };

function App() {
  const [connection, setConnection] = useState<ConnectionState>({ kind: "loading" });
  const [nickname, setNickname] = useState("");
  const [ageMonths, setAgeMonths] = useState("9");
  const [createdChild, setCreatedChild] = useState<ChildProfile | null>(null);
  const [growthMap, setGrowthMap] = useState<GrowthMap | null>(null);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setConnection({ kind: "loading" });
    try {
      const [health, runtime] = await Promise.all([getHealth(), getCoreRuntimeStatus()]);
      setConnection({ kind: "connected", health, runtime });
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

  async function handleCreateChild(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedNickname = nickname.trim();
    if (!trimmedNickname) {
      setFormError("아이를 구분할 닉네임을 입력해 주세요.");
      return;
    }

    const parsedAge = Number.parseInt(ageMonths, 10);
    if (!Number.isFinite(parsedAge) || parsedAge < 0 || parsedAge > 24) {
      setFormError("영아 모드 검증을 위해 월령은 0~24개월로 입력해 주세요.");
      return;
    }

    setSaving(true);
    setFormError(null);
    try {
      const child = await createChild({
        nickname: trimmedNickname,
        stage: "infant_0_2",
        age_months: parsedAge,
        interests: [],
      });
      const map = await getGrowthMap(child.id);
      setCreatedChild(child);
      setGrowthMap(map);
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "프로필 저장에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  }

  const isConnected = connection.kind === "connected";
  const mode = isConnected ? connection.health.operation_mode : null;

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand">
          <img className="brand-logo" src="/growwise-symbol.svg" alt="" aria-hidden="true" />
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
              <p className="muted">
                {connection.runtime.started_by_desktop
                  ? "Desktop이 Python Core를 자동 기동했습니다."
                  : "이미 실행 중인 Python Core에 연결했습니다."}
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
          <p className="muted">LLM 장애가 기록·검색·자료 관리의 중단으로 이어지지 않습니다.</p>
        </article>

        <article className="status-card">
          <p className="card-label">로컬 모델</p>
          <p className="status-title">
            {isConnected && connection.health.llm_features_enabled
              ? connection.health.model_provider
              : "선택 사항"}
          </p>
          <p className="muted">AI는 deterministic core를 보강하며 필수 런타임이 아닙니다.</p>
        </article>
      </section>

      <section className="workspace">
        <div className="section-heading">
          <div>
            <p className="eyebrow">WALKING SKELETON</p>
            <h2>프로필 저장 → 재조회 검증</h2>
          </div>
          <span className="badge">Pre-alpha</span>
        </div>

        <div className="skeleton-grid">
          <form className="profile-form" onSubmit={handleCreateChild}>
            <label>
              <span>아이 닉네임</span>
              <input
                value={nickname}
                onChange={(event) => setNickname(event.target.value)}
                placeholder="예: 수아"
                maxLength={40}
                disabled={!isConnected || saving}
              />
            </label>
            <label>
              <span>월령</span>
              <input
                type="number"
                min="0"
                max="24"
                value={ageMonths}
                onChange={(event) => setAgeMonths(event.target.value)}
                disabled={!isConnected || saving}
              />
            </label>
            <button className="primary-button" type="submit" disabled={!isConnected || saving}>
              {saving ? "저장 및 확인 중…" : "로컬에 프로필 저장"}
            </button>
            {formError && <p className="form-error">{formError}</p>}
          </form>

          <article className="verification-card" aria-live="polite">
            {createdChild && growthMap ? (
              <>
                <p className="card-label">ROUND TRIP VERIFIED</p>
                <h3>{createdChild.nickname}</h3>
                <p className="muted">
                  프로필 ID <code>{createdChild.id}</code>가 저장되었고, 같은 ID로 성장 맥락을
                  다시 조회했습니다.
                </p>
                <dl className="verification-list">
                  <div>
                    <dt>월령</dt>
                    <dd>{createdChild.age_months}개월</dd>
                  </div>
                  <div>
                    <dt>최근 기록</dt>
                    <dd>{growthMap.total_logs_in_period}건</dd>
                  </div>
                  <div>
                    <dt>조회 기간</dt>
                    <dd>{growthMap.period_days}일</dd>
                  </div>
                </dl>
              </>
            ) : (
              <>
                <p className="card-label">DATA PATH</p>
                <h3>아직 검증 전입니다.</h3>
                <p className="muted">
                  프로필을 저장하면 React → Tauri IPC → FastAPI → Markdown/SQLite → FastAPI →
                  Tauri IPC → React 경로를 확인합니다.
                </p>
              </>
            )}
          </article>
        </div>
      </section>
    </main>
  );
}

export default App;
