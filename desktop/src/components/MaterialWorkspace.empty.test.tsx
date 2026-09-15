import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { MaterialWorkspace } from "./MaterialWorkspace";
const noop = () => undefined;

describe("MaterialWorkspace empty states", () => {
  it("explains both review and approved empty lanes", () => {
    const html = renderToStaticMarkup(<MaterialWorkspace materials={[]} resources={[]} materialKind="english_card" topic="" goal="" selectedResourceRefs={[]} busy={false} error={null} revisionNotes={{}} editingMaterialId={null} onKindChange={noop} onTopicChange={noop} onGoalChange={noop} onToggleResource={noop} onGenerate={noop} onReview={noop} onRevisionNoteChange={noop} onRevise={noop} onEditStart={noop} onEdit={noop} onPrint={noop} />);
    expect(html).toContain("검토할 자료가 없습니다.");
    expect(html).toContain("승인된 자료가 없습니다.");
  });
});
