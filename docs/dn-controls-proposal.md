# Digitone stock kick controls: review proposal

**Nonbinding draft for [#63](https://github.com/simonjohansson/x0z/issues/63)
and [#67](https://github.com/simonjohansson/x0z/issues/67), 26 October 2026.**
Exact IDs and saved positions require user review before implementation. This
document changes no source, registration, API or persisted layout. Scope:
Digitone OS **1.44**, Elekloader PR #200 head
`2ab5f424c4721e4277d2112a5ae755d9938f50d6`.

Propose separate machines **80: `X0Z 808`** and **90: `X0Z 909`**, retaining
the [private contract's](render-contract.md) candidate IDs. Check conflicts
with every selected mod's `dnmachine:<id>` resource before adoption. Native
sound slot 0 holds `id << 8`; this is a saved identity, not the private C enum.

## Minimal page candidate

Declare **16** `dnm_knob` entries: SYN1 A–H blank; SYN2 A–C used for both
machines, D used only for 909, E–H blank. Labels are at most five characters,
with `fmt = NULL` for the native numeric display and `look = 0` for the SDK's
plain knob. Use no `DNM_PAGES2`, extra page or new sound slots.

| Position / knob index | Stock parameter ID | Native sound slot | Verified raw bounds | 808 label / meaning / default | 909 label / meaning / default |
| --- | --- | --- | --- | --- | --- |
| SYN2 A / 8 | 119 | 27 | 0..32512 | `LEVEL` / instrument gain / `100 << 8` | `LEVEL` / instrument gain / `100 << 8` |
| SYN2 B / 9 | 120 | 28 | 0..32512 | `TONE` / output tone network / `64 << 8` | `TUNE` / stock pitch-control path / `64 << 8` |
| SYN2 C / 10 | 121 | 29 | 0..32512 | `DECAY` / resonator feedback / `64 << 8` | `DECAY` / tonal amplitude decay / `64 << 8` |
| SYN2 D / 11 | 122 | 30 | 0..32512 | blank, ignored; default `-1` | `ATTK` / pulse/noise branch level / `64 << 8` |

Every other `dnm_knob.name` is NULL and its `int16_t defaults[16]` entry is
**-1**, meaning leave its native value unchanged. Blank words remain saved
native data; they are not guaranteed zero or available for silent reuse.
The declared defaults are **25600** for LEVEL and **16384** for the other
controls, not calibrated Roland presets. LEVEL means linear gain 100/127;
64 is position 64/127 of the eventual circuit mapping.

These bounds were read independently from all four parameter records in the
verified stock image, not inferred from UI names. The record table is at
`0x4018d454`, 60 bytes per record: words 1/2/3 contain sound slot/min/max.
Their original FM defaults are respectively **0, 8192, 32512, 0**; the machine's
proposed defaults deliberately replace those on selection. The 134-record
table SHA-256 is
`d1c4f7627bdb3a78fec01bbdfaee265a618c69c89f01fe89182efef59a6fc2b1`;
the verified OS image SHA-256 is
`d4f200d04484333d82822db7744e6484d0def8f2db8ddf55ee2b780cc13c9659`.

The companion's `knob_id`, `dnm_knob_range()` and `set_knobs()` agree with this
mapping. Selecting a **different** machine applies its nonnegative defaults
through `core_sound_set(track, record[1], value)`, then sets slot 0. Selecting
the same machine does not reset controls. Returning to FM restores its first
16 knob defaults. Second-page defaults are restored when leaving a machine
that had `DNM_PAGES2`; these candidates do not take those pages. Defaults on
selection do not prove save/load behavior or migration of existing sounds.

## Sound policy and remaining gates

Set descriptor **flags = 0**: `DNM_OWN_ENV` stays off so the companion applies
its AMP envelope **and velocity** after the machine render. Turning that flag
on bypasses both, not just the envelope. The kick's LEVEL and intrinsic decay
remain model controls; native AMP/filter/mixer processing stays a separate
integration check. No additional velocity gain or strength/accent knob is
proposed while the circuit excitation mapping remains unresolved.

Ordinary note pitch must not make the stock 808 chromatic. Keep 909 Tune's
circuit meaning rather than treating it as semitone transpose. A pitch change
must not alter these control positions; test the stock-mode pitch policy
independently of voice pitch telemetry and trigger strength.

[#75](https://github.com/simonjohansson/x0z/issues/75) does **not** block
standalone C declaration/default/mapping tests. It **does** block native
control acceptance: the bounded smoother probe observes delivered values
`370, 730, 1078, 1416, 1744, 2062, 2370, 2670`, while the current accessor path
keeps returning target `12345`. Do not present target-buffer edits as final
smoothed/locked/LFO control delivery or bypass the missing route with injected
delivered frames.

After user approval, take these steps separately:

1. Compile real C descriptors and test all 16 entries, defaults, flags and
   semantic bindings with native-service fakes. Use distinct A/B/C/D values,
   endpoints and fractional raw words; verify exact `(raw-min)/(max-min)`,
   invalid-frame atomicity, ignored blanks and no invented strength control.
2. Resolve #75, then select each machine through the emulator's native menu.
   Independently inspect sound slots and final render values for selection,
   same-machine reselection, encoder/MIDI edits, reset, locks and LFO ramps.
   Verify every callback's track/voice identity and unrelated-track isolation.
3. Qualify sound/kit save/reload/copy, FM/808/909 switching, and missing-mod
   loading without overwriting the only saved copy. Add the first audible
   selected-voice slice only after its transport is established; check buffer
   guards, stock-voice coexistence and exactly-once companion AMP/velocity
   separately from kick fidelity.

## Inspected sources

- [Pinned DN machine SDK](../vendor/elekloader/elekloader/sdk/include/digitone-mk1/machines.h): descriptor fields, 16-knob/default arrays, flags and ranges.
- [Actual companion](../vendor/elekloader/mods/machines-dn1/machines.c): `knob_id`, `param_rec`, `dnm_knob_range`, `set_knobs`, `machines_pick`, `dnm_render`, `envelope`.
- [Core OS 1.44 parameter-table export](../vendor/elekloader/mods/core-dn1/mod.json), [verified firmware manifest](../firmware/manifest.json), [native probe and table extraction](../tools/x0z/digitone_adapter.py), [current evidence limits](development.md).
- [SDK DN sine example](../vendor/elekloader/examples/dn-sine-machine/sine.c) supplies the real DN descriptor pattern. ModelDigi's inspected `machines/digitone/README.md` is still a placeholder and points to that example; its implemented Digitakt layout must not be copied as a DN range/layout contract.
