import { FormEvent, useState } from "react";

import type { GeneratedMaterial } from "./api";

interface MaterialEditPanelProps {
  material: GeneratedMaterial;
  busy: boolean;
  onSave: (title: string, contentMarkdown: string, note: string | null) => Promise<void>;
  onCancel: () => void;
}

export function MaterialEditPanel({
  material,
  busy,
  onSave,
  onCancel,
}: MaterialEditPanelProps) {
  const [title, setTitle] = useState(material.title);
  const [content, setContent] = useState(material.content_markdown);
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedTitle = title.trim();
    const normalizedContent = content.trim();
    if (!normalizedTitle) {
      setError("제목을 입력해 주세요.");
      return;
    }
    if (!normalizedContent) {
      setError("자료 내용을 입력해 주세요.");
      return;
    }
    setError(null);
    await onSave(normalizedTitle, normalizedContent, note.trim() || null);
  }

  return (
    <form className="revision-panel" onSubmit={handleSubmit}>
      <p className="card-label">PARENT EDIT · NEW VERSION</p>
      <p className="muted">
        기존 v{material.version}은 그대로 보존됩니다. 저장하면 v{material.version + 1} 검토본을
        새로 만듭니다.
      </p>
      <label>
        <span>제목</span>
        <input value={title} onChange={(event) => setTitle(event.target.value)} maxLength={500} disabled={busy} />
      </label>
      <label>
        <span>Markdown 내용</span>
        <textarea value={content} onChange={(event) => setContent(event.target.value)} maxLength={100000} disabled={busy} />
      </label>
      <label>
        <span>버전 메모(선택)</span>
        <textarea value={note} onChange={(event) => setNote(event.target.value)} maxLength={2000} placeholder="예: 질문 수를 줄이고 표현을 간결하게 다듬음" disabled={busy} />
      </label>
      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="review-actions">
        <button className="primary-button" type="submit" disabled={busy}>{busy ? "저장 중…" : "새 버전 저장"}</button>
        <button className="quiet-button" type="button" onClick={onCancel} disabled={busy}>취소</button>
      </div>
    </form>
  );
}
