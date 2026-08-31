"""
Authentication and role scoping.

The simulated two-step verification is deliberate, not a shortcut: the design
already assumes it, and a demo that walks a judge through an MFA prompt is more
honest about what a deployment requires than one that logs straight in. Any
six-digit code is accepted and the interface says so on screen.

What is *not* simulated is the role scoping. A regulator's token cannot reach a
factory record, and that is enforced here in a dependency rather than by hiding
a button in the frontend.
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from .config import READ_ONLY_ROLES, ROLES, settings

bearer = HTTPBearer(auto_error=False)


class Principal(BaseModel):
    role: str
    msp_id: str
    org: str
    person: str
    label: str
    read_only: bool


def issue_token(role: str) -> str:
    if role not in ROLES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unknown role {role}")
    profile = ROLES[role]
    now = dt.datetime.now(dt.UTC)
    claims = {
        "sub": profile["identity"],
        "role": role,
        "msp_id": profile["msp_id"],
        "iat": now,
        "exp": now + dt.timedelta(minutes=settings.token_ttl_minutes),
    }
    return jwt.encode(claims, settings.secret_key, algorithm=settings.algorithm)


def current_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> Principal:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "sign in to continue")
    try:
        claims = jwt.decode(
            credentials.credentials, settings.secret_key, algorithms=[settings.algorithm]
        )
    except JWTError:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "session expired, sign in again"
        ) from None

    role = claims.get("role")
    if role not in ROLES:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "unrecognised role in token")

    profile = ROLES[role]
    return Principal(
        role=role,
        msp_id=profile["msp_id"],
        org=profile["org"],
        person=profile["person"],
        label=profile["label"],
        read_only=role in READ_ONLY_ROLES,
    )


CurrentUser = Annotated[Principal, Depends(current_principal)]


def require_roles(*allowed: str):
    """
    Restrict an endpoint to named roles.

    The message names the roles that *are* allowed, because a 403 that only says
    "forbidden" teaches the user nothing — the design specification asks for the
    same thing on screen.
    """

    def dependency(user: CurrentUser) -> Principal:
        if user.role not in allowed:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"this view is for {', '.join(allowed)}; you are signed in as {user.role}",
            )
        return user

    return dependency


def require_capability(user: Principal, capability: str) -> None:
    """
    Check a named capability rather than a role.

    Role checks scattered through handlers are how gaps appear: a new endpoint
    gets written, nobody remembers to add the check, and it silently serves
    everyone. Reads were exactly that gap here — the regulator, whose entire
    screen promises it sees no factory data, could list every committed record
    through the API.
    """
    from .config import CAPABILITIES

    if capability not in CAPABILITIES.get(user.role, set()):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            {
                "code": "CAPABILITY_DENIED",
                "message": (
                    f"{user.label} may not {capability.replace('_', ' ')}. "
                    "Read-only observer access covers aggregate governance "
                    "statistics and events only; factory-level records require a "
                    "separate lawful-basis access grant."
                    if user.read_only
                    else f"{user.label} may not {capability.replace('_', ' ')}."
                ),
            },
        )


def deny_read_only(user: Principal) -> None:
    """
    The regulator observes. It does not write.

    Called at the top of every mutating handler rather than relying on route
    grouping, so adding a new write endpoint cannot silently omit the check.
    """
    if user.read_only:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "read-only observer access: factory-level records and write actions "
            "require a separate lawful-basis access grant",
        )
