import { describe, expect, it } from "vitest";

import type { ActivityPlan, GeneratedMaterial, MaterialUseHistoryItem } from "./api";
import { ensureMaterialQuest } from "./material-quest";

function material(id: string): GeneratedMaterial {
  return {
    id,
    child_id: "child-a",
    kind: "science_inquiry",
    title: "얼음이 녹는 모습 관찰",
    content_markdown: "# 관찰",
    status: "approved",
    source_refs: [],
    generator_mode: "deterministic_template",
    review_note: null,
    request_topic: "얼음",
    request_goal: null,
    version: 1,
    parent_material_id: null,
    version_note: null,
  };
}

function activity(id: string): ActivityPlan {
  return {
    id,
    child_id: "child-a",
    title: "얼음이 녹는 모습 관찰",
    status: "suggested",
    source_refs: ["material:material-a"],
    parent_note: null,
    started_at: null,
    completed_at: null,
    skipped_at: null,
  };
}

describe("ensureMaterialQuest", () => {
  it("reuses an existing material quest without creating another activity", async () => {
    const existing: MaterialUseHistoryItem = {
      activity: activity("activity-existing"),
      learning_logs: [],
    };
    let createCalls = 0;

    const result = await ensureMaterialQuest(material("material-a"), {
      listResults: async () => [existing],
      create: async () => {
        createCalls += 1;
        return activity("unexpected");
      },
    });

    expect(result.created).toBe(false);
    expect(result.item.activity.id).toBe("activity-existing");
    expect(createCalls).toBe(0);
  });

  it("creates a suggested quest with the material provenance ref when none exists", async () => {
    let listCalls = 0;
    const created = activity("activity-created");
    const result = await ensureMaterialQuest(material("material-b"), {
      listResults: async () => {
        listCalls += 1;
        return listCalls === 1 ? [] : [{ activity: created, learning_logs: [] }];
      },
      create: async (childId, title, sourceRefs) => {
        expect(childId).toBe("child-a");
        expect(title).toBe("얼음이 녹는 모습 관찰");
        expect(sourceRefs).toEqual(["material:material-b"]);
        return created;
      },
    });

    expect(result.created).toBe(true);
    expect(result.item.activity.id).toBe("activity-created");
  });

  it("coalesces concurrent registration for the same material", async () => {
    let createCalls = 0;
    let listCalls = 0;
    const created = activity("activity-once");
    const api = {
      listResults: async () => {
        listCalls += 1;
        await Promise.resolve();
        return listCalls === 1 ? [] : [{ activity: created, learning_logs: [] }];
      },
      create: async () => {
        createCalls += 1;
        await Promise.resolve();
        return created;
      },
    };
    const target = material("material-concurrent");

    const [first, second] = await Promise.all([
      ensureMaterialQuest(target, api),
      ensureMaterialQuest(target, api),
    ]);

    expect(createCalls).toBe(1);
    expect(first.item.activity.id).toBe("activity-once");
    expect(second.item.activity.id).toBe("activity-once");
  });
});
