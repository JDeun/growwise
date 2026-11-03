import type { MaterialAction } from "./api";

let pending: { childId: string; action: MaterialAction } | null = null;

export function queueMaterialComposition(childId: string, action: MaterialAction) {
  pending = { childId, action };
}

export function takeMaterialComposition(childId: string): MaterialAction | null {
  const request = pending;
  pending = null;
  return request?.childId === childId ? request.action : null;
}
