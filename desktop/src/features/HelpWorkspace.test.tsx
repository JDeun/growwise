import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { HelpWorkspace } from "./HelpWorkspace";

describe("HelpWorkspace bundled licenses", () => {
  it("provides offline full-text licenses in closed, keyboard-scrollable disclosures", () => {
    const html = renderToStaticMarkup(<HelpWorkspace active />);
    expect(html).toContain("Apache License");
    expect(html).toContain("Third-Party Notices");
    expect(html).toContain("langgraph-sdk");
    expect(html.match(/<details>/g)).toHaveLength(2);
    expect(html).not.toContain("<details open");
    expect(html).toContain('tabindex="0" aria-label="GrowWise 라이선스 전문"');
    expect(html).toContain('tabindex="0" aria-label="Python 런타임 의존성 고지 전문"');
  });

  it("does not mount the help content when inactive", () => {
    expect(renderToStaticMarkup(<HelpWorkspace active={false} />)).toBe("");
  });
});
