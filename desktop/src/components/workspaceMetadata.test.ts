import { describe, expect, it } from "vitest";

import { WORKSPACE_LABELS } from "./workspaceLabels";
import { WORKSPACE_LAYOUT } from "./workspaceLayout";
import { WORKSPACE_VIEWS } from "./workspaceViews";

describe("workspace metadata", () => {
  it("stays complete for every registered workspace", () => {
    for (const view of WORKSPACE_VIEWS) {
      expect(WORKSPACE_LABELS[view]).toBeTruthy();
      expect(WORKSPACE_LAYOUT[view]).toBeTruthy();
    }
  });
});
