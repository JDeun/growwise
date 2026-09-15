import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { MaterialWorkspace } from "./MaterialWorkspace";

const noop = () => undefined;

describe("MaterialWorkspace accessibility", () => {
  it("exposes named review and approved regions and an alert error", () => {
    const html = renderToStaticMarkup(
      <MaterialWorkspace
        materials={[]}
        resources={[]}
        materialKind="science_inquiry"
        topic="달팽이"
        goal=""
        selectedResourceRefs={[]}
        busy={false}
        error="생성 실패"
        revisionNotes={{}}
        editingMaterialId={null}
        onKindChange={noop}
        onTopicChange={noop}
        onGoalChange={noop}
        onToggleResource={noop}
        onGenerate={noop}
        onReview={noop}
        onRevisionNoteChange={noop}
        onRevise={noop}
        onEditStart={noop}
        onEdit={noop}
        onPrint={noop}
      />,
    );

    expect(html).toContain('aria-labelledby="materials-title"');
    expect(html).toContain('aria-labelledby="review-lane-title"');
    expect(html).toContain('aria-labelledby="approved-lane-title"');
    expect(html).toContain('role="alert"');
  });
});
