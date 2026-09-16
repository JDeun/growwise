# Desktop completion audit

This audit treats the current React/Tauri desktop as a production user surface, not a demo of Core endpoints.

## Current structural risk

`desktop/src/App.tsx` now acts primarily as the Core-backed controller/orchestration boundary. System status, child profile, observation/growth, search/conversation, resource library, infant guidance, activities, timeline, and data-management presentation live in typed feature components. App still owns substantial feature state and mutation handlers, so future work can continue moving controller logic into feature hooks without changing Core contracts or child-scope behavior.

## P0 completion batch

- [x] Introduce persistent workspace navigation: Home, Observations, Growth, Activities, Search, Library, Materials, Settings.
- [x] Preserve active child context across all workspace views (the App remains mounted across workspace changes and the child switcher remains available in child-scoped views).
- [x] Add route/view-level empty, loading, and error states. Growth, observations, library, materials, and activities now load independently, expose local recovery actions, and no longer collapse the whole child context when one endpoint fails.
- [x] Make Core-only/offline capability explicit in the UI; a persistent capability status explains that deterministic records, search, growth, activities, resource management and Parent Review remain available when AI is unavailable.
- [x] Move backup/import/restore and runtime diagnostics into Settings (the Settings workspace projects system status and data-management surfaces together).
- [x] Make Parent Review a first-class Materials workflow, not an inline implementation detail.
- [x] Provide visible success feedback for writes. Child profile, observation, resource, material, and activity mutations now announce completion through a persistent-in-viewport polite status notice; backup create/export/import/restore retain Settings-local status feedback, and destructive import/restore actions use the accessible app confirmation dialog.
- [x] Audit keyboard focus, landmarks, labels, aria-live errors/status, reduced motion, and contrast. Workspace navigation now exposes tablist/tab/tabpanel semantics with roving keyboard focus and a skip link; dialogs trap focus; form errors/status use alert/status semantics; reduced-motion overrides are present; and the primary action/text color was darkened so normal-size white/green combinations clear WCAG AA contrast.
- [x] Add narrow-window behavior suitable for common laptop sizes (workspace navigation and content grids collapse at 900/700/600 px breakpoints, with reduced-width shell spacing on small windows).
- [x] Break App.tsx into feature components without changing Core semantics. App retains orchestration and mutation ownership while workspace presentation is split into typed feature sections.

## P1 product-quality batch

- [x] Home dashboard with next useful actions and recent records rather than system implementation details. Home now summarizes recent observations, active activities, reviewable materials and library size, exposes direct workspace actions, and tolerates partial summary failures.
- [x] Timeline filters and record detail view. Observations can be filtered by text, experience axis, activity linkage and period; selecting a record opens a detail panel with activity, axes, interests, tags and next-activity context.
- [ ] Growth map visual hierarchy and explainability.
- [ ] Activity lifecycle UX: suggested -> active -> completed/skipped -> linked observation.
- [ ] Material queue segmented by draft/review/approved and print/export affordances.
- [ ] Resource library search/filter/detail/edit/delete flows.
- [ ] Conversation history/session affordances and evidence presentation.
- [ ] Onboarding for first child and optional local-model setup.
- [x] Consistent confirmation dialogs instead of browser `window.confirm` for destructive backup import/restore operations.

## Definition of done

A non-developer can install GrowWise, create/select a child, record an observation, inspect growth context, search records, run an activity, generate and parent-review a material, print an approved material, manage resources, back up/restore data, and continue using deterministic core functionality while the LLM provider is unavailable. No required workflow should depend on understanding Core/sidecar implementation terminology.
