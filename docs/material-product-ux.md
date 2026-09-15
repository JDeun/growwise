# Material product UX invariants

The desktop material workflow mirrors Core/API/IPC state rather than inventing a second lifecycle.

1. Generation remains available through deterministic templates when the optional LLM is unavailable.
2. Parent Review is a visible lane, not a hidden status field.
3. Draft, review-pending, and revision-requested material cannot expose print/PDF actions.
4. Only `approved` material is presented as ready to use.
5. Revision and direct parent editing create immutable successors through existing IPC commands.
6. Selected resource provenance is shown with human-readable titles during review.
7. Rejected/archived material remains recoverable but visually de-emphasized.
8. Busy state disables duplicate mutations and errors are announced with `role=alert`.
