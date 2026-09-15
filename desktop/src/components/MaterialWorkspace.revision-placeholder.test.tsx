import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { GeneratedMaterial } from "../api";
import { MaterialWorkspace } from "./MaterialWorkspace";
const noop = () => undefined;
describe("MaterialWorkspace revision prompt", () => {
  it("gives a concrete revision example", () => {
    const m: GeneratedMaterial = { id: "m", child_id: "c", kind: "activity_guide", title: "x", content_markdown: "# x", status: "review_pending", source_refs: [], generator_mode: "template", review_note: null, request_topic: "x", request_goal: null, version: 1, parent_material_id: null, version_note: null };
    const html = renderToStaticMarkup(<MaterialWorkspace materials={[m]} resources={[]} materialKind="activity_guide" topic="" goal="" selectedResourceRefs={[]} busy={false} error={null} revisionNotes={{}} editingMaterialId={null} onKindChange={noop} onTopicChange={noop} onGoalChange={noop} onToggleResource={noop} onGenerate={noop} onReview={noop} onRevisionNoteChange={noop} onRevise={noop} onEditStart={noop} onEdit={noop} onPrint={noop} />);
    expect(html).toContain("질문 수를 줄이고 아이가 직접 관찰할 여백을 늘려 주세요");
  });
});
