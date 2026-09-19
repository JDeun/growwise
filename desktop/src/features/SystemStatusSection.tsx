import { useState } from "react";

import {
  prepareLocalAi,
  type ChildProfile,
  type CoreRuntimeStatus,
  type HealthResponse,
} from "../api";

type ConnectionState =
  | { kind: "loading" }
  | { kind: "connected"; health: HealthResponse; runtime: CoreRuntimeStatus }
  | { kind: "offline"; message: string };

interface SystemStatusSectionProps {
  connection: ConnectionState;
  activeChild: ChildProfile | null;
  childrenCount: number;
  onRefresh?: () => void | Promise<void>;
}

type PreparingTarget = "basic" | "vision";

function availabilityLabel(value: boolean | null | undefined): string {
  if (value === true) return "준비됨";
  if (value === false) return "준비 필요";
  return "확인 안 됨";
}

export function SystemStatusSection({
  connection,
  activeChild,
  childrenCount,
  onRefresh,
}: SystemStatusSectionProps) {
  const [preparing, setPreparing] = useState<PreparingTarget | null>(null);
  const [setupNotice, setSetupNotice] = useState<string | null>(null);
  const [setupError, setSetupError] = useState<string | null>(null);

  const connected = connection.kind === "connected";
  const health = connected ? connection.health : null;
  const ollama = health?.model_provider.toLowerCase() === "ollama";
  const aiReady = Boolean(health?.llm_features_enabled);
  const basicModelsReady = Boolean(
    health?.llm_model_available === true
      && (health?.embedding_model_available === true || !health?.embedding_reachable),
  );
  const canPrepareBasic = Boolean(
    connected
      && ollama
      && health.llm_reachable
      && (!basicModelsReady || health.embedding_model_available === false),
  );
  const sharesMultimodalModel = Boolean(
    health?.llm_model_id
      && health?.vision_model_id
      && health.llm_model_id === health.vision_model_id,
  );
  const canPrepareVision = Boolean(
    connected
      && ollama
      && !sharesMultimodalModel
      && health.vision_reachable
      && health.vision_model_available === false,
  );

  let aiStatus = "확인 대기";
  let aiDescription = "앱이 준비되면 AI 보조 기능 상태를 확인합니다.";
  if (connected) {
    if (aiReady) {
      aiStatus = "사용 가능";
      aiDescription = "한 로컬 멀티모달 모델로 기록 정리, 검색, 자료 만들기와 사진 이해를 보조합니다.";
    } else if (ollama && health.llm_reachable && health.llm_model_available === false) {
      aiStatus = "모델 준비 필요";
      aiDescription = "로컬 AI는 실행 중입니다. 필요한 모델만 준비하면 바로 사용할 수 있습니다.";
    } else if (ollama && !health.llm_reachable) {
      aiStatus = "Ollama 준비 필요";
      aiDescription = "AI는 선택 기능입니다. Ollama를 설치·실행한 뒤 다시 확인해 주세요.";
    } else {
      aiStatus = "선택 기능 미사용";
      aiDescription = "AI 없이도 기록, 기본 검색, 활동과 자료 관리는 계속 사용할 수 있습니다.";
    }
  }

  async function handlePrepare(target: PreparingTarget) {
    setPreparing(target);
    setSetupNotice(null);
    setSetupError(null);
    try {
      const result = await prepareLocalAi(target);
      setSetupNotice(
        result === "already_ready"
          ? "이미 필요한 AI 모델이 준비되어 있습니다."
          : target === "basic"
            ? "기본 AI 준비를 마쳤습니다."
            : "사진 AI 준비를 마쳤습니다.",
      );
      await onRefresh?.();
    } catch (error) {
      setSetupError(
        error instanceof Error
          ? error.message
          : "AI 모델을 준비하지 못했습니다. Ollama 실행 상태를 확인해 주세요.",
      );
    } finally {
      setPreparing(null);
    }
  }

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
        <p className="status-title">{aiStatus}</p>
        <p className="muted">{aiDescription}</p>

        {canPrepareBasic && (
          <button
            className="quiet-button"
            type="button"
            disabled={preparing !== null}
            onClick={() => void handlePrepare("basic")}
          >
            {preparing === "basic" ? "기본 AI 준비 중…" : "기본 AI 준비"}
          </button>
        )}
        {canPrepareVision && (
          <button
            className="quiet-button"
            type="button"
            disabled={preparing !== null}
            onClick={() => void handlePrepare("vision")}
          >
            {preparing === "vision" ? "사진 AI 준비 중…" : "사진 AI 준비"}
          </button>
        )}
        {connected && ollama && !health.llm_reachable && onRefresh && (
          <button className="quiet-button" type="button" onClick={() => void onRefresh()}>
            상태 다시 확인
          </button>
        )}

        {preparing && (
          <p className="muted" role="status" aria-live="polite">
            처음 준비할 때는 모델 다운로드 때문에 시간이 걸릴 수 있습니다. 다른 화면은 계속 사용할 수 있습니다.
          </p>
        )}
        {setupNotice && <p className="muted" role="status">{setupNotice}</p>}
        {setupError && <p className="form-error" role="alert">{setupError}</p>}

        {connection.kind === "connected" && (
          <details className="technical-details">
            <summary>고급 진단 정보</summary>
            <dl>
              <div><dt>실행 방식</dt><dd>{connection.runtime.started_by_desktop ? "데스크톱에서 자동 시작" : "기존 로컬 서비스 사용"}</dd></div>
              <div><dt>동작 모드</dt><dd>{connection.health.operation_mode}</dd></div>
              <div><dt>AI 공급자</dt><dd>{connection.health.model_provider}</dd></div>
              <div><dt>텍스트 AI 연결</dt><dd>{connection.health.llm_reachable ? "연결됨" : "연결 안 됨"}</dd></div>
              <div><dt>텍스트 모델</dt><dd>{connection.health.llm_model_id ?? "미지정"} · {availabilityLabel(connection.health.llm_model_available)}</dd></div>
              <div><dt>검색 모델</dt><dd>{connection.health.embedding_model_id ?? "미지정"} · {availabilityLabel(connection.health.embedding_model_available)}</dd></div>
              <div><dt>사진 모델</dt><dd>{connection.health.vision_model_id ?? "미지정"} · {availabilityLabel(connection.health.vision_model_available)}</dd></div>
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
