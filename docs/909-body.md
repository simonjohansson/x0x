# First 909 triangle body

This [#25](https://github.com/simonjohansson/x0x/issues/25) increment adds an
unshaped triangle foundation to the existing combined mod. It is not yet a
complete or calibrated 909. The stock pitch path, diode shaping, VCA/envelopes,
Attack pulse/noise and circuit retrigger behavior remain open in #25/#79.
The existing controls/IDs and START-latched MODEL selection stay unchanged.

## Source boundary and provisional model

Roland service notes S02 p.4/p.11 and Whittle S05 p.3/p.12 identify a triangle
relaxation oscillator around IC13, then antiparallel diode shaping at D10/D11
through R52=10 kΩ. The original schematic, not the 909-like Plaits class, is
the selected baseline. Source hashes/paths are recorded in
[research/manifest.json](../research/manifest.json).

This first slice implements only the triangle waveform. The fixed 50 Hz pitch,
250 ms amplitude decay, internal gain 0.25 and zero-crossing phase restart are
explicitly provisional audition values, not values derived from the complete
Roland VCO/trigger/VCA. Unlike 808's resonant feedback loss, this amplitude
multiplies a separate oscillator. Native AMP/velocity, filtering, effects and
track volume remain downstream.

At 48 kHz, the independent analytical reference is

`y[n] = 0.25 * exp(-(n+1)/12000) * (2/pi) * asin(sin(2*pi*50*(n+1)/48000))`.

Each ASM backend uses a wrapping unsigned 32-bit phase accumulator with step
`round(50*2^32/48000)=4473924`, then folds it into a triangle and multiplies by
the decaying amplitude. Starting phase 0x40000000 in the folded representation
corresponds to a rising zero crossing. Phase/amplitude advance before each
output sample. Ordinary note pitch does not transpose this prototype.

The two body words are private per-voice state, reused between selected models;
MODEL switching clears the selected voice's old state. Every START currently
restarts the prototype's phase and amplitude. This does not claim the physical
909's clamp-release or free-running behavior. The 808 retains its separate
Tone history and existing live Tone/Decay behavior.

909 TNTUN, DECAY and ATTK are delivered but do not yet shape this first body.
The stock Tune controls pitch-envelope time, not chromatic transpose; deriving
that path is a later increment. The raw triangle also lacks the diode stage's
harmonic rounding and an antialiasing qualification.

## Independent and integration checks

[`body909.py`](../tools/x0x/body909.py) uses trigonometric triangle evaluation,
independent of the ASM integer phase folding. Host tests establish frequency,
gain/decay, onset and the odd-harmonic spectrum. Actual CPU tests compare
unshifted 24000-sample renders to this reference and each other under the
existing 1e-5 FS bound; no gain fit, normalization or alignment is allowed.

Run `mise run test` for host/C checks, `mise run test:909:body` for both actual
ASM implementations and cross-CPU comparison, and `mise run test:{dt,dn,dn2}`
separately for native installed-mod checks. The independent model is committed
in `5cb8a73`, and actual ASM/C routing in `6b3e05e`.

111 host tests and all independent C/UI suites pass. The actual 24000-sample
renders give:

| Check | ColdFire | SHARC+ |
| --- | --- | --- |
| Maximum reference error | 5.243e-7 FS | 4.673e-7 FS |
| Measured frequency | 49.999997 Hz | 49.999997 Hz |
| Fitted amplitude time constant | 0.249998572 s | 0.249999278 s |
| Maximum instructions per 909 block | 711 including test wrapper | 734 |

The two CPU outputs differ by at most 2.129e-7 FS. Both retain state/output,
callee/context and retrigger/interleaving guards. The combined SHARC callback
passes 4686 component calls with 914 code bytes, unchanged 320 state bytes and
overall worst 827 instructions under the unchanged 1000-instruction bound.
The 808 path and its Tone/Decay comparisons remain checked by that same suite.

The actual ColdFire four-second run exposes a known fixed-point limit: the
nearest-even envelope settles at 6022 Q31 LSBs, producing a peak residual of
2.805e-6 FS. This is bounded below the existing 1e-5 FS numeric limit, not exact
tail silence. Revisit the tail policy when implementing the stock VCA/envelope;
do not infer a physical 909 noise floor from integer arithmetic.

Native installed-mod checks retain the existing 808 Tone/Decay, controls,
lock/LFO, persistence, MODEL latching and unrelated-stock-output checks.
Component passes alone do not prove those native paths or downstream audio.

| Device | First 909 native evidence | Full native regression |
| --- | --- | --- |
| DT 1.54 | 23200 raw samples at the actual C/ASM boundary match the oracle within 5.243e-7 FS; isolated post-START PCM peak 3306/32768; 123 callbacks contain nonzero 808 and 909 tracks together | 32108 callbacks complete; only deferred #78 parameter/page reset checks fail |
| DN 1.44 | Native run in progress | Final isolated capture under investigation |
| DN2 1.12 | Native run in progress | Combined controls/audio regression pending |

DT's representative p-lock check obtains its exact expected value from the
native held-step DECAY display and requires that word in the render callback,
with the saved base unchanged. It does not assume a fixed result from relative
encoder acceleration. The tested lock is raw 24064 and the base remains 16384.

DT captures are `out/dt/silent/{raw,native}-909.wav`. Its firmware SHA256 is
`df8bf16ac6521a4758b9892a8a5a9a520484e94a9b599f4ab45fa88f726f60d0`.

VST references (#2) and physical-device testing are outside this increment.
