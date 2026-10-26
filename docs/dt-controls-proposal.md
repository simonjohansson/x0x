# Digitakt stock kick controls: review proposal

**Nonbinding draft for [#55](https://github.com/simonjohansson/x0z/issues/55)
and [#59](https://github.com/simonjohansson/x0z/issues/59), 26 October 2026.**
The candidate IDs and saved positions below require user approval before
implementation. This document assigns nothing and changes no API, descriptor,
firmware registration or persisted layout. Scope: Digitakt OS **1.54**, pinned
Elekloader PR #200 head `2ab5f424c4721e4277d2112a5ae755d9938f50d6`.

Use separate candidate machines **80: `X0Z 808` / `808`** and
**90: `X0Z 909` / `909`**, as proposed in the [private render contract](render-contract.md).
Check resource conflicts against every selected mod before adoption; being
inside the SDK's 4–127 range does not establish that an ID is available.

## Smallest layout candidate

One SRC page per machine, using `struct cm_machine` with `.params = 3`,
`.render = id`, `.tag = CM_UI_TAG`, and a `struct cm_ui` with
`.abi = cm_ui_v3`, `.page_from = 3`. This borrows SLICE's eight native SRC
positions and UI machinery, as ModelDigi does. It proposes no extra sound
slots, second page, model selector, custom persistence format or new MIDI CCs.
The render subscriber would make the selected track's audio separately.

| Position | Accessor index | Native sound slot / byte offset | Parameter ID in bank 3 | 808 label / meaning / default | 909 label / meaning / default |
| --- | --- | --- | --- | --- | --- |
| A | 0 | 17 / `0x36` | 132 (`0x84`) | `LEVEL` / instrument level / 100 | `LEVEL` / instrument level / 100 |
| B | 1 | 18 / `0x38` | 133 (`0x85`) | `TONE` / output tone network / 64 | `TUNE` / stock pitch-control path / 64 |
| C | 2 | 19 / `0x3a` | 134 (`0x86`) | `DECAY` / resonator feedback / 64 | `DECAY` / tonal amplitude decay / 64 |
| D | 3 | 20 / `0x3c` | 135 (`0x87`) | hidden, ignored | `ATTK` / pulse/noise branch level / 64 |
| E–H | 4–7 | 21–24 / `0x3e`–`0x44` | 136–139 | hidden, ignored | hidden, ignored |

All declared controls propose **raw minimum 0, maximum `127 << 8` = 32512**,
using `CM_RANGE | CM_DEFAULT`; table defaults are display positions, stored as
`default << 8` (LEVEL **25600**, others **16384**). Use stock look **`0x86`**,
the generic knob look used by ModelDigi, and explicit long names `Level`,
`Tone`, `Tune`, `Decay`, `Attack`. For LFO names, use the same labels and names.
These initial positions are review choices, not calibrated Roland presets.
LEVEL 100 means **100/127** of the contract's linear instrument gain; position
64 means **64/127** of the eventual physical control mapping.

Mark every unused knob `CM_HIDDEN`, with no semantic binding and no default
or range override. D also needs `CM_NOT_SAMPLE` in **both** machines: visible
Attack on the 909, hidden on the 808. The pinned one-page SRC cycling path
uses D's flag to keep the page instead of opening the stock waveform view.
Hidden positions still have native backing words and may appear as `Unused`
in native LFO lists. Do not assume their words are zero, repurpose them as
version markers, or promise migration to future controls.

This intentionally uses the legacy eight-position page rather than
`cm_ui32`: the latter adds seven saved slots and its extended-value validation
and persistence behavior. ModelDigi needs that larger layout for its controls;
these kick pages do not. `CM_SRC_BLANK` belongs to the extended page map, so
this legacy candidate expresses empty positions with `CM_HIDDEN`.

## Delivery and sound policy

The proposed range comes from the explicit declarations above, **not** from
`cm_src_value()`. At this pin, indices 0–7 read the signed native
`fw_voice_params[53 * track + index]` word unchanged; the accessor neither
clamps nor normalizes it. The C adapter must validate the declared raw range
and pass the exact fraction **raw / 32512**, preserving delivered fractional
values such as raw 1. Native locks, smoothing and LFOs require emulator tests
against this actual layout before claiming that every path obeys its bounds.

`CM_DEFAULT` participates in the page's range/reset lookup. The separate
`mp_sound_defaults()` helper only handles extended `cm_ui32` pages, so it is
not evidence that a legacy machine selection or fresh sound initializes the
proposed words. Verify actual native selection/reset paths before adopting
this candidate; if the legacy path cannot satisfy them, review the smallest
necessary change rather than silently introducing extra persisted slots.

Stock **808 stays nonchromatic**: native note-pitch changes must not transpose
the resonator. The 909's Tune remains its circuit control, not semitone
transpose; this candidate adds no chromatic mapping. Tone/Decay and Attack
retain their [shared meanings](render-contract.md): Attack is branch level,
not ADSR attack time. Test note changes explicitly as unsupported pitch
modulation for stock mode.

There is **no strength/accent knob**. Native velocity/accent-to-excitation
mapping remains deferred until its delivered values and host gain behavior
are established. A fixed strength in a diagnostic fixture is not a production
policy. Instrument LEVEL and decay remain part of the DSP model; the native
AMP/velocity/filter pipeline is a separate integration concern. Do not apply
velocity twice or use the host AMP envelope as a substitute for kick decay.

## Tests after approval, in small increments

1. **Declarations without DSP:** compile each real page declaration against
   the pinned SDK. Check ID/name, every label/default/range, native slot and
   semantic binding; D's sample flag; all hidden positions; no extra slots.
   Fake native-service tests must preserve fractions and reject out-of-range
   words without partial delivery. Assert 808 note changes leave its model
   settings unchanged and no strength value is invented.
2. **Native controls with diagnostic ASM:** select each reviewed machine
   through the emulated panel; inspect defaults and reset, turn every declared
   encoder to endpoints, and prove hidden controls do not affect the receiver
   or open the sample browser. Read each stored native word independently of
   the callback; compare it with post-smoothing delivery. Exercise stock CC
   mappings, parameter locks and LFO values, including fractional values,
   without changing another track's settings.
3. **Persistence before kick integration:** save/reload/copy sounds and kits;
   compare IDs, raw words, labels and defaults. Switch stock/808/909 machines
   on different tracks, and test loading with the relevant registration
   absent. Keep the only saved copy intact; do not infer fallback behavior.
4. **First audible slice:** replace only a selected track's block through the
   existing render event. Check unrelated audio and buffer guards, native
   AMP/filter behavior and exactly-once gain separately from model timbre.
   Keep raw-kernel, emulator and eventual reference comparisons distinct.

Current native observer tests prove PLAY → START → C capture → ASM observation
with **no machine registration**. They do not qualify these proposed pages,
their persistence, pitch policy, replacement audio or strength mapping.

## Inspected sources

- [Pinned SDK C declarations](../vendor/elekloader/elekloader/sdk/include/digitakt-mk1/core3.h): `cm_machine`, `cm_ui`, knob flags, native slot macros and render accessor declarations.
- [Page layout/ranges/cycling](../vendor/elekloader/mods/machine-pages/pages.c): `ID_BASE`, `mp_layout_track`, `mp_range`, `mp_src_key`, `mp_lfo`, `mp_tick`; [native range hooks](../vendor/elekloader/mods/machine-pages/pages.s).
- [Actual accessor and extended-page validation](../vendor/elekloader/mods/machine-pages/src.c): `cm_src_value`, `valid`, native/extended save paths; [extended defaults](../vendor/elekloader/mods/machine-pages/params.c): `mp_sound_defaults`.
- [Core machine registration/render mapping](../vendor/elekloader/mods/core/machines.s): descriptor fields, `core_mparams`, `core_mrender`.
- [ModelDigi pattern](https://github.com/simonjohansson/ModelDigi/blob/c412bdf2ab3b0b5b62484e8195c2f880d1964c67/machines/digitakt/modeldigi.c): SLICE bank, explicit ranges/defaults, `CM_NOT_SAMPLE`, hidden/blank positions and native render event. Its extra-value layout is not copied into this smaller proposal.
- [Shared semantics and unadopted ID candidates](render-contract.md), [research on original controls](kick-drum-research.md), [current emulator evidence](development.md).
