import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { GeneratedMaterial } from "../api";
import { MaterialWorkspace } from "./MaterialWorkspace";
const noop = () => undefined;
describe("MaterialWorkspace inactive review boundary", () => {
  it("does not expose approval controls for archived material", () => {
    const material: GeneratedMaterial = { id: "m1", child_id: "c1", kind: "activity_guide", title: "보관", content_markdown: "# 보관", status: "archived", source_refs: [], generator_mode: "template", review_note: null, request_topic: "보관", request_goal: null, version: 1, parent_material_id: null, version_note: null };
    const html = renderToStaticMarkup(<MaterialWorkspace materials={[material]} resources={[]} materialKind="activity_guide" topic="" goal="" selectedResourceRefs={[]} busy={false} error={null} revisionNotes={{}} editingMaterialId={null} onKindChange={noop} onTopicChange={noop} onGoalChange={noop} onToggleResource={noop} onGenerate={noop} onReview={noop} onRevisionNoteChange={noop} onRevise={noop} onEditStart={noop} onEdit={noop} onPrint={noop} />);
    expect(html).not.toContain("승인하고 사용");
    expect(html).not.toContain("직접 편집");
  });
});
