from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class Article:
    url: str
    title: str
    section: str
    publisher: str
    published_at: str | None = None
    text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Article":
        return cls(**data)


@dataclass(frozen=True)
class Script:
    article_url: str
    title: str
    created_at: str
    body: str
    sources: list[dict[str, str]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Script":
        return cls(**data)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
