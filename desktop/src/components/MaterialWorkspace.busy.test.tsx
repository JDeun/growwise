import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { GeneratedMaterial } from "../api";
import { MaterialWorkspace } from "./MaterialWorkspace";

const noop = () => undefined;
const material: GeneratedMaterial = { id: "m1", child_id: "c1", kind: "activity_guide", title: "활동", content_markdown: "# 활동", status: "review_pending", source_refs: [], generator_mode: "template", review_note: null, request_topic: "활동", request_goal: null, version: 1, parent_material_id: null, version_note: null };

describe("MaterialWorkspace mutation locking", () => {
  it("disables mutation controls while a material operation is running", () => {
    const html = renderToStaticMarkup(<MaterialWorkspace materials={[material]} resources={[]} materialKind="activity_guide" topic="활동" goal="" selectedResourceRefs={[]} busy error={null} revisionNotes={{ m1: "수정" }} editingMaterialId={null} onKindChange={noop} onTopicChange={noop} onGoalChange={noop} onToggleResource={noop} onGenerate={noop} onReview={noop} onRevisionNoteChange={noop} onRevise={noop} onEditStart={noop} onEdit={noop} onPrint={noop} />);
    expect((html.match(/disabled=""/g) ?? []).length).toBeGreaterThanOrEqual(6);
    expect(html).toContain("처리 중…");
  });
});
