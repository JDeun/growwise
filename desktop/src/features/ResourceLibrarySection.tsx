import type { FormEvent } from "react";

import type { ViewLoadState } from "../child-context-state";
import { ViewStateNotice } from "../components";
import type { ResourceKind, ResourceRecord } from "../api";

interface ResourceLibrarySectionProps {
  resourceKind: ResourceKind;
  resourceTitle: string;
  resourceContent: string;
  saving: boolean;
  error: string | null;
  loadState: ViewLoadState;
  resources: ResourceRecord[];
  onKindChange: (value: ResourceKind) => void;
  onTitleChange: (value: string) => void;
  onContentChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onRetry: () => void;
}

export function ResourceLibrarySection({
  resourceKind,
  resourceTitle,
  resourceContent,
  saving,
  error,
  loadState,
  resources,
  onKindChange,
  onTitleChange,
  onContentChange,
  onSubmit,
  onRetry,
}: ResourceLibrarySectionProps) {
  return (
    <section className="resource-section">
      <div className="resource-grid">
        <form className="resource-form" onSubmit={onSubmit}>
          <p className="card-label">RESOURCE LIBRARY</p>
          <h3>자료를 지식베이스에 넣습니다.</h3>
          <label>
            <span>종류</span>
            <select value={resourceKind} onChange={(event) => onKindChange(event.target.value as ResourceKind)}>
              <option value="note">메모</option>
              <option value="book">도서</option>
              <option value="curriculum">교육과정</option>
              <option value="web">웹 자료</option>
              <option value="file">파일 메모</option>
            </select>
          </label>
          <label>
            <span>제목</span>
            <input value={resourceTitle} onChange={(event) => onTitleChange(event.target.value)} maxLength={500} />
          </label>
          <label>
            <span>내용</span>
            <textarea value={resourceContent} onChange={(event) => onContentChange(event.target.value)} placeholder="자료의 핵심 내용이나 메모" />
          </label>
          <button className="primary-button" type="submit" disabled={saving}>{saving ? "저장 중…" : "자료 저장"}</button>
          {error && <p className="form-error" role="alert">{error}</p>}
        </form>

        <div className="resource-list">
          <p className="card-label">INDEXED RESOURCES</p>
          <h3>{loadState.kind === "ready" ? `${resources.length}건` : "자료 목록"}</h3>
          {loadState.kind === "loading" && <ViewStateNotice kind="loading" title="자료 목록을 불러오는 중입니다." description="저장된 자료를 아이 범위에 맞춰 확인합니다." />}
          {loadState.kind === "error" && <ViewStateNotice kind="error" title="자료 목록을 불러오지 못했습니다." description={loadState.message} action={<button className="quiet-button" type="button" onClick={onRetry}>다시 시도</button>} />}
          {loadState.kind === "ready" && resources.length === 0 && <ViewStateNotice kind="empty" title="연결된 자료가 아직 없습니다." description="메모, 책, 교육과정 또는 웹 자료를 저장하면 여기에 모입니다." />}
          {loadState.kind === "ready" && resources.map((resource) => (
            <article className="resource-card" key={resource.id}>
              <strong>{resource.title}</strong>
              <span>{resource.kind}</span>
              {resource.content && <p>{resource.content}</p>}
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
