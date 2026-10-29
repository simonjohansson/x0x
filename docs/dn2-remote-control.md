# Digitone II remote-control notebook

Recorded on 29 October 2026 for DN2 OS 1.12 and DigiHealth revision 3.
This is historical setup and navigation evidence, not authorization for a
new device action. Recheck the installed build, client checkout, current
project and relevant menu state before reusing it. Local paths and saved
slot contents may have changed.

These are DN2 OS 1.12 / DigiHealth revision-3 controls, verified during the
2026-10-29 investigation. Reuse a single MIDI port and `RemoteKeys` session
for each batch. Do not launch Python, fetch HELLO/STATS and render a PNG after
every button. Check once at a meaningful boundary; prefer memory readback for
machine, parameters and voice allocation. Key completion confirms delivery,
not completion of a project load or save.

- Use the matched DigiHealth client. This session's clean checkout is
  `/private/tmp/x0x-digihealth-dn2-support`, revision
  `afc751d67b1b1575f7a5fc40f104c11451fc3ea5`. Run Python with `mise`.
- `TRK(n)` selects track n; `SYN` opens its synth page; `VOICE` opens VOICE
  SETUP. `FUNC(VOICE)` does not open that page. Normal tests need **DYN (16)**
  and **UNISON STATE OFF**, not 16 locked voices or unison with 16 notes.
- From SYN, `FUNC(SYN)` opens the machine selector. The XP03 order is
  **FM TONE, FM DRUM, WAVETONE, SWARMER, X0X KICKS**. From confirmed FM TONE,
  `DOWN,DOWN,DOWN,DOWN,YES` selects x0x. From confirmed x0x,
  `UP,UP,UP,UP,YES` selects FM TONE. Allow the machine load to settle before
  opening another menu. XB00 has no x0x entry.
- From ordinary menus, successive `NO` presses return towards the main page.
  Do not use this as a reset while a save/load/update confirmation is open.
  SETTINGS remembers selection: do not assume its cursor is on PROJECT.
- From SETTINGS with PROJECT selected: `YES` opens PROJECT. Its rows are
  **LOAD PROJECT, SAVE PROJECT AS, MANAGE PROJECTS**. With LOAD selected,
  `YES` opens the populated-slot list. With SAVE AS selected, `YES` opens the
  destination list; selecting a destination opens a separate name screen,
  whose `YES` actually saves. Wait for SAVING to finish.
- In LOAD PROJECT, **CREATE NEW is the final unnumbered command**. Named
  `NEW PROJECT` entries in slots 126/127 are existing saved projects, not
  initialization commands. Handle the current-project save question and
  initialization separately; do not send extra YES/NO through an unseen
  transition.
- Test-slot policy: use one documented, verified-empty slot for repeatable
  tests and preserve a pristine all-FM baseline for reload. **Do not overwrite
  slot 2**: it contains `DNII M1_FINAL`. The user's current SP setup was copied
  to slot **006**; the pristine test slot is **007 NEW PROJECT** (saved and
  verified). It has all 16 FM TONE tracks, DYN16, unison OFF, channels 1–16,
  AMP volume 32, centered pan, sends zero and a step-1 trig on each track.
  Reload that baseline before each scenario;
  do not save x0x scenario changes over its pristine copy.
- Full project reload/save shortcuts, with explicit starting cursors: in
  LOAD PROJECT with **001 selected**, `DOWN` six times then `YES` loads 007
  (the current inventory has every slot 001–007 populated). If asked to save
  the modified current project, decline with one `NO`, then wait for loading.
  In SAVE PROJECT AS with **001 selected**, the same six DOWNs and YES choose
  007; wait for its name screen, then YES saves. Use this only for an intended
  pristine-baseline update. Recheck navigation if populated slots change.
- Fast scenario reset, physically verified: from the main page of the pristine
  baseline, **`FUNC(YES)`** saves the current pattern to the temporary area.
  After a scenario, **`FUNC(NO)`** restores that snapshot, including machine
  selection and sound controls. A 16-voice readback verified x0x→all FM TONE.
  Use this instead of reopening PROJECT for each model/knob test. It restores
  the pattern, not project MIDI settings; establish it again after loading a
  project or rebooting. Do not use FUNC+YES on a modified scenario if the
  intent is to retain the pristine snapshot.
- MIDI CONFIG is the fourth SETTINGS row. Its rows are **SYNC, PORT CONFIG,
  CHANNELS**. CHANNELS starts at TRACK 1; `DOWN` selects the next track and
  `LEFT`/`RIGHT` change its channel. For these tests use tracks **1→1 through
  16→16**. A fresh project initially received only tracks 1–8; the user set
  9→9 through 16→16. Leave subsequent channel options unchanged. Select track
  10 while using all channels, matching this setup's auto channel.
- Common MIDI controls: source A/B/C **CC40/41/42**, x0x model **CC45**
  (808=0, 909=127), pan **CC89** (not CC10), AMP volume **CC90**, chorus/delay/
  reverb sends **CC29/30/31**. Send model CC only to an x0x track.
- Verify all 16 voices without an image: CF outgoing frame **0x80005e60**,
  2688 bytes, big-endian uint16; pitch at word `1+slot`, machine at `74+slot`
  (FM TONE=0, x0x=20). Native voice records at **0x40288300**, stride 20:
  owner byte +5, gate word +6 (`0xffff` after note-off). Require 16 distinct
  owners, active gates and expected pitches; owners persist after release.
- Current DigiHealth `FRAME` returns 128×64 pixels and a generation number,
  not a page/menu ID. Its `ev_tick` receives the native view controller and
  `ev_draw` receives the composed frame. A semantic UI-state query is possible
  follow-up work, but native page IDs and offsets have not been qualified.
  Do not infer actual state solely from the last key sent. DSP peek is about
  3 KB/s; use ordinary CF PEEK for UI/control/ownership checks.
- For a previously inspected, fixed dialog, compare its fresh raw bitmap
  region with the saved reference instead of rendering another image. The
  XP03 restore confirmation was verified this way against the inspected XB00
  `UPGRADE OS NOW / CONFIRM Y/N` modal. Keep generation freshness checks;
  inspect an image only on a mismatch or an unknown transition.

Run the documented chords with the matched client, for example:

```sh
mise exec -- uv run --offline --with mido --with python-rtmidi \
  python /private/tmp/x0x-digihealth-dn2-support/tools/digiusb.py \
  keys 'FUNC(NO),TRK(10),SYN'
```

That is the fast stock-pattern reset only after establishing the pristine
snapshot with `FUNC(YES)`. For FM TONE→x0x on track 1, replace the final argument
with `'TRK(1),FUNC(SYN),DOWN,DOWN,DOWN,DOWN,YES'`. Defaults are 100 ms taps;
keep bounded holds and the client's duplicate/status/no-replay handling.
