import { describe, expect, it } from "vitest";

import { parseLearningGoals, parseProfileList } from "./DataManagementSection";

describe("DataManagementSection profile helpers", () => {
  it("normalizes comma-separated profile context without duplicates", () => {
    expect(parseProfileList("공룡, 그림책, 공룡,  만들기 ")).toEqual([
      "공룡",
      "그림책",
      "만들기",
    ]);
  });

  it("normalizes line-separated learning goals without duplicates", () => {
    expect(parseLearningGoals("읽기\n\n자기 말로 설명하기\r\n읽기")).toEqual([
      "읽기",
      "자기 말로 설명하기",
    ]);
  });
});
