import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { GeneratedMaterial } from "../api";
import { MaterialWorkspace } from "./MaterialWorkspace";
const noop = () => undefined;
describe("MaterialWorkspace inactive material", () => {
  it("keeps rejected material recoverable but outside active lanes", () => {
    const material: GeneratedMaterial = { id: "m1", child_id: "c1", kind: "field_trip", title: "사용하지 않을 자료", content_markdown: "# x", status: "rejected", source_refs: [], generator_mode: "template", review_note: null, request_topic: "x", request_goal: null, version: 1, parent_material_id: null, version_note: null };
    const html = renderToStaticMarkup(<MaterialWorkspace materials={[material]} resources={[]} materialKind="field_trip" topic="" goal="" selectedResourceRefs={[]} busy={false} error={null} revisionNotes={{}} editingMaterialId={null} onKindChange={noop} onTopicChange={noop} onGoalChange={noop} onToggleResource={noop} onGenerate={noop} onReview={noop} onRevisionNoteChange={noop} onRevise={noop} onEditStart={noop} onEdit={noop} onPrint={noop} />);
    expect(html).toContain("사용하지 않는 자료 1개");
    expect(html).toContain("사용하지 않을 자료");
    expect(html).not.toContain("인쇄 / PDF 저장");
  });
});
