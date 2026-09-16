import type { BoardBookRecommendations, InfantObservationHints } from "../api";

interface InfantGuidanceSectionProps {
  observationHints: InfantObservationHints | null;
  boardBooks: BoardBookRecommendations | null;
  loading: boolean;
  error: string | null;
  onLoad: () => void;
}

export function InfantGuidanceSection({
  observationHints,
  boardBooks,
  loading,
  error,
  onLoad,
}: InfantGuidanceSectionProps) {
  return (
    <section className="infant-guidance-section">
      <div className="activity-heading">
        <div>
          <p className="card-label">INFANT OBSERVATION GUIDE</p>
          <h3>관찰 힌트와 보드북 연결</h3>
          <p className="muted">진단 체크리스트가 아니라 일상에서 무엇을 살펴볼지 돕습니다.</p>
        </div>
        <button className="quiet-button" type="button" onClick={onLoad} disabled={loading}>
          {loading ? "불러오는 중…" : "관찰 힌트·책 보기"}
        </button>
      </div>
      {error && <p className="form-error" role="alert">{error}</p>}
      {(observationHints || boardBooks) && (
        <div className="resource-grid">
          <div className="resource-list">
            <p className="card-label">OBSERVATION HINTS</p>
            <h3>{observationHints?.hints.length ?? 0}개 영역</h3>
            {observationHints?.hints.map((hint) => (
              <article className="resource-card" key={hint.domain}>
                <strong>{hint.domain}</strong>
                <p>{hint.cue}</p>
                <small>{hint.rationale}</small>
              </article>
            ))}
            {observationHints && <p className="muted">{observationHints.source} · 진단용 아님</p>}
          </div>
          <div className="resource-list">
            <p className="card-label">BOARD BOOKS</p>
            <h3>{boardBooks?.recommendations.length ?? 0}권</h3>
            {boardBooks?.recommendations.map((book) => (
              <article className="resource-card" key={`${book.resource_id ?? book.title}-${book.title}`}>
                <strong>{book.title}</strong>
                <p>{book.reason}</p>
                <small>{book.read_aloud_tip}</small>
              </article>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
