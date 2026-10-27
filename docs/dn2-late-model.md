# DN2 late MODEL delivery: upstream trace

## Fix published and pin adopted

Digikit revision `a28817d61c06cdea4fb0dbc1625a238fce0b39b9` fixes native
SIMR/CIMR mask effects and is now the submodule pin. The approved public patch is
[draft upstream PR200](https://github.com/ElekLabs/digikit/pull/200), not merged.
Fourteen synthetic peripheral tests, two actual native-MMIO tests and eighteen
neighboring SSI/timer checks pass. Its broader routed gate is incomplete due
to generated-core/frontend/workspace prerequisites, as recorded in that PR.
No mod delay, retry, selector or control-map workaround was introduced.

Unchanged production 808-leakage firmware SHA256
`42558bbf749b98635ceec1bcf8a388607978b0269d03c5dfa08e6409e5821092`
passes both its full scenario (including previously missing bright note75) and
the original late T2 probe on the fixed candidate runtime. After the original
3,000-frame post-CC settle, the fresh note selects 909 in six frames, within
the unchanged 32-frame acknowledgement bound. Stored MODEL changes 0→32512;
old voices retain their latches. There is no additional pre-CC idle pause.
Evidence: `out/dn2/intc-requalification/qualification.json` and frozen reports.

The adopted pin's normal daemon builds without generated-core regeneration or
binary/fingerprint overrides. The standard current Tune/full-OS run passes
37,821 audio / 37,822 DSP frames, including both 808 Tone checks and native
controls/mixed models. Original-order late qualification on that normal daemon
remains the final adoption gate in #80; the candidate result is kept distinct.
Native build/pin receipts are in `out/909-tune/digikit-adoption.json`.

## Historical reproduction before the fix

A focused diagnostic using upstream Elekloader
`b893c9317936633d7a32829b618c2867ee99277c`, DN2 OS 1.12 and the pinned Digikit
reproduces the late post-double-STOP T2 CC45 failure. It distinguishes a dropped
edit from a later overwrite; it does not establish which upstream layer is
responsible or adopt a mod workaround.

The frozen production baseline is the main-input build, firmware SHA256
`772e35814e66a4a3cfec6bad36b205991bd5771507ffb87c173e0a3b37a6ac81`.
A separate SDK-lookup logger uses firmware SHA256
`7189d8dcce07ce9f3b68ff04e763c4d26425b4b377ae41c10fb31cb0ff63a481`,
retaining the frozen production SHARC/Core/x0x artifacts. Instrumentation changes
ColdFire instruction timing; keep this evidence distinct from production boot.

Before the late CC, T2's stored MODEL is 0 and the diagnostic SDK CC-lookup
counter is 32. All three CC45=127 bytes enter the receive ring: received-byte
and taken-interrupt counts both increase from 126 to 129 and the queue drains.
Across about 3,000 DSP frames, however:

- SDK `dn2_cc_code` is never called: its counter stays 32.
- Stored T2 MODEL stays 0; the native write-watch records no overwrite.
- All 42 write-watch events were retained, with no truncation.
- The following note76 therefore still receives raw MODEL 0 and selects 808.

The loss occurs **before SDK CC lookup and DSP selection**. Changing the DSP
selector, CC map or bounds would not repair that observed path. No extra idle
delay, different-track substitution or widened acceptance bound was adopted.

Next trace the native MIDI receive/parser/dispatch path between the receive ISR
and SDK lookup. Native firmware behavior versus emulator input/interrupt
synchronization remains unproved. Then fix the responsible layer and qualify
the late T2 transition, old voices' latches and mixed tracks. Earlier passing
MODEL paths and general firmware runs do not close this separate gate.

Local evidence is under `out/dn2/late-model-upstream/`: `diagnosis.json`,
`probe-observations.json`, `probe-report.json`, `native-write-watch-2.jsonl`,
`native-write-watch-2.summary.json` and `provenance.json`. The focused setup
checks pass; its late-transition verdict fails. No real device, reference audio
or HTML report was used.

## Stage trace: receive callbacks reorder the bytes

A subsequent isolated diagnostic keeps the same frozen production artifacts,
logging the native receive callback and complete CC-message handler before and
after their original functions. The wire/DMA ring contains the requested bytes
`B1 2D 7F`, but the native parser buffer contains `B1 7F 2D`; the queued control
event therefore requests controller127/value45 rather than MODEL45/value127.
The SDK correctly reports controller127 as unmapped. This is neither a CC gate
nor a later stored-MODEL overwrite.

Receipt counters go15→16→15→16 as nested native receive callbacks overwrite
each other's parser state. Native ISR400021a0 writes source28 to SIMR at
fc04c01c before lowering IPL to3, then writes CIMR atfc04c01d on return.
The configured source is level4. The pinned Digikit INTC's SIMR/CIMR writes
are plain register storage and do not update IMR; MIDI servicing continues to
see an unmasked source and permits reentry. The missing interrupt-mask side
effects are an emulator fault; patching x0x selection/CC mapping or adding idle
time would conceal it.

Stage evidence, frozen snapshot/address receipts and diagnostic source are in
`out/dn2/late-model-stages/`, including the exact requested wire bytes and the
reordered parser/control event. Instrumentation affects timing, so retain the
original production failure separately. Fix and qualify Digikit's hardware mask
semantics upstream, then rerun production #80 and the missing bright-Tone note.
A common cause for that separate missing-note observation remains unproved.
