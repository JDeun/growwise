import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { MaterialWorkspace } from "./MaterialWorkspace";
const noop = () => undefined;
describe("MaterialWorkspace errors", () => {
  it("announces errors without removing deterministic generation controls", () => {
    const html = renderToStaticMarkup(<MaterialWorkspace materials={[]} resources={[]} materialKind="math_activity" topic="덧셈" goal="" selectedResourceRefs={[]} busy={false} error="모델 연결 실패 — 기본 생성은 계속 사용할 수 있습니다." revisionNotes={{}} editingMaterialId={null} onKindChange={noop} onTopicChange={noop} onGoalChange={noop} onToggleResource={noop} onGenerate={noop} onReview={noop} onRevisionNoteChange={noop} onRevise={noop} onEditStart={noop} onEdit={noop} onPrint={noop} />);
    expect(html).toContain('role="alert"');
    expect(html).toContain("수학 놀이 만들기");
  });
});
