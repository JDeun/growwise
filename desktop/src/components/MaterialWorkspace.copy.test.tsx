import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { MaterialWorkspace } from "./MaterialWorkspace";

const noop = () => undefined;

describe("MaterialWorkspace degraded-mode copy", () => {
  it("does not imply that generation requires an LLM", () => {
    const html = renderToStaticMarkup(<MaterialWorkspace materials={[]} resources={[]} materialKind="activity_guide" topic="" goal="" selectedResourceRefs={[]} busy={false} error={null} revisionNotes={{}} editingMaterialId={null} onKindChange={noop} onTopicChange={noop} onGoalChange={noop} onToggleResource={noop} onGenerate={noop} onReview={noop} onRevisionNoteChange={noop} onRevise={noop} onEditStart={noop} onEdit={noop} onPrint={noop} />);
    expect(html).toContain("AI 보조 기능이 없어도");
    expect(html).toContain("기본 템플릿으로 자료를 만들 수 있습니다");
  });
});
