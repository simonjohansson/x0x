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
separately for native installed-mod checks. Current runs are in progress;
component/native results will be recorded here before this increment is accepted.

VST references (#2) and physical-device testing are outside this increment.
