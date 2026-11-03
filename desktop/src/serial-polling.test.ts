import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { startSerialPolling } from "./serial-polling";

beforeEach(() => { vi.useFakeTimers(); });
afterEach(() => { vi.clearAllTimers(); vi.useRealTimers(); });

describe("serial status polling", () => {
  it("delivers a slow response instead of superseding it and waits before another read", async () => {
    let finish!: () => void;
    const pending = new Promise<void>((resolve) => { finish = resolve; });
    const update = vi.fn();
    const poll = vi.fn(async (current: () => boolean) => {
      await pending;
      if (current()) update();
    });
    const stop = startSerialPolling({ intervalMs: 1500, inFlight: {current:false}, poll });
    await vi.advanceTimersByTimeAsync(1500);
    await vi.advanceTimersByTimeAsync(15000);
    expect(poll).toHaveBeenCalledTimes(1);
    finish();
    await vi.advanceTimersByTimeAsync(0);
    expect(update).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1499);
    expect(poll).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(poll).toHaveBeenCalledTimes(2);
    stop();
  });

  it("cancels late state/error writes and shares the in-flight guard across effect replacements", async () => {
    let finish!: () => void;
    const pending = new Promise<void>((resolve) => { finish = resolve; });
    const inFlight = {current:false};
    const oldUpdate = vi.fn();
    const stop = startSerialPolling({ intervalMs:1500, inFlight, poll: async (current) => {
      await pending;
      if (current()) oldUpdate();
    }});
    await vi.advanceTimersByTimeAsync(1500);
    stop();
    const next = vi.fn(async () => undefined);
    const stopNext = startSerialPolling({intervalMs:1500,inFlight,poll:next});
    await vi.advanceTimersByTimeAsync(3000);
    expect(next).not.toHaveBeenCalled();
    finish();
    await vi.advanceTimersByTimeAsync(1500);
    expect(next).toHaveBeenCalledTimes(1);
    expect(oldUpdate).not.toHaveBeenCalled();
    stopNext();
    expect(inFlight.current).toBe(false);
  });
});
