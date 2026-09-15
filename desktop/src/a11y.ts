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
