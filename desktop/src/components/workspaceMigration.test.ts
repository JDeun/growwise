import { describe, expect, it } from "vitest";

import { WORKSPACE_MIGRATION } from "./workspaceMigration";
import { PRODUCT_WORKSPACE_VIEWS } from "./workspaceViews";

describe("workspaceMigration", () => {
  it("maps every layout feature into a user-facing product workspace", () => {
    const productViews = new Set(PRODUCT_WORKSPACE_VIEWS);
    for (const target of Object.values(WORKSPACE_MIGRATION)) {
      expect(productViews.has(target)).toBe(true);
    }

    expect(WORKSPACE_MIGRATION.observations).toBe("learning");
    expect(WORKSPACE_MIGRATION.growth).toBe("profile");
    expect(WORKSPACE_MIGRATION.activities).toBe("materials");
    expect(WORKSPACE_MIGRATION.search).toBe("conversation");
    expect(WORKSPACE_MIGRATION.discovery).toBe("materials");
    expect(WORKSPACE_MIGRATION.library).toBe("materials");
  });
});
