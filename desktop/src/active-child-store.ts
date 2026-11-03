import type { ChildProfile } from "./api";

export const LAST_CHILD_KEY = "growwise:last-child-id";

export function readRememberedChildId(storage: Pick<Storage, "getItem">): string | null {
  try { return storage.getItem(LAST_CHILD_KEY); } catch { return null; }
}

export function writeRememberedChildId(
  storage: Pick<Storage, "setItem" | "removeItem">, childId: string,
): void {
  try {
    if (childId) storage.setItem(LAST_CHILD_KEY, childId);
    else storage.removeItem(LAST_CHILD_KEY);
  } catch { /* Restricted storage must not prevent in-memory child selection. */ }
}

export function resolveActiveChildId(
  children: ChildProfile[], preferredId: string | null | undefined, rememberedId: string | null,
): string {
  for (const candidate of [preferredId, rememberedId]) {
    if (candidate && children.some((child) => child.id === candidate)) return candidate;
  }
  return children[0]?.id ?? "";
}

type ChildState = {
  children: ChildProfile[];
  activeChildId: string;
  loading: boolean;
  error: string | null;
};

type ChildStorage = Pick<Storage, "getItem" | "setItem" | "removeItem">;

export class ActiveChildStore {
  private state: ChildState = { children: [], activeChildId: "", loading: true, error: null };
  private generation = 0;
  private listeners = new Set<() => void>();

  constructor(
    private loadChildren: () => Promise<ChildProfile[]>,
    private storage: ChildStorage,
  ) {}

  snapshot = (): ChildState => this.state;
  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => { this.listeners.delete(listener); };
  };
  private publish(next: ChildState) {
    this.state = next;
    for (const listener of this.listeners) listener();
  }
  private activeChild() {
    return this.state.children.find((child) => child.id === this.state.activeChildId) ?? null;
  }
  cancelPending = () => { this.generation += 1; };

  selectChild = (childId: string) => {
    if (childId && !this.state.children.some((child) => child.id === childId)) return;
    this.generation += 1;
    this.publish({ ...this.state, activeChildId: childId, loading: false, error: null });
    writeRememberedChildId(this.storage, childId);
  };

  syncRememberedChild = () => {
    const childId = resolveActiveChildId(
      this.state.children, this.state.activeChildId, readRememberedChildId(this.storage),
    );
    if (childId !== this.state.activeChildId) this.selectChild(childId);
  };

  refreshChildren = async (preferredId?: string | null): Promise<ChildProfile | null> => {
    const request = ++this.generation;
    this.publish({ ...this.state, loading: true, error: null });
    try {
      const children = await this.loadChildren();
      if (request !== this.generation) return this.activeChild();
      const childId = resolveActiveChildId(
        children, preferredId ?? this.state.activeChildId, readRememberedChildId(this.storage),
      );
      this.publish({ children, activeChildId: childId, loading: false, error: null });
      writeRememberedChildId(this.storage, childId);
      return this.activeChild();
    } catch (cause) {
      if (request !== this.generation) return this.activeChild();
      this.publish({ ...this.state, loading: false, error: cause instanceof Error
        ? cause.message : "아이 목록을 불러오지 못했습니다." });
      throw cause;
    }
  };

  upsertChild = (child: ChildProfile, options: { select?: boolean } = {}) => {
    this.generation += 1;
    this.publish({
      ...this.state,
      children: [child, ...this.state.children.filter((item) => item.id !== child.id)],
      activeChildId: options.select ? child.id : this.state.activeChildId,
      loading: false,
    });
    if (options.select) writeRememberedChildId(this.storage, child.id);
  };
}
