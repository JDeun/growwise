import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { GeneratedMaterial } from "../api";
import { MaterialWorkspace } from "./MaterialWorkspace";
const noop = () => undefined;
const material: GeneratedMaterial = { id: "m1", child_id: "c1", kind: "reading_activity", title: "읽기", content_markdown: "# 읽기", status: "review_pending", source_refs: [], generator_mode: "template", review_note: null, request_topic: "읽기", request_goal: null, version: 1, parent_material_id: null, version_note: null };
describe("MaterialWorkspace revision intent", () => {
  it("keeps the new-version action disabled until a revision note exists", () => {
    const html = renderToStaticMarkup(<MaterialWorkspace materials={[material]} resources={[]} materialKind="reading_activity" topic="" goal="" selectedResourceRefs={[]} busy={false} error={null} revisionNotes={{}} editingMaterialId={null} onKindChange={noop} onTopicChange={noop} onGoalChange={noop} onToggleResource={noop} onGenerate={noop} onReview={noop} onRevisionNoteChange={noop} onRevise={noop} onEditStart={noop} onEdit={noop} onPrint={noop} />);
    expect(html).toMatch(/disabled=""[^>]*>새 버전 만들기/);
  });
});
