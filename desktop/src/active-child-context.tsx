import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { listChildren, type ChildProfile } from "./api";

export const LAST_CHILD_KEY = "growwise:last-child-id";

export function resolveActiveChildId(
  children: ChildProfile[],
  preferredId: string | null | undefined,
  rememberedId: string | null,
): string {
  const candidates = [preferredId, rememberedId].filter(
    (value): value is string => Boolean(value),
  );
  for (const candidate of candidates) {
    if (children.some((child) => child.id === candidate)) return candidate;
  }
  return children[0]?.id ?? "";
}

interface ActiveChildContextValue {
  children: ChildProfile[];
  activeChildId: string;
  activeChild: ChildProfile | null;
  loading: boolean;
  error: string | null;
  selectChild: (childId: string) => void;
  syncRememberedChild: () => void;
  refreshChildren: (preferredId?: string | null) => Promise<ChildProfile | null>;
  upsertChild: (child: ChildProfile, options?: { select?: boolean }) => void;
}

const ActiveChildContext = createContext<ActiveChildContextValue | null>(null);

export function ActiveChildProvider({ children: content }: { children: ReactNode }) {
  const [children, setChildren] = useState<ChildProfile[]>([]);
  const [activeChildId, setActiveChildId] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const selectChild = useCallback((childId: string) => {
    setActiveChildId(childId);
    if (childId) {
      window.localStorage.setItem(LAST_CHILD_KEY, childId);
    } else {
      window.localStorage.removeItem(LAST_CHILD_KEY);
    }
  }, []);

  const syncRememberedChild = useCallback(() => {
    const rememberedId = window.localStorage.getItem(LAST_CHILD_KEY);
    const selectedId = resolveActiveChildId(children, rememberedId, activeChildId);
    if (selectedId !== activeChildId) setActiveChildId(selectedId);
    if (!selectedId && rememberedId) window.localStorage.removeItem(LAST_CHILD_KEY);
  }, [activeChildId, children]);

  const refreshChildren = useCallback(async (preferredId?: string | null) => {
    setLoading(true);
    setError(null);
    try {
      const loaded = await listChildren();
      const rememberedId = window.localStorage.getItem(LAST_CHILD_KEY);
      const selectedId = resolveActiveChildId(loaded, preferredId, rememberedId);
      setChildren(loaded);
      setActiveChildId(selectedId);
      if (selectedId) {
        window.localStorage.setItem(LAST_CHILD_KEY, selectedId);
      } else {
        window.localStorage.removeItem(LAST_CHILD_KEY);
      }
      return loaded.find((child) => child.id === selectedId) ?? null;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "아이 목록을 불러오지 못했습니다.");
      throw cause;
    } finally {
      setLoading(false);
    }
  }, []);

  const upsertChild = useCallback(
    (child: ChildProfile, options: { select?: boolean } = {}) => {
      setChildren((current) => [child, ...current.filter((item) => item.id !== child.id)]);
      if (options.select) selectChild(child.id);
    },
    [selectChild],
  );

  useEffect(() => {
    void refreshChildren().catch(() => undefined);
  }, [refreshChildren]);

  const activeChild = useMemo(
    () => children.find((child) => child.id === activeChildId) ?? null,
    [activeChildId, children],
  );

  const value = useMemo<ActiveChildContextValue>(
    () => ({
      children,
      activeChildId,
      activeChild,
      loading,
      error,
      selectChild,
      syncRememberedChild,
      refreshChildren,
      upsertChild,
    }),
    [
      activeChild,
      activeChildId,
      children,
      error,
      loading,
      refreshChildren,
      selectChild,
      syncRememberedChild,
      upsertChild,
    ],
  );

  return <ActiveChildContext.Provider value={value}>{content}</ActiveChildContext.Provider>;
}

export function useActiveChild(): ActiveChildContextValue {
  const value = useContext(ActiveChildContext);
  if (!value) throw new Error("useActiveChild must be used inside ActiveChildProvider");
  return value;
}
