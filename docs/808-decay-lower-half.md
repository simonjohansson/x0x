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

The final paired comparison is bound to committed implementation `853bb77` and
covers all 81 settings / 243 recordings, with full 12-second actual CPU tails,
raw timing and gain, and the independently verified reference track correction
×4. SHARC was freshly rendered from that frozen commit. ColdFire's completed
candidate grid is linked by verified model/source hashes and byte-identical
rebuilt images for all three stages; its original execution receipt is preserved,
not rewritten as a later execution.

| CPU / window | Prior mean RMS error | Current mean RMS error |
| --- | --- | --- |
| ColdFire, first 150 ms | .0664795555 FS | .0656948750 FS |
| SHARC, first 150 ms | .0664794214 FS | .0656947597 FS |
| ColdFire, whole 12 seconds | .009779942875 FS | .009679612085 FS |
| SHARC, whole 12 seconds | .009780020725 FS | .009679692219 FS |

Eighteen settings improve, nine settings at reference Decay display 32 regress,
and all 54 minimum/upper-range outputs on each CPU remain byte identical to
`65aeaf7`, including default and the four original corners. The ColdFire mean
whole-tail error reduction is 1.026%; it is not a fidelity or completion grade.
No fitted gain, onset alignment or waveform averaging is used. All three takes
remain separate; the as-recorded residuals are retained alongside the fixed ×4
correction. Held-out audio remains unused. The original HTML comparison report
is unchanged. The subsequently requested website was cancelled before
publication; its unpublished files are separate from this engine evidence.

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

These are all nine regressions, using the mean of the three takes for each
reference setting. The table shows ColdFire's raw first-150-ms RMS errors; SHARC
has the same regression pattern, and both CPUs' complete window results remain
in the paired JSON. Reference display 32 maps to native raw 4096 (knob 16).

| Reference Tone display | Prior error | Current error |
| --- | --- | --- |
| 0 | .03925760 FS | .03978473 FS |
| 32 | .04050986 FS | .04102754 FS |
| 64 | .04088795 FS | .04140195 FS |
| 96 | .04101539 FS | .04152854 FS |
| 128 | .04098045 FS | .04149493 FS |
| 159 | .04084963 FS | .04136686 FS |
| 191 | .04064708 FS | .04116852 FS |
| 223 | .04053830 FS | .04106326 FS |
| 255 | .04093963 FS | .04146182 FS |

Across the nine Tone positions, first-150-ms error at Decay32 increases 1.278%,
while Decay64 and Decay96 decrease 5.187% and 7.323%, respectively. Those are
changes in this diagnostic error measure, not sound-quality scores. The default
and corner clips cannot demonstrate the correction; an interior control example
is needed.

## Final qualification for this increment

- **Fresh requested rerun at committed `853bb77`:** all 190 tracked host tests,
  seven compiled C/UI and adapter boundary commands, and the guarded ColdFire
  12-case suite pass. Unadopted prototype tests are excluded. These receipts are
  under `out/808-decay-lower/retest-853/`; C/UI uses DSP/native fakes and does not
  stand in for installed-emulator audio. The fresh ColdFire maximum across the
  static cases is 3.873e-6 FS, with live-interior error 1.778e-6 FS.
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
  are intentionally changed. The fresh committed full 81-setting / 12-second
  grid also passes its independent oracle, maximum 3.947e-6 FS. Four whole
  architectural contexts and six 512-sample prefixes match the ordinary guarded
  fixture in the fresh NativeCore preflight, without stale-library overrides.
- **Paired CPU grid/history:** all 81 peer comparisons pass, maximum 5.226e-6
  FS. Seven explicit one-voice histories were freshly replayed from committed
  `853bb77` on both CPUs, with maximum peer difference 5.190e-6 FS and no numeric
  failures. Full-tail CPU samples are executed, including quiet tails. The
  existing 1e-5 FS bounds are unchanged. These checks establish implementation
  agreement; they do not establish faithful residual-charge or native allocator
  behavior.

The installed-emulator runs used an immutable candidate with the matching DSP
and C inputs. Their actual pre-commit provenance is retained; they were not
rerun or relabelled merely to obtain the later commit string.

| Emulator / device | Current evidence | Remaining failed gate |
| --- | --- | --- |
| digiemu / DT | 52,357 callbacks, 125 mixed-audible blocks; delivered raw8192/12288 and fresh body/Tone/C47 checks pass, maxima 9.657e-7 / 3.051e-6 FS | **FAIL:** parameter/page reset, deferred #78 |
| digiemu / DN | 109,148 callbacks, 74 mixed-audible frames; raw8192/12288 checks pass, maxima 9.704e-7 / 3.059e-6 FS over 38,304 samples each | **FAIL:** one-PCM16-unit bright baseline, #20 |
| Digikit / DN2 | **PASS:** 40,217 audio frames / 40,218 DSP frames on the normal daemon; no halt, missing blocks or controller error; both interior controls and nonlinear body/Tone/C47 continuation pass | No new failed gate in this run; physical/fidelity acceptance remains separate |

DN2's largest interior continuation error across body state, Tone capacitor and
terminal raw output is 6.446e-8 FS. Earlier observer-only Tone/capture/encoder
setup failures are preserved and corrected using the existing capture and
bounded targeting patterns, without changing firmware, waits or numeric limits.
DT and DN remain failed overall because their listed failures are retained.
No physical devices were used, and raw component agreement is not native PCM
acceptance.

Original source hashes, candidate comparisons, all regressions and CPU receipts
are under `out/808-decay-grid/` and `out/808-decay-lower/`. Final paired results
are `full-grid/measurements.json`, `full-grid/history/measurements.json` and
`full-grid/paired-summary.json` beneath the latter folder. The CF source/image
binding preserves its original execution and verifies those bytes against
`853bb77`; the SHARC runtime/code preflight has its own receipt. Native reports
are under `native/dt/`, `native/dn-v5/` and `native/dn2/`.
The [full-grid commands](808-grid-comparison.md#artifacts-and-reproduction)
accept an explicit committed `--revision` and separate output directory.
Grid and history receipts must match that revision. Fresh history analysis now
uses the grid's own verified fixed-controls receipt, without depending on an
ignored preflight file from the initial experiment.

Neither a small average improvement nor numeric implementation agreement closes
#9, #79 or broad #2 fidelity gates. The paired grid is complete for this
increment; the retained native failures and unfinished body/feedback behavior
remain explicit work in the existing plan.
