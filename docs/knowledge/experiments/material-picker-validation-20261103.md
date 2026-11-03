# Material selector refinement — 2026-11-03

The actual production material selector still inherited the metadata font size and a compact native
control height. Its CSS now uses the existing 14px control token, a 44px minimum height, and the same
padding, surface, border and radius as neighboring controls. Labels, selection behavior and stored
materials are unchanged.

After a fresh production build, the actual authenticated Core/browser journey passed all 21 asserted
steps with AI disabled and synthetic data. It switches between two saved documents in both
directions, generates a real PDF, verifies child isolation and original photo preservation, and
checks selected-record export and backup/restore. Only the native IPC transport is replaced by the
browser test adapter; this is separate from native Windows verification.

The resulting material-selector screenshot was inspected at 1440×1000. The control is visibly
consistent with the surrounding form, and its title and neighboring action remain readable. This
small refinement did not include a new responsive or long-content sweep. The Impeccable source
detector reported no finding; that result does not replace the screenshot review.

The [portable report](material-picker-validation-20261103.json) preserves all asserted steps,
native CSP, script/Core/metrics fingerprints, production asset hashes, CSS source hash and the
reviewed screenshot hash. Its temporary output path is removed. Screenshots and synthetic PDFs
remain local. This run requested no memory soak; the earlier RSS experiment and later Linux
diagnosis are separate evidence.
