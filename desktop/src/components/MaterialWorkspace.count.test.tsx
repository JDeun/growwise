import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { GeneratedMaterial } from "../api";
import { MaterialWorkspace } from "./MaterialWorkspace";
const noop = () => undefined;
function item(id: string, status: GeneratedMaterial["status"]): GeneratedMaterial { return { id, child_id: "c1", kind: "activity_guide", title: id, content_markdown: "# x", status, source_refs: [], generator_mode: "template", review_note: null, request_topic: id, request_goal: null, version: 1, parent_material_id: null, version_note: null }; }
describe("MaterialWorkspace lane counts", () => {
  it("shows counts for review and approved queues", () => {
    const html = renderToStaticMarkup(<MaterialWorkspace materials={[item("a", "draft"), item("b", "review_pending"), item("c", "approved")]} resources={[]} materialKind="activity_guide" topic="" goal="" selectedResourceRefs={[]} busy={false} error={null} revisionNotes={{}} editingMaterialId={null} onKindChange={noop} onTopicChange={noop} onGoalChange={noop} onToggleResource={noop} onGenerate={noop} onReview={noop} onRevisionNoteChange={noop} onRevise={noop} onEditStart={noop} onEdit={noop} onPrint={noop} />);
    expect(html).toMatch(/검토함<\/h3><span>2<\/span>/);
    expect(html).toMatch(/사용 가능<\/h3><span>1<\/span>/);
  });
});
