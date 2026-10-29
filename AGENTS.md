# Repository instructions

## Git

- Write commit messages that conform to Tim Pope's standards.
- Don't add emojis to commit messages.
- NEVER use `git -C <path>`. Run Git commands from the correct working directory.
- When working on a feature branch, use `git worktree add` instead of `git checkout -b`.

## Environment

- Prefer `rg` over `grep`.
- Prefer `fd` over `find`.
- Always manage language runtimes with `mise`.

## Working preferences

- When asked to follow an existing pattern, inspect that pattern first and mirror its boundaries closely.
- Keep changes strictly scoped to the explicit request; do not expand into adjacent systems, public contracts, generated artifacts, or secondary workflows without confirmation.
- If instructions are ambiguous or appear to conflict, stop and ask before implementing.
- Treat established public/stable boundaries as off-limits unless explicitly asked to change them.
- When corrected, pause, reassess, and reduce the diff instead of immediately trying a new design.
- Before changing generated files, schemas, APIs, persisted formats, or other broad-impact artifacts, explain why it is necessary and wait for confirmation.

## Keep issues and documentation current

- Update the issues being worked on at each meaningful increment and before handing work back: record current status, completed acceptance checks, validation evidence, remaining work and blockers.
- Keep affected documentation and roadmap issues in sync with the implementation and issue status in the same increment. Remove stale instructions that describe completed work as pending.
- When work is deferred or moved to a follow-up issue, link that issue and update the original issue, plan and affected docs. A deferred or untested check is not a passing check.
- Distinguish host, component, emulator and physical-device evidence. Preserve historical evidence with an explicit historical label and a link to the current status.

## Documentation boundaries

- Keep `README.md` focused on using x0x: supported devices/OS, obtaining and
  installing a build, selecting the machine, controls and audible limitations.
  Link developer setup, model internals, measurements and investigations from
  `docs/`; do not append progress logs, addresses or build receipts to the README.
- Keep one current status per topic. Mark superseded evidence as historical,
  link its exact revision, and remove contradictory current instructions from
  linked docs and roadmap issues. Check links when moving or deleting docs.
- Keep reusable rules here and detailed procedures in linked runbooks. A dated
  local path, firmware version or test result is evidence to recheck, not a
  permanent environment guarantee.

## Implementation and verification

- Follow the existing device/target boundaries; keep host modelling, build
  and qualification tools in `tools/x0x/`. Read each device's actual call path
  before sharing adapter or manifest code; similar layouts do not establish
  interchangeable device contracts.
- Reuse the existing build, validation and report helpers. When retiring an
  implementation, search callers, manifests and test runners for orphaned
  headers, fixtures and tests; retain independent reference oracles in use.
- Verify that each required test is reached by a documented mise task. A test
  file that is never invoked provides no regression coverage. Report skipped
  prerequisites explicitly; required acceptance checks must not silently pass.
- Follow the existing 808 fixture pattern for small protocol/partition checks
  that can run without private recordings; keep large capture archives local.
- Test the changed path at its real boundary. Component DSP checks do not
  establish native MODEL/ATTACK routing, save/reload behavior or device audio.
- For DSP performance work, check START, interval boundaries, body, tail and
  retirement at relevant control extremes, plus the intended concurrent-track
  workload. Track maximum work as well as typical work; instruction counts,
  measured handler cycles and total DSP utilization are different evidence.

## Evidence integrity

- Reject non-finite audio and metrics before comparisons or success reports;
  use strict JSON output for numerical receipts. Test an invalid result as
  well as a passing result when changing a qualification gate.
- Preserve completed evidence when rerunning a long job. Publish new outputs
  and their success receipt together only after checks complete; an interrupted
  run must not leave old passing metrics attached to new or partial artifacts.
- Verify artifact hashes when consuming receipts. Bind results to the actual
  source, model, toolchain and dependency inputs; label older-source evidence
  as historical instead of presenting it as qualification of the current build.
- A dependency's commit ID alone does not establish a clean pinned build.
  Check the checkout and imported tool path used, including the matched client
  for live readback. Reuse existing revision/cleanliness checks where available.
  Use the same selected checkout/toolchain throughout build and readback.
- Keep fixed gain, timing, cohort partitions and acceptance criteria explicit.
  Preserve failed acquisitions and regressions; fitting holdouts and emulator
  agreement do not establish fresh-source or listening acceptance.

## Physical-device work

- Follow the current request's authorization; prior installations and this
  notebook do not authorize flashing, project writes or a new device test.
- Read the [DN2 remote-control runbook](docs/dn2-remote-control.md) before DN2
  work. Reuse one MIDI port/session per batch and verify state at meaningful
  boundaries; key delivery is not proof of a completed load, save or update.
- Preserve user projects. Do not overwrite slot 002 (`DNII M1_FINAL`). The
  2026-10-29 setup used slot 006 for the user's SP copy and slot 007 for a
  pristine all-FM baseline; recheck their identity before using them. Never
  save an x0x scenario over the pristine baseline or replace its temporary
  pattern snapshot with a modified scenario.
