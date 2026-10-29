# x0x

808 and provisional 909 kick engines for Digitakt, Digitone and Digitone II.
The normal mod uses the frozen learned 808 model, with audio sample loops written
in ColdFire and SHARC assembly. The former 808 circuit/body/Tone/coupling chain
has been removed. The retained 909 is provisional; its replacement is next.

| Device | Pinned stock OS | DSP | Saved machine ID |
| --- | --- | --- | --- |
| Digitakt mk1 | 1.54 | ColdFire ASM | 80 |
| Digitone mk1 | 1.44 | ColdFire ASM | 80 |
| Digitone II | 1.12 | SHARC ASM | 20 |

`TNTUN`, `DECAY`, `ATTK` and `MODEL` keep their saved positions and defaults.
MODEL selects 808 below native value 16384 and 909 above it. Each voice latches
MODEL on START. The 808 also latches Tone and Decay on START; editing them affects
the next hit. The provisional 909 retains live Tune/Decay; ATTK remains reserved.
The mod writes 32 mono samples per callback at 48 kHz. Stock envelopes, filters,
velocity, mixing and voice allocation remain the SDK/firmware's responsibility.

The current 808 models the captured isolated hits. It does not claim measured
analog retrigger behaviour or universal inaudibility. DSP amplitude is four times
the recorded capture amplitude, with no per-hit gain or alignment correction.

## Build and test

Language runtimes are managed by mise. The pinned Elekloader includes the 64 KiB
DN2 owner from upstream PR 211. Keep stock firmware inputs local; see
[firmware/README.md](firmware/README.md) for exact filenames and hashes.

```sh
mise install
mise run bootstrap
mise run firmware:dt
mise run firmware:dn
mise run firmware:dn2
mise run test
mise run test:dt:mod
mise run test:dn:mod
```

Normal builds produce `out/{dt,dn,dn2}/x0x.syx`, `build.json`, `link-map.json` and
local `.elemod` dependencies. They include both models. No alternate test glue
is substituted for the actual machine sources. Generated tables and firmware
stay under ignored `out/`; do not check them in.

`mise run test` checks model mathematics, actual assembled instructions,
ColdFire integer-reference agreement, mixed-model slot isolation, START/reset,
invalid inputs, ABI/EMAC preservation, bounded writes and the compiled native
C adapters. The emulator smoke tasks boot the normal DT1/DN1 packages without
HLE, select X0X from the native panel, trigger a hit and compare its callback
output and full 808 state to the independent integer reference. They also
require nonzero downstream PCM. Executable JIT memory is required by Unicorn.
The first run fetches pinned Python dependencies; the model tasks reuse that cache.

For full waveform/source-cohort reports, the ignored local capture corpus is
required. Run `mise run research:808:sharc-model` or
`mise run research:808:coldfire-model`. Reports and listening material go under
`out/808-model/`. Device tests are separate evidence; emulator results are not
physical qualification. DN2 flashing uses DigiHealth's `codex/dn2-support` branch.

## Model and resources

[models/808.npz](models/808.npz) is the 9,179-byte frozen coefficient source,
SHA-256 `fb4519537afc1142f3c108bc9e94fe40b752f2b967a97ab6e185e5e47a04d112`.
It is the candidate from `field-2026-10-28`; the original captures and listening
responses remain in the ignored research archive. Normal builds verify its hash
and generate each target's numerical representation. No capture archive is
needed to build the mod.

ColdFire uses a tagged 1,412-byte voice state, with a shared payload for 808/909.
SHARC uses 1,060 bytes per voice; combined code is 4,794 bytes, with 29,980 bytes
of initialized tables. Tables plus all 16 state slots consume 46,944 bytes of the
private data allocation. The private code/data split stays inside the 64 KiB SDK
owner. Audio arithmetic remains in ASM; C handles native frames and dispatch.

The accepted historical isolated-render cohort had at most 2.7e-6 DSP full-scale
port error against the frozen model, and about 0.56% median / 0.70% worst relative
L2 error against the selected source recordings. Those are waveform metrics,
not audibility thresholds. Listening round four returned 16/16 “can't tell”.
Earlier physical DN2 witnesses matched the 808 within 8.3e-7 DSP full scale;
that waveform comparison is historical evidence. The normal combined `X0X2`
build also passed a fresh physical code/table, native START/control-latch,
mixed-model state and stack-guard smoke. That smoke did not capture new audio.

The current plan and acceptance evidence live in [#82](https://github.com/simonjohansson/x0x/issues/82).
[#94](https://github.com/simonjohansson/x0x/issues/94) tracks final coexistence
with the future replacement 909. Sixteen simultaneous kicks, broad platform
qualification and full-device headroom are outside mod acceptance.
