# 808 continuing pitch: measured cause and rejected corrections

This preserves the investigation at the separate [Tone correction](808-tone.md),
`3c3db81`, whose body was unchanged from `853bb77`. The later
[effective feedback calibration](808-feedback-calibration.md), `fb343b5`,
changes two Q43 coefficients on both CPUs and improves late pitch from
49.72 to 47.65 Hz against 47.78 Hz recorded. Its full paired/native results
supersede the old pending status; the rejected corrections below remain
unadopted. The current [Tone-shape correction](808-tone-shape.md), `f59f129`,
retains that body. The website is cancelled and remains unpublished.

## Cause in the actual CPU output

At maximum Decay, the actual ColdFire body measures 49.7217 Hz over
150–300 ms; after Tone/C47 it measures 49.7220 Hz. Each of the three reference
takes measures 47.7789 Hz. Negative crossings and same-polarity peaks separately
confirm the discrepancy. Quiet tails still agree near 47.65 Hz.

Two fresh guarded CPU traces, default and maximum Decay, produce 192,000
samples byte-identical to the accepted cached bodies. At maximum Decay,
150–300 ms accumulates 0.31891 modal cycles beyond the quiet pole. Evaluating
the model terms along captured states attributes +0.31838 cycles to Q43,
−0.000065 to C39 and zero to the main source; block quadrature leaves a
0.000594-cycle residual. The reconstructed common node continues crossing
Q43's knee until about 416.7 ms.

A separately labelled model counterfactual removes only Q43 after the captured
150 ms state. It then measures approximately 47.65 Hz while retaining C39.
Thus Tone/C47, a late companion pulse and crossing polarity do not explain the
excess. The current sign, modal projection and 6 ms capacitor-state conversion
are internally consistent; this does not establish complete circuit fidelity.

## Candidates left out of production

All comparisons retain the scheduled timing, raw output scale, every training
repetition and the documented reference multiplier ×4. There is no fitted gain,
phase/delay alignment, normalization or held-out audio. A 500 ms screen is not
a full-tail comparison or an emulator qualification.

| Candidate | Evidence | Result and decision |
| --- | --- | --- |
| Published Q43 soft knee, S03 Eq.8, without subtracting its zero-voltage current | All 81 settings / 243 takes / full 12 s; five independent KCL/refinement/equilibrium tests | Mean whole error .00967961→.00990733 FS; 65 settings worsen. Long late pitch 49.7220→49.7678 Hz. Not ported. |
| Fixed 14 V amplifier headroom, fed back into capacitor KCL | All 81 settings / 243 takes / first 500 ms; six numeric tests, unchanged refinement limits | Slight late improvement, 49.7220→49.6051 Hz, but every one of the 54 settings with actual clipping worsens at 25/50/150 ms. Default peak moves farther from the reference. Not ported. |
| Fixed 12 V headroom | Same bounded screen and numeric checks | Every setting worsens in the early raw windows; the lower peak also worsens. Not ported. |
| Fixed 4 V main trigger, all other quantities unchanged | All 81 settings / 243 takes / first 500 ms; source and refinement checks | Long late pitch becomes 47.649 Hz, but every take worsens in every reported raw window. Mean 500 ms error .0460243→.0627967 FS. Not ported or compensated by fitted gain. |
| Finite C39/R161 mutual loading with the physical D52 clamp | All 81 settings / 243 takes / first 500 ms; three independent KCL/refinement tests | Mean 500 ms error improves .0460243→.0445667 FS and long late pitch becomes 49.1784 Hz, but extra loss changes the already calibrated decay. All first-25-ms settings worsen. Not ported. |
| The same C39 loading with analytically de-embedded quiet poles | Separate complete bounded screen; four characteristic/KCL/switch/refinement tests | The full quiet pole and loss remain unchanged without new fitted parameters, but mean 500 ms error worsens to .0463642 FS and long late pitch to 49.7814 Hz. Not ported. |
| Fixed 4 ms switch/C39 event, after the separate C15 Tone correction | All 81 settings / 243 takes / first 500 ms; refinement and source/event review | Every take worsens at 25/150/500 ms. Mean 500 ms error .0459027→.0719778 FS and long late pitch 49.72→51.26 Hz. Not ported. |
| Initial switched-frequency calibration after `fb343b5` | One scalar fit on original five settings / 15 takes / first 150 ms; independent capacitor continuity, synthetic recovery, refinement and 81-setting / 500 ms screen | 131.006→131.475 Hz; five-point SSE improves .438%, but 76/81 first-25-ms settings worsen and default 500 ms worsens. Mean 500 ms improves only .110%. Rejected; production frequency unchanged. |
| Finite Q43 soft knee with current effective lambda/k, after `f59f129` | Fixed source alpha 14.315/V; no fit/zero-current subtraction; independent KCL, equilibrium and 8→16 refinement, all 81 settings / 243 takes / first 500 ms | All 81 first-25-ms settings worsen, 54 first-150-ms settings worsen; mean 500 ms .03935443→.03951943 FS. Rejected, despite numeric checks passing. |
| Same-owned-voice retained circuit state on `f59f129`, after the major Q43 calibration | Seven complete 13/16-second histories, reset/retained at 16 substeps; independent capacitor/continuity tests and unchanged 1e-7 refinement guard | Five histories worsen / two improve; mean RMS .02540739→.03555512 FS (+39.94%), musical .0628900→.0880407. First hits agree; reset model agrees with actual CF within 2.334e-6 FS. Rejected; native owner identity and retained-body headroom remain unqualified. |

The manufacturer specifies about 4 V for an unaccented hardware trigger and
4–14 V with accent. The recordings have Total Accent zero, verified in all
486 training before/after readbacks. This does not establish an electrical
4 V mapping inside the software reference. The current fixed 14 V trigger and
volts-to-digital encoding remain provisional; replacing them independently
does not reproduce the recordings.

Independent schematic-image checks also confirm that C43 is **33 µF**, not
33 nF. Its 1.551–18.051 s feedback-shelf time constant and measured omitted
forcing do not explain the roughly 2 Hz late error. No unchanged nominal
feedback candidate was rerun, and no quiet-pitch retuning was adopted.
S01's approximately 4 ms and S03's approximately 6 ms describe the same Q42/Q43
release/C39 event; the former is not an additional 4 ms after the main trigger.
Neither approximate timing text uniquely calibrates this software reference.

## Next work and evidence limits

The later joint feedback calibration substantially improves late pitch but
retains onset/short-Decay regressions. These tests ruled out isolated
corrections; they do not justify another trigger constant, a fitted pitch
envelope or a relaxed acceptance limit. The separate nominal Tone correction
is qualified; the mutually loaded output candidate also worsened
the measured raw windows and remains unported. Existing #9 retained-state
experiments must distinguish a declared component voice from unproved native
ownership before changing START behavior.

Local reproducible evidence is preserved under `out/808-pitch-sigh-audit/`,
`out/808-soft-leakage/`, `out/808-saturation/`, `out/808-trigger-baseline/`,
`out/808-feedback-audit/` and `out/808-c39-loading/`.
The later timing screen and cache/source binding are under
`out/808-attack-window-4ms/`, `out/808-initial-frequency-screen/` and
`out/808-q43-soft-calibrated/`. The updated same-owner history experiment is
under `out/808-retrigger-model-f59/`; its original failed 8→16 check and the
private helper's exact-6-ms rejection fix remain preserved. All source snapshots,
receipts, failures and rejected outputs remain distinct from accepted audio.
The source/equation checks and model screens are not new native-emulator or
physical-device evidence. Current full-grid and native qualification is the subsequent
[main-pulse timescale correction](808-main-pulse-time.md), `9e78ca9`; feedback
and Tone records retain their historical qualification. #78 and historical #20 remain unresolved,
and broad #9/#79/#2 fidelity gates remain open.


## Subsequent output and upper-Decay diagnostics

On qualified `9e78ca9`, a fixed C49/C50 replacement for the provisional C47
stage was screened separately from earlier additive-output trials. Physical
100/182 division worsens all 243 first-500-ms takes. Unit-HF shape alone
improves 216 and worsens 27 (all minimum Decay), with only .0779% mean
improvement; all 27 minimum-Decay full tails also regress slightly. Later
minimum-Decay tail shape improves, but this conditional replacement omits full
C47/Q44 loading and is not adopted. No poles, gain or timing were fitted.
Evidence: `out/808-output-pair-replacement/`.

A separately validated upper-Decay estimator rejects every one of 135 declared
windows across 45 training takes. An analysis filter magnifies weak
nonfundamental content, invalidating its homogeneous quiet-pole assumption;
independent raw recomputation confirms the result. No rejected estimate is a
usable Decay measurement. This neither justifies changing nor confirms the
existing upper law. Frozen criteria remain unchanged, and no production
correction or further estimator variants follow from this run. Evidence:
`out/808-upper-decay/{validation,reference,review}/`.
