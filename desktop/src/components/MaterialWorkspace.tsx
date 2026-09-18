import { useEffect, useMemo, useState, type FormEvent } from "react";

import { MaterialEditPanel } from "../MaterialEditPanel";
import type {
  AiEnhancementStatus,
  GeneratedMaterial,
  MaterialKind,
  MaterialStatus,
  ResourceKind,
  ResourceRecord,
  Stage,
} from "../api";
import { materialCatalogForStage, materialCatalogItem } from "../material-catalog";
import { EmptyState } from "./EmptyState";
import { EntityLinkPanel } from "./EntityLinkPanel";
import { MaterialContent } from "./MaterialContent";
import { MaterialCurriculumTargets } from "./MaterialCurriculumTargets";
import { MaterialKindGuide } from "./MaterialKindGuide";
import { MaterialParentGuide } from "./MaterialParentGuide";
import { MaterialResultPanel } from "./MaterialResultPanel";
import "./MaterialWorkspace.queue.css";

const STATUS_LABELS: Record<MaterialStatus, string> = {
  draft: "초안",
  review_pending: "부모 검토 필요",
  revision_requested: "수정 요청됨",
  approved: "승인됨",
  rejected: "사용 안 함",
  archived: "보관됨",
};

const AI_STATUS_LABELS: Record<AiEnhancementStatus, string> = {
  not_requested: "기본 템플릿",
  queued: "AI 보조 준비 중",
  running: "AI 보조 적용 중",
  completed: "AI 보조 완료",
  failed: "기본 템플릿 사용",
  skipped: "AI 보조 미사용",
};

const RESOURCE_KIND_LABELS: Record<ResourceKind, string> = {
  book: "책",
  curriculum: "교육과정",
  web: "웹 자료",
  note: "메모",
  file: "파일",
};

const PRINT_SCOPE_ATTRIBUTE = "data-growwise-print-scope";
const PRINT_TARGET_ATTRIBUTE = "data-growwise-print-target";

interface MaterialWorkspaceProps {
  materials: GeneratedMaterial[];
  resources: ResourceRecord[];
  stage?: Stage;
  materialKind: MaterialKind;
  topic: string;
  goal: string;
  selectedResourceRefs: string[];
  busy: boolean;
  error: string | null;
  revisionNotes: Record<string, string>;
  editingMaterialId: string | null;
  onKindChange: (kind: MaterialKind) => void;
  onTopicChange: (value: string) => void;
  onGoalChange: (value: string) => void;
  onToggleResource: (resourceId: string) => void;
  onGenerate: (event: FormEvent<HTMLFormElement>) => void;
  onReview: (materialId: string, status: MaterialStatus) => void;
  onRevisionNoteChange: (materialId: string, note: string) => void;
  onRevise: (materialId: string) => void;
  onEditStart: (materialId: string | null) => void;
  onEdit: (
    materialId: string,
    title: string,
    content: string,
    note: string | null,
  ) => void | Promise<void>;
  onPrint: (material: GeneratedMaterial) => void;
  onResultRecorded?: () => void | Promise<void>;
}

function sourceTitle(ref: string, resources: ResourceRecord[]): string {
  if (!ref.startsWith("resource:")) return `외부 출처 · ${ref}`;
  const id = ref.slice("resource:".length);
  return resources.find((resource) => resource.id === id)?.title ?? "연결 자료";
}

function MaterialSources({
  material,
  resources,
}: {
  material: GeneratedMaterial;
  resources: ResourceRecord[];
}) {
  if (material.source_refs.length === 0) return null;
  return (
    <div className="material-sources" aria-label="참고한 자료">
      {material.source_refs.map((ref) => (
        <span key={ref}>{sourceTitle(ref, resources)}</span>
      ))}
    </div>
  );
}

function MaterialHeading({ material }: { material: GeneratedMaterial }) {
  const aiStatus = material.ai_status ?? "not_requested";
  return (
    <div className="material-card-heading">
      <div>
        <div className="material-heading-statuses">
          <span className={`material-status status-${material.status}`}>
            {STATUS_LABELS[material.status]}
          </span>
          <span className={`material-ai-status ai-${aiStatus}`}>{AI_STATUS_LABELS[aiStatus]}</span>
        </div>
        <h4>{material.title}</h4>
      </div>
      <small>
        {material.version}번째 버전 · {materialCatalogItem(material.kind).label}
      </small>
    </div>
  );
}

function MaterialLinks({ material }: { material: GeneratedMaterial }) {
  return (
    <EntityLinkPanel
      entityId={material.id}
      ownerChildId={material.child_id}
      label="다른 아이와 생성 자료 연결"
    />
  );
}

function MaterialCore({
  material,
  resources,
  compact = false,
}: {
  material: GeneratedMaterial;
  resources: ResourceRecord[];
  compact?: boolean;
}) {
  return (
    <>
      <MaterialSources material={material} resources={resources} />
      <MaterialLinks material={material} />
      <MaterialCurriculumTargets targets={material.curriculum_targets} />
      <div className={`material-preview${compact ? " compact" : ""}`}>
        <MaterialContent markdown={material.content_markdown} />
      </div>
      <MaterialParentGuide material={material} />
    </>
  );
}

export function MaterialWorkspace(props: MaterialWorkspaceProps) {
  const {
    materials,
    resources,
    stage = "preschool_3_5",
    materialKind,
    topic,
    goal,
    selectedResourceRefs,
    busy,
    error,
    revisionNotes,
    editingMaterialId,
    onKindChange,
    onTopicChange,
    onGoalChange,
    onToggleResource,
    onGenerate,
    onReview,
    onRevisionNoteChange,
    onRevise,
    onEditStart,
    onEdit,
    onPrint,
    onResultRecorded = () => undefined,
  } = props;

  const catalog = materialCatalogForStage(stage);
  const selectedCatalogItem = catalog.find((item) => item.kind === materialKind) ?? catalog[0];
  const drafts = materials.filter((material) => material.status === "draft");
  const reviewQueue = materials.filter((material) =>
    ["review_pending", "revision_requested"].includes(material.status),
  );
  const approved = materials.filter((material) => material.status === "approved");
  const inactive = materials.filter((material) =>
    ["rejected", "archived"].includes(material.status),
  );
  const editingMaterial = editingMaterialId
    ? materials.find((material) => material.id === editingMaterialId) ?? null
    : null;
  const activeMaterials = useMemo(
    () => materials.filter((material) => !["rejected", "archived"].includes(material.status)),
    [materials],
  );
  const [selectedMaterialId, setSelectedMaterialId] = useState<string | null>(null);

  useEffect(() => {
    setSelectedMaterialId((current) => {
      if (current && activeMaterials.some((material) => material.id === current)) return current;
      return activeMaterials[0]?.id ?? null;
    });
  }, [activeMaterials]);

  const selectedMaterial =
    activeMaterials.find((material) => material.id === selectedMaterialId) ?? null;

  function printApprovedCard(material: GeneratedMaterial, card: Element | null) {
    if (!card) return;

    document
      .querySelectorAll(`[${PRINT_TARGET_ATTRIBUTE}="true"]`)
      .forEach((node) => node.removeAttribute(PRINT_TARGET_ATTRIBUTE));
    card.setAttribute(PRINT_TARGET_ATTRIBUTE, "true");
    document.body.setAttribute(PRINT_SCOPE_ATTRIBUTE, "single");

    const cleanup = () => {
      card.removeAttribute(PRINT_TARGET_ATTRIBUTE);
      document.body.removeAttribute(PRINT_SCOPE_ATTRIBUTE);
      window.removeEventListener("afterprint", cleanup);
    };

    window.addEventListener("afterprint", cleanup, { once: true });
    try {
      onPrint(material);
    } catch (printError) {
      cleanup();
      throw printError;
    }
  }

  return (
    <section className="material-workspace" aria-labelledby="materials-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">학습 자료</p>
          <h2 id="materials-title">만들고, 부모가 확인한 뒤 사용합니다.</h2>
          <p className="muted">
            AI 보조 기능이 없어도 기본 템플릿으로 자료를 만들 수 있습니다. 만든 초안은 먼저 저장되고,
            사용할 내용은 부모가 확인해 승인합니다. 승인 전 자료는 인쇄하거나 PDF로 내보낼 수 없습니다.
          </p>
        </div>
        <span className="badge">부모 확인</span>
      </div>

      <div className="material-queue-summary" aria-label="자료 처리 현황">
        <article>
          <span>1. 초안</span>
          <strong>{drafts.length}</strong>
          <small>생성·편집 중</small>
        </article>
        <article>
          <span>2. 부모 검토</span>
          <strong>{reviewQueue.length}</strong>
          <small>승인 또는 수정 결정</small>
        </article>
        <article>
          <span>3. 승인·사용</span>
          <strong>{approved.length}</strong>
          <small>인쇄·PDF·결과 기록</small>
        </article>
      </div>

      <div className="material-studio" data-testid="material-studio">
        <aside className="material-studio-list" aria-label="학습 자료 목록">
          <div className="material-studio-list-heading">
            <div>
              <p className="card-label">Library</p>
              <h3>자료 목록</h3>
            </div>
            <span>{activeMaterials.length}</span>
          </div>
          {activeMaterials.length === 0 ? (
            <EmptyState
              title="아직 만든 자료가 없습니다."
              description="오른쪽 설정에서 첫 자료를 만들면 중앙 문서 캔버스에 표시됩니다."
            />
          ) : (
            <div className="material-studio-list-items">
              {activeMaterials.map((material) => (
                <button
                  key={material.id}
                  type="button"
                  className={`material-studio-list-item${selectedMaterial?.id === material.id ? " is-selected" : ""}`}
                  onClick={() => setSelectedMaterialId(material.id)}
                >
                  <span className={`material-studio-status status-${material.status}`}>
                    {STATUS_LABELS[material.status]}
                  </span>
                  <strong>{material.title}</strong>
                  <small>{materialCatalogItem(material.kind).label} · v{material.version}</small>
                </button>
              ))}
            </div>
          )}
        </aside>

        <section className="material-document-stage" aria-label="선택한 학습 자료 미리보기">
          {selectedMaterial ? (
            <>
              <div className="material-document-toolbar">
                <div>
                  <span>Document preview</span>
                  <strong>{selectedMaterial.title}</strong>
                </div>
                <span className={`material-status status-${selectedMaterial.status}`}>
                  {STATUS_LABELS[selectedMaterial.status]}
                </span>
              </div>
              <article className="material-document-paper">
                <MaterialCore material={selectedMaterial} resources={resources} />
              </article>
            </>
          ) : (
            <div className="material-document-empty">
              <span aria-hidden="true">✦</span>
              <h3>학습 자료가 이곳에 표시됩니다.</h3>
              <p>주제와 목표를 입력하면 부모가 검토할 수 있는 초안을 만듭니다.</p>
            </div>
          )}
        </section>

        <aside className="material-control-panel" aria-label="AI 학습자료 설정">
          <div className="material-control-heading">
            <div>
              <p className="card-label">AI Controls</p>
              <h3>자료 만들기</h3>
            </div>
            <span className="material-ai-indicator">AI · optional</span>
          </div>
          <form className="material-composer material-studio-controls" onSubmit={onGenerate}>
        <fieldset className="material-kind-picker">
          <legend>무엇을 만들까요?</legend>
          <div className="material-kind-options">
            {catalog.map((item) => (
              <label
                key={item.kind}
                className={`material-kind-option${materialKind === item.kind ? " selected" : ""}`}
              >
                <input
                  type="radio"
                  name="material-kind"
                  value={item.kind}
                  checked={materialKind === item.kind}
                  onChange={() => onKindChange(item.kind)}
                  disabled={busy}
                />
                <span>
                  <strong>{item.label}</strong>
                  <small>{item.description}</small>
                </span>
              </label>
            ))}
          </div>
        </fieldset>

        <MaterialKindGuide item={selectedCatalogItem} />

        <label className="material-topic-field">
          <span>주제</span>
          <input
            value={topic}
            onChange={(event) => onTopicChange(event.target.value)}
            maxLength={200}
            placeholder={selectedCatalogItem.placeholder}
            disabled={busy}
          />
        </label>
        <label className="material-goal-field">
          <span>부모 목표(선택)</span>
          <input
            value={goal}
            onChange={(event) => onGoalChange(event.target.value)}
            maxLength={300}
            placeholder={selectedCatalogItem.goalPlaceholder}
            disabled={busy}
          />
        </label>
        {resources.length > 0 && (
          <fieldset className="resource-grounding-picker">
            <legend>참고할 내 자료(선택)</legend>
            <p className="muted">선택한 자료만 새 자료의 내용을 만들 때 참고합니다.</p>
            <div className="resource-grounding-list">
              {resources.map((resource) => {
                const ref = `resource:${resource.id}`;
                return (
                  <label key={resource.id} className="resource-grounding-item">
                    <input
                      type="checkbox"
                      checked={selectedResourceRefs.includes(ref)}
                      onChange={() => onToggleResource(resource.id)}
                      disabled={busy}
                    />
                    <span>
                      <strong>{resource.title}</strong>
                      <small>{RESOURCE_KIND_LABELS[resource.kind]}</small>
                    </span>
                  </label>
                );
              })}
            </div>
          </fieldset>
        )}
        <button className="primary-button" type="submit" disabled={busy || !topic.trim()}>
          {busy ? "초안 저장 중…" : `${selectedCatalogItem.label} 만들기`}
        </button>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
          </form>

          {selectedMaterial ? (
            <section className="material-selected-actions" aria-label="선택 자료 작업">
              <div>
                <span>선택 자료</span>
                <strong>{selectedMaterial.title}</strong>
              </div>
              <div className="material-actions">
                {selectedMaterial.status === "draft" ? (
                  <button
                    type="button"
                    className="primary-button"
                    disabled={busy}
                    onClick={() => onReview(selectedMaterial.id, "review_pending")}
                  >
                    부모 검토로 보내기
                  </button>
                ) : null}
                {["review_pending", "revision_requested"].includes(selectedMaterial.status) ? (
                  <button
                    type="button"
                    className="primary-button"
                    disabled={busy}
                    onClick={() => onReview(selectedMaterial.id, "approved")}
                  >
                    승인하고 사용
                  </button>
                ) : null}
                {selectedMaterial.status === "approved" ? (
                  <button
                    type="button"
                    className="primary-button"
                    onClick={(event) =>
                      printApprovedCard(
                        selectedMaterial,
                        document.querySelector(
                          `.approved-card[data-material-id="${selectedMaterial.id}"]`,
                        ) ?? event.currentTarget.closest(".material-workspace"),
                      )
                    }
                  >
                    인쇄 / PDF
                  </button>
                ) : null}
                <button
                  type="button"
                  className="quiet-button"
                  disabled={busy}
                  onClick={() => onEditStart(selectedMaterial.id)}
                >
                  직접 편집
                </button>
              </div>
            </section>
          ) : null}
        </aside>
      </div>

      <div className="material-workflow-divider">
        <span>Workflow</span>
        <strong>전체 자료 흐름</strong>
      </div>

      <div className="material-queue-lanes">
        <section className="material-lane" aria-labelledby="draft-lane-title">
          <div className="lane-heading">
            <div>
              <span className="material-lane-step">1단계</span>
              <h3 id="draft-lane-title">초안</h3>
            </div>
            <span>{drafts.length}</span>
          </div>
          {drafts.length === 0 ? (
            <EmptyState
              title="대기 중인 초안이 없습니다."
              description="새 자료를 만들거나 편집본을 만들면 이 단계에서 내용을 정리할 수 있습니다."
            />
          ) : (
            drafts.map((material) => (
              <article className="material-card draft-card" key={material.id}>
                <MaterialHeading material={material} />
                <MaterialCore material={material} resources={resources} compact />
                <div className="material-actions">
                  <button
                    type="button"
                    className="primary-button"
                    disabled={busy}
                    onClick={() => onReview(material.id, "review_pending")}
                  >
                    부모 검토로 보내기
                  </button>
                  <button
                    type="button"
                    className="quiet-button"
                    disabled={busy}
                    onClick={() => onEditStart(material.id)}
                  >
                    직접 편집
                  </button>
                  <button
                    type="button"
                    className="quiet-button danger-text"
                    disabled={busy}
                    onClick={() => onReview(material.id, "rejected")}
                  >
                    사용 안 함
                  </button>
                </div>
              </article>
            ))
          )}
        </section>

        <section className="material-lane" aria-labelledby="review-lane-title">
          <div className="lane-heading">
            <div>
              <span className="material-lane-step">2단계</span>
              <h3 id="review-lane-title">부모 검토</h3>
            </div>
            <span>{reviewQueue.length}</span>
          </div>
          {reviewQueue.length === 0 ? (
            <EmptyState
              title="검토할 자료가 없습니다."
              description="초안을 검토 단계로 보내면 승인, 편집 또는 수정 요청을 결정할 수 있습니다."
            />
          ) : (
            reviewQueue.map((material) => (
              <article className="material-card review-card" key={material.id}>
                <MaterialHeading material={material} />
                <MaterialCore material={material} resources={resources} />
                {material.review_note && (
                  <p className="review-note">
                    <strong>검토 메모</strong> {material.review_note}
                  </p>
                )}
                <div className="material-actions">
                  <button
                    type="button"
                    className="primary-button"
                    disabled={busy}
                    onClick={() => onReview(material.id, "approved")}
                  >
                    승인하고 사용
                  </button>
                  <button
                    type="button"
                    className="quiet-button"
                    disabled={busy}
                    onClick={() => onEditStart(material.id)}
                  >
                    직접 편집
                  </button>
                  <button
                    type="button"
                    className="quiet-button danger-text"
                    disabled={busy}
                    onClick={() => onReview(material.id, "rejected")}
                  >
                    사용 안 함
                  </button>
                </div>
                <div className="revision-request">
                  <label>
                    <span>수정 요청</span>
                    <textarea
                      value={revisionNotes[material.id] ?? ""}
                      onChange={(event) => onRevisionNoteChange(material.id, event.target.value)}
                      maxLength={1000}
                      placeholder="예: 질문 수를 줄이고 아이가 직접 관찰할 여백을 늘려 주세요."
                      disabled={busy}
                    />
                  </label>
                  <button
                    type="button"
                    className="quiet-button"
                    disabled={busy || !(revisionNotes[material.id] ?? "").trim()}
                    onClick={() => onRevise(material.id)}
                  >
                    새 버전 만들기
                  </button>
                </div>
              </article>
            ))
          )}
        </section>

        <section className="material-lane" aria-labelledby="approved-lane-title">
          <div className="lane-heading">
            <div>
              <span className="material-lane-step">3단계</span>
              <h3 id="approved-lane-title">승인·사용</h3>
            </div>
            <span>{approved.length}</span>
          </div>
          {approved.length === 0 ? (
            <EmptyState
              title="승인된 자료가 없습니다."
              description="부모가 내용을 확인하고 승인한 자료만 인쇄하거나 PDF로 내보낼 수 있습니다."
            />
          ) : (
            approved.map((material) => (
              <article className="material-card approved-card" data-material-id={material.id} key={material.id}>
                <MaterialHeading material={material} />
                <MaterialCore material={material} resources={resources} compact />
                <div className="material-actions">
                  <button
                    className="primary-button"
                    type="button"
                    onClick={(event) =>
                      printApprovedCard(material, event.currentTarget.closest(".approved-card"))
                    }
                  >
                    인쇄 / PDF 내보내기
                  </button>
                  <button
                    className="quiet-button"
                    type="button"
                    disabled={busy}
                    onClick={() => onEditStart(material.id)}
                  >
                    새 편집본 만들기
                  </button>
                </div>
                <MaterialResultPanel material={material} onRecorded={onResultRecorded} />
              </article>
            ))
          )}
        </section>
      </div>

      {inactive.length > 0 && (
        <details className="inactive-materials">
          <summary>사용하지 않는 자료 {inactive.length}개</summary>
          {inactive.map((material) => (
            <p key={material.id}>
              {material.title} · {STATUS_LABELS[material.status]} · {material.version}번째 버전
            </p>
          ))}
        </details>
      )}

      {editingMaterial && (
        <MaterialEditPanel
          material={editingMaterial}
          busy={busy}
          onCancel={() => onEditStart(null)}
          onSave={(title, content, note) => onEdit(editingMaterial.id, title, content, note)}
        />
      )}
    </section>
  );
}
