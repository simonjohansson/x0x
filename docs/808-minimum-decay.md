# 808 minimum-Decay correction

The approved next step is to shorten minimum Decay without disturbing the
already closer default/maximum sounds. The previous qualified DSP is
`0f7ef30`, including its fixed output factor 1.601664543. This increment fits
one minimum effective damping time, **19.22924 ms instead of 33.3 ms**, and
limits the new control segment to native words below 4096 (displayed Decay32).
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

## Qualification status

199 tracked host tests and targeted CPU checks pass. Both ports agree with
the independent model at the short segment and its boundary. Full guarded
SHARC regression, fresh full training grids and seven histories are in progress.
Do not claim the unchanged later settings or 909 outputs byte-identical until
those comparisons finish. Raw-body .25 FS, rendered-chain .5 FS and numerical
1e-5 FS limits stay unchanged. Full-device runs follow the agreed integration
cadence; no fresh native or physical-device claim is made here.

Remaining upper-middle Decay, onset/pitch/tone and full fidelity stay in #79/#2.
#9 remains complete as the supported baseline. HTML and held-out recordings
remain untouched.
