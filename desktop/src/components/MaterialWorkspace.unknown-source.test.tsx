import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { GeneratedMaterial } from "../api";
import { MaterialWorkspace } from "./MaterialWorkspace";
const noop = () => undefined;
describe("MaterialWorkspace external provenance", () => {
  it("shows non-resource provenance labels verbatim for review", () => {
    const material: GeneratedMaterial = { id: "m1", child_id: "c1", kind: "field_trip", title: "탐방", content_markdown: "# 탐방", status: "review_pending", source_refs: ["osm:place:123"], generator_mode: "template", review_note: null, request_topic: "탐방", request_goal: null, version: 1, parent_material_id: null, version_note: null };
    const html = renderToStaticMarkup(<MaterialWorkspace materials={[material]} resources={[]} materialKind="field_trip" topic="" goal="" selectedResourceRefs={[]} busy={false} error={null} revisionNotes={{}} editingMaterialId={null} onKindChange={noop} onTopicChange={noop} onGoalChange={noop} onToggleResource={noop} onGenerate={noop} onReview={noop} onRevisionNoteChange={noop} onRevise={noop} onEditStart={noop} onEdit={noop} onPrint={noop} />);
    expect(html).toContain("osm:place:123");
  });
});
