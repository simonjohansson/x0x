"""Legacy ASM partition within the pinned 64 KiB DN2 voice owner."""
from . import cpu

CODE_BYTES = 8192


def voice_layout(code_bytes=CODE_BYTES):
    sdk = cpu.require_module("elekloader.sdk.sharc", "elekloader")
    layout = dict(sdk.machine_layout("voice"))
    if type(code_bytes) is not int or code_bytes < 64 or code_bytes % 4:
        raise ValueError("private code region must contain aligned guard bytes")
    extra = code_bytes - layout["code_bytes"]
    if extra >= layout["data_bytes"]:
        raise ValueError("private code region leaves no author data")
    layout["code_bytes"] = code_bytes
    layout["data_address"] += extra
    layout["data_bytes"] -= extra
    return layout


def voice_artifact(code, data, render_offset_bytes, machine_id, stack_bytes, *,
                   code_bytes=CODE_BYTES, voice_bytes=0):
    sdk = cpu.require_module("elekloader.sdk.sharc", "elekloader")
    device = cpu.require_module("elekloader.devices.digitone_mk2", "elekloader")
    sharc = cpu.require_module("elekloader.sharc", "elekloader")
    profile = device.DEVICE.releases["1.12"].sharc
    layout = voice_layout(code_bytes)
    guard = profile["code_guard_bytes"]
    if (not isinstance(code, bytes) or not code or len(code) % 2
            or len(code) + guard > layout["code_bytes"]):
        raise ValueError("x0x SHARC code exceeds its private region or is unaligned")
    if (type(render_offset_bytes) is not int or render_offset_bytes % 2
            or not 0 <= render_offset_bytes < len(code)):
        raise ValueError("x0x SHARC entry must be even and inside supplied code")
    if not isinstance(data, bytes) or len(data) % 4 or len(data) > layout["data_bytes"]:
        raise ValueError("x0x SHARC data exceeds its private region or is unaligned")
    # Reuse the qualified adapter and scalar checks; only author bytes move.
    doc = sdk.voice_artifact(b"\x01\x00" * 2, b"", 0, machine_id, stack_bytes)
    prefix = doc["segments"][1]["offset_bytes"]
    adapter_state = doc["zero"][-1]
    data_offset = prefix + layout["code_bytes"]
    voice_at = data_offset + (len(data) + 7) // 8 * 8
    if (type(voice_bytes) is not int or voice_bytes < 0 or voice_bytes % 4
            or voice_at + 16 * voice_bytes > adapter_state["offset_bytes"]):
        raise ValueError("private voice states exceed author data or are unaligned")
    padded = code + b"\x01\x00" * ((layout["code_bytes"] - len(code)) // 2)
    doc["segments"] = [doc["segments"][0],
                       {"offset_bytes": prefix, "kind": "code", "hex": padded.hex()}]
    if data:
        doc["segments"].append({"offset_bytes": data_offset, "kind": "data", "hex": data.hex()})
    end = data_offset + len(data)
    doc["zero"] = ([{"offset_bytes": end, "size_bytes": adapter_state["offset_bytes"] - end}]
                   if end < adapter_state["offset_bytes"] else []) + [adapter_state]
    doc["entries"] = {"render_offset_bytes": prefix + render_offset_bytes}
    if voice_bytes:
        doc["voice_state"] = dict(offset_bytes=voice_at, voice_bytes=voice_bytes)
    sharc.module_payload(doc, profile)
    return doc
