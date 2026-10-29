# Development and qualification

Reference-driven 808 and 909 kick engines for Digitakt, Digitone and Digitone II.
Both engines run in handwritten ColdFire and SHARC ASM. C handles native control
frames and per-voice dispatch.

| Device | Stock OS | DSP | Saved machine ID |
| --- | --- | --- | --- |
| Digitakt mk1 | 1.54 | ColdFire ASM | 20 |
| Digitone mk1 | 1.44 | ColdFire ASM | 20 |
| Digitone II | 1.12 | SHARC ASM | 20 |

MODEL selects 808 below native value 16384 and 909 at or above it. Selection
latches on START. The 808 latches Tone/Decay; the 909 latches Tune/Attack/Decay.
Changes take effect on the next hit. Each callback writes 32 mono samples at
48 kHz. Stock velocity, envelopes, filters, mixing and voice allocation belong
to the SDK. Controls and user-visible limitations are in the [user guide](../README.md).

On DN2, a new kick fades older kicks on its own track over 128 samples, then
retires their synthesis. Other tracks remain independent and all sixteen native
slots remain available. Preserving overlapping tails is tracked in
[#95](https://github.com/simonjohansson/x0x/issues/95).

## Build and test

Runtimes are managed with mise. The development environment is macOS with
Homebrew `m68k-elf-gcc` and `m68k-elf-binutils` installed. Bootstrap initializes
the pinned dependencies and builds both the patched ColdFire emulator and the
firmware-free native SHARC library. Stock inputs stay local; see
[firmware/README.md](../firmware/README.md) for filenames and checksums.

```sh
mise install
mise run bootstrap
mise run test
```

The stock-free test task executes actual ASM, compares ColdFire output and
state with independent integer specifications, and checks START/latches, model
transitions, independent slots, invalid controls, bounded writes, ABI/EMAC
preservation and native C adapters. It also runs the listening-page controller
checks. JIT execution requires executable memory. CI runs this task without
stock firmware; a skipped required check fails the task.

With the stock images installed locally:

```sh
mise run firmware:dt
mise run firmware:dn
mise run firmware:dn2
mise run test:dt:mod
mise run test:dn:mod
```

Builds create `out/{dt,dn,dn2}/x0x.syx`, with build receipts, link maps and
`.elemod` dependencies alongside them. They verify both frozen model sources
and generate target tables; capture archives are unnecessary for building.

The DT/DN full-OS smokes select 808, 909 at both Attack endpoints, and 808 again
through native panel controls. Each observed sample block and private state is
checked against the independent integer oracle. Each isolated tail finishes
before the next UI edit. These smokes do not establish rapid live editing,
broad polyphony acceptance or physical-device behavior.

## Frozen models and resources

- [models/808.npz](../models/808.npz): quantized body field and shared Tone law.
  `tools/x0x/field808.py` is its fitter and host reference;
  `tools/x0x/tone_factor808.py` supplies Tone fitting and filtering.
- [models/909.npz](../models/909.npz): phase, envelope and joint onset fields.
  `tools/x0x/fit909.py` fits coefficients; `tools/x0x/field909.py` decodes them.
  [models/909.json](../models/909.json) binds the frozen coefficients to their
  capture/partition hashes and records model measurements.

SHARC has a 6,144-byte private code budget, 44,396 initialized table bytes and
512 bytes per voice. Tables and sixteen allocated states use 52,592 of the
56,320 private data bytes inside the pinned 64 KiB SDK owner. ColdFire uses
125,700 table bytes and a shared 1,412-byte tagged voice state. Read actual code
size, linked layout and tool/source identities from a freshly generated
`out/{dt,dn,dn2}/build.json`. Host C references are never linked into firmware.

## Reproduce fitting and source comparisons

Private recordings belong in `research/reference/808-fit-model/` and
`research/reference/909-fit-model/`. The small protocol/partition fixtures are
tracked in [tests/fixtures/808-model](../tests/fixtures/808-model) and
[tests/fixtures/909-model](../tests/fixtures/909-model). Research commands require
the matching recordings and metadata; a fresh clone includes neither recordings
nor generated reports.

```sh
mise run python -- -m x0x.fit808 verify
mise run python -- -m x0x.field808
mise run research:808:sharc-model
mise run research:808:coldfire-model
mise run research:909:fit
mise run research:909:sharc-model
mise run research:909:coldfire-model
mise run research:909:report
```

808 fitting writes a candidate and listening report to `out/808-model/field/`;
its target comparisons write to `out/808-model/{sharc,coldfire}/`. 909 fitting
writes candidates under `out/909-model/host/` and verifies the frozen decoder.
Neither fitter replaces the tracked coefficient source. 909 qualification keeps
each run under `out/909-model/qualification/{sharc,coldfire}/runs/` and atomically
publishes the latest completed receipt. Failed runs remain available for
investigation. The report command verifies both completed target receipts and
writes `research/reference/909-fit-model/model-report.html`; rerun both targets
after changing source inputs.

Use `mise run python -- -m x0x.MODULE ...` for the shared pinned Python/numeric
environment. Qualification receipts identify the gain convention of their
rendered WAVs. DSP-scale output needs a factor of 0.25 to match capture gain;
808 listening material already applies its reported playback gain. No per-hit
alignment or gain fitting is used. Fitting holdouts do not establish independent
fresh-source, listening or physical-device acceptance.

## Remaining acceptance

Combined-engine qualification is tracked in
[#94](https://github.com/simonjohansson/x0x/issues/94) and parent
[#82](https://github.com/simonjohansson/x0x/issues/82). Physical ColdFire,
independent fresh-source and listening acceptance remain open; broader emulator
acceptance is tracked in [#20](https://github.com/simonjohansson/x0x/issues/20).
Conditional TONE/TUNE labels, hiding ATTACK for 808 and a two-position MODEL
selector are tracked in [Elekloader #109](https://github.com/simonjohansson/elekloader/issues/109).
DN2 diagnostic work follows the [remote-control runbook](dn2-remote-control.md).
