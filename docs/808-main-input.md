# 808 shaped main input and bridge forcing

This #9/#79 increment replaces the provisional y-drive with the C40/D53 pulse
shaper and the main bridged-T input on both CPUs. It keeps the calibrated
47.65 Hz settled pole, 6 ms high-frequency window, existing Decay curve,
companion pulse, saved controls/IDs and MODEL policy. It does not complete the
frequency-dependent feedback, pitch sigh, intrinsic accent or loaded output.

## Source model

S01 p.9 / S03 §§3–5 give R162=4.7 kΩ, R163=100 kΩ, C40=15 nF and a
1 ms trigger. The passive shelf has DC gain `R162/(R162+R163)=.04489016`
and time constant `(R162||R163)*C40=67.33524 us`. D53 limits the negative
falling edge; use an ideal -0.71 V clamp that changes capacitor charge.
This differs from clipping the output of an unchanged linear filter and from
S03's alternative memoryless nonlinear cascade. Finite diode conduction and
transistor behavior remain approximations.

The fixed intrinsic trigger is **14 V**, the upper endpoint of S03's published
4–14 V range. It is a provisional fixed-strength baseline, not a fit to the VST
or a velocity/accent mapping. Retain the previous encoding, 15 V = .25 FS.
During ON, u relaxes from 14 V toward `14*DC_GAIN`; at 1 ms the ideal diode
sets it to -0.71 V, then it decays toward zero. All sources use the same fixed
encoding; no output normalization, corner-specific gain or fitted timing.

For modal state z=w+i*y, output b=u+w, pole A=-sigma-i*omega and
`a=1/(R167*C41)`, the effective constant-feedback bridge gives:

```
L = (sigma*sigma+omega*omega)/a + 2*a - 2*sigma
Bmain = L*(1 - i*sigma/omega)
dz/dt = A*z + Bmain*u + Bcompanion*r
Hmain(s) = 1 + L*s / ((s+sigma)^2+omega^2)
```

This restores the main channel's band-pass numerator and direct feedthrough.
The effective damping is still the existing calibrated proxy, not the stock
VR6/R164/R169/C43 feedback shelf. The main and companion channels enter with
their distinct source factors; a raw pulse is no longer added to y.

`pulse808.py` independently integrates each constant/exponential input segment
in closed form. Both ASM backends advance the oscillator and C40 state with
one-step integrated gains, adding the source's direct feedthrough only to the
rendered output. A midpoint-curvature correction interpolates gains across each
existing Decay segment. The 6 ms coordinate conversion retains capacitor state;
START still resets the full chain, so faithful residual-state retrigger remains
open. Samples retain the existing after-interval convention: the main falling
edge affects the first OFF interval after the 48 ON samples.

## Integration and checks

ColdFire now has five volatile words per voice, with its coefficient scratch
on the stack. SHARC adds the C40 node bank at offset 576 and per-slot coefficient
scratch at 640, for 1,024 total private bytes. These are backend-private layouts;
the SDK render interface, saved formats and public controls are unchanged.
C ownership/model clears and every affected observer/guard include the new word.
Off-state Q31 rounding fixed points use the existing precision-floor policy;
there is no fitted tail cutoff. No new output limiter or tolerance relaxation.

136 host tests and independent C/UI suites pass. New tests check the passive
shelf/diode charge behavior, the main transfer's inverse-Laplace step response,
and a separate numerical solution of the coupled pulse/bridge ODEs with live
Decay edits. Actual CPU checks retain the 1e-5 FS limit, state/output/stack and
SDK-context guards, fractional/live controls, retrigger/interleaving and 909
regressions. The 9,012-call SHARC suite passes with 2,896 code bytes and 1,024
private bytes. Counts remain informational, without an instruction budget.

[Native-emulator evidence](808-main-input-native.md) and five-setting results
below record the completed runs.
The HTML report and held-out audio remain untouched. Known #78 resets,
historical #20 silence residue and separate #80 late MODEL delivery keep their
own acceptance gates. No complete stock-circuit or physical-device claim.

## Reference results

Both actual ASM backends rendered two seconds at the default and four
Tone/Decay corners. The comparison uses the same fifteen hash-, protocol- and
repeat-verified training takes, retaining scheduled MIDI timing and raw mod
gain. Only the documented common reference multiplier x4 is applied; there
is no normalization, fitted gain or onset alignment. Held-out audio was not
read. These are isolated CPU renders, separate from native downstream PCM.

| Setting | Whole-clip raw RMS FS, companion / main input | First 25 ms RMS FS, companion / main input |
| --- | --- | --- |
| Default | 0.065463 / 0.041022 | 0.264613 / 0.094923 |
| Dark, short | 0.021744 / 0.005352 | 0.171688 / 0.035088 |
| Bright, short | 0.022874 / 0.005978 | 0.183413 / 0.042563 |
| Dark, long | 0.075368 / 0.081041 | 0.264948 / 0.098185 |
| Bright, long | 0.076637 / 0.082112 | 0.279421 / 0.106893 |

The first 6, 25 and 150 ms improve at every setting. Whole-clip error falls
37% at default and 74–75% at short Decay, while **both long settings regress
7–8%**. Preserve those regressions; the earlier pre-frequency-switch default
error of 0.02770 FS is also still better than the current 0.04102 FS. This
improves the initial excitation without completing the pitch/feedback or long
tail behavior. It does not establish stock fidelity or close #9/#79/#2.

The maximum full-render error against the independent model is 8.836e-7 FS
for ColdFire and 8.624e-7 FS for SHARC; maximum cross-CPU difference is
1.189e-6 FS, below the unchanged 1e-5 FS limit. Supplemental guarded actual
CPU probes at raw Decay 8192 and 24576 also pass, with maximum model error
4.085e-7 FS and cross-CPU difference 4.196e-7 FS. These supplement the full
suites rather than changing their original case inventory.

Local raw renders, source/executable hashes, reference provenance and
6/25/150-ms windows are in
`out/reference/808-main-input/measurements.json`; supplemental probes are in
`midpoint-proof.json` beside it. The previous comparison is the companion
increment, `2f80a48`. The HTML report's saved SHA256 still matches exactly.
Next continue the existing feedback/pitch-sigh alignment, using these retained
long-tail and default regressions to prioritize it.
