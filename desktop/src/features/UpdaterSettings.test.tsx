import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

const invoke = vi.hoisted(() => vi.fn());
vi.mock("@tauri-apps/api/core", () => ({ invoke }));
import { appUpdateStatus, checkAppUpdate, installAppUpdate } from "../updater-api";
import { UpdateSummary } from "./UpdaterSettings";

describe("explicit signed app updates", () => {
  it("distinguishes unconfigured, unchecked, no-update and available states", () => {
    const state = { configured: false, current_version: "0.1.0-alpha.0", checked: false,
      available_version: null, notes: null };
    expect(renderToStaticMarkup(<UpdateSummary status={state} />)).toContain("설정되지 않았습니다");
    expect(renderToStaticMarkup(<UpdateSummary status={{ ...state, configured: true }} />)).toContain("아이 기록은 보내지 않습니다");
    expect(renderToStaticMarkup(<UpdateSummary status={{ ...state, configured: true, checked: true }} />)).toContain("최신입니다");
    const html = renderToStaticMarkup(<UpdateSummary status={{ ...state, configured: true,
      available_version: "1.0.0", notes: "<script>synthetic()</script>" }} />);
    expect(html).toContain("새 버전 1.0.0");
    expect(html).not.toContain("<script>");
    expect(html).toContain("&lt;script&gt;");
  });

  it("uses native commands and confirms the checked version without supplying URLs or keys", async () => {
    invoke.mockResolvedValue({});
    await appUpdateStatus(); await checkAppUpdate(); await installAppUpdate("1.0.0");
    expect(invoke.mock.calls).toEqual([
      ["app_update_status"], ["check_app_update"],
      ["install_app_update", { version: "1.0.0", confirmed: true }],
    ]);
  });
});
