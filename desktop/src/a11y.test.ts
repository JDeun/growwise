import { describe, expect, it } from "vitest";
import { isActivationKey, nextWorkspaceIndex, statusAnnouncement } from "./a11y";

describe("desktop accessibility helpers", () => {
  it("wraps arrow navigation and supports Home/End", () => {
    expect(nextWorkspaceIndex(0, "ArrowLeft", 4)).toBe(3);
    expect(nextWorkspaceIndex(3, "ArrowRight", 4)).toBe(0);
    expect(nextWorkspaceIndex(2, "Home", 4)).toBe(0);
    expect(nextWorkspaceIndex(1, "End", 4)).toBe(3);
  });

  it("only treats keyboard activation keys as activation", () => {
    expect(isActivationKey("Enter")).toBe(true);
    expect(isActivationKey(" ")).toBe(true);
    expect(isActivationKey("Escape")).toBe(false);
  });

  it("never announces null status as text", () => {
    expect(statusAnnouncement(null)).toBe("");
    expect(statusAnnouncement(" 저장 완료 ")).toBe("저장 완료");
  });
});
