import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { ApiCredentialStatus } from "../credential-api";
import { CredentialEditor } from "./ApiKeySettings";

const saved: ApiCredentialStatus = {
  service_id: "data4library", configured: true, source: "saved", supported: true,
};

function render(credential: ApiCredentialStatus, value = "") {
  return renderToStaticMarkup(<CredentialEditor credential={credential} value={value}
    busy={false} connected onChange={() => {}} onSave={() => {}} onDelete={() => {}} onTest={() => {}} />);
}

describe("personal API credential controls", () => {
  it("uses an empty password field and status labels instead of saved-key readback", () => {
    const html = render(saved);
    expect(html).toContain('type="password"');
    expect(html).toContain('autoComplete="off"');
    expect(html).toContain('spellCheck="false"');
    expect(html).toContain('value=""');
    expect(html).toContain("OS 보안 저장소에 저장됨");
    expect(html).toContain("실제 연결 확인");
    expect(html).toContain("키 사용 해제");
    expect(html).not.toContain("synthetic-test-key");
  });

  it("shows inherited and disabled states without claiming OS storage on unsupported systems", () => {
    expect(render({ ...saved, source: "environment" })).toContain("환경변수에서 제공됨");
    expect(render({ ...saved, source: "disabled", configured: false })).toContain("사용 해제됨");
    const html = render({ ...saved, supported: false, source: "none", configured: false });
    expect(html).toContain("보안 키 저장을 지원하지 않습니다");
    expect(html).toMatch(/<input[^>]*disabled/);
    expect(html).toMatch(/<button[^>]*disabled[^>]*>키 저장/);
  });
});
