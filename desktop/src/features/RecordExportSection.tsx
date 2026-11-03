import { useEffect, useState, type FormEvent } from "react";

import { exportChildRecords, type ChildProfile } from "../api";

export function recordExportPeriod(start: string, end: string): { startDate: string | null; endDate: string | null } {
  for (const value of [start, end]) {
    if (!value) continue;
    const parsed = new Date(`${value}T00:00:00Z`);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || Number.isNaN(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== value) {
      throw new Error("기록 내보내기 날짜를 확인해 주세요.");
    }
  }
  if (start && end && start > end) throw new Error("종료일은 시작일 이후로 선택해 주세요.");
  if (start && end && (Date.parse(end) - Date.parse(start)) / 86400000 > 36600) {
    throw new Error("한 번에 내보낼 기간은 36,600일 이내로 선택해 주세요.");
  }
  return { startDate: start || null, endDate: end || null };
}

export function RecordExportSection({ children, currentChildId, connected, busy, onBusyChange }: {
  children: ChildProfile[];
  currentChildId: string | null;
  connected: boolean;
  busy: boolean;
  onBusyChange: (busy: boolean) => void;
}) {
  const [childId, setChildId] = useState(currentChildId ?? "");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  useEffect(() => {
    setChildId((current) => children.some((child) => child.id === current)
      ? current : children.some((child) => child.id === currentChildId) ? currentChildId ?? "" : "");
  }, [children, currentChildId]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const selected = children.find((child) => child.id === childId);
    if (!connected || busy || exporting || !selected) return;
    setError(null);
    setNotice(null);
    let period;
    try { period = recordExportPeriod(start, end); }
    catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); return; }
    setExporting(true);
    onBusyChange(true);
    try {
      const path = await exportChildRecords(selected.id, period.startDate, period.endDate);
      setNotice(path ? `${selected.nickname}의 선택 기록 ZIP을 저장했습니다: ${path}` : "파일 저장을 취소했습니다.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "선택 기록 내보내기에 실패했습니다.");
    } finally {
      setExporting(false);
      onBusyChange(false);
    }
  }

  const disabled = !connected || busy || exporting;
  return (
    <section className="record-export-section data-section-divider" aria-labelledby="record-export-title">
      <h2 id="record-export-title">선택한 기록 내보내기</h2>
      <p className="muted">아이와 기간을 골라 원본 Markdown과 관련 첨부 파일을 ZIP으로 저장합니다. 이 ZIP은 전체 앱 복원용 백업이 아닙니다.</p>
      <p className="muted">개인 기록과 사진이 원문 그대로 포함될 수 있습니다. 공유하기 전에 내용을 확인해 주세요.</p>
      <form className="record-export-form" onSubmit={(event) => void submit(event)}>
        <div className="field-grid">
          <label>내보낼 아이<select value={childId} disabled={disabled} onChange={(event) => { setChildId(event.target.value); setNotice(null); setError(null); }}>
            <option value="">아이를 선택해 주세요</option>
            {children.map((child) => <option key={child.id} value={child.id}>{child.nickname}</option>)}
          </select></label>
          <label>시작일(선택)<input type="date" value={start} disabled={disabled} onChange={(event) => setStart(event.target.value)} /></label>
          <label>종료일(선택)<input type="date" value={end} disabled={disabled} min={start || undefined} onChange={(event) => setEnd(event.target.value)} /></label>
        </div>
        <p className="muted record-export-help">날짜를 비우면 전체 기간입니다. 시작일과 종료일을 모두 포함하며, 아이 프로필과 선택한 기록에 필요한 참고 자료도 함께 담습니다.</p>
        <button className="quiet-button" type="submit" disabled={disabled || !childId}>{exporting ? "기록 ZIP 준비·저장 중…" : "선택 기록 내보내기"}</button>
        {error && <p className="form-error" role="alert">{error}</p>}
        {notice && <p className="muted" role="status">{notice}</p>}
      </form>
    </section>
  );
}
