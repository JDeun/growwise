import { describe, expect, it } from "vitest";

import type { MaterialStatus } from "./api";
import { materialLane } from "./material-workflow";

const ALL_STATUSES: MaterialStatus[] = ["draft", "review_pending", "revision_requested", "approved", "rejected", "archived"];

describe("material workflow exhaustiveness", () => {
  it("classifies every IPC material status into exactly one product lane", () => {
    const classified = ALL_STATUSES.map((status) => [status, materialLane(status)] as const);
    expect(classified).toHaveLength(ALL_STATUSES.length);
    expect(classified.filter(([, lane]) => lane === "approved").map(([status]) => status)).toEqual(["approved"]);
  });
});
