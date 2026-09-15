import type { FormEvent } from "react";

import { MaterialEditPanel } from "../MaterialEditPanel";
import type {
  GeneratedMaterial,
  MaterialKind,
  MaterialStatus,
  ResourceRecord,
} from "../api";
import { EmptyState } from "./EmptyState";

const KIND_LABELS: Record<MaterialKind, string> = {
  activity_guide: "활동 가이드",
  reading_activity: "독서 활동지",
  english_card: "영어 대화 카드",
  math_activity: "수학 놀이",
  science_inquiry: "과학 탐구",
  writing_prompt: "글쓰기·말하기",
  field_trip: "탐방·여행 활동지",
};

const STATUS_LABELS: Record<MaterialStatus, string> = {
  draft: "초안",
  review_pending: "부모 검토 필요",
  revision_requested: "수정 요청됨",
  approved: "승인됨",
  rejected: "사용 안 함",
  archived: "보관됨",
};

interface MaterialWorkspaceProps {
  materials: GeneratedMaterial[];
  resources: ResourceRecord[];
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
  onEdit: (materialId: string, title: string, content: string, note: string | null) => void;
  onPrint: (material: GeneratedMaterial) => void;
}

function sourceTitle(ref: string, resources: ResourceRecord[]): string {
  if (!ref.startsWith("resource:")) return ref;
  const id = ref.slice("resource:".length);
  return resources.find((resource) => resource.id === id)?.title ?? "연결 자료";
}

export function MaterialWorkspace({
  materials,
  resources,
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
}: MaterialWorkspaceProps) {
  const pending = materials.filter((material) =>
    ["draft", "review_pending", "revision_requested"].includes(material.status),
  );
  const approved = materials.filter((material) => material.status === "approved");
  const inactive = materials.filter((material) =>
    ["rejected", "archived"].includes(material.status),
  );
  const editingMaterial = editingMaterialId
    ? materials.find((material) => material.id === editingMaterialId) ?? null
    : null;

  return (
    <section className="material-workspace" aria-labelledby="materials-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">MATERIALS</p>
          <h2 id="materials-title">만들고, 부모가 검토한 뒤 사용합니다.</h2>
          <p className="muted">
            AI 연결 여부와 관계없이 기본 템플릿으로 생성할 수 있습니다. 승인 전 자료는 인쇄할 수 없습니다.
          </p>
        </div>
        <span className="badge">Parent Review</span>
      </div>

      <form className="material-composer" onSubmit={onGenerate}>
        <label>
          <span>자료 종류</span>
          <select value={materialKind} onChange={(event) => onKindChange(event.target.value as MaterialKind)} disabled={busy}>
            {Object.entries(KIND_LABELS).map(([kind, label]) => <option key={kind} value={kind}>{label}</option>)}
          </select>
        </label>
        <label className="material-topic-field">
          <span>주제</span>
          <input value={topic} onChange={(event) => onTopicChange(event.target.value)} maxLength={200} placeholder="예: 비 오는 날의 달팽이" disabled={busy} />
        </label>
        <label className="material-goal-field">
          <span>부모 목표(선택)</span>
          <input value={goal} onChange={(event) => onGoalChange(event.target.value)} maxLength={300} placeholder="예: 정답보다 관찰 질문을 중심으로" disabled={busy} />
        </label>
        {resources.length > 0 && (
          <fieldset className="resource-grounding-picker">
            <legend>근거로 사용할 내 자료(선택)</legend>
            <p className="muted">선택한 자료만 명시적으로 생성 맥락에 연결됩니다.</p>
            <div className="resource-grounding-list">
              {resources.map((resource) => {
                const ref = `resource:${resource.id}`;
                return (
                  <label key={resource.id} className="resource-grounding-item">
                    <input type="checkbox" checked={selectedResourceRefs.includes(ref)} onChange={() => onToggleResource(resource.id)} disabled={busy} />
                    <span><strong>{resource.title}</strong><small>{resource.kind}</small></span>
                  </label>
                );
              })}
            </div>
          </fieldset>
        )}
        <button className="primary-button" type="submit" disabled={busy || !topic.trim()}>{busy ? "처리 중…" : `${KIND_LABELS[materialKind]} 만들기`}</button>
        {error && <p className="form-error" role="alert">{error}</p>}
      </form>

      <div className="material-lanes">
        <section className="material-lane" aria-labelledby="review-lane-title">
          <div className="lane-heading"><h3 id="review-lane-title">검토함</h3><span>{pending.length}</span></div>
          {pending.length === 0 ? <EmptyState title="검토할 자료가 없습니다." description="새 자료를 만들면 이곳에서 내용을 확인하고 승인하거나 수정할 수 있습니다." /> : pending.map((material) => (
            <article className="material-card review-card" key={material.id}>
              <div className="material-card-heading"><div><span className={`material-status status-${material.status}`}>{STATUS_LABELS[material.status]}</span><h4>{material.title}</h4></div><small>v{material.version} · {KIND_LABELS[material.kind]}</small></div>
              {material.source_refs.length > 0 && <div className="material-sources" aria-label="생성 근거">{material.source_refs.map((ref) => <span key={ref}>{sourceTitle(ref, resources)}</span>)}</div>}
              <div className="material-preview"><pre>{material.content_markdown}</pre></div>
              {material.review_note && <p className="review-note"><strong>검토 메모</strong> {material.review_note}</p>}
              <div className="material-actions">
                <button type="button" className="primary-button" disabled={busy} onClick={() => onReview(material.id, "approved")}>승인하고 사용</button>
                <button type="button" className="quiet-button" disabled={busy} onClick={() => onEditStart(material.id)}>직접 편집</button>
                <button type="button" className="quiet-button danger-text" disabled={busy} onClick={() => onReview(material.id, "rejected")}>사용 안 함</button>
              </div>
              <div className="revision-request">
                <label><span>수정 요청</span><textarea value={revisionNotes[material.id] ?? ""} onChange={(event) => onRevisionNoteChange(material.id, event.target.value)} maxLength={1000} placeholder="예: 질문 수를 줄이고 아이가 직접 관찰할 여백을 늘려 주세요." disabled={busy} /></label>
                <button type="button" className="quiet-button" disabled={busy || !(revisionNotes[material.id] ?? "").trim()} onClick={() => onRevise(material.id)}>새 버전 만들기</button>
              </div>
            </article>
          ))}
        </section>

        <section className="material-lane" aria-labelledby="approved-lane-title">
          <div className="lane-heading"><h3 id="approved-lane-title">사용 가능</h3><span>{approved.length}</span></div>
          {approved.length === 0 ? <EmptyState title="승인된 자료가 없습니다." description="부모가 내용을 확인하고 승인한 자료만 여기에 표시됩니다." /> : approved.map((material) => (
            <article className="material-card approved-card" key={material.id}>
              <div className="material-card-heading"><div><span className="material-status status-approved">승인됨</span><h4>{material.title}</h4></div><small>v{material.version}</small></div>
              <div className="material-preview compact"><pre>{material.content_markdown}</pre></div>
              <div className="material-actions"><button className="primary-button" type="button" onClick={() => onPrint(material)}>인쇄 / PDF 저장</button><button className="quiet-button" type="button" disabled={busy} onClick={() => onEditStart(material.id)}>새 편집본 만들기</button></div>
            </article>
          ))}
        </section>
      </div>

      {inactive.length > 0 && <details className="inactive-materials"><summary>사용하지 않는 자료 {inactive.length}개</summary>{inactive.map((material) => <p key={material.id}>{material.title} · {STATUS_LABELS[material.status]} · v{material.version}</p>)}</details>}

      {editingMaterial && <MaterialEditPanel material={editingMaterial} busy={busy} onCancel={() => onEditStart(null)} onSave={(title, content, note) => onEdit(editingMaterial.id, title, content, note)} />}
    </section>
  );
}
