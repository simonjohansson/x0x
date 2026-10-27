# Digitone combined x0x controls: approved saved layout

**One x0x mod contains both engines**, selected per sound/track with MODEL.
Mixed 808/909 voices must coexist in the same installed build. The earlier
separate ID-80/ID-90 engine proposal is superseded. See the
[common product contract](render-contract.md#one-combined-mod-on-every-device).

**The user explicitly approved this combined ID/layout on 26 October 2026,
then revised it to remove LEVEL, move the sound controls to A/B/C and keep
MODEL in F. The table below is the current approved layout.**
Implementation and emulator acceptance belong to
[#40](https://github.com/simonjohansson/x0x/issues/40). Approval does not establish
working native defaults or persistence. Scope: DN OS 1.44,
Elekloader PR #200 pin `2ab5f424c4721e4277d2112a5ae755d9938f50d6`.

## One registration and shared controls

Use the approved shared ID **80**, name `X0X KICKS`; ID 90 is unassigned.
Check the selected mods' `dnmachine:<id>` resources before adoption. Native
sound slot 0 stores the one identity as `id << 8`; MODEL stores the chosen drum.

Use 16 native knob entries, with SYN1 blank and no `DNM_PAGES2` or extra saved
slots. Keep one static shared page layout:

| Position / knob index | Parameter ID / sound slot | Label and meaning | Raw default |
| --- | --- | --- | --- |
| SYN2 A / 8 | 119 / 27 | `TNTUN`, 808 Tone / 909 Tune | 16384 (64) |
| SYN2 B / 9 | 120 / 28 | `DECAY`, selected model's decay | 16384 (64) |
| SYN2 C / 10 | 121 / 29 | `ATTK`, 909 attack; ignored in 808 | 16384 (64) |
| SYN2 D / 11 | 122 / 30 | blank | -1 (unchanged) |
| SYN2 E / 12 | 123 / 31 | blank | -1 (unchanged) |
| SYN2 F / 13 | 124 / 32 | `MODEL`, 808/909 selector | 0 (808) |
| SYN2 G–H / 14–15 | 125–126 / 33–34 | blank | -1 (unchanged) |

All used positions have verified native range 0..32512. Records 119..122
map to slots 27..30; record 124 independently verifies slot 32, min 0,
max 32512 and original FM default 8192. The stock table at `0x4018d454` has
60 bytes per record and SHA-256
`d1c4f7627bdb3a78fec01bbdfaee265a618c69c89f01fe89182efef59a6fc2b1`.
The verified SysEx hash is
`d4f200d04484333d82822db7744e6484d0def8f2db8ddf55ee2b780cc13c9659`.

Use native numeric formatting and the plain knob look. Every unused entry has
NULL name and default -1. Blank words remain native saved data, not guaranteed
zero. Initial defaults are control positions rather than calibrated Roland
presets; no strength/accent control is introduced.

## Per-voice policy and native limits

Apply the [common selector policy](render-contract.md#one-combined-mod-on-every-device):
quantize delivered MODEL at raw 16384, latch at the next trigger/START and clear
only that voice's old model tail when the model changes. Preserve other voices,
including simultaneously active voices using the other model. Same-model
retrigger follows the circuit's separately tested residual-state policy.

Descriptor flags stay 0: the companion applies AMP and velocity once; neither
`DNM_OWN_ENV` nor `DNM_PAGES2` is enabled. Intrinsic kick decay remains a model control. Native track level handles
volume, with fixed internal output calibration and no x0x LEVEL knob. Ordinary note pitch does not make the stock 808 chromatic, and
909 Tune is not semitone transpose.

`set_knobs` applies defaults when selecting a different native machine, not on
same-machine reselection. Switching 808/909 uses MODEL inside x0x, so it must
not invoke machine-selection defaults or overwrite saved controls. Native
selection, reset, FM/x0x switching and save/load still need emulator coverage.

The delivery work formerly tracked in [#75](https://github.com/simonjohansson/x0x/issues/75)
now belongs to #40, including MODEL: `dnm_knob` currently supplies target words rather
than the observed final smoothed/controller/LFO frame. C-only declaration tests
do not resolve that transport gap. Connect the existing tested private
final-frame reader to the installed mod as part of #40.

## Small test increments

1. Test the one descriptor, both control interpretations, blanks, distinct
   fractions/endpoints and selector policy without either renderer.
2. Resolve final-frame delivery, then test native control and MODEL ramps,
   locks, threshold crossings, per-voice latching and unrelated-track isolation.
3. Round-trip the single identity, MODEL and controls through sound/kit saves.
   Model changes must not select another native machine or reset all controls.
4. Add each body to the same mod. Test mixed 808/909 voices as soon as both are
   present, including companion gain and voice limits. Complete qualification
   requires both models and their coexistence, not one-engine artifacts.

## Inspected sources

- [Pinned DN machine SDK](../vendor/elekloader/elekloader/sdk/include/digitone-mk1/machines.h): descriptor fields, 16-knob/default arrays, flags and ranges.
- [Actual companion](../vendor/elekloader/mods/machines-dn1/machines.c): `knob_id`, `param_rec`, `dnm_knob_range`, `set_knobs`, `machines_pick`, `dnm_render`, `envelope`.
- [Core OS 1.44 parameter-table export](../vendor/elekloader/mods/core-dn1/mod.json), [verified firmware manifest](../firmware/manifest.json), [native probe and table extraction](../tools/x0x/digitone_adapter.py), [current evidence limits](development.md).
- [SDK DN sine example](../vendor/elekloader/examples/dn-sine-machine/sine.c) supplies the real DN descriptor pattern. ModelDigi's inspected `machines/digitone/README.md` is still a placeholder and points to that example; its implemented Digitakt layout must not be copied as a DN range/layout contract.
