import type { FormEvent } from "react";

import type { ViewLoadState } from "../child-context-state";
import type { ActivityPlan, ExperienceAxis, GrowthMap } from "../api";
import { AXIS_OPTIONS, activityStatusLabel } from "../presentation";
import { GrowthContextPanel } from "./GrowthContextPanel";

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
          <p className="muted">
            관련 활동과 경험 축은 선택 사항입니다. 연결한 경우에만 활동의 후속 관찰로 기록됩니다.
          </p>
        </div>
        <textarea
          value={observation}
          onChange={(event) => onObservationChange(event.target.value)}
          placeholder="예: 그림책의 고양이 그림을 오래 바라보고 여러 번 손으로 가리켰다."
          maxLength={10000}
          disabled={saving}
        />
        {activityPlans.length > 0 && (
          <label className="observation-activity-link">
            <span>관련 활동(선택)</span>
            <select
              value={selectedActivityId}
              onChange={(event) => onSelectedActivityChange(event.target.value)}
              disabled={saving}
            >
              <option value="">일반 관찰 기록</option>
              {activityPlans
                .filter((activity) => activity.status !== "archived")
                .map((activity) => (
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
              <button
                key={option.value}
                type="button"
                className={`axis-chip ${active ? "active" : ""}`}
                aria-pressed={active}
                onClick={() => onToggleAxis(option.value)}
              >
                {option.label}
              </button>
            );
          })}
        </div>
        <button className="primary-button" type="submit" disabled={saving}>
          {saving ? "기록 중…" : "관찰 저장"}
        </button>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
      </form>

      <GrowthContextPanel
        growthState={growthState}
        growthMap={growthMap}
        onRetry={onRetryGrowth}
      />
    </div>
  );
}
