import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { GeneratedMaterial } from "../api";
import { MaterialWorkspace } from "./MaterialWorkspace";

const noop = () => undefined;

describe("MaterialWorkspace print copy", () => {
  it("describes current OS print/PDF capability accurately", () => {
    const material: GeneratedMaterial = { id: "m1", child_id: "c1", kind: "reading_activity", title: "읽기", content_markdown: "# 읽기", status: "approved", source_refs: [], generator_mode: "template", review_note: null, request_topic: "읽기", request_goal: null, version: 1, parent_material_id: null, version_note: null };
    const html = renderToStaticMarkup(<MaterialWorkspace materials={[material]} resources={[]} materialKind="reading_activity" topic="" goal="" selectedResourceRefs={[]} busy={false} error={null} revisionNotes={{}} editingMaterialId={null} onKindChange={noop} onTopicChange={noop} onGoalChange={noop} onToggleResource={noop} onGenerate={noop} onReview={noop} onRevisionNoteChange={noop} onRevise={noop} onEditStart={noop} onEdit={noop} onPrint={noop} />);
    expect(html).toContain("인쇄 / PDF 내보내기");
    expect(html).not.toContain("전용 PDF");
  });
});
