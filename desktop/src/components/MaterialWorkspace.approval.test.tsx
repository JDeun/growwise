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

  it("offers one primary use action while keeping workflow controls collapsed", () => {
    const material: GeneratedMaterial = { id: "m2", child_id: "c1", kind: "activity_guide", title: "산책 활동", content_markdown: "# 산책", status: "draft", source_refs: [], generator_mode: "template", review_note: null, request_topic: "산책", request_goal: null, version: 1, parent_material_id: null, version_note: null };
    const html = renderToStaticMarkup(<MaterialWorkspace materials={[material]} resources={[]} materialKind="activity_guide" topic="" goal="" selectedResourceRefs={[]} busy={false} error={null} revisionNotes={{}} editingMaterialId={null} onKindChange={noop} onTopicChange={noop} onGoalChange={noop} onToggleResource={noop} onGenerate={noop} onUse={noop} onReview={noop} onRevisionNoteChange={noop} onRevise={noop} onEditStart={noop} onEdit={noop} onPrint={noop} />);

    expect(html).toContain("이 활동 사용하기");
    expect(html).toContain('<details class="material-workflow-admin">');
    expect(html).not.toContain('<details class="material-workflow-admin" open');
    expect(html).toContain("부모 가이드·교육과정·출처는 필요할 때만");
  });

});
