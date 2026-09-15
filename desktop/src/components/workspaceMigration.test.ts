import { describe, expect, it } from "vitest";

import { WORKSPACE_LAYOUT } from "./workspaceLayout";
import { WORKSPACE_MIGRATION } from "./workspaceMigration";

describe("workspaceMigration", () => {
  it("maps every legacy layout key back to its product workspace", () => {
    for (const [view, keys] of Object.entries(WORKSPACE_LAYOUT)) {
      for (const key of keys) expect(WORKSPACE_MIGRATION[key]).toBe(view);
    }
  });
});
