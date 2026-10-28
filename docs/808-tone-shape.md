# 808 reference-calibrated Tone curve

This #9/#79 increment corrects the remaining interior Tone control shape after
[the nominal C15 correction](808-tone.md). The RC topology, trapezoidal filter,
5220/220 Ω endpoints, body/Q43 parameters, output gain, live history, START,
saved controls and native interfaces stay unchanged. The preceding fully
qualified engine is [the feedback calibration](808-feedback-calibration.md),
`fb343b5`. This is an effective software-reference control curve, not a
measurement of an original vintage potentiometer.

## Why change the control curve

Recordings at the same Decay share a body and downstream fixed stages. Their
relative Tone transfers therefore test the control curve separately from the
larger body mismatch. All 243 training WAVs and readbacks are retained as 216
nontrivial Tone/bright pairs, with three repetitions separate. The 27 bright
self-pairs are trivial and excluded. Scheduled timing, the actual preceding
prefix sample and documented reference ×4 remain; no gain, delay, phase or DC
parameter is fitted. Held-out recordings remain unused.

For any two trapezoidal RC filters with the same input, their outputs satisfy

```
y_t - y_b + q_t * (y_t-y_t_previous) - q_b * (y_b-y_b_previous) = 0
q = sample_rate * R * C - 1/2
```

With the source bright endpoint fixed at 220 Ω, conditional resistance estimates
are stable across Decays and early/full windows. Relative to the former curve,
Tone 32 needs about 521 Ω less resistance, whereas Tone 223 needs about 41 Ω
more. Changing only its nominal midpoint parameter cannot do both.

A separate matched-Z filter trial was rejected: with the same source priors it
worsens all 216 conditional-transfer pairs. Freely fitting both endpoint RCs
cannot distinguish these filter families: they obey the same identity after
reparameterization. These findings justify a control correction, not a new
filter realization or an assertion about the reference's internal circuitry.

## One shared parameter

Keep the original circuit resistance network and use

```
s = sqrt(tone_raw / 32512)
pot = 10000 * (1-s) / (1+a*s)
R = 220 + 10000 * pot / (10000+pot)
a = 1.3739869594783976
```

One bounded Newton run minimizes the relative-identity squared residual over
all 216 pairs / first 500 ms, with only this scalar free. Known synthetic
parameters recover before the real fit. Starting from the same nominal 15%
midpoint gives a=1.3472101867808715; the fitted objective changes
.447143590670→.439789766976. Its final gradient is −7.50e-15, Jacobian rank one,
and neither bound is active. This conditional objective is not a whole-kick
waveform fit. The fixed bright prior remains a limitation; free-pair estimates
outside the nominal endpoint are not adopted as physical component values.

Every one of the 189 interior Tone pairs improves at each measured window;
27 dark endpoint pairs remain unchanged. Mean causal pair prediction errors:

| Window | Previous RMS FS | Corrected RMS FS |
| --- | --- | --- |
| First 6 ms | .0030329993 | .0009267654 |
| First 25 ms | .0017000610 | .0004571192 |
| First 150 ms | .0008211964 | .0001879490 |
| First 500 ms | .0004767043 | .0001032079 |
| Whole 12 s | .0000978276 | .0000210730 |

## Whole-kick screen and remaining gates

A separate host-stage screen uses the same fresh actual ColdFire bodies from
`fb343b5` for both old and new Tone laws, unchanged C47, all 81 settings and
all 243 training receipts. It compares the first 500 ms, not new CPU output.

| Window | Previous mean RMS FS | Corrected | Improved / regressed / unchanged settings |
| --- | --- | --- | --- |
| First 6 ms | .05868299 | .05849928 | 42 / 21 / 18 |
| First 25 ms | .07359259 | .07359106 | 29 / 34 / 18 |
| First 150 ms | .06107990 | .06107184 | 38 / 25 / 18 |
| First 500 ms | .03936188 | .03935446 | 39 / 24 / 18 |

All endpoints are unchanged in this model screen. Isolated transfer improvement
is substantial, but the absolute full-kick improvement is small and includes
regressions: the body still dominates. The fixed nominal-midpoint sqrt trial
slightly improves whole-kick means more than the relative-transfer fitted
curve, while retaining isolated interior-transfer regressions. The selected
curve targets the independent Tone-control defect, not the best of several
whole-waveform fits.

Implementation and guarded component qualification are complete. Numeric
limits remain unchanged; no full-tail, installed-emulator, held-out or complete
engine-fidelity pass follows from this screen. No HTML or website changes.
The host model passes 191 tracked tests and seven compiled C/UI checks; those
UI checks use fake native boundaries. ColdFire's all-32,513-word actual guarded
coefficient check passes its existing two-Q31-ULP limit (maximum 1.955 ULP),
with exact old endpoint words. Its private Q32 integer-root / 64-bit scalar
calculation preserves the 76-byte frame and audio/state ABI. A cheaper Q24
candidate failed this scalar guard and was not adopted. The new SHARC image
uses 6,008 code / 1,664 state bytes, within the existing private allocation.
ColdFire's full Tone/C47 suites also pass: primitive maximum error 1.12e-8 FS,
composed chain 2.333e-6 FS, with endpoint audio and final state byte identical.
The extra live interior-control sequence passes at 7.46e-9 FS. Its measured
maximum is 2,213 instructions per block including the fixture wrapper; this is
cost evidence, not a real-device deadline qualification. Independent review
finds no source/math integration blocker. SHARC's full ordinary suite passes
16,008 guarded callbacks, with maximum 808 error 8.265e-6 FS under the unchanged
1e-5 bound. Both endpoint files and all twelve stored 909 files remain byte
identical. The suite began on the precommit working tree at `91d913d`; its
generic report records HEAD at completion. Explicit source/model/image binding
to `f59f129` preserves that execution distinction rather than claiming a new
Git-sourced run. The committed image rebuild also matches exactly.
Fresh paired tails/histories and installed-emulator results follow below.
Local source/readback receipts, synthetic proofs and fit trace are under
`out/808-tone-discretization/` and `out/808-tone-sqrt-curve/`; the independent
integrated screen is `out/808-tone-sqrt-screen/fitted/`.


## Paired full tails and installed firmware

Committed `f59f129` is qualified against all 81 settings / 243 separate training
takes / full 12-second tails on both actual CPUs, plus seven full 13/16-second
histories. ColdFire reuses only the source/model/rebuilt-image-proved actual
`fb343b5` bodies and freshly executes Tone/C47. SHARC freshly executes the
entire combined kernel. Both grids retain all 18 endpoint files byte identically;
63 interior files change. The unchanged START policy and visible ceil-to-32
musical scheduling remain. This does not establish faithful retained charge.

| Window | Previous CF mean RMS FS | Current | Improved / regressed / unchanged |
| --- | --- | --- | --- |
| First 6 ms | .05868299 | .05849928 | 42 / 21 / 18 |
| First 25 ms | .07359259 | .07359106 | 29 / 34 / 18 |
| First 150 ms | .06107990 | .06107184 | 38 / 25 / 18 |
| First 500 ms | .03936188 | .03935446 | 39 / 24 / 18 |
| Whole 12 s | .00815222 | .00815064 | 38 / 25 / 18 |

SHARC agrees with these trends. Max oracle errors are 7.351e-6 CF / 8.377e-6
SHARC FS; CPU differences are 8.567e-6 for the grid and 8.535e-6 for histories,
all under the unchanged 1e-5 limit. The means above are per-setting RMS means,
not the relative-identity objective used to calibrate the control curve.
An independent six-setting / 18-take audit recomputes 360 before/after RMS
values at both reported gain conventions within 1.638e-15 FS.

All absolute full-engine regressions remain, despite the improved isolated
control. Listed positions are displayed reference controls, not native words:

| Tone | Regressing Decays, first 150 ms | Regressing Decays, whole 12 s |
| --- | --- | --- |
| 32 | 128, 159 | 128, 159 |
| 64 | 0, 32, 96, 128, 159, 191 | 0, 32, 96, 128, 159 |
| 96 | 0, 32, 64, 96, 128, 159, 191, 223 | 0, 32, 64, 96, 128, 159, 191 |
| 128 | 0, 32, 64, 96, 128, 159, 191, 223 | 0, 32, 64, 96, 128, 159, 191 |
| 159 | 255 | 223, 255 |
| 191 | None | 255 |
| 223 | None | 255 |

The first-500-ms cohort is the whole-tail cohort excluding Tone 223 / Decay
255. All other positions improve or are the unchanged endpoints. Three history
residuals improve and four regress:

| History | Previous CF RMS FS | Current |
| --- | --- | --- |
| Default pair, 50 ms | .01626155 | .01626072 |
| Default pair, 150 ms | .01456417 | .01456497 |
| Default pair, 500 ms | .01057712 | .01057802 |
| Long pair, 50 ms | .02736753 | .02736456 |
| Long pair, 150 ms | .02460064 | .02459799 |
| Long pair, 500 ms | .02159523 | .02159543 |
| Musical | .06288947 | .06289002 |

All three latest-listed firmware builds complete their installed emulator
scenarios. Source archives, firmware and runtime identities are retained:

| Device | Current result | New numeric evidence |
| --- | --- | --- |
| DT | Only deferred #78 reset failures; 53,154 callbacks | Fresh raw callback maximum 7.272e-6 FS over 40,064 samples per interior Decay case |
| DN | Pass; 109,213 callbacks, 71 audible mixed blocks, no observer violations | Fresh raw callback maximum 7.286e-6 FS over 38,304 samples per interior Decay case |
| DN2 | Pass; 42,055 audio / 42,056 DSP frames, no halt/missing/controller error | Added Tone raw 4096/24320 snapshot-continuation capacitor errors 3.842e-8 / 3.992e-8 FS over 576/544 samples |

DT/DN use unchanged observers and scenarios. DN2 preserves every original
check and adds those two interior Tone entries to the existing capture loop;
exact original/expanded function hashes are bound in its receipt. No waits or
limits change. The first sandbox attempt could not create a control socket
before emulation; the identical driver passed with local-socket permission.
All existing control, persistence, locks/LFOs, mixed-model, stock-track and 909
checks retain their scope. Raw callback/state evolution evidence remains
separate from stock-processed PCM and the component/reference grid.

DN's silence checker sees one zero 100 ms window for each dark/bright/909
baseline. This does not prove sixty-window stability or fix historical #20:
`fb343b5` reproduced one count through all sixty windows. Its downstream-cause
qualification remains [separate](dn-silence-residue.md). DT #78 stays deferred.

Final local evidence is under `out/808-tone-shape/`: `analysis/paired-summary.json`,
`full-grid/{measurements.json,history/measurements.json}`, the independent audit,
`coldfire/native-qualification.json`, `native/dn2/qualification.json` and
`review/review.json`. All original fit/guard failures remain preserved. Broad
#9/#79/#2 fidelity gates remain open; no held-out audio, physical devices,
HTML or website changes. This completes this control increment, not the engine.
The consolidated local `final-qualification.json` has SHA256
`817fe9a78666eae66720f24e58e71034a91c8c52adffd092ebd3b067f2bbeaf4`.
