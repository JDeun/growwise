import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import type { LearningLog } from "../api";
import { EMPTY_LEARNING_EVIDENCE, LearningEvidenceDetails, LearningEvidenceFields } from "./LearningEvidence";

const record: LearningLog = { id: "log-a", child_id: "child-a", activity_plan_id: null,
  parent_observation: "함께 읽었다", tags: [], experience_axes: [], interest: null,
  next_activity: null, created_at: null };

describe("optional learning evidence controls and readable saved state", () => {
  it("keeps the three check states distinct and bounds text input", () => {
    const html = renderToStaticMarkup(<LearningEvidenceFields value={EMPTY_LEARNING_EVIDENCE}
      onChange={vi.fn()} books={[]} bookLoading={false} bookError={null} disabled={false} />);
    expect(html).toContain('value="unknown" selected=""');
    expect(html).toContain('value="true"');
    expect(html).toContain('value="false"');
    expect(html).toContain('maxLength="4000"');
    expect(html).toContain('maxLength="10000"');
    expect(html).toContain("참고 자료에 책을 저장하면 연결할 수 있습니다");
  });

  it("makes a book-list failure recoverable without disabling other optional fields", () => {
    const html = renderToStaticMarkup(<LearningEvidenceFields value={EMPTY_LEARNING_EVIDENCE}
      onChange={vi.fn()} books={[]} bookLoading={false} bookError="책 목록 불러오기 실패"
      disabled={false} />);
    expect(html).toContain("책 목록 불러오기 실패");
    expect(html).not.toContain('disabled=""');
  });

  it.each([true, false, null])("renders saved evidence_checked=%s without collapsing unknown", (checked) => {
    const html = renderToStaticMarkup(<LearningEvidenceDetails record={{ ...record,
      ai_hint: "<script>인용한 힌트</script>", evidence_checked: checked,
      child_reexplanation: "아이의 자기 설명", book_id: "unavailable-book",
    }} books={[]} />);
    expect(html).toContain(checked === null ? "기록하지 않음" : checked ? "확인함" : "확인하지 않음");
    expect(html).toContain("아이의 자기 설명");
    expect(html).toContain("연결한 책 · 현재 목록에 없음");
    expect(html).toContain("&lt;script&gt;");
    expect(html).not.toContain("<script>");
    expect(html).not.toContain("unavailable-book");
  });

  it("does not add empty verification claims to legacy records", () => {
    expect(renderToStaticMarkup(<LearningEvidenceDetails record={record} books={[]} />)).toBe("");
  });
});
