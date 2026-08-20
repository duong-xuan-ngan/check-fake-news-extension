from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from typing import Optional

import jwt
import requests
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import get_settings
from . import db

_bearer = HTTPBearer(auto_error=False)


class GoogleTokenError(Exception):
    pass


class RefreshTokenError(Exception):
    pass


def exchange_google_code(code: str, code_verifier: str, redirect_uri: str) -> dict:
    """Exchange an OAuth authorization code (PKCE) for an identity."""
    settings = get_settings()
    print(f"[auth] exchange_google_code: client_id={settings.google_client_id!r}")
    print(f"[auth] exchange_google_code: redirect_uri={redirect_uri!r}")
    print(f"[auth] exchange_google_code: code_len={len(code)} code_verifier_len={len(code_verifier)}")
    if not settings.google_client_id:
        raise GoogleTokenError("GOOGLE_CLIENT_ID is not configured")
    if not settings.google_client_secret:
        raise GoogleTokenError("GOOGLE_CLIENT_SECRET is not configured")

    token_resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
        },
        timeout=10,
    )
    print(f"[auth] token endpoint status={token_resp.status_code} body={token_resp.text[:500]}")
    if token_resp.status_code != 200:
        detail = ""
        try:
            body = token_resp.json()
            detail = body.get("error_description") or body.get("error") or token_resp.text[:300]
        except ValueError:
            detail = token_resp.text[:300]
        raise GoogleTokenError(f"Failed to exchange authorization code: {detail}")

    token_json = token_resp.json()
    id_token = token_json.get("id_token")
    if not id_token:
        raise GoogleTokenError(f"No id_token returned by Google: {token_json}")

    info_resp = requests.get(
        "https://oauth2.googleapis.com/tokeninfo",
        params={"id_token": id_token},
        timeout=10,
    )
    print(f"[auth] tokeninfo status={info_resp.status_code} body={info_resp.text[:500]}")
    if info_resp.status_code != 200:
        raise GoogleTokenError(f"Invalid Google id_token: {info_resp.text[:300]}")

    info = info_resp.json()
    print(f"[auth] tokeninfo aud={info.get('aud')!r} expected={settings.google_client_id!r} email_verified={info.get('email_verified')!r}")
    if info.get("aud") != settings.google_client_id:
        raise GoogleTokenError("Token audience does not match this application")
    if not info.get("email_verified"):
        raise GoogleTokenError("Google account email is not verified")

    return {
        "sub": info.get("sub"),
        "email": info.get("email"),
        "name": info.get("name"),
        "picture": info.get("picture"),
    }


def create_access_token(user_id: str) -> str:
    settings = get_settings()
    if not settings.jwt_secret:
        raise RuntimeError("JWT_SECRET is not configured")

    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expires_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_refresh_token(user_id: str) -> str:
    """Generate a new refresh token and store its hash."""
    settings = get_settings()
    raw = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    db.store_refresh_token(_hash_token(raw), user_id, expires_at)
    return raw


def issue_tokens(user_id: str) -> dict:
    return {
        "access_token": create_access_token(user_id),
        "refresh_token": create_refresh_token(user_id),
    }


def rotate_refresh_token(raw_token: str) -> dict:
    """Validate a refresh token, revoke it, and issue a fresh pair."""
    if not raw_token:
        raise RefreshTokenError("Missing refresh token")

    record = db.get_refresh_token(_hash_token(raw_token))
    if record is None:
        raise RefreshTokenError("Invalid refresh token")
    if record["revoked_at"] is not None:
        raise RefreshTokenError("Refresh token already used")
    if record["expires_at"] is None or record["expires_at"] <= datetime.now(timezone.utc):
        raise RefreshTokenError("Refresh token expired")

    db.revoke_refresh_token(_hash_token(raw_token))
    return issue_tokens(record["user_id"])


def revoke_refresh_token(raw_token: str) -> None:
    if raw_token:
        db.revoke_refresh_token(_hash_token(raw_token))


def decode_access_token(token: str) -> Optional[str]:
    settings = get_settings()
    if not settings.jwt_secret:
        return None
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return payload.get("sub")
    except jwt.PyJWTError:
        return None


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> dict:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
        )
    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    user = db.user_for_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unknown user",
        )
    return user


def enforce_daily_quota(user: dict = Depends(get_current_user)) -> dict:
    """Consume one daily check for the authenticated user; 429 if exhausted."""
    settings = get_settings()
    today = datetime.now(timezone.utc).date()
    used = db.consume_daily_check(user["id"], today, settings.daily_check_limit)
    if used is None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "daily_limit_reached",
                "limit": settings.daily_check_limit,
                "remaining": 0,
            },
        )
    return user
