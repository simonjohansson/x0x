# Initial 808 software-reference comparison

27 October 2026, [#2](https://github.com/simonjohansson/x0x/issues/2).
Production DSP revision: `4e6c3c77694f29cdc47b8327012aa80373836cce`.
This diagnostic compares the current prototype before circuit alignment is
complete. No production DSP changes, gain fitting or fidelity pass is implied.

The portable local [HTML report](../out/reference/808-baseline/index.html)
embeds five selectable settings, raw/supplemental timing views, six measurement
panels per setting and twenty-five audio examples. The generated HTML, float
renders, listening WAVs and detailed `report.json` remain Git-ignored under
`out/reference/808-baseline/`; the source recordings remain ignored in research.
The HTML works offline without its neighboring files.

## Inputs and scope

Reference: Roland TR-808 VST3 1.1.4 build22074, REAPER 7.82 on macOS arm64.
The default and four Tone/Decay corners use three fresh takes each. All fifteen
WAV hashes, parameter readbacks before/after, fixed instrument controls,
identical L/R samples, saved host gain and sample-identical repeats are checked.
Held-out audio is not read. The full source provenance is in the local
`research/reference/808/README.md`, sessions and capture metadata.

Only Tone/Decay vary. Fixed source settings include BD Level=204/255,
Tune/Gain/Pan=128/255, Volume=108/127, Accent Level=0 and MIDI note36/velocity100.
The current x0x prototype has fixed intrinsic excitation and ignores pitch and
strength; native AMP/velocity processing is excluded. Consequently the source
instrument's level and raw engine scale are not calibrated equivalents.

Both compiled ASM backends are freshly executed through existing guarded
component runners. ColdFire composes its production body, Tone and coupling
kernels; SHARC executes the production SDK callback in 808 mode. This is **raw
ASM/component-emulator evidence**, not a fresh full-OS or physical-device run.
The shared ColdFire source serves DT/DN; SHARC serves DN2.

- Reference WAV: 48 kHz stereo float32, one-second preroll, twelve-second tail.
  Remove only the documented preroll at scheduled MIDI; no detected-onset trim.
- Common comparison/render window: two seconds, 96,000 samples, one START.
  Retain separate full twelve-second reference metrics. Do not zero-pad the
  unrendered x0x tail. Listening clips end abruptly at the excerpt boundary.
- Nearest native UI mapping: reference 0/128/255 maps to raw 0/16384/32512.
  The default is the approved native64/127; reference128/255 differs by
  0.198 percentage points. Endpoint positions coincide. No fitted pot curve.
- Preserve as-recorded gain and its residual. Also compare using one fixed
  reference multiplier ×4, undoing only the documented 0.25 host-track gain.
  No per-hit normalization or fitted gain; all audio examples stay unaligned.
- Primary timing remains raw. A supplementary display shifts x0x by +294
  samples (+6.125 ms), selected once from positive correlation of the default's
  first 200 ms within ±480 samples. Apply that same shift to every setting's
  waveform/residual display only. It includes phase/pitch/attack differences;
  it is not a measured device latency or an acceptance correction.

## Results

Positive-peak decay fits below describe each two-second signal. They do not
assert a single physical circuit time constant. Frequency uses the existing
cross-checked cycle estimator; individual early-cycle points are exploratory.

| Setting | Reference Tone/Decay | Reference / x0x median Hz | Reference / x0x decay fit ms | Unaligned residual RMS FS, host gain removed |
| --- | --- | --- | --- | --- |
| Default | 128/128 | 47.64 / 55.00 | 143.0 / 250.3 | 0.06474 |
| Dark, short | 0/0 | 46.67 / 55.00 | 25.4 / 142.1 | 0.03820 |
| Bright, short | 255/0 | 46.68 / 55.00 | 29.2 / 142.1 | 0.03916 |
| Dark, long | 0/255 | 47.65 / 55.00 | 365.8 / 1003.5 | 0.10987 |
| Bright, long | 255/255 | 47.65 / 55.00 | 364.8 / 1003.4 | 0.11168 |

Both CPUs reproduce the same provisional model: maximum oracle errors are
6.735e-7 FS (ColdFire) and 7.404e-7 FS (SHARC); the largest cross-CPU difference
is 8.122e-7 FS. All satisfy the existing **1e-5 FS numeric limit**, which is
separate from any reference-fidelity criterion. No VST tolerance is frozen.

The reference has a pronounced early transient and a changing pitch trajectory;
x0x has a smoother fixed-frequency body. The default spectral panel shows
reference harmonics missing from the current near-sinusoidal output. Tone
endpoint behavior must be revisited with that richer excitation and full loading,
not inferred from the isolated RC checks. Source loading and nonlinear stages
remain open in [the circuit inventory](reference-alignment.md).

## Prioritized fixes for #9 and #79

1. **Source-derived resonator and pitch path.** Replace the provisional fixed
   55 Hz mode with the selected circuit's body/forcing and initial pitch path.
   Verify equations independently, implement both CPUs, then repeat these five
   diagnostics. Do not treat lowering one frequency constant as circuit alignment.
2. **Stock Decay feedback and knob response.** The short setting currently rings
   roughly five times too long; long settings roughly 2.7 times too long.
   Derive the frequency-dependent feedback network and control curve rather
   than fitting each corner independently. Preserve live-control/state tests.
3. **Excitation shaping and loaded Tone/output interaction.** Derive the missing
   pulse-edge RC/diode/forcing stages and connected loading; inspect attack,
   pitch evolution and spectrum after each integrated change.
4. **Global output calibration.** Revisit one fixed scale after the shape changes
   and native gain/excitation paths are accounted for. Current corrected peak
   ratios vary from 0.795 to 0.900; a gain adjustment cannot fix pitch or decay.

The full grid, held-out settings, retrigger/history, other excitation strengths,
live-tail changes, high-rate aliasing checks, frozen acceptance criteria and
blinded listening remain open in #2. Do not consume held-out settings to choose
model changes. Matching this software reference is not original Roland hardware
or physical-device qualification. No new engine issue is needed: #9/#79 already
own these missing model stages.

## Reproduce

With the existing pinned submodules/toolchains and local capture corpus:

```sh
mise run test:808:body
mise run research:808:reference
```

The research task uses the existing digiemu environment and optional, pinned
NumPy2.5.4, SoundFile0.14.0 and Matplotlib3.11.2 packages; production runtime
requirements do not change. Current-source and executable hashes must match
passing component reports before any audio is rendered. Individual phases are
available through `python -m x0x.reference808_compare --phase
coldfire|sharc|report` in that environment. Re-running report alone requires the
matching float renders and their metadata; missing/stale artifacts fail.

Validation: 120 host tests and independent C/UI suites pass. The research run
also checks guards/oracle agreement, cross-CPU agreement, source/capture hashes,
fresh-repeat identity and both signs of a synthetic correlation shift. Report
charts and browser case/view switching were inspected. Listening WAV copies
are embedded without clipping/normalization; this is not a blinded listening
assessment. Existing native evidence and known #78/#80/#20 gates are unchanged.
