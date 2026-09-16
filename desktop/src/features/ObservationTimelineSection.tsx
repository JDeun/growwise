import type { ViewLoadState } from "../child-context-state";
import { ViewStateNotice } from "../components";
import type { ActivityPlan, LearningLog } from "../api";
import { AXIS_OPTIONS } from "../presentation";

interface ObservationTimelineSectionProps {
  loadState: ViewLoadState;
  timeline: LearningLog[];
  activityPlans: ActivityPlan[];
  onRetry: () => void;
}

export function ObservationTimelineSection({
  loadState,
  timeline,
  activityPlans,
  onRetry,
}: ObservationTimelineSectionProps) {
  return (
    <section className="timeline-section">
      <div className="activity-heading">
        <div>
          <p className="card-label">OBSERVATION TIMELINE</p>
          <h3>관찰 기록</h3>
        </div>
        <span className="badge">{loadState.kind === "ready" ? `${timeline.length}건` : "확인 중"}</span>
      </div>
      {loadState.kind === "loading" && <ViewStateNotice kind="loading" title="관찰 기록을 불러오는 중입니다." description="이 아이의 기록만 확인합니다." />}
      {loadState.kind === "error" && <ViewStateNotice kind="error" title="관찰 기록을 불러오지 못했습니다." description={loadState.message} action={<button className="quiet-button" type="button" onClick={onRetry}>다시 시도</button>} />}
      {loadState.kind === "ready" && timeline.length === 0 && <ViewStateNotice kind="empty" title="아직 기록이 없습니다." description="기록 공백은 실패가 아닙니다. 의미 있는 순간이 있을 때만 남겨도 됩니다." />}
      {loadState.kind === "ready" && timeline.length > 0 && (
        <div className="timeline-list">
          {timeline.map((log) => {
            const linkedActivity = log.activity_plan_id
              ? activityPlans.find((item) => item.id === log.activity_plan_id)
              : null;
            return (
              <article key={log.id} className="timeline-card">
                {linkedActivity && <small className="timeline-activity">활동 · {linkedActivity.title}</small>}
                <p>{log.parent_observation}</p>
                <div className="axis-summary">
                  {log.experience_axes.map((axis) => (
                    <span key={axis}>{AXIS_OPTIONS.find((item) => item.value === axis)?.label ?? axis}</span>
                  ))}
                </div>
                {log.created_at && <time dateTime={log.created_at}>{new Date(log.created_at).toLocaleString("ko-KR")}</time>}
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
