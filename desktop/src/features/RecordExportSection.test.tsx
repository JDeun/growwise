import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const invoke = vi.hoisted(() => vi.fn());
vi.mock("@tauri-apps/api/core", () => ({ invoke }));
import { exportChildRecords, type ChildProfile } from "../api";
import { recordExportPeriod, RecordExportSection } from "./RecordExportSection";

describe("selected record export", () => {
  beforeEach(() => { invoke.mockReset(); });

  it("defaults to the current child and clearly distinguishes a raw ZIP from restore backups", () => {
    const children: ChildProfile[] = [
      { id: "child-a", nickname: "첫째", stage: "elementary", age_months: 96, interests: [] },
      { id: "child-b", nickname: "둘째", stage: "preschool_3_5", age_months: 50, interests: [] },
    ];
    const html = renderToStaticMarkup(<RecordExportSection children={children} currentChildId="child-b"
      connected busy={false} onBusyChange={() => undefined} />);
    expect(html).toContain('<option value="child-b" selected="">둘째</option>');
    expect(html).toContain("시작일(선택)");
    expect(html).toContain("종료일(선택)");
    expect(html).toContain("전체 앱 복원용 백업이 아닙니다");
    expect(html).toContain("개인 기록과 사진이 원문 그대로 포함될 수 있습니다");
  });

  it("sends only the chosen child and optional date boundaries to the native export command", async () => {
    invoke.mockResolvedValue(null);
    expect(await exportChildRecords("child-a")).toBeNull();
    expect(invoke).toHaveBeenLastCalledWith("export_child_records", {childId:"child-a",startDate:null,endDate:null});
    invoke.mockResolvedValue("/chosen/records.zip");
    expect(await exportChildRecords("child-b", "2026-01-01", "2026-11-03")).toBe("/chosen/records.zip");
    expect(invoke).toHaveBeenLastCalledWith("export_child_records", {childId:"child-b",startDate:"2026-01-01",endDate:"2026-11-03"});
  });

  it("accepts open-ended or inclusive same-day periods and rejects malformed/reversed dates", () => {
    expect(recordExportPeriod("", "")).toEqual({startDate:null,endDate:null});
    expect(recordExportPeriod("2026-11-03", "2026-11-03")).toEqual({startDate:"2026-11-03",endDate:"2026-11-03"});
    expect(recordExportPeriod("2026-01-01", "")).toEqual({startDate:"2026-01-01",endDate:null});
    expect(() => recordExportPeriod("2026-02-30", "")).toThrow("날짜");
    expect(() => recordExportPeriod("2026-11-04", "2026-11-03")).toThrow("종료일");
    expect(() => recordExportPeriod("1800-01-01", "2026-11-03")).toThrow("36,600일");
  });
});
