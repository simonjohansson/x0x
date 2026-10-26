# x0z

Research toward faithful 808 and 909 kick engines for Digitakt, Digitone and
Digitone II. C handles native controls and device integration; audio rendering
uses ColdFire assembly on Digitakt/Digitone and SHARC+ assembly on Digitone II.
Each instrument has one shared behavioral model and independent reference,
with a separate implementation for each CPU architecture.

The [development guide](docs/development.md) covers mise setup, pinned emulator
dependencies, independent test commands and the latest-only firmware baseline.

Start with the [kick-drum research](docs/kick-drum-research.md) and
[implementation plan](docs/implementation-plan.md). Establish the necessary
interfaces, harnesses and device adapters first, then develop the six
device/engine combinations in small independently testable slices. Digitakt II
is outside the active scope.

Downloaded source material is kept locally in `research/`. Its two tracked
manifests record how to reconstruct the archive; downloaded files remain
git-ignored.
