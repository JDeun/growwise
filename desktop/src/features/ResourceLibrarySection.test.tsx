import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import type { ResourceRecord } from "../api";
import { filterResources, ResourceLibrarySection } from "./ResourceLibrarySection";

const resources: ResourceRecord[] = [
  {
    id: "note-1",
    kind: "note",
    title: "Moon phases",
    child_id: "child-1",
    summary: "달의 모양 관찰",
    content: "crescent moon observation",
    source_url: null,
    source_name: "parent",
    author: null,
    tags: ["science"],
    stage_tags: ["elementary"],
    provenance: { origin: "desktop_manual" },
  },
  {
    id: "book-1",
    kind: "book",
    title: "Forest book",
    child_id: "child-1",
    summary: null,
    content: "trees and insects",
    source_url: null,
    source_name: "library",
    author: "Writer",
    tags: ["nature"],
    stage_tags: ["elementary"],
    provenance: { origin: "catalog" },
  },
];

describe("ResourceLibrarySection", () => {
  it("filters by text across content and tags and by resource kind", () => {
    expect(filterResources(resources, "science", "all").map((item) => item.id)).toEqual([
      "note-1",
    ]);
    expect(filterResources(resources, "insects", "book").map((item) => item.id)).toEqual([
      "book-1",
    ]);
    expect(filterResources(resources, "moon", "book")).toEqual([]);
  });

  it("exposes search, filter, detail, edit, and delete affordances", () => {
    const html = renderToStaticMarkup(
      <ResourceLibrarySection
        resourceKind="note"
        resourceTitle=""
        resourceContent=""
        saving={false}
        error={null}
        loadState={{ kind: "ready" }}
        resources={resources}
        onKindChange={vi.fn()}
        onTitleChange={vi.fn()}
        onContentChange={vi.fn()}
        onSubmit={vi.fn()}
        onRetry={vi.fn()}
        onUpdate={vi.fn(async () => undefined)}
        onDelete={vi.fn(async () => undefined)}
      />,
    );

    expect(html).toContain("자료 검색");
    expect(html).toContain("종류 필터");
    expect((html.match(/>상세<\/button>/g) ?? []).length).toBe(2);
    expect((html.match(/>편집<\/button>/g) ?? []).length).toBe(2);
    expect((html.match(/>삭제<\/button>/g) ?? []).length).toBe(2);
  });
});
