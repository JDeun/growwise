import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";

import { listChildren, type ChildProfile } from "./api";

import { ActiveChildStore } from "./active-child-store";
export {
  LAST_CHILD_KEY, readRememberedChildId, writeRememberedChildId, resolveActiveChildId,
} from "./active-child-store";

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
  const [store] = useState(() => new ActiveChildStore(listChildren, {
    getItem: (key) => window.localStorage.getItem(key),
    setItem: (key, value) => window.localStorage.setItem(key, value),
    removeItem: (key) => window.localStorage.removeItem(key),
  }));
  const { children, activeChildId, loading, error } = useSyncExternalStore(
    store.subscribe, store.snapshot, store.snapshot,
  );
  const { selectChild, syncRememberedChild, refreshChildren, upsertChild } = store;

  useEffect(() => {
    void refreshChildren().catch(() => undefined);
    return store.cancelPending;
  }, [store, refreshChildren]);

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

export function useOptionalActiveChild(): ActiveChildContextValue | null {
  return useContext(ActiveChildContext);
}

export function useActiveChild(): ActiveChildContextValue {
  const value = useOptionalActiveChild();
  if (!value) throw new Error("useActiveChild must be used inside ActiveChildProvider");
  return value;
}
