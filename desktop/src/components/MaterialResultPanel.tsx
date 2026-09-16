import type { FormEvent } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  createActivity,
  createObservation,
  listActivities,
  listObservations,
  transitionActivity,
  type ActivityPlan,
  type ExperienceAxis,
  type GeneratedMaterial,
  type LearningLog,
} from "../api";
import { AXIS_OPTIONS } from "../presentation";
import "./MaterialResultPanel.css";

type MaterialUseOutcome = "completed" | "partial" | "skipped";
type QuestLoadState = "loading" | "ready" | "error";

interface MaterialResultPanelProps {
  material: GeneratedMaterial;
  onRecorded: () => void | Promise<void>;
}

const QUEST_STATUS = {
  suggested: "생성됨",
  active: "진행 중",
  completed: "완료됨",
  skipped: "건너뜀",
  archived: "보관됨",
} as const;

function section(label: string, value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? `${label}: ${trimmed}` : null;
}

function activityTimestamp(activity: ActivityPlan | null): string | null {
  if (!activity) return null;
  const value = activity.completed_at ?? activity.skipped_at ?? activity.started_at ?? null;
  return value ? new Date(value).toLocaleString("ko-KR") : null;
}

export function MaterialResultPanel({ material, onRecorded }: MaterialResultPanelProps) {
  const [open, setOpen] = useState(false);
  const [loadState, setLoadState] = useState<QuestLoadState>("loading");
  const [activity, setActivity] = useState<ActivityPlan | null>(null);
  const [results, setResults] = useState<LearningLog[]>([]);
  const [outcome, setOutcome] = useState<MaterialUseOutcome>("completed");
  const [observation, setObservation] = useState("");
  const [process, setProcess] = useState("");
  const [childQuestion, setChildQuestion] = useState("");
  const [interest, setInterest] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [nextActivity, setNextActivity] = useState("");
  const [axes, setAxes] = useState<ExperienceAxis[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const materialRef = `material:${material.id}`;

  const reloadQuest = useCallback(async () => {
    setLoadState("loading");
    setError(null);
    try {
      const [activities, observations] = await Promise.all([
        listActivities(material.child_id),
        listObservations(material.child_id),
      ]);
      const linkedActivity =
        activities.find((candidate) => candidate.source_refs.includes(materialRef)) ?? null;
      const linkedResults = linkedActivity
        ? observations
            .filter((log) => log.activity_plan_id === linkedActivity.id)
            .sort((left, right) =>
              String(right.created_at ?? "").localeCompare(String(left.created_at ?? "")),
            )
        : [];
      setActivity(linkedActivity);
      setResults(linkedResults);
      setLoadState("ready");
    } catch (cause) {
      setLoadState("error");
      setError(cause instanceof Error ? cause.message : "퀘스트 상태를 불러오지 못했습니다.");
    }
  }, [material.child_id, materialRef]);

  useEffect(() => {
    void reloadQuest();
  }, [reloadQuest]);

  const questStatus = activity?.status ?? "suggested";
  const hasResult = results.length > 0;
  const timestamp = activityTimestamp(activity);
  const latestResult = results[0] ?? null;
  const canStart = !activity || activity.status === "suggested" || activity.status === "skipped";
  const canComplete = !activity || ["suggested", "active", "skipped"].includes(activity.status);
  const canSkip = !activity || ["suggested", "active"].includes(activity.status);

  const progressStep = useMemo(() => {
    if (hasResult) return 4;
    if (activity?.status === "completed" || activity?.status === "skipped") return 3;
    if (activity?.status === "active") return 2;
    return 1;
  }, [activity?.status, hasResult]);

  function toggleAxis(axis: ExperienceAxis) {
    setAxes((current) =>
      current.includes(axis) ? current.filter((item) => item !== axis) : [...current, axis],
    );
  }

  function resetForm() {
    setOutcome("completed");
    setObservation("");
    setProcess("");
    setChildQuestion("");
    setInterest("");
    setDifficulty("");
    setNextActivity("");
    setAxes([]);
    setError(null);
  }

  async function ensureActivity(): Promise<ActivityPlan> {
    if (activity) return activity;
    const created = await createActivity(material.child_id, material.title, [materialRef]);
    setActivity(created);
    return created;
  }

  async function setQuestStatus(target: "active" | "completed" | "skipped"): Promise<ActivityPlan> {
    let current = await ensureActivity();

    if (target === "active") {
      if (current.status === "suggested" || current.status === "skipped") {
        current = await transitionActivity(current.id, "active");
      }
      return current;
    }

    if (target === "completed") {
      if (current.status === "suggested" || current.status === "skipped") {
        current = await transitionActivity(current.id, "active");
      }
      if (current.status === "active") {
        current = await transitionActivity(current.id, "completed");
      }
      return current;
    }

    if (current.status === "suggested" || current.status === "active") {
      current = await transitionActivity(current.id, "skipped");
    }
    return current;
  }

  async function runQuestAction(action: "start" | "complete" | "skip") {
    setBusy(true);
    setError(null);
    try {
      const updated = await setQuestStatus(
        action === "start" ? "active" : action === "complete" ? "completed" : "skipped",
      );
      setActivity(updated);
      await reloadQuest();
      await onRecorded();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "퀘스트 상태를 변경하지 못했습니다.");
    } finally {
      setBusy(false);
    }
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
      const linkedActivity = await setQuestStatus(
        outcome === "partial" ? "active" : outcome,
      );
      setActivity(linkedActivity);

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
        activity_plan_id: linkedActivity.id,
      });

      await reloadQuest();
      await onRecorded();
      resetForm();
      setOpen(false);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "활동 결과 저장에 실패했습니다.");
    } finally {
      setBusy(false);
    }
  }

  function openResultForm() {
    if (activity?.status === "skipped") setOutcome("skipped");
    else if (activity?.status === "active") setOutcome("partial");
    else setOutcome("completed");
    setOpen(true);
  }

  return (
    <section className="material-quest" aria-label={`${material.title} 활동 퀘스트`}>
      <div className="material-quest-heading">
        <div>
          <span className="material-quest-kicker">QUEST</span>
          <strong>활동 퀘스트</strong>
          <small>인쇄한 자료를 실제로 사용한 상태와 결과를 이어서 기록합니다.</small>
        </div>
        <div className="material-quest-tags" aria-label="퀘스트 상태">
          <span className={`quest-tag status-${questStatus}`}>{QUEST_STATUS[questStatus]}</span>
          {hasResult && <span className="quest-tag result-recorded">결과 기록됨 · {results.length}</span>}
        </div>
      </div>

      <div className="material-quest-track" aria-label="퀘스트 진행 단계">
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

      {loadState === "loading" && <p className="muted">퀘스트 상태 확인 중…</p>}
      {loadState === "error" && (
        <div className="material-quest-error">
          <p className="form-error" role="alert">{error}</p>
          <button className="quiet-button" type="button" onClick={() => void reloadQuest()}>
            다시 확인
          </button>
        </div>
      )}

      {loadState === "ready" && (
        <>
          {(timestamp || latestResult) && (
            <div className="material-quest-meta">
              {timestamp && <small>최근 상태 변경 · {timestamp}</small>}
              {latestResult && (
                <small>최근 결과 · {latestResult.parent_observation.split("\n")[0]}</small>
              )}
            </div>
          )}

          <div className="material-quest-actions">
            {canStart && (
              <button
                className="primary-button"
                type="button"
                disabled={busy}
                onClick={() => void runQuestAction("start")}
              >
                {activity?.status === "skipped" ? "다시 시작" : "퀘스트 시작"}
              </button>
            )}
            {canComplete && activity?.status !== "completed" && (
              <button
                className="quiet-button"
                type="button"
                disabled={busy}
                onClick={() => void runQuestAction("complete")}
              >
                완료로 표시
              </button>
            )}
            {canSkip && (
              <button
                className="quiet-button"
                type="button"
                disabled={busy}
                onClick={() => void runQuestAction("skip")}
              >
                이번에는 건너뜀
              </button>
            )}
            <button
              className="quiet-button"
              type="button"
              disabled={busy}
              onClick={openResultForm}
            >
              {hasResult ? "결과 추가 기록" : "활동 결과 기록"}
            </button>
          </div>
        </>
      )}

      {open && (
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
                resetForm();
                setOpen(false);
              }}
            >
              닫기
            </button>
          </div>

          <fieldset className="material-result-outcomes">
            <legend>이번 기록의 진행 결과</legend>
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
                  disabled={busy || activity?.status === "completed"}
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
      )}
    </section>
  );
}
