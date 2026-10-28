# x0x

Research toward faithful 808 and 909 kick engines for Digitakt, Digitone and
Digitone II. C handles native controls and device integration; audio rendering
uses ColdFire assembly on Digitakt/Digitone and SHARC+ assembly on Digitone II.
Each instrument has one shared behavioral model and independent reference,
with a separate implementation for each CPU architecture.

**One x0x mod per device contains both the 808 and 909 engines.** A saved
MODEL selector chooses the sound per track/voice, so 808 and 909 tracks can
play concurrently from the same installed mod. Each device has its own build
of that combined mod.

The [development guide](docs/development.md) covers mise setup, pinned emulator
dependencies, independent test commands and the latest-only firmware baseline.

Start with the [architecture](docs/architecture.md),
[kick-drum research](docs/kick-drum-research.md) and
[implementation plan](docs/implementation-plan.md). All three silent milestones
and the supported [808 baseline](docs/808-body.md) are complete. It uses a
47.65 Hz settled body, shaped excitation, live Tone/Decay and output coupling
on both CPUs. Intrinsic circuit accent and retained-state retrigger remain
explicit refinements in #79/#2; current behavior is fixed excitation and reset
on START. Gain stays unchanged. See the [latest Decay evidence](docs/808-decay-shape.md).

The [909](docs/909-body.md) also makes sound in all three emulators, with Tune,
Decay and the [loaded VCA](docs/909-vca.md); Attack and remaining implementation
follow in #25; DN2 shared-noise timing needs
[Elekloader #108](https://github.com/simonjohansson/elekloader/issues/108).
Both engines' circuit/held-out fidelity remains open in #79/#2.
DSP-only changes use actual CPU component/reference checks; full-device runs
cover integration changes and milestones. Prior native evidence stays labelled
as prior. DT reset #78 and historical DN residue #20 remain unresolved;
DN2 MIDI delivery #80 and private capacity #81 are complete. Digitakt II is
outside the active scope.

Downloaded source material is kept locally in `research/`. Its two tracked
manifests record how to reconstruct the archive; downloaded files remain
git-ignored.
