import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { ResourceRecord } from "../api";
import { MaterialSources } from "./MaterialSources";

function resource(id: string, title: string): ResourceRecord {
  return {
    id,
    kind: "book",
    title,
    child_id: null,
    summary: null,
    content: null,
    source_url: null,
    source_name: null,
    author: null,
    tags: [],
    stage_tags: [],
    provenance: {},
  };
}

describe("MaterialSources", () => {
  it("renders a resolved title for each library source ref", () => {
    const html = renderToStaticMarkup(
      <MaterialSources
        sourceRefs={["resource:r1", "resource:r2"]}
        resources={[resource("r1", "달팽이 관찰 그림책"), resource("r2", "비 오는 날 산책 노트")]}
      />,
    );

    expect(html).toContain("달팽이 관찰 그림책");
    expect(html).toContain("비 오는 날 산책 노트");
  });

  it("shows external provenance refs verbatim", () => {
    const html = renderToStaticMarkup(<MaterialSources sourceRefs={["osm:place:123"]} />);

    expect(html).toContain("osm:place:123");
  });

  it("renders the empty state when there are no source refs", () => {
    const html = renderToStaticMarkup(<MaterialSources sourceRefs={[]} />);

    expect(html).toContain("연결된 출처가 없습니다.");
    expect(html).not.toContain('role="list"');
  });

  it("exposes accessible list semantics and a labelled region", () => {
    const html = renderToStaticMarkup(<MaterialSources sourceRefs={["resource:r1"]} />);

    expect(html).toContain('role="list"');
    expect(html).toContain("aria-label=");
    expect(html).toContain('aria-labelledby="material-sources-title"');
    expect(html).toContain("<li>");
  });
});
