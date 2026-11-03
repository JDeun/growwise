import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { GeneratedMaterial, Stage } from "../api";
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

function render(materials: GeneratedMaterial[], editingMaterialId: string | null = null, stage?: Stage) {
  return renderToStaticMarkup(
    <MaterialWorkspace
      materials={materials}
      resources={[]}
      stage={stage}
      materialKind="reading_activity"
      topic="고양이"
      goal=""
      selectedResourceRefs={[]}
      busy={false}
      error={null}
      revisionNotes={{}}
      editingMaterialId={editingMaterialId}
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
      onResultRecorded={noop}
    />,
  );
}

describe("MaterialWorkspace", () => {
  it("omits worksheets from infant previews and printable approved cards", () => {
    const html = render([{ ...base, kind: "activity_guide", status: "approved" }], null, "infant_0_2");
    expect(html).toContain("인쇄 / PDF 내보내기");
    expect(html).not.toContain("material-presentation-template");
    expect(html).not.toContain("material-presentation-writing-space");
  });
  it("projects standard publications in the primary and printable reading views while preserving raw edits", () => {
    const material = {
      ...base,
      status: "approved" as const,
      content_markdown: "# 고양이 읽기\n\n> GrowWise 활동 자료 · 부모가 내용을 확인한 뒤 사용합니다.\n\n## 오늘의 목표\n- 목표: 고양이 관찰하기\n- 교육과정 연결: 자연탐구\n- 적용 교육과정: 교육과정 정보\n- 기준 고시: 고시 정보\n\n## 준비물\n- 그림책\n\n## 단계별 활동 기준\n- 학습 수준: 관찰과 설명\n\n## 활동 자료\n1. 고양이의 움직임을 그려 봅니다.\n",
      parent_guide_markdown: "## 부모가 확인할 활동 기준\n활동 기준은 부모 가이드에서 확인합니다.",
    };
    const reading = render([material]);
    expect(reading).not.toContain("교육과정 연결: 자연탐구");
    expect(reading).not.toContain("학습 수준: 관찰과 설명");
    expect((reading.match(/고양이의 움직임을 그려 봅니다/g) ?? []).length).toBe(2);
    expect(reading).toContain("활동 기준은 부모 가이드에서 확인합니다.");
    const editing = render([material], material.id);
    expect(editing).toContain("교육과정 연결: 자연탐구");
    expect(editing).toContain("학습 수준: 관찰과 설명");
  });

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
    expect(html).toContain('aria-label="선택한 학습 자료 미리보기"');
    expect(html).toContain("<h3>새 자료 만들기</h3>");
    expect(html).toContain("이 활동 사용하기");
    expect(html).toContain('role="tablist"');
    expect(html).toContain("부모 가이드");
    expect(html).toContain("출처");
  });

  it("keeps review-pending material out of the printable and closed-loop lane", () => {
    const html = render([base]);
    expect(html).toContain("이 활동 사용하기");
    expect(html).toContain('<details class="material-workflow-admin">');
    expect(html).not.toContain("인쇄 / PDF 내보내기");
    expect(html).not.toContain("자료 사용과 결과");
  });

  it("only exposes print and closed-loop tracking after parent approval", () => {
    const html = render([{ ...base, status: "approved" }]);
    expect(html).toContain("승인·사용");
    expect(html).toContain("인쇄 / PDF 내보내기");
    expect(html).toContain("자료 사용과 결과");
    expect(html).toContain("이 자료를 실제로 사용한 상태와 결과를 이어서 기록합니다.");
    expect(html).not.toContain("승인하고 사용");
  });

  it("communicates deterministic generation availability without implementation jargon", () => {
    const html = render([]);
    expect(html).toContain("주제와 목표를 정하면 아이에게 맞는 활동 자료를 준비합니다.");
    expect(html).not.toContain("Core 템플릿");
    expect(html).not.toContain("AI &amp; template controls");
    expect(html).not.toContain("Parent Review");
    expect(html).not.toContain("MATERIALS");
  });
});
