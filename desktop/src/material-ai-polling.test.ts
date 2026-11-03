import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { GeneratedMaterial } from "./api";
import { materialAiCompletionNotice, startMaterialAiPolling } from "./material-ai-polling";

function material(
  ai_status: GeneratedMaterial["ai_status"],
  generator_mode = "template",
  child_id = "child-a",
): GeneratedMaterial {
  return {
    id: "material-1", child_id, ai_status, generator_mode,
    kind: "reading_activity", title: "고양이 읽기", content_markdown: "# 읽기",
    status: "draft", source_refs: [], review_note: null, request_topic: "고양이",
    request_goal: null, version: 1, parent_material_id: null, version_note: null,
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

beforeEach(() => vi.useFakeTimers());
afterEach(() => { vi.clearAllTimers(); vi.useRealTimers(); });

describe("background material polling", () => {
  it("waits for each read and announces completion once before stopping", async () => {
    const request = deferred<GeneratedMaterial[]>();
    const load = vi.fn().mockReturnValueOnce(request.promise)
      .mockResolvedValue([material("completed", "llm_enhanced")]);
    const onUpdate = vi.fn();
    const onFinished = vi.fn();
    const stop = startMaterialAiPolling({
      childId: "child-a", pendingIds: ["material-1"], inFlight: { current: false },
      isCurrent: () => true, load, onUpdate, onFinished,
    });
    await vi.advanceTimersByTimeAsync(1500);
    await vi.advanceTimersByTimeAsync(15000);
    expect(load).toHaveBeenCalledTimes(1);
    request.resolve([material("running")]);
    await vi.advanceTimersByTimeAsync(1500);
    expect(load).toHaveBeenCalledTimes(2);
    expect(onUpdate).toHaveBeenLastCalledWith([material("completed", "llm_enhanced")]);
    expect(onFinished).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(15000);
    expect(load).toHaveBeenCalledTimes(2);
    stop();
  });

  it("discards a read after unmount and releases the shared in-flight guard", async () => {
    const request = deferred<GeneratedMaterial[]>();
    const inFlight = { current: false };
    const onUpdate = vi.fn();
    const onFinished = vi.fn();
    const stop = startMaterialAiPolling({
      childId: "child-a", pendingIds: ["material-1"], inFlight,
      isCurrent: () => true, load: () => request.promise, onUpdate, onFinished,
    });
    await vi.advanceTimersByTimeAsync(1500);
    stop();
    request.resolve([material("completed", "llm_enhanced")]);
    await vi.advanceTimersByTimeAsync(15000);
    expect(onUpdate).not.toHaveBeenCalled();
    expect(onFinished).not.toHaveBeenCalled();
    expect(inFlight.current).toBe(false);
  });

  it("never commits an old child's reply or overlaps it with the new child's poll", async () => {
    const request = deferred<GeneratedMaterial[]>();
    const inFlight = { current: false };
    let oldScope = true;
    const oldUpdate = vi.fn();
    const oldFinished = vi.fn();
    const stopOld = startMaterialAiPolling({
      childId: "child-a", pendingIds: ["material-1"], inFlight,
      isCurrent: () => oldScope, load: () => request.promise,
      onUpdate: oldUpdate, onFinished: oldFinished,
    });
    await vi.advanceTimersByTimeAsync(1500);
    oldScope = false;
    stopOld();
    const loadNew = vi.fn().mockResolvedValue([material("completed", "llm_enhanced", "child-b")]);
    const newUpdate = vi.fn();
    const stopNew = startMaterialAiPolling({
      childId: "child-b", pendingIds: ["material-1"], inFlight,
      isCurrent: () => true, load: loadNew, onUpdate: newUpdate, onFinished: vi.fn(),
    });
    await vi.advanceTimersByTimeAsync(1500);
    expect(loadNew).not.toHaveBeenCalled();
    request.resolve([material("completed", "llm_enhanced")]);
    await vi.advanceTimersByTimeAsync(1500);
    expect(oldUpdate).not.toHaveBeenCalled();
    expect(oldFinished).not.toHaveBeenCalled();
    expect(loadNew).toHaveBeenCalledTimes(1);
    expect(newUpdate).toHaveBeenCalledWith([material("completed", "llm_enhanced", "child-b")]);
    stopNew();
  });

  it("rejects replies from an obsolete request generation even for the same child", async () => {
    const request = deferred<GeneratedMaterial[]>();
    let generation = 1;
    const onUpdate = vi.fn();
    const onFinished = vi.fn();
    startMaterialAiPolling({
      childId: "child-a", pendingIds: ["material-1"], inFlight: { current: false },
      isCurrent: () => generation === 1, load: () => request.promise, onUpdate, onFinished,
    });
    await vi.advanceTimersByTimeAsync(1500);
    generation = 2;
    request.resolve([material("completed", "llm_enhanced")]);
    await vi.advanceTimersByTimeAsync(15000);
    expect(onUpdate).not.toHaveBeenCalled();
    expect(onFinished).not.toHaveBeenCalled();
  });

  it("retries a temporary read failure without treating the template as AI output", async () => {
    const load = vi.fn().mockRejectedValueOnce(new Error("temporary outage"))
      .mockResolvedValue([material("failed", "template_quality_fallback")]);
    const onFinished = vi.fn();
    startMaterialAiPolling({
      childId: "child-a", pendingIds: ["material-1"], inFlight: { current: false },
      isCurrent: () => true, load, onUpdate: vi.fn(), onFinished,
    });
    await vi.advanceTimersByTimeAsync(1500);
    expect(onFinished).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1500);
    expect(onFinished).toHaveBeenCalledTimes(1);
    const notice = materialAiCompletionNotice(onFinished.mock.calls[0][0]);
    expect(notice).toContain("기본 템플릿을 유지");
    expect(notice).not.toContain("AI 학습 자료가 준비");
    expect(materialAiCompletionNotice([material("completed", "template_safety_fallback")]))
      .not.toContain("AI 학습 자료가 준비");
  });
});
