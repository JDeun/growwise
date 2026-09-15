export function statusAnnouncement(message: string | null): string {
  return message?.trim() ?? "";
}

export function nextWorkspaceIndex(current: number, key: string, itemCount: number): number {
  if (itemCount <= 0) return 0;
  if (key === "Home") return 0;
  if (key === "End") return itemCount - 1;
  if (key === "ArrowRight" || key === "ArrowDown") return (current + 1) % itemCount;
  if (key === "ArrowLeft" || key === "ArrowUp") return (current - 1 + itemCount) % itemCount;
  return current;
}

export function isActivationKey(key: string): boolean {
  return key === "Enter" || key === " ";
}

export function isDismissKey(key: string): boolean {
  return key === "Escape";
}

const ROVING_KEYS = new Set([
  "ArrowLeft",
  "ArrowRight",
  "ArrowUp",
  "ArrowDown",
  "Home",
  "End",
]);

export function isRovingKey(key: string): boolean {
  return ROVING_KEYS.has(key);
}

// Wraps focus across the members of a focus trap (e.g. a modal dialog) so
// Tab / Shift+Tab keep the caret inside the dialog instead of escaping to the
// page behind it. Returns the same index when the key is not a Tab.
export function focusTrapIndex(
  current: number,
  count: number,
  key: string,
  shiftKey: boolean,
): number {
  if (count <= 0) return 0;
  if (key !== "Tab") return current;
  const delta = shiftKey ? -1 : 1;
  return (current + delta + count) % count;
}
