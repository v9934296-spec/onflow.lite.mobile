"""Consent status payloads for /me and /api/v1/consent."""

from __future__ import annotations

from pydantic import BaseModel


class ConsentStatus(BaseModel):
    granted: bool
    granted_at: str | None
    copy_version: str | None
    source: str | None


class ConsentGrantRequest(BaseModel):
    copy_version: str


class ConsentGrantResponse(BaseModel):
    status: ConsentStatus
