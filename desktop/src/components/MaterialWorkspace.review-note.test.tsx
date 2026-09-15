import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { GeneratedMaterial } from "../api";
import { MaterialWorkspace } from "./MaterialWorkspace";
const noop = () => undefined;
describe("MaterialWorkspace review notes", () => {
  it("renders review notes as escaped text", () => {
    const material: GeneratedMaterial = { id: "m1", child_id: "c1", kind: "writing_prompt", title: "글쓰기", content_markdown: "# 글쓰기", status: "revision_requested", source_refs: [], generator_mode: "template", review_note: "<script>bad()</script> 질문을 줄여 주세요", request_topic: "글쓰기", request_goal: null, version: 1, parent_material_id: null, version_note: null };
    const html = renderToStaticMarkup(<MaterialWorkspace materials={[material]} resources={[]} materialKind="writing_prompt" topic="" goal="" selectedResourceRefs={[]} busy={false} error={null} revisionNotes={{}} editingMaterialId={null} onKindChange={noop} onTopicChange={noop} onGoalChange={noop} onToggleResource={noop} onGenerate={noop} onReview={noop} onRevisionNoteChange={noop} onRevise={noop} onEditStart={noop} onEdit={noop} onPrint={noop} />);
    expect(html).toContain("&lt;script&gt;bad()&lt;/script&gt;");
    expect(html).toContain("질문을 줄여 주세요");
  });
});
