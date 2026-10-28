# Proposal: fixed internal 808 output calibration

Decision pending. No output coefficient has been fitted or applied.

The [render contract](render-contract.md) and #9 include fixed internal output
calibration, with native track level handling volume. The continuation loop
also says no fitted gain. Clarify whether that restriction bans fitting an
engine coefficient, or bans gain correction during the reference comparison.
The existing raw comparison remains the evidence baseline either way.

## Current evidence

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

## Proposed bounded step

Fit **one positive 808 engine constant**, shared by both CPUs and every setting,
from the existing training corpus with a declared raw first-500-ms objective.
Apply it in ASM after output coupling and before native AMP/track level; the
independent model uses the same frozen constant. Controls, saved sounds, IDs,
MODEL policy, trigger strength and state ownership stay unchanged.

Freeze that value before rerunning full training tails and seven histories.
Retain every setting/repetition and all early, late, level and shape regressions.
The reference recordings and their scheduled timing remain unchanged. There is
no per-recording, per-setting or per-device scale selection during comparison,
and held-out audio remains unused until its criteria are frozen.

Preserve the existing .25 FS internal-body, .5 FS rendered-chain and 1e-5 FS
backend numerical limits. A gain would amplify existing implementation error;
current worst SHARC agreement is already close to 1e-5. Improve implementation
accuracy if needed or reject the candidate. Do not relax those limits, clip a
result to pass, or treat a trained constant as a fidelity acceptance result.
Qualify any adopted constant on both actual CPU components and DT/DN/DN2
installed emulators, with existing native #78/#20 distinctions retained.

The alternative is to keep the current unit conversion and continue circuit
modeling. No extra LEVEL knob or native gain multiplication is proposed.
