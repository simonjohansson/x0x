# DN2 shared DSP clock: upstream capability proposal

**Feature request filed with human permission: [Elekloader #108](https://github.com/simonjohansson/elekloader/issues/108), 28 October 2026. No public API, saved layout or runtime change adopted.**
This is a prerequisite for the continuous shared-noise part of #25, not a
firmware-boot bug. The supported 808 baseline #9 stays complete.

## Concrete gap

Pinned Elekloader `b893c9317936633d7a32829b618c2867ee99277c` is also current
upstream HEAD when checked on 28 October. Its public
[`voice.h`](../vendor/elekloader/elekloader/sdk/include/digitone-mk2/voice.h)
provides output, slot, pitch, START and parameter words. It runs per matching
voice, without an engine-block callback or absolute audio position. The
[linker](../vendor/elekloader/elekloader/link.py) permits the supported voice/filter
pair, not a separate voice/master combination. These limits are not permission
to bypass the guard or invent a mod transport.

A free-running noise source shared by all voices must advance with zero, one
or many consumers and give each consumer the same interval regardless of slot
order. DT has a pre-track render event and DN has an input render event; DN2
needs an upstream-supported equivalent. Neither slot number, START, callback
count nor UI milliseconds establishes the missing audio clock.

## Proposed upstream work

Request an optional once-per-engine/audio-block callback, before voice consumers,
including zero-voice blocks. A timestamp alternative must define equivalent
advancement through idle time. Preserve current opt-out behavior, voice ABI,
IDs, controls and saved sounds. Review exact interface and packaging changes
upstream before implementation; this document selects no field/layout/signature.

Required tests cover initialization, zero/one/many and reordered voices, idle
intervals, restart/wrap, block units and unchanged existing mods. Component
execution and DN2 full-device integration are appropriate here because this
would change the SDK boundary. It does not reinstate full-device tests for
every DSP coefficient change.

A public issue draft, containing only public SDK facts and a generic shared-source
use case, is prepared at `out/upstream-elekloader-audio-clock/issue.md`. It contains
no private mod code, firmware, recordings or private repository links. The human selected `simonjohansson/elekloader`, where issue #108 is now filed.
No PR or SDK implementation is adopted. The request is distinct from the
existing block-load/peek issue #98 and idle-measure issue #107; those do not
provide a supported mod-facing engine clock.

## Work that remains separate

The isolated source clock/owner arithmetic already passes its tests; that is not
an implemented DN2 clock hook. The newly corrected joint C11/C13/C15 model is
source-consistent but remains worse than body-only audio and has no corrected
CPU port. Q12 and MAIN-boundary findings are diagnostics, not permission to fit
gain/phase/DC or adopt an unmeasured master stage. These do not close #25 or
#79/#2 fidelity gates.
