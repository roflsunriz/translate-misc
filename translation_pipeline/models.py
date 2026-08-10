from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

ARTICLE_ATTRIBUTION = (
    "*翻訳初稿は PLaMo 2 translate の出力を使用し、別のLLMによる校閲を経て作成した。"
    "公開前に人間が最終確認・修正している。*"
)


@dataclass(frozen=True)
class Article:
    url: str
    title: str
    author: str | None
    published_date: str | None
    source_markdown: str


@dataclass(frozen=True)
class Endpoint:
    base_url: str
    model: str | None
    api_key: str
    timeout_seconds: float


@dataclass(frozen=True)
class SessionMetadata:
    slug: str
    category: str
    original_url: str
    title: str
    author: str | None
    published_date: str | None
    created_at: str
    translator_model: str
    reviewer_provider: str
    reviewer_model: str
    stage: str = "awaiting_human_review"
    commit: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> SessionMetadata:
        return cls(
            slug=str(value["slug"]),
            category=str(value["category"]),
            original_url=str(value["original_url"]),
            title=str(value["title"]),
            author=_optional_string(value.get("author")),
            published_date=_optional_string(value.get("published_date")),
            created_at=str(value["created_at"]),
            translator_model=str(value["translator_model"]),
            reviewer_provider=str(value["reviewer_provider"]),
            reviewer_model=str(value["reviewer_model"]),
            stage=str(value.get("stage", "awaiting_human_review")),
            commit=_optional_string(value.get("commit")),
        )


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
