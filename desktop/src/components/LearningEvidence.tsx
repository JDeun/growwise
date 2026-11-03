import { useEffect, useState } from "react";

import { listResources, type LearningLog, type ResourceRecord } from "../api";
import "./LearningEvidence.css";

export interface LearningEvidenceDraft {
  book_id: string | null;
  ai_hint: string;
  evidence_checked: boolean | null;
  child_reexplanation: string;
}

export const EMPTY_LEARNING_EVIDENCE: LearningEvidenceDraft = {
  book_id: null, ai_hint: "", evidence_checked: null, child_reexplanation: "",
};

export function useLearningBooks(childId: string) {
  const [books, setBooks] = useState<ResourceRecord[]>([]);
  const [bookError, setBookError] = useState<string | null>(null);
  const [bookLoading, setBookLoading] = useState(false);
  useEffect(() => {
    let cancelled = false;
    setBooks([]);
    setBookError(null);
    setBookLoading(Boolean(childId));
    if (!childId) return;
    void listResources(childId).then((items) => {
      if (!cancelled) setBooks(items.filter((item) => item.kind === "book"));
    }).catch(() => {
      if (!cancelled) setBookError("책 목록을 불러오지 못했습니다. 다른 내용은 기록할 수 있습니다.");
    }).finally(() => {
      if (!cancelled) setBookLoading(false);
    });
    return () => { cancelled = true; };
  }, [childId]);
  return { books, bookError, bookLoading };
}

export function LearningEvidenceFields({ value, onChange, books, bookError, bookLoading, disabled }: {
  value: LearningEvidenceDraft;
  onChange: (value: LearningEvidenceDraft) => void;
  books: ResourceRecord[];
  bookError: string | null;
  bookLoading: boolean;
  disabled: boolean;
}) {
  return <div className="learning-evidence-fields">
    <label>
      <span>함께 읽은 책</span>
      <select value={value.book_id ?? ""} disabled={disabled || bookLoading}
        onChange={(event) => onChange({ ...value, book_id: event.target.value || null })}>
        <option value="">연결하지 않음</option>
        {books.map((book) => <option key={book.id} value={book.id}>{book.title}</option>)}
      </select>
      {bookError && <small className="muted">{bookError}</small>}
      {bookLoading && <small className="muted">책 목록을 불러오는 중…</small>}
      {!bookLoading && !bookError && books.length === 0 && <small className="muted">참고 자료에 책을 저장하면 연결할 수 있습니다.</small>}
    </label>
    <label>
      <span>AI가 준 힌트</span>
      <textarea value={value.ai_hint} maxLength={4000} disabled={disabled}
        placeholder="실제로 받은 힌트가 있다면 남겨 주세요."
        onChange={(event) => onChange({ ...value, ai_hint: event.target.value })} />
    </label>
    <label>
      <span>근거 확인 여부</span>
      <select value={value.evidence_checked === null ? "unknown" : String(value.evidence_checked)}
        disabled={disabled} onChange={(event) => onChange({ ...value,
          evidence_checked: event.target.value === "unknown" ? null : event.target.value === "true",
        })}>
        <option value="unknown">기록하지 않음</option>
        <option value="true">확인함</option>
        <option value="false">확인하지 않음</option>
      </select>
    </label>
    <label>
      <span>아이가 다시 설명한 내용</span>
      <textarea value={value.child_reexplanation} maxLength={10000} disabled={disabled}
        placeholder="힌트나 근거를 확인한 뒤 아이가 자기 말로 설명한 내용을 적습니다."
        onChange={(event) => onChange({ ...value, child_reexplanation: event.target.value })} />
    </label>
  </div>;
}

export function LearningEvidenceDetails({ record, books }: {
  record: LearningLog;
  books: ResourceRecord[];
}) {
  if (!record.book_id && !record.ai_hint && !record.child_reexplanation
    && record.evidence_checked == null) return null;
  const book = books.find((item) => item.id === record.book_id);
  return <dl className="learning-evidence-details">
    {record.book_id && <div><dt>함께 읽은 책</dt><dd>{book?.title ?? "연결한 책 · 현재 목록에 없음"}</dd></div>}
    {record.ai_hint && <div><dt>AI가 준 힌트</dt><dd>{record.ai_hint}</dd></div>}
    <div><dt>근거 확인</dt><dd>{record.evidence_checked == null ? "기록하지 않음"
      : record.evidence_checked ? "확인함" : "확인하지 않음"}</dd></div>
    {record.child_reexplanation && <div><dt>아이가 다시 설명한 내용</dt><dd>{record.child_reexplanation}</dd></div>}
  </dl>;
}
