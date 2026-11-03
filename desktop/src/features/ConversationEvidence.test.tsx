import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { ConversationEvidence as Evidence } from "../evidence-api";
import { ConversationEvidence, ConversationEvidenceContent } from "./ConversationEvidence";

const evidence: Evidence = {
  source_id: "record:synthetic", entity_id: "synthetic", entity_type: "learning_log",
  title: "씨앗 관찰 <script>bad()</script>", occurred_at: "2026-11-03T00:00:00Z",
  body: "부모가 직접 남긴 관찰 <img src=x onerror=bad()>\n아이의 다음 질문",
  source_url: "https://example.org/original",
};

describe("conversation originals", () => {
  it("offers keyboard-accessible disclosures instead of inert numbered source spans", () => {
    const html = renderToStaticMarkup(<ConversationEvidence childId="child-a" sourceIds={["record:one", "chunk:two:0"]} />);
    expect(html).toContain("<details");
    expect(html).toContain("<summary>기록 1 · 원본 보기</summary>");
    expect(html).toContain("자료 근거 2 · 원본 보기");
    expect(html).not.toContain("<details open");
    expect(html).not.toContain('title="record:one"');
  });

  it("renders actual original text as escaped text with its date and a safe link", () => {
    const html = renderToStaticMarkup(<ConversationEvidenceContent evidence={evidence} />);
    expect(html).toContain("부모가 직접 남긴 관찰");
    expect(html).toContain("아이의 다음 질문");
    expect(html).toContain('dateTime="2026-11-03T00:00:00Z"');
    expect(html).toContain("&lt;script&gt;");
    expect(html).not.toContain("<script>");
    expect(html).not.toContain("<img");
    expect(html).toContain('href="https://example.org/original"');
    expect(html).toContain("답변 이후 수정되었을 수 있습니다");
  });

  it("does not render an unsafe external URL even if a malformed transport payload supplies one", () => {
    for (const source_url of ["javascript:bad()", "file:///private/secret", "https://user:password@example.org"]) {
      const html = renderToStaticMarkup(<ConversationEvidenceContent evidence={{ ...evidence, source_url }} />);
      expect(html).not.toContain("href=");
    }
    const html = renderToStaticMarkup(<ConversationEvidence childId={null} sourceIds={["record:one"]} />);
    expect(html).not.toContain("<details");
  });
});
