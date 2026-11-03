import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ResourceDetailsFields, ResourceScopeField } from "./components/ResourceDetailsFields";
import { emptyResourceDetails, resourceDetailsDraft, resourceDetailsPayload } from "./resource-details";
import type { ResourceRecord } from "./api";

describe("resource metadata and scope", () => {
  it("defaults to the current child and keeps optional metadata empty", () => {
    expect(resourceDetailsPayload(emptyResourceDetails(), "child-a")).toEqual({
      child_id: "child-a", summary: null, source_name: null, source_url: null, author: null, tags: [],
    });
  });

  it("preserves editable metadata and device-wide scope through an edit draft", () => {
    const resource: ResourceRecord = {
      id: "resource-a", kind: "book", title: "달 관찰", child_id: null,
      summary: "달의 모양", content: "함께 기록", source_name: "도서관",
      source_url: "https://example.org/book", author: "김작가", tags: ["자연", "관찰"],
      stage_tags: ["elementary"], provenance: { origin: "catalog" },
    };
    const draft = resourceDetailsDraft(resource);
    expect(resourceDetailsPayload(draft, "child-a")).toEqual({
      child_id: null, summary: resource.summary, source_name: resource.source_name,
      source_url: resource.source_url, author: resource.author, tags: resource.tags,
    });
    const html = renderToStaticMarkup(<ResourceDetailsFields value={draft} onChange={() => undefined} />);
    expect(html).toContain('value="김작가"');
    expect(html).toContain('value="https://example.org/book"');
    expect(html).toContain('value="자연, 관찰"');
  });

  it("trims and deduplicates tags without dropping tags beyond the API limit silently", () => {
    const draft = { ...emptyResourceDetails(), tags: " 자연, ,관찰, 자연 " };
    expect(resourceDetailsPayload(draft, "child-a").tags).toEqual(["자연", "관찰"]);
    expect(() => resourceDetailsPayload({ ...draft, tags: "x".repeat(201) }, "child-a")).toThrow("200자");
    expect(() => resourceDetailsPayload({ ...draft, tags: Array.from({ length: 101 }, (_, i) => String(i)).join(",") }, "child-a")).toThrow("100개");
  });

  it("makes device-wide sharing consequences explicit before saving", () => {
    const html = renderToStaticMarkup(<ResourceScopeField value="shared" onChange={() => undefined} />);
    expect(html).toContain('value="shared" selected=""');
    expect(html).toContain("모든 아이 화면의 검색과 자료 생성에서 사용할 수 있습니다");
    expect(html).toContain("인터넷에 공개되지는 않습니다");
  });
});
