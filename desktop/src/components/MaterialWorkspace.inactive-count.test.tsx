import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { GeneratedMaterial } from "../api";
import { MaterialWorkspace } from "./MaterialWorkspace";
const noop = () => undefined;
function m(id: string, status: GeneratedMaterial["status"]): GeneratedMaterial { return { id, child_id: "c", kind: "activity_guide", title: id, content_markdown: "# x", status, source_refs: [], generator_mode: "template", review_note: null, request_topic: id, request_goal: null, version: 1, parent_material_id: null, version_note: null }; }
describe("MaterialWorkspace inactive count", () => {
  it("counts rejected and archived material together", () => {
    const html = renderToStaticMarkup(<MaterialWorkspace materials={[m("r", "rejected"), m("a", "archived")]} resources={[]} materialKind="activity_guide" topic="" goal="" selectedResourceRefs={[]} busy={false} error={null} revisionNotes={{}} editingMaterialId={null} onKindChange={noop} onTopicChange={noop} onGoalChange={noop} onToggleResource={noop} onGenerate={noop} onReview={noop} onRevisionNoteChange={noop} onRevise={noop} onEditStart={noop} onEdit={noop} onPrint={noop} />);
    expect(html).toContain("사용하지 않는 자료 2개");
  });
});
