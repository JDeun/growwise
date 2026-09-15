import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ConfirmDialog } from "./ConfirmDialog";

const noop = () => undefined;

const base = {
  title: "이 백업을 복원할까요?",
  description: "현재 기록을 이 백업으로 교체합니다.",
  confirmLabel: "복원",
  onConfirm: noop,
  onCancel: noop,
};

describe("ConfirmDialog accessibility", () => {
  it("renders nothing while closed", () => {
    expect(renderToStaticMarkup(<ConfirmDialog open={false} {...base} />)).toBe("");
  });

  it("exposes a labelled, described modal alertdialog", () => {
    const html = renderToStaticMarkup(<ConfirmDialog open {...base} />);
    expect(html).toContain('role="alertdialog"');
    expect(html).toContain('aria-modal="true"');
    expect(html).toContain('aria-labelledby="confirm-dialog-title"');
    expect(html).toContain('aria-describedby="confirm-dialog-description"');
    expect(html).toContain('id="confirm-dialog-title"');
    expect(html).toContain('id="confirm-dialog-description"');
  });

  it("offers both a keyboard-reachable dismiss and confirm control", () => {
    const html = renderToStaticMarkup(<ConfirmDialog open {...base} />);
    // A native cancel button gives a focusable Escape/Tab target inside the trap.
    expect(html).toContain(">취소</button>");
    expect(html).toContain(">복원</button>");
    expect(html).not.toContain('role="button"');
  });

  it("uses the danger styling for destructive confirmations", () => {
    const html = renderToStaticMarkup(<ConfirmDialog open destructive {...base} />);
    expect(html).toContain("danger-button");
  });
});
