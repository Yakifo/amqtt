import base64
import binascii
import hashlib
import hmac

from pwdlib.hashers import HasherProtocol


def _ensure_str(value: str | bytes) -> str:
    return value.decode("utf-8") if isinstance(value, bytes) else value


def _decode_passlib_b64(value: str) -> bytes:
    return base64.b64decode(value + ("=" * (-len(value) % 4)))


class LegacyPasslibScryptHasher(HasherProtocol):
    @classmethod
    def identify(cls, hash: str | bytes) -> bool:  # ruff: ignore[builtin-argument-shadowing]# pylint: disable=redefined-builtin
        del cls
        try:
            password_hash = _ensure_str(hash)
        except UnicodeDecodeError:
            return False
        return password_hash.startswith("$scrypt$")

    @property
    def name(self) -> str:
        # Matches the passlib identifier prefix in the DB string
        return "scrypt"

    # Perfect signature match keeping parameters keyword-only
    def hash(self, password: str | bytes, *, salt: bytes | None = None) -> str:
        msg = "Use Argon2 or Bcrypt to hash new entries."
        raise NotImplementedError(msg)

    def verify(self, password: str | bytes, hash: str | bytes) -> bool:  # ruff: ignore[builtin-argument-shadowing] # pylint: disable=redefined-builtin
        try:
            # Passlib format: $scrypt$ln=14,r=8,p=1$salt_b64$hash_b64
            parts = _ensure_str(hash).split("$")
            if len(parts) < 5 or parts[1] != "scrypt":
                return False

            # 1. Parse configuration parameters from the config string block
            config_params: dict[str, int] = {}
            for param in parts[2].split(","):
                key, val = param.split("=")
                config_params[key] = int(val)

            # Passlib uses 'ln' (log2 of N). Calculate actual cost N:
            n_cost = 2 ** config_params["ln"]
            r_block = config_params["r"]
            p_parallel = config_params["p"]

            # 2. Extract salt and hash, accounting for dropped Base64 padding
            salt = _decode_passlib_b64(parts[3])
            expected_checksum = _decode_passlib_b64(parts[4])

            # 3. Ensure uniform bytes formatting for the incoming password parameter
            password_bytes = password if isinstance(password, bytes) else password.encode("utf-8")

            # 4. Generate identical verification chunk using standard library hashlib
            computed_checksum = hashlib.scrypt(
                password_bytes,
                salt=salt,
                n=n_cost,
                r=r_block,
                p=p_parallel,
                maxmem=1024 * 1024 * 64,  # 64MB memory ceiling safety threshold
                dklen=32,
            )

            # 5. Execute timing-safe string comparison
            return hmac.compare_digest(computed_checksum, expected_checksum)
        except (KeyError, ValueError, UnicodeDecodeError, binascii.Error):
            return False

    def check_needs_rehash(self, hash: str | bytes) -> bool:  # ruff: ignore[builtin-argument-shadowing]# pylint: disable=redefined-builtin
        return True


class LegacyPasslibPBKDF2Hasher(HasherProtocol):
    @classmethod
    def identify(cls, hash: str | bytes) -> bool:  # ruff: ignore[builtin-argument-shadowing]# pylint: disable=redefined-builtin
        del cls
        try:
            password_hash = _ensure_str(hash)
        except UnicodeDecodeError:
            return False
        return password_hash.startswith("$pbkdf2-sha256$")

    @property
    def name(self) -> str:
        return "pbkdf2-sha256"

    # Updated to perfectly match pwdlib's protocol signature
    def hash(self, password: str | bytes, *, salt: bytes | None = None) -> str:
        # Prevent generation of new legacy hashes
        msg = "Use Argon2/Bcrypt for new hashes."
        raise NotImplementedError(msg)

    def verify(self, password: str | bytes, hash: str | bytes) -> bool:  # ruff: ignore[builtin-argument-shadowing]# pylint: disable=redefined-builtin
        try:
            parts = _ensure_str(hash).split("$")
            if len(parts) < 5 or parts[1] != "pbkdf2-sha256":
                return False

            rounds = int(parts[2])
            # Account for passlib's custom B64 format padding drops
            salt = _decode_passlib_b64(parts[3])
            expected_checksum = _decode_passlib_b64(parts[4])

            # Ensure the password input is bytes for hashlib compatibility
            password_bytes = password if isinstance(password, bytes) else password.encode("utf-8")

            computed_checksum = hashlib.pbkdf2_hmac("sha256", password_bytes, salt, rounds, dklen=32)

            return hmac.compare_digest(computed_checksum, expected_checksum)
        except (ValueError, UnicodeDecodeError, binascii.Error):
            return False

    def check_needs_rehash(self, hash: str | bytes) -> bool:  # ruff: ignore[builtin-argument-shadowing]# pylint: disable=redefined-builtin
        return True
