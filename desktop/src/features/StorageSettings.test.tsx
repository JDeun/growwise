import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { StorageSettings } from "./StorageSettings";

afterEach(() => vi.unstubAllGlobals());

describe("StorageSettings relocation warning", () => {
  it("shows a committed-but-not-durable warning after the required page reload", () => {
    vi.stubGlobal("window", {
      localStorage: {
        getItem: (key: string) => key === "growwise:relocation-warning"
          ? "새 저장소로 연결했지만 디스크 동기화 실패 <details>"
          : null,
      },
    });
    const html = renderToStaticMarkup(<StorageSettings connected />);
    expect(html).toContain('role="alert"');
    expect(html).toContain("새 저장소로 연결했지만 디스크 동기화 실패 &lt;details&gt;");
    expect(html).not.toContain("<details>");
  });

  it("keeps settings available when localStorage access is blocked", () => {
    vi.stubGlobal("window", {
      get localStorage() { throw new Error("storage blocked"); },
    });
    const html = renderToStaticMarkup(<StorageSettings connected={false} />);
    expect(html).toContain("저장 폴더 변경");
    expect(html).not.toContain("storage blocked");
  });
});
