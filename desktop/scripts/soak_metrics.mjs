export const MEMORY_WARMUP = Object.freeze({
  maximumSeconds: 300,
  minimumSeconds: 60,
  minimumCycles: 3,
  sampleIntervalSeconds: 15,
});

export const MEMORY_GROWTH_LIMITS = Object.freeze({
  coreBytes: 32 * 1024 * 1024,
  browserBytes: 8 * 1024 * 1024,
});

const positiveBytes = value => Number.isSafeInteger(value) && value > 0;

// Resident pages can be reclaimed or faulted back in by the OS. Exercise a fixed representative
// workload before measuring growth; an RSS plateau is not evidence of allocation stability.
export function assessMemoryWarmup(samples, cycles) {
  const valid = samples.length > 0 && samples.every(item => positiveBytes(item.coreRssBytes));
  const elapsedSeconds = samples.at(-1)?.elapsedSeconds;
  const expired = Number.isFinite(elapsedSeconds) && elapsedSeconds > MEMORY_WARMUP.maximumSeconds;
  return {ready:valid && Number.isInteger(cycles) && cycles >= MEMORY_WARMUP.minimumCycles
      && Number.isFinite(elapsedSeconds) && elapsedSeconds >= MEMORY_WARMUP.minimumSeconds && !expired,
    valid, expired, elapsedSeconds, cycles};
}

export function assessMemoryGrowth(samples, {requirePrivate = false} = {}) {
  const valid = samples.length > 1 && samples.every(item => positiveBytes(item.coreRssBytes)
    && positiveBytes(item.heapUsedBytes) && (!requirePrivate || positiveBytes(item.corePrivateBytes)));
  if (!valid) return {valid:false, withinBudget:false};
  const growth = field => Math.max(...samples.map(item=>item[field])) - samples[0][field];
  const coreRssGrowthBytes = growth("coreRssBytes");
  const browserHeapGrowthBytes = growth("heapUsedBytes");
  const corePrivateGrowthBytes = requirePrivate ? growth("corePrivateBytes") : null;
  return {valid:true, withinBudget:coreRssGrowthBytes <= MEMORY_GROWTH_LIMITS.coreBytes
      && browserHeapGrowthBytes <= MEMORY_GROWTH_LIMITS.browserBytes
      && (!requirePrivate || corePrivateGrowthBytes <= MEMORY_GROWTH_LIMITS.coreBytes),
    coreRssGrowthBytes, browserHeapGrowthBytes, corePrivateGrowthBytes};
}

export function parseLinuxMemoryStatus(text) {
  const values = {};
  for (const line of text.split("\n")) {
    const match = /^(Threads|RssAnon|RssFile|RssShmem):\s+(\d+)(?:\s+kB)?$/.exec(line.trim());
    if (match) values[match[1]] = Number(match[2]);
  }
  return {
    ...(values.Threads === undefined ? {} : {coreThreads:values.Threads}),
    ...Object.fromEntries(["RssAnon","RssFile","RssShmem"]
      .filter(key => values[key] !== undefined).map(key => [`core${key}Bytes`,values[key] * 1024])),
  };
}
