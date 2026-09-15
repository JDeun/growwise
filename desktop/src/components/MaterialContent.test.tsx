import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { MaterialContent } from "./MaterialContent";

function render(markdown: string) {
  return renderToStaticMarkup(<MaterialContent markdown={markdown} />);
}

describe("MaterialContent", () => {
  it("renders headings and both list kinds", () => {
    const html = render("## 시작 전\n- 준비물을 챙깁니다\n- 관심 장면을 찾습니다\n\n## 순서\n1. 먼저 봅니다\n2. 이어서 말합니다");
    expect(html).toContain("<h2>시작 전</h2>");
    expect(html).toContain("<ul>");
    expect(html).toContain("<li>준비물을 챙깁니다</li>");
    expect(html).toContain("<ol>");
    expect(html).toContain("<li>먼저 봅니다</li>");
  });

  it("renders emphasis and inline code", () => {
    const html = render("**중요**한 `topic` 를 봅니다");
    expect(html).toContain("<strong>중요</strong>");
    expect(html).toContain("<code>topic</code>");
  });

  it("renders a Markdown table as an accessible table", () => {
    const html = render("| 단계 | 활동 |\n| --- | --- |\n| 1 | 관찰 |\n| 2 | 기록 |");
    expect(html).toContain("<table");
    expect(html).toContain("<thead>");
    expect(html).toContain('scope="col"');
    expect(html).toContain("<th");
    expect(html).toContain("단계");
    expect(html).toContain("<tbody>");
    expect(html).toContain("<td");
    expect(html).toContain("관찰");
  });

  it("renders blockquote and fenced-code figures/shapes", () => {
    const html = render("> 관찰 메모입니다\n\n```\n +---+\n | ^ |\n +---+\n```");
    expect(html).toContain("<blockquote>");
    expect(html).toContain("관찰 메모입니다");
    expect(html).toContain("<pre");
    expect(html).toContain("<code>");
    expect(html).toContain("+---+");
  });

  it("neutralizes embedded HTML so a script tag stays inert and escaped", () => {
    const malicious = "안녕 <script>alert('xss')</script> 끝";
    const html = render(malicious);
    // React escapes the angle brackets; no live <script> element is emitted.
    expect(html).not.toContain("<script>");
    expect(html).not.toContain("</script>");
    expect(html).toContain("&lt;script&gt;");
  });

  it("neutralizes an img onerror payload", () => {
    const html = render("![x](y) <img src=x onerror=alert(1)>");
    expect(html).not.toContain("<img");
    expect(html).toContain("&lt;img");
    expect(html).not.toContain("onerror=alert(1)>");
  });

  it("does not emit raw HTML from a table cell payload", () => {
    const html = render("| a | b |\n| --- | --- |\n| <b>x</b> | ok |");
    expect(html).not.toContain("<b>x</b>");
    expect(html).toContain("&lt;b&gt;x&lt;/b&gt;");
  });

  it("handles empty content without crashing", () => {
    expect(render("")).toContain('data-empty="true"');
    expect(render("   \n  \n")).toContain('data-empty="true"');
  });
});
