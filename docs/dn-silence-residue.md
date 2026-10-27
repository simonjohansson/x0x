# Digitone silence residue: downstream attribution

The exact-zero native capture gate in [#20](https://github.com/simonjohansson/x0x/issues/20)
remains failed. A bounded investigation of the reproduced 808 bright-Tone
baseline places the residual after the x0x body and native AMP output.
It does not establish an emulator arithmetic defect or justify a mod workaround.

The frozen run uses commit `d3ba46f`, Digitone OS 1.44 and firmware SHA256
`e641724c50928d751b2739bf35bd4dabb529a6c724ad827e75e751ebe3b68d49`.
Across 150 native 32-sample blocks, all selected x0x inputs to the stock
per-voice filters are exactly zero. Those filters nevertheless repeat constant
outputs of −3/−8/−8 Q31 words with unchanged internal state. Tiny signed 24-bit
SSI values become sparse −1 PCM16 values under the existing arithmetic shift.

Diagnostic zeroing before the stock filters does not remove the residue;
zeroing after them reduces it, with downstream mixer/master state also
contributing. A zero ADC peer does not remove it. These interventions are
diagnostic only and are not production changes. The native fractional/truncating
MAC configuration is consistent with fixed-point filter limit cycles, but
correctness against hardware is unproved. A pure-stock note/release comparison
is inconclusive because its FM source remains nonzero after three seconds.

Evidence and original raw words are preserved under
`out/dn/silence-residue/`: `diagnosis.json`, `run-01/stage2-attribution.json`,
`run-01/filter-cycle.json`, snapshots and the inconclusive stock probe.
Later waveform-specific zero baselines do not resolve this historical failure.
Do not subtract the residue, relax the exact-zero gate, bypass stock filters or
clear unrelated state. A correction requires a demonstrated arithmetic defect;
otherwise revising native-silence acceptance is a separate reviewed decision.
Only emulator evidence was collected; no physical-device qualification.
