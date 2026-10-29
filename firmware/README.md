# Local firmware inputs

Use the pinned stock images supported by the current engine builds:

| Device | Pinned OS | Official support page | Local stock image |
| --- | --- | --- | --- |
| Digitakt mk1 | 1.54 | [Digitakt downloads](https://www.elektron.se/support-downloads/digitakt) | `Digitakt_OS1.54.syx` |
| Digitone mk1 | 1.44 | [Digitone downloads](https://www.elektron.se/support-downloads/digitone) | `Digitone_and_Digitone_Keys_OS1.44.syx` |
| Digitone II | 1.12 | [Digitone II downloads](https://www.elektron.se/support-downloads/digitone-ii) | `Digitone_II_OS1.12.syx` |

[manifest.json](manifest.json) records each official download URL, verification
time, archive/image filename, byte count and SHA-256. The ZIPs and extracted
images are local, ignored inputs; do not commit or redistribute them. The saved
support-page HTML is also ignored. On a fresh clone, download the listed ZIP
from Elektron, extract its `.syx` image and check both hashes against the manifest.

All three downloaded images match the pinned Elekloader release profiles by
SHA-256. Their decompressed main-image hashes/lengths also match, and the SDK's
stock verifier passes transport/container checks, protected ranges and in-place
decompression. The Digitone II HMAC verifies. The manifest records the exact SDK
revision used. These checks identify valid stock inputs; they do not qualify a
custom engine or device workload.

Recheck the official page before changing the baseline. A newer official OS
requires a matching reviewed SDK/profile and integration evidence. Do not fall
back to an older supported profile when the latest OS needs a port. Historical
profiles present in a dependency do not expand x0x's supported OS set.

Stock-free model and bounded instruction checks do not require firmware images.
The normal `mise run firmware:dt`, `firmware:dn` and `firmware:dn2` tasks build
the combined x0x mod, including both frozen reference-driven 808 and 909 ASM engines.
Each output directory records its stock verification, source paths, model hash
and firmware SHA-256. Native-emulator and physical-device results are separate
from packaging evidence; see [current qualification](https://github.com/simonjohansson/x0x/issues/94)
and the [development guide](../docs/development.md).
