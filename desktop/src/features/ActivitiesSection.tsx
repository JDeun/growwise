import { useState } from "react";

import type { ViewLoadState } from "../child-context-state";
import { EntityLinkPanel, ViewStateNotice } from "../components";
import {
  listActivityObservations,
  type ActivityPlan,
  type ActivityStatus,
  type InfantActivitySuggestions,
  type LearningLog,
} from "../api";
import { activityStatusLabel } from "../presentation";
import "./ActivitiesSection.css";

interface ActivitiesSectionProps {
  suggestions: InfantActivitySuggestions | null;
  suggestionsLoading: boolean;
  error: string | null;
  planBusy: boolean;
  plans: ActivityPlan[];
  loadState: ViewLoadState;
  onLoadSuggestions: () => void;
  onSaveActivity: (title: string) => void;
  onTransition: (activityId: string, status: ActivityStatus) => void;
  onRetryPlans: () => void;
}

type ObservationLookup =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "ready"; logs: LearningLog[] }
  | { kind: "error"; message: string };

const LIFECYCLE: Array<{
  key: "suggested" | "active" | "finished" | "observation";
  label: string;
  description: string;
}> = [
  { key: "suggested", label: "1. 선택", description: "후보 중 부모가 고른 활동만 저장" },
  { key: "active", label: "2. 진행", description: "시작한 활동을 현재 맥락으로 유지" },
  { key: "finished", label: "3. 마침", description: "완료 또는 건너뜀을 결과로 기록" },
  { key: "observation", label: "4. 관찰", description: "필요할 때 후속 관찰을 활동에 연결" },
];

function formatActivityTime(value: string | null): string | null {
  return value ? new Date(value).toLocaleString("ko-KR") : null;
}

export function ActivitiesSection({
  suggestions,
  suggestionsLoading,
  error,
  planBusy,
  plans,
  loadState,
  onLoadSuggestions,
  onSaveActivity,
  onTransition,
  onRetryPlans,
}: ActivitiesSectionProps) {
  const [observationLookups, setObservationLookups] = useState<Record<string, ObservationLookup>>({});

  const suggestedCount = plans.filter((plan) => plan.status === "suggested").length;
  const activeCount = plans.filter((plan) => plan.status === "active").length;
  const completedCount = plans.filter((plan) => plan.status === "completed").length;
  const skippedCount = plans.filter((plan) => plan.status === "skipped").length;

  async function loadLinkedObservations(activityId: string) {
    setObservationLookups((current) => ({ ...current, [activityId]: { kind: "loading" } }));
    try {
      const logs = await listActivityObservations(activityId);
      setObservationLookups((current) => ({
        ...current,
        [activityId]: { kind: "ready", logs },
      }));
    } catch (lookupError) {
      setObservationLookups((current) => ({
        ...current,
        [activityId]: {
          kind: "error",
          message:
            lookupError instanceof Error
              ? lookupError.message
              : "연결된 관찰을 불러오지 못했습니다.",
        },
      }));
    }
  }

  return (
    <>
      <section className="activity-section">
        <div className="activity-heading">
          <div>
            <p className="card-label">ACTIVITY INVITATIONS</p>
            <h3>다음 활동 후보</h3>
            <p className="muted">
              추천은 의무가 아닙니다. 부모가 선택한 후보만 활동 목록에 저장됩니다.
            </p>
          </div>
          <button
            className="quiet-button"
            type="button"
            onClick={onLoadSuggestions}
            disabled={suggestionsLoading}
          >
            {suggestionsLoading ? "불러오는 중…" : "활동 후보 보기"}
          </button>
        </div>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        {suggestions && (
          <div className="activity-grid">
            {suggestions.suggestions.map((suggestion) => (
              <article
                className="activity-card"
                key={`${suggestion.title}-${suggestion.description}`}
              >
                <h4>{suggestion.title}</h4>
                <p>{suggestion.description}</p>
                {suggestion.observation_cue && <small>{suggestion.observation_cue}</small>}
                <button
                  type="button"
                  className="quiet-button activity-save"
                  disabled={planBusy}
                  onClick={() => onSaveActivity(suggestion.title)}
                >
                  활동으로 저장
                </button>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="quest-section">
        <div className="activity-heading">
          <div>
            <p className="card-label">ACTIVITY LIFECYCLE</p>
            <h3>선택한 활동</h3>
            <p className="muted">
              활동은 과제가 아니라 관찰을 돕는 초대입니다. 완료와 건너뜀 모두 유효한 결과입니다.
            </p>
          </div>
          <span className="badge">
            {loadState.kind === "ready" ? `${plans.length}건` : "확인 중"}
          </span>
        </div>

        {loadState.kind === "ready" && plans.length > 0 && (
          <div className="activity-lifecycle" aria-label="활동 진행 흐름">
            {LIFECYCLE.map((step) => {
              const count =
                step.key === "suggested"
                  ? suggestedCount
                  : step.key === "active"
                    ? activeCount
                    : step.key === "finished"
                      ? completedCount + skippedCount
                      : null;
              return (
                <article key={step.key}>
                  <div>
                    <strong>{step.label}</strong>
                    {count !== null && <span>{count}건</span>}
                  </div>
                  <small>{step.description}</small>
                </article>
              );
            })}
          </div>
        )}

        {loadState.kind === "loading" && (
          <ViewStateNotice
            kind="loading"
            title="활동 목록을 불러오는 중입니다."
            description="저장한 활동 상태를 확인합니다."
          />
        )}
        {loadState.kind === "error" && (
          <ViewStateNotice
            kind="error"
            title="활동 목록을 불러오지 못했습니다."
            description={loadState.message}
            action={
              <button className="quiet-button" type="button" onClick={onRetryPlans}>
                다시 시도
              </button>
            }
          />
        )}
        {loadState.kind === "ready" && plans.length === 0 && (
          <ViewStateNotice
            kind="empty"
            title="저장한 활동이 없습니다."
            description="활동 후보에서 선택한 항목만 이 목록에 저장됩니다."
          />
        )}
        {loadState.kind === "ready" && plans.length > 0 && (
          <div className="activity-lifecycle-list">
            {plans.map((activity) => {
              const lookup = observationLookups[activity.id] ?? { kind: "idle" as const };
              const primaryTime =
                activity.status === "completed"
                  ? formatActivityTime(activity.completed_at)
                  : activity.status === "skipped"
                    ? formatActivityTime(activity.skipped_at)
                    : formatActivityTime(activity.started_at);

              return (
                <article className={`activity-lifecycle-card status-${activity.status}`} key={activity.id}>
                  <div className="activity-lifecycle-card-heading">
                    <div>
                      <strong>{activity.title}</strong>
                      {primaryTime && <small>{primaryTime}</small>}
                    </div>
                    <span className={`status-badge status-${activity.status}`}>
                      {activityStatusLabel(activity.status)}
                    </span>
                  </div>

                  {activity.parent_note && <p>{activity.parent_note}</p>}

                  <div className="activity-stage-track" aria-label={`${activity.title} 진행 상태`}>
                    <span className="done">선택</span>
                    <span
                      className={
                        ["active", "completed", "skipped", "archived"].includes(activity.status)
                          ? "done"
                          : ""
                      }
                    >
                      진행
                    </span>
                    <span
                      className={
                        ["completed", "skipped", "archived"].includes(activity.status) ? "done" : ""
                      }
                    >
                      마침
                    </span>
                    <span className={lookup.kind === "ready" && lookup.logs.length > 0 ? "done" : ""}>
                      관찰
                    </span>
                  </div>

                  <div className="review-actions">
                    {activity.status === "suggested" && (
                      <button
                        type="button"
                        className="primary-button"
                        disabled={planBusy}
                        onClick={() => onTransition(activity.id, "active")}
                      >
                        시작
                      </button>
                    )}
                    {activity.status === "active" && (
                      <button
                        type="button"
                        className="primary-button"
                        disabled={planBusy}
                        onClick={() => onTransition(activity.id, "completed")}
                      >
                        완료
                      </button>
                    )}
                    {(activity.status === "suggested" || activity.status === "active") && (
                      <button
                        type="button"
                        className="quiet-button"
                        disabled={planBusy}
                        onClick={() => onTransition(activity.id, "skipped")}
                      >
                        건너뜀
                      </button>
                    )}
                    {activity.status === "skipped" && (
                      <button
                        type="button"
                        className="quiet-button"
                        disabled={planBusy}
                        onClick={() => onTransition(activity.id, "active")}
                      >
                        다시 시작
                      </button>
                    )}
                    <button
                      type="button"
                      className="quiet-button"
                      disabled={lookup.kind === "loading"}
                      onClick={() => void loadLinkedObservations(activity.id)}
                    >
                      {lookup.kind === "loading" ? "관찰 확인 중…" : "연결 관찰 확인"}
                    </button>
                  </div>

                  <EntityLinkPanel
                    entityId={activity.id}
                    ownerChildId={activity.child_id}
                    label="다른 아이와 활동 연결"
                  />

                  <div className="activity-observation-link" role="status" aria-live="polite">
                    {lookup.kind === "idle" && (
                      <p>
                        후속 관찰은 관찰 작업공간에서 이 활동을 선택해 저장하면 자동으로 연결됩니다.
                      </p>
                    )}
                    {lookup.kind === "error" && (
                      <p className="form-error" role="alert">
                        {lookup.message}
                      </p>
                    )}
                    {lookup.kind === "ready" && lookup.logs.length === 0 && (
                      <p>
                        아직 연결된 후속 관찰이 없습니다. 활동을 평가하기보다 의미 있는 변화가 있을 때
                        기록해 주세요.
                      </p>
                    )}
                    {lookup.kind === "ready" && lookup.logs.length > 0 && (
                      <div>
                        <strong>연결된 관찰 {lookup.logs.length}건</strong>
                        <p>{lookup.logs[0].parent_observation}</p>
                        {lookup.logs[0].created_at && (
                          <small>{new Date(lookup.logs[0].created_at).toLocaleString("ko-KR")}</small>
                        )}
                      </div>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </section>
    </>
  );
}
