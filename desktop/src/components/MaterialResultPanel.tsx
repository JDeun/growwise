import { FormEvent, useState } from "react";

import {
  createActivity,
  createObservation,
  transitionActivity,
  type ActivityStatus,
  type ExperienceAxis,
  type GeneratedMaterial,
} from "../api";
import { AXIS_OPTIONS } from "../presentation";
import "./MaterialResultPanel.css";

type MaterialUseOutcome = "completed" | "partial" | "skipped";

interface MaterialResultPanelProps {
  material: GeneratedMaterial;
  onRecorded: () => void | Promise<void>;
}

function section(label: string, value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? `${label}: ${trimmed}` : null;
}

export function MaterialResultPanel({ material, onRecorded }: MaterialResultPanelProps) {
  const [open, setOpen] = useState(false);
  const [outcome, setOutcome] = useState<MaterialUseOutcome>("completed");
  const [observation, setObservation] = useState("");
  const [process, setProcess] = useState("");
  const [childQuestion, setChildQuestion] = useState("");
  const [interest, setInterest] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [nextActivity, setNextActivity] = useState("");
  const [axes, setAxes] = useState<ExperienceAxis[]>([]);
  const [activityId, setActivityId] = useState<string | null>(null);
  const [activityStatus, setActivityStatus] = useState<ActivityStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function toggleAxis(axis: ExperienceAxis) {
    setAxes((current) =>
      current.includes(axis) ? current.filter((item) => item !== axis) : [...current, axis],
    );
  }

  function reset() {
    setOutcome("completed");
    setObservation("");
    setProcess("");
    setChildQuestion("");
    setInterest("");
    setDifficulty("");
    setNextActivity("");
    setAxes([]);
    setActivityId(null);
    setActivityStatus(null);
    setError(null);
  }

  async function ensureOutcome(
    linkedActivityId: string,
    currentStatus: ActivityStatus,
  ): Promise<ActivityStatus> {
    let status = currentStatus;

    if (outcome === "partial") {
      if (status === "suggested" || status === "skipped") {
        const updated = await transitionActivity(linkedActivityId, "active");
        status = updated.status;
        setActivityStatus(status);
      }
      return status;
    }

    if (outcome === "completed") {
      if (status === "suggested" || status === "skipped") {
        const updated = await transitionActivity(linkedActivityId, "active");
        status = updated.status;
        setActivityStatus(status);
      }
      if (status === "active") {
        const updated = await transitionActivity(linkedActivityId, "completed");
        status = updated.status;
        setActivityStatus(status);
      }
      return status;
    }

    if (status === "suggested" || status === "active") {
      const updated = await transitionActivity(linkedActivityId, "skipped");
      status = updated.status;
      setActivityStatus(status);
    }
    return status;
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const mainObservation = observation.trim();
    if (!mainObservation) {
      setError("실제 활동에서 관찰한 내용을 한 줄 이상 적어 주세요.");
      return;
    }

    setBusy(true);
    setError(null);
    try {
      let linkedActivityId = activityId;
      let linkedActivityStatus = activityStatus;
      if (!linkedActivityId || !linkedActivityStatus) {
        const activity = await createActivity(
          material.child_id,
          material.title,
          [`material:${material.id}`],
        );
        linkedActivityId = activity.id;
        linkedActivityStatus = activity.status;
        setActivityId(activity.id);
        setActivityStatus(activity.status);
      }

      linkedActivityStatus = await ensureOutcome(linkedActivityId, linkedActivityStatus);
      setActivityStatus(linkedActivityStatus);

      const details = [
        section("활동 과정", process),
        section("아이 질문·반응", childQuestion),
        section("흥미", interest),
        section("어려움", difficulty),
        section("다음에 해볼 것", nextActivity),
      ].filter((item): item is string => item !== null);
      const text = details.length > 0
        ? `${mainObservation}\n\n${details.join("\n")}`
        : mainObservation;

      await createObservation({
        child_id: material.child_id,
        observation: text,
        experience_axes: axes,
        activity_plan_id: linkedActivityId,
      });

      await onRecorded();
      reset();
      setOpen(false);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "활동 결과 저장에 실패했습니다.");
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <button className="quiet-button" type="button" onClick={() => setOpen(true)}>
        활동 결과 기록
      </button>
    );
  }

  return (
    <form className="material-result-panel" onSubmit={submit}>
      <div className="material-result-heading">
        <div>
          <strong>이 자료로 활동한 결과</strong>
          <small>저장하면 관찰 기록과 성장 맥락에 다시 반영됩니다.</small>
        </div>
        <button
          className="quiet-button"
          type="button"
          disabled={busy}
          onClick={() => {
            reset();
            setOpen(false);
          }}
        >
          닫기
        </button>
      </div>

      <fieldset className="material-result-outcomes">
        <legend>진행 결과</legend>
        {([
          ["completed", "완료"],
          ["partial", "일부 진행"],
          ["skipped", "이번에는 건너뜀"],
        ] as const).map(([value, label]) => (
          <label key={value}>
            <input
              type="radio"
              name={`material-outcome-${material.id}`}
              value={value}
              checked={outcome === value}
              onChange={() => setOutcome(value)}
              disabled={busy || activityId !== null}
            />
            <span>{label}</span>
          </label>
        ))}
      </fieldset>

      <label>
        <span>부모 관찰 *</span>
        <textarea
          value={observation}
          onChange={(event) => setObservation(event.target.value)}
          maxLength={10000}
          placeholder="예: 얼음이 녹는 모습을 예상보다 오래 지켜보고, 물이 생긴 이유를 물었다."
          disabled={busy}
        />
      </label>

      <div className="material-result-grid">
        <label>
          <span>활동 과정</span>
          <textarea value={process} onChange={(event) => setProcess(event.target.value)} disabled={busy} />
        </label>
        <label>
          <span>아이 질문·반응</span>
          <textarea value={childQuestion} onChange={(event) => setChildQuestion(event.target.value)} disabled={busy} />
        </label>
        <label>
          <span>흥미를 보인 점</span>
          <textarea value={interest} onChange={(event) => setInterest(event.target.value)} disabled={busy} />
        </label>
        <label>
          <span>어려워한 점</span>
          <textarea value={difficulty} onChange={(event) => setDifficulty(event.target.value)} disabled={busy} />
        </label>
      </div>

      <label>
        <span>다음에 해볼 것</span>
        <input
          value={nextActivity}
          onChange={(event) => setNextActivity(event.target.value)}
          maxLength={1000}
          placeholder="예: 같은 크기의 얼음을 햇빛과 그늘에서 비교하기"
          disabled={busy}
        />
      </label>

      <fieldset className="material-result-axes">
        <legend>경험·학습 축(선택)</legend>
        <div>
          {AXIS_OPTIONS.map((option) => (
            <button
              key={option.value}
              type="button"
              className={`axis-chip ${axes.includes(option.value) ? "active" : ""}`}
              aria-pressed={axes.includes(option.value)}
              onClick={() => toggleAxis(option.value)}
              disabled={busy}
            >
              {option.label}
            </button>
          ))}
        </div>
      </fieldset>

      {error && <p className="form-error" role="alert">{error}</p>}
      <button className="primary-button" type="submit" disabled={busy || !observation.trim()}>
        {busy ? "결과 저장 중…" : "결과 저장"}
      </button>
    </form>
  );
}
