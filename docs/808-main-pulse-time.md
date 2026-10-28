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

## Completed CPU and installed-emulator qualification

Committed engine `9e78ca94ea376593494caea2abd8857380fa34da` is qualified for
this bounded increment. Each port regenerates 50 dependent constants: C40
retention/ON contribution and 48 main-input polynomial coefficients. ColdFire
changes 48 values; two rounded curvature words remain identical. SHARC changes
all 50. Regenerating the nominal formula first reproduces every old word.
Instruction topology, addresses, frame, state and all other stages are
unchanged. The ColdFire diagnostic remains 1,716 bytes; SHARC remains 6,008
code / 1,664 state bytes. No SDK, saved layout or public renderer change is
involved. The precommit guarded executions retain their original provenance;
exact committed source and rebuilt-image identity bind their evidence to
`9e78ca9`, rather than relabeling them as new executions.

All 191 tracked host tests pass. ColdFire's normal 12-static/live/context suite
and fresh Tone/C47 composition pass: maximum body error 8.2633e-6 FS and
composed-chain error 2.0204e-6. SHARC's full 16,008 guarded callbacks pass,
including the original context and 909 cases; all 12 stored 909 files remain
byte-identical. Its largest static error is 9.9068e-6 FS. Actual raw-body
observation, before Tone/C47, gives CF .249997510575 FS and SHARC
.249997660518 FS under the unchanged .25 bound. Minimum measured headroom is
only 2.339e-6 FS. C/UI source boundaries are unchanged and retain their separate
earlier evidence; the fresh 191-test result is a host result.

Both CPUs then freshly execute all 81 settings for their full 12-second tails
and seven complete 13/16-second declared single-voice histories. All nine
ColdFire body streams are new; no previous body cache supplies this result.
The full-grid CPU/oracle maxima are CF 8.2346e-6 FS and SHARC 9.997719752e-6
under the unchanged 1e-5 bound. The latter leaves only 2.28025e-9 FS numerical
margin; a separate refined-RK4-32 check still passes at 9.992147430e-6. This
small margin remains visible, not a widened tolerance. Peak differences between
the actual CPUs are 4.9202e-6 FS across the grid and 4.2934e-6 across histories.
The long batch paths preserve their stated post-call guards; they do not claim
full-grid per-instruction/raw-body watching.

Against `f59f129`, the documented source correction ×4 improves every setting's
cumulative raw residual on both CPUs, including all original default/four
corners and all three separate takes. Actual ColdFire means are:

| Window | Previous mean RMS FS | C40 correction | Settings improved / regressed |
| --- | --- | --- | --- |
| First 150 ms | .06107184 | .06060181 | 81 / 0 |
| First 500 ms | .03935446 | .03904460 | 81 / 0 |
| Whole 12 s | .008150639 | .008085791 | 81 / 0 |

This is the unweighted mean of per-setting RMSE, distinct from the fit's
15-take SSE. It is not a fidelity percentage. The original nine minimum-Decay
150–500-ms regressions remain; direct stored-CPU checks at both Tone endpoints,
all three takes and both CPUs reproduce the derived values within 1.496e-16 FS.
Full-tail comparisons retain additional
small late-window regressions: corrected CF 2–4 s has two; SHARC 2–4 s has 27
and 4–8 s has 18. Tiny changes near the recording floor are not useful fidelity
claims. All seven declared histories improve in source-corrected whole-timeline
RMSE on both CPUs, but they test explicit component voice/reset scheduling,
not native owner identity or physical retrigger behavior. The as-recorded
convention is also preserved: without the documented ×4 correction, all 81
whole-12-s residuals worsen (CF mean .004349324→.004451523), and five of seven
histories worsen. No fitted gain or alignment hides those results.

Latest listed firmware runs use the pinned normal emulators, with raw callback
proof kept separate from stock-processed PCM:

| Device | Installed-emulator result | Evidence and limits |
| --- | --- | --- |
| DT, OS 1.54 | 52,557 callbacks; only known #78 reset failures | Fresh raw Decay 8192 / 12288 errors 2.7820e-6 / 8.1306e-6 FS; controls, mixed audio, locks, LFO and reload checks retained. |
| DN, OS 1.44 | Current scenario passes; 108,769 callbacks, 75 mixed audible blocks | Fresh raw errors 2.7923e-6 / 8.1517e-6 FS. Dark, bright and 909 each pass one 100-ms zero window; historical #20 remains unresolved, with no 60-window stability claim. |
| DN2, OS 1.12 | Full scenario passes; 40,221 audio / 40,222 DSP frames | A newly active 808 bank at age 32 matches independent state within 1.099e-7 FS; the old nominal-timescale mutation fails at .003866 FS. Native audio and original 909 witness also pass. |

DN2's observed transition is an inactive zero bank to one callback with 256
initial samples remaining. The initial 288 write is established by the
source/header contract, not directly observed; no slot-to-track identity or
global clock is inferred. Post-attack continuation alone is not used as proof
of the changed excitation. Late post-STOP MODEL was not rerun for this DSP
increment; #80's original-order adopted-runtime evidence is separate.
Persistence across restart, physical-device timing, complete output loading,
stock-circuit fidelity and held-out acceptance remain unqualified.

The ignored `out/808-c40-time-cpu/final-qualification.json` ledger binds the
component, full-grid/history, reference comparison and three native reports.
It independently rechecks 185 raw artifact sizes/hashes, 179 native source
files, the 81-file DSP snapshot, firmware and runtime hashes. Guarded instruction-component, NativeCore batch and installed full-OS
evidence remain distinct.

Local fit/numerical evidence is under `out/808-c40-time-screen/`, independent
model audit under `out/808-next-candidate-review/`, and CPU implementation,
review and subsequent qualification under `out/808-c40-time-cpu/`. Broad
#79/#2 fidelity remains open; #9 is accepted as the supported baseline. DT #78 stays deferred, historical DN #20
unresolved, held-out audio unused and HTML/website untouched.
