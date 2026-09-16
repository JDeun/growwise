export type ChildContextKey =
  | "growth"
  | "observations"
  | "library"
  | "materials"
  | "activities";

export type ViewLoadState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "ready" }
  | { kind: "error"; message: string };

export type ChildContextLoadState = Record<ChildContextKey, ViewLoadState>;

export const CHILD_CONTEXT_KEYS: readonly ChildContextKey[] = [
  "growth",
  "observations",
  "library",
  "materials",
  "activities",
] as const;

export function childContextState(kind: "idle" | "loading" | "ready"): ChildContextLoadState {
  return Object.fromEntries(CHILD_CONTEXT_KEYS.map((key) => [key, { kind }])) as ChildContextLoadState;
}

export function isCurrentChildScope(
  childId: string,
  requestId: number,
  currentChildId: string | null,
  currentRequestId: number,
): boolean {
  return childId === currentChildId && requestId === currentRequestId;
}

export function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error && error.message.trim() ? error.message : fallback;
}
