import socket

import pytest

from translation_pipeline.errors import PipelineError
from translation_pipeline.extractor import validate_public_url


def _resolve_to(address: str):  # type: ignore[no-untyped-def]
    def resolver(*args: object, **kwargs: object) -> list[tuple[object, ...]]:
        del args, kwargs
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))]

    return resolver


def test_public_url_is_accepted() -> None:
    validate_public_url("https://example.com/article", resolver=_resolve_to("93.184.216.34"))


@pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.2", "169.254.1.1", "::1"])
def test_private_or_reserved_url_is_rejected(address: str) -> None:
    with pytest.raises(PipelineError, match="プライベート"):
        validate_public_url("https://example.com/article", resolver=_resolve_to(address))


def test_private_url_requires_explicit_override() -> None:
    validate_public_url(
        "http://localhost/article",
        allow_private=True,
        resolver=_resolve_to("127.0.0.1"),
    )


def test_credentials_in_url_are_rejected() -> None:
    with pytest.raises(PipelineError, match="認証情報"):
        validate_public_url(
            "https://user:password@example.com", resolver=_resolve_to("93.184.216.34")
        )
