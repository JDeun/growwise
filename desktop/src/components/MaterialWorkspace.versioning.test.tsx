import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { GeneratedMaterial } from "../api";
import { MaterialWorkspace } from "./MaterialWorkspace";

const noop = () => undefined;
const material: GeneratedMaterial = { id: "m2", child_id: "c1", kind: "writing_prompt", title: "두 번째 버전", content_markdown: "# v2", status: "review_pending", source_refs: [], generator_mode: "template", review_note: "문항 축소", request_topic: "하루", request_goal: null, version: 2, parent_material_id: "m1", version_note: "문항 축소", created_at: "2026-09-15T00:00:00Z" };

describe("MaterialWorkspace immutable versions", () => {
  it("makes version and review note visible before approval", () => {
    const html = renderToStaticMarkup(<MaterialWorkspace materials={[material]} resources={[]} materialKind="writing_prompt" topic="" goal="" selectedResourceRefs={[]} busy={false} error={null} revisionNotes={{}} editingMaterialId={null} onKindChange={noop} onTopicChange={noop} onGoalChange={noop} onToggleResource={noop} onGenerate={noop} onReview={noop} onRevisionNoteChange={noop} onRevise={noop} onEditStart={noop} onEdit={noop} onPrint={noop} />);
    expect(html).toContain("v2");
    expect(html).toContain("문항 축소");
  });
});
