# Desktop components

Feature components own presentation and accessibility semantics while `App.tsx` is incrementally reduced to orchestration/state.

`MaterialWorkspace` is the first productized vertical slice. It consumes the existing typed IPC controller operations and enforces the parent-review presentation boundary: draft/review/revision material stays in the review lane, only approved material receives print/PDF affordances, and rejected/archived material is de-emphasized.

Do not introduce Core implementation terminology into primary user copy. Deterministic Core functionality must remain visibly usable when optional AI providers are unavailable.
