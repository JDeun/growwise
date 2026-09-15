import { useEffect, useRef, type KeyboardEvent } from "react";

import { focusTrapIndex, isDismissKey } from "../a11y";

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  busy?: boolean;
  destructive?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel,
  busy = false,
  destructive = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const cancelRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (!open) return;
    cancelRef.current?.focus();
    const onKeyDown = (event: globalThis.KeyboardEvent) => {
      if (isDismissKey(event.key) && !busy) onCancel();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, busy, onCancel]);

  // Keep Tab / Shift+Tab inside the modal so keyboard focus cannot land on the
  // page behind the backdrop while the dialog is open.
  function handleFocusTrap(event: KeyboardEvent<HTMLElement>) {
    if (event.key !== "Tab") return;
    const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(
      'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    );
    if (!focusable || focusable.length === 0) return;
    const items = Array.from(focusable);
    const current = items.indexOf(document.activeElement as HTMLElement);
    const target = focusTrapIndex(current < 0 ? 0 : current, items.length, event.key, event.shiftKey);
    event.preventDefault();
    items[target]?.focus();
  }

  if (!open) return null;

  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={() => !busy && onCancel()}>
      <section
        ref={dialogRef}
        className="confirm-dialog"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        aria-describedby="confirm-dialog-description"
        onMouseDown={(event) => event.stopPropagation()}
        onKeyDown={handleFocusTrap}
      >
        <h2 id="confirm-dialog-title">{title}</h2>
        <p id="confirm-dialog-description">{description}</p>
        <div className="dialog-actions">
          <button ref={cancelRef} className="quiet-button" type="button" disabled={busy} onClick={onCancel}>
            취소
          </button>
          <button
            className={destructive ? "danger-button" : "primary-button"}
            type="button"
            disabled={busy}
            onClick={onConfirm}
          >
            {busy ? "처리 중…" : confirmLabel}
          </button>
        </div>
      </section>
    </div>
  );
}
