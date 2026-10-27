# DN2 private voice allocation

Issue [#81](https://github.com/simonjohansson/x0x/issues/81) reallocates x0x's
volatile code/data space inside the existing 16 KiB voice reservation. It does
not change the pinned Elekloader SDK, module format, adapter, saved sound or
project data. The SDK's public convenience layout remains 6 KiB code / 7 KiB
data; only x0x's producer and matching diagnostics use the private partition.

All address ranges below have an exclusive end.

| Region | Previous allocation | Private allocation |
| --- | --- | --- |
| Pinned adapter | `0x20090000..0x20090800`, 2 KiB | Unchanged |
| Author code, including 64-byte read-ahead guard | `0x20090800..0x20092000`, 6 KiB | `0x20090800..0x20092800`, 8 KiB |
| Author data | `0x20092000..0x20093c00`, 7 KiB | `0x20092800..0x20093c00`, 5 KiB |
| Pinned adapter state | `0x20093c00..0x20094000`, 1 KiB | Unchanged |

The render entry remains PC16 `0xbc8400`. Usable author code increases from
6,080 to 8,128 bytes after the existing guard. Current accepted DSP uses 5,672
code bytes and 1,664 data bytes. The isolated pulse prototype's measured
7,500/4,736 bytes fit this partition, but that prototype's audio behavior and
installed delivery remain unqualified and it is not included by this change.

`tools/x0x/sharc_layout.py` copies the public layout and builds the existing
prelinked payload with the private split. It reuses the SDK's qualified adapter
and scalar checks, then runs the unchanged upstream `module_payload` validator.
Code padding, entry bounds, alignment, full owner coverage, adapter bytes/state
and oversize rejection remain enforced. All private ASM state addresses move
by `0x800`; callback arguments, output buffers and native adapter state do not.
The linker, fixtures, bridge window and native observers follow the same split.

## Qualification

The synthetic format proof is in
`out/dn2/capacity/existing-format-proof.json`. Focused host tests check both
the unchanged public default and the private bounds, including rejected guard,
adapter, overlap and entry mutations.

The existing component proof under `out/sharc-layout-relocation/` passes the
callback, selector, historical silence and full body suites. It rejects seven
callback and six selector mutations; the full body executes 14,298 calls.
All 29 existing 808/909 output files are byte identical to accepted `65aeaf7`.
Reversing only the address relocation reproduces the accepted kernel sources.
The original wrapper's post-success report-printing errors are recorded
separately in `diagnostic-qualification.json`; they do not replace or repeat
the successfully saved component reports.

Thirteen focused host tests pass. Compiled C delivery and 82 synthetic native
bridge calls also pass. The bridge fixture now pads the entire 8 KiB code span;
a 7,500-byte test catches the old helper's 6 KiB assumption. Its first diagnostic
run reached the bridge assertions and then failed while printing a hash from a
removed local variable. The failed log is preserved; the report expression was
fixed and the adapter check rerun in a separate diagnostic copy. The running
native source snapshot was not changed by that report-only fix.

Installed DN2 OS 1.12 qualification passes on the normal pinned Digikit daemon:
37,816 audio / 37,817 DSP frames, with no halt, missing block or ColdFire error.
The existing controls, locks/LFO, persistence, mixed models, stock coexistence,
808 checks and five 909 settings pass. The fresh 909 witness is observed at age
32 / remaining 64 samples inside four of the original 24 allowed frames. Phase,
C9 and encoded C8 errors are 1.86e-9 cycles, 1.12e-7 and 1.24e-6 under the
unchanged 1e-5 bound. Raw DSP and downstream PCM remain separate evidence.

The separate original-order late-MODEL probe passes on the same firmware:
immediate CC after double STOP, exactly 3,000 post-CC DSP frames, fresh track 2
selects 909 within three of the allowed 32 frames, and older voices retain their
models. It runs 4,776 audio/DSP frames without halt, missing blocks or CF error.

Firmware SHA256:
`b1b7b354631046229eaf77649ff72c3a31eb816e1004dfe89d4a9090f54eb239`.
Normal daemon SHA256:
`0e3cbb14f59620f8bd99197f7d9c28b8748639772ad1d60b76f9240308cee764`.
The immutable source inventory, build/adapter checks, full native result and
late-MODEL result are under `out/dn2/capacity/`; the full result is retained in
`native-full/run.log`, and the separate probe in `late-model/report.json`.

DT/DN code is unchanged; their existing native evidence, including deferred #78
and unresolved #20, remains separate. Reference fidelity, Attack/noise
integration and physical timing are not gates completed by this allocation.
