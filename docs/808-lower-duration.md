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

## Qualified at `53c4e66`

203 tracked host tests, the full guarded ColdFire body/Tone/coupling suites and
2,100 focused SHARC static/live calls pass. The SHARC minimum sound is verified
byte-identical to the previous output. Additional read-only pre-Tone witnesses
observe 4,608 raw samples at all nine Decay positions' first 512 samples; the
maximum remains .249997646 FS. Three 909 diagnostics retain byte-identical first
1,024 samples. These are relevant component checks, not a new complete 909 suite.
Code stays 7,176 bytes and SHARC state 1,664 bytes; instruction topology is unchanged.

Both actual CPUs freshly render all 81 settings / 243 training comparisons /
complete 12-second tails and seven declared-single-voice histories. Grid oracle
maxima are 3.988e-6 FS CF / 5.794e-6 SHARC; peer maximum 5.834e-6. History oracle
maxima are 3.237e-6 / 5.611e-6, peer 5.667e-6. The 1e-5 numeric, .25 raw-body and
.5 chain limits stay unchanged; maximum chain peak stays .400704205 FS.

**All 54 unaffected settings and all seven histories per CPU remain byte-identical,**
including every minimum/default/upper reference setting. Six unaffected ColdFire
body streams also remain identical. Verification binds 82 source files, immutable
runtime/image receipts and 185 raw artifacts, 128 identical to the parent.
Ignored evidence is in `out/808-lower-duration/`; final qualification SHA256:
`429dceced8bf9f034218f958bfb32e468b56b0cc9fcc171fd0a521c92ac14931`.

### Reference results

| Reference Decay at Tone128 | Reference t90/t99, ms | Previous | Current |
| --- | --- | --- | --- |
| 32 | 48.417 / 91.250 | 46.896 / 101.125 | 45.938 / 100.104 |
| 64 | 80.333 / 159.646 | 80.375 / 174.354 | 79.146 / 171.583 |
| 96 | 120.250 / 235.938 | 120.958 / 257.146 | 119.500 / 253.812 |

Affected duration checks rise **135→159 of 162 per CPU**, resolving 24 of the
27 short-tail misses. Whole-surface checks rise **432→456 of 486**. No previously
passing duration check is lost. Individually, 96 absolute timing errors improve
and 66 worsen while staying within their previous passing margins.

The darkest Tone at reference Decay32 remains failed on all three takes: t99 is
101.458 ms against 92.083 ms, an error of 9.375 ms versus the 9.208 ms allowance.
Its **0.167 ms miss is not waived**. The other 27 remaining failures are default
Decay t90, unchanged by this increment. The fit/release guard preserves already
passing body levels, so a stronger scalar adjustment is not adopted to force
those three dark-tail checks through at the expense of another metric.

All **1,380 previously passing eligible level checks remain passing** out of
1,890 across CPUs. Counts remain 690/945 per CPU and 27/81 settings meeting every
eligible level check. The tightest retained level margin is .00221 dB; it stays
visible rather than becoming a padded tolerance. This does not qualify full
level acceptance, intrinsic strength or retained-state retrigger.

### Counterevidence and limits

All 81 changed takes improve the first-6-ms routing-corrected residual; all 81
regress at 25 ms. At 150/500 ms and the complete tail, 27 improve and 54 regress;
the other 162 takes are unchanged. Mean whole-clip CF residual rises
.004587884→.004596382 FS, about **.185%**. Both original recording gain and the
fixed routing-corrected convention remain in comparison.json, including every
quiet/late/DC difference. Raw waveform error remains diagnostic.

Existing pitch diagnostics remain within the displayed target ranges where
reliable: affected body maximum 12.555 cents, late-sigh 28.751, settling 6.053.
Early estimates remain unresolved; 27 settling and 54 quiet estimates per CPU
are also unresolved. No amplitude/reliability rule is loosened to score them.

The existing broad body-band ratio diagnostic also retains adverse results:
mean absolute error grows 2.476→2.892 dB across both CPUs, with 54 results
improving and 108 worsening. Maximum current absolute error is 3.904 dB and
maximum shift 1.154 dB. This is not the still-unfrozen meaningful-harmonic
protocol, and no tone/listening pass is claimed.

No C/UI/plumbing, saved-layout, state-extent, ABI, SDK or dependency changes;
no fresh full-OS or physical-device claim. Prior native evidence remains prior,
and historical #20 acceptance remains open. #9 stays complete. Remaining
onset/body-shape/Tone differences, metric/listening protocols, held-out fidelity,
intrinsic accent and faithful residual-state retrigger stay in #79/#2.
The website and its unfinished generator work remain untouched.
