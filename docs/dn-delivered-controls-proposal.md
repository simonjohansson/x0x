# DN delivered controls: narrow proposal for review

Investigation for [#75](https://github.com/simonjohansson/x0z/issues/75),
26 October 2026. **Proposal only; no new hook, API or firmware patch is
implemented or approved here.** [#40](https://github.com/simonjohansson/x0z/issues/40)
remains open. Scope is Digitone mk1 OS **1.44**, Elekloader PR 200 commit
`2ab5f424c4721e4277d2112a5ae755d9938f50d6` and digiemu
`f57c2f237e84b8ff91bc3adb2a2931bccf9928e9`.

The smallest candidate uses existing Core events: retain the
`ev_render_params` pointer for this render interrupt, then read its final
contents inside the later machine render callback. This needs proof of the
bank's lifetime, event ordering and invalidation at this exact pin before
production adoption; it does not create a public lifetime promise. If the
existing route cannot satisfy those checks, propose one read-only final-parameter event
at the site below. Do not privately patch firmware or recreate its modulation
arithmetic in x0z.

## What is established

The bounded native test executes actual stock smoothing, the linked Core
parameter event, the compiled C adapter and handwritten diagnostic assembly.
For SYN2 A, sound slot 27 of voice 3, target **12345** produces pre-controller
frame words **370, 730, 1078, 1416, 1744, 2062, 2370, 2670** over eight calls.
`dnm_knob(3, 8)` and the adapter continue returning **12345**. The report
explicitly records `render_frame_delivered: false`; this is evidence of the
transport limitation, not acceptance of delivered controls.

Reproduce with `mise run test:dn:native`. The ignored report is
`out/dn-adapter-native-report.json`; the tracked test is
[digitone_adapter.py](../tools/x0z/digitone_adapter.py). A recompiled observer
that substitutes the target accessor for the frame is rejected. This test
does not boot the OS, establish locks/controllers/LFO delivery, or measure
the DSP-to-audio lag.

The downloaded stock SysEx SHA-256 is
`d4f200d04484333d82822db7744e6484d0def8f2db8ddf55ee2b780cc13c9659`.
Its main image SHA-256 is
`fce648a97c6c5d93b961732e8f8db6b02e0820c6d344c7e2131fa05a4b3168e4`.
The disassembly below was checked against that stock main image, loaded at
`0x40000400`, rather than inferred from a different OS profile.

## Existing supported surfaces

| Surface | What it supplies | Can it supply final controls now? |
| --- | --- | --- |
| `dnm_knob`, `FW_VOICE_PARAM` | Target words at `fw_voice_params + 18 + 158*v + 2*k` | No: native smoothing demonstrably changes a separate frame. |
| `ev_render_params(words)` | Smoothed, lock-bearing words before controllers and LFOs; `words[79*v+k]` | Its documented callback-time values are too early. Retaining the pointer until the later machine callback is the smallest candidate, but the SDK does not explicitly guarantee that lifetime. |
| `FW_LFO(v,i)[FW_LFO_DEST/FW_LFO_MOD]` | Each LFO's destination and signed contribution | Insufficient: no complete controller/final frame, and stock applies clamping between LFO contributions. Summing contributions onto targets would change smoothing and saturation behavior. |
| `ev_render_voices` / machine `render` | Eight audio blocks / one replacement block, after the final-control calculations | No parameter pointer argument. It could consume the earlier pointer after same-interrupt lifetime and ordering are proved for the matched pin. |
| `fxkit` | Separate effect controls, mixer, LFOs and locks | A different effect path; it does not provide the native per-voice final synth frame. |

The current documented exports therefore do not yet establish a complete,
supported final-control route. A successful same-interrupt pointer experiment
alone would establish pinned implementation behavior, not a new lifetime
promise for a public callback argument.

## Exact native ordering

These are probe/review addresses, not proposed hard-coded x0z addresses.

| OS 1.44 site | Instructions / behavior |
| --- | --- |
| `0x4009d1e4..0x4009d262` | Toggle bank index `fw[0x80001fa0]`, select `bank = 0x80001fa4 + 0xa90*index`, clear it, and save `frame = bank + 80` at `-108(a6)`. The frame's cleared extent is `0xa40` bytes. |
| `0x4009db96` | `4eb94009bf86`: call native smoother `0x4009bf86(frame, fw_voice_params)`. Render MACSR setup at `0x4009d1de` is `a93c00000020`. |
| `0x4009dba0` | Stock `4eb94009c078`: controller stage. Core replaces this call with `core_render_params`, dispatches existing callbacks with `frame+18`, then tail-jumps to the original controller stage. |
| `0x4009dd02` | `4eb9400fed62`: native two-LFO-per-voice processing. At `0x400ff130..0x400ff15e`, a contribution is added to the selected word and clamped to `0..0x7f00`; the word is then stored. |
| `0x4009de38..0x4009df36` | Further pitch/header and pan/gain processing. In particular `0x4009df28` stores a clamped word after the LFO call. A hook immediately after the LFO call is too early to describe the whole final stage. |
| `0x4009df48..0x4009df58` | Push `frame`; `0x4009df4c` is `4eb940097680`, calling `0x40097680(frame, gain_vector)`, then `addq.l #8,sp`. The inspected helper reads parameter words and writes eight gain-vector entries; it does not store into the parameter frame. |
| `0x4009df74..0x4009dfe6` | Pack selected words from the generated bank into main SRAM. The first copy is 74 bytes per voice from `bank+132+158*v` to `0x80001c00+74*v`: sound slots 17..53. The complete expanded 79-word record is not the compact DSP wire format. |
| `0x4009e026..0x4009e050` | Configure eDMA channel 47 from `0x80001c00` to shared RAM `0x10000000`, then start it. The outgoing compact parameter packet is `0x3a0` bytes. |
| `0x4009e06c..0x4009e098` | Select the other bank. Stock `0x4009e098` is `4eb940098fc4` (`VOICE_PREP`); Core wraps it with `core_render_voices`, which subsequently invokes the companion's `dnm_render` at event order 50. |

The generated words stay in the selected SRAM bank through this sequence;
the later code changes which bank its registers address rather than moving
the captured words. That supports the retained-pointer candidate by static
inspection. It does not yet prove every runtime path, event ordering with
other mods, or the callback argument's supported lifetime.

An isolated local prototype subsequently observed 59 complete event sequences
in standard `Session(hle=False)` mode: in, pre-controller, controller, LFO,
final, late consumer, out. Both SRAM banks alternated and the consumer's 1264
copied bytes matched the final same-bank view. Six separately labelled native
stage calls with injected state produced fractional final values distinct from
target 12345; a deliberately missing capture failed closed and recovered in
the next block. These are observer experiments, not production adapter or
native lock/lifecycle acceptance. The tracked reusable harness is now
[digitone_transport.py](../tools/x0z/digitone_transport.py), with
`mise run test:dn:frame` for bounded stages and `mise run test:dn:transport`
for the separate standard full-OS observer. Its generated subscriber, firmware
and reports stay in ignored `out/dn/transport`.

Strict diagnostics are separate: stock code at `0x4009de90` reads `0x12a`
with A0=0 under that fixture's model settings, both with and without the observer.
The strict flag is set in the first cycle; Session reports it after a slice.
Standard-mode sequences must not be called strict-qualified, and their success
does not resolve that model/setup limitation.

## Preferred next step: prove the existing-event route

The observer harness establishes the current-pin bank route under the stated
emulator settings. The next increment is production adapter consumption and
the remaining native source/lifecycle/timing checks below; the prototype alone
does not close #75.

Prove that the `ev_render_params` argument remains readable through the machine
callback of the **same** render interrupt, with its contents modified by the
subsequent stock stages. Keep its existing pre-controller behavior unchanged.
Inspect the SRAM bank ownership and every relevant event path at the matched
pin, then test them in the emulator. No lifetime across interrupts is needed,
and no new public SDK contract is implied by this private implementation proof.

If supported, x0z can privately capture that pointer, read it inside its
machine render callback, and clear it at render entry/exit so missing callbacks
cannot reuse a previous bank. Use the documented Core events, including
`ev_render_in/out`, rather than recovering `a6`, a bank index or a firmware
address. Read only the mapped words from the eight voice records, preserving
their actual fractions. Resolve sound slots from the pinned stock parameter
records and the reviewed knob mapping. The existing adapter's current
`dnm_knob` call must not be presented as having acquired this behavior merely
because a frame pointer was captured elsewhere.

This is a private x0z adapter follow-up after lifetime review and tests; it
does not change `dnm_knob`, a machine ID, a saved slot or an engine contract.
If the bank cannot be consumed safely within that interrupt, stop this approach
instead of retaining an invalid pointer. An upstream documentation clarification
could make a wider promise, but is not a prerequisite invented by this project.

## Fallback for Core review: one final-parameter observer

Only if the existing-event route fails the required lifetime/ordering proof, propose a new Core event,
provisionally `ev_render_params_final`, wrapping the six-byte call at
**`0x4009df4c`** (`4eb940097680`). The wrapper first executes the original
`0x40097680` call with its original two arguments, then dispatches observers,
and resumes at `0x4009df52`. This observes completed controller/LFO/pan/gain
words before packing/DMA. Exact post-helper state preservation and the claim
that later packing leaves these words unchanged are implementation tests,
not assumptions a mod should encode.

Proposed minimal callback: `void f(const int16_t *words)`, where `words` is
voice 0 slot 0 (`frame+18`), and only **8 * 79 words / 1264 bytes** are promised.
No header, FX record or compact-packet layout is exposed. Core owns the
storage; observers may read/copy required words during the callback and may
not retain or write the pointer. No allocation, waits or UI calls; preserve
MACSR, and preserve any additional EMAC/register state required by the
reviewed Core wrapper. With no subscriber the original native call must run
unchanged. Existing `ev_render_params` writers retain their present semantics.

Upstream would own this one firmware site, event registration, an appropriate
new Core capability/version requirement, SDK declarations and documentation.
x0z would copy only its approved control words into private state for the
later machine callback. No private parallel patch or silent fallback to
targets should be added. OS 1.43 is outside x0z's latest-only scope; any wider
upstream OS support requires its own verified sites and tests.

## Block ownership and acceptance gates

The stock documentation says a parameter frame's audio reaches
`ev_render_voices` **two blocks later** (64 samples, about 1.33 ms at 48 kHz).
The callback late in the **same** interrupt sees final words for the newly
generated bank while the original FM audio belongs to the other bank.
Neither proposed route makes those generations identical. The current bounded
eight-call test has no DSP/audio scheduling and does not measure that lag.

For the first control-delivery test, record generated-block identity and the
actual machine-callback block separately. A custom machine renders on the main
CPU, so the stock DSP delay must not be silently added to its controls or
subtracted from its START metadata. Before claiming native timing parity,
trace START, slot reassignment, final controls and audible output together;
any delayed policy must carry the matching ownership metadata, not a free
running two-element value queue. Pitch, gate, machine identity and AMP/velocity
remain their own existing companion paths; a word-frame observer alone does
not qualify their timing or modulation semantics.

Small deliverables, in order:

1. **Route/lifetime proof:** establish the existing same-interrupt bank lifetime
   and guards at this pin, or present the single fallback event for explicit
   review before changing the public boundary. No production descriptor or
   saved layout is needed.
2. **Bounded native proof:** real live edit and native locks, mod-wheel /
   breath / aftertouch, both LFOs separately and together, final saturation
   and fractional values reach the compiled adapter at the chosen point.
   Verify all eight slots and track isolation; retain the exact smoothing
   trace. Compare captured words against the native final frame, not targets.
   Check actual mapped ranges before changing any adapter rejection policy.
3. **Mutation and ownership checks:** omit/redirect the chosen event, feed the
   pre-controller frame or target buffer, use the wrong bank/voice, reuse a
   stale pointer and inject a frame write; each must fail. With no subscriber,
   stock packet/audio and live machine routing remain unchanged. A fallback
   wrapper additionally preserves original call count, registers, stack, CCR
   and required EMAC state, with only declared memory writes.
4. **Integration timing:** use an isolated digiemu fixture with both native
   CPUs to trace generated frame, DMA packet, START, companion render and
   audible block. Establish the documented two-block FM relationship and
   the replacement machine's actual relationship; do not align waveforms
   away to conceal a difference. Then measure callback overhead. Emulator
   evidence still does not qualify physical deadlines or kick fidelity.

## Inspected primary sources

- [Core parameter event](../vendor/elekloader/mods/core-dn1/block.s),
  [audio event](../vendor/elekloader/mods/core-dn1/voices.s),
  [entry/exit events](../vendor/elekloader/mods/core/render.s),
  [OS-specific sites](../vendor/elekloader/mods/core-dn1/mod.json).
- [Core C contract](../vendor/elekloader/elekloader/sdk/include/digitone-mk1/core3.h),
  [native timing description](../vendor/elekloader/docs/ADAPTING.md#key-leds-and-each-blocks-sound-parameters-core-dn1-33-digitone-mk1),
  [machine API](../vendor/elekloader/elekloader/sdk/include/digitone-mk1/machines.h),
  [target accessor and companion rendering](../vendor/elekloader/mods/machines-dn1/machines.c),
  [companion subscription order](../vendor/elekloader/mods/machines-dn1/mod.json).
- [digiemu two-CPU/DMA model](../vendor/digiemu/emu/dsplink.py). Its scheduling
  implementation is emulator evidence, not an independent hardware timing
  measurement. The stock disassembly sites above can be regenerated from
  the verified local firmware; extracted firmware remains ignored.
