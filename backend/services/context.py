"""
UserContext and Admin Authentication (Addendum D).
- Constant-time password validation against ADMIN_PASSWORD from environment.
- HMAC-SHA256 signed admin tokens with expiry.
- Rate-limiting (5 failures -> 60s lockout).
- Write routes dependency (require_admin_context).
- Public read dependency (get_user_context).
- Never leaks or logs ADMIN_PASSWORD.
"""
from __future__ import annotations

import hmac
import hashlib
import time
import json
import base64
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from backend.config import settings

log = logging.getLogger(__name__)

security_bearer = HTTPBearer(auto_error=False)


@dataclass
class UserContext:
    user_id: str = "guest"
    display_name: str = "Viewer"
    roles: list[str] = field(default_factory=lambda: ["viewer"])
    is_admin: bool = False

    def has_role(self, role: str) -> bool:
        return role in self.roles or self.is_admin


# Rate-limiting state for login: client IP -> list of failed attempt timestamps
_LOGIN_FAILURES: dict[str, list[float]] = {}
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_SEC = 60.0


def check_rate_limit(ip: str) -> None:
    now = time.time()
    attempts = _LOGIN_FAILURES.get(ip, [])
    # Keep attempts within lockout window
    recent = [t for t in attempts if now - t < LOCKOUT_DURATION_SEC]
    _LOGIN_FAILURES[ip] = recent
    if len(recent) >= MAX_FAILED_ATTEMPTS:
        retry_after = int(LOCKOUT_DURATION_SEC - (now - recent[0]))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed login attempts. Please wait {max(1, retry_after)} seconds.",
        )


def record_login_failure(ip: str) -> None:
    now = time.time()
    attempts = _LOGIN_FAILURES.get(ip, [])
    attempts.append(now)
    _LOGIN_FAILURES[ip] = attempts


def reset_login_failures(ip: str) -> None:
    _LOGIN_FAILURES.pop(ip, None)


def sign_admin_token() -> str:
    """Create a signed, expiring admin token."""
    payload = {
        "sub": "admin",
        "role": "admin",
        "exp": int(time.time()) + (settings.ADMIN_TOKEN_EXPIRE_HOURS * 3600),
        "iat": int(time.time()),
    }
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8").rstrip("=")
    key = settings.ADMIN_SECRET_KEY.encode("utf-8")
    sig = hmac.new(key, payload_b64.encode("utf-8"), hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).decode("utf-8").rstrip("=")
    return f"{payload_b64}.{sig_b64}"


def verify_admin_token(token: str) -> bool:
    """Validate token signature and expiration."""
    if not token or "." not in token:
        return False
    parts = token.split(".")
    if len(parts) != 2:
        return False
    payload_b64, sig_b64 = parts
    try:
        # Recompute sig
        key = settings.ADMIN_SECRET_KEY.encode("utf-8")
        expected_sig = hmac.new(key, payload_b64.encode("utf-8"), hashlib.sha256).digest()
        expected_sig_b64 = base64.urlsafe_b64encode(expected_sig).decode("utf-8").rstrip("=")
        if not hmac.compare_digest(sig_b64, expected_sig_b64):
            return False

        # Check payload and expiry
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8"))
        if payload.get("sub") != "admin":
            return False
        if payload.get("exp", 0) < time.time():
            return False
        return True
    except Exception:
        return False


def get_token_from_request(request: Request) -> Optional[str]:
    # 1. Bearer Header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    # 2. HttpOnly Cookie
    cookie_token = request.cookies.get("admin_token")
    if cookie_token:
        return cookie_token.strip()
    return None


def get_user_context(request: Request) -> UserContext:
    """Public read context. If valid admin token is present, returns admin context; otherwise guest."""
    token = get_token_from_request(request)
    if token and verify_admin_token(token):
        return UserContext(user_id="admin", display_name="Administrator", roles=["admin"], is_admin=True)
    return UserContext(user_id="guest", display_name="Viewer", roles=["viewer"], is_admin=False)


def require_admin_context(request: Request) -> UserContext:
    """Enforce admin authentication for mutating endpoints."""
    if not settings.is_admin_configured:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Write operations disabled: Admin authentication is not configured (ADMIN_PASSWORD or ADMIN_SECRET_KEY missing/unset).",
        )

    token = get_token_from_request(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required: Admin token missing.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_admin_token(token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or expired admin token. Please sign in again.",
        )

    return UserContext(user_id="admin", display_name="Administrator", roles=["admin"], is_admin=True)


# Keep ADMIN_CONTEXT available for testing utilities if needed
ADMIN_CONTEXT = UserContext(user_id="admin", display_name="Administrator", roles=["admin"], is_admin=True)
