# Private instrument and render contract

This is the development contract for [issue #4](https://github.com/simonjohansson/x0z/issues/4).
It defines one instrument behavior for the ColdFire and SHARC+ implementations.
It does not define a firmware ABI, permanent machine ID or saved-sound format.
The [research](kick-drum-research.md) remains the source for the circuit model;
the [implementation plan](implementation-plan.md) assigns its implementation.

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
| 808/909 Level | Linear amplitude gain, with `0` muted and `1` the calibrated nominal maximum | One fixed instrument-to-digital calibration; no normalization per hit |
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
pulse. The development dependency is pinned to Elekloader PR #200 at
`2ab5f424c4721e4277d2112a5ae755d9938f50d6`, including its matching voice header
and adapter. The DN2 foundation must exercise this exact boundary; a merge or
matching textual ABI name alone is not evidence of compatibility.

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
[pinned Digitone adapter explanation](https://github.com/irpina/elekloader/blob/c150ac583a4b7e6d64680d5592f4a40f409193f7/docs/ADAPTING.md#L1747-L1839)
and [inspected DN2 callback](https://github.com/irpina/elekloader/blob/2ab5f424c4721e4277d2112a5ae755d9938f50d6/docs/MACHINES-DN2-VOICE.md#L71-L98).

Permanent machine IDs, native control slots/defaults, saved control layouts,
model selection and active-tail switching remain proposals for their respective
device tickets. No IDs or positions are reserved here. A combined selector
requires reviewed quantization, switch timing and state-clearing behavior before
it can become persistent. Until then, fixtures select one model explicitly.

The following are concrete **review candidates**, not registrations or saved
layout commitments:

| Device | 808 candidate ID | 909 candidate ID | Proposed control order |
| --- | --- | --- | --- |
| Digitakt | 80 | 90 | Level, Tone/Tune, Decay, 909 Attack, trigger strength |
| Digitone | 80 | 90 | Same semantic order; choose native slots after checking their unequal stock ranges |
| Digitone II | 20 (shared) | 20 (shared) | One native SYN page with a MODEL selector; see the selected packaging direction and exact review candidate below |

These values fall inside the pinned SDK's namespaces (DT 4–127, DN 1–127,
DN2 5–31). Check resource conflicts with every selected mod before approval.
The UI tickets must present actual slots, labels, defaults and raw ranges for
review; in particular, DN's existing ratio/algorithm slots cannot be assumed to
behave like a full-range continuous knob. The trigger-strength path remains
subject to the adapter's accent/velocity trace. No candidate appears in a
firmware descriptor, and the private C enums are unrelated to these IDs.
The [DN2 packaging proposal](dn2-packaging-proposal.md) expands its candidates
and coexistence limits for review; it does not approve them.

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

VST captures and calibrated timbre tolerances remain deferred reference work.
This contract allows diagnostic and analytic tests to proceed without claiming
an implemented kick, measured polyphony or original-hardware fidelity.
