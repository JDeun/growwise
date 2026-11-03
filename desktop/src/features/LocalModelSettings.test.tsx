import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { InstalledModelList } from "./LocalModelSettings";

describe("installed local model presentation", () => {
  it("distinguishes selected model and metadata from an integrity recheck", () => {
    const html = renderToStaticMarkup(<InstalledModelList
      models={[{ name: "local-test:latest", size: 1024 ** 3, digest: "test-digest" }]}
      currentModel="local-test" busy={false} onSelect={() => {}} onRemove={() => {}}
    />);
    expect(html).toContain("현재 선택");
    expect(html).toContain("1.0 GB");
    expect(html).toContain("test-digest");
    expect(html).toContain("다시 검사한 결과는 아닙니다");
    expect(html).toContain("local-test:latest 삭제");
  });

  it("shows empty state and renders untrusted model labels as text", () => {
    expect(renderToStaticMarkup(<InstalledModelList
      models={[]} currentModel={null} busy={false} onSelect={() => {}} onRemove={() => {}}
    />)).toContain("설치된 모델이 없습니다");
    const html = renderToStaticMarkup(<InstalledModelList
      models={[{ name: "<img src=x onerror=alert(1)>", size: 1, digest: "" }]}
      currentModel={null} busy onSelect={() => {}} onRemove={() => {}}
    />);
    expect(html).not.toContain("<img");
    expect(html).toContain("&lt;img");
    expect(html).toContain("disabled");
  });
});
