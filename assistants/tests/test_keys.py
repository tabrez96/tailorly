import hashlib

from assistants import keys


def test_generate_shape():
    raw, prefix, digest = keys.generate()
    assert raw.startswith("tly_mcp_")
    assert len(prefix) == 8 and prefix == raw[len("tly_mcp_") :][:8]
    assert digest == hashlib.sha256(raw.encode()).hexdigest() and len(digest) == 64


def test_generate_unique():
    a, b = keys.generate(), keys.generate()
    assert a[0] != b[0] and a[2] != b[2]
