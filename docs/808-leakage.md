# 808 Q43 leakage and pitch sigh

This #9/#79 increment adds amplitude-dependent Q43 leakage to both CPU
renderers. It preserves the calibrated 47.65 Hz quiet-body pole, existing Decay
anchors, shaped main/C39 inputs, voltage encoding and approved saved controls.
It does not impose a generic pitch envelope. The main-input-only measurements
in [the preceding checkpoint](808-main-input.md) remain historical.

The native results below describe the original `d3ba46f` run. Its DN2 MIDI/missing
note failures were subsequently resolved by the pinned upstream Digikit fix;
[unchanged-firmware requalification](dn2-late-model.md) passes the full and
original late-MODEL scenarios. The DN baseline remains open in #20, with
[downstream attribution](dn-silence-residue.md). These native fixes do not change
the 808 algorithm or qualify its remaining circuit/fidelity gaps.

## Circuit relationship and approximation

S03 §8.2/Eqs.8–9 and S01 p.9 describe current through Q43 when Vcomm swings
negative. The original PDF gives **V0 = -0.556 V**, m=1.4765e-5 A/V and
alpha=14.3150/V; its OCR loses the knee's minus sign. The fitted current is
`-m/alpha * log(1+exp(-alpha*(Vcomm-V0)))`.

Use its hard-knee asymptote for this first integrated leakage step:

```
iC = m * min(Vcomm + .556, 0)
```

This is an explicit ideal-knee approximation to the published fit, not a
measured transistor model or a parameter fitted to the recordings. The finite
soft knee, complete frequency-dependent C43 feedback, mutual source loading,
intrinsic accent and residual-state retrigger remain open.

With R165=47 kΩ and R166=6.8 kΩ, Eq.9 simplifies to

```
1/Reffective = 1/(R165+R166) + R165/(R165+R166)*iC/Vcomm
```

Use the equivalent current term directly in the capacitor KCL:
`extra dq2/dt = -R165/(R165+R166)*iC/C42`. It never divides by Vcomm, so the
zero crossing needs no arbitrary epsilon or singular-resistance clamp.
Leakage is disabled while Q43 already grounds the attack branch for 6 ms.

For the current calibrated state z=w+i*y, output b=u+w, a=1/(R167*C41),
sigma from Decay and omega=2*pi*47.65:

```
q1 = -a*(sigma*w + omega*y)/(sigma*sigma+omega*omega)
Vcomm = u-q1
extra dw/dt = R165/(R165+R166)*iC/C42
extra dy/dt = -sigma/omega * extra dw/dt
```

The leakage flow leaves q1 and Vcomm constant when u is held, so each leakage
half-step is exact. Both ASM ports place a half-step before and after the
existing exact linear/source step. This symmetric split is a discretization
choice; it is checked against an independent continuous ODE, not assumed to
be the original circuit. Live Decay preserves the existing state policy.

## Integration and numeric checks

No dynamic state word, saved value or SDK interface was added. ColdFire keeps
five words per voice and uses a 96-byte frame; SHARC keeps 1,024 private bytes,
reusing its source-bias scratch only after the attack. The block-entry counter
prevents leakage on the last attack interval before the physical state
conversion. Both ports interpolate the common-node factors over the existing
Decay segments, including a midpoint curvature correction.

The independent oracle uses four RK4 substeps per post-attack sample and exact
source-node decay. Refinement to eight substeps, physical KCL and invariant
checks, live controls, all native coefficient positions and continuation from
a captured native state have dedicated tests. Two-second splitting error is
at most 7.890e-7 FS at the tested positions; this is separate from arithmetic
and interpolation error in actual CPU execution. The numeric waveform limit
remains 1e-5 FS. No gain/time fitting, limiter or tolerance relaxation.

The native DN2 Tone observer now continues that nonlinear ODE from captured
w/y, C40 and C39 state and propagates the Tone capacitor's voltage/current
history. A linear settled-sinusoid formula would no longer test the actual
sound. Native before/after snapshots and callback counts remain distinct from
isolated CPU waveform proof.

142 host tests and independent C/UI suites pass. Both full CPU suites pass,
including the shared 9,012-call SHARC suite: 3,490 code bytes / 1,024 private
bytes. Additional guarded interpolation probes pass without changing the
1e-5 FS bound. Instruction counts remain informational.

## Priority and remaining work

The training-only diagnostic at `out/reference/808-feedback-analysis/` found
that the long reference's early reliable frequency falls from about 55.7 Hz to
47.65 Hz, while the previous implementation immediately settled near 47.65 Hz.
It accumulated about .61 cycles of phase lag. Phase-or-waveform mismatch
accounts for about 88% of long-tail residual energy; this is a descriptive
decomposition, not permission to align recordings or ignore amplitude error.

A separate nominal linear C43-feedback candidate settles around 49.44 Hz and
changes the maximum Decay to about 544 ms. It cannot implement this nonlinear
sigh and would reintroduce the known settled-pitch mismatch. Its unported
model/proof is preserved in ignored `out/reference/808-feedback-candidate/`
for the later feedback step; it is not a production or fidelity pass.

#78 DT resets remain deferred; historical DN residue #20 and distinct late DN2
MODEL #80 remain unresolved/unqualified. No physical-device claim. The HTML
report and held-out recordings remain untouched.

## Five-setting training comparison

Both actual CPUs rendered two seconds at the default and four Tone/Decay
corners. The same fifteen training takes pass hash/protocol/repeat checks.
Only the documented reference multiplier x4 is applied; raw mod gain and
scheduled MIDI timing are retained, without normalization or alignment.

| Setting | Whole-clip raw RMS FS, main-input / leakage |
| --- | --- |
| Default | 0.041022 / 0.020685 |
| Dark, short | 0.005352 / 0.003859 |
| Bright, short | 0.005978 / 0.004630 |
| Dark, long | 0.081041 / 0.049761 |
| Bright, long | 0.082112 / 0.050461 |

All five whole-clip errors improve: about 50% at default, 23–28% at short
Decay and 39% at long Decay. The first 6 ms are exactly unchanged; first-25-ms
errors improve 14–20% and first-150-ms errors improve 23–52%. The default whole
error is now below the earlier pre-frequency-switch result of .02770 FS.
These are training diagnostics, not acceptance thresholds or a fidelity pass.

The maximum full-render error versus the independent nonlinear ODE is
3.626e-6 FS for ColdFire and 1.951e-6 FS for SHARC. Maximum cross-CPU
difference is 5.226e-6 FS, below the unchanged 1e-5 FS numeric limit.
Local source/executable/sample hashes, raw floats, both CPU residuals and
windows are in `out/reference/808-leakage/measurements.json`.

The pitch trajectory is still imperfect. For dark/long, reliable windows
require at least three valid cycles above the existing amplitude floor:

| Window | Reference / current frequency, Hz |
| --- | --- |
| 25–75 ms | 53.160 / 51.875 |
| 75–150 ms | 49.237 / 50.794 |
| 150–300 ms | 47.778 / 49.722 |
| 500–1000 ms | 47.652 / 47.650 |

The initial sigh is too weak and persists too long. **The 150–300-ms frequency
submetric regresses:** the previous 47.648 Hz was closer to the reference than
the new 49.722 Hz. The default 75–150-ms estimate also worsens (47.661→49.283 Hz
against 47.857 Hz); long 300–500-ms frequency errors grow as well. Preserve
these regressions alongside the improved raw residuals; the complete retained
feature list is in the measurements JSON.
Short-tail trajectory windows lack sufficient reliable cycles and are masked;
do not turn their noisy estimates into pitch claims. Continue the existing
feedback/input/transistor alignment using these remaining errors; do not fit
an unrelated pitch envelope or close #9/#79/#2.

## Installed-emulator results

All three latest listed firmware emulators ran the changed DSP. These native
results are separate from the isolated CPU/reference comparison:

| Device | Current run | Remaining failure |
| --- | --- | --- |
| DT OS 1.54 | 39,631 callbacks / 27,977 observed 808 coupling blocks; controls, raw/downstream audio, locks/LFO, reload, mixed models and 909 checks complete | Only the known parameter/page reset checks in deferred #78 |
| DN OS 1.44 | 100,787 callbacks / 92,407 observed 808 coupling blocks; other tested controls/audio/locks/LFO/reload/mixed/909 paths pass | #20 bright-Tone silence baseline reproduces one PCM16 count through all sixty 100 ms checks; dark and 909 baselines are zero |
| DN2 OS 1.12 | Boots and renders both models; earlier controls, mixed tracks, locks/LFO, reload and live Decay stages complete. Dark-Tone nonlinear continuation predicts 544 samples with 3.296e-8 FS capacitor error | The following bright-Tone note75 has no matching active lane after 150 DSP frames. The run fails there; later checks are unexecuted, not passing |

The DN2 missing-note observation is not a numeric mismatch and is not yet
proved to share #80's late CC loss. The independent
[upstream MIDI trace](dn2-late-model.md) now identifies nested receive callbacks
and reordered CC bytes caused by missing Digikit interrupt-mask semantics.
An upstream fix and native requalification remain; a shared cause for the
missing note is still unproved.
Do not conceal the new missing-note result with retries or idle delays.

Built firmware SHA256 values:

- DT: `b2c3ab3f908597e5e42232c7b27a7afa2bf3cb008ca59930aa12dded0db3881f`.
- DN: `e641724c50928d751b2739bf35bd4dabb529a6c724ad827e75e751ebe3b68d49`.
- DN2: `42558bbf749b98635ceec1bcf8a388607978b0269d03c5dfa08e6409e5821092`.

Reports and capture copies are preserved under
`out/reference/808-leakage/native/{dt,dn,dn2}/`. Each copy's capture-scope file
identifies the WAVs referenced by its report; other retained files are partial
or historical and do not qualify unexecuted checks. No waveform tolerance or
exact-zero baseline was widened. Full native acceptance remains open.
