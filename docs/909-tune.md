# 909 Tune and pitch CV

The existing #25/#79 increment adds the C9/IC12 Tune path on both CPUs and
routes approved control A to it on DT, DN and DN2. Tune changes the initial
pitch sweep's discharge time rather than transposing the settled oscillator.
The [diode shaper](909-shaping.md), unloaded Decay approximation and fixed
internal audio scale remain. IDs, saved controls and MODEL policy are unchanged.

## Model and explicit approximations

S02 pp.5/11 and S05 pp.3/12 draw C9=0.33 µF discharging through
`(R57 + VR2*position) || R26`, with 22 kΩ, 100 kΩ and 330 kΩ respectively.
The provisional resistance-linear mapping gives minimum/default/maximum
time constants of 6.806/19.592/29.393 ms. During the nominal 2 ms trigger,
R21=2.2 kΩ charges C9 from a provisional 14.1 V Q2/D7 source.
IC12 gives relative frequency `1 + (R27/R26)*(C9/15 V)`, with R27=1.5 MΩ.
The independent model solves the switched RC state and its interval-integrated
phase, checked against separate eight-substep RK4 capacitor-current equations.

Settled pitch is explicitly calibrated to **52.58 Hz** from the training
recordings; the nominal component/comparator assumptions predict about
58.17 Hz. This is one global training calibration, not a fitted Tune trajectory.
Physical pot taper, Q11/C14 trigger reset, retained-charge retrigger,
transistor/diode operating points and the loaded VCA remain unqualified.

Both ASM ports integrate interval-mean C9 charge using a bounded small-argument
series. Delayed-point phase integration failed the unchanged numeric bound and
was rejected. ColdFire's private body call now accepts Tune alongside Decay;
the existing per-voice bank holds phase, amplitude, C9 and trigger countdown.
SHARC uses existing private allocation. No public SDK or saved-format changes.

## CPU and installed-emulator evidence

The Tune/current-main host suite has 156 tests plus the independent C/UI suites.
Actual ColdFire and SHARC cover fractional/end-point Tune, live changes during
charging/discharging, Decay, retrigger/interleaving and state/context guards.
Maximum 909 model errors are 1.87e-6/5.84e-6 FS and paired difference 4.58e-6 FS,
below the unchanged 1e-5 FS limit. The shared SHARC suite executes 14,298 calls,
with 4,866 code bytes and 1,024 private bytes; existing 808 checks pass.

All three latest listed firmware emulators exercise the installed change:

| Device | Result |
| --- | --- |
| DT 1.54 | 47,354 callbacks; all five 909 settings, native locks/LFO/reloads and mixed models pass. Only deferred #78 reset checks fail. |
| DN 1.44 | 117,674 callbacks; all five settings and prior functional regressions complete with no DSP violations. Only historical #20's bright-Tone exact-zero baseline fails. |
| DN2 1.12 | Standard pinned-runtime full run passes: 37,821 audio / 37,822 DSP frames, both 808 Tone checks, native Tune/Decay cases, locks/LFO/reloads and mixed models; no missing blocks or reported halt. Separate original late-MODEL probe remains #80 evidence. |

The first DN endpoint setup failed because encoder acceleration invalidated a
linear detent-to-value assumption. The corrected harness uses observed stored
values to reach the same exact endpoints/default, with the same encoder timing;
the failed setup is retained separately. This changes no firmware or acceptance
bound. Raw output and downstream PCM remain distinct checks.

Component evidence is under `out/909-tune/{coldfire,sharc}/`; those original
reports retain their old Digikit pin. The standard new-pin SHARC rerun is
`out/sharc/body808/report.json`. Native reports/captures are preserved under
`out/909-tune/native/`, with DN's corrected run in `dn-corrected/`.
DN2 uses public Digikit `a28817d61c06cdea4fb0dbc1625a238fce0b39b9` and its
normal built daemon, without a binary or fingerprint override.

## Five-setting training comparison

Actual half-second output from each CPU is compared against all three fresh
training repetitions at each setting. Timing/gain remain raw, with only the
audited reference ×4; no alignment, fitted gain or normalization. Mean raw RMS
errors below are descriptive, not frozen fidelity acceptance:

| Setting | Diode-only | Tune |
| --- | ---: | ---: |
| Default | .10283 | .08229 |
| Low Tune, short Decay | .06364 | .06519 |
| High Tune, short Decay | .06579 | .06079 |
| Low Tune, long Decay | .09448 | .12929 |
| High Tune, long Decay | .10758 | .12974 |

Default settled pitch is 52.580003 Hz versus 52.580160 Hz reference;
high-Tune/long body pitch is 54.2000 versus 54.1700 Hz. Preserve the worsening
low/short and both long waveform errors. The loaded ENV1/Q12 envelope and
Q11 finite trigger/reset are the next existing planned corrections, followed
by Attack; source alignment and full fidelity remain open. Comparison/provenance
is in `out/reference/909-tune/measurements.json`. Held-out audio and the HTML
report remain untouched. No physical devices were used.
