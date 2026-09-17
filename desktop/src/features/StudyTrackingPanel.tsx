import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { useActiveChild } from "../active-child-context";
import {
  createStudyPlan,
  getStudyWeakMap,
  listSelfExplanations,
  listStudyMistakes,
  listStudyPlans,
  listStudyProgress,
  listStudyReflections,
  recommendStudyResources,
  recordSelfExplanation,
  recordStudyMistake,
  recordStudyProgress,
  recordStudyReflection,
  updateStudyPlanItemStatus,
  type MistakeRecord,
  type MistakeType,
  type PlanItemStatus,
  type SelfExplanationLog,
  type StudyPlan,
  type StudyProgressState,
  type StudyReflection,
  type StudyResourceRecommendation,
  type StudyUnitProgress,
  type WeakMap,
} from "../study-api";
import "./StudyTrackingPanel.css";

type StudyTab = "progress" | "mistake" | "reflection" | "explanation" | "map";

const TABS: Array<{ value: StudyTab; label: string }> = [
  { value: "progress", label: "진도" },
  { value: "mistake", label: "오답" },
  { value: "reflection", label: "회고" },
  { value: "explanation", label: "자기설명" },
  { value: "map", label: "복습지도·계획" },
];

const PROGRESS_OPTIONS: Array<{ value: StudyProgressState; label: string }> = [
  { value: "planned", label: "학습 예정" },
  { value: "in_progress", label: "학습 중" },
  { value: "review", label: "복습 필요" },
  { value: "revisit", label: "다시 확인" },
  { value: "comfortable", label: "현재는 편안함" },
];

const MISTAKE_OPTIONS: Array<{ value: MistakeType; label: string }> = [
  { value: "concept", label: "개념" },
  { value: "process", label: "풀이 과정" },
  { value: "reading", label: "문제 읽기" },
  { value: "calculation", label: "계산" },
  { value: "attention", label: "확인 누락" },
  { value: "communication", label: "설명·표현" },
  { value: "other", label: "기타" },
];

const PLAN_STATUS_LABEL: Record<PlanItemStatus, string> = {
  planned: "예정",
  done: "완료",
  skipped: "건너뜀",
};

export function isSecondaryStage(stage: string | null | undefined): boolean {
  return stage === "middle" || stage === "high";
}

function messageFrom(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

export function StudyTrackingPanel() {
  const { activeChild, activeChildId } = useActiveChild();
  const childId = activeChildId;
  const enabled = isSecondaryStage(activeChild?.stage);

  const [tab, setTab] = useState<StudyTab>("progress");
  const [subject, setSubject] = useState("");
  const [unit, setUnit] = useState("");
  const [progressState, setProgressState] = useState<StudyProgressState>("in_progress");
  const [progressNote, setProgressNote] = useState("");
  const [mistakeType, setMistakeType] = useState<MistakeType>("concept");
  const [mistakePrompt, setMistakePrompt] = useState("");
  const [learnerResponse, setLearnerResponse] = useState("");
  const [correctedUnderstanding, setCorrectedUnderstanding] = useState("");
  const [workedWell, setWorkedWell] = useState("");
  const [difficultPoint, setDifficultPoint] = useState("");
  const [nextStep, setNextStep] = useState("");
  const [explanation, setExplanation] = useState("");
  const [openQuestion, setOpenQuestion] = useState("");
  const [planTitle, setPlanTitle] = useState("");
  const [targetDate, setTargetDate] = useState("");
  const [parentNote, setParentNote] = useState("");

  const [progress, setProgress] = useState<StudyUnitProgress[]>([]);
  const [mistakes, setMistakes] = useState<MistakeRecord[]>([]);
  const [reflections, setReflections] = useState<StudyReflection[]>([]);
  const [explanations, setExplanations] = useState<SelfExplanationLog[]>([]);
  const [weakMap, setWeakMap] = useState<WeakMap | null>(null);
  const [plans, setPlans] = useState<StudyPlan[]>([]);
  const [resources, setResources] = useState<StudyResourceRecommendation[]>([]);
  const [resourceKey, setResourceKey] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const contextReady = Boolean(childId && subject.trim() && unit.trim());
  const counts = useMemo(
    () => ({
      progress: progress.length,
      mistake: mistakes.length,
      reflection: reflections.length,
      explanation: explanations.length,
      map: weakMap?.entries.length ?? 0,
    }),
    [explanations.length, mistakes.length, progress.length, reflections.length, weakMap?.entries.length],
  );

  const refresh = useCallback(async (targetChildId: string) => {
    setLoading(true);
    setError(null);
    try {
      const [nextProgress, nextMistakes, nextReflections, nextExplanations, nextMap, nextPlans] =
        await Promise.all([
          listStudyProgress(targetChildId),
          listStudyMistakes(targetChildId),
          listStudyReflections(targetChildId),
          listSelfExplanations(targetChildId),
          getStudyWeakMap(targetChildId),
          listStudyPlans(targetChildId),
        ]);
      setProgress(nextProgress);
      setMistakes(nextMistakes);
      setReflections(nextReflections);
      setExplanations(nextExplanations);
      setWeakMap(nextMap);
      setPlans(nextPlans);
    } catch (cause) {
      setError(messageFrom(cause, "중·고 학습 기록을 불러오지 못했습니다."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    setResources([]);
    setResourceKey(null);
    setNotice(null);
    setError(null);
    setSubject("");
    setUnit("");
    if (!enabled || !childId) {
      setProgress([]);
      setMistakes([]);
      setReflections([]);
      setExplanations([]);
      setWeakMap(null);
      setPlans([]);
      return;
    }
    void refresh(childId);
  }, [childId, enabled, refresh]);

  if (!enabled || !childId) return null;

  async function refreshMap() {
    if (!childId) return;
    const nextMap = await getStudyWeakMap(childId);
    setWeakMap(nextMap);
  }

  async function submitProgress(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!contextReady) return;
    setBusy(true);
    setError(null);
    try {
      const created = await recordStudyProgress(childId, {
        subject: subject.trim(),
        unit: unit.trim(),
        state: progressState,
        note: progressNote.trim() || null,
        last_studied_at: new Date().toISOString(),
      });
      setProgress((current) => [created, ...current]);
      await refreshMap();
      setProgressNote("");
      setNotice("진도 상태를 기록했습니다.");
    } catch (cause) {
      setError(messageFrom(cause, "진도 저장에 실패했습니다."));
    } finally {
      setBusy(false);
    }
  }

  async function submitMistake(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!contextReady) return;
    setBusy(true);
    setError(null);
    try {
      const created = await recordStudyMistake(childId, {
        subject: subject.trim(),
        unit: unit.trim(),
        mistake_type: mistakeType,
        prompt: mistakePrompt.trim() || null,
        learner_response: learnerResponse.trim() || null,
        corrected_understanding: correctedUnderstanding.trim() || null,
        evidence_ref: null,
      });
      setMistakes((current) => [created, ...current]);
      await refreshMap();
      setMistakePrompt("");
      setLearnerResponse("");
      setCorrectedUnderstanding("");
      setNotice("오답·실수 기록을 저장했습니다. 한 번의 실수를 고정된 약점으로 해석하지 않습니다.");
    } catch (cause) {
      setError(messageFrom(cause, "오답 기록 저장에 실패했습니다."));
    } finally {
      setBusy(false);
    }
  }

  async function submitReflection(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!contextReady) return;
    setBusy(true);
    setError(null);
    try {
      const created = await recordStudyReflection(childId, {
        subject: subject.trim(),
        unit: unit.trim(),
        worked_well: workedWell.trim() || null,
        difficult_point: difficultPoint.trim() || null,
        next_step: nextStep.trim() || null,
      });
      setReflections((current) => [created, ...current]);
      await refreshMap();
      setWorkedWell("");
      setDifficultPoint("");
      setNextStep("");
      setNotice("학습 회고를 저장했습니다.");
    } catch (cause) {
      setError(messageFrom(cause, "회고 저장에 실패했습니다."));
    } finally {
      setBusy(false);
    }
  }

  async function submitExplanation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!contextReady || !explanation.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const created = await recordSelfExplanation(childId, {
        subject: subject.trim(),
        unit: unit.trim(),
        explanation: explanation.trim(),
        evidence_refs: [],
        open_question: openQuestion.trim() || null,
      });
      setExplanations((current) => [created, ...current]);
      setExplanation("");
      setOpenQuestion("");
      setNotice("아이의 자기설명을 저장했습니다.");
    } catch (cause) {
      setError(messageFrom(cause, "자기설명 저장에 실패했습니다."));
    } finally {
      setBusy(false);
    }
  }

  async function submitPlan(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!planTitle.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const created = await createStudyPlan(childId, {
        title: planTitle.trim(),
        target_date: targetDate || null,
        parent_note: parentNote.trim() || null,
        max_items: 6,
      });
      setPlans((current) => [created, ...current]);
      setPlanTitle("");
      setTargetDate("");
      setParentNote("");
      setNotice("최근 기록 근거로 복습 계획을 만들었습니다.");
    } catch (cause) {
      setError(messageFrom(cause, "학습 계획 생성에 실패했습니다."));
    } finally {
      setBusy(false);
    }
  }

  async function loadResources(entrySubject: string, entryUnit: string) {
    const key = `${entrySubject}\u0000${entryUnit}`;
    setBusy(true);
    setError(null);
    try {
      setResources(await recommendStudyResources(childId, entrySubject, entryUnit));
      setResourceKey(key);
    } catch (cause) {
      setError(messageFrom(cause, "연결 자료를 찾지 못했습니다."));
    } finally {
      setBusy(false);
    }
  }

  async function setPlanItemStatus(
    plan: StudyPlan,
    itemIndex: number,
    status: PlanItemStatus,
  ) {
    setBusy(true);
    setError(null);
    try {
      const updated = await updateStudyPlanItemStatus(childId, plan.id, itemIndex, status);
      setPlans((current) => current.map((item) => (item.id === updated.id ? updated : item)));
    } catch (cause) {
      setError(messageFrom(cause, "계획 상태를 바꾸지 못했습니다."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="study-tracking-panel" aria-labelledby="study-tracking-title">
      <div className="section-heading compact">
        <div>
          <p className="eyebrow">SECONDARY STUDY TRACKER</p>
          <h3 id="study-tracking-title">중·고 학습 트래커</h3>
          <p className="muted">
            점수·등수·또래 비교 없이, 실제 오답·회고·설명을 근거로 필요한 복습만 정리합니다.
          </p>
        </div>
        <span className="badge">Self vs. self</span>
      </div>

      <div className="study-unit-context">
        <label>
          <span>과목</span>
          <input value={subject} onChange={(event) => setSubject(event.target.value)} maxLength={120} placeholder="예: 수학" disabled={busy} />
        </label>
        <label>
          <span>단원·주제</span>
          <input value={unit} onChange={(event) => setUnit(event.target.value)} maxLength={240} placeholder="예: 일차함수" disabled={busy} />
        </label>
      </div>

      <div className="study-tabs" role="tablist" aria-label="중·고 학습 기록 종류">
        {TABS.map((item) => (
          <button
            key={item.value}
            type="button"
            role="tab"
            aria-selected={tab === item.value}
            className={tab === item.value ? "active" : ""}
            onClick={() => setTab(item.value)}
          >
            {item.label}<span>{counts[item.value]}</span>
          </button>
        ))}
      </div>

      {error && <p className="form-error" role="alert">{error}</p>}
      {notice && <p className="study-notice" role="status">{notice}</p>}
      {loading && <p className="muted">학습 추적 기록을 불러오는 중…</p>}

      {tab === "progress" && (
        <form className="study-form" onSubmit={submitProgress}>
          <label>
            <span>현재 상태</span>
            <select value={progressState} onChange={(event) => setProgressState(event.target.value as StudyProgressState)} disabled={busy}>
              {PROGRESS_OPTIONS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
            </select>
          </label>
          <label><span>메모</span><textarea value={progressNote} onChange={(event) => setProgressNote(event.target.value)} maxLength={4000} placeholder="지금 어디까지 이해했는지 사실 중심으로 적습니다." disabled={busy} /></label>
          <button className="primary-button" type="submit" disabled={busy || !contextReady}>진도 기록</button>
          <div className="study-history-list">
            {progress.slice(0, 8).map((item) => <article key={item.id}><strong>{item.subject} · {item.unit}</strong><span>{PROGRESS_OPTIONS.find((option) => option.value === item.state)?.label ?? item.state}</span>{item.note && <p>{item.note}</p>}</article>)}
          </div>
        </form>
      )}

      {tab === "mistake" && (
        <form className="study-form" onSubmit={submitMistake}>
          <label><span>실수 유형</span><select value={mistakeType} onChange={(event) => setMistakeType(event.target.value as MistakeType)} disabled={busy}>{MISTAKE_OPTIONS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
          <label><span>문제·상황</span><textarea value={mistakePrompt} onChange={(event) => setMistakePrompt(event.target.value)} maxLength={4000} disabled={busy} /></label>
          <label><span>아이의 답·풀이</span><textarea value={learnerResponse} onChange={(event) => setLearnerResponse(event.target.value)} maxLength={4000} disabled={busy} /></label>
          <label><span>다시 확인한 이해</span><textarea value={correctedUnderstanding} onChange={(event) => setCorrectedUnderstanding(event.target.value)} maxLength={4000} disabled={busy} /></label>
          <button className="primary-button" type="submit" disabled={busy || !contextReady}>오답 기록</button>
          <div className="study-history-list">
            {mistakes.slice(0, 8).map((item) => <article key={item.id}><strong>{item.subject} · {item.unit}</strong><span>{MISTAKE_OPTIONS.find((option) => option.value === item.mistake_type)?.label ?? item.mistake_type}</span>{item.corrected_understanding && <p>{item.corrected_understanding}</p>}</article>)}
          </div>
        </form>
      )}

      {tab === "reflection" && (
        <form className="study-form" onSubmit={submitReflection}>
          <label><span>잘 된 점</span><textarea value={workedWell} onChange={(event) => setWorkedWell(event.target.value)} maxLength={4000} disabled={busy} /></label>
          <label><span>어려웠던 점</span><textarea value={difficultPoint} onChange={(event) => setDifficultPoint(event.target.value)} maxLength={4000} disabled={busy} /></label>
          <label><span>다음 한 단계</span><textarea value={nextStep} onChange={(event) => setNextStep(event.target.value)} maxLength={4000} disabled={busy} /></label>
          <button className="primary-button" type="submit" disabled={busy || !contextReady}>회고 저장</button>
          <div className="study-history-list">
            {reflections.slice(0, 8).map((item) => <article key={item.id}><strong>{item.subject} · {item.unit}</strong>{item.difficult_point && <p>어려움: {item.difficult_point}</p>}{item.next_step && <p>다음: {item.next_step}</p>}</article>)}
          </div>
        </form>
      )}

      {tab === "explanation" && (
        <form className="study-form" onSubmit={submitExplanation}>
          <label><span>아이의 자기설명 *</span><textarea value={explanation} onChange={(event) => setExplanation(event.target.value)} maxLength={8000} placeholder="배운 내용을 아이의 말로 설명한 그대로 기록합니다." disabled={busy} /></label>
          <label><span>아직 남은 질문</span><textarea value={openQuestion} onChange={(event) => setOpenQuestion(event.target.value)} maxLength={4000} disabled={busy} /></label>
          <button className="primary-button" type="submit" disabled={busy || !contextReady || !explanation.trim()}>자기설명 저장</button>
          <div className="study-history-list">
            {explanations.slice(0, 8).map((item) => <article key={item.id}><strong>{item.subject} · {item.unit}</strong><p>{item.explanation}</p>{item.open_question && <p>남은 질문: {item.open_question}</p>}</article>)}
          </div>
        </form>
      )}

      {tab === "map" && (
        <div className="study-map-layout">
          <section className="study-weak-map" aria-label="복습 신호 지도">
            <p className="muted">{weakMap?.interpretation ?? "아직 복습 신호가 없습니다."}</p>
            {(weakMap?.entries ?? []).map((entry) => {
              const key = `${entry.subject}\u0000${entry.unit}`;
              return (
                <article key={key}>
                  <div><strong>{entry.subject} · {entry.unit}</strong><span>근거 {entry.evidence_count}건</span></div>
                  {entry.recurring_mistake_types.length > 0 && <p>반복 유형: {entry.recurring_mistake_types.join(", ")}</p>}
                  {entry.recent_difficulties.map((item) => <p key={item}>최근 어려움: {item}</p>)}
                  {entry.parent_support_points.map((item) => <p className="study-support" key={item}>{item}</p>)}
                  <button className="quiet-button" type="button" disabled={busy} onClick={() => void loadResources(entry.subject, entry.unit)}>연결 자료 찾기</button>
                  {resourceKey === key && (
                    <div className="study-resource-list">
                      {resources.length === 0 ? <span className="muted">연결되는 로컬 자료가 없습니다.</span> : resources.map((resource) => <span key={resource.resource_id}><strong>{resource.title}</strong> · {resource.reason}</span>)}
                    </div>
                  )}
                </article>
              );
            })}
          </section>

          <section className="study-plan-section" aria-label="시험과 복습 계획">
            <form className="study-plan-form" onSubmit={submitPlan}>
              <h4>최근 근거로 계획 만들기</h4>
              <label><span>계획 이름 *</span><input value={planTitle} onChange={(event) => setPlanTitle(event.target.value)} maxLength={240} placeholder="예: 중간고사 복습" disabled={busy} /></label>
              <label><span>목표일</span><input type="date" value={targetDate} onChange={(event) => setTargetDate(event.target.value)} disabled={busy} /></label>
              <label><span>부모 메모</span><textarea value={parentNote} onChange={(event) => setParentNote(event.target.value)} maxLength={4000} disabled={busy} /></label>
              <button className="primary-button" type="submit" disabled={busy || !planTitle.trim() || (weakMap?.entries.length ?? 0) === 0}>계획 생성</button>
            </form>
            <div className="study-plan-list">
              {plans.map((plan) => (
                <article key={plan.id}>
                  <div className="study-plan-heading"><strong>{plan.title}</strong>{plan.target_date && <span>{plan.target_date}</span>}</div>
                  {plan.items.map((item, index) => (
                    <div className="study-plan-item" key={`${item.subject}-${item.unit}-${index}`}>
                      <div><strong>{item.subject} · {item.unit}</strong><p>{item.focus}</p></div>
                      <div className="study-plan-actions">
                        <span>{PLAN_STATUS_LABEL[item.status]}</span>
                        <button type="button" className="quiet-button" disabled={busy || item.status === "done"} onClick={() => void setPlanItemStatus(plan, index, "done")}>완료</button>
                        <button type="button" className="quiet-button" disabled={busy || item.status === "skipped"} onClick={() => void setPlanItemStatus(plan, index, "skipped")}>건너뜀</button>
                      </div>
                    </div>
                  ))}
                </article>
              ))}
            </div>
          </section>
        </div>
      )}
    </section>
  );
}
