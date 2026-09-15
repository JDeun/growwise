import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { GeneratedMaterial } from "../api";
import { MaterialWorkspace } from "./MaterialWorkspace";
const noop = () => undefined;
describe("MaterialWorkspace approved status", () => {
  it("labels printable material as approved", () => {
    const material: GeneratedMaterial = { id: "m1", child_id: "c1", kind: "science_inquiry", title: "과학", content_markdown: "# 과학", status: "approved", source_refs: [], generator_mode: "template", review_note: null, request_topic: "과학", request_goal: null, version: 1, parent_material_id: null, version_note: null };
    const html = renderToStaticMarkup(<MaterialWorkspace materials={[material]} resources={[]} materialKind="science_inquiry" topic="" goal="" selectedResourceRefs={[]} busy={false} error={null} revisionNotes={{}} editingMaterialId={null} onKindChange={noop} onTopicChange={noop} onGoalChange={noop} onToggleResource={noop} onGenerate={noop} onReview={noop} onRevisionNoteChange={noop} onRevise={noop} onEditStart={noop} onEdit={noop} onPrint={noop} />);
    expect(html).toContain("승인됨");
    expect(html).toContain("인쇄 / PDF 저장");
  });
});
