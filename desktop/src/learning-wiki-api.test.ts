import { invoke } from "@tauri-apps/api/core";
import { describe, expect, it, vi } from "vitest";

import { getLearningWiki, rebuildLearningWiki } from "./learning-wiki-api";

vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn().mockResolvedValue({}) }));

describe("Learning Wiki desktop bridge", () => {
  it("scopes reads and explicit rebuilds to the chosen child", async () => {
    await getLearningWiki("child-a");
    expect(invoke).toHaveBeenLastCalledWith("get_learning_wiki", { childId: "child-a" });
    await rebuildLearningWiki("child-b");
    expect(invoke).toHaveBeenLastCalledWith("rebuild_learning_wiki", { childId: "child-b" });
  });
});
