import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { GeneratedMaterial, MaterialStatus } from "../api";
import { MaterialWorkspace } from "./MaterialWorkspace";

const noop = () => undefined;
const statuses: MaterialStatus[] = ["draft", "review_pending", "revision_requested", "rejected", "archived"];

function material(status: MaterialStatus): GeneratedMaterial {
  return { id: `m-${status}`, child_id: "c1", kind: "math_activity", title: status, content_markdown: "# test", status, source_refs: [], generator_mode: "template", review_note: null, request_topic: "test", request_goal: null, version: 1, parent_material_id: null, version_note: null };
}

describe("MaterialWorkspace adversarial policy", () => {
  it.each(statuses)("does not leak a print action for %s", (status) => {
    const html = renderToStaticMarkup(<MaterialWorkspace materials={[material(status)]} resources={[]} materialKind="math_activity" topic="test" goal="" selectedResourceRefs={[]} busy={false} error={null} revisionNotes={{}} editingMaterialId={null} onKindChange={noop} onTopicChange={noop} onGoalChange={noop} onToggleResource={noop} onGenerate={noop} onReview={noop} onRevisionNoteChange={noop} onRevise={noop} onEditStart={noop} onEdit={noop} onPrint={noop} />);
    expect(html).not.toContain("인쇄 / PDF 저장");
  });
});
