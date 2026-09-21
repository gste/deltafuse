"""Ed25519 signatures (RFC 8032), pure Python.

The reference implementation from RFC 8032 section 6, adapted to Python 3 and
checked against the section 7.1 test vectors in the unit tests. The Core's
dependencies are limited to jsonschema and pyyaml, so no crypto library is
available.

Used to sign and verify Human Gate receipts - a handful per Change. It is not
constant-time: fine for a local tool signing a few receipts, not for a service
that signs on demand for untrusted callers.
"""

from __future__ import annotations

import hashlib

_P = 2**255 - 19
_Q = 2**252 + 27742317777372353535851937790883648493


def _inv(x: int) -> int:
    return pow(x, _P - 2, _P)


_D = -121665 * _inv(121666) % _P
_SQRT_M1 = pow(2, (_P - 1) // 4, _P)

Point = tuple[int, int, int, int]


def _sha512_modq(data: bytes) -> int:
    return int.from_bytes(hashlib.sha512(data).digest(), "little") % _Q


def _add(p: Point, q: Point) -> Point:
    a = (p[1] - p[0]) * (q[1] - q[0]) % _P
    b = (p[1] + p[0]) * (q[1] + q[0]) % _P
    c = 2 * p[3] * q[3] * _D % _P
    d = 2 * p[2] * q[2] % _P
    e, f, g, h = b - a, d - c, d + c, b + a
    return (e * f, g * h, f * g, e * h)


def _mul(s: int, p: Point) -> Point:
    q: Point = (0, 1, 1, 0)  # neutral element
    while s > 0:
        if s & 1:
            q = _add(q, p)
        p = _add(p, p)
        s >>= 1
    return q


def _equal(p: Point, q: Point) -> bool:
    if (p[0] * q[2] - q[0] * p[2]) % _P != 0:
        return False
    return (p[1] * q[2] - q[1] * p[2]) % _P == 0


def _recover_x(y: int, sign: int) -> int | None:
    if y >= _P:
        return None
    x2 = (y * y - 1) * _inv(_D * y * y + 1)
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (_P + 3) // 8, _P)
    if (x * x - x2) % _P != 0:
        x = x * _SQRT_M1 % _P
    if (x * x - x2) % _P != 0:
        return None
    if (x & 1) != sign:
        x = _P - x
    return x


_GY = 4 * _inv(5) % _P
_GX = _recover_x(_GY, 0)
assert _GX is not None
_G: Point = (_GX, _GY, 1, _GX * _GY % _P)


def _compress(p: Point) -> bytes:
    zinv = _inv(p[2])
    x = p[0] * zinv % _P
    y = p[1] * zinv % _P
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")


def _decompress(data: bytes) -> Point | None:
    if len(data) != 32:
        return None
    y = int.from_bytes(data, "little")
    sign = y >> 255
    y &= (1 << 255) - 1
    x = _recover_x(y, sign)
    if x is None:
        return None
    return (x, y, 1, x * y % _P)


def _expand(secret: bytes) -> tuple[int, bytes]:
    if len(secret) != 32:
        raise ValueError("an Ed25519 private key is 32 bytes")
    h = hashlib.sha512(secret).digest()
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a, h[32:]


def public_key(secret: bytes) -> bytes:
    """The 32-byte public key of a 32-byte private key (seed)."""
    a, _ = _expand(secret)
    return _compress(_mul(a, _G))


def sign(secret: bytes, message: bytes) -> bytes:
    """A 64-byte signature of `message`."""
    a, prefix = _expand(secret)
    pub = _compress(_mul(a, _G))
    r = _sha512_modq(prefix + message)
    r_point = _compress(_mul(r, _G))
    h = _sha512_modq(r_point + pub + message)
    s = (r + h * a) % _Q
    return r_point + int.to_bytes(s, 32, "little")


def verify(public: bytes, message: bytes, signature: bytes) -> bool:
    """True only for a valid signature of `message` under `public`."""
    if len(public) != 32 or len(signature) != 64:
        return False
    a_point = _decompress(public)
    if a_point is None:
        return False
    r_bytes = signature[:32]
    r_point = _decompress(r_bytes)
    if r_point is None:
        return False
    s = int.from_bytes(signature[32:], "little")
    if s >= _Q:
        return False
    h = _sha512_modq(r_bytes + public + message)
    return _equal(_mul(s, _G), _add(r_point, _mul(h, a_point)))
