import type { ViewLoadState } from "../child-context-state";
import { ViewStateNotice } from "../components";
import type { ActivityPlan, ActivityStatus, InfantActivitySuggestions } from "../api";
import { activityStatusLabel } from "../presentation";

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
  return (
    <>
      <section className="activity-section">
        <div className="activity-heading">
          <div>
            <p className="card-label">ACTIVITY INVITATIONS</p>
            <h3>다음 활동 후보</h3>
            <p className="muted">추천은 의무가 아닙니다. 부모가 선택한 후보만 활동 목록에 저장됩니다.</p>
          </div>
          <button className="quiet-button" type="button" onClick={onLoadSuggestions} disabled={suggestionsLoading}>
            {suggestionsLoading ? "불러오는 중…" : "활동 후보 보기"}
          </button>
        </div>
        {error && <p className="form-error" role="alert">{error}</p>}
        {suggestions && (
          <div className="activity-grid">
            {suggestions.suggestions.map((suggestion) => (
              <article className="activity-card" key={`${suggestion.title}-${suggestion.description}`}>
                <h4>{suggestion.title}</h4>
                <p>{suggestion.description}</p>
                {suggestion.observation_cue && <small>{suggestion.observation_cue}</small>}
                <button type="button" className="quiet-button activity-save" disabled={planBusy} onClick={() => onSaveActivity(suggestion.title)}>
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
            <p className="card-label">ACTIVITY QUESTS</p>
            <h3>선택한 활동</h3>
            <p className="muted">건너뜀은 실패가 아니며, 나중에 다시 시작할 수 있습니다.</p>
          </div>
          <span className="badge">{loadState.kind === "ready" ? `${plans.length}건` : "확인 중"}</span>
        </div>
        {loadState.kind === "loading" && <ViewStateNotice kind="loading" title="활동 목록을 불러오는 중입니다." description="저장한 활동 상태를 확인합니다." />}
        {loadState.kind === "error" && <ViewStateNotice kind="error" title="활동 목록을 불러오지 못했습니다." description={loadState.message} action={<button className="quiet-button" type="button" onClick={onRetryPlans}>다시 시도</button>} />}
        {loadState.kind === "ready" && plans.length === 0 && <ViewStateNotice kind="empty" title="저장한 활동이 없습니다." description="활동 후보에서 선택한 항목만 이 목록에 저장됩니다." />}
        {loadState.kind === "ready" && plans.length > 0 && (
          <div className="quest-list">
            {plans.map((activity) => (
              <article className="quest-card" key={activity.id}>
                <div>
                  <strong>{activity.title}</strong>
                  <span className={`status-badge status-${activity.status}`}>{activityStatusLabel(activity.status)}</span>
                </div>
                {activity.parent_note && <p>{activity.parent_note}</p>}
                <div className="review-actions">
                  {activity.status === "suggested" && <button type="button" className="primary-button" disabled={planBusy} onClick={() => onTransition(activity.id, "active")}>시작</button>}
                  {activity.status === "active" && <button type="button" className="primary-button" disabled={planBusy} onClick={() => onTransition(activity.id, "completed")}>완료</button>}
                  {(activity.status === "suggested" || activity.status === "active") && <button type="button" className="quiet-button" disabled={planBusy} onClick={() => onTransition(activity.id, "skipped")}>건너뜀</button>}
                  {activity.status === "skipped" && <button type="button" className="quiet-button" disabled={planBusy} onClick={() => onTransition(activity.id, "active")}>다시 시작</button>}
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </>
  );
}
