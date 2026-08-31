"""Sign-in: role picker, then the simulated two-step verification."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from ..auth import CurrentUser, issue_token
from ..config import ROLES

router = APIRouter(prefix="/auth", tags=["auth"])


class RoleOption(BaseModel):
    role: str
    label: str
    org: str
    person: str
    summary: str
    landing: str


class VerifyRequest(BaseModel):
    role: str
    code: str = Field(min_length=1, max_length=12)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    org: str
    person: str
    landing: str


@router.get("/roles", response_model=list[RoleOption])
def roles() -> list[RoleOption]:
    return [
        RoleOption(
            role=key, label=v["label"], org=v["org"], person=v["person"],
            summary=v["summary"], landing=v["landing"],
        )
        for key, v in ROLES.items()
    ]


@router.post("/verify", response_model=TokenResponse)
def verify(body: VerifyRequest) -> TokenResponse:
    """
    Any six-digit code is accepted, and the interface says so on screen.

    The shape of the flow is real even though the check is not: a deployment
    swaps this for a TOTP validation and nothing else changes.
    """
    if body.role not in ROLES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unknown role {body.role}")
    digits = body.code.strip()
    if not (len(digits) == 6 and digits.isdigit()):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Invalid code. For this demo, enter any 6-digit number.",
        )
    profile = ROLES[body.role]
    return TokenResponse(
        access_token=issue_token(body.role), role=body.role,
        org=profile["org"], person=profile["person"], landing=profile["landing"],
    )


@router.get("/me")
def me(user: CurrentUser) -> dict:
    return user.model_dump()
