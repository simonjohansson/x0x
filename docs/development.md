# Development and qualification

Reference-driven 808 and 909 kick engines for Digitakt, Digitone and Digitone II.
Both engines run in handwritten ColdFire and SHARC ASM. C handles native control
frames and per-voice dispatch. The superseded circuit engines and fitters are removed.

| Device | Stock OS | DSP | Saved machine ID |
| --- | --- | --- | --- |
| Digitakt mk1 | 1.54 | ColdFire ASM | 20 |
| Digitone mk1 | 1.44 | ColdFire ASM | 20 |
| Digitone II | 1.12 | SHARC ASM | 20 |

`TNTUN`, `DECAY`, `ATTK` and `MODEL` retain their saved slots, ranges and defaults.
MODEL selects 808 below native value 16384 and 909 at or above it. Selection latches on
START. The 808 latches Tone/Decay; the 909 latches Tune/Attack/Decay. Changes take
effect on the next hit. Each callback writes 32 mono samples at 48 kHz. Stock
velocity, envelopes, filters, mixing and voice allocation belong to the SDK.

Conditional TONE/TUNE labels, hiding ATTACK for 808, and the two-position MODEL
selector are deferred to [Elekloader #109](https://github.com/simonjohansson/elekloader/issues/109).
The current page keeps the labels and numeric selector described above. Digitakt
and Digitone sounds saved with the former machine ID 80 must select X0X again
and be saved with ID 20; there is no automatic project migration.

## Build and test

Runtimes are managed with mise. The tested development environment is macOS
with Homebrew `m68k-elf-gcc` and `m68k-elf-binutils` installed. Bootstrap builds
both the patched ColdFire emulator and the firmware-free native SHARC library.
 Stock inputs stay local; see
[firmware/README.md](../firmware/README.md) for filenames and checksums.

```sh
mise install
mise run bootstrap
mise run firmware:dt
mise run firmware:dn
mise run firmware:dn2
mise run test
mise run test:dt:mod
mise run test:dn:mod
```

Normal packages are `out/{dt,dn,dn2}/x0x.syx`, with build receipts, link maps and
`.elemod` dependencies alongside them. Builds verify both frozen model sources
and generate target tables; the capture archives are unnecessary for building.

Tests execute actual ASM, compare ColdFire output and state with independent
integer specifications, and check START/latches, model transitions, independent
slots, invalid controls, bounded writes, ABI/EMAC preservation and native C
adapters. The full-OS emulator tasks exercise the normal 808 path; both-model
adapter and DSP boundary checks are separate component tests. JIT execution
requires executable memory. No physical-device result is implied by these tests.

## Frozen models and historical qualification

- [models/808.npz](../models/808.npz): frozen 808 field and Tone law, 9,179 bytes.
- [models/909.npz](../models/909.npz): frozen 909 phase, envelope and joint onset
  fields, 19,305 bytes. [models/909.json](../models/909.json) records capture hashes,
  fitting partitions, equations and full host metrics.

The following full-cohort metrics are historical evidence from the
[combined-engine integration](https://github.com/simonjohansson/x0x/commit/04eff0ed65699e7addc403c992d6f05e46374267).
They do not qualify subsequent source changes. The 909 source corpus contains 384 isolated-knob positions and 4,096 joint
positions. Both ASM targets render all 721 withheld settings against 724 raw
recordings, plus eight corners and two fractional cases. Whole-waveform error is
about 2.53% median, 3.91% p95 and 7.02% worst; worst error after 10 ms is 4.94%.
Maximum port differences from the frozen model are 6.56e-6 DSP FS for SHARC and
1.16e-6 for ColdFire. ColdFire matches its integer oracle sample and state exactly.
These unaligned waveform metrics include model error and source variation;
audibility and independent fresh-source acceptance remain separate.

SHARC has a 6,144-byte private code budget and 44,396 initialized data bytes,
with 512 bytes per voice. Read the current code size from `out/dn2/build.json`
(`model.code_bytes`); the XP03 historical build used 5,046 bytes. Tables and sixteen allocated states use 52,592 of the
56,320 private data bytes inside the pinned 64 KiB SDK owner. ColdFire uses
125,700 table bytes and a shared 1,412-byte tagged voice state; the normal DT
package leaves about 102 KiB of DDR free. Audio loops are ASM; host C references
are never linked into firmware.

Full source/render evidence remains local in `research/reference/808-fit-model/`,
`research/reference/909-fit-model/` and `out/909-model/qualification/`. The current
909 report is `research/reference/909-fit-model/model-report.html`. Native rendered
WAVs retain DSP gain; divide by four to match the capture track's 0.25 gain. No
per-hit alignment or gain fitting is applied.

The frozen 909 protocol is tracked in `tests/fixtures/909-model/events.csv`.
The large source recordings remain local. Use the shared pinned environment:

```sh
mise run research:909:fit
mise run research:909:sharc-model
mise run research:909:coldfire-model
mise run research:909:report
```

Fitting writes a candidate under `out/909-model/host/` and verifies it against the
frozen decoder; it does not replace the tracked coefficient source. Qualification
keeps each run under `out/909-model/qualification/{sharc,coldfire}/runs/` and
atomically publishes the latest completed receipt. Failed runs remain available
for investigation. Report generation rejects changed artifacts and historical
source inputs; rerun both targets after changing inputs. The pinned corpus is a
fitting holdout, not independent fresh-source or perceptual acceptance.

For another command, `mise run python -- -m x0x.MODULE ...` supplies the same
Python and numeric-library versions used by builds and tests. The complete
stock-free test task fails if a required check is skipped. CI runs this task
without stock firmware; native firmware smokes still require the local images.

Current integration and evidence are tracked in
[#94](https://github.com/simonjohansson/x0x/issues/94) and parent
[#82](https://github.com/simonjohansson/x0x/issues/82). Physical ColdFire acceptance
awaits a device. DN2 diagnostic work uses the matched client in the
[remote-control runbook](dn2-remote-control.md); verify its checkout before use.

The historical XP03 interim DN2 fix was verified for both models with sixteen native slots
across one/two kick tracks: each new kick chokes older hits on its own track
with a 128-sample fade, then retires their synthesis. Normal-DSP XP03 was
installed and byte-verified during that qualification. Dual/mixed-model, live-control and held-stock-track
USB tests pass; the user also heard the diagnostic build clean through the
Digitone outputs/headphones. That historical run passed 76 host tests; current results belong to the
current test task/CI and issue #96. This intentionally changes
closely spaced kick overlap; it does not restrict the native voice pool to one.
Preserving overlapping tails efficiently is tracked in [#95](https://github.com/simonjohansson/x0x/issues/95).
The [live investigation](dn2-live-artifacts.md) separates the confirmed
overload from the buffer-handoff fault, records the original-image A/B,
sixteen-slot qualification and remaining broader device/fidelity checks.
Matched fresh-project measurements put stock-DSP all-FM playback at about
414k handler cycles, versus 420k with x0x installed but unused, 439k with one
808 plus fifteen FM tracks, and 444k with one 909 plus fifteen FM tracks.
These are handler averages, not total DSP utilization.
The exact low-level handoff owner remains unproven; this fix prevents the
tested kick workload from accumulating over-budget synthesis work.
