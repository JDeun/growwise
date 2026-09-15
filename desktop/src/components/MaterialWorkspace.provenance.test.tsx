import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { GeneratedMaterial, ResourceRecord } from "../api";
import { MaterialWorkspace } from "./MaterialWorkspace";

const noop = () => undefined;
const resource: ResourceRecord = { id: "r1", kind: "book", title: "우리집 자연책", child_id: "c1", summary: null, content: "달팽이", source_url: null, source_name: "parent", author: null, tags: [], stage_tags: ["elementary"], provenance: { origin: "desktop_manual" } };
const material: GeneratedMaterial = { id: "m1", child_id: "c1", kind: "science_inquiry", title: "달팽이 관찰", content_markdown: "# 달팽이", status: "review_pending", source_refs: ["resource:r1"], generator_mode: "template", review_note: null, request_topic: "달팽이", request_goal: null, version: 1, parent_material_id: null, version_note: null };

describe("MaterialWorkspace provenance", () => {
  it("shows a human-readable source title during parent review", () => {
    const html = renderToStaticMarkup(<MaterialWorkspace materials={[material]} resources={[resource]} materialKind="science_inquiry" topic="" goal="" selectedResourceRefs={[]} busy={false} error={null} revisionNotes={{}} editingMaterialId={null} onKindChange={noop} onTopicChange={noop} onGoalChange={noop} onToggleResource={noop} onGenerate={noop} onReview={noop} onRevisionNoteChange={noop} onRevise={noop} onEditStart={noop} onEdit={noop} onPrint={noop} />);
    expect(html).toContain("우리집 자연책");
    expect(html).not.toContain("resource:r1</span>");
  });
});
