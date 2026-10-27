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
are accepted. The [first 808 body](docs/808-body.md) now makes sound in every
emulator: an uncalibrated 55 Hz decaying sine with live DECAY feedback control
and [Tone](docs/808-tone.md) and [C47 coupling](docs/808-coupling.md) RC stages. The first
[909 triangle body](docs/909-body.md) also makes sound in all three emulators. Both engines
remain provisional; remaining circuit stages follow in #9/#25/#79.
The Digitakt reset bug is deferred to #78. Digitakt II is outside the active scope.
A separate late DN2 MODEL transition is being investigated in #80.

Downloaded source material is kept locally in `research/`. Its two tracked
manifests record how to reconstruct the archive; downloaded files remain
git-ignored.
