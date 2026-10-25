"""Read the text of a Messages row.

Recent macOS versions often leave `message.text` empty and keep the words inside `attributedBody`, an Apple
"typedstream" blob. We only need the plain string, which sits after the `NSString` marker as
`\\x01+` followed by a length (one byte, or 0x81 + 2 bytes, or 0x82 + 4 bytes) and UTF-8 text.
"""
from __future__ import annotations

from typing import Optional

_OBJECT_REPLACEMENT = "￼"  # stands in for an attachment


def _from_typedstream(blob: bytes) -> Optional[str]:
    start = blob.find(b"NSString")
    if start < 0:
        return None
    tag = blob.find(b"\x01+", start, start + 24)
    if tag < 0:
        return None
    pos = tag + 2
    if pos >= len(blob):
        return None
    first = blob[pos]
    if first == 0x81:
        length = int.from_bytes(blob[pos + 1 : pos + 3], "little")
        pos += 3
    elif first == 0x82:
        length = int.from_bytes(blob[pos + 1 : pos + 5], "little")
        pos += 5
    else:
        length = first
        pos += 1
    raw = blob[pos : pos + length]
    if len(raw) != length:
        return None
    return raw.decode("utf-8", errors="replace")


def message_text(text: Optional[str], attributed: Optional[bytes]) -> Optional[str]:
    """The words of a message, or None for attachments, empty rows and anything we cannot read."""
    value = text
    if not value and attributed:
        value = _from_typedstream(bytes(attributed))
    if not value:
        return None
    value = value.replace(_OBJECT_REPLACEMENT, "").strip()
    return value or None


def encode_for_tests(text: str) -> bytes:
    """Build a blob in the same shape macOS writes, so tests can cover the decoder without real chats."""
    body = text.encode("utf-8")
    if len(body) < 0x80:
        length = bytes([len(body)])
    elif len(body) < 0x10000:
        length = b"\x81" + len(body).to_bytes(2, "little")
    else:
        length = b"\x82" + len(body).to_bytes(4, "little")
    return b"\x04\x0bstreamtyped\x81\xe8\x03\x84\x01@\x84\x84\x84\x12NSAttributedString\x00\x84\x84\x08NSObject\x00\x85\x92\x84\x84\x84\x08NSString\x01\x94\x84\x01+" + length + body + b"\x86\x84\x02iI\x01"
