import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { MaterialWorkspace } from "./MaterialWorkspace";

const noop = () => undefined;

describe("MaterialWorkspace degraded-mode copy", () => {
  it("does not imply that generation requires an LLM", () => {
    const html = renderToStaticMarkup(<MaterialWorkspace materials={[]} resources={[]} materialKind="activity_guide" topic="" goal="" selectedResourceRefs={[]} busy={false} error={null} revisionNotes={{}} editingMaterialId={null} onKindChange={noop} onTopicChange={noop} onGoalChange={noop} onToggleResource={noop} onGenerate={noop} onReview={noop} onRevisionNoteChange={noop} onRevise={noop} onEditStart={noop} onEdit={noop} onPrint={noop} />);
    expect(html).toContain("AI 연결 여부와 관계없이");
    expect(html).toContain("기본 템플릿으로 생성할 수 있습니다");
  });
});
