# Desktop completion audit

This audit treats the current React/Tauri desktop as a production user surface, not a demo of Core endpoints.

## Current structural risk

`desktop/src/App.tsx` is still a ~46 KB monolith containing connection status, child creation/switching, observations, growth map, search, conversation, resources, material generation/review/editing, activities, infant guidance, backups, and printing. The persistent workspace shell now projects those existing sections into task-oriented views while keeping the same mounted App/controller state, so the previous one-long-page information architecture is no longer the primary user surface. Component isolation and maintainability remain unfinished until the monolith is split without changing Core semantics.

## P0 completion batch

- [x] Introduce persistent workspace navigation: Home, Observations, Growth, Activities, Search, Library, Materials, Settings.
- [x] Preserve active child context across all workspace views (the App remains mounted across workspace changes and the child switcher remains available in child-scoped views).
- [ ] Add route/view-level empty, loading, and error states instead of relying on one global page flow.
- [x] Make Core-only/offline capability explicit in the UI; a persistent capability status explains that deterministic records, search, growth, activities, resource management and Parent Review remain available when AI is unavailable.
- [x] Move backup/import/restore and runtime diagnostics into Settings (the Settings workspace projects system status and data-management surfaces together).
- [x] Make Parent Review a first-class Materials workflow, not an inline implementation detail.
- [ ] Provide visible success feedback for writes. Backup create/export/import/restore now provide in-app status feedback, and destructive import/restore actions use the accessible app confirmation dialog.
- [x] Audit keyboard focus, landmarks, labels, aria-live errors/status, reduced motion, and contrast. Workspace navigation now exposes tablist/tab/tabpanel semantics with roving keyboard focus and a skip link; dialogs trap focus; form errors/status use alert/status semantics; reduced-motion overrides are present; and the primary action/text color was darkened so normal-size white/green combinations clear WCAG AA contrast.
- [x] Add narrow-window behavior suitable for common laptop sizes (workspace navigation and content grids collapse at 900/700/600 px breakpoints, with reduced-width shell spacing on small windows).
- [ ] Break App.tsx into feature components without changing Core semantics.

## P1 product-quality batch

- [ ] Home dashboard with next useful actions and recent records rather than system implementation details.
- [ ] Timeline filters and record detail view.
- [ ] Growth map visual hierarchy and explainability.
- [ ] Activity lifecycle UX: suggested -> active -> completed/skipped -> linked observation.
- [ ] Material queue segmented by draft/review/approved and print/export affordances.
- [ ] Resource library search/filter/detail/edit/delete flows.
- [ ] Conversation history/session affordances and evidence presentation.
- [ ] Onboarding for first child and optional local-model setup.
- [x] Consistent confirmation dialogs instead of browser `window.confirm` for destructive backup import/restore operations.

## Definition of done

A non-developer can install GrowWise, create/select a child, record an observation, inspect growth context, search records, run an activity, generate and parent-review a material, print an approved material, manage resources, back up/restore data, and continue using deterministic core functionality while the LLM provider is unavailable. No required workflow should depend on understanding Core/sidecar implementation terminology.
