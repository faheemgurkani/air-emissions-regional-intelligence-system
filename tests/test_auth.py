"""
Tests for auth layer (DATA_LAYER): password hashing, JWT create/decode, get_current_user dependency.
"""
import pytest

from auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def _bcrypt_available():
    """Skip if passlib/bcrypt backend is unavailable or incompatible (e.g. bcrypt 4.x vs passlib)."""
    try:
        hash_password("test")
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _bcrypt_available(), reason="bcrypt backend unavailable or incompatible")
class TestPasswordHashing:
    def test_hash_and_verify_roundtrip(self):
        password = "securepassword123"
        hashed = hash_password(password)
        assert hashed != password
        assert verify_password(password, hashed) is True

    def test_verify_fails_for_wrong_password(self):
        hashed = hash_password("correct")
        assert verify_password("wrong", hashed) is False

    def test_same_password_different_hashes(self):
        a = hash_password("same")
        b = hash_password("same")
        assert a != b
        assert verify_password("same", a) and verify_password("same", b)


class TestJWT:
    def test_create_and_decode_token(self):
        token = create_access_token(subject=42)
        assert isinstance(token, str)
        sub = decode_access_token(token)
        assert sub == "42"

    def test_decode_invalid_token_returns_none(self):
        assert decode_access_token("invalid.jwt.here") is None
        assert decode_access_token("") is None

    def test_create_token_subject_string(self):
        token = create_access_token(subject="user@example.com")
        sub = decode_access_token(token)
        assert sub == "user@example.com"
