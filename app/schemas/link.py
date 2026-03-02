from datetime import datetime

from pydantic import BaseModel, HttpUrl, field_serializer


class LinkCreate(BaseModel):
    original_url: HttpUrl
    custom_alias: str | None = None
    expires_at: datetime | None = None

    @field_serializer("original_url")
    def serialize_url(self, v: HttpUrl) -> str:
        return str(v)


class LinkUpdate(BaseModel):
    original_url: HttpUrl | None = None
    expires_at: datetime | None = None

    @field_serializer("original_url")
    def serialize_url(self, v: HttpUrl | None) -> str | None:
        return str(v) if v else None


class LinkOut(BaseModel):
    id: int
    alias: str
    original_url: str
    owner_id: int
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LinkList(BaseModel):
    items: list[LinkOut]
    total: int
    offset: int
    limit: int


class StatsOut(BaseModel):
    alias: str
    total_clicks: int
    unique_ips: int
