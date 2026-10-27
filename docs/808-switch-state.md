# 808 capacitor state at the initial frequency switch

This #9/#79 increment corrects the state conversion at the end of the initial
6 ms window on both CPUs. The preceding [bridge derivation](808-retrigger.md)
showed that retaining modal x/y across a resistance change does not retain
C41/C42 charge. The body still uses calibrated pitch/Decay and a provisional
1 ms drive. Companion excitation, pulse shaping, full feedback and leakage
remain missing; this is not the complete attack.

## Derivation and implementation

After the drive ends, let x be the output, y its modal quadrature, sigma the
calibrated damping, and omega the damped angular frequency. With
`a=1/(R167*C41)`, the corresponding capacitor voltages are:

```
q1 = -a*(sigma*x + omega*y)/(sigma*sigma + omega*omega)
q2 = -x-q1
```

Here capacitor voltages share x's unchanged internal scale; no claim of a
calibrated volts-to-digital-full-scale mapping is made.

For constant effective damping these obey `dq1/dt=a*x`, consistent with the
ideal bridge. At the resistance switch retain x and both capacitor voltages.
Writing h/l for the high/low angular frequencies gives:

```
r = h/l
p = (sigma*sigma + l*l)/(sigma*sigma + h*h)
y_after = (p*r)*y_before + ((p-1)*sigma/l)*x
```

This changes the meaning of y without adding an input or changing output x at
the event. The transform occurs once, after sample 288 and before sample 289.
The existing 32-sample callback boundaries, private state size, START behavior,
control delivery, saved layouts and MODEL policy remain unchanged. The current
internal audio scale also stays unchanged; no raw circuit voltage is injected.

For the independent oracle, convolve the finite drive analytically during the
high-frequency interval, convert its terminal state with the exact formula,
and solve the subsequent free decay analytically. This is independent of the
ASM recurrence. Live Decay continues to update loss without restarting a note.
The constant-damping circuit interpretation is local to the switch, not proof
of the complete frequency-dependent feedback shelf during arbitrary modulation.

Both backends evaluate a short series, with `n=sigma/h` and `z=n*n`:

```
alpha = 1/r + (r-1/r)*(z-z*z)
beta = -(r-1/r)*n*(1-z+z*z)
y_after = alpha*y_before + beta*x
```

They obtain sigma from the current high-frequency cosine coefficient using a
second-order approximation to `-log(rho)`. This avoids a division/log routine
in either DSP. Across all 32,513 native Decay positions, an analytical Q31
arithmetic check bounds coefficient-approximation error on a quarter-scale
state by 2.382e-8 FS. It is separate from actual-CPU execution and does not
change the existing 1e-5 FS waveform limit. The transform's absolute coefficient
sum stays below one, so it cannot enlarge the existing state bound.

## Evidence and remaining work

Host tests check capacitor-voltage conservation, direct impulse convolution
across the switch, settled pitch/Decay, fractional/live controls and headroom.
131 host tests and independent C/UI suites pass. The shared SHARC suite passes
9,012 calls, with 1,410 code bytes and unchanged 512 private bytes. ColdFire
keeps three private words. Full two-second matching CPU renders remain below
the unchanged 1e-5 FS limit: maximum errors are 1.396e-6 FS (ColdFire),
6.549e-7 FS (SHARC), and 1.289e-6 FS between CPUs. Fractional/live controls,
retrigger/interleaving, guard/context and existing 909 checks remain active.

All three native-emulator scenarios ran with the installed correction:

- DT completes 39,431 callbacks and 28,102 observed counter/coupling blocks.
  Only known #78 parameter/page resets fail.
- DN completes 100,786 callbacks and 92,412 observed counter/coupling blocks.
  Its overall run fails solely on the reproduced #20 pre-bright-Tone baseline:
  one PCM16 count remains through all sixty 100 ms checks. Dark-Tone and 909
  baselines are zero. Other tested control/audio/lock/LFO/reload/mixed-model
  checks pass. Earlier passing baselines did not resolve this failure.
- DN2's tested scenario passes 31,878 DSP frames, with no reported halt or
  missing blocks. Its native counter bank is consumed after the settled note;
  exact drive/switch/state-conversion timing remains separate component proof.
  #80's late MODEL path remains separately unqualified.

These are native functional checks, not original-hardware or full-fidelity
qualification. Local evidence remains in the existing device reports under
`out/dt/silent/`, `out/dn/silent/` and `out/dn2/silent/`.

## Five-setting training comparison

Both CPUs freshly render 96,000 samples per setting. The same fifteen fresh
training takes pass hash, repeat and control/protocol checks. The comparison
retains MIDI at zero, the documented common reference multiplier x4 and raw
mod scale; no alignment, normalization or fitted gain.

| Setting | Whole-clip raw RMS FS, prior switch / state correction |
| --- | --- |
| Default | 0.065637 / 0.065629 |
| Dark, short | 0.024086 / 0.023023 |
| Bright, short | 0.025161 / 0.024122 |
| Dark, long | 0.067908 / 0.070383 |
| Bright, long | 0.069125 / 0.071617 |

The first 6 ms are bit-identical in ColdFire. First 25 ms residuals improve at
all five settings. First 150 ms and whole-clip residuals improve for default
and short settings, but worsen for both long settings. Default whole-clip error
is essentially unchanged. The earlier default/short regressions against the
pre-switch Decay baseline remain unresolved; this is not a fidelity pass or the
missing companion pulse. Preserve both long-setting regressions. Detailed
windows, measurements, executable/source hashes and raw floats are in
`out/reference/808-switch-state/measurements.json`.

Native firmware SHA256:

- DT: `af035be82c8dd7f2417dbdd9d16c2d952a4c5ae41ea1ff2ea2fd35f4615ecf80`.
- DN: `da75200a80c0d6a18fc6f90c88e86ce68dbfafe1d1500273ee4b2fb81e140146`.
- DN2: `dc6c23ece9552fa6a02a772e3bf0d34fbaa2eb281ca0ef92fd4aa5ef4e7ed031`.

The HTML report and held-out audio remain untouched. #78 reset behavior,
historical #20 silence residue and #80 late MODEL delivery keep their separate
acceptance status. Next integrate the companion input with consistent forcing
and a documented fixed voltage-to-audio scale, retaining explicit approximations
for the remaining circuit stages.
