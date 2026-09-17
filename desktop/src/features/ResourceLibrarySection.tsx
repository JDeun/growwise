import { useEffect, useMemo, useState, type FormEvent } from "react";

import { useOptionalActiveChild } from "../active-child-context";
import type { ViewLoadState } from "../child-context-state";
import { ConfirmDialog, EntityLinkPanel, ViewStateNotice } from "../components";
import type { ResourceCreateInput, ResourceKind, ResourceRecord } from "../api";
import { canMutateResourceInChildView, resourceScopeLabel } from "../resource-scope";
import "./ResourceLibrarySection.css";

type ResourceKindFilter = "all" | ResourceKind;

const RESOURCE_KIND_LABELS: Record<ResourceKind, string> = {
  note: "메모",
  book: "도서",
  curriculum: "교육과정",
  web: "웹 자료",
  file: "파일 메모",
};

export function filterResources(
  resources: ResourceRecord[],
  query: string,
  kind: ResourceKindFilter,
): ResourceRecord[] {
  const needle = query.trim().toLocaleLowerCase();
  return resources.filter((resource) => {
    if (kind !== "all" && resource.kind !== kind) return false;
    if (!needle) return true;
    const haystack = [
      resource.title,
      resource.summary,
      resource.content,
      resource.source_name,
      resource.author,
      ...resource.tags,
      ...resource.stage_tags,
    ]
      .filter(Boolean)
      .join(" ")
      .toLocaleLowerCase();
    return haystack.includes(needle);
  });
}

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
  onUpdate: (resourceId: string, request: ResourceCreateInput) => Promise<void>;
  onDelete: (resourceId: string) => Promise<void>;
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
  onUpdate,
  onDelete,
}: ResourceLibrarySectionProps) {
  const activeChildContext = useOptionalActiveChild();
  const activeChildId = activeChildContext?.activeChildId || null;
  const [query, setQuery] = useState("");
  const [kindFilter, setKindFilter] = useState<ResourceKindFilter>("all");
  const [selectedResourceId, setSelectedResourceId] = useState<string | null>(null);
  const [editingResource, setEditingResource] = useState<ResourceRecord | null>(null);
  const [editKind, setEditKind] = useState<ResourceKind>("note");
  const [editTitle, setEditTitle] = useState("");
  const [editContent, setEditContent] = useState("");
  const [editError, setEditError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ResourceRecord | null>(null);
  const [mutationBusy, setMutationBusy] = useState(false);

  const filteredResources = useMemo(
    () => filterResources(resources, query, kindFilter),
    [kindFilter, query, resources],
  );
  const selectedResource =
    resources.find((resource) => resource.id === selectedResourceId) ?? null;

  useEffect(() => {
    if (
      selectedResourceId &&
      !filteredResources.some((resource) => resource.id === selectedResourceId)
    ) {
      setSelectedResourceId(null);
    }
  }, [filteredResources, selectedResourceId]);

  function startEditing(resource: ResourceRecord) {
    if (!canMutateResourceInChildView(resource, activeChildId)) return;
    setEditingResource(resource);
    setEditKind(resource.kind);
    setEditTitle(resource.title);
    setEditContent(resource.content ?? "");
    setEditError(null);
  }

  async function handleUpdate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editingResource || !canMutateResourceInChildView(editingResource, activeChildId)) return;
    const title = editTitle.trim();
    if (!title) {
      setEditError("자료 제목을 입력해 주세요.");
      return;
    }
    setMutationBusy(true);
    setEditError(null);
    try {
      await onUpdate(editingResource.id, {
        kind: editKind,
        title,
        child_id: editingResource.child_id,
        summary: editingResource.summary,
        content: editContent.trim() || null,
        source_url: editingResource.source_url,
        source_name: editingResource.source_name,
        author: editingResource.author,
        tags: editingResource.tags,
        stage_tags: editingResource.stage_tags,
        provenance: editingResource.provenance,
      });
      setEditingResource(null);
    } catch {
      // App owns the operation error notice. Keep the editor open so the parent can retry.
    } finally {
      setMutationBusy(false);
    }
  }

  async function handleDelete() {
    if (!deleteTarget || !canMutateResourceInChildView(deleteTarget, activeChildId)) return;
    setMutationBusy(true);
    try {
      await onDelete(deleteTarget.id);
      if (selectedResourceId === deleteTarget.id) setSelectedResourceId(null);
      if (editingResource?.id === deleteTarget.id) setEditingResource(null);
      setDeleteTarget(null);
    } catch {
      // App owns the operation error notice. Keep confirmation open on failure.
    } finally {
      setMutationBusy(false);
    }
  }

  return (
    <section className="resource-section">
      <div className="resource-grid">
        <form className="resource-form" onSubmit={onSubmit}>
          <p className="card-label">참고 자료 추가</p>
          <h3>나중에 다시 쓸 자료를 저장합니다.</h3>
          <p className="muted">책, 교육과정, 웹 자료나 직접 적은 메모를 한곳에 모아 검색하고 학습 자료를 만들 때 참고할 수 있습니다.</p>
          <label>
            <span>종류</span>
            <select
              value={resourceKind}
              onChange={(event) => onKindChange(event.target.value as ResourceKind)}
            >
              {Object.entries(RESOURCE_KIND_LABELS).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </label>
          <label>
            <span>제목</span>
            <input
              value={resourceTitle}
              onChange={(event) => onTitleChange(event.target.value)}
              maxLength={500}
            />
          </label>
          <label>
            <span>내용</span>
            <textarea
              value={resourceContent}
              onChange={(event) => onContentChange(event.target.value)}
              placeholder="자료의 핵심 내용이나 메모"
            />
          </label>
          <button className="primary-button" type="submit" disabled={saving || mutationBusy}>
            {saving ? "저장 중…" : "자료 저장"}
          </button>
          {error && <p className="form-error" role="alert">{error}</p>}
        </form>

        <div className="resource-browser">
          <div className="resource-browser-heading">
            <div>
              <p className="card-label">저장된 참고 자료</p>
              <h3>
                {loadState.kind === "ready"
                  ? `${filteredResources.length} / ${resources.length}건`
                  : "자료 목록"}
              </h3>
            </div>
            {loadState.kind === "ready" && (query || kindFilter !== "all") && (
              <button
                className="quiet-button"
                type="button"
                onClick={() => {
                  setQuery("");
                  setKindFilter("all");
                }}
              >
                필터 초기화
              </button>
            )}
          </div>

          {loadState.kind === "ready" && resources.length > 0 && (
            <div className="resource-filters" aria-label="자료 검색 및 필터">
              <label>
                <span>자료 검색</span>
                <input
                  type="search"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="제목, 내용, 태그 검색"
                />
              </label>
              <label>
                <span>종류 필터</span>
                <select
                  value={kindFilter}
                  onChange={(event) => setKindFilter(event.target.value as ResourceKindFilter)}
                >
                  <option value="all">전체</option>
                  {Object.entries(RESOURCE_KIND_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
              </label>
            </div>
          )}

          {loadState.kind === "loading" && (
            <ViewStateNotice
              kind="loading"
              title="자료 목록을 불러오는 중입니다."
              description="선택한 아이의 자료와 함께 볼 수 있는 공유 자료를 확인합니다."
            />
          )}
          {loadState.kind === "error" && (
            <ViewStateNotice
              kind="error"
              title="자료 목록을 불러오지 못했습니다."
              description={loadState.message}
              action={
                <button className="quiet-button" type="button" onClick={onRetry}>
                  다시 시도
                </button>
              }
            />
          )}
          {loadState.kind === "ready" && resources.length === 0 && (
            <ViewStateNotice
              kind="empty"
              title="연결된 자료가 아직 없습니다."
              description="메모, 책, 교육과정 또는 웹 자료를 저장하면 여기에 모입니다."
            />
          )}
          {loadState.kind === "ready" && resources.length > 0 && filteredResources.length === 0 && (
            <ViewStateNotice
              kind="empty"
              title="조건에 맞는 자료가 없습니다."
              description="검색어나 종류 필터를 바꿔 보세요."
              action={
                <button
                  className="quiet-button"
                  type="button"
                  onClick={() => {
                    setQuery("");
                    setKindFilter("all");
                  }}
                >
                  필터 초기화
                </button>
              }
            />
          )}

          {loadState.kind === "ready" && filteredResources.length > 0 && (
            <div className="resource-results">
              <div className="resource-list" aria-label="자료 목록">
                {filteredResources.map((resource) => {
                  const mutable = canMutateResourceInChildView(resource, activeChildId);
                  return (
                    <article
                      className={`resource-card${selectedResourceId === resource.id ? " is-selected" : ""}`}
                      key={resource.id}
                    >
                      <div className="resource-card-heading">
                        <div>
                          <strong>{resource.title}</strong>
                          <span>{RESOURCE_KIND_LABELS[resource.kind]}</span>
                        </div>
                        <span className="resource-scope">
                          {resourceScopeLabel(resource, activeChildId)}
                        </span>
                      </div>
                      {(resource.summary || resource.content) && (
                        <p>{resource.summary ?? resource.content}</p>
                      )}
                      {resource.tags.length > 0 && (
                        <div className="resource-tags" aria-label="자료 태그">
                          {resource.tags.map((tag) => <span key={tag}>{tag}</span>)}
                        </div>
                      )}
                      {!mutable && (
                        <p className="muted">
                          다른 아이에서 공유된 자료입니다. 이 화면에서는 읽기 전용입니다.
                        </p>
                      )}
                      <div className="resource-card-actions">
                        <button
                          className="quiet-button"
                          type="button"
                          onClick={() => setSelectedResourceId(resource.id)}
                        >
                          상세
                        </button>
                        <button
                          className="quiet-button"
                          type="button"
                          onClick={() => startEditing(resource)}
                          disabled={mutationBusy || !mutable}
                          title={!mutable ? "원래 아이 화면에서 편집할 수 있습니다." : undefined}
                        >
                          편집
                        </button>
                        <button
                          className="quiet-button danger-button"
                          type="button"
                          onClick={() => setDeleteTarget(resource)}
                          disabled={mutationBusy || !mutable}
                          title={!mutable ? "원래 아이 화면에서 삭제할 수 있습니다." : undefined}
                        >
                          삭제
                        </button>
                      </div>
                    </article>
                  );
                })}
              </div>

              {selectedResource && (
                <aside className="resource-detail" aria-label="선택한 자료 상세">
                  <div className="resource-detail-heading">
                    <div>
                      <p className="card-label">자료 상세</p>
                      <h4>{selectedResource.title}</h4>
                    </div>
                    <button
                      className="quiet-button"
                      type="button"
                      onClick={() => setSelectedResourceId(null)}
                    >
                      닫기
                    </button>
                  </div>
                  <dl>
                    <div>
                      <dt>종류</dt>
                      <dd>{RESOURCE_KIND_LABELS[selectedResource.kind]}</dd>
                    </div>
                    <div>
                      <dt>사용 범위</dt>
                      <dd>{resourceScopeLabel(selectedResource, activeChildId)}</dd>
                    </div>
                    {selectedResource.source_name && (
                      <div><dt>출처</dt><dd>{selectedResource.source_name}</dd></div>
                    )}
                    {selectedResource.author && (
                      <div><dt>저자</dt><dd>{selectedResource.author}</dd></div>
                    )}
                  </dl>
                  {!canMutateResourceInChildView(selectedResource, activeChildId) && (
                    <p className="muted">
                      공유받은 자료는 이 아이의 화면에서 읽기 전용으로 사용합니다.
                    </p>
                  )}
                  {selectedResource.source_url && (
                    <p className="resource-source-url">{selectedResource.source_url}</p>
                  )}
                  {selectedResource.summary && <p>{selectedResource.summary}</p>}
                  {selectedResource.content && <pre>{selectedResource.content}</pre>}
                  {Object.keys(selectedResource.provenance).length > 0 && (
                    <details className="resource-provenance">
                      <summary>출처 세부 정보</summary>
                      {Object.entries(selectedResource.provenance).map(([key, value]) => (
                        <span key={key}>{key}: {value}</span>
                      ))}
                    </details>
                  )}
                  <EntityLinkPanel
                    entityId={selectedResource.id}
                    ownerChildId={selectedResource.child_id}
                    label="다른 아이와 자료 연결"
                  />
                </aside>
              )}
            </div>
          )}
        </div>
      </div>

      {editingResource && (
        <form className="resource-edit-panel" onSubmit={(event) => void handleUpdate(event)}>
          <div className="resource-detail-heading">
            <div>
              <p className="card-label">자료 편집</p>
              <h3>자료 수정</h3>
            </div>
            <button
              className="quiet-button"
              type="button"
              onClick={() => setEditingResource(null)}
              disabled={mutationBusy}
            >
              취소
            </button>
          </div>
          <div className="resource-edit-grid">
            <label>
              <span>종류</span>
              <select
                value={editKind}
                onChange={(event) => setEditKind(event.target.value as ResourceKind)}
              >
                {Object.entries(RESOURCE_KIND_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </label>
            <label>
              <span>제목</span>
              <input
                value={editTitle}
                onChange={(event) => setEditTitle(event.target.value)}
                maxLength={500}
              />
            </label>
          </div>
          <label>
            <span>내용</span>
            <textarea value={editContent} onChange={(event) => setEditContent(event.target.value)} />
          </label>
          {editError && <p className="form-error" role="alert">{editError}</p>}
          <button className="primary-button" type="submit" disabled={mutationBusy}>
            {mutationBusy ? "저장 중…" : "수정 저장"}
          </button>
        </form>
      )}

      <ConfirmDialog
        open={deleteTarget !== null}
        title="자료 삭제"
        description={
          deleteTarget
            ? `‘${deleteTarget.title}’ 자료를 저장 목록과 검색에서 삭제합니다. 이 작업은 되돌릴 수 없습니다.`
            : ""
        }
        confirmLabel="자료 삭제"
        busy={mutationBusy}
        destructive
        onConfirm={() => void handleDelete()}
        onCancel={() => {
          if (!mutationBusy) setDeleteTarget(null);
        }}
      />
    </section>
  );
}
