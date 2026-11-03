import { invoke } from "@tauri-apps/api/core";
import { describe, expect, it, vi } from "vitest";

import { deleteConversation, deleteEntityLink, retryPhotoRecord } from "./record-actions-api";

vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn().mockResolvedValue({ deleted: true }) }));

describe("existing record lifecycle actions", () => {
  it("forwards the owning child when revoking a shared link", async () => {
    await deleteEntityLink("link-a", "owner-a");
    expect(invoke).toHaveBeenLastCalledWith("delete_entity_link", {
      linkId: "link-a", actingChildId: "owner-a",
    });
  });

  it("targets the selected conversation and saved failed photo record", async () => {
    await deleteConversation("session-a");
    expect(invoke).toHaveBeenLastCalledWith("delete_conversation", { sessionId: "session-a" });
    await retryPhotoRecord("photo-a");
    expect(invoke).toHaveBeenLastCalledWith("retry_photo_record", { recordId: "photo-a" });
  });
});
