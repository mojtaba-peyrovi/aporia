from __future__ import annotations

import hashlib


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_upload_bytes(uploaded_file) -> tuple[str, bytes]:
    if uploaded_file is None:
        raise ValueError("No file uploaded")
    name = getattr(uploaded_file, "name", None) or "upload"
    data = uploaded_file.getvalue()
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("upload.getvalue() did not return bytes")
    return str(name), bytes(data)


def upload_hash(uploaded_file) -> str:
    _, data = read_upload_bytes(uploaded_file)
    return sha256_hex(data)

