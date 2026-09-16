import { useEffect, useState, type FormEvent } from "react";

import type { ChildContextLoadState } from "../child-context-state";
import { ViewStateNotice } from "../components";
import { getHealth, type ChildProfile, type GrowthMap, type Stage } from "../api";
import { stageLabel } from "../presentation";
import "./ChildProfileSection.css";

type ModelOnboardingState =
  | { kind: "idle" }
  | { kind: "checking" }
  | { kind: "ready"; provider: string }
  | { kind: "optional"; provider: string; configured: boolean };

interface ChildProfileSectionProps {
  connected: boolean;
  children: ChildProfile[];
  activeChild: ChildProfile | null;
  childContext: ChildContextLoadState;
  growthMap: GrowthMap | null;
  activityCount: number;
  nickname: string;
  childStage: Stage;
  ageMonths: string;
  saving: boolean;
  error: string | null;
  onNicknameChange: (value: string) => void;
  onStageChange: (value: Stage) => void;
  onAgeMonthsChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onSelectChild: (childId: string) => void;
}

export function ChildProfileSection({
  connected,
  children,
  activeChild,
  childContext,
  growthMap,
  activityCount,
  nickname,
  childStage,
  ageMonths,
  saving,
  error,
  onNicknameChange,
  onStageChange,
  onAgeMonthsChange,
  onSubmit,
  onSelectChild,
}: ChildProfileSectionProps) {
  const firstRun = children.length === 0;
  const [modelOnboarding, setModelOnboarding] = useState<ModelOnboardingState>({ kind: "idle" });

  useEffect(() => {
    let cancelled = false;
    if (!firstRun || !connected) {
      setModelOnboarding({ kind: "idle" });
      return () => { cancelled = true; };
    }

    setModelOnboarding({ kind: "checking" });
    void getHealth()
      .then((health) => {
        if (cancelled) return;
        setModelOnboarding(
          health.llm_reachable
            ? { kind: "ready", provider: health.model_provider }
            : {
                kind: "optional",
                provider: health.model_provider,
                configured: health.llm_configured,
              },
        );
      })
      .catch(() => {
        if (!cancelled) {
          setModelOnboarding({ kind: "optional", provider: "ollama", configured: true });
        }
      });

    return () => { cancelled = true; };
  }, [connected, firstRun]);

  return (
    <>
      <div className="section-heading">
        <div>
          <p className="eyebrow">CHILD CONTEXT</p>
          <h2>{firstRun ? "처음 설정을 마치면 바로 기록을 시작할 수 있습니다." : "기존 기록을 이어서 사용합니다."}</h2>
        </div>
        <span className="badge">{firstRun ? "FIRST RUN" : "Pre-alpha"}</span>
      </div>

      {firstRun && (
        <section className="onboarding-panel" aria-label="GrowWise 첫 실행 설정">
          <div className="onboarding-heading">
            <div>
              <p className="card-label">2-MINUTE SETUP</p>
              <h3>필수 설정은 첫 아이 프로필 하나뿐입니다.</h3>
            </div>
            <span className="onboarding-optional-badge">AI 선택 사항</span>
          </div>
          <ol className="onboarding-steps">
            <li className={connected ? "is-complete" : "is-current"}>
              <span className="onboarding-step-number">1</span>
              <div>
                <strong>GrowWise Core 연결</strong>
                <p>{connected ? "로컬 Core가 준비됐습니다." : "Desktop이 로컬 Core 연결을 확인하고 있습니다."}</p>
              </div>
            </li>
            <li className={connected ? "is-current" : ""}>
              <span className="onboarding-step-number">2</span>
              <div>
                <strong>첫 아이 프로필 만들기</strong>
                <p>닉네임과 교육 단계만 있으면 됩니다. 월령은 선택입니다.</p>
              </div>
            </li>
            <li className={modelOnboarding.kind === "ready" ? "is-complete" : "is-optional"}>
              <span className="onboarding-step-number">3</span>
              <div>
                <strong>로컬 AI 보강 연결 · 선택</strong>
                {modelOnboarding.kind === "checking" ? (
                  <p>로컬 모델 런타임 상태를 확인하고 있습니다.</p>
                ) : modelOnboarding.kind === "ready" ? (
                  <p>{modelOnboarding.provider} 런타임이 연결돼 있어 AI 보강을 바로 사용할 수 있습니다.</p>
                ) : (
                  <>
                    <p>
                      {modelOnboarding.kind === "optional" && modelOnboarding.configured
                        ? `${modelOnboarding.provider} 설정은 준비돼 있지만 런타임이 아직 연결되지 않았습니다.`
                        : "로컬 AI를 설정하지 않아도 됩니다."}
                      {" "}기록·검색·성장 맵·활동·자료 관리는 Core-only로 계속 동작합니다.
                    </p>
                    <div className="onboarding-model-help" aria-label="기본 Ollama 설정 도움말">
                      <span>기본 로컬 모델을 쓰려면 Ollama를 실행하고 필요한 모델을 준비하세요.</span>
                      <code>ollama serve</code>
                      <code>ollama pull qwen3.5:9b</code>
                    </div>
                  </>
                )}
              </div>
            </li>
          </ol>
          <p className="onboarding-footnote muted">AI 단계는 건너뛰어도 첫 아이를 저장하는 즉시 GrowWise의 필수 기능을 사용할 수 있습니다.</p>
        </section>
      )}

      {children.length > 0 && (
        <div className="child-switcher">
          <label>
            <span>아이 선택</span>
            <select value={activeChild?.id ?? ""} onChange={(event) => onSelectChild(event.target.value)}>
              {children.map((child) => (
                <option key={child.id} value={child.id}>
                  {child.nickname} · {stageLabel(child.stage)} · {child.age_months ?? "-"}개월
                </option>
              ))}
            </select>
          </label>
          <p className="muted">마지막 선택을 기억하지만 데이터는 항상 Core에서 다시 조회합니다.</p>
        </div>
      )}

      <div className="skeleton-grid">
        <form className="profile-form" onSubmit={onSubmit}>
          <p className="card-label">{firstRun ? "FIRST CHILD" : "NEW CHILD"}</p>
          <label>
            <span>아이 닉네임</span>
            <input value={nickname} onChange={(event) => onNicknameChange(event.target.value)} placeholder="예: 샘플아이" maxLength={40} disabled={!connected || saving} />
          </label>
          <label>
            <span>교육 단계</span>
            <select value={childStage} onChange={(event) => onStageChange(event.target.value as Stage)} disabled={!connected || saving}>
              <option value="infant_0_2">영아 0~2세</option>
              <option value="preschool_3_5">유아 3~5세</option>
              <option value="elementary">초등</option>
              <option value="middle">중등</option>
              <option value="high">고등</option>
            </select>
          </label>
          <label>
            <span>월령(선택)</span>
            <input type="number" min="0" max="240" value={ageMonths} onChange={(event) => onAgeMonthsChange(event.target.value)} placeholder="예: 108" disabled={!connected || saving} />
          </label>
          <button className="primary-button" type="submit" disabled={!connected || saving}>
            {saving ? "저장 중…" : firstRun ? "첫 프로필 저장" : "새 프로필 저장"}
          </button>
          {error && <p className="form-error" role="alert">{error}</p>}
        </form>

        <article className="verification-card">
          {activeChild ? (
            <>
              <p className="card-label">ACTIVE CONTEXT</p>
              <h3>{activeChild.nickname}</h3>
              <p className="muted">프로필은 선택 즉시 유지하고, 각 기록 영역은 Core에서 독립적으로 다시 불러옵니다.</p>
              <dl className="verification-list">
                <div><dt>월령</dt><dd>{activeChild.age_months ?? "-"}개월</dd></div>
                <div><dt>최근 기록</dt><dd>{childContext.growth.kind === "ready" && growthMap ? growthMap.total_logs_in_period : "—"}</dd></div>
                <div><dt>활동</dt><dd>{childContext.activities.kind === "ready" ? activityCount : "—"}</dd></div>
              </dl>
            </>
          ) : (
            <>
              <p className="card-label">FIRST STEP</p>
              <h3>첫 아이 프로필을 만들어 주세요.</h3>
              <p className="muted">개인 식별정보 대신 앱 안에서 구분할 닉네임만 사용해도 됩니다.</p>
            </>
          )}
        </article>
      </div>

      {!activeChild && connected && !firstRun && (
        <section className="child-context-required">
          <ViewStateNotice
            kind="empty"
            title="먼저 아이 프로필을 만들어 주세요."
            description="관찰, 성장, 활동, 자료, 검색 작업공간은 선택한 아이의 기록 범위 안에서 동작합니다."
          />
        </section>
      )}
    </>
  );
}
