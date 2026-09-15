import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { MaterialWorkspace } from "./MaterialWorkspace";
const noop = () => undefined;
describe("MaterialWorkspace keyboard semantics", () => {
  it("uses native form controls rather than click-only divs", () => {
    const html = renderToStaticMarkup(<MaterialWorkspace materials={[]} resources={[]} stage="preschool_3_5" materialKind="activity_guide" topic="" goal="" selectedResourceRefs={[]} busy={false} error={null} revisionNotes={{}} editingMaterialId={null} onKindChange={noop} onTopicChange={noop} onGoalChange={noop} onToggleResource={noop} onGenerate={noop} onReview={noop} onRevisionNoteChange={noop} onRevise={noop} onEditStart={noop} onEdit={noop} onPrint={noop} />);
    expect(html).toContain("<form");
    expect(html).toContain("<fieldset");
    expect(html).toContain('type="radio"');
    expect(html).toContain('name="material-kind"');
    expect(html).toContain('type="submit"');
    expect(html).not.toContain('role="button"');
  });
});
