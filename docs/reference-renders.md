# Executable third-party drum references

[#79](https://github.com/simonjohansson/x0x/issues/79) now has reproducible host
renders of the original Plaits `AnalogBassDrum` and `SyntheticBassDrum` classes.
This is research equipment. Production C, ColdFire/SHARC ASM, saved controls and
firmware are unchanged. The [alignment inventory](reference-alignment.md) retains
the original Roland schematics as the circuit baseline.

## Source and reconstruction

The original-author sources are pinned to eurorack
`f4cfa7697095a28d292bff758beb51deb49b5a86` and its actual `stmlib` Git submodule
`e3bd7c9cc00e4364166f9905c0509b6ffd0535ec`. The original four inspected snapshots
S43–S46 match the source archive byte for byte. New S47/S48 records in the
[manifest](../research/manifest.json) contain the archive URLs, sizes and SHA256:

| Source | Archive SHA256 |
| --- | --- |
| S47 eurorack | `7bade44c4b3839c7e505a128e68896cf0b039849b8bc824a41e0051e1dfb016e` |
| S48 stmlib | `eff5d6642a93498996661e0dd4b5a1de4b98093f25a009166910726d1262b5d2` |

After a new clone, fetch these two archives manually, then run the optional task:

```sh
mkdir -p research/sources
curl -fL https://codeload.github.com/pichenettes/eurorack/tar.gz/f4cfa7697095a28d292bff758beb51deb49b5a86 -o research/sources/eurorack-f4cfa7697095a28d292bff758beb51deb49b5a86.tar.gz
curl -fL https://codeload.github.com/pichenettes/stmlib/tar.gz/e3bd7c9cc00e4364166f9905c0509b6ffd0535ec -o research/sources/stmlib-e3bd7c9cc00e4364166f9905c0509b6ffd0535ec.tar.gz
mise run research:plaits
```

The runner downloads nothing. It validates both archives before building,
extracts fresh source into temporary build directories, checks S43–S46 against
the manifest, and compiles the original headers/resources without modifying
them. Missing archives return unavailable (exit 77); a hash mismatch fails.
Downloaded/extracted code and output stay ignored. Only the manifests, harness,
runner and documentation are tracked. This is not a new production dependency.
The compiled drum/DSP sources retain Emilie Gillet's MIT notices; the full
archives also contain unrelated material under other licenses.

## Exact experiment

[`plaits_drums.cc`](../tests/reference/plaits_drums.cc) calls the classes directly:

- 48 kHz, 12-sample blocks, two seconds per capture; sustain off, accent 0.8.
- Analog base frequency 55 Hz; synthetic base frequency 50 Hz. Default Tone and
  Decay positions 0.5; Analog attack/self FM amounts 1. Synthetic FM amount 1,
  FM-decay position 0, dirtiness `0.4 - 0.25*decay^2`.
- Seven cases per class: default, minimum/maximum Decay, minimum/maximum Tone,
  disabled FM and a second trigger at sample 7200 (150 ms).
- Static zero initialization followed by the original `Init()`. This deliberately
  initializes the two transient-envelope fields omitted by the pinned synthetic
  class's `Init()` without patching that class. Each capture starts a new process.
- Explicit global noise seed 33. One silent 12-sample block primes the synthetic
  frequency interpolator before the first trigger. That block is checked for
  exact silence and excluded from the capture.

The harness bypasses the complete Plaits engine, its overdrive and hardware-clock
note correction. These settings are an explicit experiment, **not a calibration
of stock Roland knobs or an assertion that the same positions mean the same
thing in x0x**. Synthetic noise uses the original global RNG; this single-voice
experiment does not establish a production per-voice noise/ownership policy.

Both normal and AddressSanitizer/UndefinedBehaviorSanitizer builds use mise's
Clang 23.1.3 in C++ driver mode, C++11, `-O2 -DTEST -fno-strict-aliasing -ffp-contract=off`.
Strict-aliasing optimization is disabled for the original DSP's bit access.
The report records compiler flags/version, source and harness hashes, binary
hash, project revision/dirtiness and the four analytical prototype source hashes.
Bit identity across other compilers/platforms is not established.

## Results, 27 October 2026

All fourteen cases produce finite, nonzero audio. Fresh processes repeat
byte-identical output, and sanitized builds produce identical samples with no
reported ASan/UBSan failures. Decay increases late/early energy; Tone and FM
change the output. Retriggers preserve the preceding prefix but differ from
both an uninterrupted tail and a newly initialized hit. Changing the seed affects
only the noisy synthetic class. Missing/tampered archive guards and the existing
host/C suites pass (117 host tests).

The following are **descriptive fits to the rendered classes**, not original
hardware measurements or target tolerances:

| Class/case | Raw peak FS | Median tonal frequency Hz | Positive-peak decay fit s |
| --- | --- | --- | --- |
| Analog default | 0.605782 | 56.0075 | 0.105790 |
| Analog short | 0.503731 | unresolved | 0.013157 |
| Analog long | 0.650749 | 57.9239 | 0.999664 |
| Analog FM off | 0.307056 | 54.9806 | 0.106489 |
| Synthetic default | 0.894644 | 49.9672 | 0.049172 |
| Synthetic short | 0.838868 | 50.0895 | 0.020542 |
| Synthetic long | 0.950883 | 49.9901 | 0.774228 |

The short Analog hit does not provide enough reliable cycles for the existing
frequency estimator. It is recorded as unresolved rather than changing that
estimator's gates. FM, noise and nonexponential envelopes also affect these fits;
retrigger captures must not be interpreted as a single physical RC time constant.

`out/reference/plaits/report.json` holds settings, measurements and hashes.
`{analog,synthetic}-{case}.f32` contain authoritative little-endian float32 samples;
the WAV files are unnormalized PCM16 listening copies. All fourteen captures
fit within unity; the runner would retain raw float output and omit the PCM
copy for any over-unity result rather than clip or normalize it.

## What this changes in the implementation plan

The current analytical x0x prototypes differ substantially from these classes.
Over the same two-second, unshifted window, default RMS differences are
0.085353 FS (Analog versus the finite-drive 808 body/Tone/coupling) and 0.080329 FS (Synthetic
versus 909 triangle/Decay). The prototype comparison includes the subsequent finite-808-drive update;
the original third-party class captures are unchanged. These are comparisons of **analytical prototypes**,
not fresh ASM/native renders. The reference and prototypes have different gain,
control mappings, excitation and phase policies. No alignment, gain fitting,
normalization or fidelity pass/fail threshold is applied.

Useful next source-to-model-to-ASM increments remain:

1. Derive finite 808 excitation from S01/S03, then integrate it through both CPU
   backends. The executable Analog reference supplies a concrete 1 ms excitation
   and asymmetric edge example; its gain/diode approximation is not automatically
   the chosen stock equation.
2. Derive the pitch transient/feedback and deliberate residual-state retrigger
   behavior. The reference's 6 ms FM pulse and self FM explain why its measured
   pitch differs from the fixed x0x oscillator. Retain the known primary-source
   timing differences and physical/logical voice ownership constraints.
3. Keep the original Tone/Decay networks as the authority. Plaits' exponential
   Q and Tone coefficient mappings do not replace the stock VR5/VR6 derivations.
4. Derive the 909 diode shaper, pitch path and complete envelope/attack network
   from S02/S05. The author's synthetic class is only 909-like; it is useful
   executable evidence for envelopes/noise/VCA ideas, not the stock circuit oracle.

#79 remains open for the missing stock models, corrections and final alignment
report. #9/#25 own the integrated ASM changes. This increment adds no native
emulator or VST/physical-device proof; #2 remains deferred. Existing #78, #80 and
DN's failed capture baseline in #20 are unchanged and were not re-probed.
