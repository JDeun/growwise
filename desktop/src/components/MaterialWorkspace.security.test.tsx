import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { GeneratedMaterial } from "../api";
import { MaterialWorkspace } from "./MaterialWorkspace";
const noop = () => undefined;
const material: GeneratedMaterial = { id: "m1", child_id: "c1", kind: "activity_guide", title: "unsafe-looking", content_markdown: '<img src=x onerror="alert(1)"><script>alert(2)</script>', status: "review_pending", source_refs: [], generator_mode: "template", review_note: null, request_topic: "x", request_goal: null, version: 1, parent_material_id: null, version_note: null };
describe("MaterialWorkspace rendering boundary", () => {
  it("escapes generated markdown instead of injecting executable HTML", () => {
    const html = renderToStaticMarkup(<MaterialWorkspace materials={[material]} resources={[]} materialKind="activity_guide" topic="" goal="" selectedResourceRefs={[]} busy={false} error={null} revisionNotes={{}} editingMaterialId={null} onKindChange={noop} onTopicChange={noop} onGoalChange={noop} onToggleResource={noop} onGenerate={noop} onReview={noop} onRevisionNoteChange={noop} onRevise={noop} onEditStart={noop} onEdit={noop} onPrint={noop} />);
    expect(html).toContain("&lt;script&gt;");
    expect(html).not.toContain("<script>alert(2)</script>");
  });
});
