import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { GeneratedMaterial } from "../api";
import { MaterialWorkspace } from "./MaterialWorkspace";
const noop = () => undefined;
function item(id: string, status: GeneratedMaterial["status"]): GeneratedMaterial { return { id, child_id: "c1", kind: "activity_guide", title: id, content_markdown: "# item", status, source_refs: [], generator_mode: "template", review_note: null, request_topic: id, request_goal: null, version: 1, parent_material_id: null, version_note: null }; }
describe("MaterialWorkspace print boundary", () => {
  it("renders one print affordance for one approved item even with hostile adjacent states", () => {
    const html = renderToStaticMarkup(<MaterialWorkspace materials={[item("draft", "draft"), item("approved", "approved"), item("rejected", "rejected")]} resources={[]} materialKind="activity_guide" topic="" goal="" selectedResourceRefs={[]} busy={false} error={null} revisionNotes={{}} editingMaterialId={null} onKindChange={noop} onTopicChange={noop} onGoalChange={noop} onToggleResource={noop} onGenerate={noop} onReview={noop} onRevisionNoteChange={noop} onRevise={noop} onEditStart={noop} onEdit={noop} onPrint={noop} />);
    expect((html.match(/인쇄 \/ PDF 저장/g) ?? []).length).toBe(1);
  });
});
