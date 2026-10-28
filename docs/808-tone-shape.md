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
Fresh paired tails/histories and all three installed scenarios remain pending.
Local source/readback receipts, synthetic proofs and fit trace are under
`out/808-tone-discretization/` and `out/808-tone-sqrt-curve/`; the independent
integrated screen is `out/808-tone-sqrt-screen/fitted/`.
