import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const invoke = vi.hoisted(() => vi.fn());
vi.mock("@tauri-apps/api/core", () => ({ invoke, isTauri: () => true }));
import { ExternalSourceLink, externalHttpUrl, openNativeSource } from "./ExternalSourceLink";

describe("external source opening", () => {
  beforeEach(() => { invoke.mockReset(); });

  it("passes a canonical HTTP source to the native default-browser command", async () => {
    invoke.mockResolvedValue(undefined);
    await openNativeSource("https://example.org/씨앗?q=source#details");
    expect(invoke).toHaveBeenCalledWith("open_external_url", {
      url: "https://example.org/%EC%94%A8%EC%95%97?q=source#details",
    });
  });

  it("blocks credentials, unsafe schemes and control characters before native invocation", async () => {
    for (const href of ["file:///private/secret", "javascript:bad()", "mailto:a@example.org",
      "https://name:secret@example.org", "https://example.org/\nsource", " https://example.org/", "https://example.org/\u0085source"]) {
      expect(externalHttpUrl(href)).toBeNull();
      await expect(openNativeSource(href)).rejects.toThrow("HTTP(S)");
      expect(renderToStaticMarkup(<ExternalSourceLink href={href}>원 출처 열기</ExternalSourceLink>)).toBe("");
    }
    expect(invoke).not.toHaveBeenCalled();
  });

  it("retains a real accessible browser link and propagates native failure to its UI handler", async () => {
    const html = renderToStaticMarkup(<ExternalSourceLink href="https://example.org/source">원 출처 열기</ExternalSourceLink>);
    expect(html).toContain('href="https://example.org/source"');
    expect(html).toContain('target="_blank"');
    expect(html).toContain('rel="noopener noreferrer"');
    invoke.mockRejectedValue(new Error("No default browser"));
    await expect(openNativeSource("https://example.org/source")).rejects.toThrow("No default browser");
  });
});
