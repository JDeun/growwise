import type { FormEvent } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  listPhotoRecords,
  recordMaterialResult,
  transitionActivity,
  type ActivityPlan,
  type ExperienceAxis,
  type GeneratedMaterial,
  type LearningLog,
  type PhotoActivityRecord,
} from "../api";
import { ensureMaterialQuest } from "../material-quest";
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

function activityTimestamp(activity: ActivityPlan | null): string | null {
  if (!activity) return null;
  const value = activity.completed_at ?? activity.skipped_at ?? activity.started_at ?? null;
  return value ? new Date(value).toLocaleString("ko-KR") : null;
}

function photoRecordSummary(record: PhotoActivityRecord): string {
  const firstLine = record.generated_observation.split("\n")[0]?.trim();
  return (firstLine || "사진 기록").slice(0, 120);
}

function photoRecordTimestamp(record: PhotoActivityRecord): string | null {
  const value = record.updated_at ?? record.created_at ?? null;
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
  const [photoRecords, setPhotoRecords] = useState<PhotoActivityRecord[]>([]);
  const [selectedPhotoRecordIds, setSelectedPhotoRecordIds] = useState<string[]>([]);
  const [photoLoading, setPhotoLoading] = useState(false);
  const [photoError, setPhotoError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const onRecordedRef = useRef(onRecorded);

  useEffect(() => {
    onRecordedRef.current = onRecorded;
  }, [onRecorded]);

  const reloadQuest = useCallback(async () => {
    setLoadState("loading");
    setError(null);
    try {
      const ensured = await ensureMaterialQuest({
        id: material.id,
        child_id: material.child_id,
        title: material.title,
      });
      setActivity(ensured.item.activity);
      setResults(ensured.item.learning_logs);
      setLoadState("ready");
      if (ensured.created) await onRecordedRef.current();
    } catch (cause) {
      setLoadState("error");
      setError(cause instanceof Error ? cause.message : "퀘스트 상태를 불러오지 못했습니다.");
    }
  }, [material.child_id, material.id, material.title]);

  useEffect(() => {
    void reloadQuest();
  }, [reloadQuest]);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setPhotoLoading(true);
    setPhotoError(null);
    void listPhotoRecords(material.child_id)
      .then((records) => {
        if (!cancelled) setPhotoRecords(records.filter((record) => record.status === "committed"));
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          setPhotoRecords([]);
          setPhotoError(
            cause instanceof Error ? cause.message : "사진 기록을 불러오지 못했습니다.",
          );
        }
      })
      .finally(() => {
        if (!cancelled) setPhotoLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [material.child_id, open]);

  const questStatus = activity?.status ?? "suggested";
  const hasResult = results.length > 0;
  const timestamp = activityTimestamp(activity);
  const latestResult = results[0] ?? null;
  const canStart = !activity || activity.status === "suggested" || activity.status === "skipped";
  const canComplete = !activity || ["suggested", "active", "skipped"].includes(activity.status);
  const canSkip = !activity || ["suggested", "active"].includes(activity.status);
  const availablePhotos = useMemo(() => photoRecords.slice(0, 8), [photoRecords]);

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

  function togglePhotoRecord(recordId: string) {
    setSelectedPhotoRecordIds((current) =>
      current.includes(recordId)
        ? current.filter((item) => item !== recordId)
        : [...current, recordId],
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
    setSelectedPhotoRecordIds([]);
    setError(null);
  }

  async function ensureActivity(): Promise<ActivityPlan> {
    if (activity) return activity;
    const ensured = await ensureMaterialQuest({
      id: material.id,
      child_id: material.child_id,
      title: material.title,
    });
    setActivity(ensured.item.activity);
    setResults(ensured.item.learning_logs);
    if (ensured.created) await onRecordedRef.current();
    return ensured.item.activity;
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
      const request = {
        outcome,
        observation: mainObservation,
        process: process.trim() || null,
        child_question: childQuestion.trim() || null,
        interest: interest.trim() || null,
        difficulty_note: difficulty.trim() || null,
        next_activity: nextActivity.trim() || null,
        experience_axes: axes,
        activity_plan_id: activity?.id ?? null,
        photo_record_ids: selectedPhotoRecordIds,
      };
      const response = await recordMaterialResult(material.id, request);
      setActivity(response.activity);
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
              <small>각 입력값을 구조화해서 저장하고 다음 추천·자료 생성에 다시 사용합니다.</small>
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

          <fieldset className="material-result-photo-evidence">
            <legend>사진·산출물 증거(선택)</legend>
            <p className="muted">
              사진 기록 작업공간에서 부모 검토까지 마친 기록을 연결합니다. 이미지 파일은 복제하지 않습니다.
            </p>
            {photoLoading && <p className="muted">사진 기록 확인 중…</p>}
            {photoError && <p className="form-error">{photoError}</p>}
            {!photoLoading && !photoError && availablePhotos.length === 0 && (
              <p className="muted">연결할 수 있는 확정 사진 기록이 아직 없습니다.</p>
            )}
            {availablePhotos.length > 0 && (
              <div className="material-photo-options">
                {availablePhotos.map((record) => {
                  const selected = selectedPhotoRecordIds.includes(record.id);
                  const photoTimestamp = photoRecordTimestamp(record);
                  const shared = record.child_id !== material.child_id;
                  return (
                    <label className="material-photo-option" key={record.id}>
                      <input
                        type="checkbox"
                        checked={selected}
                        onChange={() => togglePhotoRecord(record.id)}
                        disabled={busy}
                      />
                      <span>
                        <strong>{photoRecordSummary(record)}</strong>
                        <small>
                          {shared ? "공유 사진 · " : ""}
                          {photoTimestamp ?? "저장된 사진 기록"}
                        </small>
                      </span>
                    </label>
                  );
                })}
              </div>
            )}
          </fieldset>

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
