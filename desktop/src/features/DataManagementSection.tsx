import { useEffect, useMemo, useState } from "react";

import {
  deleteChild,
  listChildren,
  type BackupItem,
  type ChildProfile,
} from "../api";

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
  const [children, setChildren] = useState<ChildProfile[]>([]);
  const [deleteChildId, setDeleteChildId] = useState("");
  const [deleteConfirmation, setDeleteConfirmation] = useState("");
  const [privacyBusy, setPrivacyBusy] = useState(false);
  const [privacyError, setPrivacyError] = useState<string | null>(null);

  useEffect(() => {
    if (!connected) {
      setChildren([]);
      setDeleteChildId("");
      return;
    }
    let cancelled = false;
    void listChildren()
      .then((items) => {
        if (!cancelled) setChildren(items);
      })
      .catch(() => {
        if (!cancelled) setPrivacyError("삭제할 아이 목록을 불러오지 못했습니다.");
      });
    return () => {
      cancelled = true;
    };
  }, [connected]);

  const selectedChild = useMemo(
    () => children.find((child) => child.id === deleteChildId) ?? null,
    [children, deleteChildId],
  );
  const destructiveBusy = busy || privacyBusy;
  const deletionConfirmed =
    selectedChild !== null && deleteConfirmation.trim() === selectedChild.nickname;

  async function handleDeleteChild() {
    if (!selectedChild || !deletionConfirmed || destructiveBusy) return;
    setPrivacyBusy(true);
    setPrivacyError(null);
    try {
      await deleteChild(selectedChild.id);
      if (localStorage.getItem("growwise:last-child-id") === selectedChild.id) {
        localStorage.removeItem("growwise:last-child-id");
      }
      // A full reload deliberately discards every in-memory child-scoped view/request after purge.
      window.location.reload();
    } catch (deleteError) {
      setPrivacyError(
        deleteError instanceof Error && deleteError.message.trim()
          ? deleteError.message
          : "아이 데이터 삭제에 실패했습니다.",
      );
      setPrivacyBusy(false);
    }
  }

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
          <button className="quiet-button" type="button" onClick={onImport} disabled={!connected || destructiveBusy}>
            외부 ZIP 가져오기
          </button>
          <button className="quiet-button" type="button" onClick={onCreate} disabled={!connected || destructiveBusy}>
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
                <button className="quiet-button" type="button" disabled={destructiveBusy} onClick={() => onExport(backup.archive)}>
                  ZIP 내보내기
                </button>
                <button className="quiet-button" type="button" disabled={destructiveBusy} onClick={() => onRestore(backup.archive)}>
                  이 백업 복원
                </button>
              </div>
            </article>
          ))}
        </div>
      )}

      <div className="activity-heading privacy-danger-zone">
        <div>
          <p className="card-label">PRIVACY</p>
          <h2>아이 데이터 영구 삭제</h2>
          <p className="muted">
            선택한 아이의 현재 기록, 검색 인덱스, 대화, 작업 상태와 체크포인트를 삭제합니다.
            이미 만들어 둔 과거 백업 ZIP에는 해당 데이터가 남아 있을 수 있으므로 필요하면 백업 파일도 직접 폐기해 주세요.
          </p>
        </div>
      </div>
      {privacyError && <p className="form-error" role="alert">{privacyError}</p>}
      <div className="field-grid">
        <label>
          삭제할 아이
          <select
            value={deleteChildId}
            onChange={(event) => {
              setDeleteChildId(event.target.value);
              setDeleteConfirmation("");
              setPrivacyError(null);
            }}
            disabled={!connected || destructiveBusy}
          >
            <option value="">선택해 주세요</option>
            {children.map((child) => (
              <option key={child.id} value={child.id}>{child.nickname}</option>
            ))}
          </select>
        </label>
        <label>
          삭제 확인
          <input
            value={deleteConfirmation}
            onChange={(event) => setDeleteConfirmation(event.target.value)}
            placeholder={selectedChild ? `${selectedChild.nickname} 입력` : "먼저 아이를 선택해 주세요"}
            disabled={!selectedChild || destructiveBusy}
          />
        </label>
      </div>
      <div className="review-actions">
        <button
          className="danger-button"
          type="button"
          disabled={!connected || destructiveBusy || !deletionConfirmed}
          onClick={() => void handleDeleteChild()}
        >
          {privacyBusy ? "삭제 중…" : "아이 데이터 영구 삭제"}
        </button>
      </div>
    </section>
  );
}
