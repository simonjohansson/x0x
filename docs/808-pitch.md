# 808 settled-body pitch

This #9/#2 increment changes the provisional body from 55 Hz to **47.65 Hz**
on ColdFire (DT/DN) and SHARC (DN2). It uses the rounded settled-body frequency
in the [initial five-setting training diagnostic](808-reference-baseline.md).
The approved default and long-Decay recordings settle near 47.65 Hz; the shorter
hits have lower whole-hit median estimates, about 46.67 Hz. One shared frequency
is used at every setting; no corner-specific pitch or per-hit gain is fitted.
Held-out settings are not used.

This corrects the prototype's settled pitch only. It is not the full
source-derived bridged-T resonator or the initial changing pitch. The short-hit
frequency difference, pitch sigh, nonlinear forcing, stock Decay feedback/pot
mapping and residual-state retrigger remain open in #9/#79. Saved IDs, controls,
MODEL policy, internal drive and Decay mapping stay unchanged.

## Coefficients

Let `w=2*pi*47.65/48000`. Keep the existing Decay-dependent retention `r` and
use `c=r*cos(w)`, `s=r*sin(w)` in the existing rotation. Update both the real
and imaginary coefficients together so the angle changes while the intended
pole radius/Decay remains the same. The analytical finite-pulse convolution
uses that same declared physical frequency, without copying the ASM recurrence.

ColdFire uses Q1.31 endpoint/interpolation coefficients:

| Coefficient | Minimum | Maximum-minus-minimum |
| --- | --- | --- |
| c | 2147126590 | 270547 |
| s | 13392598 | 1688 |

SHARC retains its small-delta representation `a=c-1`, avoiding near-one
float32 coefficient bias. The corresponding float32 words are:

| Coefficient | Minimum | Maximum-minus-minimum |
| --- | --- | --- |
| a | 0xb92e5840 | 0x39041a51 |
| s | 0x3bcc5ad6 | 0x3552f0ab |

The DN2 native Tone-state check now reads the declared model frequency rather
than assuming 55 Hz. This changes the expected physical pole, not the test's
error limit. Production state size, code length and control delivery are unchanged.

## Validation and remaining work

The original HTML and its baseline measurements remain historical and untouched
at the user's request. New five-setting float renders and measurements belong
under `out/reference/808-pitch/`; never overwrite `808-baseline` for this increment.
Keep primary timing and gain conventions from the initial diagnostic: scheduled
MIDI at zero, one fixed reference ×4 to undo the documented host gain, no fitted
gain, onset alignment or normalization. The numerical 1e-5 FS CPU/oracle limit
remains separate from any VST-fidelity criterion.

Run `mise run test:808:body` for both actual ASM backends and matching composed
outputs, and `mise run test` for the host/C boundaries. Native checks remain
`mise run test:dt`, `mise run test:dn`, and `mise run test:dn2`, using emulators
only. Their downstream/native evidence is separate from raw component renders.
The known #78 DT reset and #80 late DN2 MODEL delivery gates remain open; #20's
historical DN residue must not be declared fixed by a changed waveform.

The changed component suites pass: 120 host tests, independent C/UI tests,
and 8,820 shared SHARC callback cases, including existing 909 behavior. Matching
composed renders retain the original 1e-5 FS limit: maximum errors are
1.750e-6 FS (ColdFire), 1.552e-6 FS (SHARC), and 1.844e-6 FS between CPUs.
Raw ColdFire body frequency is 47.650004 Hz with a 250.000885 ms default decay.
SHARC composed output measures 47.653061 Hz over its shorter test window;
its Tone/C47 transient is included and agrees with the independent oracle.

The installed DT build's functional checks pass across 39,446 callbacks;
only known #78 parameter/page resets fail. Its unnormalized native PCM measures
47.652534 Hz. Firmware SHA256:
`85336d6d305e9495c437a821a61dff60dc96f241ae2fa0160b35dfad0c9c221b`.
The DN native functional checks also pass across 100,792 callbacks and its
unnormalized downstream PCM measures 47.641554 Hz. Overall acceptance remains
failed on the historical #20 `tone_bright_exact_zero_baseline`: one PCM16 count
persists for six seconds. The waveform change did not fix that gate. Firmware
SHA256: `9fbe12bc4da0cab7b3b33a8dd222ec755fb055fe8a7a2a722d38e9897bc6b8a5`.

DN2's installed coupled-emulator scenario passes across 31,879 DSP frames,
with no halt or missing blocks. Native float PCM measures 47.650329 Hz. Native
controls, locks/LFO, reload, mixed models, Tone/coupling and 909 checks remain
passing in this scenario; the separate #80 late MODEL path is not qualified.
Firmware SHA256:
`892551cd08a12d89c2dc8508bc9b03e65608febf01820184a2efc010ee853823`.

## Fresh five-setting comparison

Both actual ASM backends were freshly rendered for two seconds per setting,
using the same fifteen hash-verified fresh reference takes and fixed host-gain
correction as the initial diagnostic. Full measurements, source/executable
hashes and float renders are in `out/reference/808-pitch/measurements.json`
and neighboring files. No alignment, normalization or per-hit gain fit is used.

| Setting | Reference median Hz | ColdFire Hz | SHARC Hz | Unaligned residual RMS FS, before / after pitch correction |
| --- | --- | --- | --- | --- |
| Default | 47.64380 | 47.65001 | 47.65000 | 0.06474 / 0.03154 |
| Dark, short | 46.66961 | 47.65009 | 47.65001 | 0.03820 / 0.03422 |
| Bright, short | 46.67983 | 47.65008 | 47.65001 | 0.03916 / 0.03503 |
| Dark, long | 47.65359 | 47.65000 | 47.65000 | 0.10987 / 0.11633 |
| Bright, long | 47.65360 | 47.65000 | 47.65001 | 0.11168 / 0.11790 |

The default waveform residual roughly halves, and both short corners improve
slightly. **Both long-corner raw residuals worsen**, despite the much closer
settled pitch. This is retained as a mismatch, not normalized or phase-fitted
away. Pitch agreement alone cannot establish waveform fidelity; the initial
pitch/forcing, phase evolution and overly long tails still differ. Short hits
retain about a 0.98 Hz median discrepancy, so this does not close the full
pitch-path work. Decay remains the next independent calibration/model issue.

Across these full two-second renders, maximum analytical errors are
2.142e-6 FS (ColdFire) and 2.021e-6 FS (SHARC); cross-CPU difference is
2.511e-6 FS. These still pass the unchanged 1e-5 FS numeric limit. They are
not VST-fidelity tolerances, and the long-corner regression is not a pass.
