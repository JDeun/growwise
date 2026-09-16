import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { materialCatalogItem } from "../material-catalog";
import { MaterialKindGuide } from "./MaterialKindGuide";

describe("MaterialKindGuide", () => {
  it("renders the selected material workflow and parent review points", () => {
    const item = materialCatalogItem("science_inquiry");
    const html = renderToStaticMarkup(<MaterialKindGuide item={item} />);

    expect(html).toContain('aria-label="과학 탐구 생성 가이드"');
    expect(html).toContain("권장 흐름");
    expect(html).toContain("예측");
    expect(html).toContain("관찰·실험");
    expect(html).toContain("부모 검토 포인트");
    expect(html).toContain("결론을 미리 정해 두지 않았는가");
  });
});
