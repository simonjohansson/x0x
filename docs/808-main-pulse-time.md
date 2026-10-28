# 808 main-pulse timescale calibration

This #9/#79 increment changes the effective C40 main-source time constant on
both CPUs. The nominal R162/R163/C40 identities remain recorded; the model
scales their isolated RC time by one training-calibrated factor. It preserves
trigger amplitude, DC divider/ON equilibrium, 1 ms and 6 ms edges, both poles,
Decay, Q43, Tone/C47, gain, START, state and ABI. The preceding qualified engine
is [the Tone-shape correction](808-tone-shape.md), `f59f129`.

## One effective excitation parameter

```
nominal_tau = (4700 || 100000) * 15 nF = 67.3352435530086 us
tau = nominal_tau * 1.0279664783107476 = 69.21837318138271 us
```

At the fixed resistance this corresponds to about 15.4195 nF, but it is not a
measurement of the software reference's capacitor or a verified hardware lot.
Only the main source's physical evolution changes, not recording onset/delay.
Source advance, exact bridge forcing and ON bias all use the same timescale.

One bounded log-parameter fit uses the original default/four corners, three
separate takes each, first 150 ms and unweighted raw SSE. Scheduled crop and
fixed documented reference multiplier ×4 remain. No gain, phase, delay, DC or
other model parameter is fitted; no held-out audio is read. The declared box is
.75–1.25 times nominal. Synthetic .95-times-nominal recovery passes before the
single real run; no numerical restart or second fit selects this candidate.

The upper-box preflight fails: its body peaks exceed the unchanged .25 FS
bound and its maximum-Decay split error exceeds 1e-5. Those receipts remain
preserved. The fit uses independently validated RK4-8 with body/chain proposal
rejection at .25/.5 FS, retaining the objective and box. Final SSE changes
389.258086210→382.234084479; refined RK4-16 confirms 382.234067421.

**This is a feasible best-seen, body-bound-limited candidate, not a stationary
optimum.** It stops at 30 iterations with 23 body-guard rejections. The final
relative gradient .2069 still wants a larger timescale; the nominal parameter
box is inactive. Refined maximum body output .249997527 FS leaves only
2.473e-6 FS headroom. Neither the bound nor the numeric limits were relaxed.

## Independent model and training screen

All nine Decay settings pass fixed-candidate numerical checks: RK4-8→16 maximum
3.953e-8 FS under 1e-7, split→refined maximum 3.222e-6 FS under 1e-5, and an
independent capacitor/source KCL check. Quiet pitch, control laws and source
edges remain fixed. Reviewer source-channel/target audits retain all original
WAV/RPP hashes, 193 readbacks and repetitions.

The first-500-ms model screen compares all 81 settings / 243 takes against the
qualified actual ColdFire output, with same-model checks confirming every
cumulative-window improvement is larger than baseline quantization effects:

| Window | Previous mean RMS FS | Candidate | Settings improved / regressed |
| --- | --- | --- | --- |
| First 6 ms | .05849928 | .05646960 | 81 / 0 |
| First 25 ms | .07359106 | .07270595 | 81 / 0 |
| First 150 ms | .06107184 | .06060186 | 81 / 0 |
| First 500 ms | .03935446 | .03904458 | 81 / 0 |
| 150–500 ms | .02215694 | .02197746 | 72 / 9 |

The nine late-window regressions are every Tone at minimum Decay, worst about
+2.631e-6 FS. All remain in the receipts. Long-bright late pitch barely changes
47.65170→47.65195 Hz against 47.77891 recorded; this does not close pitch-sigh
fidelity. An independent nine-take arithmetic review agrees within
5.28e-16 FS. This bounded screen is not a full-tail or native result.

## CPU implementation and remaining gates

Each port changes exactly 50 dependent constants: C40 retention/ON contribution
and 48 main-input polynomial coefficients. Regenerating the nominal formula
first reproduces every old word exactly. Instruction forms, addresses, frame,
state, all other stages and code extent stay unchanged. SHARC remains 6,008
code / 1,664 state bytes. No SDK, saved layout, renderer interface or runtime
patch is involved.

Actual nine-Decay preflights measure raw body output before Tone/C47. Maximum
CF output is .249997510575 FS; SHARC is .249997660518. Both satisfy the unchanged
quarter-scale bound, minimum observed headroom 2.339e-6 FS. CF's full normal
static/live/context suite and composed Tone/C47 pass: maximum body error
8.264e-6 FS and composed-chain error 2.021e-6, unchanged 1e-5 bound. The SHARC
ordinary suite continues with an added raw-body observation guard; no production
instrumentation or filtered-output substitute supplies that headroom proof.
191 tracked host tests pass; unchanged C/UI source boundaries retain their
separate earlier evidence.

Full SHARC, paired full tails/histories and installed DT/DN/DN2 qualification
remain pending. In DN2, a post-attack snapshot continuation alone cannot prove
the changed initial source. Fresh finite-age state evidence, firmware/kernel
identity and downstream native audio have distinct scopes. No global audio
clock, native owner identity or slot-to-track mapping is inferred.

Local fit/numerical evidence is under `out/808-c40-time-screen/`, independent
model audit under `out/808-next-candidate-review/`, and CPU implementation,
review and subsequent qualification under `out/808-c40-time-cpu/`. Broad
#9/#79/#2 fidelity remains open. DT #78 stays deferred, historical DN #20
unresolved, held-out audio unused and HTML/website untouched.
