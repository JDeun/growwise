# Documentation to implementation trace audit

Observed 2026-11-03 against code revision `e3c3b3b` plus the current working tree. This is a
code/caller/test trace, not a replacement for Windows runtime, household use or model-quality
evaluation. The original nine gaps below are closed by the follow-up evidence table. The historical
reproductions remain unchanged. A later explicit child/date raw-record export requirement is tracked
separately and is not silently counted as implemented by the full backup feature.

Documents reviewed: README; vision/product specification; user guide/product tour; roadmap;
architecture/data model; material UX; Learning Wiki; integrations; privacy/hardening contracts;
release/readiness/operator handoff. Research candidate matrices and explicitly future/operator-only
items are kept separate from claims that a user can use a feature today.

## Confirmed gaps at the snapshot

| Priority | Promise and trigger | Actual boundary | Required work |
| --- | --- | --- | --- |
| P1 | `product-spec.md:81-88`, `vision.md` promise temporal/axis natural-language retrieval. Ask “최근 한 달 신체 활동 기록만 찾아줘” with a 90-day-old physical log. | `services/search.py:9` has no date/axis/order fields; `storage/sqlite.py:396` performs OR keyword matching and updated-time ranking. Synthetic local reproduction returned that old log. Conversation `services/context.py:175` bypasses even the keyword planner. | Shared conservative query plan, enforce dates/axis/order before limit in direct and conversational retrieval; offline/provider-failure regressions. Assigned research/docs agent. |
| P1 | `hardening-contracts.md:58` promises stale async child isolation; switch secondary child while study requests are pending. | `StudyTrackingPanel.tsx:121` commits six responses without scope generation; mutations append unconditionally. `LearningRecordWorkspace.tsx:425` mounts it without a child key. | Guard or remount the child-owned tracker; prove late child A reads/writes cannot appear under B. |
| P2 | `product-spec.md:88` and vision examples offer “이 책과 현재 관심사를 연결해 내일 할 활동을 만들어줘”. | Conversation service only stores a grounded answer; it never creates a material nor returns an actionable parent-confirmed generation proposal. | Explicit typed proposal plus parent action into existing material generation; retain review boundary. Assigned root. |
| P2 | `user-guide.md:166-169` promises editable reference summary/source/author/tags and child/global scope. | `use-resource-management.ts:67` hardcodes null source/author/summary, empty tags, current child. `ResourceLibrarySection.tsx:111` edits only kind/title/content, resending other fields unchanged. Core supports the missing metadata. | Expose bounded metadata and scope controls; preserve original ownership on edit and prove actual request payloads. Assigned dependency agent. |
| P2 | `data-model.md:172-180` documents `book_id`, `ai_hint`, `evidence_checked`, `child_reexplanation` on LearningLog. | `domain/models.py:227` and create API/desktop forms contain none. Separate secondary self-explanation entities do not implement these general record fields. | Optional persisted fields through record/result capture and details, with legacy defaults and source visibility checks. Assigned root. |
| P2 | README/user guide promise approved print/PDF without requiring internal workflow management. | Actual print action exists at `MaterialWorkspace.tsx:678`, inside the advanced “자료 수정·검토 관리” disclosure (`:508`), not in the primary document actions. | Reachable primary approved print action using existing scoped print path. Assigned root. |
| P2 | User guide allows record date and describes recent experience coverage. Enter an old event today. | `services/growth.py:117` uses `created_at` instead of `occurred_at`; timeline uses event date. | Keep recent coverage aligned to event time, retaining created-time fallback for legacy records. |
| P2 | `product-spec.md:90` promises related sources and records with answers. Inspect a cited original from a conversation. | `SearchConversationSection.tsx:81-95` renders inert numbered spans with raw IDs in `title`; no original title, date, text or detail action. | Child-visible original evidence disclosure/resolution, with deleted/revoked-source handling; avoid treating a numbered badge as actual source inspection. |
| P2 | References can be shared with every child; save a global reference through the new scope control and refresh the library. | The child-filtered collection originally omitted null-owner references, so a successfully saved global source disappeared from its own UI. | Resource collections explicitly include globals while ordinary child-owned entity listings keep their strict default. `test_resource_visibility_api.py` covers actual HTTP collection behavior. |

## Feature matrix

“Wired” means the visible caller reaches the real implementation. Tests listed are existing
regression entry points, not a claim that this audit reran every test. The final actual-Core browser
journey is separately recorded in [the expanded 18-step run](knowledge/experiments/live-core-browser-20261103-completion.md).
Rows below describe the original trace; the resolution table is the current disposition.

| Documented feature | UI / native entry | Core/storage path | Evidence and status |
| --- | --- | --- | --- |
| First profile, birthday/month/grade, family context | ChildProfileSection, ChildProfileEditor; child commands | child_profile_routes; ChildProfile current-date curriculum methods | Wired; child/profile and curriculum tests; actual UI first profile. |
| Multiple children / switch / private scope | ActiveChildProvider, profile switcher | visibility, entity links, child-scoped routes | Wired; actual private-scope browser check; secondary tracker race remains above. |
| Independent reading/diary/school/self-study/assignment records | LearningRecordWorkspace, learning-record API/IPC | learning_record_routes → LearningLog Markdown/SQLite | Wired; actual separate reading record; optional documented fields missing above. |
| Observation and optional asynchronous tagging | ObservationGrowthSection; create_observation_background | background_write_routes, BackgroundAiJobRunner, ObservationEnricher | Wired; background/provider-failure tests; original saved first. |
| Infant low-pressure suggestions | ActivitiesSection, infant commands | infant activity routes, InfantActivityService | Wired; test_infant_activity / test_infant_guidance; no field-effectiveness claim. |
| Infant observation hints and read-aloud/board books | InfantGuidanceSection, real onLoad handler | infant hints and board-books routes; local/public/offline sources | Wired; test_infant_guidance, component source-label/privacy test. |
| Experience map, three layers, diversity | Profile development tab / GrowthContextPanel | GrowthMapService | Wired; test_growth; event-date defect above. |
| Timeline search/axis/activity/period filters | ObservationTimelineSection | saved LearningLog fields | Wired; client filtering and details; separate from missing natural-language filters. |
| Seven material families, every stage | MaterialWorkspace composer / material commands | MaterialGenerationService, stage-kind templates, curriculum resolver | Wired; material/scaffold/commercial/malformed tests; live deterministic generation. Real model evidence remains sample-scoped. |
| Immediate saved fallback, durable enhancement/retry | MaterialAiNotice; retry IPC | background_write_routes, durable queue, shared inference/mutation locks | Wired; background/retry tests; inadequate model output preserves template. |
| Parent use/reject/revise/edit and immutable history | Primary use; advanced review/edit | material_routes, review graph, MaterialReviewService, immutable version locks | Wired; live use, review/recovery/race tests. |
| Parent guide, sources and curriculum details | Canvas guide/source tabs | stored parent_guide, validated source refs, curriculum target metadata | Wired; presentation/source/privacy tests. |
| Print/PDF, page size/orientation/margins, worksheet | Approved advanced print action, PrintLayout | native WebView OS print and scoped CSS | Implemented and gated; primary-action reachability gap above. ADR0001 chooses OS print, not a server PDF engine. |
| Activity lifecycle and structured result | ActivitiesSection / MaterialResultPanel | ActivityService / MaterialQuestService → LearningLog and entity links | Wired; actual one-line result and persisted provenance; richer optional fields above. |
| Prior records inform next materials | Local parent guide + optional private model guidance | MaterialFeedbackService, local-only Wiki context | Wired; background/context/privacy tests; deterministic guidance is bounded, not a guarantee of educational usefulness. |
| References create/read/update/delete, share/revoke | ResourceLibrarySection / EntityLinkPanel | resource_routes, ResourceIngestor, entity links | Basic CRUD wired and actual UI tested; metadata/global-create gap above. |
| External books/curriculum/places/science resource candidates | DiscoveryWorkspace, saved-candidate action | EducationDiscoveryService + allowlisted public query adapters | Wired; discovery/offline/privacy tests. Explicit candidate-only integrations are not falsely counted missing. |
| Official curriculum version and update watch | Material curriculum panel; CI watcher artifact | curriculum_versions, official catalog, curriculum_watch | Wired; grade/date fail-closed tests; new web notices require review, no automatic promotion. |
| Lexical/embedding/graph retrieval and grounded answers | Conversation and direct-search UI / search commands | NaturalLanguageSearch, ChildContextService, HybridRagIndex, graph context | Basic paths wired and actual UI tested; temporal/axis/last-event and generation-action gaps above. |
| Conversations, follow-up, confirmed deletion | SearchConversationSection | conversation_routes, SQLiteConversationStore | Wired; actual follow-up/source citation and deletion preserving sources. |
| Learning Wiki, explicit rebuild, source provenance | Profile report / LearningWikiPanel; wiki IPC | LearningWikiService; original-only fingerprints, local-only synthesis | Wired; actual UI rebuild and source refs; test_learning_wiki and API tests. |
| Photos upload/manual/AI draft/commit/retry/share | PhotoActivityWorkspace / photo IPC | photo_routes, managed assets, PhotoJobRunner, PhotoActivityService | Wired; actual upload/manual commit/byte-preserved restore; photo/retry/privacy tests. |
| Secondary progress/mistake/reflection/explanation | StudyTrackingPanel; study API/IPC | study_routes; study domain entities, Markdown/SQLite | Wired, not absent; stale-child completion defect above. |
| Weakness hypotheses/resources/support/plan status | Tracker map/plan tab | StudyTrackingService; weak-map/resources/plans routes | Wired; test_study_tracking/context; non-diagnostic language. |
| Backup/create/export/import/restore/history | Backup workspace; native file dialogs | backup routes and BackupService/archive validator/recovery journal | Wired; actual UI backup/restore plus backup/security/recovery tests. ZIP is a lossless snapshot. |
| Full current-child purge | DataManagementSection confirmed nickname | PrivacyService; source, index, jobs, assets, links, conversations | Wired; privacy tests; historical ZIPs and retained relocation copy explicitly separate. |
| Whole store relocation/recovery | StorageSettings / storage_commands | CoreProcessManager stop/lock/copy/verify/restart; durable pointer + dirty index rebuild | Wired; native actual Core relocation test; original recovery copy retained and disclosed. |
| Local model list/download/select/remove | LocalModelSettings / model_commands | configured local Ollama tags/show/pull/delete, saved selection/restart | Wired; capability/role/confirmation tests; tag digest is metadata, not fresh integrity proof. |
| Personal API keys/status/disable/connection check | ApiKeySettings / credential_commands | OS native store, Core restart, fixed public integration tests | Wired; synthetic macOS native-store round trip; Windows runtime requires platform evidence. |
| Hardware model defaults and provider replacement | Settings preparation / core_process; advanced env config | hardware recommendation, factory, separate embedding/vision config | Wired; native recommendation and provider tests; defaults are not blanket measured quality recommendations. |
| Accessibility, keyboard/focus, localization foundation | Workspace nav, dialogs, main.tsx document locale | a11y/i18n utilities | Implemented foundation and tests. Full English UI translation is not promised: most product copy remains Korean. |
| Windows/macOS package and signed-update automation | package workflow / readiness/configurator scripts | sidecar build/smoke, Tauri bundle/release manifest | Code/CI paths present. Signing credentials, durable updater trust root and installed-client verification remain explicitly operator-only. |
| Maintainer research wiki | docs/knowledge, offline CLI and workflows | append-only source/experiment registries, structural/history checks | Wired; dedicated tests/CI; distinct from child Learning Wiki. |

## Explicit future or external evidence, not hidden implementation claims

- App-level storage encryption, redacted sharing export, per-call remote consent and model-engine
  prompt-log control are explicitly absent in `privacy-and-safety.md:106`; OS disk encryption and
  configured-provider opt-in are the implemented boundaries. These remain optional future features,
  not completed code or an inferred reason to change lossless backup semantics.
- `integrations.md:26-42` explicitly separates connected adapters from the candidate/extension matrix
  (for example speech, math engines and notation). Candidate links are not promised live features.
- Anthropic/Google vendor SDKs are optional future adapters; local/remote OpenAI-compatible and
  Ollama are the actual supported text providers. Independently selected AI review models are not
  configured today; automated review is deterministic and Parent Review is implemented.
  Architecture's broad role-separation wording has been corrected to name actual text/vision/
  embedding roles and independent text-task budgets.
- Household longitudinal usefulness, representative hardware/age-kind model quality, production
  signing/notarization and durable updater-key validation cannot be inferred from source tests.
  Their procedures and open status are documented in operational-validation/operator-handoff.

Completion refers to tested user behavior, not merely domain entities or an adapter function
existing. Closing these nine findings is not evidence that every possible future defect is absent.

## Resolution of the original nine findings

All nine original gaps are closed in the working tree based on `e3c3b3b`. The
[18-step actual-Core journey](knowledge/experiments/live-core-browser-20261103-completion.md) loaded
`index-DgKRkCJj.js` and `index-CgZeVefP.css`; the artifact pins its script and build hashes.

| Finding | Implemented path | Verification and disposition |
| --- | --- | --- |
| Temporal/axis/last-event search | Shared `NaturalLanguageSearch.explicit_plan`, `record_time`, direct/context retrieval; constrained questions bypass model rewrite | **Closed.** `test_search_constraints.py` and actual FastAPI query exclude a 90-day-old event entered today; filter before limit, provider fallback and last-occurrence ordering verified. This is focused API/service evidence, not an added browser assertion. |
| Late secondary-child responses | Keyed `ChildLearningRecords` remount, containing StudyTrackingPanel | **Closed.** Actual Core learning/study responses from A are deliberately delivered after B loads; B's displayed data remains isolated in the 18-step journey. |
| Conversation generation command | Typed persisted `material_action`, explicit parent CTA and material-composer handoff | **Closed.** Actual UI proposal creates nothing alone; topic and visible book reach composer; parent submits an unapproved reading draft with the saved book ref. |
| Reference metadata and scope controls | ResourceDetailsFields, create/edit payload helpers, ownership/scope-aware resource routes | **Closed.** UI creates global metadata, edits source name and private scope, preserves author/URL/tags, shows current details and confirms deletion; focused HTTP/component tests cover bounds and scope denial. |
| Optional LearningLog fields | Domain/API/native/TS fields, LearningEvidence form/detail/history and source-visibility validation | **Closed.** Actual material result stores book/hint/false/reexplanation; independent record shows true and its distinct reexplanation. All three added form/history/detail screenshots inspected; scope/legacy tests remain. |
| Primary approved print | Primary canvas CTA, scoped approved card, temporary supporting-detail expansion | **Closed.** Browser verifies native-print call dispatch, real eight-page PDF, one-document print scope and restoration of prior details. OS print dialog is a separate native target. |
| Experience-date growth | Shared occurred_at-first helper, created_at legacy fallback and future exclusion | **Closed.** `test_growth.py` verifies old backfilled events excluded, recent event with older creation included, legacy fallback and event-time moments. Not inferred from a screenshot. |
| Inspectable original citations | Child-visible evidence resolver, native IPC, ConversationEvidence disclosure | **Closed.** Actual UI opens title/date/current authored body; ten API regressions reject Wiki/deleted/revoked/stale-global/unsafe URL paths. Display metadata is localized without changing authored text. |
| Global reference collection wiring | Explicit `include_global` for resource collections, strict default elsewhere | **Closed.** Actual global save remains reachable for editing; HTTP regression includes global+own sources while excluding sibling-private sources and duplicate grants. |

External source opening has a separate runtime follow-up: ExternalSourceLink reaches
`external_commands::open_external_url` through native IPC, validates HTTP(S), and opens the OS default
browser. The isolated macOS native smoke was run by the integration agent. Its success is separate
from the browser IPC adapter's evidence.

## Later explicit export requirement

`data-model.md` additionally requires a portable raw Markdown bundle selected by child and period.
Normal backup is a full lossless snapshot and does not implement that selection. A distinct scoped
export endpoint/native/UI is now implemented: `backup/records_export.py`,
`api/records_export_routes.py`, native `export_child_records` and the Backup workspace form.
Sixteen actual API tests pass, including byte-exact originals, event-time filtering, supporting books
and assets, raw-source ownership, revoked sharing, symlink/traversal/hash rejection, limits and
temporary cleanup. The different manifest is rejected by whole-app restore; normal whole-backup
validation still passes. Native three tests and frontend form/API checks passed in their owning lane.
**Closed by actual production UI verification.** The [final21-assertion run](knowledge/experiments/live-core-browser-20261103-verified.md) selects child/date in the form, downloads the real ZIP, checks scope and all hashes, and confirms full restore rejects it. The new export screenshot was independently inspected.
See [the exact export boundary](record-export.md).

## Independent second contract pass

A second implementation pass reread the README, product specification, data model, user guide and
roadmap requirements, distinguishing current product contracts from conceptual entity names, future
integration candidates and external operational evidence. It found two additional concrete gaps
besides the separately tracked selective export:

- Generated materials did not retain the actual accepted model identity or stable parent decision
  time. `generator_version`, accepted-only `model_provider/model_id`, `review_decision` and
  `reviewed_at` now survive Markdown rebuild, background enhancement and archival. Parent edits
  carry their own producer and immutable origin lineage. Existing records retain unknown metadata.
  The collapsed parent guide exposes these facts; it does not invent a model for fallback output or
  independent parent checklist attestations. Eleven focused producer tests include actual HTTP
  use/edit/archive round trips, and the review checkpoint records its actual `decision_at`.
- The infant contract explicitly forbids worksheets, but the supporting print template was
  rendered for every stage. `MaterialParentGuide` now receives the selected child's stage and omits
  worksheet writing zones for infants while retaining the parent interaction guide. Stage-specific
  component tests cover the distinction.

Both second-pass findings are **closed**: producer/review-time service/HTTP/UI tests pass; the [final actual-Core run](knowledge/experiments/live-core-browser-20261103-verified.md) also verifies infant worksheet absence, visible safety guidance and actual infant PDF generation.

No further concrete missing current promise was confirmed in this bounded pass. This is a scoped
contract trace, not proof of universal model quality, infant safety certification, long-term household
effectiveness or installed Windows runtime behavior. The model evidence preserves weak-model
failures and the first unsafe infant candidate alongside the corrected, parent-reviewed samples.

## Follow-up implementation evidence

The search/date gaps above now have a working-tree fix: shared explicit date/axis/event-order plans
serve direct and conversational retrieval; strict queries exclude unfiltered Wiki/RAG/graph context.
The event-time helper prefers `occurred_at`, then legacy `created_at`; growth also excludes future
events. Subject and reading-kind metadata work without duplicate optional experience tags.
`tests/test_search_constraints.py` covers the documented month/physical query, last measurement,
provider failure/constraint removal, date ranges, literal topics, untagged records, calendar words
and chat source isolation. A real FastAPI TestClient call with AI disabled returned only yesterday's
event and excluded an event90daysold enteredtoday (HTTP200). Final aggregate CI and the other assigned
fixes remain separate verification steps.

The original-source reader is implemented through `api/evidence_routes.py`, native
`evidence_commands.rs`, `evidence-api.ts` and `ConversationEvidence.tsx`. It resolves each disclosure
against the current original, never a cached chunk body; every open rechecks current child visibility.
Derived Wiki, deleted/revoked originals, private sources behind stale global chunks and unsafe URLs
are rejected. Nine actual API tests and six frontend rendering/IPC tests passed; source content is
escaped text with title/event date and an optional safe link. Keyboard users can open each disclosure
and focus its scrolling text. The expanded actual-Core journey now verifies that click path.

Current local checks for this lane:66 focused search/growth/context/graph/wiki tests passed, including
the Windows cp1252-default/UTF-8 Git history regression. Ruff and mypy passed for the changed source.
The resolution table records the completed integration without deleting this historical audit
evidence. Full commit CI/native-platform results remain separate from the scope of a local browser run.


## Release hardening follow-up

The release audit subsequently confirmed that plugin registration alone lacked a reachable updater
check/install flow, and a signed stable tag could pass while updater artifacts were disabled.
`UpdaterSettings`, native `updater_commands` and the committed optional Cargo feature now implement
explicit version checking and confirmed verified installation/restart. Stable preflight and asset
assembly fail closed without activation/signing inputs and all three signed updater bundles.
The shared confirmation dialog now uses a real fixed portal overlay; busy install prevents new
background input/navigation, traps focus and restores editable UI on failure. Native signature/
interruption tests and browser IPC-only confirmation/focus/failure checks cover this code path;
production-key success and physical Windows updates remain unverified operator evidence.
See [the dated audit and release assessment](release-readiness-20261103.md).
