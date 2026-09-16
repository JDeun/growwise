import type { BackupItem } from "../api";

interface DataManagementSectionProps {
  connected: boolean;
  backups: BackupItem[];
  busy: boolean;
  error: string | null;
  notice: string | null;
  onImport: () => void;
  onCreate: () => void;
  onExport: (archiveName: string) => void;
  onRestore: (archiveName: string) => void;
}

export function DataManagementSection({
  connected,
  backups,
  busy,
  error,
  notice,
  onImport,
  onCreate,
  onExport,
  onRestore,
}: DataManagementSectionProps) {
  return (
    <section className="data-management-section">
      <div className="activity-heading">
        <div>
          <p className="card-label">DATA MANAGEMENT</p>
          <h2>백업과 복원</h2>
          <p className="muted">
            Markdown 정본을 portable ZIP으로 보관하고, 복원 시 검색 인덱스를 다시 만듭니다.
          </p>
        </div>
        <div className="review-actions">
          <button className="quiet-button" type="button" onClick={onImport} disabled={!connected || busy}>
            외부 ZIP 가져오기
          </button>
          <button className="quiet-button" type="button" onClick={onCreate} disabled={!connected || busy}>
            {busy ? "처리 중…" : "지금 백업"}
          </button>
        </div>
      </div>
      {error && <p className="form-error" role="alert">{error}</p>}
      {notice && <p className="muted" role="status" aria-live="polite">{notice}</p>}
      {backups.length === 0 ? (
        <p className="muted">아직 만든 백업이 없습니다.</p>
      ) : (
        <div className="quest-list">
          {backups.map((backup) => (
            <article className="quest-card" key={backup.archive}>
              <div>
                <strong>{backup.archive}</strong>
                <span className="status-badge">
                  {Math.max(1, Math.round(backup.size_bytes / 1024))} KB
                </span>
              </div>
              <p>{new Date(backup.modified_at).toLocaleString("ko-KR")}</p>
              <div className="review-actions">
                <button className="quiet-button" type="button" disabled={busy} onClick={() => onExport(backup.archive)}>
                  ZIP 내보내기
                </button>
                <button className="quiet-button" type="button" disabled={busy} onClick={() => onRestore(backup.archive)}>
                  이 백업 복원
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
