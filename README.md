# x0x

808 and 909 kick machines for Digitakt, Digitone and Digitone II.
Select a model, shape the kick, and use your device's normal sequencer, filters,
AMP controls and effects.

## Supported devices

| Device | Required OS |
| --- | --- |
| Digitakt mk1 | 1.54 |
| Digitone mk1 | 1.44 |
| Digitone II | 1.12 |

Use the build for your exact device and OS. Digitakt II is not supported.

## Install

There are no published release downloads yet. Follow the
[build instructions](docs/development.md#build-and-test) to create your firmware
image from your own stock OS download. The resulting files are:

| Device | Firmware image |
| --- | --- |
| Digitakt mk1 | `out/dt/x0x.syx` |
| Digitone mk1 | `out/dn/x0x.syx` |
| Digitone II | `out/dn2/x0x.syx` |

Back up your projects and sounds. Follow your device's OS-upgrade procedure,
send the matching image with Elektron Transfer or `elektroid-cli`, and confirm
the upgrade on the device. Wait for the upgrade and restart to finish.

## Play your first kick

1. Select the track you want to use.
2. Open its machine selector and choose **X0X KICKS**. On Digitakt, use
   **FUNC + SRC**. On Digitone II, use **FUNC + SYN**. On Digitone mk1, hold
   the track key, open **MACHINES**, then select X0X.
3. Open **SRC** on Digitakt, **SYN2** on Digitone mk1, or **SYN** on Digitone II.
4. Set **MODEL** to **0** for 808 or **127** for 909, then trigger a note or
   place a trig in the sequencer.
5. Adjust the controls below. Changes take effect on the next hit.

| Knob | Label | What it does |
| --- | --- | --- |
| A | TNTUN | 808: Tone, from darker to brighter. 909: Tune, shaping the pitch sweep. |
| B | DECAY | Adjusts the kick's decay. |
| C | ATTK | Shapes the 909 attack. Has no effect on 808. |
| F | MODEL | Selects 808 at values below 64 and 909 at 64 or above. Use 0/127 for clear selection. |

Tone/Tune, Decay and Attack start at 64. Use the native AMP/track volume for
level. AMP envelopes and note length can shorten the sound; check those settings
if a long kick gets cut off.

## Current limitations

- On Digitone II, a new kick fades out the previous kick on the same track
  over about 2.7 ms. Other tracks stay independent. Overlapping tails are
  [planned separately](https://github.com/simonjohansson/x0x/issues/95).
- The controls currently use the shared TNTUN label and a numeric MODEL
  selector. ATTACK remains visible for 808 even though it has no effect.
- Older Digitakt/Digitone sounds saved with the former X0X registration must
  have X0X selected again and be saved. There is no automatic migration.
- Broader sound-fidelity acceptance and physical Digitakt/Digitone qualification
  remain in progress. See [current qualification](https://github.com/simonjohansson/x0x/issues/94)
  for tested builds and workloads.

For development, model research and test commands, see the
[development guide](docs/development.md).
