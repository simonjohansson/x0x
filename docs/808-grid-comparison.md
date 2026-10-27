# Full 808 training-grid diagnostic

This #2 diagnostic compares the accepted 808 algorithm at commit
`65aeaf7a76a55248903f2eec2b464752711defd7` against the available training
recordings. It uses actual ColdFire and SHARC component output, with fixed raw
sample timing and gain. It is not a native firmware capture or a fidelity
acceptance result. The existing HTML report remains unchanged.

The source is the captured Roland TR-808 VST3 1.1.4 build22074 in REAPER7.82
on macOS-arm64, as recorded in the capture handover. It is software-reference
evidence, not a measurement of an original physical TR-808.

## Scope and checks

| Corpus | Coverage | Compared duration after the first scheduled note |
| --- | --- | --- |
| Training grid | 81 Tone/Decay settings, all three fresh repetitions: 243 WAVs | Full 12 seconds per setting and CPU |
| History diagnostic | Six repeated-note pairs and one musical sequence, each on a declared single component voice | Full 13 seconds for pairs; 16 seconds for the musical sequence |
| Held out | 16 settings, three repetitions: 48 WAVs | Unused; acceptance criteria remain open |

The grid positions are 0, 32, 64, 96, 128, 159, 191, 223 and 255. Each maps to
the nearest existing native UI position, `round(displayed*127/255)*256`.
No interpolated host audio substitutes for a CPU render.

The accepted 808 component has fixed intrinsic pitch and ignores the SDK pitch
word. The SHARC fixture actually delivers pitch15487 and `0xffffffff` in unused
parameter words; those inert values are recorded accurately, rather than
claimed as MIDI-note delivery proof. The reference notes remain note36.

Every selected recording is hash checked against `recordings.csv`. Protocol,
MIDI note 36/velocity 100, 48 kHz float stereo, equal channels, unchanged
before/after control readbacks and fixed source controls are verified. The
13-second grid recordings retain their one-second prefix; comparisons remove
exactly that scheduled prefix, rather than detecting or aligning the onset.
All three training takes at each setting are bit identical. Their individual
receipts and residuals are retained rather than silently selecting one take.

The REAPER project has track gain .25 and master gain 1, with no hardware
output/recording route. The comparison retains as-recorded errors and a
separate reference-times-four error. This is the recorded host routing factor,
not a fitted gain, peak normalization or calibration of the mod's voltage
encoding. No phase, delay or timing fit is performed.

Full-tail raw residuals cover 0–12 seconds, with separate first 6/25/150/500 ms,
first two seconds, and 2–4/4–8/8–12-second windows. Pitch, decay fits and Hann
spectral diagnostics reuse the existing analyzer on the first two seconds;
that feature scope does not truncate the full audio comparison. Pitch windows
need at least three valid cycles and retain the existing amplitude and
crossing/peak-period masks. A computable decay fit is not a circuit-fidelity
claim.

## Frozen actual CPU evidence

The experiment freezes tracked sources, models and fixtures from the accepted
commit under `out/reference/808-grid/accepted-65aeaf7`. This deliberately
excludes the simultaneous private SHARC relocation and unadopted DSP
prototypes. The accepted combined SHARC kernel is 5,672 bytes, with 1,664 bytes
of state at the old private address `0x20092000`.

The emulator/tooling pins are digiemu `f57c2f237e84`, Digikit `a28817d61c06`
and Elekloader `b893c9317936`. Full hashes, source inventories, executable
hashes, runtime receipts and driver hashes are preserved with the results.

The original full ColdFire experiment and the tracked 808 reproduction driver
both use the normal Runner constructors, retaining both instruction-count and
write logging hooks. The optional shared fast ColdFire constructor is used by
the separate 909 grid, not this 808 path. ColdFire renders the actual accepted
body, Tone and C47 kernels with the normal per-call output/state/stack/register/EMAC checks and write ownership
instrumentation. The body ABI has no Tone input, so nine actual full-tail body
streams feed independently initialized Tone/C47 stages for all 81 settings.
Six independently replayed fresh composed prefixes match the cached-stage
outputs bit for bit. Each full composed output is also checked against the
independent accepted oracle at the unchanged `1e-5` FS bound.

SHARC executes the same immutable accepted instructions through Digikit's
firmware-free NativeCore. Its separate fast-path proof compares four complete
architectural/context cases and twelve stored guarded audio cases against the
accepted instruction fixture, with byte-identical audio. Long renders retain
callback return/trap and output/state boundary checks, and independently check
each full waveform against the accepted oracle at `1e-5` FS. They do not claim
full per-instruction ownership instrumentation for every long callback.

## History evidence boundary

The seven explicit timelines are replayed on one declared component voice,
with the accepted START policy clearing body, Tone and C47 state. This is not
an inferred native allocator identity or proof of faithful residual circuit
state. Note-off does not gate this intrinsic 808 component, and native AMP,
velocity, filters and track level are outside this diagnostic.

START is delivered at the first 32-sample block boundary at or after each
scheduled note. The pairs land exactly on boundaries. The musical event at
3.125 seconds is delivered 16 samples later; this remains visible in the
receipt and is not removed by onset alignment. Each history keeps its own
full protocol duration. An initial trial that incorrectly retained Tone/C47
state on START is preserved separately and excluded from the current-mod
baseline.

## Results and next priorities

All 81 full-tail renders pass the unchanged independent `1e-5` FS bound on
both CPUs. Maximum oracle errors are **3.626e-6 FS ColdFire** and **3.947e-6 FS
SHARC**; the maximum paired CPU difference is **5.226e-6 FS**. Rendering took
954.45 seconds on ColdFire and 437.51 seconds on SHARC in this experiment.
These numerical checks establish implementation agreement, not reference fidelity.

The largest twelve-second RMS residual is the bright/maximum-Decay setting:
**.02060084 FS ColdFire / .02060119 FS SHARC** against reference times four.
At Tone128 the default is .00844466 FS and minimum Decay .00187480 FS. Mean
error across Tone rises from .001810 FS at minimum Decay to .020515 FS at
maximum Decay. This does not establish that a global gain adjustment is right.

The full surface exposes the provisional Decay mapping between its three
anchors. Positive-peak decay fits below use the same first-two-second analyzer;
they are descriptive audio fits, not physical capacitor time constants.

| Decay display, Tone128 | Reference fit, ms | Current ColdFire fit, ms |
| --- | ---: | ---: |
| 0 | 29.16 | 35.63 |
| 32 | 34.50 | 42.13 |
| 64 | 71.34 | 54.20 |
| 96 | 102.89 | 78.40 |
| 128 | 143.01 | 142.92 |
| 159 | 187.67 | 167.17 |
| 191 | 240.68 | 204.11 |
| 223 | 300.95 | 261.95 |
| 255 | 365.96 | 365.43 |

The default and long anchors agree in duration while much of the middle
surface decays too quickly; display32 instead decays too slowly. Corner-only
checks concealed this. The accepted source/feedback/VR6 control work in
#9/#79 should address this surface, with the full grid retained as its regression.

Maximum Decay still has too much late pitch sigh: at Tone128 the reliable
150–300 ms frequency is **49.7220 Hz current versus 47.7789 Hz reference**.
The quiet .5–2-second values are **47.6500 versus 47.6532 Hz**. Retuning the
settled pole would address the wrong part of this measured difference. Only
32.9% of that setting's waveform-error energy lies in the first150 ms, versus
79.1% at the default. Both the attack and continuing long-body evolution matter.

The onset/peak gap also remains: reference/current Tone128 peaks are
.30855/.23241 FS at the default and .31872/.23633 FS at maximum Decay.
Source-supported excitation, loading and feedback corrections still need to
explain this; no fitted amplitude or unadopted feedback/saturation prototype
is substituted here.

All seven corrected component histories pass the cross-CPU `1e-5` FS check,
with maximum difference **5.190e-6 FS**. ColdFire/reference-times-four RMS errors
are .01711/.01500/.01130 FS for default-Decay 50/150/500 ms pairs,
.03125/.02980/.03083 FS for maximum-Decay pairs, and **.07372 FS** for the musical
sequence. These support the existing residual-state/retrigger workstream, with
the declared-voice and block scheduling limits above. They do not prove native
allocation equivalence or a complete musical acceptance gate.

The next useful 808 fixes remain within #9/#79: the feedback/Decay control
surface and amplitude-dependent body evolution, then source-supported early
excitation/output and residual-state retrigger behavior. No held-out or broad
fidelity gate is marked complete by this diagnostic.

## Artifacts and reproduction

Ignored evidence is under `out/reference/808-grid/`: `frozen.json`,
`source-inventory.json`, `reference-validation.json`, the frozen source tree,
actual `coldfire/` and `sharc/` render receipts/audio, full `measurements.json`,
and the separately labeled `history/measurements.json`. The original guarded
component suites remain separate evidence. Render drivers and their hashes
are retained alongside these artifacts.

The tracked bootstrap archives the accepted sources if needed, verifies their
tracked DSP/model/fixture bytes and exact clean vendor gitlinks, and starts a
child process with those archived modules first on `PYTHONPATH`. Current source
edits therefore cannot silently enter an accepted-revision render. It rebuilds
ColdFire through the existing guarded component suites. The SHARC support
builds/checks the standard firmware-free library under Digikit's bench lock,
freezes its executable/runtime receipts and proves the fast path before use;
there is no stale-library or runtime override.

After restoring the reference recordings and installing the pinned dependencies,
the command chain below regenerates both raw grids, the seven declared-voice
histories and their JSON measurements. `mise run bootstrap` initializes the
existing emulator/toolchain dependencies. The existing Digikit `gen:core` task
then generates the strict firmware-free shared core required by the library
builder. Run that setup before rendering jobs; do not regenerate the core while
a comparison or library build is running. The normal uv commands may download
missing cached Python packages on a new computer; the recorded experiment used
the same versions with `--offline`.

```sh
mise install
mise run bootstrap
(cd vendor/digikit && mise run gen:core)
mise exec -- env PYTHONPATH=tools uv run --frozen --project vendor/digiemu \
  --python "$(mise which python)" python -m x0x.reference808_grid --backend coldfire
mise exec -- env PYTHONPATH=tools uv run --frozen --project vendor/digikit \
  --python "$(mise which python)" python -m x0x.reference808_grid --backend sharc
mise exec -- env PYTHONPATH=tools uv run --frozen --project vendor/digiemu \
  --python "$(mise which python)" --with numpy==2.5.4 --with soundfile==0.14.0 \
  python -m x0x.reference808_grid
```

These commands default to the original `65aeaf7` baseline. For a later committed
808 correction, pass `--revision <commit>` and a separate `--output` directory
to every render/comparison command. Render and history receipts must match that
resolved revision; failed numeric receipts are rejected. `--frozen-source` can
select its archive location; otherwise it is derived from output/revision.
Review the body/Tone/C47 chain and START policy when adopting a new revision;
the renderer does not infer new engine semantics from a Git hash.
The initial full experiment retains its original executed drivers and hashes.
The tracked reproduction bootstrap was checked separately with fresh ColdFire
component builds and all 81 setting prefixes (4,096 samples each), byte identical
to those completed full-tail renders. Packaging checks do not replace or relabel
the original full-tail receipts.

The runner rejects incomplete/duplicate grids, incorrect native mappings,
changed input hashes and mismatched accepted revisions. Its focused host tests
cover training-only selection, duplicate/wrong-repeat rejection, sparse pitch
reliability and the full twelve-second tail scope. Physical-device evidence,
held-out acceptance and changes to the HTML report are outside this increment.
