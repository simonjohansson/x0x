# Full 909 training-grid diagnostic

This diagnostic compares the accepted implementation at `65aeaf7` against all
729 Tune/Attack/Decay training settings, with all three fresh takes per setting.
Each recording is cropped only at its scheduled MIDI time (one second), retaining
the complete subsequent 16 seconds. No onset alignment, fitted gain, peak
normalization or held-out selection is applied. The independently audited host
track gain of0.25 is inverted; as-recorded errors are retained alongside it.

The accepted engine implements Tune/Decay and ignores ATTACK.81actual Tune/Decay
renders per CPU are therefore reused transparently across nine reference ATTACK
positions. SHARC receives all nine valid ATTACK words in a separate audio-invariance
check; the ColdFire body ABI has no ATTACK argument and the accepted C callers do
not pass one. This does not establish functional ATTACK delivery or sound controls.

The CPU programs and model/fixture sources come from a frozen accepted Git revision,
not live uncommitted experiments. ColdFire executes the actual kernel using the
pinned Unicorn backend. Its long diagnostic omits only Python instruction-count
and per-store logging, retaining the accepted per-call state/output/stack/register/
EMAC postchecks. A separate preflight compares output, complete state banks and
EMAC snapshots byte-for-byte with the original guarded runner. SHARC executes the
same accepted code through firmware-free Digikit NativeCore, after whole-context
and stored guarded-waveform comparisons. Neither route is installed/native-OS or
physical-device evidence.

All 81 renders execute all 768,000 samples on each CPU. The independent model may use
a documented exact-zero continuation after its passive C8 state is below the base
knee and the trigger is off; this is never described as executed CPU output or
used to omit a real tail. Numeric1e−5FS limits remain separate from reference
fidelity, which is unqualified.

The main artifacts live in ignored `out/reference/909-grid/`: `corpus.json` audits
all metadata, `reference-metrics.jsonl` and `reference-envelopes.npz` retain full-tail
features, backend receipts identify every actual render, and `comparisons.jsonl`
retains every take's raw timing/gain errors. `report.json` ranks whole-waveform,
transient and late-tail gaps and summarizes control-surface trends. Its ATTACK
surface shows the reference's change alongside the accepted engine's zero change.

The seven non-held-out history/musical sequences are a separate diagnostic under
`history/`, with full 17/20 second post-first-trigger tails. They explicitly own one
test voice and replay the existing reset-on-START policy. Events are delivered at
the next 32 sample component boundary; the musical 3.125 second event's 16 sample delay
is declared. Note-offs and velocity are recorded as source context; the standalone
body has no native AMP/GATE path. These results establish neither native allocator
identity nor faithful analog residual-state retriggering.192 held-out takes remain
reserved;44 support WAVs remain capture-integrity controls, not extra fidelity cases.

The HTML report remains unchanged.

## Measured baseline

All 81 renders on each CPU executed16 seconds. Their maximum pair difference is
2.76417e−6FS. ColdFire/model and SHARC/model maxima are 1.76516e−6 and 3.19054e−6 FS,
respectively, within the existing 1e−5 numeric limit. This establishes CPU agreement,
not faithful909sound.

The following errors use the first take and the fixed raw ×4 source correction.
The worst setting is selected by mean full-window error; repeats are not cherry-picked.
Values are RMSE in full scale units.

| Reference Tune/Attack/Decay | CF 16 s | SHARC 16 s | CF first 150 ms | SHARC first 150 ms |
| --- | ---: | ---: | ---: | ---: |
| Default 128/128/128 |0.0123477101|0.0123476915|0.1272803861|0.1272801887|
| Worst 32/255/255 |0.0174472715|0.0174472642|0.1724404748|0.1724404033|

Default reference peak averages0.454889FS across repeats; both CPUs peak at
0.146781FS. Reference body pitch is52.5830Hz versus52.8207Hz for the current
50–200ms body window.99% energy arrives by0.15604s in the reference and0.16938s
in the current engine. These are differences to investigate, not fitted targets.

At default Tune/Decay, reference ATTACK0→255 changes mean first 50 ms energy from
0.00142435565 to 0.00150555633 FS² s and mean peak from 0.233067 to 0.498292 FS.
The accepted implementation produces exactly the same audio at all nine ATTACK
positions. The largest2–16second residual RMS anywhere in the grid is3.78707e−7FS;
the full late samples/DC remain included even when the CPU output is exactly zero.

Of 729 settings, 385 have three sample-identical recordings. The remaining repeat
variation ends by sample 221 (4.6042 ms) after scheduled MIDI. The largest corrected
pair difference is0.155827FS; largest full 16 s pair RMSE is0.000609437FS. At the
default setting, first/second takes differ in 203 samples (9–213), peak difference
0.0780531FS and full 16 s RMSE0.000307716FS. Repeats remain separate; their variable
onset is not treated as an independently captured noise waveform.

The seven history diagnostics agree across CPUs within1.83657e−6 FS. Their largest
full-sequence reference RMSE occurs in the20 second musical sequence:0.03882146FS
(CF) and0.03882141FS (SHARC). They retain the explicit reset-on-START component
policy; this is not native allocation or analog retrigger acceptance.

Prioritize the early waveform/level/trajectory discrepancy using the ATTACK0
surface, then qualify the missing ATTACK path across its nine settings. The
existing isolated pulse/noise experiments must not be substituted for this accepted
baseline: their source/reference mismatch remains unresolved. Long Decay with
low Tune, especially32/255/255, is the strongest full-window regression target.
Keep the held-out corpus reserved while those corrections are developed.

## Regenerate

From the checkout root, after the documented mise/toolchain bootstrap and with the
provided reference tree present. A fresh clone also needs
`(cd vendor/digikit && mise run gen:core)` before the SHARC NativeCore build:

```zsh
grid_revision=65aeaf7
grid_output=out/reference/909-grid

grid_cf=(mise exec -- uv run --frozen --project vendor/digiemu
  --with numpy==2.5.4 --with soundfile==0.14.0
  --python "$(mise which python)" python tools/x0x/reference909_grid.py
  --revision "$grid_revision" --output "$grid_output")
grid_sharc=(mise exec -- uv run --frozen --project vendor/digikit
  --with numpy==2.5.4 --with soundfile==0.14.0
  --python "$(mise which python)" python tools/x0x/reference909_grid.py
  --revision "$grid_revision" --output "$grid_output")

"${grid_cf[@]}" --stage render-coldfire
"${grid_sharc[@]}" --stage render-sharc
"${grid_cf[@]}" --stage references
"${grid_cf[@]}" --stage compare
"${grid_cf[@]}" --stage repeats
"${grid_cf[@]}" --stage history-coldfire
"${grid_sharc[@]}" --stage history-sharc
```

The driver freezes the requested tracked revision, verifies exact clean vendor
pins, rebuilds actual kernels and qualifies the batching path; old ignored output
is not a prerequisite. The SHARC helper uses the existing pinned NativeCore build
under Digikit's benchmark lock. It has no firmware input or stale-library fallback.
`compare` also writes repeat metrics; the repeat-only stage above independently
regenerates their complete three-pair-per-setting artifact.

The driver deliberately accepts only the resolved `65aeaf7` baseline. To compare
a future engine, update the baseline and review its actual render chain and ATTACK
coverage first; reusing81renders is valid only while ATTACK remains unimplemented.

An optional `--frames 4096` render smoke uses a separate output directory.
Comparison always requires all 16 seconds.
Focused metadata/coverage checks run with:

```zsh
mise exec -- env PYTHONPATH=tools python -m unittest discover \
  -s tests/host -p test_reference909_grid.py -v
```
