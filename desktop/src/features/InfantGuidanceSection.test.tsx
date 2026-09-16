import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { InfantGuidanceSection } from "./InfantGuidanceSection";

describe("InfantGuidanceSection", () => {
  it("distinguishes saved books, public candidates, and offline suggestions", () => {
    const html = renderToStaticMarkup(
      <InfantGuidanceSection
        observationHints={null}
        boardBooks={{
          recommendations: [
            {
              resource_id: "book-1",
              title: "저장한 책",
              reason: "로컬 자료",
              read_aloud_tip: "천천히 읽기",
              source: "local_library",
            },
            {
              resource_id: null,
              title: "공개 후보",
              reason: "검색 후보",
              read_aloud_tip: "상세 확인",
              source: "public_discovery",
            },
            {
              resource_id: null,
              title: "오프라인 제안",
              reason: "범주형 제안",
              read_aloud_tip: "반응 관찰",
              source: "local_library_or_offline_fallback",
            },
          ],
        }}
        loading={false}
        error={null}
        onLoad={() => undefined}
      />,
    );

    expect(html).toContain("내 자료실에 저장된 책");
    expect(html).toContain("공개 도서 후보 · 상세 적합성 확인 필요");
    expect(html).toContain("오프라인 범주형 제안");
    expect(html).toContain("아이 ID·관찰 원문·사진을 보내지 않습니다");
    expect(html).toContain("후보는 자동 저장하지 않습니다");
  });
});
