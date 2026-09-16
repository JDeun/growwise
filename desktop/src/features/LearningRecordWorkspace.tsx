import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { useActiveChild } from "../active-child-context";
import {
  createLearningRecord,
  listLearningRecords,
  type ExperienceAxis,
  type LearningLog,
  type LearningRecordKind,
} from "../api";
import { AXIS_OPTIONS } from "../presentation";
import "./LearningRecordWorkspace.css";

const AI_POLL_INTERVAL_MS = 1500;

type IndependentKind = Exclude<
  LearningRecordKind,
  "observation" | "photo_activity" | "material_use"
>;

const KIND_OPTIONS: Array<{ value: IndependentKind; label: string; hint: string }> = [
  { value: "reading_reflection", label: "독서·독서감상", hint: "읽은 책, 감상문, 인상 깊은 장면" },
  { value: "diary", label: "일기", hint: "아이의 일기나 하루 회고" },
  { value: "institution", label: "학교·학원·교육기관", hint: "학교 수업, 학원, 문화센터, 온라인 수업" },
  { value: "self_study", label: "자율학습", hint: "스스로 찾아본 주제나 연습" },
  { value: "assignment", label: "과제·프로젝트", hint: "숙제, 발표, 만들기, 프로젝트" },
  { value: "other", label: "기타 학습", hint: "위 유형에 들어가지 않는 학습 경험" },
];

const AI_LABEL: Record<string, string> = {
  not_requested: "직접 기록",
  queued: "AI 보강 대기",
  running: "AI 보강 중",
  completed: "AI 보강 완료",
  failed: "AI 보강 실패 · 원본 보존",
  skipped: "AI 보강 생략",
};

function kindLabel(kind: LearningRecordKind): string {
  return KIND_OPTIONS.find((item) => item.value === kind)?.label ?? "학습 기록";
}

function displayDate(record: LearningLog): string {
  const value = record.occurred_at ?? record.created_at;
  return value ? new Date(value).toLocaleDateString("ko-KR") : "날짜 없음";
}

export function LearningRecordWorkspace({ active }: { active: boolean }) {
  const {
    children,
    activeChildId: childId,
    selectChild,
    syncRememberedChild,
  } = useActiveChild();
  const [records, setRecords] = useState<LearningLog[]>([]);
  const [kind, setKind] = useState<IndependentKind>("reading_reflection");
  const [title, setTitle] = useState("");
  const [date, setDate] = useState("");
  const [subject, setSubject] = useState("");
  const [institution, setInstitution] = useState("");
  const [summary, setSummary] = useState("");
  const [learnerWork, setLearnerWork] = useState("");
  const [process, setProcess] = useState("");
  const [interest, setInterest] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [nextActivity, setNextActivity] = useState("");
  const [tags, setTags] = useState("");
  const [axes, setAxes] = useState<ExperienceAxis[]>([]);
  const [sharedChildIds, setSharedChildIds] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const siblings = useMemo(
    () => children.filter((child) => child.id !== childId),
    [children, childId],
  );
  const selectedKind = KIND_OPTIONS.find((item) => item.value === kind) ?? KIND_OPTIONS[0];
  const hasPendingAi = useMemo(
    () => records.some((record) => record.ai_status === "queued" || record.ai_status === "running"),
    [records],
  );

  const loadRecords = useCallback(async (targetChildId: string) => {
    if (!targetChildId) {
      setRecords([]);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setRecords(await listLearningRecords(targetChildId));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "학습 기록을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!active) return;
    syncRememberedChild();
  }, [active, syncRememberedChild]);

  useEffect(() => {
    if (!active) return;
    setSharedChildIds([]);
    setNotice(null);
    setRecords([]);
    if (!childId) return;
    void loadRecords(childId);
  }, [active, childId, loadRecords]);

  useEffect(() => {
    if (!active || !childId || !hasPendingAi) return;
    let cancelled = false;
    const poll = () => {
      void listLearningRecords(childId)
        .then((nextRecords) => {
          if (!cancelled) setRecords(nextRecords);
        })
        .catch(() => undefined);
    };
    const timer = window.setInterval(poll, AI_POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [active, childId, hasPendingAi]);

  function toggleAxis(axis: ExperienceAxis) {
    setAxes((current) =>
      current.includes(axis) ? current.filter((item) => item !== axis) : [...current, axis],
    );
  }

  function toggleSharedChild(targetId: string) {
    setSharedChildIds((current) =>
      current.includes(targetId)
        ? current.filter((item) => item !== targetId)
        : [...current, targetId],
    );
  }

  function resetForm() {
    setTitle("");
    setDate("");
    setSubject("");
    setInstitution("");
    setSummary("");
    setLearnerWork("");
    setProcess("");
    setInterest("");
    setDifficulty("");
    setNextActivity("");
    setTags("");
    setAxes([]);
    setSharedChildIds([]);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!childId || !title.trim() || !summary.trim()) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const occurredAt = date ? new Date(`${date}T12:00:00`).toISOString() : null;
      const record = await createLearningRecord(childId, {
        kind,
        title: title.trim(),
        occurred_at: occurredAt,
        subject: subject.trim() || null,
        institution: institution.trim() || null,
        summary: summary.trim(),
        learner_work: learnerWork.trim() || null,
        process: process.trim() || null,
        interest: interest.trim() || null,
        difficulty_note: difficulty.trim() || null,
        next_activity: nextActivity.trim() || null,
        tags: tags.split(",").map((item) => item.trim()).filter(Boolean),
        experience_axes: axes,
        shared_child_ids: sharedChildIds,
      });
      setRecords((current) => [record, ...current.filter((item) => item.id !== record.id)]);
      setNotice("학습 기록을 저장했습니다. AI 보강을 사용 중이면 뒤에서 태그와 다음 맥락을 정리합니다.");
      resetForm();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "학습 기록 저장에 실패했습니다.");
    } finally {
      setBusy(false);
    }
  }

  if (!active) return null;

  return (
    <section className="learning-record-workspace" aria-labelledby="learning-record-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">LEARNING RECORDS</p>
          <h2 id="learning-record-title">GrowWise 밖에서 한 학습도 같은 성장 맥락에 연결합니다.</h2>
          <p className="muted">
            독서감상문, 일기, 학교·학원 수업, 자율학습, 과제를 기록합니다. 저장은 즉시 끝나고
            AI 정리는 선택적으로 백그라운드에서 진행됩니다.
          </p>
        </div>
        <span className="badge">Closed Loop</span>
      </div>

      {children.length === 0 ? (
        <p className="muted">먼저 홈에서 아이 프로필을 만들어 주세요.</p>
      ) : (
        <>
          <label className="learning-child-picker">
            <span>아이</span>
            <select
              value={childId}
              onChange={(event) => selectChild(event.target.value)}
              disabled={busy}
            >
              {children.map((child) => (
                <option key={child.id} value={child.id}>{child.nickname}</option>
              ))}
            </select>
          </label>

          <form className="learning-record-form" onSubmit={submit}>
            <fieldset className="learning-kind-picker">
              <legend>무엇을 기록하나요?</legend>
              <div>
                {KIND_OPTIONS.map((item) => (
                  <label key={item.value} className={kind === item.value ? "selected" : ""}>
                    <input
                      type="radio"
                      name="learning-kind"
                      value={item.value}
                      checked={kind === item.value}
                      onChange={() => setKind(item.value)}
                      disabled={busy}
                    />
                    <span><strong>{item.label}</strong><small>{item.hint}</small></span>
                  </label>
                ))}
              </div>
            </fieldset>

            <div className="learning-record-two-column">
              <label><span>제목 *</span><input value={title} onChange={(event) => setTitle(event.target.value)} maxLength={500} placeholder="예: 어린 왕자 독서감상" disabled={busy} /></label>
              <label><span>학습한 날짜</span><input type="date" value={date} onChange={(event) => setDate(event.target.value)} disabled={busy} /></label>
              <label><span>과목·영역</span><input value={subject} onChange={(event) => setSubject(event.target.value)} maxLength={200} placeholder="예: 국어, 수학, 미술" disabled={busy} /></label>
              <label><span>학교·학원·기관</span><input value={institution} onChange={(event) => setInstitution(event.target.value)} maxLength={500} placeholder="예: 학교 과학 수업, 피아노 학원" disabled={busy} /></label>
            </div>

            <label><span>무엇을 했고 무엇을 배웠나요? *</span><textarea value={summary} onChange={(event) => setSummary(event.target.value)} maxLength={10000} placeholder="부모가 확인한 사실이나 아이가 설명한 내용을 기록하세요." disabled={busy} /></label>
            <label><span>{kind === "diary" ? "아이의 일기" : kind === "reading_reflection" ? "독서감상문·아이의 글" : "아이 결과물·답변(선택)"}</span><textarea value={learnerWork} onChange={(event) => setLearnerWork(event.target.value)} maxLength={20000} placeholder="아이가 직접 쓴 글이나 답변이 있으면 원문 그대로 남길 수 있습니다." disabled={busy} /></label>

            <div className="learning-record-two-column">
              <label><span>학습 과정</span><textarea value={process} onChange={(event) => setProcess(event.target.value)} disabled={busy} /></label>
              <label><span>흥미를 보인 점</span><textarea value={interest} onChange={(event) => setInterest(event.target.value)} disabled={busy} /></label>
              <label><span>어려워한 점</span><textarea value={difficulty} onChange={(event) => setDifficulty(event.target.value)} disabled={busy} /></label>
              <label><span>다음에 이어볼 것</span><textarea value={nextActivity} onChange={(event) => setNextActivity(event.target.value)} disabled={busy} /></label>
            </div>

            <label><span>태그(쉼표로 구분)</span><input value={tags} onChange={(event) => setTags(event.target.value)} placeholder="예: 우주, 독서, 질문" disabled={busy} /></label>

            <fieldset className="learning-axis-picker">
              <legend>경험·학습 축(선택)</legend>
              <div>
                {AXIS_OPTIONS.map((option) => (
                  <button key={option.value} type="button" className={`axis-chip ${axes.includes(option.value) ? "active" : ""}`} aria-pressed={axes.includes(option.value)} onClick={() => toggleAxis(option.value)} disabled={busy}>{option.label}</button>
                ))}
              </div>
            </fieldset>

            {siblings.length > 0 && (
              <fieldset className="learning-shared-children">
                <legend>같이 한 아이와 연결(선택)</legend>
                <p className="muted">같은 기록을 복제하지 않고 여러 아이 문맥에 연결합니다.</p>
                <div>
                  {siblings.map((child) => (
                    <label key={child.id}><input type="checkbox" checked={sharedChildIds.includes(child.id)} onChange={() => toggleSharedChild(child.id)} disabled={busy} /><span>{child.nickname}</span></label>
                  ))}
                </div>
              </fieldset>
            )}

            {error && <p className="form-error" role="alert">{error}</p>}
            {notice && <p className="learning-record-notice" role="status">{notice}</p>}
            <button className="primary-button" type="submit" disabled={busy || !title.trim() || !summary.trim()}>{busy ? "저장 중…" : `${selectedKind.label} 저장`}</button>
          </form>

          <section className="learning-record-history" aria-labelledby="learning-history-title">
            <div className="section-heading compact"><div><p className="eyebrow">HISTORY</p><h3 id="learning-history-title">최근 학습 기록</h3></div><span className="badge">{records.length}건</span></div>
            {loading ? <p className="muted">기록을 불러오는 중…</p> : records.length === 0 ? <p className="muted">아직 별도 학습 기록이 없습니다.</p> : (
              <div className="learning-record-list">
                {records.map((record) => (
                  <article key={record.id} className="learning-record-card">
                    <div className="learning-record-card-heading"><div><span>{kindLabel(record.record_kind ?? "other")}</span><strong>{record.title ?? "제목 없는 기록"}</strong></div><small>{displayDate(record)}</small></div>
                    {(record.subject || record.institution) && <p className="learning-record-meta">{[record.subject, record.institution].filter(Boolean).join(" · ")}</p>}
                    <p>{record.parent_observation}</p>
                    {record.learner_work && <details><summary>아이의 글·결과물 보기</summary><p className="learning-work-text">{record.learner_work}</p></details>}
                    <div className="learning-record-tags"><span>{AI_LABEL[record.ai_status ?? "not_requested"] ?? record.ai_status}</span>{record.interest && <span>흥미 · {record.interest}</span>}{record.difficulty_note && <span>어려움 · {record.difficulty_note}</span>}</div>
                  </article>
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </section>
  );
}
