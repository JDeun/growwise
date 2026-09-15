import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { ResourceRecord } from "../api";
import { MaterialWorkspace } from "./MaterialWorkspace";
const noop = () => undefined;
describe("MaterialWorkspace grounding copy", () => {
  it("states that only selected resources are connected", () => {
    const resource: ResourceRecord = { id: "r", kind: "note", title: "메모", child_id: "c", summary: null, content: null, source_url: null, source_name: null, author: null, tags: [], stage_tags: [], provenance: {} };
    const html = renderToStaticMarkup(<MaterialWorkspace materials={[]} resources={[resource]} materialKind="activity_guide" topic="x" goal="" selectedResourceRefs={[]} busy={false} error={null} revisionNotes={{}} editingMaterialId={null} onKindChange={noop} onTopicChange={noop} onGoalChange={noop} onToggleResource={noop} onGenerate={noop} onReview={noop} onRevisionNoteChange={noop} onRevise={noop} onEditStart={noop} onEdit={noop} onPrint={noop} />);
    expect(html).toContain("선택한 자료만 명시적으로 생성 맥락에 연결됩니다");
  });
});
