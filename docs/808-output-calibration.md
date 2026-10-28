# 808 fixed output calibration

Subsequent [minimum-Decay qualification at e0adf4e](808-minimum-decay.md)
retains this factor. The calibration results below remain the historical
`0f7ef30` comparison; current level/duration results are in the linked correction.

The human approved one fixed DSP scaling factor on 28 October 2026 after
clarifying that native AMP/track LEVEL remains the user volume control. This
increment applies **1.6016645431518555 (+4.091431 dB)** after C47 on both CPUs.
It is shared across settings and devices, with no saved value or comparison-time
normalization. The model's circuit state and native volume path stay unscaled.

## Level protocol frozen before fitting

Measurements use the scheduled MIDI sample as time zero at 48 kHz. There is
no onset alignment, averaging of recordings, phase shift or DC subtraction.
The reference multiplier of four only removes the audited REAPER routing.
Keep as-recorded comparisons separately. Use each of the 243 training takes
and both actual CPU baselines, bound to `5963a34`:

- Peak: maximum absolute sample over 0–500 ms.
- Attack RMS: 0–25 ms; body RMS: 25–150 ms; tail/body RMS: 150–500 ms.
- Level error: `20*log10(model/reference)`, with an inclusive +/-2 dB target.
- A reference window below .001 FS (-60 dBFS) is retained as a quiet diagnostic,
  excluded from the level-fit/pass count. An eligible silent model is unresolved
  and cannot be repaired by gain. This floor is fixed before fitting.
- Minimize equally weighted squared dB errors over every eligible measure,
  recording and CPU. This fits aggregate level, not phase-sensitive waveform
  cancellation. Bound the factor by the existing .5 FS synth-chain headroom,
  with .1% safety, then round once to a common binary factor.

The unconstrained fitted factor is 1.6016644952887347; its common binary value
is 1.6016645431518555. Baseline full-tail peak .2501798868 FS permits a headroom
factor 1.9965633783, so the headroom bound is inactive. There are 1,890 eligible
checks; 54 quiet tail/body checks remain separate. No held-out audio informed
the fit. The approved pitch/decay/tone/listening targets still need their own
operational protocols before held-out acceptance.

## Numerical prerequisite

Directly boosting the prior implementation would exceed its unchanged 1e-5 FS
model-agreement limit. The main error is the existing quadratic interpolation
of Q43's feedback coefficients, not a new sound parameter. Keep its endpoints,
midpoint and independent circuit oracle; add the cubic remainder
`d*t*(1-t)*(t-.5)` on both CPUs. Derive `d` from the mean exact-coefficient
residual at retention coordinates .25 and .75, divided by that basis. No VST
fit is used for this numerical correction. SHARC also uses an `expm1` form for
C39 source retention, avoiding float32 rounding of a coefficient near one. Host coverage checks the remainder
against the independent coefficient function over both control segments.

C47's previous-input/output history remains unscaled; multiply only the emitted
sample. ColdFire uses the common factor in Q2.30, with fractional EMAC followed
by a left shift; SHARC uses the identical float32 factor. The raw body keeps
its .25 FS bound and the complete rendered synth chain keeps .5 FS. An isolated
RC stress input alternating between +/- .25 DC can reach almost .5 before
calibration: its mathematical bound becomes `.5*factor`, below representable
full scale. This adversarial filter test is separate from the unchanged .5 FS
bound on actual synth renders. Numeric agreement stays 1e-5 FS in output units.

## Qualified result at `0f7ef30`

198 tracked host tests, six isolated C/UI checks and both guarded CPU suites
pass. SHARC executes 16,008 guarded callbacks with 183,040 raw-body observations;
all twelve stored 909 outputs remain byte-identical. Its code is 6,120 bytes,
with the unchanged 1,664-byte private state. Guarded working-tree source/images
are bound to the committed source; fresh full-grid renders use the archived
`0f7ef30` snapshot. No fresh full-device OS run or physical-device test is claimed.

Both CPUs freshly render all 81 settings / 243 takes / 12-second tails and all
seven declared-single-voice histories. Maximum grid oracle errors are
7.109e-6 FS (ColdFire) and 6.694e-6 FS (SHARC); histories are 3.237e-6 / 5.611e-6.
All seven declared histories improve their reference residuals on both CPUs;
this does not qualify faithful residual-state behavior or native ownership.
Peer maxima are 5.834e-6 for the grid and 5.667e-6 for histories. All remain below
the unchanged 1e-5 FS limit. Actual maximum synth-chain peak is .400704205 FS,
below .5; the separate raw-body quarter-FS checks pass.

The following counts are **per CPU**, preserving all three takes. Both CPUs
have identical pass counts. They are level checks, not fidelity percentages.

| Measure | Eligible checks | Before within +/-2 dB | After within +/-2 dB |
| --- | --- | --- | --- |
| Peak, 0–500 ms | 243 | 21 | 165 |
| Attack RMS, 0–25 ms | 243 | 0 | 240 |
| Body RMS, 25–150 ms | 243 | 0 | 108 |
| Tail/body RMS, 150–500 ms | 216 | 27 | 54 |

Across both CPUs, 96 → 1,134 of 1,890 eligible checks pass. The 54 quieter checks
remain diagnostics. Nine of 81 settings pass every eligible level check on both
CPUs; **full level acceptance still fails**. The RMS of the dB errors falls
4.7542 → 2.4214 dB. Do not reinterpret a passing average as all-setting acceptance.

At default controls, ColdFire deviations are peak +2.062 dB, attack +.214 dB,
body -2.036 dB and tail/body -2.600 dB. The worst minimum-Decay body is +7.893 dB;
long tails can be -4.176 dB. One attack setting remains +2.0011 dB and fails the
inclusive 2 dB limit; it is not rounded into a pass. The frozen screen proves
no single gain can satisfy every check: its feasible dB interval is empty,
[6.26788, -1.80124]. Next address envelope balance rather than choose per-setting
scales or loosen the target.

| Routing-corrected ColdFire raw RMS error | Before | After |
| --- | --- | --- |
| First 25 ms | .071831522 FS | .048644044 FS |
| First 500 ms | .038040112 FS | .021897009 FS |
| Whole 12 seconds | .007880723 FS | .004550782 FS |

Whole-clip diagnostic error falls about 42.25%. Both CPUs improve 72 settings /
216 takes and regress all nine minimum-Decay settings / 27 takes in those three
windows. Other windows, all repetitions and both routing conventions remain in
the raw comparisons. Uncorrected as-recorded errors increase at all 243 takes;
this is preserved, not normalized away. Raw waveform error is diagnostic,
not the accepted fidelity gate. Accent, retained-state retrigger, other metric
protocols, listening and held-out fidelity remain open in #79/#2. #9 stays complete.

Evidence is local and ignored under `out/808-output-calibration/`: the original
pre-fit protocol, reproduced fit, `actual-levels/levels.json`, both full grids,
raw before/after audit and `final-qualification.json`. The final verifier checks
82 source files, 185 raw CPU artifacts, pinned runtimes, both grids and histories,
all stored 909 identities and the original numerical/headroom limits.
Its receipt SHA256 is `2b93900b750c769b02c480a9242530158131f7caf00d711ec799ae16a2750192`.

Reproduce the fit with the existing training files:

```sh
mise exec -- uv run --offline --frozen --project vendor/digiemu \
  --with numpy==2.5.4 --with soundfile==0.14.0 --python "$(mise which python)" \
  python -m x0x.level808 --baseline out/808-decay-shape-cpu/full-grid \
  --output out/808-output-calibration/reproduced-fit
```

The helper validates the baseline render receipts and recording hashes before
measuring. Add `--candidate <qualified-grid-folder>` for actual before/after
levels; it verifies the production factor against the frozen baseline fit.
Full waveform comparisons remain separate diagnostics using the existing grid
comparator. HTML and held-out recordings remain untouched. This does not reopen
#9 or qualify intrinsic accent, retained-state retrigger or final native #20.
