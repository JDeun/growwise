import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { GeneratedMaterial } from "../api";
import { MaterialWorkspace } from "./MaterialWorkspace";

const noop = () => undefined;
const base: GeneratedMaterial = {
  id: "material-1",
  child_id: "child-1",
  kind: "reading_activity",
  title: "고양이 읽기",
  content_markdown: "# 고양이 읽기\n\n질문을 나눠 보세요.",
  status: "review_pending",
  source_refs: [],
  generator_mode: "template",
  review_note: null,
  request_topic: "고양이",
  request_goal: null,
  version: 1,
  parent_material_id: null,
  version_note: null,
};

function render(materials: GeneratedMaterial[]) {
  return renderToStaticMarkup(
    <MaterialWorkspace
      materials={materials}
      resources={[]}
      materialKind="reading_activity"
      topic="고양이"
      goal=""
      selectedResourceRefs={[]}
      busy={false}
      error={null}
      revisionNotes={{}}
      editingMaterialId={null}
      onKindChange={noop}
      onTopicChange={noop}
      onGoalChange={noop}
      onToggleResource={noop}
      onGenerate={noop}
      onReview={noop}
      onRevisionNoteChange={noop}
      onRevise={noop}
      onEditStart={noop}
      onEdit={noop}
      onPrint={noop}
    />,
  );
}

describe("MaterialWorkspace", () => {
  it("separates draft, parent-review, and approved-use stages", () => {
    const html = render([
      { ...base, id: "draft", status: "draft" },
      { ...base, id: "review", status: "review_pending" },
      { ...base, id: "approved", status: "approved" },
    ]);
    expect(html).toContain("1. 초안");
    expect(html).toContain("2. 부모 검토");
    expect(html).toContain("3. 승인·사용");
    expect(html).toContain("부모 검토로 보내기");
    expect(html).toContain("승인하고 사용");
    expect(html).toContain("인쇄 / PDF 내보내기");
  });

  it("keeps review-pending material out of the printable lane", () => {
    const html = render([base]);
    expect(html).toContain("부모 검토 필요");
    expect(html).toContain("승인하고 사용");
    expect(html).not.toContain("인쇄 / PDF 내보내기");
  });

  it("only exposes print and PDF export after parent approval", () => {
    const html = render([{ ...base, status: "approved" }]);
    expect(html).toContain("승인·사용");
    expect(html).toContain("인쇄 / PDF 내보내기");
    expect(html).not.toContain("승인하고 사용");
  });

  it("communicates deterministic generation availability", () => {
    const html = render([]);
    expect(html).toContain("AI 연결 여부와 관계없이 기본 템플릿으로 생성할 수 있습니다.");
  });
});
