import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { MaterialCurriculumTargets } from "./MaterialCurriculumTargets";

describe("MaterialCurriculumTargets", () => {
  it("renders nothing for legacy materials without targets", () => {
    expect(renderToStaticMarkup(<MaterialCurriculumTargets />)).toBe("");
  });

  it("shows framework, domain, source and mapping level", () => {
    const html = renderToStaticMarkup(
      <MaterialCurriculumTargets
        targets={[
          {
            mapping_id: "gw:kr:2022:elementary:science-inquiry",
            framework: "2022 개정 초·중등학교 교육과정",
            domain: "과학",
            description: "질문을 만들고 관찰한 뒤 증거를 바탕으로 설명하는 학습과 연결합니다.",
            source_ref: "교육부고시 제2022-33호",
            standard_codes: [],
          },
        ]}
      />,
    );

    expect(html).toContain("교육과정 연결 1개");
    expect(html).toContain("2022 개정 초·중등학교 교육과정");
    expect(html).toContain("과학");
    expect(html).toContain("교육부고시 제2022-33호");
    expect(html).toContain("영역/교과 수준 매핑");
  });
});
