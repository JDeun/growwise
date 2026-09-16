import { ChangeEvent, useCallback, useEffect, useRef, useState } from "react";

import { useActiveChild } from "../active-child-context";
import {
  commitPhotoRecord,
  createPhotoRecord,
  getPhotoAsset,
  listPhotoRecords,
  type PhotoActivityRecord,
  type PhotoAsset,
  type PhotoRecordStatus,
  type PhotoUploadInput,
} from "../api";
import "./PhotoActivityWorkspace.css";

const MAX_FILES = 8;
const MAX_FILE_BYTES = 15 * 1024 * 1024;
const MAX_TOTAL_BYTES = 60 * 1024 * 1024;
const POLL_INTERVAL_MS = 2500;
const ACCEPTED_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

const STATUS_LABEL: Record<PhotoRecordStatus, string> = {
  queued: "대기 중",
  processing: "사진 분석 중",
  draft: "검토 필요",
  committed: "기록 완료",
  failed: "처리 중단",
  discarded: "사용 안 함",
};

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error(`${file.name} 파일을 읽지 못했습니다.`));
    reader.onload = () => {
      const value = String(reader.result ?? "");
      const comma = value.indexOf(",");
      if (comma < 0) {
        reject(new Error(`${file.name} 파일 인코딩에 실패했습니다.`));
        return;
      }
      resolve(value.slice(comma + 1));
    };
    reader.readAsDataURL(file);
  });
}

function messageFrom(error: unknown): string {
  if (error instanceof Error) return error.message;
  return typeof error === "string" ? error : "사진 기록 처리에 실패했습니다.";
}

function isBackgroundRecord(record: PhotoActivityRecord): boolean {
  return record.status === "queued" || record.status === "processing";
}

type Props = { active: boolean };

export function PhotoActivityWorkspace({ active }: Props) {
  const {
    children,
    activeChildId: childId,
    selectChild,
    syncRememberedChild,
  } = useActiveChild();
  const recordsRequestId = useRef(0);
  const [sharedChildIds, setSharedChildIds] = useState<string[]>([]);
  const [records, setRecords] = useState<PhotoActivityRecord[]>([]);
  const [files, setFiles] = useState<File[]>([]);
  const [previews, setPreviews] = useState<string[]>([]);
  const [storedPreviews, setStoredPreviews] = useState<string[]>([]);
  const [context, setContext] = useState("");
  const [manualObservation, setManualObservation] = useState("");
  const [aiAssist, setAiAssist] = useState(true);
  const [draft, setDraft] = useState<PhotoActivityRecord | null>(null);
  const [draftAssets, setDraftAssets] = useState<PhotoAsset[]>([]);
  const [editedObservation, setEditedObservation] = useState("");
  const [pendingRecordId, setPendingRecordId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const refreshRecords = useCallback(async (targetChildId: string) => {
    const requestId = ++recordsRequestId.current;
    if (!targetChildId) {
      setRecords([]);
      return [] as PhotoActivityRecord[];
    }
    const nextRecords = await listPhotoRecords(targetChildId);
    if (requestId !== recordsRequestId.current) return [] as PhotoActivityRecord[];
    setRecords(nextRecords);
    return nextRecords;
  }, []);

  useEffect(() => {
    if (!active) {
      recordsRequestId.current += 1;
      return;
    }
    syncRememberedChild();
  }, [active, syncRememberedChild]);

  useEffect(() => {
    if (!active) return;
    setSharedChildIds([]);
    setRecords([]);
    setFiles([]);
    setStoredPreviews([]);
    setContext("");
    setManualObservation("");
    setDraft(null);
    setDraftAssets([]);
    setEditedObservation("");
    setPendingRecordId(null);
    setError(null);
    setNotice(null);
    void refreshRecords(childId).catch((loadError) => setError(messageFrom(loadError)));
  }, [active, childId, refreshRecords]);

  useEffect(() => {
    const urls = files.map((file) => URL.createObjectURL(file));
    setPreviews(urls);
    return () => urls.forEach((url) => URL.revokeObjectURL(url));
  }, [files]);

  useEffect(() => {
    if (!active || !childId || !records.some(isBackgroundRecord)) return;
    let cancelled = false;

    const check = async () => {
      try {
        const nextRecords = await refreshRecords(childId);
        if (cancelled) return;
        if (!pendingRecordId) return;
        const pending = nextRecords.find((record) => record.id === pendingRecordId);
        if (!pending) return;
        if (pending.status === "draft") {
          setDraft(pending);
          setEditedObservation(pending.generated_observation);
          setPendingRecordId(null);
          setNotice(
            pending.generation_mode === "llm_photo_synthesis"
              ? "AI 보조 초안이 준비되었습니다. 실제 경험과 맞는지 확인하세요."
              : "AI를 사용할 수 없어 직접 기록 모드로 전환했습니다. 사진과 부모 입력은 그대로 보존되었습니다.",
          );
        } else if (pending.status === "failed") {
          setPendingRecordId(null);
          setError(
            "사진 기록의 로컬 처리도 완료하지 못했습니다. 원본 사진은 보관되어 있으므로 다시 열어 확인할 수 있습니다.",
          );
        }
      } catch (pollError) {
        if (!cancelled) setError(messageFrom(pollError));
      }
    };

    const timer = window.setInterval(() => void check(), POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [active, childId, pendingRecordId, records, refreshRecords]);

  function handleChildChange(event: ChangeEvent<HTMLSelectElement>) {
    selectChild(event.target.value);
  }

  function toggleSharedChild(targetChildId: string) {
    setSharedChildIds((current) =>
      current.includes(targetChildId)
        ? current.filter((id) => id !== targetChildId)
        : [...current, targetChildId],
    );
  }

  function handleFiles(event: ChangeEvent<HTMLInputElement>) {
    const selected = Array.from(event.target.files ?? []);
    setError(null);
    setNotice(null);
    if (selected.length > MAX_FILES) {
      setError(`사진은 한 기록에 최대 ${MAX_FILES}장까지 선택할 수 있습니다.`);
      event.target.value = "";
      return;
    }
    const invalid = selected.find(
      (file) => !ACCEPTED_TYPES.has(file.type) || file.size > MAX_FILE_BYTES,
    );
    if (invalid) {
      setError("JPEG, PNG, WebP 형식의 15MB 이하 사진만 사용할 수 있습니다.");
      event.target.value = "";
      return;
    }
    const totalBytes = selected.reduce((sum, file) => sum + file.size, 0);
    if (totalBytes > MAX_TOTAL_BYTES) {
      setError("한 기록에 선택한 사진의 전체 용량은 60MB 이하여야 합니다.");
      event.target.value = "";
      return;
    }
    setFiles(selected);
    setStoredPreviews([]);
    setDraft(null);
    setDraftAssets([]);
    setEditedObservation("");
    setPendingRecordId(null);
  }

  async function handleCreate() {
    if (!childId || files.length === 0 || busy || pendingRecordId) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const uploads: PhotoUploadInput[] = await Promise.all(
        files.map(async (file) => ({
          filename: file.name,
          mime_type: file.type,
          data_base64: await fileToBase64(file),
        })),
      );
      const result = await createPhotoRecord(childId, uploads, {
        userContext: context.trim() || undefined,
        manualObservation: manualObservation.trim() || undefined,
        aiAssist,
        sharedChildIds,
      });
      setDraftAssets(result.assets);
      setStoredPreviews([]);
      await refreshRecords(childId);

      if (result.record.status === "draft") {
        setDraft(result.record);
        setEditedObservation(result.record.generated_observation);
        setPendingRecordId(null);
        setNotice(
          result.record.generation_mode === "manual_photo_diary"
            ? "사진을 저장했습니다. 작성한 내용을 확인한 뒤 기록으로 확정하세요."
            : "사진을 저장했습니다. AI를 사용할 수 없어 직접 기록 가능한 초안으로 열었습니다.",
        );
        return;
      }

      setPendingRecordId(result.record.id);
      setDraft(null);
      setEditedObservation("");
      setNotice(
        "사진을 안전하게 저장했습니다. AI 보조는 백그라운드에서 진행됩니다. 다른 작업공간을 사용해도 됩니다.",
      );
    } catch (createError) {
      setError(messageFrom(createError));
    } finally {
      setBusy(false);
    }
  }

  async function handleCommit() {
    if (!draft || draft.status !== "draft" || !editedObservation.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      await commitPhotoRecord(draft.id, editedObservation.trim());
      setNotice(
        sharedChildIds.length > 0
          ? "사진 기록을 저장했습니다. 함께 선택한 아이의 기록에서도 같은 원본을 링크로 볼 수 있습니다."
          : "검토한 사진 기록을 관찰 타임라인에 저장했습니다.",
      );
      setDraft(null);
      setDraftAssets([]);
      setStoredPreviews([]);
      setEditedObservation("");
      setContext("");
      setManualObservation("");
      setFiles([]);
      setPendingRecordId(null);
      await refreshRecords(childId);
    } catch (commitError) {
      setError(messageFrom(commitError));
    } finally {
      setBusy(false);
    }
  }

  async function reopenDraft(record: PhotoActivityRecord) {
    if (record.status !== "draft" || busy) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const contents = await Promise.all(
        record.photo_asset_ids.map((assetId) => getPhotoAsset(record.child_id, assetId)),
      );
      setDraft(record);
      setDraftAssets(contents.map((content) => content.asset));
      setStoredPreviews(
        contents.map(
          (content) => `data:${content.asset.mime_type};base64,${content.data_base64}`,
        ),
      );
      setEditedObservation(record.generated_observation);
      setFiles([]);
      setContext(record.user_context ?? "");
      setManualObservation(record.generated_observation);
      setPendingRecordId(null);
      setNotice("저장된 초안을 열었습니다. 실제 경험과 맞는지 확인한 뒤 기록으로 확정하세요.");
    } catch (loadError) {
      setError(messageFrom(loadError));
    } finally {
      setBusy(false);
    }
  }

  if (!active) return null;

  const visiblePreviews = previews.length > 0 ? previews : storedPreviews;
  const hasBackgroundWork = records.some(isBackgroundRecord);
  const shareCandidates = children.filter((child) => child.id !== childId);

  return (
    <main className="photo-workspace app-shell" aria-labelledby="photo-workspace-title">
      <section className="workspace photo-workspace-card">
        <div className="section-heading">
          <div>
            <p className="card-label">사진 활동 기록</p>
            <h2 id="photo-workspace-title">사진 일기와 활동 기록</h2>
            <p className="muted">
              사진과 부모가 직접 쓴 글만으로도 완전한 기록을 만들 수 있습니다. AI는 원할 때 장면
              설명과 초안 작성을 돕는 보조 기능이며, 사용할 수 없어도 기록 기능은 그대로 동작합니다.
            </p>
          </div>
        </div>

        <div className="photo-privacy-note">
          <strong>사진은 로컬에 보관됩니다</strong>
          <p>
            원본은 GrowWise 관리 폴더에 저장되고 정확한 GPS 좌표는 기록하지 않습니다. AI 보조를
            켜면 로컬 모델이 백그라운드에서 처리하며, 느린 컴퓨터에서는 몇 분이 걸려도 앱을 계속
            사용할 수 있습니다.
          </p>
        </div>

        {hasBackgroundWork && (
          <div className="photo-privacy-note" role="status" aria-live="polite">
            <strong>AI 보조 작업 진행 중</strong>
            <p>앱을 계속 사용할 수 있습니다. 실패해도 사진과 부모 입력은 직접 편집 가능한 초안으로 남습니다.</p>
          </div>
        )}

        <label className="photo-field">
          <span>기본 아이</span>
          <select
            value={childId}
            onChange={handleChildChange}
            disabled={busy || children.length === 0}
          >
            {children.length === 0 && <option value="">먼저 아이 프로필을 만들어주세요</option>}
            {children.map((child) => (
              <option key={child.id} value={child.id}>
                {child.nickname}
              </option>
            ))}
          </select>
        </label>

        {shareCandidates.length > 0 && (
          <fieldset className="photo-field" disabled={busy || pendingRecordId !== null}>
            <legend>같이 연결할 아이 · 선택</legend>
            <p className="muted">같은 원본을 복사하지 않고 해당 아이의 기록에 링크로 연결합니다.</p>
            {shareCandidates.map((child) => (
              <label key={child.id}>
                <input
                  type="checkbox"
                  checked={sharedChildIds.includes(child.id)}
                  onChange={() => toggleSharedChild(child.id)}
                />{" "}
                {child.nickname}
              </label>
            ))}
          </fieldset>
        )}

        <label className="photo-field">
          <span>활동 사진 · 최대 {MAX_FILES}장 / 전체 60MB</span>
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            multiple
            onChange={handleFiles}
            disabled={!childId || busy || pendingRecordId !== null}
          />
        </label>

        {visiblePreviews.length > 0 && (
          <div className="photo-preview-grid" aria-label="활동 사진 미리보기">
            {visiblePreviews.map((url, index) => (
              <figure key={`${index}-${url.slice(0, 40)}`}>
                <img src={url} alt={`활동 사진 ${index + 1}`} />
                <figcaption>
                  {files[index]?.name ?? draftAssets[index]?.original_filename ?? `사진 ${index + 1}`}
                </figcaption>
              </figure>
            ))}
          </div>
        )}

        <label className="photo-field">
          <span>직접 기록</span>
          <textarea
            value={manualObservation}
            onChange={(event) => setManualObservation(event.target.value)}
            placeholder="예: 오늘 둘이 공원에서 낙엽을 모았다. 아이가 노란 잎을 골라 나란히 놓았고 함께 색을 비교했다."
            maxLength={10_000}
            disabled={busy || pendingRecordId !== null}
          />
        </label>

        <label className="photo-field">
          <span>AI에게 참고시킬 추가 설명 · 선택</span>
          <textarea
            value={context}
            onChange={(event) => setContext(event.target.value)}
            placeholder="예: 장소나 상황처럼 사진만으로 알 수 없는 맥락을 적어주세요."
            maxLength={10_000}
            disabled={busy || pendingRecordId !== null || !aiAssist}
          />
        </label>

        <label className="photo-field">
          <span>
            <input
              type="checkbox"
              checked={aiAssist}
              onChange={(event) => setAiAssist(event.target.checked)}
              disabled={busy || pendingRecordId !== null}
            />{" "}
            로컬 AI에게 사진 설명과 기록 초안 도움받기
          </span>
          <small className="muted">끄면 사진과 직접 작성한 글만 저장합니다.</small>
        </label>

        <button
          className="primary-button"
          type="button"
          onClick={handleCreate}
          disabled={!childId || files.length === 0 || busy || pendingRecordId !== null}
        >
          {busy
            ? "사진 저장 중…"
            : pendingRecordId
              ? "AI 보조 작업 중…"
              : aiAssist
                ? "사진 저장하고 AI 보조 시작"
                : "사진 일기 저장"}
        </button>

        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        {notice && (
          <p className="muted photo-notice" role="status" aria-live="polite">
            {notice}
          </p>
        )}

        {draft && draft.status === "draft" && (
          <section className="photo-draft" aria-labelledby="photo-draft-title">
            <div className="activity-heading">
              <div>
                <p className="card-label">부모 확인</p>
                <h3 id="photo-draft-title">저장 전 확인</h3>
                <p className="muted">직접 쓴 기록과 AI 보조 내용 모두 부모가 최종 기준입니다.</p>
              </div>
              <span className="status-badge">검토 필요</span>
            </div>

            {draftAssets.some((asset) => asset.caption) && (
              <details className="photo-caption-details">
                <summary>로컬 AI가 사진에서 읽은 장면 확인</summary>
                {draftAssets.map((asset) => (
                  <div key={asset.id} className="photo-caption-item">
                    <strong>{asset.original_filename}</strong>
                    <p>{asset.caption ?? "장면 설명을 만들지 못했습니다."}</p>
                  </div>
                ))}
              </details>
            )}

            <label className="photo-field">
              <span>최종 관찰 기록</span>
              <textarea
                value={editedObservation}
                onChange={(event) => setEditedObservation(event.target.value)}
                maxLength={10_000}
                disabled={busy}
              />
            </label>
            <button
              className="primary-button"
              type="button"
              onClick={handleCommit}
              disabled={!editedObservation.trim() || busy}
            >
              확인하고 관찰 기록으로 저장
            </button>
          </section>
        )}
      </section>

      <section className="workspace photo-history">
        <div className="activity-heading">
          <div>
            <p className="card-label">사진 기록 내역</p>
            <h2>사진 일기와 초안</h2>
          </div>
        </div>
        {records.length === 0 ? (
          <p className="muted">아직 사진으로 만든 기록이 없습니다.</p>
        ) : (
          <div className="quest-list">
            {records.map((record) => (
              <article className="quest-card" key={record.id}>
                <div className="material-meta">
                  <strong>사진 {record.photo_asset_ids.length}장</strong>
                  <span className={`status-badge status-${record.status}`}>
                    {STATUS_LABEL[record.status]}
                  </span>
                </div>
                <p>{record.generated_observation}</p>
                {record.generation_mode === "manual_photo_diary" && (
                  <p className="muted">직접 기록 모드</p>
                )}
                {record.status === "processing" && (
                  <p className="muted">AI가 사진을 보조 분석하고 있습니다. 화면을 떠나도 계속 진행됩니다.</p>
                )}
                {record.status === "queued" && (
                  <p className="muted">앞선 작업이 끝나면 자동으로 보조 분석을 시작합니다.</p>
                )}
                {record.status === "failed" && (
                  <p className="form-error">로컬 기록 처리에 문제가 생겼습니다. 원본 사진은 보관되어 있습니다.</p>
                )}
                {record.status === "draft" && (
                  <button
                    className="quiet-button"
                    type="button"
                    onClick={() => void reopenDraft(record)}
                    disabled={busy}
                  >
                    초안 검토
                  </button>
                )}
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
