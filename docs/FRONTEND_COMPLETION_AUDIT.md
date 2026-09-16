# Desktop completion audit

This audit treats the current React/Tauri desktop as a production user surface, not a demo of Core endpoints.

## Current structural risk

`desktop/src/App.tsx` remains the largest Core-backed controller/orchestration boundary. Presentation is split into typed feature components and `ActiveChildProvider` now owns the shared child list/selection used by the newer workspaces, but App still keeps legacy child/controller state for several older surfaces. The states are synchronized and race-guarded today; a later refactor can remove the duplicate controller ownership without changing Core contracts. This is a maintainability item, not a blocker for the user workflows below.

## Current workspace surface

The desktop exposes eleven persistent workspaces:

1. Home
2. Observations
3. Photos
4. Learning records
5. Growth
6. Activities / Quest Board
7. Search / conversations
8. Discovery
9. Library
10. Materials
11. Settings

The selected child is preserved across child-scoped workspaces. Photo, Discovery and Learning Records use the shared active-child context directly and clear child-scoped drafts/results when the child changes.

## P0 completion batch

- [x] Persistent eleven-workspace navigation with keyboard/tab semantics, skip link, reduced-motion support and responsive laptop-width layouts.
- [x] Child-scoped loading/error/empty states with stale-response guards so a slow request for a previous child cannot overwrite the current view.
- [x] Explicit Core-only mode. Recording, lexical retrieval, activity management, deterministic material generation, Parent Review, backup/restore and manual photo diary remain usable without an LLM.
- [x] Backup/import/restore, child purge and runtime diagnostics live in Settings with app-level confirmation rather than browser confirmation APIs.
- [x] Parent Review is a first-class material state machine. Only approved materials are printable/exportable.
- [x] Visible success/error feedback for writes and background AI state (`queued`, `running`, `completed`, `failed`, `skipped`).
- [x] Desktop Core trust boundary uses OS app-data, a random loopback port and a per-run session token.

## P1 product-quality batch

- [x] Home dashboard summarizes useful next actions and recent child-scoped records instead of implementation details.
- [x] Observation timeline supports filters, activity linkage, experience axes and record details.
- [x] Growth map presents record coverage/diversity as context, not ability, diagnosis, percentile or peer ranking.
- [x] Quest Board manages selected activities and approved generated materials through `생성됨 -> 진행 중 -> 완료됨/건너뜀 -> 결과 기록됨`.
- [x] An approved `GeneratedMaterial` automatically receives a real `ActivityPlan` with `material:<UUID>` provenance when its approved-use card is rendered. The material card and global Quest Board therefore operate on the same activity object rather than parallel synthetic state.
- [x] Material result entry persists structured process, child question/reaction, interest, difficulty, next activity and experience axes as a `LearningLog(record_kind=material_use)`.
- [x] Material-use results feed the next material-generation cycle. Raw parent/learner text stays in the local parent guide; model-facing personalization receives generalized scaffolding signals only.
- [x] Materials generate two parent-reviewable outputs: child-facing material plus a parent teaching/facilitation guide. Approved print output uses kind-specific A4 presentation templates.
- [x] Seven material kinds are available across stages, including parent-led, low-pressure infant variants.
- [x] Resource library provides search/filter/detail/edit/delete, provenance display, synchronized RAG mutation and read-only presentation for sibling-shared resources.
- [x] `child_scope` sharing is visibility, not ownership: sibling-shared resources can be read/retrieved but not edited, deleted or re-shared outside the owning child context.
- [x] Search/conversation history preserves evidence IDs and keeps conversation text separate from factual evidence.
- [x] First-run onboarding explains that the child profile is the only required setup and local AI is optional.

## P2 closed-loop and discovery batch

- [x] Manual photo diary works without AI. Photo bytes are saved first; optional vision/text analysis runs through a durable background job. Parent notes are never passed into the vision caption call.
- [x] Photos commit to `LearningLog(record_kind=photo_activity)` after parent review and survive AI/provider failure.
- [x] Independent Learning Records workspace captures reading reflections, diary entries, school/academy learning, self-study, assignments/projects and other learning that did not originate from a GrowWise quest.
- [x] Independent records use the same `LearningLog` ecosystem so they participate in search, growth context and later material personalization instead of forming an isolated diary database.
- [x] Discovery combines official curriculum metadata, optional public curriculum endpoints, Data4Library book candidates and optional Overpass place discovery.
- [x] External candidates are never automatically persisted. The parent explicitly saves a candidate to create a provenance-bearing `ResourceRecord` and RAG evidence.
- [x] External discovery privacy is enforced in code: free-form interests/goals/log tags/activity titles are local ranking context, while public adapters receive only canonical allow-listed education topics. Child IDs, names, nicknames, raw observations, parent notes and photos do not cross this boundary.
- [x] Overpass receives coordinates only when the parent explicitly enters latitude/longitude; those coordinates are not stored in the child profile.
- [x] Shared resources participate in child-scoped RAG visibility without turning `child_scope` into a semantic expansion edge.
- [x] Slow non-interactive text-model work uses deterministic-save-first background enrichment. Interactive chat/search remains foreground because the parent is waiting for an answer.

## Definition of done

For repository-controlled behavior, a non-developer can:

- create/select multiple children and switch child-scoped workspaces safely;
- record ordinary observations, manual/AI-assisted photo diaries, and independent reading/diary/school/self-study records;
- connect one source activity/resource to multiple children without duplicating the source record;
- inspect growth context and search long-term records/resources;
- discover public books/curriculum/places without sending private child text to public adapters;
- save chosen discovery evidence to the library;
- generate a child-facing material and parent guide with or without an LLM;
- Parent Review, edit/revise, approve, print/PDF and manage approved materials as Quest Board items;
- enter the real-world result of a printed activity and have that result feed later material personalization;
- back up, restore/export/import and permanently purge a child's live data;
- continue all required deterministic workflows while the LLM provider is unavailable.

No required workflow should depend on understanding Core/sidecar implementation terminology. Public stable distribution still requires operator-owned signing/notarization, updater trust-root activation, packaged-client update testing and household dogfooding as described in `docs/RELEASE_READINESS.md`.
