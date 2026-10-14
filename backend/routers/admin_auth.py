"""
Admin Authentication Router (Addendum D).
- POST /api/admin/login
- POST /api/admin/logout
- GET /api/admin/status
"""
from __future__ import annotations

import hmac
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel

from backend.config import settings
from backend.services.context import (
    UserContext,
    check_rate_limit,
    record_login_failure,
    reset_login_failures,
    sign_admin_token,
    require_admin_context,
    get_user_context,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


class LoginRequest(BaseModel):
    password: str


class LoginResponse(BaseModel):
    status: str
    token: str
    expires_in_hours: int


@router.post("/login", response_model=LoginResponse)
def admin_login(body: LoginRequest, request: Request, response: Response):
    """
    Authenticate admin with ADMIN_PASSWORD.
    Uses constant-time comparison, rate-limiting, and sets HttpOnly cookie.
    Password is never logged or returned.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"

    if not settings.is_admin_configured:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access is disabled: Admin authentication is not configured (ADMIN_PASSWORD or ADMIN_SECRET_KEY missing/unset).",
        )

    # 1. Rate-limit check
    check_rate_limit(client_ip)

    # 2. Constant-time comparison
    is_valid = hmac.compare_digest(body.password.strip(), settings.ADMIN_PASSWORD.strip())

    if not is_valid:
        record_login_failure(client_ip)
        log.warning("Failed admin login attempt from IP %s", client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )

    # Reset failure tracking on success
    reset_login_failures(client_ip)

    # Issue signed token
    token = sign_admin_token()

    # Set secure HttpOnly cookie (SameSite Lax, secure in prod)
    response.set_cookie(
        key="admin_token",
        value=token,
        max_age=settings.ADMIN_TOKEN_EXPIRE_HOURS * 3600,
        httponly=True,
        samesite="lax",
        secure=settings.is_cookie_secure,
    )

    log.info("Admin successfully signed in from IP %s", client_ip)
    return LoginResponse(
        status="ok",
        token=token,
        expires_in_hours=settings.ADMIN_TOKEN_EXPIRE_HOURS,
    )


@router.post("/logout", dependencies=[Depends(require_admin_context)])
def admin_logout(response: Response, ctx: UserContext = Depends(require_admin_context)):
    """Clear admin cookie. Admin-only."""
    response.delete_cookie("admin_token")
    return {"status": "logged_out"}


@router.get("/status")
def admin_status(ctx: UserContext = Depends(get_user_context)):
    """Check current admin session state without credentials."""
    is_admin = ctx.is_admin
    configured = bool(settings.is_admin_configured)
    return {
        "is_admin": is_admin,
        "is_configured": configured,
    }
