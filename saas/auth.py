"""
JWT-based session auth for NorthSignal SaaS.
Tokens stored in HTTP-only cookies.
"""
from __future__ import annotations

import os
import time
from typing import Optional

from fastapi import Cookie, Depends, HTTPException, status
from fastapi.responses import Response

# ── Simple JWT-like token using HMAC ──────────────────────────────────────────
# No external JWT library needed — keeps dependencies minimal.

import hashlib
import hmac
import base64
import json

SECRET = os.getenv("SESSION_SECRET", "change-this-secret-in-production-please")
TOKEN_TTL = 60 * 60 * 24 * 7  # 7 days


def _sign(payload: dict) -> str:
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    sig = hmac.new(SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def _verify(token: str) -> Optional[dict]:
    try:
        body, sig = token.rsplit(".", 1)
        expected = hmac.new(SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(base64.urlsafe_b64decode(body).decode())
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


def create_session_token(user_id: int, email: str) -> str:
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": time.time() + TOKEN_TTL,
    }
    return _sign(payload)


def set_session_cookie(response: Response, user_id: int, email: str) -> None:
    token = create_session_token(user_id, email)
    response.set_cookie(
        key="session",
        value=token,
        httponly=True,
        max_age=TOKEN_TTL,
        samesite="lax",
        secure=os.getenv("HTTPS", "false").lower() == "true",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie("session")


def get_current_user_id(session: Optional[str] = Cookie(default=None)) -> Optional[int]:
    if not session:
        return None
    payload = _verify(session)
    return payload["user_id"] if payload else None


def require_auth(user_id: Optional[int] = Depends(get_current_user_id)) -> int:
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"},
        )
    return user_id
