import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { GeneratedMaterial } from "../api";
import { MaterialWorkspace } from "./MaterialWorkspace";
const noop = () => undefined;
describe("MaterialWorkspace approved editing", () => {
  it("calls approved editing a new copy rather than implying in-place mutation", () => {
    const material: GeneratedMaterial = { id: "m1", child_id: "c1", kind: "activity_guide", title: "활동", content_markdown: "# 활동", status: "approved", source_refs: [], generator_mode: "template", review_note: null, request_topic: "활동", request_goal: null, version: 3, parent_material_id: "m0", version_note: null };
    const html = renderToStaticMarkup(<MaterialWorkspace materials={[material]} resources={[]} materialKind="activity_guide" topic="" goal="" selectedResourceRefs={[]} busy={false} error={null} revisionNotes={{}} editingMaterialId={null} onKindChange={noop} onTopicChange={noop} onGoalChange={noop} onToggleResource={noop} onGenerate={noop} onReview={noop} onRevisionNoteChange={noop} onRevise={noop} onEditStart={noop} onEdit={noop} onPrint={noop} />);
    expect(html).toContain("새 편집본 만들기");
  });
});
