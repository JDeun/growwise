/** A slow read never overlaps or invalidates the previous poll. */
export function startSerialPolling({ intervalMs, inFlight, poll, isCurrent = () => true, onError }: {
  intervalMs: number;
  inFlight: { current: boolean };
  poll: (isCurrent: () => boolean) => Promise<void>;
  isCurrent?: () => boolean;
  onError?: (error: unknown) => void;
}): () => void {
  let cancelled = false;
  let timer: ReturnType<typeof setTimeout>;
  const current = () => !cancelled && isCurrent();
  const schedule = () => { timer = setTimeout(() => { void run(); }, intervalMs); };
  async function run() {
    if (!current()) return;
    if (inFlight.current) { schedule(); return; }
    inFlight.current = true;
    try { await poll(current); }
    catch (error) { if (current()) onError?.(error); }
    finally { inFlight.current = false; }
    if (current()) schedule();
  }
  schedule();
  return () => { cancelled = true; clearTimeout(timer); };
}
