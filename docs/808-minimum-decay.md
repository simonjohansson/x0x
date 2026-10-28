# 808 minimum-Decay correction

Subsequent [upper-middle Decay work](808-upper-decay.md) preserves every
minimum-setting output below. This document records the `e0adf4e` qualification.

The approved next step is to shorten minimum Decay without disturbing the
already closer default/maximum sounds. The previous qualified DSP is
`0f7ef30`, including its fixed output factor 1.601664543. This increment fits
one minimum effective damping time, **19.22924 ms instead of 33.3 ms**, and
limits the new control segment to native words below 4096 (reference Decay 32/255,
native 16/127).
No gain, pitch, saved controls, lifecycle or public boundary changes.

## Training-only choice

The protocol was written before fitting in `out/808-min-decay/protocol.json`.
Use all 27 minimum-Decay training recordings, nine Tone positions and three
separate takes. At fixed scheduled onset and reference routing x4, minimize
equally weighted squared log ratios of cumulative-energy t90 and t99 over
0–500 ms. Bound tau to [10, 33.3] ms. No gain, phase, delay or DC is fitted;
held-out audio stays unused. A bounded scalar search selects 19.22924 ms.
This is a best-seen effective response parameter, not identification of a
physical resistor/capacitor or proof of a unique optimum on a sampled objective.

A refined independent model screen changes Tone128 t90/t99 from 30.125/70.021 ms
to 18.417/40.021 ms, against 19.500/37.750 ms recorded. Mean first-500-ms raw
reference RMS over all 27 takes falls .012965165 to .006611355 FS. These are
model results, not actual-CPU qualification or complete fidelity acceptance.
Full 12-second CPU/reference comparisons must confirm duration and waveform
improvements before adopting the correction.

## Local control segment

For p=raw/4096 below 4096, use

```
q = p*p + k*p*p*(1-p)
rho = rho_min + (rho_32-rho_min)*q
```

`rho_min=exp(-1/(48000*.01922924))`; `rho_32` is the unchanged previous law at
raw4096, tau .04786953125. Derive k=1.627244023017021 from the old endpoint
retention derivative: minimum slope is zero and the value/first derivative
join the prior curve at raw4096. k is derived, not a second VST-fitted control.
Every model word from raw4096 upward is exactly unchanged. Host tests cover
all-word monotonicity and the join; the independent source/KCL oracle remains
separate from the CPU interpolations.

Both CPUs add a dedicated short coefficient bank, preserving their existing
later branches. It uses the existing exact integrated main/companion input
coefficients, quadratic main interpolation and cubic feedback remainder at the
new segment endpoints. The SHARC implementation tags the temporary coordinate
as q-1 within registers; no flag, SDK word or persisted state is added. ColdFire
keeps its existing five state words; SHARC keeps 1,664 bytes. The new interior
raw2048 and edge raw4095 receive guarded component coverage.

## Qualified at `e0adf4e`

199 tracked host tests and both guarded actual CPU suites pass, including new
short-segment interior raw2048 and edge raw4095. SHARC runs 16,392 guarded calls
and 195,328 actual raw-body observations; its code is 6,878 bytes within the
existing reservation, with unchanged 1,664-byte state. All twelve prior 909
regression files are byte-identical. Working-tree component execution remains
labelled as such and is bound by source/image identity to committed code;
fresh full grids use the archived `e0adf4e` snapshot.

Both CPUs freshly render all 81 settings / 243 takes / full 12-second tails and
seven declared-single-voice histories. **All 72 later settings and all seven
histories remain byte-identical on each CPU.** All eight nonminimum ColdFire
body streams also remain identical. Maximum grid oracle errors are 7.109e-6 FS
(CF) and 6.694e-6 (SHARC), history errors 3.237e-6 / 5.611e-6; peer errors are
5.834e-6 / 5.667e-6. Limits remain 1e-5 FS, .25 FS raw body and .5 FS synth chain;
maximum emitted peak remains .400704205 FS.

Full-tail measurements confirm the screen at Tone128 / minimum Decay:

| Cumulative-energy time | Reference | Previous | Current |
| --- | --- | --- | --- |
| t90 | 19.500 ms | 30.125 ms | 18.417 ms |
| t99 | 37.750 ms | 70.021 ms | 40.021 ms |

Every minimum-Decay take improves both descriptors on both actual CPUs and
meets the agreed 10% or 5 ms duration margin. This qualifies this training
subset's duration checks, not the entire Decay surface or held-out fidelity.
The measurement helper first checks known pulse timings, gain invariance and
rejection of silence; there is no fitted onset shift.

All 27 minimum takes improve routing-corrected raw waveform residuals at
6/25/150/500 ms and the whole 12 seconds; all other 216 takes are unchanged.
Mean changed-subset first-500-ms CF RMS falls .012965236→.006611355 FS (about 49%).
Across all 81 settings, mean whole-clip CF RMS falls .004550782→.004406673 FS
(about 3.17%). Those are error reductions, not fidelity percentages. Both routing
conventions and every take remain available. As-recorded residuals also improve
at the changed settings in those windows.

Retain the counterevidence: the SHARC minimum takes have tiny late-window
regressions at 500–1000 ms, 1–2 s and 2–12 s; the largest all-grid mean increase
is about 1.46e-10 FS at 500–1000 ms. ColdFire's corresponding late residuals stay
identical. Quiet tails are not gain/DC-fitted or cut to erase those differences.

Level checks also improve without changing the fixed output factor. Per CPU:

| Eligible +/-2 dB checks | Previous passes | Current passes |
| --- | --- | --- |
| Peak (243) | 165 | 171 |
| Attack (243) | 240 | 243 |
| Body (243) | 108 | 135 |
| Tail/body (216) | 54 | 54 |

All nine minimum settings now meet every eligible level check; the whole-grid
count rises 9→18 of 81 settings. Combined passing checks rise 1,134→1,206 of 1,890.
The 54 quieter combined checks remain diagnostics. Other settings still fail;
this is not full level or whole-engine acceptance.

The ignored `out/808-min-decay/` contains the pre-fit protocol, scalar screen,
coefficient derivation, source snapshots, full grids, every raw regression and
`final-qualification.json`. Its verifier checks 82 source files and 185 raw CPU
artifacts; 166 artifacts are byte-identical to the parent. The immutable native
runtime and all image/source bindings are reverified. Receipt SHA256:
`ca799e973f0ed7bc20a69e93c77bec823b105d0972504d80ef81f3f1ab6aaf09`.

No C/UI/plumbing, saved-layout, DSP state extent, calling convention, dependency
or package boundary changes. Prior C/UI and full-device results remain prior;
no fresh native OS or physical-device claim is made. The agreed DSP-only
component/reference cadence applies; final native acceptance remains #20.

Remaining upper-middle Decay, onset/pitch/tone and full fidelity stay in #79/#2.
#9 remains complete as the supported baseline. HTML and held-out recordings
remain untouched.
