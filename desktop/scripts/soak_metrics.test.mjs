import { describe, expect, it } from "vitest";
import { assessRssPlateau, parseLinuxMemoryStatus, RSS_WARMUP } from "./soak_metrics.mjs";

const sample = (elapsedSeconds, coreRssBytes) => ({elapsedSeconds,coreRssBytes});
const mib = 1024 * 1024;

describe("Core RSS observation before the steady soak", () => {
  it("retains the original cold rise but requires the observed late plateau", () => {
    const trace = [sample(0,212758528),sample(30,263020544),sample(61,265023488),
      sample(93,265035776),sample(121,265035776)];
    expect(assessRssPlateau(trace.slice(0,3)).stable).toBe(false);
    expect(assessRssPlateau(trace).stable).toBe(true);
    expect(trace.at(-1).coreRssBytes - trace[0].coreRssBytes).toBe(52277248);
  });

  it("rejects sustained slow growth even below the permitted window spread", () => {
    const slow = [sample(0,200*mib),sample(15,200*mib+4096),sample(30,200*mib+8192)];
    expect(assessRssPlateau(slow)).toMatchObject({stable:false,sustainedGrowth:true});
    expect(assessRssPlateau([sample(0,200*mib),sample(15,210*mib),sample(30,220*mib)]).stable).toBe(false);
  });

  it("does not accept missing metrics, a short window or an unstable large oscillation", () => {
    expect(assessRssPlateau([sample(0,200*mib),sample(15,null),sample(30,200*mib)]).stable).toBe(false);
    expect(assessRssPlateau([sample(0,200*mib),sample(5,200*mib),sample(10,200*mib)]).stable).toBe(false);
    expect(assessRssPlateau([sample(0,200*mib),sample(15,202*mib),sample(30,200*mib)]).stable).toBe(false);
    expect(RSS_WARMUP.maximumSeconds).toBe(120);
  });

  it("records only allowlisted Linux memory/thread metrics", () => {
    expect(parseLinuxMemoryStatus("Name:\tpython\nUid:\t123\nThreads:\t8\nRssAnon:\t100 kB\nRssFile:\t20 kB\nRssShmem:\t0 kB\n"))
      .toEqual({coreThreads:8,coreRssAnonBytes:102400,coreRssFileBytes:20480,coreRssShmemBytes:0});
  });
});
