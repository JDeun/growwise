# Hardening Pass 2

This pass converts the adversarial review findings into explicit runtime invariants.

- Markdown remains the authoritative source of truth. SQLite entity and RAG indexes are rebuildable projections.
- A failed incremental entity projection triggers a rebuild from Markdown before the write is reported failed.
- Idempotency release never discards a reserved resource ID; retries reacquire the same logical ID.
- Background jobs use leases so process death cannot strand work permanently in `running`.
- The desktop shell never trusts a process merely because port 8765 is open. It starts its own Core, receives a CSPRNG session token through a private file handoff, and authenticates the health check before accepting the sidecar.
- Packaged Core HTTP requests require the per-process bearer token. Standalone developer Core remains an explicit unauthenticated localhost workflow.
- Material-review checkpoints and RAG data are projections: projection outages are logged and degraded, but do not invalidate an already committed authoritative record.
- Resource creation validates child ownership and supports idempotent replay.
- Backup import validates archive members before reading the manifest and applies a dedicated manifest size ceiling.
- Storage relocation rejects source/destination index collisions and overlapping paths.
- Lock registries are bounded and recovery writes use the same fsync durability rule as normal writes.
- RAG SQLite uses busy timeouts/WAL; lexical-only search uses FTS5 candidates when available.
- CI audits the locked Python graph, runs Rust tests, verifies authenticated bundled-Core behavior, scans secrets, and pins GitHub Actions by commit SHA.

Failure-injection coverage lives in `tests/test_hardening_pass2.py`.
