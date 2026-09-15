import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { MaterialWorkspace } from "./MaterialWorkspace";
const noop = () => undefined;
describe("MaterialWorkspace topic copy", () => {
  it("provides a concrete parent-facing topic example", () => {
    const html = renderToStaticMarkup(<MaterialWorkspace materials={[]} resources={[]} materialKind="science_inquiry" topic="" goal="" selectedResourceRefs={[]} busy={false} error={null} revisionNotes={{}} editingMaterialId={null} onKindChange={noop} onTopicChange={noop} onGoalChange={noop} onToggleResource={noop} onGenerate={noop} onReview={noop} onRevisionNoteChange={noop} onRevise={noop} onEditStart={noop} onEdit={noop} onPrint={noop} />);
    expect(html).toContain("비 오는 날의 달팽이");
  });
});
