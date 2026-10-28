# 808 lower-interior Decay response

This #9 increment changes one lower-half feedback-control shape on both CPUs,
with the current internal gain retained by human decision. Minimum/default/
maximum Decay, every upper-half value, settled pitch, excitation, Q43, Tone,
output coupling, saved controls and START policy stay fixed. This is an empirical
response correction, not identification of the original VR6 pot or complete
feedback circuit. The preceding fully qualified engine is `9e78ca9`.

For raw Decay below 16384:

```
s = raw / 16384
q = s*s + 1.5*s*s*(1-s)
tau = .0333 + (.143-.0333)*q
retention = exp(-1/(48000*tau))
```

The CPU ports insert this coordinate before their existing tau/damping setup,
reusing all coefficient tables. No additional envelope, output multiplier,
control, saved word or voice-state field is introduced.

## Training result and tradeoffs

One scalar fit starts at the old quadratic law (`k=0`) inside the predeclared
monotone box [-.75, 1.5]. Its objective is raw first-500-ms SSE across all 27
lower-interior settings and their 81 separate recordings. Synthetic recovery,
all-word monotonicity, independent capacitor KCL and accepted CPU baseline
checks precede the fit. Reference routing ×4 and scheduled crop are unchanged;
no gain, timing, phase or DC adjustment is fitted. Held-out audio is unused.

The result reaches the upper boundary: refined SSE 1613.056737→1289.944273.
The outward gradient remains about -72.12, so this is a constrained empirical
choice, not an unconstrained optimum. Exactly representable `k=1.5` produces
bit-identical retention at all 32,513 words to the fitted value one ULP below it.
The box is not extended.

All 27 affected settings improve raw 6/25/150/500-ms and 150–500-ms residuals;
54 minimum/upper settings are exactly unchanged in the same-model screen.
All 27 affected full 12-second host comparisons improve, mean RMS
.00581434→.00519920 FS. These are model/training results, not CPU or native
acceptance. The all-81 first-500-ms mean changes .03904458→.03804007 FS.

Temporal benefit is visible at unchanged gain: at Tone128, first-500-ms energy
90% times change 38.67→46.90 ms against 48.42 ms recorded (Decay32),
59.04→80.38 against 80.33 (64), and 97.83→120.92 against 120.25 (96).
Energy centroids and waveform-direction diagnostics also improve. The engine
still has a substantial amplitude deficit; this does not calibrate it away.

Counterevidence remains: positive and negative peak-slope time-constant
mismatches worsen in all 81 affected takes. Raw 500–1000-ms residuals worsen
at 18/27 settings, 1–2 s at all 27, and 2–12 s at 18/27. At 1–2 s the mean
changes 6.878e-7→1.189e-6 FS. Those regressions are retained even though whole
clips and cumulative energy timing improve. Peak slopes are mixed-stage
descriptors, not qualified quiet-pole measurements; neither descriptor is
redefined as the sole fidelity gate.

## Implementation and qualification

191 tracked host tests pass. An isolated actual ColdFire candidate passes the
existing full static/live/context/EMAC/stack suite, maximum error 7.895e-6 FS,
and 14 composed Tone/C47 checks, maximum 7.965e-6. All five anchor/upper
24,000-sample files remain byte identical to the preceding engine; a separate
actual `k=0` probe matches original output, state and EMAC. Its diagnostic is
1,748 bytes and retains the same stack frame and private state.

SHARC ordinary/component qualification and fresh paired actual-CPU full grids
remain pending. Full-device DT/DN/DN2 scenarios are deferred to the next
integration milestone: this change does not alter C plumbing, registration,
controls, saved formats, voice-state extent, calling conventions or mixing.
The `9e78ca9` full-device results remain prior evidence, not a fresh native pass. The existing .25 FS body,
.5 FS chain, 1e-5 FS backend and 1e-7 refinement bounds remain unchanged.
C/UI code and public/saved interfaces are unchanged; prior evidence is separate.
No broad #9/#79/#2 fidelity gate is closed by this increment. DT #78 remains
deferred and historical DN #20 unresolved. The HTML report and website are not
updated.

Reproducible fit/screen evidence is under `out/808-decay-shape-current/`;
independent review and direct raw recomputation under
`out/808-decay-shape-review/`; fixed-point feasibility and throwaway patches
under `out/808-decay-shape-port-review/`; CPU/native receipts under
`out/808-decay-shape-cpu/`. Precommit component runs retain their exact source/
image provenance; equivalent committed files must be bound explicitly before
reuse. No private candidate is relabeled as a fresh committed execution.
