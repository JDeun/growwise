import { useEffect, useMemo, useState } from "react";

import type { ViewLoadState } from "../child-context-state";
import { EntityLinkPanel, ViewStateNotice } from "../components";
import {
  listActivityObservations,
  type ActivityPlan,
  type ActivityStatus,
  type InfantActivitySuggestions,
  type LearningLog,
} from "../api";
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
  | { kind: "loading" }
  | { kind: "ready"; logs: LearningLog[] }
  | { kind: "error"; message: string };

type QuestFilter = "all" | "generated" | "active" | "completed" | "result" | "skipped";

const QUEST_STATUS_LABEL: Record<ActivityStatus, string> = {
  suggested: "생성됨",
  active: "진행 중",
  completed: "완료됨",
  skipped: "건너뜀",
  archived: "보관됨",
};

const QUEST_FILTERS: Array<{ value: QuestFilter; label: string }> = [
  { value: "all", label: "전체" },
  { value: "generated", label: "생성됨" },
  { value: "active", label: "진행 중" },
  { value: "completed", label: "완료됨" },
  { value: "result", label: "결과 기록됨" },
  { value: "skipped", label: "건너뜀" },
];

function formatActivityTime(value: string | null): string | null {
  return value ? new Date(value).toLocaleString("ko-KR") : null;
}

function questRank(status: ActivityStatus): number {
  return {
    active: 0,
    suggested: 1,
    completed: 2,
    skipped: 3,
    archived: 4,
  }[status];
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
  const [filter, setFilter] = useState<QuestFilter>("all");
  const [observationLookups, setObservationLookups] = useState<Record<string, ObservationLookup>>({});

  useEffect(() => {
    if (loadState.kind !== "ready" || plans.length === 0) {
      setObservationLookups({});
      return;
    }

    let active = true;
    setObservationLookups(
      Object.fromEntries(plans.map((plan) => [plan.id, { kind: "loading" as const }])),
    );

    void Promise.all(
      plans.map(async (plan) => {
        try {
          const logs = await listActivityObservations(plan.id);
          return [plan.id, { kind: "ready" as const, logs }] as const;
        } catch (lookupError) {
          return [
            plan.id,
            {
              kind: "error" as const,
              message:
                lookupError instanceof Error
                  ? lookupError.message
                  : "연결된 결과 기록을 불러오지 못했습니다.",
            },
          ] as const;
        }
      }),
    ).then((entries) => {
      if (!active) return;
      setObservationLookups(Object.fromEntries(entries));
    });

    return () => {
      active = false;
    };
  }, [loadState.kind, plans]);

  const resultCountFor = (activityId: string) => {
    const lookup = observationLookups[activityId];
    return lookup?.kind === "ready" ? lookup.logs.length : 0;
  };

  const counts = useMemo(() => {
    const generated = plans.filter((plan) => plan.status === "suggested").length;
    const active = plans.filter((plan) => plan.status === "active").length;
    const completed = plans.filter((plan) => plan.status === "completed").length;
    const skipped = plans.filter((plan) => plan.status === "skipped").length;
    const result = plans.filter((plan) => resultCountFor(plan.id) > 0).length;
    return { generated, active, completed, skipped, result };
  }, [observationLookups, plans]);

  const filteredPlans = useMemo(() => {
    return [...plans]
      .filter((plan) => {
        if (filter === "all") return plan.status !== "archived";
        if (filter === "generated") return plan.status === "suggested";
        if (filter === "active") return plan.status === "active";
        if (filter === "completed") return plan.status === "completed";
        if (filter === "skipped") return plan.status === "skipped";
        return resultCountFor(plan.id) > 0;
      })
      .sort((left, right) => {
        const statusDiff = questRank(left.status) - questRank(right.status);
        if (statusDiff !== 0) return statusDiff;
        return String(right.updated_at ?? right.created_at ?? "").localeCompare(
          String(left.updated_at ?? left.created_at ?? ""),
        );
      });
  }, [filter, observationLookups, plans]);

  return (
    <>
      <section className="activity-section">
        <div className="activity-heading">
          <div>
            <p className="card-label">NEW QUESTS</p>
            <h3>새 활동 후보</h3>
            <p className="muted">
              추천은 자동 과제가 아닙니다. 부모가 선택한 후보만 퀘스트 보드에 추가됩니다.
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
                  퀘스트로 저장
                </button>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="quest-section">
        <div className="activity-heading">
          <div>
            <p className="card-label">QUEST BOARD</p>
            <h3>활동 퀘스트</h3>
            <p className="muted">
              생성한 자료와 선택한 활동을 상태별로 관리합니다. 완료 여부와 실제 결과 기록은 별도로
              표시됩니다.
            </p>
          </div>
          <span className="badge">
            {loadState.kind === "ready" ? `${plans.filter((plan) => plan.status !== "archived").length}건` : "확인 중"}
          </span>
        </div>

        {loadState.kind === "ready" && plans.length > 0 && (
          <>
            <div className="activity-lifecycle" aria-label="퀘스트 현황">
              <article>
                <div><strong>생성됨</strong><span>{counts.generated}</span></div>
                <small>아직 시작하지 않은 퀘스트</small>
              </article>
              <article>
                <div><strong>진행 중</strong><span>{counts.active}</span></div>
                <small>현재 수행 중인 퀘스트</small>
              </article>
              <article>
                <div><strong>완료됨</strong><span>{counts.completed}</span></div>
                <small>활동 상태가 완료된 퀘스트</small>
              </article>
              <article>
                <div><strong>결과 기록됨</strong><span>{counts.result}</span></div>
                <small>관찰 데이터까지 회수된 퀘스트</small>
              </article>
            </div>

            <div className="quest-filters" aria-label="퀘스트 필터">
              {QUEST_FILTERS.map((item) => (
                <button
                  key={item.value}
                  type="button"
                  className={`quest-filter ${filter === item.value ? "active" : ""}`}
                  aria-pressed={filter === item.value}
                  onClick={() => setFilter(item.value)}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </>
        )}

        {loadState.kind === "loading" && (
          <ViewStateNotice
            kind="loading"
            title="퀘스트 목록을 불러오는 중입니다."
            description="저장한 활동 상태와 결과 기록을 확인합니다."
          />
        )}
        {loadState.kind === "error" && (
          <ViewStateNotice
            kind="error"
            title="퀘스트 목록을 불러오지 못했습니다."
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
            title="아직 퀘스트가 없습니다."
            description="활동 후보를 저장하거나 승인된 생성 자료로 활동을 시작하면 이곳에서 관리합니다."
          />
        )}
        {loadState.kind === "ready" && plans.length > 0 && filteredPlans.length === 0 && (
          <ViewStateNotice
            kind="empty"
            title="이 상태의 퀘스트가 없습니다."
            description="다른 상태 필터를 선택해 보세요."
          />
        )}
        {loadState.kind === "ready" && filteredPlans.length > 0 && (
          <div className="activity-lifecycle-list">
            {filteredPlans.map((activity) => {
              const lookup = observationLookups[activity.id] ?? { kind: "loading" as const };
              const logs = lookup.kind === "ready" ? lookup.logs : [];
              const resultCount = logs.length;
              const latestLog = logs[0] ?? null;
              const primaryTime =
                activity.status === "completed"
                  ? formatActivityTime(activity.completed_at)
                  : activity.status === "skipped"
                    ? formatActivityTime(activity.skipped_at)
                    : formatActivityTime(activity.started_at);
              const fromGeneratedMaterial = activity.source_refs.some((ref) => ref.startsWith("material:"));
              const progressStep = resultCount > 0
                ? 4
                : ["completed", "skipped", "archived"].includes(activity.status)
                  ? 3
                  : activity.status === "active"
                    ? 2
                    : 1;

              return (
                <article className={`activity-lifecycle-card status-${activity.status}`} key={activity.id}>
                  <div className="activity-lifecycle-card-heading">
                    <div>
                      <div className="quest-card-tags">
                        <span className={`status-badge status-${activity.status}`}>
                          {QUEST_STATUS_LABEL[activity.status]}
                        </span>
                        {fromGeneratedMaterial && <span className="status-badge">생성 자료</span>}
                        {resultCount > 0 && <span className="status-badge result-recorded">결과 기록됨 · {resultCount}</span>}
                      </div>
                      <strong>{activity.title}</strong>
                      {primaryTime && <small>{primaryTime}</small>}
                    </div>
                  </div>

                  {activity.parent_note && <p>{activity.parent_note}</p>}

                  <div className="activity-stage-track" aria-label={`${activity.title} 퀘스트 진행 상태`}>
                    {[
                      [1, "생성"],
                      [2, "진행"],
                      [3, "완료"],
                      [4, "결과"],
                    ].map(([step, label]) => (
                      <span key={step} className={progressStep >= Number(step) ? "done" : ""}>
                        {label}
                      </span>
                    ))}
                  </div>

                  <div className="review-actions">
                    {activity.status === "suggested" && (
                      <button
                        type="button"
                        className="primary-button"
                        disabled={planBusy}
                        onClick={() => onTransition(activity.id, "active")}
                      >
                        퀘스트 시작
                      </button>
                    )}
                    {activity.status === "active" && (
                      <button
                        type="button"
                        className="primary-button"
                        disabled={planBusy}
                        onClick={() => onTransition(activity.id, "completed")}
                      >
                        완료로 표시
                      </button>
                    )}
                    {(activity.status === "suggested" || activity.status === "active") && (
                      <button
                        type="button"
                        className="quiet-button"
                        disabled={planBusy}
                        onClick={() => onTransition(activity.id, "skipped")}
                      >
                        이번에는 건너뜀
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
                  </div>

                  <EntityLinkPanel
                    entityId={activity.id}
                    ownerChildId={activity.child_id}
                    label="다른 아이와 활동 연결"
                  />

                  <div className="activity-observation-link" role="status" aria-live="polite">
                    {lookup.kind === "loading" && <p>결과 기록 확인 중…</p>}
                    {lookup.kind === "error" && (
                      <p className="form-error" role="alert">{lookup.message}</p>
                    )}
                    {lookup.kind === "ready" && resultCount === 0 && (
                      <p>
                        아직 결과 기록이 없습니다. 생성 자료 퀘스트라면 자료 카드의 ‘활동 결과 기록’을,
                        일반 퀘스트라면 관찰 화면에서 이 활동을 선택해 기록할 수 있습니다.
                      </p>
                    )}
                    {lookup.kind === "ready" && latestLog && (
                      <div>
                        <strong>최근 결과</strong>
                        <p>{latestLog.parent_observation}</p>
                        {latestLog.created_at && (
                          <small>{new Date(latestLog.created_at).toLocaleString("ko-KR")}</small>
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
