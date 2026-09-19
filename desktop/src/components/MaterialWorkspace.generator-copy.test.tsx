import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { MaterialWorkspace } from "./MaterialWorkspace";

const noop = () => undefined;

describe("MaterialWorkspace product philosophy", () => {
  it("keeps review plumbing out of the primary product copy", () => {
    const html = renderToStaticMarkup(
      <MaterialWorkspace materials={[]} resources={[]} materialKind="activity_guide" topic="" goal="" selectedResourceRefs={[]} busy={false} error={null} revisionNotes={{}} editingMaterialId={null} onKindChange={noop} onTopicChange={noop} onGoalChange={noop} onToggleResource={noop} onGenerate={noop} onReview={noop} onRevisionNoteChange={noop} onRevise={noop} onEditStart={noop} onEdit={noop} onPrint={noop} />,
    );
    expect(html).toContain("아이에게 필요한 활동을 만들고 바로 사용합니다");
    expect(html).toContain("부모 가이드·교육과정·출처는 필요할 때만");
    expect(html).not.toContain("승인 전 자료는 인쇄하거나 PDF로 내보낼 수 없습니다");
  });
});
