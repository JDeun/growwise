import { invoke } from "@tauri-apps/api/core";
import { describe, expect, it, vi } from "vitest";

import { deleteApiCredential, listApiCredentials, saveApiCredential, testApiCredential } from "./credential-api";

vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn().mockResolvedValue([]) }));

describe("personal API credential commands", () => {
  it("requests status without requesting any saved plaintext", async () => {
    await listApiCredentials();
    expect(invoke).toHaveBeenLastCalledWith("list_api_credentials");
  });

  it("scopes save/delete and real connection tests to an allowlisted service", async () => {
    await saveApiCredential("data4library", "synthetic-test-key");
    expect(invoke).toHaveBeenLastCalledWith("save_api_credential", {
      serviceId: "data4library", value: "synthetic-test-key",
    });
    await deleteApiCredential("data4library");
    expect(invoke).toHaveBeenLastCalledWith("delete_api_credential", { serviceId: "data4library" });
    await testApiCredential("data4library");
    expect(invoke).toHaveBeenLastCalledWith("test_api_credential", { serviceId: "data4library" });
  });
});
