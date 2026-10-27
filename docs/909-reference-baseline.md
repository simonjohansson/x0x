# First bounded 909 recording comparison

This #2 diagnostic compares the [diode-shaped 909](909-shaping.md) against
the default and four Tune/Decay corners, with reference Attack fixed at 128/255.
It covers **0–500 ms after scheduled MIDI**, using actual CPU component output.
It is not native-emulator, complete-tail, held-out or stock-fidelity acceptance.
The provisional model still has fixed 50 Hz pitch and no Tune or Attack path.

## Inputs and evidence boundary

Only fifteen explicitly constructed `grid-u...-a128-d...-r...` training WAVs
were opened: three fresh takes for each selected setting. No `validation-...`
audio was discovered or read. Every selected WAV/session hash, MIDI protocol,
17-second stereo float format, channel equality, silent preroll, bounded peak,
terminal residual and all 197 before/after readbacks were checked. Fixed controls
were checked across settings, including BD Level 220, Gain/Pan 128, Volume 108,
AC Level 0, shuffle 0 and bypass/wet/delta 0/1/0.

The reference's own saved projects independently establish track volume 0.25,
master volume 1, centered pans, one source instrument, no extra FX or hardware
sends, and no input monitoring. Therefore the common **reference multiplier x4**
removes that documented host attenuation. The report also retains every
**as-recorded x1** residual. There is no fitted gain, normalization, DC removal,
onset trimming or time alignment. The reference begins six samples after MIDI;
the component begins at sample zero. Neither offset is removed or presented as
measured hardware latency.

The current actual CPU shaper proofs are reused from `out/909-shaping`, including
their matching component reports, executable/source hashes and recorded sample
hashes in `comparison.json`. The copied 24,000-sample renders are rechecked
against the independent diode/circuit model under the unchanged 1e-5 FS bound.
Equal-Decay rows intentionally reuse identical component audio because Tune is
unimplemented. ColdFire's body has no Tune/Attack arguments; the reused SHARC
fixture delivered Tune 16384, Attack 12345 and pitch word 15487, all ignored by
its current 909 DSP. **These are not requested-Tune or Attack delivery checks.**
The reference Attack is 128 in every selected recording, as requested.

Reference fresh takes are not averaged or treated as necessarily identical.
Default takes differ by up to 0.0195133 FS as recorded, confined to the first
50 ms; both high-Tune triplets are identical. All selected triplets are exactly
identical after 50 ms. Every take and pairwise variation measurement is retained.
This does not establish the reference's complete noise or retrigger model.

## Raw waveform diagnostic

RMS residuals below use x4 reference gain and retain all three fresh takes.
Ranges describe source variation, not confidence bounds or passing tolerances.

| Reference setting | ColdFire RMS residual FS | SHARC RMS residual FS |
| --- | --- | --- |
| Default | 0.102832–0.102850 | 0.102832–0.102850 |
| Low Tune, short Decay | 0.063641–0.063654 | 0.063641–0.063654 |
| High Tune, short Decay | 0.065788 | 0.065788 |
| Low Tune, long Decay | 0.094485–0.094515 | 0.094484–0.094515 |
| High Tune, long Decay | 0.107577 | 0.107577 |

Maximum peer-CPU difference is 4.229e-7 FS. That small numeric difference does
not make the large recording mismatch a pass. Raw peaks, RMS, onset, DC,
positive/negative peak-envelope fits, 10-ms RMS trajectories, spectral bands,
cycle validity and 25/50/150-ms residual windows are retained in
`out/reference/909-baseline/measurements.json`. Individual raw component outputs
and their provenance are beside it; the full recording corpus remains unchanged.

## Next existing #25 work, in measured order

1. **Stock Tune/pitch-control path.** Both current CPUs stay near 50 Hz at every
   requested Tune setting. The reference's reliable late default/long body is
   about 52.580 Hz. High-Tune long Decay has a 50–200-ms median of 54.170 Hz,
   then about 52.580 Hz at 200–500 ms. High-Tune short Decay's body median is
   59.967 Hz, but it becomes too quiet to establish a late settled frequency.
   This supports the existing source-defined Tune envelope path, not converting
   Tune into chromatic transpose or fitting an arbitrary per-corner oscillator.
2. **ENV1/Q12 VCA and Decay mapping.** Descriptive positive-peak fits over the
   available half second are about 57.3 ms at reference default versus 181.8 ms
   in the model, and 98.5–98.6 ms at reference long Decay versus 345.5 ms.
   Reference short fits are about 17.7–18.0 ms versus 15.5 ms. These are waveform
   fits, not identified single circuit RC constants. Preserve the planned
   loaded envelope/VCA and stock pot-taper work rather than applying one global
   C8 multiplier or hiding the control-dependent difference with gain fitting.
3. **Separate Attack branch.** The initial reference spectrum and repeat
   variation differ from the deterministic body. In the first 20 ms, the
   150–1000-Hz spectral share is roughly 20% at low Tune and 97% at high Tune,
   versus about 0.14% for the current short-Decay component. Tune/FM and other
   transient effects contribute; this cannot all be attributed to missing noise.
   Attack was held fixed, so this slice cannot calibrate its mapping. Use the
   existing grid recordings and circuit branch in the later planned increment.

All reliable pitch-window summaries require at least three valid cycles under
the existing amplitude floor and independent peak-period cross-check. Sparse
early cycles remain unresolved. The half-second window cannot qualify full
tails or determine whether later reference residuals are physical circuit noise.
The generic diode operating assumptions and provisional output scale remain
explicit; no additional output calibration is claimed.

## Reproduce this bounded diagnostic

Preserve the matching isolated component snapshot in `out/909-shaping` and the
local reference corpus. Refresh that snapshot's component and peer-CPU proof
when its sources change; the diagnostic rejects stale images, model sources,
component reports or sample hashes. It deliberately does not run a new native
test, rebuild firmware or open the source instrument.

Run `python -m x0x.reference909_compare` through mise with the existing capture
runtime (NumPy 2.5.4 and SoundFile 0.14.0). Three focused host tests cover the
training-name allowlist, audited gain/routing requirements and bounded-window
measurement behavior. No general comparison framework or HTML is added.

The HTML report and held-out audio remain untouched. #2/#25/#79 and the
separate #78/#20/#80 native gates retain their own acceptance evidence.
