import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { GrowthContextPanel } from "./GrowthContextPanel";
import type { GrowthMap } from "../api";

const growthMap: GrowthMap = {
  child_id: "child-1",
  period_days: 30,
  stage: "preschool_3_5",
  total_logs_in_period: 5,
  tagged_logs_in_period: 4,
  axes: [
    { axis: "reading", state: "observed", observation_count: 3 },
    { axis: "speaking", state: "observed", observation_count: 1 },
    { axis: "physical", state: "unobserved", observation_count: 0 },
  ],
  layers: [
    {
      key: "whole_person",
      label: "생활 전반",
      axes: [{ axis: "physical", state: "unobserved", observation_count: 0 }],
    },
    {
      key: "learning",
      label: "학습 경험",
      axes: [
        { axis: "reading", state: "observed", observation_count: 3 },
        { axis: "speaking", state: "observed", observation_count: 1 },
      ],
    },
    {
      key: "stage_focus",
      label: "단계 초점",
      axes: [{ axis: "reading", state: "observed", observation_count: 3 }],
    },
  ],
  diversity: {
    state: "concentrated",
    observed_axis_count: 2,
    focus_axes: ["reading"],
    note: "최근 기록이 읽기 경험에 상대적으로 많이 모였습니다.",
  },
};

describe("GrowthContextPanel", () => {
  it("presents record distribution without framing counts as ability scores", () => {
    const html = renderToStaticMarkup(
      <GrowthContextPanel growthState={{ kind: "ready" }} growthMap={growthMap} onRetry={vi.fn()} />,
    );

    expect(html).toContain("최근 30일의 기록 분포");
    expect(html).toContain("경험 축 커버리지");
    expect(html).toContain("세 가지 관찰 렌즈");
    expect(html).toContain("관찰 3건");
    expect(html).toContain("관찰 횟수는 아이의 능력");
    expect(html).toContain("기록이 없는 축은 결핍이나 지연을 의미하지 않습니다.");
  });
});
