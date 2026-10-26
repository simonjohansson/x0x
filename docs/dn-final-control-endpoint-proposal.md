# DN final-control endpoint policy

**Approved by the user on 26 October 2026:** “Approve the DN-only endpoint policy.”
The implementation is being verified against the acceptance checks below. Scope is the private
Digitone OS 1.44 final-frame adapter at Elekloader PR 200 commit
`2ab5f424c4721e4277d2112a5ae755d9938f50d6`. This adopts no saved layout or ID.

## Measured gap

An isolated digiemu fixture based on x0z `3cd387a` settles voice 0's LEVEL target
and Q16 smoother at raw 32512, disables that voice's separate per-voice controller
contribution, and moves the LFO destination from slot 27 to slot 28. Actual
CC1=127, its producer, controller stage and final stage then give:

| Block | Target | Smoothed | Settled CC1 used | Controller word | Final word |
| --- | --- | --- | --- | --- | --- |
| 0 | 32512 | 32512 | 0 | 32512 | 32512 |
| 1 | 32512 | 32512 | 983 | 32634 | 32634 |

The real `x0z_dn_frame_read(frame, 0, 119, ...)` returns **0** with a valid
current-bank pointer and ready phase 3; it returns normally to `0xdeadbee0`.
The stock parameter record has UI minimum 0 and maximum 32512. The final word
is positive and representable, but the current reader rejects it as above UI
maximum. This blocks final-range qualification; it is not a passing gate.

The ignored source/log are `out/dn/probe_saturation.py` and
`out/dn/saturation-probe.log`. Reconstruct from the pinned harness by settling
target/smoother as above, keeping the LFO on another parameter, and observing
the frame before invoking the production reader. No raw/settled CC value is
substituted. The ordinary low-range regression deliberately avoids this limit.
A separate stock-controller helper probe reaches 32767 at positive saturation
and 0 at negative saturation. The final-frame result above establishes that a
later stage need not clamp the selected control back to its UI maximum.

## Approved DN-only policy

For verified full-range SYN2 records 119..126 with stock bounds 0..32512:

- Accept final scalar words 0..32767. Keep negative words, invalid records/slots,
  unavailable/expired frames and malformed ranges rejected without state updates.
- Preserve the actual observed `x0z_dn_value.raw`, even when it exceeds 32512.
  `minimum` and `maximum` remain **stock UI bounds**, not delivered-word bounds.
- Clamp only the normalized model position to those UI bounds. For example,
  raw 32634 retains raw 32634 and UI bounds 0..32512, with position
  **32512/32512**. UI maximum 32512 must still map exactly to 1; ordinary
  fractional values keep their exact ratios.
- Preserve observed MODEL separately, then pass `min(raw, 32512)` to the
  existing ColdFire selector interface. Its 16384 threshold, START latch,
  per-voice tail policy and existing accepted canonical domain stay unchanged.
  Native MODEL 32513, 32634 and 32767 therefore all select 909 at START.
- Keep the old target-accessor diagnostic strict. Do not infer this acceptance
  for other parameter records, DT, DN2 or the SHARC callback without evidence.

This preserves the shared model's `[0,1]` control contract and raw observability.
Normalizing against 32767 instead would move the UI maximum below position 1.
Allowing positions above 1 would extend the shared instrument contract. Neither
alternative is part of the approved policy.

## Implementation acceptance

1. Host cases cover 0, fractional values, 32512, 32513, 32634 and 32767;
   preserve actual raw/UI metadata and verify clamped positions exactly.
2. Replay the actual final-frame case above through the compiled adapter and
   receiver. No target substitution, denominator rescaling or hidden gain change.
3. Exercise native MODEL above UI maximum through DN canonicalization and the
   existing actual selector ASM; retain threshold/latch/voice-isolation tests.
4. Retain negative/malformed/missing/stale rejection and atomic state/receiver
   checks, and keep the target-only diagnostic's rejection behavior unchanged.

The user's supplied AGENTS.md requires review before API changes. The explicit
approval above authorizes this DN-only raw-reader/receiver rejection behavior
and metadata meaning. Native-source, ownership, selector
integration, full-OS timing and fidelity gates in #75/#40 remain separate.
