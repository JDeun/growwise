import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { GeneratedMaterial } from "../api";
import { MaterialWorkspace } from "./MaterialWorkspace";
const noop = () => undefined;
describe("MaterialWorkspace parent edit", () => {
  it("offers editing both before and after approval without mutating copy in place", () => {
    const base: GeneratedMaterial = { id: "m1", child_id: "c1", kind: "reading_activity", title: "읽기", content_markdown: "# 읽기", status: "review_pending", source_refs: [], generator_mode: "template", review_note: null, request_topic: "읽기", request_goal: null, version: 1, parent_material_id: null, version_note: null };
    const html = renderToStaticMarkup(<MaterialWorkspace materials={[base, { ...base, id: "m2", status: "approved", version: 2 }]} resources={[]} materialKind="reading_activity" topic="" goal="" selectedResourceRefs={[]} busy={false} error={null} revisionNotes={{}} editingMaterialId={null} onKindChange={noop} onTopicChange={noop} onGoalChange={noop} onToggleResource={noop} onGenerate={noop} onReview={noop} onRevisionNoteChange={noop} onRevise={noop} onEditStart={noop} onEdit={noop} onPrint={noop} />);
    expect(html).toContain("직접 편집");
    expect(html).toContain("새 편집본 만들기");
  });
});
