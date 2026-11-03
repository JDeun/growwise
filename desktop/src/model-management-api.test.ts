import { invoke } from "@tauri-apps/api/core";
import { describe, expect, it, vi } from "vitest";

import { listLocalModels, removeLocalModel, setLocalModel } from "./model-management-api";

vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn().mockResolvedValue([]) }));

describe("local model management IPC", () => {
  it("sends role and exact model with confirmation but no UI supplied endpoint", async () => {
    await listLocalModels("embedding");
    expect(invoke).toHaveBeenLastCalledWith("list_local_models", { component: "embedding" });
    await removeLocalModel("text", "temporary-test:latest");
    expect(invoke).toHaveBeenLastCalledWith("remove_local_model", {
      component: "text", model: "temporary-test:latest", confirmed: true,
    });
    await setLocalModel("vision", "multimodal:latest");
    expect(invoke).toHaveBeenLastCalledWith("set_local_model", {
      component: "vision", model: "multimodal:latest",
    });
  });
});
