import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { LearningWiki } from "../learning-wiki-api";
import { LearningWikiContent } from "./LearningWikiPanel";

const wiki: LearningWiki = {
  id: "wiki-a",
  child_id: "child-a",
  title: "Learning Wiki",
  content_markdown: "## 이어지는 질문\n\n씨앗은 왜 날아가? <img src=x onerror=alert(1)>",
  source_refs: ["learning_log:record-a"],
  revision: 2,
  rebuilt_at: "2026-11-03T00:00:00Z",
  generator_mode: "deterministic_projection",
  derived: true,
};

describe("Learning Wiki provenance", () => {
  it("shows original evidence and escapes untrusted context without a diagnostic claim", () => {
    const html = renderToStaticMarkup(<LearningWikiContent wiki={wiki} />);
    expect(html).toContain("씨앗은 왜 날아가?");
    expect(html).toContain("learning_log:record-a");
    expect(html).toContain("버전 2");
    expect(html).toContain("판정이 아닙니다");
    expect(html).toContain("&lt;img");
    expect(html).not.toContain("<img");
  });

  it("treats absent observations as a neutral empty state", () => {
    const html = renderToStaticMarkup(<LearningWikiContent wiki={{ ...wiki, source_refs: [] }} />);
    expect(html).toContain("질문이나 경험을 남기면");
    expect(html).not.toContain("씨앗은 왜 날아가?");
  });

  it("keeps generated source IDs in collapsed provenance without repeating them in the summary", () => {
    const sourceRefs = [
      "learning_log:019a11d1-1111-7111-8111-111111111111",
      "activity_plan:019a11d1-2222-7222-8222-222222222222",
    ];
    const content = [
      "## 이미 해본 경험",
      "- 씨앗의 모양과 이동 방법을 비교했다.",
      `  - 근거: \`${sourceRefs[0]}\`, \`${sourceRefs[1]}\``,
      "- 아이가 '근거: 관찰한 모양이 달라서'라고 설명했다.",
      "  - 근거: 관찰한 모양이 달랐다.",
      "  - 근거: `아이가 직접 쓴 인용`",
    ].join("\n");
    const input = { ...wiki, source_refs: sourceRefs, content_markdown: content };
    const original = JSON.stringify(input);
    const html = renderToStaticMarkup(<LearningWikiContent wiki={input} />);
    const visibleSummary = html.split("<details>")[0];
    expect(visibleSummary).toContain("씨앗의 모양과 이동 방법을 비교했다.");
    expect(visibleSummary).toContain("관찰한 모양이 달라서");
    expect(visibleSummary).toContain("관찰한 모양이 달랐다.");
    expect(visibleSummary).toContain("아이가 직접 쓴 인용");
    for (const source of sourceRefs) {
      expect(visibleSummary).not.toContain(source);
      expect(html.slice(html.indexOf("<details>"))).toContain(source);
    }
    expect(html).not.toContain("<details open");
    expect(JSON.stringify(input)).toBe(original);
  });
});
