import base64
import hashlib

import pytest

from amqtt.contrib.auth_db import hasher as hasher_module
from amqtt.contrib.auth_db.hasher import (
    LegacyPasslibPBKDF2Hasher,
    LegacyPasslibScryptHasher,
    _decode_passlib_b64,
    _ensure_str,
)


def _b64_no_padding(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii").rstrip("=")


def _scrypt_hash(
    checksum: bytes,
    *,
    salt: bytes = b"salt",
    config: str = "ln=4,r=2,p=1",
) -> str:
    return f"$scrypt${config}${_b64_no_padding(salt)}${_b64_no_padding(checksum)}"


def _pbkdf2_hash(password: str | bytes, *, rounds: int = 2, salt: bytes = b"salt") -> str:
    password_bytes = password if isinstance(password, bytes) else password.encode("utf-8")
    checksum = hashlib.pbkdf2_hmac("sha256", password_bytes, salt, rounds, dklen=32)
    return f"$pbkdf2-sha256${rounds}${_b64_no_padding(salt)}${_b64_no_padding(checksum)}"


def test_helpers_decode_strings_and_passlib_base64_without_padding() -> None:
    assert _ensure_str(b"value") == "value"
    assert _ensure_str("value") == "value"
    assert _decode_passlib_b64("dmFsdWU") == b"value"


def test_scrypt_identify_handles_strings_bytes_non_matches_and_bad_bytes() -> None:
    assert LegacyPasslibScryptHasher.identify("$scrypt$ln=4,r=1,p=1$c2FsdA$Y2hlY2s") is True
    assert LegacyPasslibScryptHasher.identify(b"$scrypt$ln=4,r=1,p=1$c2FsdA$Y2hlY2s") is True
    assert LegacyPasslibScryptHasher.identify("$pbkdf2-sha256$1$c2FsdA$Y2hlY2s") is False
    assert LegacyPasslibScryptHasher.identify(b"\xff") is False


def test_scrypt_metadata_and_hash_generation_disabled() -> None:
    hasher = LegacyPasslibScryptHasher()

    assert hasher.name == "scrypt"
    assert hasher.check_needs_rehash("$scrypt$ln=4,r=1,p=1$c2FsdA$Y2hlY2s") is True
    with pytest.raises(NotImplementedError, match="Use Argon2 or Bcrypt"):
        hasher.hash("password")


@pytest.mark.parametrize(
    ("password", "hash_as_bytes"),
    [
        ("password", False),
        (b"password", True),
    ],
)
def test_scrypt_verify_accepts_matching_checksum(
    monkeypatch: pytest.MonkeyPatch,
    password: str | bytes,
    hash_as_bytes: bool,
) -> None:
    expected_checksum = b"x" * 32
    calls: list[dict[str, object]] = []

    def fake_scrypt(
        password_bytes: bytes,
        *,
        salt: bytes,
        n: int,
        r: int,
        p: int,
        maxmem: int,
        dklen: int,
    ) -> bytes:
        calls.append(
            {
                "password": password_bytes,
                "salt": salt,
                "n": n,
                "r": r,
                "p": p,
                "maxmem": maxmem,
                "dklen": dklen,
            },
        )
        return expected_checksum

    monkeypatch.setattr(hasher_module.hashlib, "scrypt", fake_scrypt)
    password_hash = _scrypt_hash(expected_checksum)
    password_hash_input = password_hash.encode("utf-8") if hash_as_bytes else password_hash

    assert LegacyPasslibScryptHasher().verify(password, password_hash_input) is True
    assert calls == [
        {
            "password": b"password",
            "salt": b"salt",
            "n": 16,
            "r": 2,
            "p": 1,
            "maxmem": 1024 * 1024 * 64,
            "dklen": 32,
        },
    ]


def test_scrypt_verify_rejects_mismatched_checksum(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hasher_module.hashlib, "scrypt", lambda *args, **kwargs: b"y" * 32)

    assert LegacyPasslibScryptHasher().verify("password", _scrypt_hash(b"x" * 32)) is False


@pytest.mark.parametrize(
    "password_hash",
    [
        "not-a-scrypt-hash",
        "$pbkdf2-sha256$1$c2FsdA$Y2hlY2s",
        "$scrypt$ln=4,r=1,p=1$c2FsdA",
        "$scrypt$ln=bad,r=1,p=1$c2FsdA$Y2hlY2s",
        "$scrypt$ln=4,r=1$c2FsdA$Y2hlY2s",
        "$scrypt$ln=4,r=1,p=1$A$Y2hlY2s",
    ],
)
def test_scrypt_verify_rejects_invalid_formats(password_hash: str) -> None:
    assert LegacyPasslibScryptHasher().verify("password", password_hash) is False


def test_scrypt_verify_rejects_hash_bytes_that_are_not_utf8() -> None:
    assert LegacyPasslibScryptHasher().verify("password", b"\xff") is False


def test_pbkdf2_identify_handles_strings_bytes_non_matches_and_bad_bytes() -> None:
    assert LegacyPasslibPBKDF2Hasher.identify("$pbkdf2-sha256$1$c2FsdA$Y2hlY2s") is True
    assert LegacyPasslibPBKDF2Hasher.identify(b"$pbkdf2-sha256$1$c2FsdA$Y2hlY2s") is True
    assert LegacyPasslibPBKDF2Hasher.identify("$scrypt$ln=4,r=1,p=1$c2FsdA$Y2hlY2s") is False
    assert LegacyPasslibPBKDF2Hasher.identify(b"\xff") is False


def test_pbkdf2_metadata_and_hash_generation_disabled() -> None:
    hasher = LegacyPasslibPBKDF2Hasher()

    assert hasher.name == "pbkdf2-sha256"
    assert hasher.check_needs_rehash("$pbkdf2-sha256$1$c2FsdA$Y2hlY2s") is True
    with pytest.raises(NotImplementedError, match="Use Argon2/Bcrypt"):
        hasher.hash("password")


@pytest.mark.parametrize(
    ("password", "hash_as_bytes"),
    [
        ("password", False),
        (b"password", True),
    ],
)
def test_pbkdf2_verify_accepts_matching_checksum(password: str | bytes, hash_as_bytes: bool) -> None:
    password_hash = _pbkdf2_hash(password)
    password_hash_input = password_hash.encode("utf-8") if hash_as_bytes else password_hash

    assert LegacyPasslibPBKDF2Hasher().verify(password, password_hash_input) is True


def test_pbkdf2_verify_rejects_mismatched_checksum() -> None:
    password_hash = _pbkdf2_hash("password")

    assert LegacyPasslibPBKDF2Hasher().verify("wrong-password", password_hash) is False


@pytest.mark.parametrize(
    "password_hash",
    [
        "not-a-pbkdf2-hash",
        "$scrypt$ln=4,r=1,p=1$c2FsdA$Y2hlY2s",
        "$pbkdf2-sha256$1$c2FsdA",
        "$pbkdf2-sha256$not-rounds$c2FsdA$Y2hlY2s",
        "$pbkdf2-sha256$1$A$Y2hlY2s",
    ],
)
def test_pbkdf2_verify_rejects_invalid_formats(password_hash: str) -> None:
    assert LegacyPasslibPBKDF2Hasher().verify("password", password_hash) is False


def test_pbkdf2_verify_rejects_hash_bytes_that_are_not_utf8() -> None:
    assert LegacyPasslibPBKDF2Hasher().verify("password", b"\xff") is False
