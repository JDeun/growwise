import type { ResourceCreateInput, ResourceRecord } from "./api";

export interface ResourceDetailsDraft {
  summary: string;
  sourceName: string;
  sourceUrl: string;
  author: string;
  tags: string;
  scope: "child" | "shared";
}

export const emptyResourceDetails = (): ResourceDetailsDraft => ({
  summary: "", sourceName: "", sourceUrl: "", author: "", tags: "", scope: "child",
});

export function resourceDetailsDraft(resource: ResourceRecord): ResourceDetailsDraft {
  return {
    summary: resource.summary ?? "", sourceName: resource.source_name ?? "",
    sourceUrl: resource.source_url ?? "", author: resource.author ?? "",
    tags: resource.tags.join(", "), scope: resource.child_id === null ? "shared" : "child",
  };
}

export function resourceDetailsPayload(
  draft: ResourceDetailsDraft, childId: string,
): Pick<ResourceCreateInput, "summary" | "source_name" | "source_url" | "author" | "tags" | "child_id"> {
  const tags = [...new Set(draft.tags.split(",").map((tag) => tag.trim()).filter(Boolean))];
  if (tags.length > 100 || tags.some((tag) => tag.length > 200)) {
    throw new Error("태그는 100개 이하, 각 200자 이하로 입력해 주세요.");
  }
  return {
    summary: draft.summary.trim() || null,
    source_name: draft.sourceName.trim() || null,
    source_url: draft.sourceUrl.trim() || null,
    author: draft.author.trim() || null,
    tags,
    child_id: draft.scope === "shared" ? null : childId,
  };
}
