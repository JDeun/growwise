import type { BoardBookRecommendations, InfantObservationHints } from "../api";

interface InfantGuidanceSectionProps {
  observationHints: InfantObservationHints | null;
  boardBooks: BoardBookRecommendations | null;
  loading: boolean;
  error: string | null;
  onLoad: () => void;
}

function bookSourceLabel(source: string): string {
  if (source === "local_library") return "내 자료실에 저장된 책";
  if (source === "public_discovery") return "공개 도서 후보 · 상세 적합성 확인 필요";
  return "오프라인 범주형 제안";
}

export function InfantGuidanceSection({
  observationHints,
  boardBooks,
  loading,
  error,
  onLoad,
}: InfantGuidanceSectionProps) {
  const hasPublicBookCandidates =
    boardBooks?.recommendations.some((book) => book.source === "public_discovery") ?? false;

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
                <p className="card-label">{bookSourceLabel(book.source)}</p>
                <strong>{book.title}</strong>
                <p>{book.reason}</p>
                <small>{book.read_aloud_tip}</small>
              </article>
            ))}
            {hasPublicBookCandidates && (
              <p className="muted">
                공개 도서 후보 검색에는 아이 ID·관찰 원문·사진을 보내지 않습니다. 관심사에서
                만든 일반 검색어만 공개 도서 API에 사용하며, 후보는 자동 저장하지 않습니다.
              </p>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
