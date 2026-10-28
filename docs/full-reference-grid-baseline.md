# Full 808/909 training baseline

The full training comparison is complete for accepted commit `65aeaf7`, before
any further engine changes. The two CPU implementations agree closely with each
other; both still have substantial differences from the recordings. This is a
diagnostic baseline, not a fidelity pass.

This document preserves the `65aeaf7` measurements and the priorities they
identified. The subsequent [lower-half 808 Decay correction](808-decay-lower-half.md)
is qualified at `853bb77`: all 81 settings / 243 takes / 12-second tails and
seven histories are compared on both CPUs. Eighteen settings improve, all nine
Decay32 settings regress, and 54 remain byte identical. The correction record
distinguishes the source/image-bound ColdFire execution from the fresh committed
SHARC run, the fresh host/C/UI/ColdFire test rerun, and installed-emulator
evidence. DT reset #78 and DN residue #20 remain failed; the DN2 run passes.
Those correction results do not replace the historical numbers below or close
fidelity acceptance. The subsequent [nominal 808 C-taper correction](808-tone.md)
is qualified at `3c3db81` on both CPUs and all three emulators. It improves
isolated Tone transfer and mean full-grid error, while retaining seven
first-150-ms and 27 whole-tail interior regressions. Its current DN run passes,
but historical #20 remains unresolved. The subsequent
[effective feedback calibration](808-feedback-calibration.md), `fb343b5`, has
fresh paired full tails/histories and all three native scenarios. Mean whole
error improves 15.62%, all seven histories improve, and 32 settings regress;
DT #78 and reproduced DN #20 failures remain, while DN2 passes. Use that
record for the body correction. Current qualification is the subsequent
[Tone-shape correction](808-tone-shape.md), `f59f129`: every isolated interior
Tone transfer improves, with a small whole-engine mean improvement and all 25
whole-tail / four history regressions retained. All three installed scenarios
complete; DT retains #78 and DN's one-zero-window pass does not fix historical
#20. The tables below preserve `65aeaf7`.

| Engine | Training coverage | Actual CPU output per setting | Main measured gaps |
| --- | --- | --- | --- |
| 808 | 81 Tone/Decay settings, all 243 takes | Full 12-second tails on ColdFire and SHARC | Interior Decay response, amplitude-dependent pitch sigh, onset/peak and retrigger history |
| 909 | 729 Tune/Attack/Decay settings, all 2,187 takes | Full 16-second tails for 81 distinct Tune/Decay settings on each CPU; Attack invariance explicitly checked | Missing Attack response, onset/body level, Tune/Decay surface and retrigger history |

Seven additional histories per engine are compared on a declared single component
voice. They are not native allocator or faithful residual-charge acceptance tests.
The 240 held-out recordings remain unused. The original HTML comparison report
is unchanged. The separate website was cancelled before publication and does
not change this frozen baseline.

## What the measurements say

For the **808**, the default positive-peak decay fit agrees at about 143 ms and
maximum Decay agrees at about 366 ms. Several intermediate settings do not:
display 64 is 54 ms versus 71 ms reference, and display 191 is 204 ms versus
241 ms reference. Display 32 instead decays too slowly, 42 ms versus 35 ms.
Corner-only comparisons missed this shape. At maximum Decay, 150–300 ms pitch
is 49.72 Hz versus 47.78 Hz reference, while quiet settled pitch agrees near
47.65 Hz. Changing the settled pitch again would target the wrong difference.
Default reference/current peaks are .309/.232 FS; the first 150 ms waveform RMS
error is .06719 FS.

For the **909**, changing Attack alters the reference transient at every
Tune/Decay combination and changes current output by exactly zero. At default
Tune/Decay, the reference peak rises from .233 to .498 FS across Attack; the
current peak remains .147 FS. At the default of all three controls, reference
body pitch is 52.583 Hz versus current 52.821 Hz, and 99% energy duration is
156 versus 169 ms. The mean per-take first 150 ms waveform RMS error is .12735 FS.
At Attack 0 it is still .12663 FS: adding Attack alone will not repair the body.
The worst
whole-tail setting is Tune 32 / Attack 255 / Decay 255, rather than a simple corner.
Adding an isolated pulse prototype is not assumed to fix these gaps: that
unadopted candidate previously worsened the measured windows.

These peaks and errors use the independently verified reference track-gain
correction of ×4. Source instrument Level and the mod's internal voltage scale
are not calibrated equivalents. No gain is fitted and no audio is normalized
or onset aligned. Full-tail RMS includes long silence; the 12- and 16-second
whole-window figures are not a meaningful cross-engine quality ranking.
All takes remain separate in the results, including the 909's varying early
transients. Pitch and decay fits are descriptive, with unreliable fits omitted.

## Work identified by this historical baseline

1. **#9/#79: correct the 808 Decay/control surface and continuing pitch sigh.**
   Preserve the already matching settled pitch and rerun the full grid to expose
   regressions between the original five settings. Continue onset/output and
   retained-state work after establishing the body response.
2. **#25/#79: correct the 909 body/transient and complete Attack.**
   First isolate the early body/level/trajectory gap on the Attack 0 surface;
   then qualify the missing pulse/noise path across the measured Attack surface.
   Keep the current failed prototype
   isolated until a combined candidate improves the relevant measurements.
   Private DN2 capacity work is tracked separately in #81.
3. **#2: retain this full baseline for each integrated correction.** Freeze
   justified acceptance criteria before using held-out recordings. Musical
   listening and native modulation/allocation acceptance remain separate gates.

## Evidence and reproduction

The [808 record](808-grid-comparison.md) and [909 record](909-reference-grid.md)
contain regeneration commands, complete methods and detailed findings. Raw
audio, per-take JSON measurements and source/runtime hashes remain ignored under
`out/reference/808-grid/`, `out/reference/909-grid/` and
`out/reference/full-grid-support/`. Tracked drivers regenerate them from the
accepted Git revision and the restored reference corpus.

All 162 unique grid outputs per CPU run actual accepted instructions through
digiemu's ColdFire backend or Digikit's firmware-free SHARC NativeCore. Maximum
cross-CPU differences are 5.226e-6 FS for 808 and 2.764e-6 FS for 909, under the
unchanged numerical 1e-5 FS limit. Independent oracle checks also pass. These
limits qualify implementation agreement, not agreement with the recordings.
An independent audit verified corpus metadata and recomputed 18 selected
boundary/default/worst-case repeat records on both CPUs from full-tail raw audio.

ColdFire is the DSP architecture shared by DT/DN; SHARC serves DN2. This run is
component evidence, not 2,430 new installed-firmware captures. Existing native
regressions remain documented separately, including deferred DT reset #78 and
unresolved DN residue #20. No physical devices were used.
