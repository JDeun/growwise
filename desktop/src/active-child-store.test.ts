import { describe, expect, it } from "vitest";

import type { ChildProfile } from "./api";
import { ActiveChildStore, LAST_CHILD_KEY } from "./active-child-store";

const first: ChildProfile = { id: "a", nickname: "첫째", stage: "elementary", age_months: 96, interests: [] };
const second: ChildProfile = { id: "b", nickname: "둘째", stage: "preschool_3_5", age_months: 60, interests: [] };

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((done, fail) => { resolve = done; reject = fail; });
  return { promise, resolve, reject };
}

function storage(initial = "") {
  const data = new Map<string, string>(initial ? [[LAST_CHILD_KEY, initial]] : []);
  return {
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => { data.set(key, value); },
    removeItem: (key: string) => { data.delete(key); },
  };
}

describe("canonical active child selection", () => {
  it("keeps remembered selection across reordered restore lists and provider remounts", async () => {
    const saved = storage("a");
    const store = new ActiveChildStore(async () => [second, first], saved);
    await store.refreshChildren();
    expect(store.snapshot().activeChildId).toBe("a");
    store.selectChild("b");
    await store.refreshChildren();
    expect(store.snapshot().activeChildId).toBe("b");
    const reloaded = new ActiveChildStore(async () => [first, second], saved);
    await reloaded.refreshChildren();
    expect(reloaded.snapshot().activeChildId).toBe("b");
  });

  it("ignores an older list after a newer list has completed", async () => {
    const older = deferred<ChildProfile[]>();
    const newer = deferred<ChildProfile[]>();
    let calls = 0;
    const store = new ActiveChildStore(() => ++calls === 1 ? older.promise : newer.promise, storage("a"));
    const oldRequest = store.refreshChildren("b");
    const newRequest = store.refreshChildren("a");
    newer.resolve([first, second]);
    await newRequest;
    older.resolve([second]);
    await oldRequest;
    expect(store.snapshot().activeChildId).toBe("a");
    expect(store.snapshot().children).toEqual([first, second]);
  });

  it("does not let a delayed preferred child or old failure undo a user's selection", async () => {
    let response = Promise.resolve([first, second]);
    const saved = storage("a");
    const store = new ActiveChildStore(() => response, saved);
    await store.refreshChildren();
    const old = deferred<ChildProfile[]>();
    response = old.promise;
    const pending = store.refreshChildren("a");
    store.selectChild("b");
    old.resolve([first]);
    expect((await pending)?.id).toBe("b");
    expect(store.snapshot().children).toEqual([first, second]);
    expect(saved.getItem(LAST_CHILD_KEY)).toBe("b");
    const failure = deferred<ChildProfile[]>();
    response = failure.promise;
    const staleFailure = store.refreshChildren("a");
    store.selectChild("b");
    failure.reject(new Error("old request failed"));
    await staleFailure;
    expect(store.snapshot()).toMatchObject({ activeChildId: "b", loading: false, error: null });
  });

  it("keeps a newly saved profile when an older list finishes later", async () => {
    const old = deferred<ChildProfile[]>();
    const store = new ActiveChildStore(() => old.promise, storage());
    const pending = store.refreshChildren();
    store.upsertChild(second, { select: true });
    old.resolve([first]);
    await pending;
    expect(store.snapshot().children).toEqual([second]);
    expect(store.snapshot().activeChildId).toBe("b");
  });

  it("uses current in-memory selection when persistence is blocked or externally stale", async () => {
    const saved = storage("a");
    const store = new ActiveChildStore(async () => [first, second], saved);
    await store.refreshChildren();
    store.selectChild("b");
    saved.setItem(LAST_CHILD_KEY, "a");
    store.syncRememberedChild();
    await store.refreshChildren();
    expect(store.snapshot().activeChildId).toBe("b");
  });

  it("falls back only when the selected child really is absent from the current list", async () => {
    let children = [first, second];
    const store = new ActiveChildStore(async () => children, storage("b"));
    await store.refreshChildren();
    children = [first];
    await store.refreshChildren();
    expect(store.snapshot().activeChildId).toBe("a");
    children = [];
    await store.refreshChildren();
    expect(store.snapshot()).toMatchObject({ activeChildId: "", children: [], loading: false });
  });

  it("retains a deliberate selection across refreshes when local storage is unavailable", async () => {
    const blocked = () => { throw new Error("restricted storage"); };
    const store = new ActiveChildStore(async () => [first, second], {
      getItem: blocked, setItem: blocked, removeItem: blocked,
    });
    await store.refreshChildren();
    store.selectChild("b");
    store.syncRememberedChild();
    await store.refreshChildren();
    expect(store.snapshot().activeChildId).toBe("b");
  });
});
