# Private instrument and render contract

Implementation status: #9 is accepted as the fixed-strength/reset-on-START
baseline at `5963a34`. The intrinsic strength and residual-circuit semantics
below remain intended #79/#2 refinements, not implemented/passing behavior.
No saved layout, SDK field or lifecycle contract was changed by that acceptance.

This is the development contract for [issue #4](https://github.com/simonjohansson/x0x/issues/4).
It defines one instrument behavior for the ColdFire and SHARC+ implementations.
It does not define a firmware ABI, permanent machine ID or saved-sound format.
The [research](kick-drum-research.md) remains the source for the circuit model;
the [implementation plan](implementation-plan.md) assigns its implementation.

## One combined mod on every device

Digitakt, Digitone and Digitone II each run one x0x mod containing both engines
under one native machine identity. MODEL is saved per sound/track and latched
per active voice at its trigger boundary. Different tracks can therefore play
808 and 909 kicks concurrently in the same installed build. There is no global
selector that forces all voices to change model together.

The six device/model cells are independent test and development slices of this
product. They are not separate mods or single-engine firmware variants. Early
incomplete slices may be tested without the other renderer, but a device's
combined mod is not release-qualified until both models and their coexistence
pass. Exercise mixed-model voices as soon as both first bodies are available.

Use delivered MODEL values, not unsmoothed targets. The approved DN2 policy is
the common behavior to carry into the DT/DN combined-layout work: 808 below raw
16384, 909 from 16384, latched at the next delivered trigger/START; changing
model clears only that voice's old dynamic state before excitation. Same-model
retrigger preserves the circuit model's separately defined residual behavior.
Native trigger/ownership differences still require each adapter's tests.

## Settings and audio units

Shared settings describe the instrument, rather than a device's knob words.
All values and state observations must be finite. A normalized control position
is a unitless value in `[0, 1]`; its accepted model maps that position to the
physical circuit quantity. Native endpoint/fractional conversions belong to the
device adapter and must be tested before they feed this boundary.

| Setting | Shared meaning | Model work still required |
| --- | --- | --- |
| 808 Tone | Position in the stock output-tone network | Component/pot curve and network coefficients |
| 808 Decay | Position controlling the resonator feedback network | Feedback mapping and coupled decay behavior; it is not assumed to be seconds |
| 808/909 Level (reference/internal only) | Linear amplitude gain for model comparisons; production uses fixed calibration and native track level | No separate x0x LEVEL knob, extra saved gain or normalization per hit |
| 909 Tune | Position controlling the stock pitch-control path | CV/envelope time-course mapping; it is not semitone transpose |
| 909 Decay | Position controlling the tonal amplitude-decay path | Envelope/VCA mapping |
| 909 Attack | Level of the separate pulse/noise attack branch | Branch gain and stock pot curve; it is not ADSR attack time |
| Trigger strength | Normalized excitation/accent input latched at the trigger | One shared mapping to electrical excitation and accent-dependent circuit behavior |

The fixture records the model revision that defines these mappings. Later
calibration changes that revision and the independent oracle once; both CPU
backends consume the updated behavior and fixtures. Each backend may use a
different stable numerical realization of those same equations.

Stock 808 mode has no chromatic pitch control. Ordinary native note-pitch
changes must not silently add one. Likewise, stock 909 Tune retains its circuit
meaning. An unsupported native modulation path must be explicitly ignored or
rejected by its adapter policy, with a test.

Raw audio uses a fixed digital full-scale reference, where a sample magnitude
of `1` is full scale. The oracle retains finite excursions beyond that range so
the analyzer can report them. It must not clip or normalize them away to match a
backend. ColdFire output conversion to Q1.31 and SHARC float output conversion
are independently tested against the declared scale, rounding and saturation.
Coefficient ranges and intermediate headroom are backend-private; output
Q1.31 does not imply that every coefficient or state variable is Q1.31.

## Events and state ownership

An event has an absolute sample timestamp, a semantic kind, an owning voice
identity and the values needed by that kind. Events are applied immediately
before rendering the sample at that timestamp. Equal-timestamp events retain
their explicit sequence order; fixtures do not silently reorder them.
For example, reset, settings and trigger at sample `64` must appear in that
order if those are the intended operations.

| Operation | Required semantic effect |
| --- | --- |
| Reset | Clear the voice's dynamic audio/history state and initialize deterministic local random state. Settings remain the separately supplied settings. |
| Fresh trigger | Excite a quiescent, initialized voice using the current settings and latched strength. Tests establish the initial-state precondition explicitly. |
| Same-voice retrigger | Apply the model's new electrical excitation to the existing circuit state. Preserve residual state unless a particular circuit stage explicitly resets it. |
| Reassignment | End the old logical ownership, reset the reused storage and bind the new identity before accepting its events. A numeric firmware slot alone does not establish identity. |
| Parameter change | Change the named setting at its timestamp, preserving dynamic state unless the shared model specifies a particular state transition. |
| Silence | Continue advancing the model and its clocks. A silent output is a valid result, not an instruction to freeze or clear state. |

Fresh-trigger and retrigger are distinct test cases even if a native API exposes
only one start flag. A device adapter must not invent unavailable history or
track identity. It records its supported policy and leaves affected repeated-hit
fidelity open until allocator/event evidence supports it. Resetting every trigger
and preserving every reused slot are both insufficient general policies.

Voice storage belongs to the caller and remains bound to one logical voice for
the duration of that assignment. A render call may change only that voice's
owned state and the declared output extent. State persists across calls.
Rendering another voice between two calls must not change the first voice's
output for the same timestamped inputs.

Any genuinely shared process, such as the 909's continuous noise source, needs
an explicit engine-level clock/owner in its model slice. Its speed must not
depend on the number or order of voice callbacks. A seed and initialization
policy are part of deterministic fixtures; independent plugin noise uses
statistical reference comparisons.

## Render boundary and timing

The current three native paths use 48 kHz and 32-sample blocks. A private render
request declares its sample rate, absolute starting sample, output count,
settings/events and owned state. The renderer writes every output sample,
including intentional zeroes. Calls for a voice cover contiguous time unless
the caller explicitly resets or advances it according to a tested policy.

The host fixture can represent sample-accurate events. Each native adapter
records both the requested event time and the delivered event time supported
by its pinned firmware path. Direct kernel/oracle comparisons use identical
delivered events. Device integration separately reports requested-to-delivered
and delivered-to-audible timing; waveform alignment cannot erase either delay.

For DN2, the inspected callback has a silent trigger-edge block followed by a
block carrying `START`. It does not provide a separate accent field or track
identity. These are adapter constraints, not definitions of the analog trigger
pulse. The development dependency is now the validated upstream Elekloader
revision `b893c9317936633d7a32829b618c2867ee99277c`, recorded in
`firmware/manifest.json` and the submodule gitlink. This supersedes the earlier
PR200-only pin. Keep its matching voice header/adapter and exercise the exact
boundary; a matching textual ABI name alone is not compatibility evidence.

### Worked fixture

Use a test-only fixed model revision, 48 kHz, a named voice `A`, explicit
normalized settings and a trigger strength of `0.75`. Reset at sample `0`,
apply settings next at sample `0`, and trigger at sample `64`. Render four
32-sample blocks. The oracle, ColdFire runner and SHARC runner all receive that
same semantic sequence and full-scale convention. Their internal parameter
words, coefficient encodings and state layouts may differ. Compare each CPU
output with the independent oracle before comparing them with one another.

A separate adapter test may inject a request at sample `17` and a diagnostic
trace showing delivery at sample `64`. That fixture records a 47-sample delivery
delay and uses sample `64` for its kernel comparison. Those numbers are an
illustrative test trace, not a measured device latency or a universal rounding
rule. A different device's observed delivery time is recorded independently.

## Host processing and unresolved device decisions

Trigger strength describes the kick circuit's excitation/accent behavior.
Native MIDI velocity may also change host AMP gain or modulation; it must not
be blindly applied once as circuit strength and again as an assumed equivalent
gain. The adapter documents the actual delivered values and downstream gain.
The kick's own decay remains part of the instrument even when the host AMP
envelope shapes its output.

Digitone's replacement path runs on the main ColdFire, overwriting stock FM
audio. Its machine companion reapplies AMP/velocity unless `DNM_OWN_ENV` is
selected. DN2 applies stock AMP/filter processing downstream. Raw kernel tests
exclude those stages; device tests record their settings and behavior. See the
[pinned Digitone adapter explanation](https://github.com/irpina/elekloader/blob/b893c9317936633d7a32829b618c2867ee99277c/docs/ADAPTING.md)
and [inspected DN2 callback](https://github.com/irpina/elekloader/blob/b893c9317936633d7a32829b618c2867ee99277c/docs/MACHINES-DN2-VOICE.md#L81-L90).

The user explicitly approved all three combined saved layouts on 26 October
2026. Each uses one native identity for both engines and the shared START-latched
MODEL policy. Approval authorizes implementation; native defaults, persistence
and lifecycle still require emulator tests.

| Device | Shared ID | Approved layout |
| --- | --- | --- |
| Digitakt | 80 | One SRC page; [exact slots and defaults](dt-controls-proposal.md) |
| Digitone | 80 | One SYN2 page; [exact slots and defaults](dn-controls-proposal.md) |
| Digitone II | 20 | One SYN page; [exact slots and defaults](dn2-packaging-proposal.md) |

The latest explicitly approved positions are A TNTUN=64, B DECAY=64,
C ATTK=64, F MODEL=0, with D/E/G/H blank. This supersedes the earlier LEVEL
knob and B/C/D sound-control positions on every device. Native track level
handles volume; keep output calibration internal rather than adding a saved gain. These values fall inside the pinned SDK namespaces
(DT 4–127, DN 1–127, DN2 5–31); builds still check resource conflicts against
selected mods. Private C enums are unrelated to these native IDs. Trigger
strength remains subject to the adapter's accent/velocity trace; no extra saved
strength control is approved. Other stable API or persistence changes require
review.

## Independent acceptance

- C adapter/control tests use native-service fakes and a fake receiver to verify
  production declarations and conversions without either CPU renderer.
- Oracle tests use analytic/circuit expectations and explicit event sequences.
- CPU tests execute actual assembled instructions and check numeric error,
  output extent, state guards and ABI preservation without native UI.
- Each available backend passes against the oracle. A missing peer reports its
  cross-CPU comparison unavailable rather than blocking a valid independent run.
- Device tests check delivered events/values, routing and host processing.
  Physical qualification alone establishes measured deadline margin on the
  exact device/firmware workload.

Training recordings are available and both engines have a
[full-grid diagnostic baseline](full-reference-grid-baseline.md); subsequent
808 component/reference qualification is recorded with
[the lower-interior Decay correction](808-decay-shape.md), `5963a34`.
Calibrated timbre acceptance and held-out validation remain open. Diagnostic
agreement does not establish measured polyphony or original-hardware fidelity.
