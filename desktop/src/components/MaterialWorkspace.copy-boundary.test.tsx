import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { GeneratedMaterial } from "../api";
import { MaterialWorkspace } from "./MaterialWorkspace";
const noop = () => undefined;
describe("MaterialWorkspace implementation copy", () => {
  it("does not expose generator implementation mode on cards", () => {
    const material: GeneratedMaterial = { id: "m1", child_id: "c1", kind: "activity_guide", title: "놀이", content_markdown: "# 놀이", status: "review_pending", source_refs: [], generator_mode: "template_safety_fallback", review_note: null, request_topic: "놀이", request_goal: null, version: 1, parent_material_id: null, version_note: null };
    const html = renderToStaticMarkup(<MaterialWorkspace materials={[material]} resources={[]} materialKind="activity_guide" topic="" goal="" selectedResourceRefs={[]} busy={false} error={null} revisionNotes={{}} editingMaterialId={null} onKindChange={noop} onTopicChange={noop} onGoalChange={noop} onToggleResource={noop} onGenerate={noop} onReview={noop} onRevisionNoteChange={noop} onRevise={noop} onEditStart={noop} onEdit={noop} onPrint={noop} />);
    expect(html).not.toContain("template_safety_fallback");
  });
});
