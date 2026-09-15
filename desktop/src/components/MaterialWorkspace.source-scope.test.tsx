import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { ResourceRecord } from "../api";
import { MaterialWorkspace } from "./MaterialWorkspace";
const noop = () => undefined;
const resource: ResourceRecord = { id: "r1", kind: "note", title: "부모 메모", child_id: "c1", summary: null, content: "내용", source_url: null, source_name: "parent", author: null, tags: [], stage_tags: [], provenance: {} };
describe("MaterialWorkspace grounding", () => {
  it("renders resources unchecked unless explicitly selected", () => {
    const html = renderToStaticMarkup(<MaterialWorkspace materials={[]} resources={[resource]} materialKind="activity_guide" topic="놀이" goal="" selectedResourceRefs={[]} busy={false} error={null} revisionNotes={{}} editingMaterialId={null} onKindChange={noop} onTopicChange={noop} onGoalChange={noop} onToggleResource={noop} onGenerate={noop} onReview={noop} onRevisionNoteChange={noop} onRevise={noop} onEditStart={noop} onEdit={noop} onPrint={noop} />);
    expect(html).toContain("부모 메모");
    expect(html).not.toContain('checked=""');
  });
});
