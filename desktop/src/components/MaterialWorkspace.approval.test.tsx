import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { GeneratedMaterial } from "../api";
import { MaterialWorkspace } from "./MaterialWorkspace";
const noop = () => undefined;
describe("MaterialWorkspace approval", () => {
  it("requires an explicit parent-facing approval action", () => {
    const material: GeneratedMaterial = { id: "m1", child_id: "c1", kind: "english_card", title: "영어", content_markdown: "# 영어", status: "review_pending", source_refs: [], generator_mode: "template", review_note: null, request_topic: "영어", request_goal: null, version: 1, parent_material_id: null, version_note: null };
    const html = renderToStaticMarkup(<MaterialWorkspace materials={[material]} resources={[]} materialKind="english_card" topic="" goal="" selectedResourceRefs={[]} busy={false} error={null} revisionNotes={{}} editingMaterialId={null} onKindChange={noop} onTopicChange={noop} onGoalChange={noop} onToggleResource={noop} onGenerate={noop} onReview={noop} onRevisionNoteChange={noop} onRevise={noop} onEditStart={noop} onEdit={noop} onPrint={noop} />);
    expect(html).toContain("승인하고 사용");
    expect(html).not.toContain("자동 승인");
  });
});
