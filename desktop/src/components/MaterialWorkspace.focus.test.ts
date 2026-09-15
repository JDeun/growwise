import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

describe("desktop focus visibility", () => {
  it("keeps focus-visible outlines for material form controls", () => {
    const css = readFileSync(fileURLToPath(new URL("../styles.css", import.meta.url)), "utf8");
    expect(css).toContain("input:focus-visible");
    expect(css).toContain("textarea:focus-visible");
    expect(css).toContain("select:focus-visible");
    expect(css).toContain("outline: 3px solid");
  });

  it("keeps a visible focus ring on the keyboard-navigable workspace nav", () => {
    const css = readFileSync(fileURLToPath(new URL("../styles.css", import.meta.url)), "utf8");
    expect(css).toContain(".workspace-nav-item:focus-visible");
  });
});
