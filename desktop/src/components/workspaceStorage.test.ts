import { describe, expect, it, vi } from "vitest";

import {
  LAST_WORKSPACE_KEY,
  LEGACY_LAST_WORKSPACE_KEY,
  readWorkspaceView,
  writeWorkspaceView,
} from "./workspaceStorage";

describe("workspaceStorage", () => {
  it("falls back to home for invalid or unavailable storage", () => {
    expect(readWorkspaceView({ getItem: () => "invalid" })).toBe("home");
    expect(readWorkspaceView({ getItem: () => { throw new Error("blocked"); } })).toBe("home");
  });

  it("restores and persists a current product view", () => {
    expect(readWorkspaceView({
      getItem: (key) => key === LAST_WORKSPACE_KEY ? "materials" : null,
    })).toBe("materials");

    const setItem = vi.fn();
    writeWorkspaceView({ setItem }, "conversation");
    expect(setItem).toHaveBeenCalledWith(LAST_WORKSPACE_KEY, "conversation");
  });

  it("does not restore a hidden legacy route from the current storage key", () => {
    expect(readWorkspaceView({
      getItem: (key) => key === LAST_WORKSPACE_KEY ? "observations" : null,
    })).toBe("home");
  });

  it("migrates the previous sidebar IA without exposing legacy routes", () => {
    const legacy = (value: string) => readWorkspaceView({
      getItem: (key) => key === LEGACY_LAST_WORKSPACE_KEY ? value : null,
    });

    expect(legacy("search")).toBe("conversation");
    expect(legacy("settings")).toBe("backup");
    expect(legacy("growth")).toBe("profile");
    expect(legacy("observations")).toBe("learning");
    expect(legacy("discovery")).toBe("materials");
    expect(legacy("library")).toBe("materials");
  });

  it("does not break navigation when persistence is blocked", () => {
    expect(() => writeWorkspaceView({ setItem: () => { throw new Error("blocked"); } }, "settings")).not.toThrow();
  });
});
