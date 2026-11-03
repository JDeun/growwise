import { beforeEach, expect, it, vi } from "vitest";

const invoke = vi.hoisted(() => vi.fn());
vi.mock("@tauri-apps/api/core", () => ({ invoke }));
import { getConversationEvidence } from "./evidence-api";

beforeEach(() => invoke.mockReset());
it("resolves a cited source only through the child-scoped native command", async () => {
  invoke.mockResolvedValue({ title: "합성 원본" });
  await getConversationEvidence("child-a", "chunk:resource-a:0");
  expect(invoke).toHaveBeenCalledWith("get_conversation_evidence", {
    childId: "child-a", sourceId: "chunk:resource-a:0",
  });
});
