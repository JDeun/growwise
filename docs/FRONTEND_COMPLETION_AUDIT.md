# Desktop completion audit

This audit treats the current React/Tauri desktop as a production user surface, not a demo of Core endpoints.

## Current structural risk

`desktop/src/App.tsx` is a ~46 KB monolith containing connection status, child creation/switching, observations, growth map, search, conversation, resources, material generation/review/editing, activities, infant guidance, backups, and printing. The functionality exists, but the information architecture is effectively one long page. That creates navigation, discoverability, accessibility, state-isolation, and maintainability risk.

## P0 completion batch

- [ ] Introduce persistent workspace navigation: Home, Record, Growth, Activities, Materials, Library, Ask, Settings.
- [ ] Preserve active child context across all workspace views.
- [ ] Add route/view-level empty, loading, and error states instead of relying on one global page flow.
- [ ] Make Core-only/offline capability explicit in the UI; LLM unavailability must not visually disable deterministic features.
- [ ] Move backup/import/restore and runtime diagnostics into Settings.
- [ ] Make Parent Review a first-class Materials workflow, not an inline implementation detail.
- [ ] Provide visible success feedback for writes and destructive-action feedback for restore/import.
- [ ] Audit keyboard focus, landmarks, labels, aria-live errors/status, reduced motion, and contrast.
- [ ] Add narrow-window behavior suitable for common laptop sizes.
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
- [ ] Consistent confirmation dialogs instead of browser `window.confirm` for destructive operations.

## Definition of done

A non-developer can install GrowWise, create/select a child, record an observation, inspect growth context, search records, run an activity, generate and parent-review a material, print an approved material, manage resources, back up/restore data, and continue using deterministic core functionality while the LLM provider is unavailable. No required workflow should depend on understanding Core/sidecar implementation terminology.
