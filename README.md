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

Start with the [kick-drum research](docs/kick-drum-research.md) and
[implementation plan](docs/implementation-plan.md). The first milestone is one selectable, silent x0x mod in each emulator,
with the MODEL selector, controls, p-locks and LFO targets working. Then add the
808 and 909 in small integrated commits. The plan has eight working issues;
Digitakt II is outside the active scope.

Downloaded source material is kept locally in `research/`. Its two tracked
manifests record how to reconstruct the archive; downloaded files remain
git-ignored.
