import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { ResourceRecord } from "../api";
import { MaterialWorkspace } from "./MaterialWorkspace";
const noop = () => undefined;
describe("MaterialWorkspace resource kind", () => {
  it("shows resource kind alongside the title", () => {
    const resource: ResourceRecord = { id: "r", kind: "book", title: "책", child_id: "c", summary: null, content: null, source_url: null, source_name: null, author: null, tags: [], stage_tags: [], provenance: {} };
    const html = renderToStaticMarkup(<MaterialWorkspace materials={[]} resources={[resource]} materialKind="reading_activity" topic="책" goal="" selectedResourceRefs={[]} busy={false} error={null} revisionNotes={{}} editingMaterialId={null} onKindChange={noop} onTopicChange={noop} onGoalChange={noop} onToggleResource={noop} onGenerate={noop} onReview={noop} onRevisionNoteChange={noop} onRevise={noop} onEditStart={noop} onEdit={noop} onPrint={noop} />);
    expect(html).toContain("<small>book</small>");
  });
});
