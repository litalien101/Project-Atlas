# Browser Client and UI TODOs

Scope: authored browser JavaScript, HTML, CSS, and web tests. The browser
test suite passed 20/20 in the audit pass; the missing items below are primarily
browser integration, behavior-claim, accessibility, and responsive-UI gaps.
`web/game.js` is generated output and is intentionally excluded.

These findings are not prerequisites for the offline CPU character-mesh
builder, except where they affect the Recipe Studio build/preview workflow.
Prioritize connection feedback and two-player rendering according to whether
the browser prototype is an active user-facing goal; defer broad mobile and
visual-polish work until the target devices and release scope are set.
P1/P2 tags below describe the finding's relative severity within the browser
surface, not a dependency order relative to the first character mesh.

## Priority fixes

### [`web/app.js`](../../web/app.js) and [`web/index.html`](../../web/index.html)

- **P1 — Show the connection failure/retry UI on initial failure and later
  snapshot-poll failures.** The initial connection path can fail while the
  retry overlay remains hidden.
  **Accept when:** first-load offline, server restart, transient API error, and
  successful recovery all yield visible, accurate status and a usable retry
  path in a browser-flow test.
- **P1 — Reconcile two-seat server behavior with player rendering.** The
  browser does not render a remote traveler despite the local two-player spec.
  Implement the supported remote traveler presentation or explicitly reduce
  the supported claim and contract.
  **Accept when:** two clients can join, each sees the other's authoritative
  state, and disconnect/reconnect behavior is tested.
- **P2 — Make appearance controls truthful without a registered model.** Do not
  imply that an appearance choice is visually applied when no runtime model is
  registered.
  **Accept when:** unsupported choices are disabled or clearly labelled as
  saved-only; future appearance rendering is verified against registered
  assets.

### [`web/input/input_manager.js`](../../web/input/input_manager.js)

- **P2 — Preserve Space activation for focused interactive controls.** Avoid
  suppressing the browser's expected button/control activation.
  **Accept when:** keyboard focus and Space/Enter behavior works on buttons and
  gameplay input does not trigger while a form control is focused.

### [`web/studio.html`](../../web/studio.html)

- **Workflow-specific — Resolve or clearly disable the missing Studio client.**
  The separate game Studio page references `/studio.js`, but no authored
  module was found at that path in the audited surfaces. Wire controls to the
  documented APIs or mark unavailable controls explicitly. This is not the
  local character Recipe Studio and is not required for the first mesh.
  **Accept when:** the page has no failed script request, each enabled control
  performs its documented operation, and review is not represented as
  automatic approval.

## Per-file disposition

### JavaScript

- [`web/app.js`](../../web/app.js) — P1 connection recovery, remote-player
  rendering/claim alignment, and truthful appearance controls above. Add
  browser-flow coverage for those states.
- [`web/network.js`](../../web/network.js) — No specific defect found in this
  pass. Movement, retry, buffering, and collision helpers have focused unit
  tests. Add client integration tests that exercise these helpers through
  actual browser requests.
- [`web/model_loader.js`](../../web/model_loader.js) — No specific defect found
  in this pass. URL validation, deduplication, cloning, and retry behavior are
  tested. Add browser-level loading coverage when an approved model is
  registered.
- [`web/input/input_manager.js`](../../web/input/input_manager.js) — P2
  focused-interactive Space behavior above; add keyboard/focus tests.
- [`web/camera/third_person_camera.js`](../../web/camera/third_person_camera.js)
  — No specific defect found in this pass. Add settings-persistence and
  input-to-camera tests; touch look is not supported by the current input path.
- [`web/animation/character_animation_controller.js`](../../web/animation/character_animation_controller.js)
  — No specific defect found in this pass. Add animation-state/crossfade tests
  when a runtime character asset exists.
- [`web/animation/retarget.js`](../../web/animation/retarget.js) — No specific
  defect found in this pass. Add rest-pose transfer, root-track omission, and
  incompatible-rig tests before enabling retargeting.
- [`web/animation/mixamo_animation_loader.js`](../../web/animation/mixamo_animation_loader.js)
  — No specific defect found in this pass. Keep dormant until compatible,
  redistribution-cleared animations are registered; add loader and skeleton
  validation tests then.

### HTML and CSS

- [`web/index.html`](../../web/index.html) — P2 clarify/disable appearance
  controls without a registered model; add automated accessibility and browser
  interaction checks.
- [`web/studio.html`](../../web/studio.html) — P1 resolve missing script and
  accurately gate/document controls above; add Studio workflow tests.
- [`web/styles.css`](../../web/styles.css) — Add touch camera controls or a
  clear mobile fallback and honor reduced-motion preferences. Add viewport and
  visual regression coverage.
- [`web/atlas-hud.css`](../../web/atlas-hud.css) — No specific defect found in
  this pass. Validate narrow/mobile layout and contrast against visual
  direction.
- [`web/atlas-panels.css`](../../web/atlas-panels.css) — Extend visible
  keyboard-focus styling consistently; add keyboard-navigation and
  accessibility tests.
- [`web/studio.css`](../../web/studio.css) — Validate responsive layout and
  focus visibility when Studio interactions are wired; add visual/accessibility
  checks.

### Tests

- [`web/tests/network.test.mjs`](../../web/tests/network.test.mjs) — Preserve
  current unit coverage; add browser integration cases for connection recovery,
  snapshot-poll failure, and remote-player rendering as implemented.
- [`web/tests/camera.test.mjs`](../../web/tests/camera.test.mjs) — Preserve
  current coverage; add camera settings/input cases when surfaces change.
  Touch-camera behavior needs implementation and tests.
- [`web/tests/model_loader.test.mjs`](../../web/tests/model_loader.test.mjs) —
  No specific test defect found in this pass; current URL safety,
  deduplication/cloning, and retry tests are useful. Real approved-asset browser
  loading remains untested because no model is registered.

## Browser-wide completion criteria

- [ ] Initial and recovered network states have accurate accessible feedback.
- [ ] Supported player count matches server, spec, and visible browser behavior.
- [ ] UI never promises visual effects or assets that are not registered.
- [ ] Keyboard, touch, reduced-motion, narrow viewports, and focus states are
  tested before release.
- [ ] Studio exposes only working operations and binds all review/build
  actions to exact candidate revisions.
