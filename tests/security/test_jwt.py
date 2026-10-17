"""
Unit tests for JWT verification.

These tests run without any infrastructure — they verify the auth
package's security properties directly.
"""
from __future__ import annotations

import time
import uuid

import jwt as pyjwt
import pytest

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../packages"))

from auth.exceptions import ExpiredTokenError, InvalidTokenError
from auth.jwt import verify_jwt

SECRET = "test-secret-that-is-long-enough-for-hs256-algorithm"
ALGORITHM = "HS256"


def _mint_token(
    secret: str = SECRET,
    sub: str | None = None,
    role: str = "user",
    aud: str = "authenticated",
    exp_offset: int = 3600,
    extra: dict | None = None,
) -> str:
    now = int(time.time())
    payload = {
        "sub": str(sub or uuid.uuid4()),
        "email": "test@example.com",
        "role": role,
        "aud": aud,
        "iat": now,
        "exp": now + exp_offset,
    }
    if extra:
        payload.update(extra)
    return pyjwt.encode(payload, secret, algorithm=ALGORITHM)


# ── Valid token ───────────────────────────────────────────────────────────────

@pytest.mark.security
def test_valid_token_returns_claims():
    token = _mint_token()
    claims = verify_jwt(token, SECRET)
    assert claims.email == "test@example.com"
    assert claims.role == "user"
    assert claims.aud == "authenticated"


@pytest.mark.security
def test_tenant_id_extracted_from_claims():
    tenant = uuid.uuid4()
    token = _mint_token(extra={"tenant_id": str(tenant)})
    claims = verify_jwt(token, SECRET)
    assert claims.tenant_id == tenant


# ── Expired token ─────────────────────────────────────────────────────────────

@pytest.mark.security
def test_expired_token_raises():
    token = _mint_token(exp_offset=-10)  # expired 10 seconds ago
    with pytest.raises(ExpiredTokenError):
        verify_jwt(token, SECRET)


# ── Wrong secret ──────────────────────────────────────────────────────────────

@pytest.mark.security
def test_wrong_secret_raises():
    token = _mint_token(secret="correct-secret-value-here")
    with pytest.raises(InvalidTokenError):
        verify_jwt(token, "completely-different-secret-value")


# ── Tampered payload ──────────────────────────────────────────────────────────

@pytest.mark.security
def test_tampered_token_raises():
    token = _mint_token()
    # Flip one character in the signature portion.
    parts = token.split(".")
    tampered = parts[0] + "." + parts[1] + "." + parts[2][:-1] + "X"
    with pytest.raises(InvalidTokenError):
        verify_jwt(tampered, SECRET)


# ── Missing required claims ───────────────────────────────────────────────────

@pytest.mark.security
def test_missing_email_claim_raises():
    now = int(time.time())
    payload = {
        "sub": str(uuid.uuid4()),
        # email intentionally omitted
        "role": "user",
        "aud": "authenticated",
        "iat": now,
        "exp": now + 3600,
    }
    token = pyjwt.encode(payload, SECRET, algorithm=ALGORITHM)
    with pytest.raises(InvalidTokenError):
        verify_jwt(token, SECRET)


# ── Wrong audience ────────────────────────────────────────────────────────────

@pytest.mark.security
def test_wrong_audience_raises():
    token = _mint_token(aud="anon")  # wrong audience
    with pytest.raises(InvalidTokenError):
        verify_jwt(token, SECRET)


# ── Empty / blank token ───────────────────────────────────────────────────────

@pytest.mark.security
@pytest.mark.parametrize("bad_token", ["", "   ", "not.a.jwt"])
def test_invalid_token_string_raises(bad_token: str):
    with pytest.raises(InvalidTokenError):
        verify_jwt(bad_token, SECRET)
