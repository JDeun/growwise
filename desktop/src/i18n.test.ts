import { describe, expect, it, vi } from "vitest";

import {
  DEFAULT_LOCALE,
  applyDocumentLocale,
  formatDate,
  formatNumber,
  loadLocale,
  persistLocale,
  resolveLocale,
} from "./i18n";

describe("localization foundation", () => {
  it("prefers an explicitly supported locale and normalizes language-only values", () => {
    expect(resolveLocale(["en-US", "ko-KR"])).toBe("en-US");
    expect(resolveLocale(["ko"])).toBe("ko-KR");
    expect(resolveLocale(["en"])).toBe("en-US");
  });

  it("ignores malformed and unsupported locale input without throwing", () => {
    expect(resolveLocale(["not_a_locale", "ja-JP", "ko-KR"])).toBe("ko-KR");
    expect(resolveLocale(["not_a_locale", "ja-JP"])).toBe(DEFAULT_LOCALE);
  });

  it("lets persisted preference override browser language", () => {
    const storage = { getItem: vi.fn(() => "en-US") };
    expect(loadLocale(storage, ["ko-KR"])).toBe("en-US");
  });

  it("survives storage denial in hardened webviews", () => {
    const storage = { getItem: vi.fn(() => { throw new Error("denied"); }) };
    expect(loadLocale(storage, ["en-US"])).toBe("en-US");
    const writeStorage = { setItem: vi.fn(() => { throw new Error("denied"); }) };
    expect(() => persistLocale(writeStorage, "ko-KR")).not.toThrow();
  });

  it("applies semantic document language without coupling startup to translations", () => {
    const root = document.createElement("html");
    applyDocumentLocale("en-US", root);
    expect(root.lang).toBe("en-US");
    expect(root.dir).toBe("ltr");
  });

  it("formats dates and numbers with locale-aware platform primitives", () => {
    expect(formatDate("invalid", "ko-KR")).toBe("");
    expect(formatNumber(1234, "en-US")).toContain("1,234");
    expect(formatDate(new Date(2026, 0, 2), "en-US")).toContain("2026");
  });
});
