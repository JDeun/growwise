import type { FormEvent } from "react";

import type { ViewLoadState } from "../child-context-state";
import { ViewStateNotice } from "../components";
import type { ActivityPlan, ExperienceAxis, GrowthMap } from "../api";
import { AXIS_OPTIONS, activityStatusLabel, axisLabel, diversityLabel } from "../presentation";

interface ObservationGrowthSectionProps {
  observation: string;
  selectedAxes: ExperienceAxis[];
  selectedActivityId: string;
  saving: boolean;
  error: string | null;
  activityPlans: ActivityPlan[];
  growthState: ViewLoadState;
  growthMap: GrowthMap | null;
  onObservationChange: (value: string) => void;
  onSelectedActivityChange: (value: string) => void;
  onToggleAxis: (axis: ExperienceAxis) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onRetryGrowth: () => void;
}

export function ObservationGrowthSection({
  observation,
  selectedAxes,
  selectedActivityId,
  saving,
  error,
  activityPlans,
  growthState,
  growthMap,
  onObservationChange,
  onSelectedActivityChange,
  onToggleAxis,
  onSubmit,
  onRetryGrowth,
}: ObservationGrowthSectionProps) {
  return (
    <div className="observation-panel">
      <form className="observation-form" onSubmit={onSubmit}>
        <div>
          <p className="card-label">OBSERVATION</p>
          <h3>의미 있는 관찰만 기록합니다.</h3>
          <p className="muted">관련 활동과 경험 축은 선택 사항입니다. 연결한 경우에만 활동의 후속 관찰로 기록됩니다.</p>
        </div>
        <textarea value={observation} onChange={(event) => onObservationChange(event.target.value)} placeholder="예: 그림책의 고양이 그림을 오래 바라보고 여러 번 손으로 가리켰다." maxLength={10000} disabled={saving} />
        {activityPlans.length > 0 && (
          <label className="observation-activity-link">
            <span>관련 활동(선택)</span>
            <select value={selectedActivityId} onChange={(event) => onSelectedActivityChange(event.target.value)} disabled={saving}>
              <option value="">일반 관찰 기록</option>
              {activityPlans.filter((activity) => activity.status !== "archived").map((activity) => (
                <option key={activity.id} value={activity.id}>
                  {activity.title} · {activityStatusLabel(activity.status)}
                </option>
              ))}
            </select>
          </label>
        )}
        <div className="axis-picker">
          {AXIS_OPTIONS.map((option) => {
            const active = selectedAxes.includes(option.value);
            return (
              <button key={option.value} type="button" className={`axis-chip ${active ? "active" : ""}`} aria-pressed={active} onClick={() => onToggleAxis(option.value)}>
                {option.label}
              </button>
            );
          })}
        </div>
        <button className="primary-button" type="submit" disabled={saving}>
          {saving ? "기록 중…" : "관찰 저장"}
        </button>
        {error && <p className="form-error" role="alert">{error}</p>}
      </form>

      <article className="observation-result">
        <p className="card-label">GROWTH CONTEXT</p>
        <h3>최근 {growthMap?.period_days ?? 30}일</h3>
        {growthState.kind === "loading" && (
          <ViewStateNotice kind="loading" title="성장 맥락을 불러오는 중입니다." description="다른 작업공간은 기다리지 않고 사용할 수 있습니다." />
        )}
        {growthState.kind === "error" && (
          <ViewStateNotice kind="error" title="성장 맥락을 불러오지 못했습니다." description={growthState.message} action={<button className="quiet-button" type="button" onClick={onRetryGrowth}>다시 시도</button>} />
        )}
        {growthState.kind === "ready" && growthMap && growthMap.total_logs_in_period === 0 && (
          <ViewStateNotice kind="empty" title="아직 최근 관찰 기록이 없습니다." description="관찰을 기록하면 경험 축과 성장 맥락이 이곳에 누적됩니다." />
        )}
        {growthState.kind === "ready" && growthMap && growthMap.total_logs_in_period > 0 && (
          <>
            <p className="muted">기록 {growthMap.total_logs_in_period}건 · 경험 축 연결 {growthMap.tagged_logs_in_period}건</p>
            <div className="growth-layers">
              {growthMap.layers.map((layer) => (
                <section className="growth-layer" key={layer.key}>
                  <strong>{layer.label}</strong>
                  <div className="axis-summary">
                    {layer.axes.filter((axis) => axis.observation_count > 0).map((axis) => (
                      <span key={axis.axis}>{axisLabel(axis.axis)} · {axis.observation_count}</span>
                    ))}
                  </div>
                  {layer.axes.every((axis) => axis.observation_count === 0) && <small>이 렌즈에 연결된 최근 기록이 아직 없습니다.</small>}
                </section>
              ))}
            </div>
            <div className={`diversity-note diversity-${growthMap.diversity.state}`}>
              <strong>{diversityLabel(growthMap.diversity.state)}</strong>
              <p>{growthMap.diversity.note}</p>
              {growthMap.diversity.focus_axes.length > 0 && <small>자주 기록된 경험: {growthMap.diversity.focus_axes.map(axisLabel).join(", ")}</small>}
            </div>
          </>
        )}
      </article>
    </div>
  );
}
