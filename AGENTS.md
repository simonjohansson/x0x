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
