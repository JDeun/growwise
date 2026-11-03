export const RSS_WARMUP = Object.freeze({
  maximumSeconds: 300,
  sampleIntervalSeconds: 15,
  minimumSpanSeconds: 30,
  maximumSpreadBytes: 512 * 1024,
  sampleCount: 3,
});

// RSS alone cannot identify an allocator or prove absence of every slow leak. Require an observed
// plateau, rejecting even small sustained increases, before starting the separate steady interval.
export function assessRssPlateau(samples) {
  const window = samples.slice(-RSS_WARMUP.sampleCount);
  if (window.length < RSS_WARMUP.sampleCount
      || window.some(item => !Number.isFinite(item.coreRssBytes) || item.coreRssBytes <= 0)) {
    return {stable:false, reason:"insufficient_valid_samples"};
  }
  const spanSeconds = window.at(-1).elapsedSeconds - window[0].elapsedSeconds;
  const values = window.map(item => item.coreRssBytes);
  const spreadBytes = Math.max(...values) - Math.min(...values);
  const sustainedGrowth = values.slice(1).every((value,index) => value > values[index]);
  return {stable:spanSeconds >= RSS_WARMUP.minimumSpanSeconds
      && spreadBytes <= RSS_WARMUP.maximumSpreadBytes && !sustainedGrowth,
    spanSeconds, spreadBytes, sustainedGrowth};
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
