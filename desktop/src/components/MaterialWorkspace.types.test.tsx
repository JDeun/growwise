import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { MATERIAL_KIND_LABELS } from "../material-workflow";
import { MaterialWorkspace } from "./MaterialWorkspace";

const noop = () => undefined;

describe("MaterialWorkspace kinds", () => {
  it("offers every material kind supported by typed IPC", () => {
    const html = renderToStaticMarkup(<MaterialWorkspace materials={[]} resources={[]} materialKind="activity_guide" topic="" goal="" selectedResourceRefs={[]} busy={false} error={null} revisionNotes={{}} editingMaterialId={null} onKindChange={noop} onTopicChange={noop} onGoalChange={noop} onToggleResource={noop} onGenerate={noop} onReview={noop} onRevisionNoteChange={noop} onRevise={noop} onEditStart={noop} onEdit={noop} onPrint={noop} />);
    for (const label of Object.values(MATERIAL_KIND_LABELS)) expect(html).toContain(label);
  });
});
