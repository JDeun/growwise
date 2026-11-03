import { useEffect, useRef, useState, type SyntheticEvent } from "react";

import { getConversationEvidence, type ConversationEvidence as Evidence } from "../evidence-api";
import { ExternalSourceLink } from "../components/ExternalSourceLink";
import "./ConversationEvidence.css";

function sourceLabel(sourceId: string, index: number): string {
  if (sourceId.startsWith("record:")) return `기록 ${index + 1}`;
  if (sourceId.startsWith("chunk:")) return `자료 근거 ${index + 1}`;
  if (sourceId.startsWith("resource:")) return `참고 자료 ${index + 1}`;
  return `연결 근거 ${index + 1}`;
}

export function ConversationEvidenceContent({ evidence }: { evidence: Evidence }) {
  return (
    <div className="conversation-original-content">
      <strong>{evidence.title}</strong>
      {evidence.occurred_at && (
        <time dateTime={evidence.occurred_at}>{new Date(evidence.occurred_at).toLocaleString("ko-KR")}</time>
      )}
      <pre tabIndex={0} aria-label="원본 기록 본문">{evidence.body}</pre>
      {evidence.source_url && <ExternalSourceLink href={evidence.source_url}>외부 원문 열기</ExternalSourceLink>}
      <small>현재 저장된 원본의 발췌입니다. 답변 이후 수정되었을 수 있습니다.</small>
    </div>
  );
}

function OriginalDisclosure({ childId, sourceId, label }: {
  childId: string; sourceId: string; label: string;
}) {
  const [evidence, setEvidence] = useState<Evidence | null>(null);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(false);
  const request = useRef(0);
  useEffect(() => () => { request.current += 1; }, []);

  async function toggle(event: SyntheticEvent<HTMLDetailsElement>) {
    const generation = ++request.current;
    setEvidence(null);
    setError(false);
    if (!event.currentTarget.open) { setLoading(false); return; }
    setLoading(true);
    try {
      const original = await getConversationEvidence(childId, sourceId);
      if (request.current === generation) setEvidence(original);
    } catch {
      if (request.current === generation) setError(true);
    } finally {
      if (request.current === generation) setLoading(false);
    }
  }

  return (
    <details className="conversation-original" onToggle={(event) => void toggle(event)}>
      <summary>{label} · 원본 보기</summary>
      {loading && <p role="status">현재 원본을 확인하는 중…</p>}
      {error && <p role="alert">원본이 삭제되었거나 현재 아이에게 공유되지 않았습니다. 닫았다 다시 열어 확인해 주세요.</p>}
      {evidence && <ConversationEvidenceContent evidence={evidence} />}
    </details>
  );
}

export function ConversationEvidence({ sourceIds, childId }: {
  sourceIds: string[]; childId: string | null;
}) {
  return (
    <div className="conversation-evidence">
      <strong>연결된 원본 근거</strong>
      {sourceIds.length > 0 && childId ? (
        <div className="conversation-originals" aria-label={`원본 근거 ${sourceIds.length}건`}>
          {[...new Set(sourceIds)].map((sourceId, index) => (
            <OriginalDisclosure key={`${childId}:${sourceId}`} childId={childId}
              sourceId={sourceId} label={sourceLabel(sourceId, index)} />
          ))}
        </div>
      ) : <p className="muted">연결된 원본 근거가 없습니다.</p>}
    </div>
  );
}
