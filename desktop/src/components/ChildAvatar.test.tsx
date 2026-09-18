import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import type { ChildProfile } from "../api";
import { ChildAvatar } from "./ChildAvatar";

const child: ChildProfile = {
  id: "child-1",
  nickname: "수아",
  stage: "preschool_3_5",
  age_months: 48,
  interests: [],
  avatar_asset_id: null,
};

describe("ChildAvatar", () => {
  it("renders a deterministic initials fallback without an asset", () => {
    const html = renderToStaticMarkup(<ChildAvatar child={child} size="lg" />);

    expect(html).toContain("수아");
    expect(html).toContain('aria-label="수아 프로필 사진"');
    expect(html).toContain("child-avatar--lg");
  });

  it("exposes edit controls only in editable mode", () => {
    const html = renderToStaticMarkup(
      <ChildAvatar child={child} editable onUpdated={vi.fn()} />,
    );

    expect(html).toContain("사진 추가");
    expect(html).toContain('type="file"');
    expect(html).toContain('accept="image/jpeg,image/png,image/webp"');
    expect(html).not.toContain(">삭제</button>");
  });

  it("shows replacement and deletion controls when an avatar is linked", () => {
    const html = renderToStaticMarkup(
      <ChildAvatar
        child={{ ...child, avatar_asset_id: "asset-1" }}
        editable
        onUpdated={vi.fn()}
      />,
    );

    expect(html).toContain("사진 변경");
    expect(html).toContain(">삭제</button>");
  });
});
