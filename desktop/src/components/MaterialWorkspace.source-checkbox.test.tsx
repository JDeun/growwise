import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { ResourceRecord } from "../api";
import { MaterialWorkspace } from "./MaterialWorkspace";
const noop = () => undefined;
describe("MaterialWorkspace selected grounding", () => {
  it("marks only explicitly selected resource references", () => {
    const resources: ResourceRecord[] = ["a", "b"].map((id) => ({ id, kind: "note", title: id, child_id: "c1", summary: null, content: id, source_url: null, source_name: "parent", author: null, tags: [], stage_tags: [], provenance: {} }));
    const html = renderToStaticMarkup(<MaterialWorkspace materials={[]} resources={resources} stage="preschool_3_5" materialKind="activity_guide" topic="놀이" goal="" selectedResourceRefs={["resource:b"]} busy={false} error={null} revisionNotes={{}} editingMaterialId={null} onKindChange={noop} onTopicChange={noop} onGoalChange={noop} onToggleResource={noop} onGenerate={noop} onReview={noop} onRevisionNoteChange={noop} onRevise={noop} onEditStart={noop} onEdit={noop} onPrint={noop} />);
    expect((html.match(/type="checkbox" checked=""/g) ?? []).length).toBe(1);
    expect((html.match(/type="checkbox"/g) ?? []).length).toBe(2);
  });
});
