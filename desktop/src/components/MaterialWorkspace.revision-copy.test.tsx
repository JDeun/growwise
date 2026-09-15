import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { GeneratedMaterial } from "../api";
import { MaterialWorkspace } from "./MaterialWorkspace";
const noop = () => undefined;
describe("MaterialWorkspace revision successor", () => {
  it("labels revision as creating a new version", () => {
    const material: GeneratedMaterial = { id: "m1", child_id: "c1", kind: "activity_guide", title: "활동", content_markdown: "# 활동", status: "review_pending", source_refs: [], generator_mode: "template", review_note: null, request_topic: "활동", request_goal: null, version: 1, parent_material_id: null, version_note: null };
    const html = renderToStaticMarkup(<MaterialWorkspace materials={[material]} resources={[]} materialKind="activity_guide" topic="" goal="" selectedResourceRefs={[]} busy={false} error={null} revisionNotes={{ m1: "질문 축소" }} editingMaterialId={null} onKindChange={noop} onTopicChange={noop} onGoalChange={noop} onToggleResource={noop} onGenerate={noop} onReview={noop} onRevisionNoteChange={noop} onRevise={noop} onEditStart={noop} onEdit={noop} onPrint={noop} />);
    expect(html).toContain("새 버전 만들기");
  });
});
