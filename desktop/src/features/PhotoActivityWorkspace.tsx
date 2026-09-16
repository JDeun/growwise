import { ChangeEvent, useCallback, useEffect, useState } from "react";

import {
  commitPhotoRecord,
  createPhotoRecord,
  getPhotoAsset,
  listChildren,
  listPhotoRecords,
  type ChildProfile,
  type PhotoActivityRecord,
  type PhotoAsset,
  type PhotoUploadInput,
} from "../api";
import "./PhotoActivityWorkspace.css";

const LAST_CHILD_KEY = "growwise:last-child-id";
const MAX_FILES = 8;
const MAX_FILE_BYTES = 15 * 1024 * 1024;
const MAX_TOTAL_BYTES = 60 * 1024 * 1024;
const ACCEPTED_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

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

type Props = { active: boolean };

export function PhotoActivityWorkspace({ active }: Props) {
  const [children, setChildren] = useState<ChildProfile[]>([]);
  const [childId, setChildId] = useState("");
  const [records, setRecords] = useState<PhotoActivityRecord[]>([]);
  const [files, setFiles] = useState<File[]>([]);
  const [previews, setPreviews] = useState<string[]>([]);
  const [storedPreviews, setStoredPreviews] = useState<string[]>([]);
  const [context, setContext] = useState("");
  const [draft, setDraft] = useState<PhotoActivityRecord | null>(null);
  const [draftAssets, setDraftAssets] = useState<PhotoAsset[]>([]);
  const [editedObservation, setEditedObservation] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const refreshRecords = useCallback(async (targetChildId: string) => {
    if (!targetChildId) {
      setRecords([]);
      return;
    }
    setRecords(await listPhotoRecords(targetChildId));
  }, []);

  useEffect(() => {
    if (!active) return;
    let cancelled = false;
    void (async () => {
      try {
        const result = await listChildren();
        if (cancelled) return;
        setChildren(result);
        const remembered = window.localStorage.getItem(LAST_CHILD_KEY);
        const selected = result.find((child) => child.id === remembered) ?? result[0] ?? null;
        setChildId(selected?.id ?? "");
        if (selected) await refreshRecords(selected.id);
      } catch (loadError) {
        if (!cancelled) setError(messageFrom(loadError));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [active, refreshRecords]);

  useEffect(() => {
    const urls = files.map((file) => URL.createObjectURL(file));
    setPreviews(urls);
    return () => urls.forEach((url) => URL.revokeObjectURL(url));
  }, [files]);

  async function handleChildChange(event: ChangeEvent<HTMLSelectElement>) {
    const next = event.target.value;
    setChildId(next);
    setDraft(null);
    setDraftAssets([]);
    setStoredPreviews([]);
    setEditedObservation("");
    setError(null);
    window.localStorage.setItem(LAST_CHILD_KEY, next);
    try {
      await refreshRecords(next);
    } catch (loadError) {
      setError(messageFrom(loadError));
    }
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
  }

  async function handleAnalyze() {
    if (!childId || files.length === 0 || busy) return;
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
      const result = await createPhotoRecord(childId, uploads, context.trim() || undefined);
      setDraft(result.record);
      setDraftAssets(result.assets);
      setStoredPreviews([]);
      setEditedObservation(result.record.generated_observation);
      setNotice(
        result.record.generation_mode === "llm_photo_synthesis"
          ? "사진 분석 초안을 만들었습니다. 내용이 실제 경험과 맞는지 확인한 뒤 저장하세요."
          : "모델 보강 없이 안전한 기본 초안을 만들었습니다. 내용을 확인하고 보완하세요.",
      );
      await refreshRecords(childId);
    } catch (analyzeError) {
      setError(messageFrom(analyzeError));
    } finally {
      setBusy(false);
    }
  }

  async function handleCommit() {
    if (!draft || !editedObservation.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      await commitPhotoRecord(draft.id, editedObservation.trim());
      setNotice("검토한 사진 기록을 관찰 타임라인에 저장했습니다.");
      setDraft(null);
      setDraftAssets([]);
      setStoredPreviews([]);
      setEditedObservation("");
      setContext("");
      setFiles([]);
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
      setNotice("이전에 만든 초안과 로컬 사진 원본을 다시 열었습니다.");
    } catch (loadError) {
      setError(messageFrom(loadError));
    } finally {
      setBusy(false);
    }
  }

  if (!active) return null;

  const visiblePreviews = previews.length > 0 ? previews : storedPreviews;

  return (
    <main className="photo-workspace app-shell" aria-labelledby="photo-workspace-title">
      <section className="workspace photo-workspace-card">
        <div className="section-heading">
          <div>
            <p className="card-label">PHOTO ACTIVITY RECORD</p>
            <h2 id="photo-workspace-title">사진으로 활동 기록 만들기</h2>
            <p className="muted">
              사진의 촬영 정보와 선택적 로컬 VLM 설명, 부모 메모를 합쳐 검토용 초안을 만듭니다.
              모델이 만든 내용은 부모가 확인하고 저장하기 전까지 관찰 기록이 아닙니다.
            </p>
          </div>
        </div>

        <div className="photo-privacy-note">
          <strong>로컬 우선</strong>
          <p>
            사진 원본은 GrowWise 관리 폴더에 content hash로 저장됩니다. 정확한 GPS 좌표는 기록하지
            않으며 외부 역지오코딩 서비스로 보내지 않습니다.
          </p>
        </div>

        <label className="photo-field">
          <span>아이</span>
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

        <label className="photo-field">
          <span>활동 사진 · 최대 {MAX_FILES}장 / 전체 60MB</span>
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            multiple
            onChange={handleFiles}
            disabled={!childId || busy}
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
          <span>부모 설명 · 선택</span>
          <textarea
            value={context}
            onChange={(event) => setContext(event.target.value)}
            placeholder="예: 공원에서 낙엽을 주워 색을 비교했고, 아이가 같은 색을 여러 번 골랐어요."
            maxLength={10_000}
            disabled={busy}
          />
        </label>

        <button
          className="primary-button"
          type="button"
          onClick={handleAnalyze}
          disabled={!childId || files.length === 0 || busy}
        >
          {busy ? "처리 중…" : "사진에서 기록 초안 만들기"}
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

        {draft && (
          <section className="photo-draft" aria-labelledby="photo-draft-title">
            <div className="activity-heading">
              <div>
                <p className="card-label">PARENT REVIEW</p>
                <h3 id="photo-draft-title">저장 전 확인</h3>
                <p className="muted">사진 해석이 틀렸거나 과도한 표현이 있으면 직접 수정하세요.</p>
              </div>
              <span className="status-badge">{draft.generation_mode}</span>
            </div>

            {draftAssets.some((asset) => asset.caption) && (
              <details className="photo-caption-details">
                <summary>모델이 사진에서 읽은 장면 확인</summary>
                {draftAssets.map((asset) => (
                  <div key={asset.id} className="photo-caption-item">
                    <strong>{asset.original_filename}</strong>
                    <p>{asset.caption ?? "시각 캡션을 만들지 못했습니다."}</p>
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
            <p className="card-label">PHOTO HISTORY</p>
            <h2>사진 기록 내역</h2>
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
                  <span className={`status-badge status-${record.status}`}>{record.status}</span>
                </div>
                <p>{record.generated_observation}</p>
                {record.status === "draft" && (
                  <button
                    className="quiet-button"
                    type="button"
                    onClick={() => void reopenDraft(record)}
                    disabled={busy}
                  >
                    검토 계속
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
