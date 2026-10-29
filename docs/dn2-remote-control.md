# Digitone II remote control

These controls apply to DN2 OS 1.12 with the revision-3 DigiHealth helper.
Before authorized device work, verify the installed build, matched client,
current project and menu state. Key completion confirms delivery; inspect the
result to establish that a machine, project or update actually loaded.

## Client setup

Choose a local checkout path. The client revision below supports DN2 remote
keys and DSP peek; it must match the helper used in the installed build.

```sh
export X0X_DIGIHEALTH=/absolute/path/to/digihealth
git clone https://github.com/simonjohansson/digihealth.git "$X0X_DIGIHEALTH"
(
  cd "$X0X_DIGIHEALTH"
  git switch --detach afc751d67b1b1575f7a5fc40f104c11451fc3ea5
  git status --porcelain
  git rev-parse HEAD
)
```

For an existing checkout, check its revision and require an empty porcelain
status instead of cloning. Run from the x0x repository with mise. For example,
read device identity before operating it:

```sh
mise exec -- uv run --with mido --with python-rtmidi \
  python "$X0X_DIGIHEALTH/tools/digiusb.py" cfw
```

Reuse one MIDI port and `RemoteKeys` session per batch. Check at meaningful
boundaries; prefer memory readback for machine, controls and voice allocation.
`FRAME` returns 128×64 pixels and a generation number, not a page/menu ID. Do
not infer state from the last key sent. Use CF PEEK for control/ownership checks;
DSP peek is slower. For a known dialog, a fresh bitmap-region comparison is
sufficient; inspect the image when it differs or the transition is unknown.

## Navigation and project preservation

- `TRK(n)` selects track n; `SYN` opens its synth page; `VOICE` opens VOICE
  SETUP. Normal multi-voice checks use **DYN (16)** and **UNISON STATE OFF**.
- From SYN, `FUNC(SYN)` opens the machine selector. Confirm the displayed
  entries before navigating. With **FM TONE, FM DRUM, WAVETONE, SWARMER,
  X0X KICKS** in that order, confirmed FM TONE → x0x is four DOWNs then YES;
  confirmed x0x → FM TONE is four UPs then YES. Let the machine load settle.
- Ordinary menus return towards the main page with `NO`. Do not use this as
  a reset through a save/load/update confirmation. SETTINGS remembers its
  selection; inspect it before opening PROJECT.
- PROJECT contains **LOAD PROJECT, SAVE PROJECT AS, MANAGE PROJECTS**.
  LOAD shows populated slots. **CREATE NEW is the final unnumbered command**;
  a project named NEW PROJECT is an existing save. Handle the current-project
  save question and initialization as separate inspected transitions.
- Before a project write, identify protected projects and verify the chosen
  test destination. Keep that device's inventory in local operating notes;
  never assume contents or navigation counts from a previous session. SAVE AS
  opens a destination list, then a name screen whose YES performs the save.
  Wait for SAVING to finish.
- Keep a pristine all-FM baseline for repeatable tests. From its main page,
  `FUNC(YES)` stores the temporary pattern snapshot; after a scenario,
  `FUNC(NO)` restores it, including machines and sound controls. This does
  not restore project MIDI settings. Establish the snapshot after loading a
  project or rebooting. Never overwrite it with a modified scenario or save
  that scenario over the pristine project.
- MIDI CONFIG is the fourth SETTINGS row, containing **SYNC, PORT CONFIG,
  CHANNELS**. CHANNELS starts at TRACK 1; DOWN selects the next track and
  LEFT/RIGHT changes its channel. Verify every channel needed by the scenario
  and choose an auto-channel/selected-track combination that avoids duplicates.

For example, after verifying track 1 is FM TONE on its SYN page and the machine
order above, one batch selects x0x:

```sh
mise exec -- uv run --with mido --with python-rtmidi \
  python "$X0X_DIGIHEALTH/tools/digiusb.py" \
  keys 'TRK(1),FUNC(SYN),DOWN,DOWN,DOWN,DOWN,YES'
```

Default taps are 100 ms. Keep bounded holds and the client's duplicate/status/
no-replay handling, then verify machine identity after the load settles.

## Controls and voice readback

Source A/B/C are **CC40/41/42**; x0x MODEL is **CC45** (808=0, 909=127).
Pan is **CC89**, AMP volume **CC90**, and chorus/delay/reverb sends **CC29/30/31**.
Send MODEL only to an x0x track.

For OS 1.12, the CF outgoing frame is **0x80005e60**, 2688 bytes of big-endian
uint16: pitch at word `1+slot`, machine at `74+slot` (FM TONE=0, x0x=20).
Native voice records start at **0x40288300**, stride 20: owner byte +5, gate
word +6 (`0xffff` after note-off). During a sixteen-voice check require distinct
owners, active gates and expected pitches; owners persist after release.
Verify the release/build identity before using these addresses.

## Optional coherent capture

`tools/x0x/dn2_capture.py` can build a separate diagnostic package with
`targets/sharc/capture.s`. After a hit reaches 100 ms, it freezes one matching
raw-voice/master-float/final-PCM record for the selected native slot. It adds
observer work and is not a performance-acceptance image. Build into a new folder:

```sh
mise run python -- -m x0x.dn2_capture build out/dn2-diagnostic \
  --digihealth "$X0X_DIGIHEALTH"
```

Installation requires the current request's authorization and installed-byte
verification. After installation, use one x0x track and leave six seconds
between triggers. Read the frozen record without sending notes or keys:

```sh
mise exec -- uv run --with mido --with python-rtmidi \
  python -m x0x.dn2_capture read out/dn2-diagnostic/readback \
  --digihealth "$X0X_DIGIHEALTH"
```

The reader rejects torn/non-finite records and writes numbered binary/JSON pairs
without overwriting existing captures. Raw/master/PCM agreement is component
transport evidence; comparison with a separate USB or analog recording requires
its own timing/gain checks.
