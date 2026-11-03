import { describe, expect, it } from "vitest";
import { assessMemoryGrowth, assessMemoryWarmup, MEMORY_WARMUP, parseLinuxMemoryStatus } from "./soak_metrics.mjs";

const mib = 1024 * 1024;
const sample = (elapsedSeconds, coreRssBytes, extra = {}) => ({elapsedSeconds, coreRssBytes,
  heapUsedBytes:6*mib, ...extra});

describe("Representative warmup and bounded memory growth", () => {
  it("requires both a full minute and three complete workspace cycles, with a bounded setup", () => {
    expect(assessMemoryWarmup([sample(0,120*mib),sample(59,120*mib)],3).ready).toBe(false);
    expect(assessMemoryWarmup([sample(0,120*mib),sample(60,120*mib)],2).ready).toBe(false);
    expect(assessMemoryWarmup([sample(0,120*mib),sample(60,120*mib)],3).ready).toBe(true);
    expect(assessMemoryWarmup([sample(0,120*mib),sample(301,120*mib)],30))
      .toMatchObject({ready:false,expired:true});
    expect(MEMORY_WARMUP.maximumSeconds).toBe(300);
  });

  it("accepts the actual Windows resident oscillation as exercised warmup, without claiming a plateau", () => {
    const trace = [sample(0,129810432),sample(17,125739008),sample(33,125820928),
      sample(50,124645376),sample(66,123527168)];
    expect(assessMemoryWarmup(trace,28).ready).toBe(true);
    expect(assessMemoryWarmup([sample(0,null),sample(60,120*mib)],3).ready).toBe(false);
  });

  it("rejects sustained growth beyond the same32MiB budget even if the last sample returns to baseline", () => {
    const trace = [sample(0,100*mib),sample(30,116*mib),sample(60,132*mib+1),sample(120,100*mib)];
    expect(assessMemoryGrowth(trace)).toMatchObject({valid:true,withinBudget:false,coreRssGrowthBytes:32*mib+1});
    expect(assessMemoryGrowth([sample(0,100*mib),sample(120,100*mib,{heapUsedBytes:14*mib+1})]).withinBudget).toBe(false);
  });

  it("requires valid private bytes on Windows and checks committed growth independently of falling RSS", () => {
    const trace = [sample(0,130*mib,{corePrivateBytes:100*mib}),sample(120,110*mib,{corePrivateBytes:132*mib+1})];
    expect(assessMemoryGrowth(trace,{requirePrivate:true}))
      .toMatchObject({valid:true,withinBudget:false,coreRssGrowthBytes:0,corePrivateGrowthBytes:32*mib+1});
    expect(assessMemoryGrowth([sample(0,130*mib),sample(120,110*mib)],{requirePrivate:true}).valid).toBe(false);
    expect(assessMemoryGrowth([sample(0,130*mib),sample(120,null)]).valid).toBe(false);
    expect(assessMemoryGrowth([sample(0,130*mib)]).valid).toBe(false);
    expect(assessMemoryGrowth([sample(0,130*mib),sample(120,110*mib)]).withinBudget).toBe(true);
  });

  it("records only allowlisted optional Linux diagnostics", () => {
    expect(parseLinuxMemoryStatus("Name:\tpython\nUid:\t123\nThreads:\t8\nRssAnon:\t100 kB\nRssFile:\t20 kB\nRssShmem:\t0 kB\n"))
      .toEqual({coreThreads:8,coreRssAnonBytes:102400,coreRssFileBytes:20480,coreRssShmemBytes:0});
  });
});
