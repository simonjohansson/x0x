# 808 output-gain decision

**Latest decision, 28 October 2026: fixed DSP output scaling is approved.**
After clarifying the distinction between the DSP's baseline output amplitude
and the device's normal LEVEL control, the human explicitly approved changing
the internal scaling factor. This supersedes the earlier same-day decision to
keep gain fixed. Normal native AMP/track-level volume handling remains in use;
there is no additional x0x LEVEL knob or saved gain parameter.

The human also approved the [808 starting fidelity targets](808-fidelity-target.md).
The [calibration implementation and level protocol](808-output-calibration.md)
are qualified at `0f7ef30` on both actual CPUs, all training settings and seven
histories. `5963a34` is the previous baseline. The fixed scale improves level
matching but does not pass every +/-2 dB window; see the remaining envelope gaps
in the results. Native volume handling is unchanged.

## Before-calibration evidence (9e78ca9)

On qualified main-pulse implementation `9e78ca9`, the first 500 ms retain these
raw measurements, using only the documented reference ×4 routing correction:

| Setting | Model / reference peak FS | Model / reference RMS ratio |
| --- | --- | --- |
| Default Tone/Decay | .24425 / .30855 | .53445 |
| Dark / minimum Decay | .20700 / .26002 | .83741 |
| Bright / maximum Decay | .25018 / .32076 | .50784 |

The norm-amplitude part accounts for about 85% of default squared residual and
93% at bright/long. These are geometric diagnostics, not a fitted correction.
Different RMS/peak ratios show that a single scale may be insufficient: shape
and envelope errors remain. No result promises that a gain constant solves them.
Raw source/render hashes and diagnostics are in
`out/808-output-calibration-proposal/measurements.json`.

## Authorized calibration scope

Fit **one positive 808 engine constant**, shared by both CPUs and every setting,
from the existing training corpus with a declared objective fixed before fitting.
Apply it in ASM after output coupling and before native AMP/track level; the
independent model uses the same frozen constant. Controls, saved sounds, IDs,
MODEL policy, trigger strength and state ownership stay unchanged.

Freeze that value before rerunning full training tails and seven histories.
Retain every setting/repetition and all early, late, level and shape regressions.
The reference recordings and their scheduled timing remain unchanged. There is
no per-recording, per-setting or per-device scale selection during comparison.
The accepted thresholds still need frozen measurement rules before held-out
audio is used; see the target document. No comparison-time gain fitting is allowed.

Preserve the existing .25 FS internal-body, .5 FS rendered-chain and 1e-5 FS
backend numerical limits. A gain would amplify existing implementation error;
current worst SHARC agreement is already close to 1e-5. Improve implementation
accuracy if needed or reject the candidate. Do not relax those limits, clip a
result to pass, or treat a trained constant as a fidelity acceptance result.
Qualify any adopted constant on both actual CPU components and reference
recordings. Run full-device DT/DN/DN2 checks for boundary changes and the next
integration/release milestone, following the agreed DSP-only test cadence.
Existing native #78/#20 distinctions remain explicit.

## Historical decision

Earlier on 28 October the human declined the calibration proposal and chose
to keep the existing internal gain. Prior qualification documents correctly
describe their unchanged gain at that checkpoint; they are historical results,
not a continuing prohibition after the explicit approval above.
