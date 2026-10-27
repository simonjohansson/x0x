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
DN/DN2 native runs and the fresh two-second five-setting comparison are pending
at this code increment; component passes do not claim those results.
