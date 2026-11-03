# Observed typography and hierarchy validation

- Observed: 2026-11-03; modified working tree based on `5c92dac76c32a8910dee6461556354c822713d33`.
- Tool: Impeccable 4.8.0, pinned source `9fadc41729c38fd47d7ae622b501558653f9d2e9`; telemetry disabled with `DO_NOT_TRACK=1`.
- Fixture: existing synthetic browser E2E IPC responses rendered by production React. This layout fixture does not use actual Core; the [final14-step journey](live-core-browser-20261103-final.md) does.
- Artifact: [sanitized measurements](design-validation-20261103.json), including raw-report hashes and scope.

The final 1440 × 1000 rendered detector pass used `index-DnarskrO.js` and
`index-D6ORJyIj.css`. All nine default product views returned zero findings in the detector's
`quality` category. Forty-one `nested-cards` style warnings remain across those views. The app's
existing frame and task grouping were deliberately preserved; this is not a zero-warning claim.
The initial dashboard pass had28 functional text findings below11px, while a source-only type scan
had missed them. This difference is why rendered inspection is required.

A separate browser layout probe measured all nine views at1440/1180/820/720px and all nine at430px.
No document-level horizontal overflow appeared. These layout runs used the same typography before
final contrast-only changes;430px is a reduced CSS viewport, not evidence for browser zoom or
assistive technology certification. The scroll-width probe also flagged the notification button's
intentionally overlaid count badge (38px versus34px); the implementation agent visually reviewed
it and retained it. No claim is made that every clipping probe was zero.

The implementation agent inspected all nine top-level views. Independently, the final actual-Core
journey's nine screenshots plus430px materials/settings were inspected. Human-readable Wiki text,
clear section hierarchy, readable record/conversation text and the primary document selector were
visible. Raw screenshot files stay local and contain only synthetic data.

Reproduction used the production browser preview, Chrome DevTools Protocol viewport changes,
`impeccable detect --json --cdp <port>` for each selected workspace, and
`document.documentElement.scrollWidth - innerWidth` for overflow. The operator's temporary harnesses
are not repository entry points; `npm run test:e2e` and `npm run test:live` remain durable regression
commands. This evidence covers default top-level states. Deep tabs and key-form states, other OS
WebViews, all font installations, keyboard/screen-reader behavior and full WCAG certification are
outside its scope.
