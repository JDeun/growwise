import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

describe("print rendering scope", () => {
  it("targets the current approved-material DOM without leaking stale single prints", () => {
    const path = fileURLToPath(new URL("./print.css", import.meta.url));
    const css = readFileSync(path, "utf8");

    expect(css).toContain('body[data-growwise-print-scope="approved"] .approved-card');
    expect(css).toContain(
      'body[data-growwise-print-scope="single"] .approved-card[data-growwise-print-target="true"]',
    );
    expect(css).toContain('body[data-growwise-print-scope="approved"] .print-material');
    expect(css).toContain('body[data-growwise-print-scope="single"] .print-material');
    expect(css).toContain(".material-queue-lanes");
    expect(css).not.toContain(".material-list");
  });

  it("removes the temporary approved print scope after the native print flow", () => {
    const path = fileURLToPath(new URL("./PrintApprovedMaterials.tsx", import.meta.url));
    const source = readFileSync(path, "utf8");

    expect(source).toContain('document.body.setAttribute(PRINT_SCOPE_ATTRIBUTE, "approved")');
    expect(source).toContain("document.body.removeAttribute(PRINT_SCOPE_ATTRIBUTE)");
    expect(source).toContain('window.addEventListener("afterprint", cleanup, { once: true })');
  });

  it("prints the reviewed MaterialContent card instead of the hidden raw Markdown copy", () => {
    const path = fileURLToPath(
      new URL("./components/MaterialWorkspace.tsx", import.meta.url),
    );
    const source = readFileSync(path, "utf8");

    expect(source).toContain('document.body.setAttribute(PRINT_SCOPE_ATTRIBUTE, "single")');
    expect(source).toContain('card.setAttribute(PRINT_TARGET_ATTRIBUTE, "true")');
    expect(source).toContain('event.currentTarget.closest(".approved-card")');
    expect(source).toContain("<MaterialContent markdown={material.content_markdown} />");
  });
});
