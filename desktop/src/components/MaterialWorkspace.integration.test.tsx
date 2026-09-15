import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { MaterialWorkspaceIntegration, type MaterialWorkspaceController } from "./MaterialWorkspace.integration";

const noop = () => undefined;

describe("MaterialWorkspaceIntegration", () => {
  it("renders through the typed controller boundary", () => {
    const controller: MaterialWorkspaceController = {
      materials: [], resources: [], materialKind: "field_trip", materialTopic: "박물관", materialGoal: "관찰 중심", selectedResourceRefs: [], materialBusy: false, materialError: null, revisionNotes: {}, editingMaterialId: null,
      setMaterialKind: noop, setMaterialTopic: noop, setMaterialGoal: noop, toggleResourceRef: noop, handleGenerateMaterial: noop, handleReviewMaterial: noop, setRevisionNote: noop, handleReviseMaterial: noop, setEditingMaterialId: noop, handleParentEdit: noop, handlePrintMaterial: noop,
    };
    const html = renderToStaticMarkup(<MaterialWorkspaceIntegration controller={controller} />);
    expect(html).toContain("탐방·여행 활동지 만들기");
    expect(html).toContain("관찰 중심");
  });
});
