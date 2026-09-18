import { describe, expect, it } from "vitest";

import type { PhotoActivityRecord, PhotoRecordStatus } from "../api";
import { filterPhotoRecords } from "./PhotoActivityWorkspace";

function record(id: string, status: PhotoRecordStatus): PhotoActivityRecord {
  return {
    id,
    child_id: "child-1",
    photo_asset_ids: [],
    user_context: null,
    generated_observation: "",
    generation_mode: "manual_photo_diary",
    status,
    job_id: null,
    error_message: null,
    suggested_tags: [],
    suggested_experience_axes: [],
    suggested_interest: null,
    suggested_difficulty_note: null,
    suggested_next_activity: null,
    learning_log_id: null,
  };
}

describe("filterPhotoRecords", () => {
  const records = [
    record("queued", "queued"),
    record("processing", "processing"),
    record("draft", "draft"),
    record("committed", "committed"),
    record("failed", "failed"),
    record("discarded", "discarded"),
  ];

  it("keeps discarded records out of the default archive", () => {
    expect(filterPhotoRecords(records, "all").map((item) => item.id)).toEqual([
      "queued",
      "processing",
      "draft",
      "committed",
      "failed",
    ]);
  });

  it("separates completed records from records that need attention", () => {
    expect(filterPhotoRecords(records, "committed").map((item) => item.id)).toEqual([
      "committed",
    ]);
    expect(filterPhotoRecords(records, "attention").map((item) => item.id)).toEqual([
      "queued",
      "processing",
      "draft",
      "failed",
    ]);
  });
});
