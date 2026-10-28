# 909 Attack: current integration prerequisite

The next functional #25 deliverable is the separate pulse/filtered-noise Attack
path. Its continuous shared source needs a supported DN2 audio clock; the public
request is [simonjohansson/elekloader#108](https://github.com/simonjohansson/elekloader/issues/108).
See the [capability proposal](dn2-audio-clock-proposal.md). Current upstream HEAD
and the validated pin are still `b893c931`; no existing newer hook was found.
DT/DN have suitable pre-render events. No slot-order, callback-count, per-note
reseed, UI-clock or unsupported master-payload workaround is adopted on DN2.

The accepted 909 renderer remains the `65aeaf7` body/Tune/Decay/trigger model;
ATTACK is still inactive. No new production DSP, public API, firmware or full-device
run follows from the diagnostics below. The supported 808 baseline #9 remains
complete and unchanged.

## Bounded checks completed on 28 October

A real mismatch existed between the two old Attack prototype network models:
the pulse component grounded the left of R45, while the noise component used
finite C13/C15 impedance. A pulse at the mix node must also drive that leg.
A new joint three-capacitor operator includes this backreaction and passes five
independent KCL/phasor/superposition tests.

Its hybrid diagnostic reuses the original actual body/Attack stages plus a
host-only correction. All 45 declared seed/take pairs improve slightly, but mean
500-ms error changes only .06829150173→.06829147245 FS and remains worse than
the body-only .06823939377. The corrected joint model has no actual CPU port;
this is not a production or reference-fidelity pass. It is retained for a later
complete branch, not landed because of a tiny average improvement.

A separate source-consistent conditional Q12 loading/DC model was also tested
as a proposed replacement at the existing renderer units. Known-truth KCL checks
pass, but its fixed limiting operating assumption is not an identified transistor.
Against five predeclared ATTACK0 settings / fifteen takes, fixed timing and the
existing reference ×4 correction, mean 500-ms error worsens
.06783476→.06838236 FS. Four of five settings worsen there; all five worsen
in the first 6/25 ms. No gain, phase, offset, master-stage or parameter sweep
rescues the result. It is rejected without a CPU port.

Independent audits reproduce 36 joint-model RMS values within 2.78e-17 FS and
108 selected Q12 RMS values exactly, with original WAV/RPP/readback hashes.
Different target selections explain the different baseline means above; the
legacy combined diagnostic and ATTACK0 screen are separate experiments.

## Source and measurement limits

IC11a's inverting voice output is not automatically the hardware MAIN boundary.
The service notes show an additional inverting IC52 master stage and input/output
coupling; C500 at the individual BD output is a shunt capacitor. The exact
reference master-gain mapping, one output-series marking and complete mix-bus
loading remain unresolved. The conditional MAIN helper has six known-truth tests,
but no MASTER emulation, guessed gain/pole/sign or correction of reference audio
is added. MAIN recordings can still test proposed renderer output pragmatically;
they are not isolated measurements of IC11a.

Source/prototype evidence stays ignored under `out/909-attack-next/`,
`out/909-vca-dc-current/`, `out/909-main-route-current/` and
`out/909-next-review/`. Earlier failed pulse/noise/taper candidates remain intact.
No held-out audio or HTML is used. Source correctness, host diagnostics, actual
CPU tests and installed-emulator evidence remain distinct.
