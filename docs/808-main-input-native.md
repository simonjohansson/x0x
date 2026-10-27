# Shaped 808 main input: native emulator evidence

These 27 October 2026 runs exercise the [main-input increment](808-main-input.md)
in installed firmware on all three emulators. They used the working source
based on `0bbad4e`, including its uncommitted main-input changes; the eventual
implementation commit identifies that source. This is native firmware evidence,
separate from the independent circuit model, isolated CPU comparisons and VST
training comparison. There is no physical-device qualification.

| Device | Firmware / emulator | Result and coverage |
| --- | --- | --- |
| Digitakt | OS 1.54 / digiemu | 39,315 callbacks, 37,800 selected callbacks; 27,721 observed 808 counter/coupling blocks. Audio, native controls, next-START MODEL, locks, LFO, save/reload and mixed models pass. Overall run fails only the existing `parameter_reset` and `page_reset` checks tracked in #78. |
| Digitone | OS 1.44 / digiemu | Pass: 100,782 callbacks and 92,406 observed 808 counter/coupling blocks; controls, MODEL, raw and downstream audio, Decay/Tone, locks, LFO, save/reload and mixed models pass. Both Tone pre-capture baselines and the 909 baseline are exactly zero in this run. |
| Digitone II | OS 1.12 / Digikit | Pass: 31,878 audio frames / 31,879 DSP frames; zero missing audio blocks, no reported halt, no controller error. Actual voice output, native PCM, controls, next-START MODEL, locks, LFO, project reload and mixed models pass. |

DT and DN observe the consumed initial counter values through real render
callbacks. DN2 observes the settled counter and downstream output; exact 1 ms
main-input / 6 ms frequency-switch timing remains isolated actual-ASM component
proof. Neither observation alone is a sample-exact full-firmware waveform
comparison against the circuit model.

DT/DN C47 entry-recurrence maximum errors are respectively 5.302e-7 FS and
5.235e-7 FS, within the existing 1e-5 FS limit. DN2's driven Tone-state prediction
maximum error is 1.180e-8 FS; the isolated native 808 capture is 24,000 frames at
48 kHz with peak 0.0197301 FS. Its live Decay test measures about 34.106 ms and
385.554 ms at the two endpoints. The raw DSP state, stock-processed voice buffer
and captured native PCM retain their separate checks; native amplitude is not
the unprocessed source-model gain.

## Reproducible local artifacts

All runs use Elekloader `b893c9317936633d7a32829b618c2867ee99277c`.
DT/DN use digiemu `f57c2f237e84b8ff91bc3adb2a2931bccf9928e9`;
DN2 uses Digikit `d0a4d76d533d7181ea5eee548ca68edaa8d49c35`.

| Device | Local report | Built firmware SHA256 |
| --- | --- | --- |
| DT | `out/dt/silent/native-report.json` | `03b21791918b72622377e15b9e7bf05e36d0a9943047198fe8dfe170a90e4b0b` |
| DN | `out/dn/silent/native-report.json` | `d4c39fcae34d781627cd24ee4dfdee0ebe696179f5602ffe533a51b2fbe38428` |
| DN2 | `out/dn2/silent/native-boot-report.json` | `772e35814e66a4a3cfec6bad36b205991bd5771507ffb87c173e0a3b37a6ac81` |

Commands were `mise run test:dt`, `mise run test:dn` and `mise run test:dn2`.
Reports and WAVs are ignored local evidence, not tracked firmware or recordings.
The reports' SHA256 values, respectively, are:

```
b76e15a3db45a5852e678a9a6c598877cb0ee7df36691dca9b37736e437f832a
8f5ad060f49d586d88e005845b2957c15ea5cecee376e221daf8664e356b4375
0c66a054e467ad03965ea8ae367e0f1f63569a0458068a29dadcce7a0c013f3c
```

## Remaining gates

#78's DT resets remain deferred. The current passing DN baselines do not resolve
#20's historical one-count residue. #80's late post-STOP DN2 MODEL delivery is a
separate, unqualified path; the tested next-START and mixed-model paths do not
close it. Persistence across DN2 emulator restart and strict-model qualification
also remain unqualified. Full 808 circuit fidelity, feedback/pitch sigh and the
remaining 909 model work are still open. The HTML report and held-out audio were
untouched by these native tests.
