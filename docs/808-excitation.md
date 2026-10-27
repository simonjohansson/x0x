# Finite 808 excitation: nominal 1 ms rectangle

[#9](https://github.com/simonjohansson/x0x/issues/9) replaces the prototype's
instantaneous `y=0.25` reset with a 48-sample rectangular drive. Roland S01 p.4
and Werner/Abel/Smith S03 §3 describe a nominal 1 ms trigger; at 48 kHz this spans
one full 32-sample callback and sixteen samples of the next callback.

Only the **duration and finite rectangular shape** are taken from the trigger
baseline. This is not the complete pulse-shaper/resonator circuit. R162/R163/C40,
the diode edge response, source impedance, physical forcing/gain, accent and
pitch-switch/feedback paths remain open in #9/#79. The rotation now uses the [47.65 Hz settled-body calibration](808-pitch.md);
Decay mapping remains provisional. The [executable Plaits reference](reference-renders.md)
provides a finite-excitation example, rather than the stock circuit authority.

## Model and fixed scale

On START, clear x/y and set the private pulse counter to 48. Before each rotation,
add `F = 0.25/48` to y while the counter is positive, then decrement it:

```
u[n] = F for 0 <= n < 48, otherwise 0
x_next = c*x + s*(y + u[n])
y_next = c*(y + u[n]) - s*x
output = x_next
```

`c` and `s` are the existing live-Decay damped-rotation coefficients. The fixed
sum of drive contributions is 0.25, preserving the prototype's internal drive
scale without normalizing rendered hits or fitting gain. This is an audition
calibration, not volts or the original bridged-T input transfer. Decay still
changes the resulting amplitude. By the triangle inequality and retention below
one, raw body magnitude remains bounded by the sum of contributions (quarter
scale); Tone/C47 retain their existing half-scale transient bound.

The independent oracle sums analytical impulse responses, not the DSP rotation:

`out[n] = F * sum(exp(L[n+1]-L[k]) * sin(w*(n+1-k)), k=0..min(n,47))`,

where `L[j]` is accumulated log retention before sample j and `w=2*pi*47.65/48000`.
The implementation factors this finite sum into cosine/sine sums. A direct
convolution test checks onset and callback/pulse boundaries independently.
The older single damped-sine formula is the historical instantaneous-drive model;
its first-peak lower bound is no longer applicable. Numeric waveform tolerance
remains 1e-5 FS, without time alignment, gain fitting or normalization.

Live Decay edits retain body and pulse state. Every START still clears the
prototype body, Tone and coupling histories and restarts the full pulse. Source
circuit residual-state retrigger behavior remains deliberately unqualified;
physical/logical voice reuse must be resolved before blindly retaining history.
MODEL continues to latch at START and clear only the selected voice.

## Private implementations and checks

ColdFire uses three words per voice: Q31 x/y and an integer remaining count.
DT/DN share that kernel, and their C dispatchers clear all three words on model
change, reassignment or leaving x0x. The four-argument calling convention stays
the same. Direct tests retain state/output/stack and full EMAC/context guards.

SHARC retains the existing metadata, x/y, Tone and coupling banks and appends
sixteen private counters at data offset 448. Total private RAM is 512 bytes; IDs,
saved values, SDK/public boundaries and native track level are unchanged. The
owned-write fixture includes only the current slot's counter. The pinned
assembler's known negative-immediate shift defect is avoided with a normal
register-count shift, retaining the existing decode guard.

Actual CPU tests require remaining count 16 after the first block and 0 after
the second. Zero-state silence, fractional/end-point Decay, live controls,
interleaved voices, retriggers, MODEL changes and ownership/context guards stay
active. All 118 host tests and independent C/UI suites pass. C fakes explicitly
verify that the new counter is cleared with the owned voice.

The composed body/Tone/C47 comparison passes all five existing cases under the
unchanged 1e-5 FS bound. Maximum model errors are 5.634e-7 FS (ColdFire) and
6.087e-7 FS (SHARC); maximum CPU difference is 8.462e-7 FS. The actual SHARC suite
passes 8820 calls, with 1170 code bytes and 512 private data bytes. 909 output remains
unchanged and passes its independent/cross-CPU comparisons in the shared build.
Instruction counts remain informational; watchdogs protect against hangs.

Use `mise run test:808:body` in order when refreshing composed captures: body,
Tone and coupling files from an older model are not current proof. Run
`mise run test` for independent host/C checks and `mise run test:{dt,dn,dn2}`
for installed-mod evidence. Component proof is not native or VST qualification.

## Native integration status

| Device | Current native evidence | Verdict |
| --- | --- | --- |
| DT 1.54 | 28685 actual pulse/coupling blocks across 39728 callbacks; counter after blocks is 16 then 0; first native PCM peak 4574/32768 | Functional checks pass; only known #78 parameter/page resets fail |
| DN 1.44 | 92401 pulse/coupling blocks across 100788 callbacks; counter values [0,16]; first 808 capture peak 6670/32768 | Current complete scenario passes, including all three exact-zero capture baselines |
| DN2 1.12 | Private pulse bank is consumed after the settled note; native 808 PCM peak 0.021596 FS; precise 32+16 timing remains actual-ASM component proof | Tested scenario passes 31879 DSP frames, with no halt/missing blocks |

All three retain native Decay/Tone, 909 endpoints, p-lock/LFO, save/reload,
MODEL latching, simultaneous models and unrelated stock-output checks. DN2's
stock-processed buffers/PCM remain distinct from raw callback samples and owned
state. Independent C and DSP test layers remain separately runnable.

DN's current exact-zero baselines pass after the excitation changes the input
waveform. This does not identify or establish a general fix for the historical
one-count failure. Keep #20 open and retain its failed two-/six-second reports;
no threshold, gain fitting, baseline subtraction or longer workaround was added
for this pulse increment. #80's late DN2 delivery path was not re-probed.

Firmware SHA256:

- DT: `870a8fac11859d5aea21110e491400e62d682e98752af6d0aeee564fe2fb5acf`.
- DN: `36f92fa0aff0bb52b4f7297c995fb0f2d66a126ae4804e1eb3f277ba3a616c23`.
- DN2: `a58b304c13f55e8b168786061cc2cb8e8432255d4e43f386822b56772433783f`.

Current reports are `out/{dt,dn}/silent/native-report.json` and
`out/dn2/silent/native-boot-report.json`. Unnormalized first-hit PCM captures are
`out/dt/silent/native-808.wav`, `out/dn/silent/808-native.wav` and
`out/dn2/silent/native-808.wav`; Decay/Tone endpoints remain alongside them.

Subsample edges, diode discretization/oversampling and alias qualification remain
circuit work. VST #2 and physical-device validation remain outside this emulator-only phase.
The pre-existing DN baseline gate #20 and late DN2 delivery gate #80 remain open;
this pulse change is not a fix or qualification of either historical failure.
