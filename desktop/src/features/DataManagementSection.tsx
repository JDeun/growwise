import { useMemo, useState } from "react";

import { LAST_CHILD_KEY, useActiveChild } from "../active-child-context";
import { deleteChild, type BackupItem } from "../api";
import "./DataManagementSection.css";

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
  const { children } = useActiveChild();
  const [deleteChildId, setDeleteChildId] = useState("");
  const [deleteConfirmation, setDeleteConfirmation] = useState("");
  const [privacyBusy, setPrivacyBusy] = useState(false);
  const [privacyError, setPrivacyError] = useState<string | null>(null);

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
      if (localStorage.getItem(LAST_CHILD_KEY) === selectedChild.id) {
        localStorage.removeItem(LAST_CHILD_KEY);
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
          <p className="card-label">내 데이터</p>
          <h2>백업과 복원</h2>
          <p className="muted">
            기록을 하나의 백업 파일로 보관할 수 있습니다. 복원하면 저장된 기록을 기준으로 검색 데이터도 다시 준비합니다.
          </p>
        </div>
        <div className="review-actions">
          <button className="quiet-button" type="button" onClick={onImport} disabled={!connected || destructiveBusy}>
            백업 파일 가져오기
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
                  파일로 내보내기
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
          <p className="card-label">개인정보와 삭제</p>
          <h2>아이 데이터 영구 삭제</h2>
          <p className="muted">
            선택한 아이의 현재 기록과 관련된 앱 데이터를 삭제합니다. 이미 만들어 둔 과거 백업 파일에는 해당 기록이 남아 있을 수 있으므로, 완전히 지우려면 백업 파일도 함께 삭제해 주세요.
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
      {selectedChild && (
        <p className="muted">실수로 삭제하지 않도록 <strong>{selectedChild.nickname}</strong>을(를) 그대로 입력해야 삭제 버튼이 활성화됩니다.</p>
      )}
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
