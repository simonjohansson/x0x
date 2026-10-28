# 808 lower-interior duration correction

The previous qualified DSP is `7716145`. Reference Decay32 has a t99 tail of
91.25 ms at Tone128, while x0x takes 101.125 ms, missing the unchanged 10% margin.
The existing lower curve also produces long t99 estimates at Decay64/96,
although those are already within tolerance. This increment refines that
existing curve, with no new control, envelope, state or public interface.

## Training-only choice

Keep the same equation below default: s=raw/16384,
q=s*s+k*s*s*(1-s), tau=.0333+(.143-.0333)*q. Fit only k in [0,1.5] using all
81 lower-interior training recordings (27 Tone/Decay settings, three takes).
Minimize equally weighted squared log t90/t99 duration ratios over the first
two seconds. Reject a candidate if any eligible previously passing level check
becomes a failure; use the existing windows, floor and 2 dB threshold.

The pre-fit protocol is `out/808-lower-duration/protocol.json`. The best-seen
feasible k=1.3229549 is constrained by the level guard, not a stationary optimum.
Round upward toward the known feasible baseline in steps of .01 to retain
implementation margin: **k=1.33**, previously 1.5. The release rule is recorded
before its separate refined model check in `release-protocol.json`. Gain remains
1.601664543; no timing, gain, phase or DC is fitted and no held-out audio is read.

At Tone128, the refined model changes Decay32 t90/t99 from 46.896/101.125 ms to
approximately 45.9/100.1 ms, against 48.417/91.250 ms. The t90 difference grows
but remains inside its existing margin; the t99 miss is corrected. Decay64/96
also have shorter t99 estimates. Mean first-two-second raw RMS over the affected
takes grows .007045185→.007107619 FS (about .89%); this remains counterevidence,
not a reason to change the approved diagnostic/acceptance distinction.

## Ports and checks

The raw0 minimum, default and every upper control word retain their model law.
Recompute the short segment's endpoint and derivative from k=1.33 so it still
joins continuously with matching slope at raw4096. Its endpoint tau is now
46.995359375 ms; the derived short shape is 1.629835106257368.

Both ports reuse their existing instructions and coefficient banks. Regenerate
only the short-bank constants and the lower curve scalar. Reproducing the old
constants first checks the derivation against the existing implementation.
SHARC quantizes the new linear short bank while preserving the old effective
minimum coefficients, rather than allowing cancellation rounding to move the
minimum sound. This is numerical anchor preservation, not another reference fit.
State extent, ABI, code topology, gain, MODEL and saved controls stay unchanged.

203 tracked host tests and the complete guarded ColdFire body suite pass. Focused
SHARC static/live guards, minimum byte identity and frozen full-grid comparisons
are pending. This candidate does not qualify full Decay, level, harmonic,
listening or held-out fidelity. #9 remains complete; #79/#2 own refinements.
The website and its unfinished generator work are preserved without updates.
