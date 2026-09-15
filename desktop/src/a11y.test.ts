import { describe, expect, it } from "vitest";
import {
  focusTrapIndex,
  isActivationKey,
  isDismissKey,
  isRovingKey,
  nextWorkspaceIndex,
  statusAnnouncement,
} from "./a11y";

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

  it("recognizes the dismiss key for modal dialogs", () => {
    expect(isDismissKey("Escape")).toBe(true);
    expect(isDismissKey("Enter")).toBe(false);
    expect(isDismissKey(" ")).toBe(false);
  });

  it("recognizes roving-navigation keys and ignores others", () => {
    for (const key of ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End"]) {
      expect(isRovingKey(key)).toBe(true);
    }
    expect(isRovingKey("Tab")).toBe(false);
    expect(isRovingKey("Enter")).toBe(false);
  });

  it("wraps a focus trap forward and backward on Tab only", () => {
    expect(focusTrapIndex(0, 2, "Tab", false)).toBe(1);
    expect(focusTrapIndex(1, 2, "Tab", false)).toBe(0);
    expect(focusTrapIndex(0, 2, "Tab", true)).toBe(1);
    expect(focusTrapIndex(1, 2, "Tab", true)).toBe(0);
    expect(focusTrapIndex(0, 2, "Enter", false)).toBe(0);
    expect(focusTrapIndex(3, 0, "Tab", false)).toBe(0);
  });
});
