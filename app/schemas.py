from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.security import validate_alias, validate_destination


class LinkCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    url: str = Field(min_length=1, max_length=4096)
    custom_alias: str | None = Field(default=None, max_length=32)
    expires_at: datetime | None = None

    @field_validator("url")
    @classmethod
    def check_url(cls, value: str) -> str:
        return validate_destination(value)

    @field_validator("custom_alias")
    @classmethod
    def check_alias(cls, value: str | None) -> str | None:
        return validate_alias(value)

    @field_validator("expires_at")
    @classmethod
    def check_expiration(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("expires_at must include a timezone")
        if value <= datetime.now(timezone.utc):
            raise ValueError("expires_at must be in the future")
        return value


class LinkCreated(BaseModel):
    code: str
    short_url: str
    original_url: str
    created_at: datetime
    expires_at: datetime | None
    management_token: str
    management_note: str = "Save this token securely; it cannot be retrieved later."


class LinkStats(BaseModel):
    code: str
    original_url: str
    click_count: int
    created_at: datetime
    expires_at: datetime | None
    last_clicked_at: datetime | None
    is_active: bool
    status: Literal["active", "expired", "disabled"]


class LinkDisabled(BaseModel):
    code: str
    is_active: bool
    message: str


class HealthResponse(BaseModel):
    status: str


class AbuseReportCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    code: str = Field(min_length=4, max_length=32)
    category: Literal["phishing", "malware", "spam", "scam", "other"]
    details: str | None = Field(default=None, max_length=1000)

    @field_validator("code")
    @classmethod
    def validate_report_code(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_-]{4,32}", value):
            raise ValueError("Short code format is invalid")
        return value

    @field_validator("details")
    @classmethod
    def normalize_details(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class AbuseReportCreated(BaseModel):
    id: int
    code: str
    status: str
    created_at: datetime


class AbuseReportAdminView(BaseModel):
    id: int
    code: str
    category: str
    details: str | None
    status: str
    created_at: datetime
    resolved_at: datetime | None


class AbuseReportResolve(BaseModel):
    model_config = ConfigDict(extra="forbid")
    disable_link: bool = False


class AbuseReportResolved(BaseModel):
    id: int
    status: str
    link_disabled: bool
    resolved_at: datetime
