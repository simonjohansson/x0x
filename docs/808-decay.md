# 808 Decay calibration from the training recordings

These measurements describe the earlier calibration. The subsequent
[companion input](808-companion.md) keeps these pole losses but adds continuing
forcing, so finite-window decay fits can differ from the bare pole time constant.
Current waveform checks use the driven analytical oracle.

The next existing #9/#2 step shortens the 808's excessive tails on both CPUs.
The old raw-body range was approximately 142 ms to 1 second, with a 250 ms
default. At fixed reference Tone 128, the two-second positive-peak fits are
29.160 ms, 143.013 ms and 365.962 ms for Decay 0/128/255. These are descriptive
output fits, not single physical circuit time constants.

Use one mapping at every Tone position. The raw-body anchor time constants
are **33.3 ms / 143 ms / 366 ms** at native raw 0/16384/32512. The short anchor
includes an approximate compensation for the existing unloaded Tone/C47 path:
a 29.16 ms body produces only a 22.60 ms positive-peak fit after that path;
33.3 ms gives about 29.48 ms. No intrinsic gain, pitch, output normalization,
per-hit alignment, saved layout or MODEL behavior changes.

This is an empirical calibration inside the provisional model, not the stock
VR6 frequency-dependent feedback shelf or its physical pot taper. It also does
not match both signs of the short reference's asymmetric decay: at Tone 128,
its negative-peak fit is only 14.871 ms. Full feedback, excitation/pitch, loading
and circuit-state retrigger work remain in #9/#79.

## Mapping and independent checks

Convert each declared body time constant to `r=exp(-1/(48000*tau))`. Below the
approved default, interpolate between the minimum/default radii with
`d/16384`; above it use `(d-16384)/16128` between default/maximum. The mapping
is continuous, strictly increasing and below unity across all 32,513 raw words.
This remains feedback loss, without an additional amplitude envelope. Exact
fractional values and live changes keep the oscillator/pulse state.

ColdFire selects two sets of Q1.31 rotation coefficients and normalizes each
raw interval before its existing EMAC multiply. The low branch excludes 16384,
so its exact factor 131072 stays signed-positive; the upper factor is
`floor(2^31/16128)=133152`. SHARC selects two affine coefficient sets using
its existing raw/32512 normalization and retains the small `c-1` representation.
The independent oracle convolves the finite drive with analytical responses
using those declared radii, rather than copying either ASM recurrence.

Tests retain the unchanged 1e-5 FS numeric limit, control/state/context guards,
min/default/max and fractional cases. Both actual CPU suites now include 16383
alongside 16384/16385 to exercise the join. The host test checks the whole raw
range for monotonicity and verifies measured body decay/pitch independently.
909 code, registration, state size and controls are unchanged.

## Evidence boundaries and next steps

The three fixed-Tone anchor triplets are training data. WAV/session hashes,
before/after parameter readbacks, fixed source settings, repeats, host gain,
channel identity and silence checks use the existing capture validator.
Anchor provenance is retained locally in `out/reference/808-decay/anchors.json`.
The five-setting comparison uses the original default and four Tone/Decay
corners, with raw timing and one known reference host-gain correction ×4.
No held-out audio is used. The original HTML report remains unchanged.

Interior positions are intentionally not claimed calibrated. For example, the
analytical composed fit at native raw 8192 is about 54.33 ms versus the training
Decay64 reference's 71.34 ms; at raw 24576 it is about 207.32 ms versus reference
Decay 191's 240.07 ms. Their exact knob fractions differ slightly. A matching
three-point range does not qualify the full response. Keep these discrepancies
visible while deriving the source feedback/control curve, rather than adding
more independent corner fits.

Run `mise run test`, `mise run test:808:body`, then the existing native
`test:dt`, `test:dn` and `test:dn2` tasks. Direct DSP output, independent model
precision, native downstream audio and software-reference agreement remain
separate. Preserve #78 resets, #20's historical DN residue and #80's separate
late MODEL gate; an unrelated waveform change does not resolve them.

## Current component increment

120 host tests and independent C/UI suites pass. The shared SHARC suite passes
9,012 calls, with 1,216 code bytes and unchanged 512 private data bytes. Matching
composed CPU checks retain 1e-5 FS: maximum errors are 1.470e-6 FS (ColdFire),
4.716e-7 FS (SHARC), and 1.656e-6 FS across CPUs. Fractional/join/live-control,
MODEL, ownership and context checks remain passing, including existing 909 audio.

DT native functional checks pass across 39,611 callbacks; full acceptance fails
only known #78 parameter/page resets. Firmware SHA256:
`90275b62fb3d89f08da4f3c1dd50c20388c9f2a933866f6185f1fa9178d5814a`.
DN's native scenario passes across 100,778 callbacks, including all three
exact-zero capture baselines. The earlier #20 one-count residue remains an
unresolved historical acceptance gate; this waveform change does not establish
a general fix. Firmware SHA256:
`1a30b9576c8b74de6ecb2d210eecb5c540ac6d9eaca6712decfcb624dd1ca470`.
DN2's native scenario passes across 31,879 DSP frames with no halt
or missing blocks. Actual body-state time constants are
33.300010/366.000485 ms at the two endpoints. Native controls,
locks/LFO, reload, mixed models, Tone/coupling and 909 checks pass in this tested
scenario. #80's separate late MODEL path is unqualified. Firmware SHA256:
`c539ea0dc93cf1b4ceade07bf561a8e12da98b366b5b7258c3ffc29d70649185`.
Fresh two-second comparison results follow below; they are separate from
downstream/native PCM and circuit-fidelity evidence.

## Two-second five-setting results

| Setting | Reference / ColdFire / SHARC decay fit ms | Raw waveform RMS FS before / after |
| --- | --- | --- |
| Default | 143.013 / 143.264 / 143.263 | 0.03154 / 0.02770 |
| Dark, short | 25.443 / 29.439 / 29.440 | 0.03422 / 0.02034 |
| Bright, short | 29.151 / 29.512 / 29.512 | 0.03503 / 0.02126 |
| Dark, long | 365.809 / 366.557 / 366.563 | 0.11633 / 0.08514 |
| Bright, long | 364.795 / 366.550 / 366.556 | 0.11790 / 0.08638 |

Both CPUs were freshly executed for 96,000 samples per setting. Before means
the previous 47.65 Hz pitch increment, with its old Decay range. All five raw
residuals improve, but none is declared a fidelity pass. Dark/short still has
a roughly 4 ms positive-peak fit difference; initial pitch/excitation, phase,
Tone/loading and the uncalibrated interior curve remain visible limitations.
Detailed measures and executable/source hashes are retained locally in
`out/reference/808-decay/measurements.json`. No fitted gain, onset alignment,
held-out audio or changed fidelity tolerances were used. The HTML is unchanged.

Across the full two-second comparison, maximum analytical errors are
1.478e-6 FS (ColdFire), 4.748e-7 FS (SHARC), and 1.714e-6 FS between CPUs, below
the existing 1e-5 FS numeric limit. These are numeric-model checks, not a
software-reference acceptance tolerance.
