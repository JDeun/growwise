import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { GeneratedMaterial } from "../api";
import { MaterialWorkspace } from "./MaterialWorkspace";

const noop = () => undefined;
const base: GeneratedMaterial = {
  id: "m1", child_id: "c1", kind: "reading_activity", title: "고양이 읽기",
  content_markdown: "# 기본 활동", status: "draft", source_refs: [],
  generator_mode: "template", review_note: null, request_topic: "고양이",
  request_goal: null, version: 1, parent_material_id: null, version_note: null,
};

function render(material: GeneratedMaterial, busy = false, otherMaterials: GeneratedMaterial[] = []) {
  return renderToStaticMarkup(<MaterialWorkspace
    materials={[material, ...otherMaterials]} resources={[]} materialKind="reading_activity" topic="" goal=""
    selectedResourceRefs={[]} busy={busy} error={null} revisionNotes={{}} editingMaterialId={null}
    onKindChange={noop} onTopicChange={noop} onGoalChange={noop} onToggleResource={noop}
    onGenerate={noop} onReview={noop} onRevisionNoteChange={noop} onRevise={noop}
    onEditStart={noop} onEdit={noop} onPrint={noop} onRetryAi={noop}
  />);
}

describe("focused material AI progress", () => {
  it.each(["queued", "running"] as const)("shows %s work and labels early use as a template decision", (ai_status) => {
    const html = render({ ...base, ai_status });
    const canvas = html.split('aria-label="선택한 학습 자료 미리보기"')[1].split("</section>")[0];
    expect(canvas).toContain('role="status"');
    expect(canvas).toContain("AI 학습 자료");
    expect(canvas).toContain("기본 템플릿으로 먼저 사용");
    expect(canvas).toContain("이 화면에 자동으로 반영");
    expect(canvas).toContain("진행 중인 AI 결과는 이 자료에 적용하지 않습니다");
  });

  it("never presents a rejected-quality fallback as AI-enhanced even with a legacy completed flag", () => {
    const html = render({ ...base, ai_status: "completed", generator_mode: "template_quality_fallback" });
    expect(html).toContain("AI 완성본이 아닙니다");
    expect(html).not.toContain("AI 보조 완료");
    expect(html).not.toContain("AI 보조 자료 준비됨");
  });

  it("distinguishes a successful AI document from an ordinary Core-only template", () => {
    expect(render({ ...base, ai_status: "completed", generator_mode: "llm_enhanced" }))
      .toContain("AI 보조 자료 준비됨");
    const core = render(base);
    expect(core).toContain("이 활동 사용하기");
    expect(core).not.toContain("material-ai-notice");
    expect(core).not.toContain("기본 템플릿으로 먼저 사용");
  });

  it("offers explicit retry only for a failed unapproved draft and prevents double submits", () => {
    expect(render({ ...base, ai_status: "failed" })).toContain("AI 보강 다시 시도");
    expect(render({ ...base, ai_status: "failed" }, true)).toContain("다시 시작 중…");
    expect(render({ ...base, ai_status: "failed" }, true))
      .toContain('class="quiet-button" disabled=""');
    expect(render({ ...base, ai_status: "failed", status: "approved" }))
      .not.toContain("AI 보강 다시 시도");
    expect(render({ ...base, ai_status: "running" })).not.toContain("AI 보강 다시 시도");
  });

  it("exposes every document in an accessible primary selector and escapes option titles", () => {
    const html = render(base, false, [{ ...base, id: "m2", title: "다른 자료 <script>bad()</script>", version: 2 }]);
    const canvas = html.split('aria-label="선택한 학습 자료 미리보기"')[1].split("</section>")[0];
    expect(canvas).toContain('aria-label="학습 자료 선택"');
    expect(canvas).toContain('<option value="m1" selected="">');
    expect(canvas).toContain('<option value="m2">');
    expect(canvas).toContain("다른 자료 &lt;script&gt;bad()&lt;/script&gt; · 2번째 버전");
    expect(canvas).not.toContain("<script>");
    expect(render(base)).not.toContain('aria-label="학습 자료 선택"');
  });
});
