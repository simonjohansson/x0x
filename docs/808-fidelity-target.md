# 808 reference-fidelity target

The human approved these starting targets on 28 October 2026: at the same
settings, x0x should sound and respond like the captured reference VST, with
small differences acceptable. Exact waveform or transistor-by-transistor
agreement is not required. Schematics guide implementation; reference measures
and listening decide this milestone's completion. This is software-reference
fidelity, not original-hardware qualification.

## Approved starting limits

| Aspect | Target |
| --- | --- |
| Pitch | Settled pitch within 20 cents; audible pitch evolution within 50 cents wherever reliably measurable. |
| Decay | Effective decay duration within 10% or 5 ms, whichever is larger; check both body and fading tail. |
| Punch and volume | Peak level and RMS level in fixed attack/body windows within 2 dB. |
| Tone | Meaningful harmonic-band balances within 3 dB. |
| Listening | No clearly objectionable tuning, punch, brightness or duration difference in switched individual hits and repeated playback. Listening can reject an objective pass. |

These are agreed product tolerances, not established limits of audibility or
passing results. Do not turn whole-waveform residual error into a fidelity
percentage or a sole acceptance gate.

## Coverage and measurement freeze

Evaluate both actual CPU implementations across all 81 training Tone/Decay
settings and all three recordings per setting. Keep setting/repeat failures
visible; a passing grid average does not excuse a failing corner. Preserve raw
recordings, scheduled timing, both gain conventions and all regressions. The
fixed reference multiplier of four only undoes the audited capture routing.
No fitted delay/phase/DC, waveform averaging or per-hit normalization is allowed.

The thresholds above are approved. Before using held-out audio, finish and
freeze the operational measurement rules: pitch reliability and windows, body
and tail duration estimators, attack/body RMS windows, harmonic bands and their
measurement floor, and the listening protocol. Unreliable estimates are
unresolved, not passes. Existing diagnostics remain useful but do not silently
become validated acceptance measurements.

The [level protocol](808-output-calibration.md) now freezes attack/body windows,
the level floor and the training-only fixed-scale objective. Other measurement
rules and held-out acceptance remain open.

After training checks pass, use the 16 held-out settings / 48 recordings and
perform the listening review. Until then those recordings stay unused. Record
any later human-approved criterion refinement and its reason; retain previous
results. If held-out audio informed a revision, identify that exposure rather
than claiming the revised criterion passed an untouched holdout.

## Fixed DSP scaling and native volume

The human explicitly approved changing a fixed internal DSP output scaling
factor after clarifying that normal device volume controls must remain in
charge. This supersedes the earlier gain freeze. Calibrate one positive 808
output factor shared across settings and CPUs using training recordings only;
apply it in the engine, not as a comparison-time adjustment or an extra saved
parameter. Freeze the factor before final validation. Do not select a different
factor per hit, recording, device or Tone/Decay setting.

Native AMP/track LEVEL processing remains downstream. IDs, saved controls,
MODEL semantics and public SDK boundaries stay unchanged. Preserve numerical
agreement and headroom limits; reject clipping or improve implementation
precision rather than relaxing limits to accommodate scaling. See the
[gain decision and prior measurements](808-output-calibration-proposal.md).

## Scope and next work

This milestone covers single hits at the recorded fixed strength. Intrinsic
accent and faithful residual-state retrigger remain separate, explicit #79/#2
work; passing this milestone does not qualify either. Repeated playback for
listening is not proof of retained-state retrigger behavior.

Next freeze the measurement protocol, assess the current engine against these
targets, and implement/qualify fixed output scaling and remaining sound
corrections sequentially. No scaling change or acceptance run is delivered by
this document. #9 stays complete as the supported baseline; #2 owns reference
acceptance and #79 owns remaining engine refinement. Leave the HTML unchanged.
