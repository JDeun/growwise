import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { MaterialWorkspace } from "./MaterialWorkspace";
const noop = () => undefined;
describe("MaterialWorkspace no-resource fallback", () => {
  it("keeps the composer usable when no resource records exist", () => {
    const html = renderToStaticMarkup(<MaterialWorkspace materials={[]} resources={[]} materialKind="activity_guide" topic="블록 놀이" goal="" selectedResourceRefs={[]} busy={false} error={null} revisionNotes={{}} editingMaterialId={null} onKindChange={noop} onTopicChange={noop} onGoalChange={noop} onToggleResource={noop} onGenerate={noop} onReview={noop} onRevisionNoteChange={noop} onRevise={noop} onEditStart={noop} onEdit={noop} onPrint={noop} />);
    expect(html).toContain("활동 가이드 만들기");
    expect(html).not.toContain("근거로 사용할 내 자료(선택)");
  });
});
