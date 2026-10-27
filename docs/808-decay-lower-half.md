# 808 lower-half Decay correction

The full training grid exposed a problem hidden by the original endpoint and
default checks: the middle of the lower Decay range decayed too quickly. This
#9/#79 increment changes only that part of the provisional control law on both
CPUs. It is an empirical training calibration, not a physical VR6 taper model.
The settled 47.65 Hz pole, internal gain, saved controls and MODEL policy stay
unchanged. Full feedback, long-kick pitch sigh and residual-state behavior remain
unfinished.

For delivered raw Decay `d < 16384`, use `x=d/16384` and
`tau=.0333+(.143-.0333)*x*x`, then `r=exp(-1/(48000*tau))`.
Raw values from 16384 through 32512 retain the previous retention interpolation.
Minimum, default and maximum anchors remain unchanged. Live changes update
coefficients without clearing the voice.

The existing coefficient tables remain in retention coordinates. Both ASM
implementations calculate the equivalent lower-branch position using
`t_sigma=.143*x*x/tau` and the second-order exponential-ratio correction
`t=t_sigma-k*t_sigma*(1-t_sigma)/2`, where
`k=(1/.0333-1/.143)/48000`. The independent oracle uses the exact exponential;
it does not copy this approximation or the DSP recurrence. ColdFire uses bounded
integer arithmetic; SHARC uses float32 reciprocal refinement. State extents,
caller contracts and the audio recurrence are unchanged.

## Measured effect and retained regressions

The actual ColdFire grid covers all 81 settings / 243 recordings, with full
12-second tails, raw timing and gain, and the independently verified reference
track correction ×4. Mean per-setting whole-tail RMS error changes from
`.009779942875` to `.009679612085` FS, a **1.026% reduction**. Eighteen settings
improve, nine settings at display 32 regress, and 54 minimum/upper-range outputs
remain byte identical. No fitted gain, onset alignment or waveform averaging is
used; held-out audio and the HTML report remain untouched.

At Tone 128:

| Decay display | Prior / current positive-peak decay fit | Reference fit | Whole-tail RMS error, prior / current |
| --- | --- | --- | --- |
| 32 | 42.13 / 41.19 ms | 34.50 ms | .00458290 / .00464066 FS |
| 64 | 54.20 / 60.78 ms | 71.34 ms | .00648836 / .00614245 FS |
| 96 | 78.40 / 94.96 ms | 102.89 ms | .00750290 / .00688180 FS |

Display 32's waveform regression is retained, including first-150-ms error
`.04098045` to `.04149493` FS. Descriptive duration improvement does not erase a
waveform regression. Broader two-half tau interpolation improved some duration
fits but worsened whole-grid error; that candidate and extra knee/upper bends
remain rejected. The upper-range duration/pitch tradeoff needs body/feedback
work, rather than extra control knots.

## Qualification checkpoint

- **Host/C:** 190 tracked host tests and the independent C/UI suites pass.
  Unadopted prototype test files are excluded from that count.
- **ColdFire:** the guarded suite adds interior/fractional controls and live
  `4096→8193→12288→24576`, retaining all prior cases and 1e-5 FS bounds. Maximum
  static/live-interior errors are 3.873e-6 / 1.778e-6 FS. All 81 actual composed
  full-tail outputs pass the oracle, maximum 3.626e-6 FS. Nine normal-versus-fast
  4,096-sample preflights match every stage's output, state and EMAC context.
  The long batch omits only Python instruction/store logging, not ISA execution
  or post-call guards. The diagnostic including wrapper is 1,716 bytes.
- **SHARC:** 16,008 guarded callbacks pass, including all original and new
  interior/live cases, Tone, MODEL, slot and 909 checks. Static/live-interior
  errors are at most 3.637e-6 / 1.758e-6 FS. Combined code is 5,796 bytes and
  state remains 1,664 bytes in the qualified private 8/5 KiB split. All 25
  unaffected stored outputs are byte identical; the four old low-control files
  are intentionally changed. The full 81-setting paired grid is still pending.
- **Native:** DT's two new delivered controls and fresh raw body/Tone/C47
  checks pass at 1e-5 FS, retaining only deferred #78 reset failures. DN's full
  scenario also completes with 109,148 callbacks and 74 mixed-audible frames;
  its interior errors are 9.704e-7 / 3.059e-6 FS over 38,304 samples each. DN
  still fails only #20's one-PCM16-unit bright baseline. Earlier observer-only
  Tone/capture/encoder-target setup errors are preserved and corrected using
  the existing capture and bounded targeting patterns, without changing the
  firmware, waits or numeric limits. DN2 qualification is pending. Raw component
  agreement is not a native PCM or physical-device acceptance result.

Original source hashes, candidate comparisons, all regressions and CPU receipts
are under `out/808-decay-grid/` and `out/808-decay-lower/`. The pre-commit CF
execution records its actual source hashes and parent revision; later Git
binding must verify those bytes without rewriting its original execution
history. The [full-grid commands](808-grid-comparison.md#artifacts-and-reproduction)
accept an explicit committed `--revision` and separate output directory.
Grid and history receipts must match that revision. Fresh history analysis now
uses the grid's own verified fixed-controls receipt, without depending on an
ignored preflight file from the initial experiment.

Neither a small average improvement nor numeric implementation agreement closes
#9, #79 or broad #2 fidelity gates. The native and paired-grid gates above must
be completed and recorded separately.
