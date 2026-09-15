import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { GeneratedMaterial } from "../api";
import { MaterialWorkspace } from "./MaterialWorkspace";
const noop = () => undefined;
describe("MaterialWorkspace long content", () => {
  it("renders long content without truncating the source string", () => {
    const content = `# 긴 자료\n${"관찰 질문입니다. ".repeat(500)}`;
    const material: GeneratedMaterial = { id: "m1", child_id: "c1", kind: "science_inquiry", title: "긴 자료", content_markdown: content, status: "review_pending", source_refs: [], generator_mode: "template", review_note: null, request_topic: "긴 자료", request_goal: null, version: 1, parent_material_id: null, version_note: null };
    const html = renderToStaticMarkup(<MaterialWorkspace materials={[material]} resources={[]} materialKind="science_inquiry" topic="" goal="" selectedResourceRefs={[]} busy={false} error={null} revisionNotes={{}} editingMaterialId={null} onKindChange={noop} onTopicChange={noop} onGoalChange={noop} onToggleResource={noop} onGenerate={noop} onReview={noop} onRevisionNoteChange={noop} onRevise={noop} onEditStart={noop} onEdit={noop} onPrint={noop} />);
    expect((html.match(/관찰 질문입니다\./g) ?? []).length).toBe(500);
  });
});
