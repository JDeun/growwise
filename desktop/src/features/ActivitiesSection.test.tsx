import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { ActivitiesSection } from "./ActivitiesSection";

const plans = [
  {
    id: "activity-1",
    child_id: "child-1",
    title: "고양이 그림책 읽기",
    status: "active" as const,
    source_refs: [],
    parent_note: null,
    started_at: "2026-09-15T09:00:00+09:00",
    completed_at: null,
    skipped_at: null,
  },
  {
    id: "activity-2",
    child_id: "child-1",
    title: "블록 쌓기",
    status: "completed" as const,
    source_refs: [],
    parent_note: null,
    started_at: "2026-09-14T09:00:00+09:00",
    completed_at: "2026-09-14T09:30:00+09:00",
    skipped_at: null,
  },
];

describe("ActivitiesSection", () => {
  it("shows the full activity lifecycle and follow-up observation affordance", () => {
    const html = renderToStaticMarkup(
      <ActivitiesSection
        suggestions={null}
        suggestionsLoading={false}
        error={null}
        planBusy={false}
        plans={plans}
        loadState={{ kind: "ready" }}
        onLoadSuggestions={vi.fn()}
        onSaveActivity={vi.fn()}
        onTransition={vi.fn()}
        onRetryPlans={vi.fn()}
      />,
    );

    expect(html).toContain("1. 선택");
    expect(html).toContain("2. 진행");
    expect(html).toContain("3. 마침");
    expect(html).toContain("4. 관찰");
    expect(html).toContain("진행 중");
    expect(html).toContain("완료");
    expect(html).toContain("연결 관찰 확인");
    expect(html).toContain("후속 관찰은 관찰 작업공간에서 이 활동을 선택해 저장하면 자동으로 연결됩니다.");
  });
});
