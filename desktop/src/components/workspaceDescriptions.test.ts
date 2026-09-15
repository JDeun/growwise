import { describe, expect, it } from "vitest";

import { WORKSPACE_DESCRIPTIONS } from "./workspaceDescriptions";
import { WORKSPACE_VIEWS } from "./workspaceViews";

describe("workspaceDescriptions", () => {
  it("describes every registered workspace", () => {
    for (const view of WORKSPACE_VIEWS) expect(WORKSPACE_DESCRIPTIONS[view]).toBeTruthy();
  });
});
