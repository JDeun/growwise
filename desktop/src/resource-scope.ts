import type { ResourceRecord } from "./api";

export function resourceScopeLabel(resource: ResourceRecord, activeChildId: string | null): string {
  if (resource.child_id === null) return "공용";
  if (activeChildId !== null && resource.child_id === activeChildId) return "현재 아이";
  return "다른 아이에서 공유됨";
}

export function canMutateResourceInChildView(
  resource: ResourceRecord,
  activeChildId: string | null,
): boolean {
  return resource.child_id === null || resource.child_id === activeChildId;
}
