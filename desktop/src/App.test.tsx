import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import App from "./App";

describe("App feature composition", () => {
  it("renders the controller shell through extracted feature sections", () => {
    const html = renderToStaticMarkup(<App />);
    expect(html).toContain("GrowWise");
    expect(html).toContain("Personal Education OS");
    expect(html).toContain("GrowWise Core");
    expect(html).toContain("NEW CHILD");
    expect(html).toContain("아이 프로필을 만들어 주세요.");
    expect(html).toContain("DATA MANAGEMENT");
  });
});
