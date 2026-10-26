# Digitakt combined x0z controls: approved saved layout

The product direction is **one x0z mod containing both 808 and 909**, with a
saved MODEL selector per sound/track. Different tracks can play both models
concurrently. This supersedes the earlier two-machine proposal and its approval;
IDs 80/90 must not become separate engine registrations. See the
[common product contract](render-contract.md#one-combined-mod-on-every-device).

**The user explicitly approved this combined ID/layout on 26 October 2026.**
Implementation and emulator acceptance belong to
[#39](https://github.com/simonjohansson/x0z/issues/39). Approval does not establish
working native defaults or persistence. Scope: DT OS 1.54, Elekloader PR #200 pin
`2ab5f424c4721e4277d2112a5ae755d9938f50d6`.

## One native registration and page

Use the approved shared ID **80**, name `X0Z KICKS`, short name `KICKS`.
Both models use that identity; ID 90 is unassigned. Check conflicts with every
selected mod before adoption. Device-specific builds still contain both engines.

Use one legacy `cm_ui_v3` SRC page with `.params = 3`, `.page_from = 3`,
`.render = id` and `CM_UI_TAG`, borrowing SLICE's existing positions as in
ModelDigi. No `cm_ui32` extras or new saved storage are proposed.

| Knob / accessor index | Native sound slot / parameter ID | Label and meaning | Display default |
| --- | --- | --- | --- |
| A / 0 | 17 / 132 | `LEVEL`, instrument gain | 100 |
| B / 1 | 18 / 133 | `TNTUN`, 808 Tone / 909 Tune | 64 |
| C / 2 | 19 / 134 | `DECAY`, selected model's decay | 64 |
| D / 3 | 20 / 135 | `ATTK`, 909 attack; ignored in 808 | 64 |
| E / 4 | 21 / 136 | hidden | none |
| F / 5 | 22 / 137 | `MODEL`, 808/909 selector | 0 (808) |
| G–H / 6–7 | 23–24 / 138–139 | hidden | none |

Declared words use `CM_RANGE | CM_DEFAULT`, raw 0..32512, with defaults
`display << 8`: LEVEL 25600, Tone/Tune/Decay/Attack 16384 and MODEL 0.
Use the generic knob look `0x86`. D requires `CM_NOT_SAMPLE` to keep SRC
cycling out of the waveform view. E/G/H use `CM_HIDDEN` with no semantic
binding or range/default override; their stored words need not be zero.
The static shared label `TNTUN` fits the SDK's five-character limit.

## Selection, delivery and remaining checks

The selector follows the [common policy](render-contract.md#one-combined-mod-on-every-device):
raw below 16384 selects 808, otherwise 909; latch at the next delivered trigger,
clear only that voice's old model state on a model change, and keep other
tracks' models/tails unchanged. Same-model retrigger is a separate circuit
policy. Both kernels must coexist in the same build and handle mixed tracks.

`cm_src_value` sign-extends the final native word; it does not clamp or
normalize it. Validate declared ranges and retain exact fractions. Native
locks, smoothing, LFOs and selector threshold crossings require emulator tests.
Stock 808 note pitch must not introduce chromatic tuning; 909 Tune retains its
circuit meaning. There is no strength knob; velocity/accent and downstream AMP
remain separate integration work.

Defaults remain a concrete SDK qualification concern: `mp_range` handles
`CM_DEFAULT`, but `mp_reset_range` gates its override on `mp_ui32`, and
`mp_sound_defaults` handles extended pages only. Prove actual selection/reset
behavior for this legacy page; do not invent a switch callback that overwrites
loaded sounds or add saved slots to conceal the gap.

## Small test increments

1. Test the single production descriptor/page, both model interpretations,
   exact endpoints/fractions, blanks and selector policy with fake services and
   a fake DSP. Neither audio renderer is needed for these C checks.
2. Test selection/defaults/reset, native encoder/MIDI/lock/LFO delivery and
   per-track selector latching with diagnostic ASM in digiemu.
3. Round-trip MODEL and controls through sound/kit save/reload/copy. Check
   model switching during tails and that another track's mode/state is unchanged.
4. Integrate each first body into this same mod. As soon as both bodies exist,
   play mixed 808/909 tracks from one installed artifact and keep that regression
   through later slices. Full qualification requires both engines.

The existing native observer has no machine registration and does not qualify
the approved layout, persistence, defaults or replacement audio path.

## Inspected sources

- [Pinned SDK C declarations](../vendor/elekloader/elekloader/sdk/include/digitakt-mk1/core3.h): `cm_machine`, `cm_ui`, knob flags, native slot macros and render accessor declarations.
- [Page layout/ranges/cycling](../vendor/elekloader/mods/machine-pages/pages.c): `ID_BASE`, `mp_layout_track`, `mp_range`, `mp_src_key`, `mp_lfo`, `mp_tick`; [native range hooks](../vendor/elekloader/mods/machine-pages/pages.s).
- [Actual accessor and extended-page validation](../vendor/elekloader/mods/machine-pages/src.c): `cm_src_value`, `valid`, native/extended save paths; [extended defaults](../vendor/elekloader/mods/machine-pages/params.c): `mp_sound_defaults`.
- [Core machine registration/render mapping](../vendor/elekloader/mods/core/machines.s): descriptor fields, `core_mparams`, `core_mrender`.
- [ModelDigi pattern](https://github.com/simonjohansson/ModelDigi/blob/c412bdf2ab3b0b5b62484e8195c2f880d1964c67/machines/digitakt/modeldigi.c): SLICE bank, explicit ranges/defaults, `CM_NOT_SAMPLE`, hidden/blank positions and native render event. Its extra-value layout is not copied into this smaller proposal.
- [Shared semantics and approved IDs](render-contract.md), [research on original controls](kick-drum-research.md), [current emulator evidence](development.md).
