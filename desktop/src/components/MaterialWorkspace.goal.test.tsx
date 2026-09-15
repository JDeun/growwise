import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { MaterialWorkspace } from "./MaterialWorkspace";
const noop = () => undefined;
describe("MaterialWorkspace parent goal", () => {
  it("renders the optional parent goal as an editable input", () => {
    const html = renderToStaticMarkup(<MaterialWorkspace materials={[]} resources={[]} materialKind="reading_activity" topic="책" goal="정답보다 대화" selectedResourceRefs={[]} busy={false} error={null} revisionNotes={{}} editingMaterialId={null} onKindChange={noop} onTopicChange={noop} onGoalChange={noop} onToggleResource={noop} onGenerate={noop} onReview={noop} onRevisionNoteChange={noop} onRevise={noop} onEditStart={noop} onEdit={noop} onPrint={noop} />);
    expect(html).toContain("부모 목표(선택)");
    expect(html).toContain('value="정답보다 대화"');
  });
});
