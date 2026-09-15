import { FormEvent, useCallback, useEffect, useState } from "react";

import type { ChildProfile } from "./api";
import {
  createStudyPlan,
  getStudyResources,
  getStudyWeakMap,
  listStudyPlans,
  recordSelfExplanation,
  recordStudyMistake,
  recordStudyProgress,
  recordStudyReflection,
  type MistakeType,
  type StudyPlan,
  type StudyProgressState,
  type StudyResourceRecommendation,
  type StudyWeakMap,
} from "./studyApi";

const PROGRESS_OPTIONS: Array<{ value: StudyProgressState; label: string }> = [
  { value: "planned", label: "예정" },
  { value: "in_progress", label: "학습 중" },
  { value: "review", label: "복습 확인" },
  { value: "revisit", label: "다시 보기" },
  { value: "comfortable", label: "현재는 편안함" },
];

const MISTAKE_OPTIONS: Array<{ value: MistakeType; label: string }> = [
  { value: "concept", label: "개념 연결" },
  { value: "process", label: "풀이 과정" },
  { value: "reading", label: "문제 읽기" },
  { value: "calculation", label: "계산" },
  { value: "attention", label: "주의 전환" },
  { value: "communication", label: "설명/표현" },
  { value: "other", label: "기타" },
];

interface StudyPanelProps {
  child: ChildProfile;
}

export function StudyPanel({ child }: StudyPanelProps) {
  const [subject, setSubject] = useState("");
  const [unit, setUnit] = useState("");
  const [progressState, setProgressState] = useState<StudyProgressState>("in_progress");
  const [progressNote, setProgressNote] = useState("");
  const [mistakeType, setMistakeType] = useState<MistakeType>("concept");
  const [learnerResponse, setLearnerResponse] = useState("");
  const [correctedUnderstanding, setCorrectedUnderstanding] = useState("");
  const [workedWell, setWorkedWell] = useState("");
  const [difficultPoint, setDifficultPoint] = useState("");
  const [nextStep, setNextStep] = useState("");
  const [explanation, setExplanation] = useState("");
  const [openQuestion, setOpenQuestion] = useState("");
  const [planTitle, setPlanTitle] = useState("다음 학습 계획");
  const [planTargetDate, setPlanTargetDate] = useState("");
  const [weakMap, setWeakMap] = useState<StudyWeakMap | null>(null);
  const [resources, setResources] = useState<StudyResourceRecommendation[]>([]);
  const [plans, setPlans] = useState<StudyPlan[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const [map, storedPlans] = await Promise.all([
      getStudyWeakMap(child.id),
      listStudyPlans(child.id),
    ]);
    setWeakMap(map);
    setPlans(storedPlans);
  }, [child.id]);

  useEffect(() => {
    setError(null);
    setNotice(null);
    setResources([]);
    void refresh().catch((refreshError) => {
      setError(refreshError instanceof Error ? refreshError.message : "학습 맥락을 불러오지 못했습니다.");
    });
  }, [refresh]);

  function normalizedContext(): { subject: string; unit: string } | null {
    const nextSubject = subject.trim();
    const nextUnit = unit.trim();
    if (!nextSubject || !nextUnit) {
      setError("과목과 단원을 먼저 입력해 주세요.");
      return null;
    }
    return { subject: nextSubject, unit: nextUnit };
  }

  async function runMutation(action: () => Promise<unknown>, successMessage: string) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await action();
      await refresh();
      setNotice(successMessage);
    } catch (mutationError) {
      setError(mutationError instanceof Error ? mutationError.message : "학습 기록 저장에 실패했습니다.");
    } finally {
      setBusy(false);
    }
  }

  async function handleProgress(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const context = normalizedContext();
    if (!context) return;
    await runMutation(
      () => recordStudyProgress(child.id, {
        ...context,
        state: progressState,
        note: progressNote.trim() || null,
        last_studied_at: new Date().toISOString(),
      }),
      "진도 맥락을 기록했습니다.",
    );
  }

  async function handleMistake(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const context = normalizedContext();
    if (!context) return;
    if (!learnerResponse.trim() && !correctedUnderstanding.trim()) {
      return setError("실수 당시 반응이나 수정된 이해 중 하나는 기록해 주세요.");
    }
    await runMutation(
      () => recordStudyMistake(child.id, {
        ...context,
        mistake_type: mistakeType,
        prompt: null,
        learner_response: learnerResponse.trim() || null,
        corrected_understanding: correctedUnderstanding.trim() || null,
        evidence_ref: null,
      }),
      "실수 기록을 저장했습니다. 한 번의 실수를 약점으로 확정하지 않습니다.",
    );
    setLearnerResponse("");
    setCorrectedUnderstanding("");
  }

  async function handleReflection(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const context = normalizedContext();
    if (!context) return;
    await runMutation(
      () => recordStudyReflection(child.id, {
        ...context,
        worked_well: workedWell.trim() || null,
        difficult_point: difficultPoint.trim() || null,
        next_step: nextStep.trim() || null,
      }),
      "학습 회고를 저장했습니다.",
    );
  }

  async function handleExplanation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const context = normalizedContext();
    if (!context) return;
    if (!explanation.trim()) return setError("아이의 자기설명 내용을 입력해 주세요.");
    await runMutation(
      () => recordSelfExplanation(child.id, {
        ...context,
        explanation: explanation.trim(),
        evidence_refs: [],
        open_question: openQuestion.trim() || null,
      }),
      "자기설명 기록을 저장했습니다.",
    );
    setExplanation("");
    setOpenQuestion("");
  }

  async function handleResources() {
    const context = normalizedContext();
    if (!context) return;
    setBusy(true);
    setError(null);
    try {
      setResources(await getStudyResources(child.id, context.subject, context.unit));
    } catch (resourceError) {
      setError(resourceError instanceof Error ? resourceError.message : "연결 자료를 찾지 못했습니다.");
    } finally {
      setBusy(false);
    }
  }

  async function handlePlan(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!planTitle.trim()) return setError("계획 제목을 입력해 주세요.");
    await runMutation(
      () => createStudyPlan(child.id, {
        title: planTitle.trim(),
        target_date: planTargetDate || null,
        parent_note: "필요한 부분을 확인하되 등수·streak·일일 강제량 없이 진행합니다.",
        max_items: 6,
      }),
      "최근 기록을 바탕으로 학습 계획을 만들었습니다.",
    );
  }

  return (
    <section className="material-section" aria-labelledby="study-tracking-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">STUDY TRACKING · SELF VS SELF</p>
          <h2 id="study-tracking-title">중·고 학습 맥락</h2>
          <p className="muted">점수·등수 대신 진도, 반복되는 어려움, 회고와 자기설명을 연결합니다.</p>
        </div>
        <span className="badge">{child.stage === "high" ? "고등" : "중등"}</span>
      </div>

      <div className="resource-grid">
        <div className="resource-form">
          <p className="card-label">CURRENT UNIT</p>
          <label><span>과목</span><input value={subject} onChange={(event) => setSubject(event.target.value)} placeholder="예: 수학" maxLength={120} /></label>
          <label><span>단원</span><input value={unit} onChange={(event) => setUnit(event.target.value)} placeholder="예: 일차함수" maxLength={240} /></label>
          <button className="quiet-button" type="button" onClick={() => void handleResources()} disabled={busy}>이 단원과 연결된 로컬 자료 찾기</button>
          {resources.map((resource) => <article className="resource-card" key={resource.resource_id}><strong>{resource.title}</strong><p>{resource.reason}</p><small>{resource.source_ref}</small></article>)}
        </div>

        <form className="resource-form" onSubmit={handleProgress}>
          <p className="card-label">PROGRESS</p><h3>진도 상태</h3>
          <label><span>현재 상태</span><select value={progressState} onChange={(event) => setProgressState(event.target.value as StudyProgressState)}>{PROGRESS_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
          <label><span>메모</span><textarea value={progressNote} onChange={(event) => setProgressNote(event.target.value)} placeholder="무엇을 다시 볼지, 어디까지 편안한지 기록" /></label>
          <button className="primary-button" type="submit" disabled={busy}>진도 기록</button>
        </form>
      </div>

      <div className="resource-grid">
        <form className="resource-form" onSubmit={handleMistake}>
          <p className="card-label">MISTAKE EVIDENCE</p><h3>실수 유형 기록</h3>
          <label><span>유형</span><select value={mistakeType} onChange={(event) => setMistakeType(event.target.value as MistakeType)}>{MISTAKE_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
          <label><span>당시 반응/풀이</span><textarea value={learnerResponse} onChange={(event) => setLearnerResponse(event.target.value)} /></label>
          <label><span>수정된 이해</span><textarea value={correctedUnderstanding} onChange={(event) => setCorrectedUnderstanding(event.target.value)} /></label>
          <button className="primary-button" type="submit" disabled={busy}>실수 기록</button>
        </form>

        <form className="resource-form" onSubmit={handleReflection}>
          <p className="card-label">REFLECTION</p><h3>학습 회고</h3>
          <label><span>잘 된 점</span><textarea value={workedWell} onChange={(event) => setWorkedWell(event.target.value)} /></label>
          <label><span>어려웠던 지점</span><textarea value={difficultPoint} onChange={(event) => setDifficultPoint(event.target.value)} /></label>
          <label><span>다음에 해볼 것</span><textarea value={nextStep} onChange={(event) => setNextStep(event.target.value)} /></label>
          <button className="primary-button" type="submit" disabled={busy}>회고 저장</button>
        </form>
      </div>

      <div className="resource-grid">
        <form className="resource-form" onSubmit={handleExplanation}>
          <p className="card-label">SELF EXPLANATION</p><h3>자기설명·근거검증</h3>
          <label><span>자기설명</span><textarea value={explanation} onChange={(event) => setExplanation(event.target.value)} placeholder="아이의 말 그대로 개념이나 풀이 이유를 기록" /></label>
          <label><span>남은 질문</span><textarea value={openQuestion} onChange={(event) => setOpenQuestion(event.target.value)} /></label>
          <button className="primary-button" type="submit" disabled={busy}>자기설명 저장</button>
        </form>

        <article className="resource-list">
          <p className="card-label">WEAK MAP</p><h3>반복 증거 지도</h3>
          <p className="muted">{weakMap?.interpretation ?? "기록을 불러오는 중입니다."}</p>
          {weakMap?.entries.length === 0 && <p className="muted">아직 반복해서 확인할 증거가 없습니다.</p>}
          {weakMap?.entries.map((entry) => <article className="resource-card" key={`${entry.subject}:${entry.unit}`}><strong>{entry.subject} · {entry.unit}</strong><span>관련 기록 {entry.evidence_count}건</span>{entry.recent_difficulties.map((difficulty) => <p key={difficulty}>{difficulty}</p>)}{entry.parent_support_points.map((point) => <small key={point}>{point}</small>)}</article>)}
        </article>
      </div>

      <div className="resource-grid">
        <form className="resource-form" onSubmit={handlePlan}>
          <p className="card-label">STUDY PLAN</p><h3>시험·복습 계획</h3>
          <label><span>계획 제목</span><input value={planTitle} onChange={(event) => setPlanTitle(event.target.value)} maxLength={240} /></label>
          <label><span>목표 날짜(선택)</span><input type="date" value={planTargetDate} onChange={(event) => setPlanTargetDate(event.target.value)} /></label>
          <button className="primary-button" type="submit" disabled={busy}>최근 기록으로 계획 만들기</button>
        </form>
        <article className="resource-list">
          <p className="card-label">SAVED PLANS</p><h3>{plans.length}개</h3>
          {plans.map((plan) => <article className="resource-card" key={plan.id}><strong>{plan.title}</strong>{plan.target_date && <span>{plan.target_date}</span>}{plan.items.map((item) => <p key={`${item.subject}:${item.unit}`}>{item.subject} · {item.unit} — {item.focus}</p>)}</article>)}
        </article>
      </div>

      {notice && <p className="muted" role="status">{notice}</p>}
      {error && <p className="form-error" role="alert">{error}</p>}
    </section>
  );
}
