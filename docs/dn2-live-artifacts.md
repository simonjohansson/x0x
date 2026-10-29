# Digitone II live-artifact investigation — 29 October 2026

The user-approved interim DN2 fix chokes older kicks on the same track, with a
128-sample fade, for both models. XP02's sixteen-slot, two-track captures are
clean and the user reports clean direct-output listening. A held stock FM
tone also remains clean. The final normal-DSP XP03 build is installed,
byte-verified and passes the repeated qualification below. Preserving
overlapping tails efficiently is tracked in #95.

Historical captures below demonstrate overload and a shared-output buffer
splice. One-voice boots of X0X2/XD01 and the intermediate XP01 optimization
were diagnostic stages, not the final solution. The exact low-level handoff
owner remains unproven; the interim fix removes accumulated kick synthesis
work. Isolated rendered WAV comparisons did not exercise this live workload.
The shared SDK and saved formats remain unchanged. Broader multi-device and
fresh-source fidelity acceptance are separate from this DN2 fix.

## Matched stock-DSP baseline and one-kick cost

At the user's request, a fresh project was initialized with FM TONE on all
sixteen tracks, DYN (16), unison off, channels 1→1 through 16→16, centered pan,
AMP volume 32 and no effect sends. The user's SP setup was preserved in slot
006; the pristine test project is saved in slot 007. An existing project named
NEW PROJECT was rejected as an initialization baseline after readback exposed
unison and missing MIDI routes. Only the subsequently verified fresh setup
contributes to the measurements below.

Normal XP03 was compared against **XB00**, built from the same OS 1.12 with
the same ColdFire core/DigiHealth meter but without the machines companion or
x0x. XB00's parsed DSP section is byte-identical to stock. Physical device
info reports XB00, DigiHealth responds after reboot and CF readback confirms
the x0x owner-hook site has its original stock bytes. This is a stock-DSP
control, not a completely unmodified ColdFire OS. No DSP peek was attempted
on this image, which has no supporting SHARC hook.

Each case has ten tightly batched 16-note MIDI triggers at 1 Hz and a separate
native sequencer test with all sixteen tracks triggering on step 1 at 120 BPM.
MIDI batches take at most 0.52 ms; native step triggers share one sequencer
step. Readback verifies sixteen distinct owners and expected pitches, all
active gates during the MIDI check, and exactly zero or one custom machine.
The one-kick cases replace FM TONE on track 1 and retain fifteen FM tracks.
Source controls are 64/64/64. The MIDI test uses notes 48–63 and velocity 32;
the sequencer uses the initialized trig defaults at note 60.

| Firmware / sixteen-track setup | MIDI mean | MIDI maximum | Native-step mean | Native-step maximum |
| --- | ---: | ---: | ---: | ---: |
| XB00: stock DSP, all FM TONE | 414,084 | 435,457 | 414,399 | 459,096 |
| XP03: x0x installed, all FM TONE | 419,677 | 441,314 | 420,115 | 457,045 |
| XP03: one 808 + fifteen FM TONE | 438,891 | 490,027 | 439,144 | 504,870 |
| XP03: one 909 + fifteen FM TONE | 444,056 | 504,176 | 443,915 | 504,804 |

All figures are raw measured handler cycles. Means use nine complete one-second
MIDI windows or eight native-step windows after discarding the first window,
which can straddle a transition. Windows are consecutive, each with 1,500
nonzero samples. Maxima include the observed transition window and are
individual observed peaks, not deterministic costs: the lower XP03 all-FM
native peak does not establish a peak-time improvement over stock.

After the identical playback/settle sequence, all-FM idle means are **414,319**
without x0x and **420,040** with it: approximately **5,721 cycles / 1.38%**
additional measured handler work while the mod is unused. The active MIDI
comparison agrees: +5,593 cycles / 1.35%. Replacing one FM voice with an active
808 adds **24,808 cycles / 5.99%** over stock all-FM; a 909 adds **29,972 /
7.24%**. These are marginal whole-handler differences, not isolated kernel
instruction counts or total DSP utilization. The final peek hook runs after
the handler timestamp and is outside this meter. ColdFire bookkeeping is
also outside the measured SHARC span.

After playing and allowing the selected kick to expire, XP03 idle means are
424,365 (808 case) and 424,009 (909). A retired custom slot still has dispatch
and validation cost; merely selecting a machine before its first allocation
is a different state. The earlier 613k/793k stress peaks used a different
two-kick project and are not a matched subtraction against this 414k baseline.

The four USB captures total **183.637 seconds**. They are finite, unclipped and
have no reported PortAudio overflow. The user declined the optional repeat
all-FM run after restoration; no A/B/A repeat is claimed. This experiment
changes no production DSP source and is not independent analog or listening
acceptance. Checked acquisition receipts, raw CF frames, audio and the stock
DSP identity receipt are under `out/dn2/baseline-cost-20261029/`; `results.json`
is checked by `analyze.py`. Reusable controls and the verified temporary
pattern save/reload shortcut are recorded in `AGENTS.md`.

The exact qualified XP03 image was restored before the user's cancellation
of that restoration arrived; fresh device info confirms XP03. Device actions
then stopped, leaving the all-FM test setup in place and SP preserved in slot
006. No post-restoration performance repeat or full DSP-byte readback is
claimed for this baseline increment.

## Historical pre-fix evidence

Historical pre-diagnostic baseline: the Digitone II reported X0X2 and
DigiHealth 1.6. DSP peek matched
all 6,144 padded author-code bytes and 44,396 coefficient-table bytes to the
qualified combined artifact. The installed image receipt is
`out/dn2/device-current/build.json`; its SHA-256 is
`793951da741afc4dc03f2051523e0ee421a8d9a739d5bafd9cbbfc4e36aa5ba8`.
This is installed DSP-byte evidence, not a fresh readback of the whole firmware.

Track 1 / MIDI channel 1 / note 60 was recorded through the Digitone II's
class-compliant USB stereo input at 48 kHz, float32. Scenarios include held
notes, fixed controls, mid-hit CC sweeps, repeated hits at 0.5 and 0.125 seconds,
isolated hits six seconds apart, low/high velocity, filter-cutoff changes and
diagnostic-channel controls. All retained acquisitions are finite and unclipped,
with no reported PortAudio overflow. The stack guard remains `57ac6a2d` and
heap faults remain zero. These checks do not accept the sound.

### Repeated-trigger cost exceeds a block

Closed DigiHealth windows reach a mean **818,676 raw EMUCLK cycles per
handler**, with a maximum **849,148**. The block period is 32 / 48,000 =
0.667 ms. Even at the processor's maximum 1 GHz, these spans require at
least 0.819 / 0.849 ms. This establishes an over-budget workload without
assuming the unit's actual configured clock. It does not measure an individual
callback's cost, total DSP busy percentage or the precise output underrun site.

The historical 808 continued its full synthesis path until age 264,000 samples
(5.5 seconds); the 909 until 96,000 (2 seconds). These are fixed render horizons,
not the audible duration at every Decay setting. The callback has no release
flag and stock AMP owns release. Fresh native allocations therefore accumulate
render work, including work on tails that stock AMP may no longer expose.
Fixed-control repeated 808 captures develop strong block-rate artifacts as
handler time rises. This is an ordinary repeated-kick scenario, not a proposed
maximum-polyphony acceptance campaign.

Analog Devices documents [up to 1 GHz for the ADSP-21569](https://www.analog.com/en/products/adsp-21569.html)
and [EMUCLK as a core-cycle counter](https://ez.analog.com/dsp/software-and-development-tools/cces/f/q-a/542109/reading-current-clock-cycle-count/409468).

### Isolated-hit artifact remains separate

Isolated captures also contain sidebands around 1.5 kHz and its multiples,
the 32-sample block rate. Some earlier isolated captures are clean. Later
isolated timing windows remain below 538,000 cycles, so the demonstrated
repeated-hit overload does **not** explain every observed glitch.

- Fresh 808 weights and Tone pole match the reference exactly. Read 909
  body/onset weights agree to below 2e-12 / 1e-8 after applying the packed-table
  scale convention. Correct coefficients do not prove correct live waveforms.
- Panel readback confirms overdrive and sample-rate reduction zero; bit
  reduction, delay, reverb and chorus off. Stock AMP/filter processing remains.
- Cutoff 127 → 64 → 32 → 127 changes output level but leaves the high-frequency
  energy fraction near 2.8%. This suggests the artifact is introduced after
  the selected low-pass filter; it is not a raw-source fidelity measurement.
- Zero/nonzero peek-reply ABAB captures have the same artifacts. A second ABAB
  test comparing a valid read with a DSP-whitelist-refused request also gives
  essentially the same result. Neither reply data nor the active memory-read
  branch explains the artifact. A fully disabled-peek firmware control has
  not been run.
- Eighteen peeks of the existing post-master L1 buffer at `0x268438` look much
  smoother than the simultaneous USB capture. These are **not coherent audio
  blocks**: peek transfers one halfword per block. The exploratory analysis
  discards each float's torn low half and accounts for successive words being
  two blocks apart. It suggests an output-path problem, but cannot conclusively
  assign it to final DSP conversion, transfer, or USB. Do not use its fitted
  smoothness or alignment as a fidelity acceptance result.

No independent analog-output recording was made. The user's audible report
and the measured USB evidence remain distinct.

### One locked voice reduces work but leaves the artifact

The user manually set VOICES to **1 (15)**: one voice locked to track 1,
15 remaining free. DigiHealth OLED readback confirms this setting. The exact
allocation harness was rerun into a separate `onevoice/` directory: 86 note-ons,
the same two models, fixed controls, six-second isolated spacing, 0.5-second
repeats and 0.125-second repeats. Its 85.333-second USB capture is finite,
unclipped and reports no PortAudio overflow.

The largest closed-window mean falls from **818,676 to 495,015 cycles**
(39.5%); the maximum falls from **849,148 to 554,815**. All recorded one-voice
spans fall below the conservative 666,667-cycle ceiling at 1 GHz. This removes
the previously demonstrated overrun of even that ceiling; the actual clock
and remaining real-time headroom have not been measured. It is not complete
performance acceptance.

Both models still exhibit isolated-hit high-frequency artifacts, including
block-rate sidebands. Limiting allocations does not fix the separate artifact.
Spectral energy on short retrigger windows is not an acceptance metric:
one-voice retriggers themselves truncate/restart a waveform.

Additional read-only MCU SRAM probes recorded USB audio while inspecting
candidate DSP-reply and USB-transfer buffers. The former did not expose the
main mix in the inspected region; the latter contains transfer descriptors,
not the proposed decoded audio frames. Neither probe supplies a coherent main
output capture or establishes where the remaining corruption occurs. Preserve
them as inconclusive experiments, not audio evidence from those buffers.

## Retrigger behavior and native settings

The original machines each have one bass-drum circuit. New triggers re-excite
or retrigger that existing circuit; they do not allocate independent parallel
kick tails. A hard reset/choke is only an approximation of the circuit's
state-dependent retrigger behavior. See Roland's
[808 service notes](https://manuals.fdiskc.com/flat/Roland%20TR-808%20Service%20Manual.pdf)
and [909 service notes](https://notebook.zoeblade.com/Downloads/Documentation/Roland/TR-909_service_notes.pdf).
The current isolated-hit models have not been qualified for that behavior.

The initial runs used track 1 CYCLE, REUSE off, DYN (16), unison off.
Elektron's [VOICE SETUP documentation](https://www.elektron.se/wp-content/uploads/2025/07/Digitone-2-User-Manual_ENG_OS1.10C_250708.pdf)
says REUSE on reuses the same voice for repeated equal pitches; locking one
voice limits a track to that voice. Both are relevant diagnostic controls.
Remote encoder attempts were acknowledged but did not visibly change this
menu, so the initial runs did not include a REUSE-on or one-voice comparison. Attempts were
reversed; the final settings were checked on the OLED.

A subsequent remote-control check also tested ordinary DOWN/RIGHT navigation,
pressed-encoder turns, FUNC-modified turns and sustained bounded impulses.
The display still read DYN (16) during those historical attempts. Readback of the native encoder event ring
confirms a correctly queued encoder event (including its signed delta), and
the installed `ev_enc` subscriber list is empty. No stuck key masks were found.
This narrows the remote-control failure beyond mere protocol acknowledgement,
but does not establish its root cause or a working button-only value edit.
Evidence is local in `out/dn2/voice-control-20261029/`. Those attempts did not
establish a working remote value edit. Subsequently, the user changed the
setting manually; `user-setting-second.png` confirms **1 (15)**. The one-voice
test above supersedes the earlier unverified setting/comparison status.
That historical run ended at one voice with source controls restored to
64/64/64 and model 808. The user subsequently increased VOICES to nine and
rejected a one-voice limit as a production solution.

## Reproduction and remaining work

All raw captures, event/sample-frame logs, screenshots, readbacks, scripts and
hashes are local under `out/dn2/artifacts-20261029/`. In particular:

- `live_scenarios.py`, `live-scenarios.{wav,json}`: held/edited/retriggered cases.
- `allocation_probe.py`, `allocation.{wav,json}`: isolated/regular/rapid cases
  and closed timing windows.
- `timing_probe.py`, `timing.{wav,json}`: timing throughout isolated held hits.
- `filter_probe.py`, `filter-probe.{wav,json}`: filter placement experiment.
- `master_probe.py`, `master-*.bin`, `master-probe.{wav,json}`: sparse DSP master
  observations and simultaneous USB audio.
- `peek_ab.py` and `peek_refused_ab.py`: diagnostic controls.
- `installed-bytes.json`, `state-analysis.json`, `final-state.json` and
  `evidence-check.json`: acquisition/readback checks and raw-audio hashes.
- `clean-808.wav`, `bad-808.wav`, `diagnosis.png`: concise listening/visual examples.
- `onevoice/allocation.{wav,json}`, `allocation-analysis.json`, `comparison.json`
  and `comparison.png`: the matched one-voice run and timing comparison.
- `onevoice/checks.json`: checks and hashes for the three new acquisitions,
  restored controls and guard. Isolated sideband peaks include approximately
  1,453/1,547 Hz (808) and 1,447/1,553 Hz (909), with corresponding higher pairs.
- `onevoice/reply_probe.py` and `usb_packet_probe.py`: inconclusive MCU-buffer
  probes, with simultaneous USB captures and raw readbacks.

The probes use mise Python 3.12.13 with mido, python-rtmidi, sounddevice, numpy
and soundfile; screenshot probes additionally use Pillow. Their read-only
DigiHealth client is `/Users/simonjohansson/src/digihealth/tools/digiusb.py`.
They are investigation scripts tied to this installed build, not a general
hardware test API. Inspect the current device, audio port and saved controls
before another run. `evidence_check.py` validates the retained acquisitions;
it must continue to report audio acceptance as failed.

The one-voice comparison is complete; a separate REUSE-on comparison is untested.
The user approved preparing and installing the diagnostic build on 29 October,
then authorized a temporary original-image A/B and return to XD01. Physical
captures and the A/B are described below. A recording of the analog output and
the original fault has now reproduced while coherent probes are active (below).
The current ABI's slot identity is not a track identity; do not implement a
global choke that could silence other tracks.

## Historical diagnostic firmware: XD01

`out/dn2/capture-XD01-live/x0x-diagnostic.syx` is the diagnostic image built
from the pinned OS 1.12 baseline. SHA-256:
`60e4c2af8e4aa9f09eecd8cadf7c3c2feaab1e302dd7291015962a83d7c594be`.
It contains the same DigiHealth 1.6 artifact and ColdFire main as the previously
installed bundle, from clean DN2-support revision
`afc751d67b1b1575f7a5fc40f104c11451fc3ea5`, built with its `build.py`.
`package-comparison.json` checks both identities and that the prepared DSP
capture payload was unchanged when the helper was added.

The historical first package in `out/dn2/capture-XD01/` omitted the ColdFire
DigiHealth helper. This was caught before flashing; that image was never
installed and is superseded. The build command now requires a clean DigiHealth
checkout and includes its helper. The normal production build is unchanged.

`tools/x0x/dn2_capture.py` stages observer instructions into copies of the
normal engine sources and links `targets/sharc/capture.s`. The coefficients,
sixteen voice-state addresses, machine ID, qualified adapter, shared SDK and
saved format stay unchanged. The build uses a private copy of the release
description to retarget only the existing peek hook to the observer, which
then jumps to the original peek. The hook site, expected stock bytes,
ownership ranges and all linker checks stay in force. No vendor file changes.

On a valid START, the diagnostic rearms for that native slot. After the 150th
callback (age 4,800 samples, approximately 100 ms), it copies the raw 32-sample
voice block. At the same handler's end, before the existing peek toggles the
bank selector, it copies the master float buffers and completed final-stereo
PCM bank. Three frame markers must agree before the record is published.
A later START invalidates and rearms the record. Use only track 1 for this
experiment; another x0x START can replace its capture.

| Core address | Bytes | Content |
| --- | ---: | --- |
| `0x2009f800` | 64 | Magic, publication status, generation, slot/model, three frame markers, age and source/bank markers |
| `0x2009f840` | 128 | Raw voice: 32 float32 samples |
| `0x2009f8c0` | 256 | Master left/right: 32 float32 samples each, source `0x268438`/`0x2684b8` |
| `0x2009f9c0` | 256 | Final-stereo bank: 64 signed words, source `0x2c0478 + bank*256`, after the stock handler's negation |

The frozen record is 704 bytes, within a 1 KiB reservation ending exactly at
the adapter state (`0x2009fc00`). Mutable counters and saved scratch registers
sit outside the frozen record. This historical package uses 5,138 of 6,144 code bytes and retains
the required 64-byte read-ahead guard. Rebuilding with the current kernel uses
the code size in its new build receipt. The observer preserves the end hook's
live registers and circular-buffer lengths and changes no interrupt or MODE
settings. Invalid slots/state pointers, stale frames and invalid PCM banks
cannot publish an accepted record.

These source labels follow the pinned stock code. Agreement of software frame
markers establishes capture order. Physical captures confirm the captured PCM
equals the master floats after polarity inversion and normalization by 2^31.
Precise alignment/scaling to the separate USB output path remains unqualified;
the raw frame-marker agreement alone does not prove that relationship.
The component tests use known synthetic master/PCM buffers, not a full stock
DSP or coupled-device run. The capture also adds work to its selected block;
handler timing is sampled before the peek hook, so it does not measure this
extra work. This diagnostic is not a performance or audio-fidelity acceptance
build and does not fix the artifact.

Validation completed:

- Six diagnostic tests execute the observer ASM on the pinned native core:
  both engines match normal samples, the 150th block is captured exactly,
  both PCM banks work, frozen records stay fixed, a second generation rearms,
  live registers/lengths survive, and invalid/torn records are refused.
- Nineteen existing SHARC engine/layout regression tests pass.
- Standard linker and independent firmware verification pass, including
  SysEx/container integrity, unchanged bootstrap/other sections, flash budget,
  in-place depack and the measured USB update staging limit. The decoded
  container is 1,968,944 bytes; wire SysEx size is larger.
- The corrected bundle's ColdFire main image matches both a standard link with
  DigiHealth and the previously installed DigiHealth bundle byte for byte.
  `build.json`, `verification.json`, `package-comparison.json` and `link-map.json`
  accompany the image. Initial component/regression logs are under
  `out/dn2/diagnostic-capture-20261029/`.

To reproduce into a **new** output folder from the repository root:

```sh
mise exec -- env PYTHONPATH="$PWD/tools:$PWD/vendor/elekloader:$PWD/vendor/digikit:$PWD/vendor/digiemu" \
  uv run --frozen --project vendor/digiemu --with numpy==2.5.4 \
  --with scipy==1.18.0 --with soundfile==0.14.0 --with networkx==3.4.2 \
  --with mypy==2.3.1 python -m x0x.dn2_capture build out/dn2/capture-XD01-new \
  --digihealth /private/tmp/x0x-digihealth-dn2-support
```

For a separately authorized subsequent installation and installed-byte verification,
retain track 1 **1 (15)**, silence other tracks, select the 808 or 909 and hold
one kick for at least 120 ms. Allow six seconds between triggers. Read while
the record is frozen:

```sh
mise exec -- uv run --python 3.12.13 --with mido --with python-rtmidi \
  python -m x0x.dn2_capture read out/dn2/capture-XD01-live/readback
```

The reader uses the sibling DigiHealth checkout's existing DSP peek and sends
no note, key or firmware command. It checks the header before and after the
read, rejects changed/mismatched records, closes its MIDI port on failure and
saves numbered `.bin`/`.json` pairs without overwriting existing captures.
Record USB audio simultaneously and compare the three stages before assigning
the artifact to a particular conversion/transfer boundary.

## Physical XD01 capture and original-image A/B

The corrected image was transferred with elektroid-cli, the observed update
dialog confirmed with DigiHealth, and version XD01 verified after reboot.
Installed-byte readback matches the 2,048-byte adapter, 6,144 padded author-code
bytes, all 44,396 table bytes, capture magic, retargeted hook and voice binding.
The stack guard remains intact. DigiHealth uptime reset and its remote-control
capabilities respond. Track 1 remains **1 (15)**; FAST AUDIO is unavailable on
this DN2 build and reports false, without a fault.

The first six snapshots (three fixed-control isolated hits per engine) freeze
successfully at age 4,800 with matching frame/generation markers. Their raw 808
samples match execution of the original assembled engine exactly; the 909
maximum error is 2.2352e-8. For every captured stereo PCM word,
`-pcm / 2^31` equals the corresponding master float exactly. These are clean
signal captures, not captures of the original fault.

The first readback check incorrectly rejected the stock callback's DDR output
pointer (`0x804acf90`). The reader now accepts the device profile's documented
DDR range as well as L1/L2. Raw recordings were intact and were decoded after
that correction, without another firmware change. Regression checks cover
valid DDR pointers and an out-of-range pointer.

The original 86-note scenario and 53-note held/velocity/CC-sweep scenario were
repeated on XD01. The earlier 1.5 kHz artifact family did not reproduce. The
user also reported clean sound through the Digitone's outputs/headphones;
that is listening evidence, not an independently recorded analog measurement.

The user then authorized an original-image control: the previous verified
X0X2/DigiHealth image was installed, its original code and tables read back,
and the identical 86-note scenario repeated with **1 (15)**. It was also clean
in the USB capture; the user reported "Still clean" through the direct output.
The diagnostic hooks therefore are not necessary for clean playback in this
fresh-boot setup. The controlled comparison is:

| One-voice run | Maximum handler cycles | 808 isolated energy above 1 kHz | 909 isolated energy above 1 kHz |
| --- | ---: | ---: | ---: |
| Historical original image, before reboot | 554,815 | 3.2001% | 6.0813% |
| XD01 after reboot | 548,520 | 0.00000247% | 0.0002843% |
| Original X0X2 after reboot | 548,574 | 0.00000247% | 0.0002843% |

These short-window spectral fractions are diagnostic comparisons, not fidelity
acceptance thresholds. Retriggers can also create legitimate discontinuities.
The actual configured DSP clock/headroom remains unmeasured.

One additional input-only/full-duplex USB experiment is **excluded** from the
USB comparison: opening a separate host output stream stopped the input frame
counter in seven cases, despite no reported PortAudio overflow. Its frozen DSP
records are retained, but the missing USB data cannot count as a passing duplex
test. The A/B input recordings identify the Digitone by name after CoreAudio
renumbered devices; an earlier failed open produced no valid capture and is
retained as a failed acquisition.

### Exact signature in the historical metallic recording

In a 2,112-frame stereo segment of the historical one-voice 808 capture
(4,224 individual samples), **every sample** exactly matches one of two
positions in the clean XD01 take, separated by **64 samples**. There are no
unmatched sample values. Most of each 32-sample block uses the older position;
the beginning uses the newer one. The transition varies over two positions,
and one stereo pair selects different generations for left and right.

This proves a periodic splice of two clean sample histories in that segment.
It strongly indicates a producer/consumer buffer-ownership or timing race,
rather than a need to retune the kick model. The 32-sample switching explains
the 1.5 kHz family of sidebands. It does **not** yet identify the exact DSP/DMA/
transport routine: at this historical A/B stage, the fault had not reproduced
while the coherent probes were active. A reboot also resets allocation/transport history; those effects have
not been separated. One voice alone did not clear the earlier bad state.

Evidence is under `out/dn2/capture-XD01-live/`: `splice-proof.json`,
`history-exact-splice.json`, `splice-diagnosis.png`, `capture-analysis.json`,
`ab-summary.json`, raw `captures/`, repeated `reproduction/`/`sweeps/` and
the original-image `ab-original/` control. The initial dynamic-allocation run's
sidebands appear as timing rises into the over-budget region; this chronology
supports an overload-related handoff problem, but does not prove its trigger.

The historical recovery used one voice plus a restart. The user subsequently
rejected a one-voice workaround and reproduced the fault at nine voices.
Keep #94 open for the source candidate and physical qualification below;
the precise handoff owner and wider device/fidelity acceptance remain unfinished.

The A/B ended with **XD01 restored and verified**. A further six coherent
snapshots and USB recording remain clean; all 12 controlled records retain
matching frame markers and the exact master/PCM relationship. The committed
`read` command also succeeds against the physical frozen record. Final OLED
readback confirms **1 (15)**; source controls are 64/64/64, model 808, SYN page.
The guard is intact and heap faults remain zero. The user reported clean direct
output on both XD01 and the original-image control. No analog file was recorded.

`evidence.json` checks 237 note-ons across 318.379 seconds of valid USB captures,
finite/unclipped audio, advancing input frames, all 12 coherent records,
installed-byte identities, the physical read-command result and the exact
historical splice proof. The failed input open and stalled duplex experiment
are explicitly excluded. Production audio acceptance remains unresolved.
Final installation/readback/state evidence is in `final/`.

## Historical XP01 polyphony reproduction and source candidate

The user's report is faint crackling around six allocated voices and severe
artifacts at nine. Physical OLED readback confirms **9 (7)** on track 1.
The installed firmware remains XD01; no new firmware was flashed in this increment.
Source controls were restored to 64/64/64, model 808. One-voice operation is not
the intended fix; the intended use includes two independent kick tracks.

The scripted nine-voice run captures isolated hits and nine hits spaced 125 ms
apart for both models. All four records have stable publication headers,
matching raw/master/PCM frame markers and age 4,800. The master-to-PCM relation
is exact for all 64 stereo words in every record (`master == -pcm / 2^31`).
The completed PCM and master blocks remain smooth while the simultaneous USB
recording develops strong block-rate artifacts under the nine-hit workload:

| Model / triggers | Maximum handler cycles | USB energy above 1 kHz | USB energy 1.4–1.6 kHz |
| --- | ---: | ---: | ---: |
| 808 / 1 | 512,287 | 0.000000032% | 0.0000000035% |
| 808 / 9 | 702,848 | 1.3750% | 0.6845% |
| 909 / 1 | 537,460 | 0.0000000046% | 0.00000000023% |
| 909 / 9 | 705,687 | 0.01079% | 0.001470% |

Both nine-hit maxima exceed the 666,667-cycle block ceiling even at 1 GHz.
The producer finishes a clean PCM bank: the evidence points to a deadline or
handoff failure after/between production and consumption, rather than corruption
of the synthesized waveform. The exact consumer/routine is still unproven.
The spectral figures describe these matched scenarios, not a general fidelity
criterion or a recording of the analog outputs. Acquisition is finite,
unclipped and reports no PortAudio overflow; guard and heap checks pass.

The source candidate changes only private engine implementation:

- 808 caches interval evaluation metadata per native voice, omits an unused
  second polynomial channel and bypasses the completed attack crossfade.
- 909 evaluates complete body blocks within a cached interval, keeping
  coefficients in registers. Private scratch at `0x2009f500..0x2009f800` is
  fully overwritten before reuse under the existing serialized callback.
  Onsets, interval boundaries and expiry retain the scalar path. A builder
  guard rejects any future state/table growth into this scratch.
- All sixteen voice states, hit lengths, control latching, coefficient tables,
  adapter, SDK/API and saved formats remain unchanged. No global choke is added.

Against the original assembled artifact, three complete 808 hits and two
complete 909 hits are **bit exact**, including terminal silence (984,160 sample
words compared). Median body instruction counts decrease from 14,931 to 9,235
for 808 (**38.15%**) and 11,288 to 9,769 for 909 (**13.46%**).
These are component instruction counts, not measured hardware-cycle savings.
909 scalar interval-boundary peaks remain about 20,790 instructions; worst-case
cost and actual device headroom still need physical measurement.

**21 SHARC component tests and 6 diagnostic-capture tests pass**, including
full 909 reference corners/fractions, independent complete tails in two 909
slots, mixed 808/909 slots, restart/latching, memory guards and coherent capture
compatibility. Normal code and observer stay inside the existing reservation.
These checks did not establish a hardware fix. The user subsequently authorized
building, flashing and temporary track changes for this debugging session;
XP01 was installed and its complete adapter/code/tables verified by DSP peek.

Current evidence is local under `out/dn2/polyphony-fix-20261029/`:
`current.{json,png}`, `nine/{audio.wav,acquisition.json,analysis.json}` and
the four frozen records; `component-comparison.json`, `comparison.log`,
`optimized-tests.log` and `capture-tests.log` describe the source candidate.
The scripts and baseline sources are retained alongside these files. Issue
#94 and parent #82 remain open; no production acceptance or root-owner fix is claimed.

## Current interim per-track choke (XP02)

XP01 reduces the nine-hit handler maxima to 638,136 cycles (808) and 613,012
(909), and the strong late-window block-rate artifacts disappear in those two
captures. The initially reported smaller isolated-909 anomaly was an analysis
window error: event-to-recorded-onset delay reached 65 ms, so the unaligned
window included its attack. Onset-aligned analysis removes that anomaly;
the isolated XP01 909 is clean. This supersedes the initial anomaly report.
Two kick tracks filling all sixteen native slots still exceed the deadline:
761,844 cycles for mixed models and 793,055 for dual 909. The user therefore
approved an interim choke for both models and sixteen-voice qualification.
Preserving overlapping tails efficiently is deferred to [#95](https://github.com/simonjohansson/x0x/issues/95).

The source implementation stops older x0x renderers on the same track at a new
START. A 128-sample (2.667 ms) linear ramp from the previous block's last sample
suppresses a hard cutoff; after four callbacks the old slot writes zeros.
This changes closely spaced kick overlap. It is not a model of an analog
circuit's state-dependent retrigger, or a cached continuation of the old tail.
No arbitrary retrigger-time window or new user setting is added.

Track identity is verified physically against four distinct held notes at
the native owner byte `0x40288305 + 20*slot`, including stock tracks. Native DSP
word 66 was tested and **is not** a track ID. The mod's guarded ColdFire hook
at `0x40025e94` tags only x0x's outgoing, undeclared SYN word 39 with
`0xa500 | track`. It runs before core's unchanged frame transfer. No saved
sound, SDK descriptor, other engine's frame, or shared SDK source is modified.
The tag is private to this DN2 implementation and reserves this unused word
until the SDK supplies explicit ownership. Missing/invalid tags cannot choke
other voices. State words 124..127 hold the private owner/dead/ramp/last-sample
metadata; the existing 512-byte stride and all sixteen addresses stay fixed.

Actual assembled component checks pass for both models: same-track retirement,
independent other tracks, exact bounded ramps, slot reuse, invalid-input
atomicity, and sixteen allocated slots leaving one full renderer per kick
track. Ramp and dead callbacks take fewer than 600 and 400 component instructions.
The actual ColdFire hook's assembly and C execute in the component emulator:
registers, SR, stack shape, native owner bytes and every stock frame word are
preserved, and only the intended x0x tag words change. The existing 21 SHARC
tests and six observer tests pass. These remain component evidence.

The larger 909 batch path from XP01 was removed to fit the choke and coherent
observer in the existing 6 KiB code reservation. The smaller 808 interval-cache
optimization remains. XP02 build/full-suite checks and physical installation,
sixteen-slot retrigger/control captures and stock-track isolation are in
progress. The subsequent XP02 physical results below are separate evidence.

### XP02 physical results

Installed firmware SHA-256 is
`40f0bbd56e9a6b46d761a5afaf30bdf6c4b9ecf789a23eb2b6d536df63d8983c`.
The first transfer failed midway with an I/O error. Its receive screen was
inspected, the incomplete transfer cancelled and a clean retry completed.
After confirmation/reboot, XP02 version, full adapter/code/tables, hook,
binding, guard and responding DigiHealth helper were verified. Observer code
is 5,670 bytes; normal code is 5,046, inside the existing 6 KiB reservation.

Physical routing readback verifies all sixteen native slots, with the user's
existing nine locked voices on track 1 and seven dynamic voices for track 2.
All sixteen tags match their native owners; exactly one full renderer remains
per kick track and all fourteen retired slots have completed their fade.
Neither track is restricted to one native voice.

Six coherent captures cover isolated and rapid dual-808, mixed-model and
dual-909 cases. All master/PCM words retain the exact relationship. With eight
triggers per track, observed closed-window maxima are **564,580**, **557,806**
and **610,388 cycles**, respectively, below the conservative block ceiling.
Event-onset-aligned late-window block sidebands are at the numerical/recording
floor (largest 1.51e-9% in these cases). The analysis excludes the attack and
uses recorded onset rather than assuming a fixed MIDI-to-audio delay.

An additional **384 triggers** across both tracks sweep Tone/Tune, Decay and
Attack for dual 808, dual 909 and both model orders. The 54.869-second USB
capture is finite/unclipped, advances continuously and reports no PortAudio
overflow. Guard checks pass. The user reports **“Sounds clean”** through the
Digitone outputs/headphones during this test. No independent analog file was
recorded.

A stock FM TONE on track 4 is held before and throughout 36 rapid track-1
kicks for each model. The stock tone is panned right and kicks left using
documented [CC 89](https://www.elektron.se/wp-content/uploads/2025/07/Digitone-2-User-Manual_ENG_OS1.10C_250708.pdf).
Track 1's locked allocation cannot steal the held stock voice; track 2 is
quiet in this control. More than 2,000 positive stock-tone crossings per case
retain their period within **0.00010 sample**, with unchanged high-frequency
and block-sideband floors. This establishes clean stock-track playback in
these fixed-build cases; the old overload was not independently recorded with
a stock tone. Earlier XP01 CC-10 panning attempts did not isolate channels;
those recordings remain valid shared-mix overload evidence only.

Receipts: `XP02/{routing.json,two/analysis.json,sweeps/acquisition.json,
stock/analysis.json,stock/continuity.json,install/installed.json}` beneath the
current evidence directory. A full **76-test** host run, native-media checks
and native C control-boundary checks pass. XP03 removes the coherent observer
and retains the identical ColdFire main. Its completed qualification follows.

### Final normal-DSP XP03 qualification

**XP03 is installed and verified**, firmware SHA-256
`cde476ddf8d5da1f5e0a7c51a8266ad5765c25aa442652b8a097e302e0aa510c`.
It contains the normal 5,046-byte engine with the per-track choke and pinned
DigiHealth helper, without the coherent observer. Complete DSP adapter/code/
table readback matches; the original peek hook is restored and capture magic
is zero. The installed owner hook and native binding match the build. Guard
and heap checks remain clean; FAST AUDIO is false and fast_fault false as
expected on this DN2 helper.

The post-reboot user allocation is **11 (5)**. The first eighteen-note primer
underfilled two slots and correctly failed the all-slot assertion on unallocated
owners 255. It and the initial replay are retained as `*-underprimed*` and
excluded from sixteen-slot acceptance. A thirty-two-note primer then populated
and verified all sixteen slots, with eleven owned by track 1 and five by
track 2, exactly two full renderers and fourteen completed retirements. The
corrected full-pool replay follows this verified primer. No production code
changed for the test correction, and the user's allocation was left intact.

Normal-build dual-808, mixed and dual-909 rapid-case maxima are **563,603**,
**568,944** and **613,334 cycles**. All six onset-aligned isolated/rapid stereo
captures have late-window block sidebands at the recording floor (largest
1.13e-9%). Another 384 triggers sweep all three controls across the four model
orders. Timing was polled throughout active sweeps and their settling period;
each case has consecutive closed-window IDs with no omitted window. Maxima
are **566,218 / 611,814 / 568,794 / 568,961 cycles**, all below 666,667 even
without assuming a configured clock below the processor's 1 GHz maximum.
These are observed raw handler spans for these cases, not a universal CPU-load
or all-preset headroom guarantee.

The held stock-track control also passes on XP03: both models retain the
440 Hz stock tone's period within **0.00010 sample** over more than 2,000
positive crossings, with unchanged high-frequency and block-sideband floors.
Normal code, live controls and the stock-track control therefore pass without
the coherent observer. Final state: both kick tracks at 64/64/64, model 808,
centered pan; track 1 SYN page and the user's **11 (5)** allocation retained.

`out/dn2/polyphony-fix-20261029/evidence.json` asserts the final results:
**1,024 MIDI note-ons over 264.704 seconds** of valid USB audio across XP02
and XP03, no reported overflow, finite/unclipped audio and advancing frames;
all sixteen native slots routed independently; six coherent diagnostic blocks
whose raw output agrees with the original ASM within 2.24e-8 and whose master/
PCM conversion is exact; normal installed-byte identities, absent observer,
consecutive sweep timing windows, current 76-test task and final guard/heap
state. The underprimed replay is explicitly excluded. User listening applies
to XP02; no independent analog recording was made. Broader multi-device,
fresh-source fidelity and low-level handoff ownership remain separate.
