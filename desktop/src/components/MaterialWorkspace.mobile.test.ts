import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

describe("material workspace responsive contract", () => {
  it("collapses lanes and composer on narrow windows", () => {
    const path = fileURLToPath(new URL("../styles.css", import.meta.url));
    const css = readFileSync(path, "utf8");
    expect(css).toContain(".material-lanes { grid-template-columns: 1fr; }");
    expect(css).toContain(".verification-list, .material-composer, .resource-grounding-list { grid-template-columns: 1fr; }");
  });
});
