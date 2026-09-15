import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

describe("desktop reduced motion", () => {
  it("keeps a prefers-reduced-motion override", () => {
    const css = readFileSync(fileURLToPath(new URL("../styles.css", import.meta.url)), "utf8");
    expect(css).toContain("@media (prefers-reduced-motion: reduce)");
  });
});
