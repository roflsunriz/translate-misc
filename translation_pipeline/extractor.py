from __future__ import annotations

import ipaddress
import json
import re
import socket
from collections.abc import Callable
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from trafilatura import extract

from translation_pipeline.errors import PipelineError
from translation_pipeline.models import Article

Resolver = Callable[..., list[tuple[Any, ...]]]
DEFAULT_RESOLVER = cast(Resolver, socket.getaddrinfo)


class _ValidatedRedirectHandler(HTTPRedirectHandler):
    def __init__(self, allow_private: bool) -> None:
        self.allow_private = allow_private
        super().__init__()

    def redirect_request(  # type: ignore[no-untyped-def]
        self, req, fp, code, msg, headers, newurl
    ):
        validate_public_url(newurl, allow_private=self.allow_private)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_and_extract(
    url: str,
    *,
    timeout_seconds: float,
    max_download_bytes: int,
    allow_private: bool = False,
    resolver: Resolver = DEFAULT_RESOLVER,
) -> Article:
    validate_public_url(url, allow_private=allow_private, resolver=resolver)
    opener = build_opener(_ValidatedRedirectHandler(allow_private))
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (compatible; translate-misc/0.1; "
                "+https://github.com/roflsunriz/translate-misc)"
            )
        },
    )
    try:
        with opener.open(request, timeout=timeout_seconds) as response:
            final_url = response.geturl()
            validate_public_url(final_url, allow_private=allow_private, resolver=resolver)
            content_type = response.headers.get_content_type()
            if content_type not in {"text/html", "application/xhtml+xml"}:
                raise PipelineError(f"HTMLページではありません（Content-Type: {content_type}）。")
            raw = response.read(max_download_bytes + 1)
            if len(raw) > max_download_bytes:
                raise PipelineError(
                    f"ページが取得上限 {max_download_bytes:,} バイトを超えています。"
                )
            charset = response.headers.get_content_charset() or "utf-8"
    except HTTPError as error:
        raise PipelineError(f"記事ページの取得に失敗しました（HTTP {error.code}）。") from error
    except (URLError, TimeoutError) as error:
        raise PipelineError(f"記事ページの取得に失敗しました: {error}") from error

    html = raw.decode(charset, errors="replace")
    body = extract(
        html,
        url=final_url,
        output_format="markdown",
        include_comments=False,
        include_tables=True,
        include_images=False,
        include_links=True,
        favor_precision=True,
    )
    metadata_json = extract(
        html,
        url=final_url,
        output_format="json",
        with_metadata=True,
        include_comments=False,
        favor_precision=True,
    )
    if not body or len(body.strip()) < 200:
        raise PipelineError(
            "記事本文を十分に抽出できませんでした。ログイン必須ページやJavaScript描画ページでは、"
            "保存済みHTMLからの入力機能を追加する必要があります。"
        )
    metadata = _parse_metadata(metadata_json)
    title = _string(metadata.get("title")) or _fallback_title(final_url)
    return Article(
        url=final_url,
        title=title,
        author=_string(metadata.get("author")),
        published_date=_string(metadata.get("date")),
        source_markdown=body.strip(),
    )


def validate_public_url(
    url: str,
    *,
    allow_private: bool = False,
    resolver: Resolver = DEFAULT_RESOLVER,
) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise PipelineError("URLは http:// または https:// で指定してください。")
    if parsed.username or parsed.password:
        raise PipelineError("認証情報を含むURLは指定できません。")
    try:
        addresses = resolver(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
    except socket.gaierror as error:
        raise PipelineError(f"ホスト名を解決できません: {parsed.hostname}") from error
    if allow_private:
        return
    for address in addresses:
        sockaddr = address[4]
        if not isinstance(sockaddr, tuple) or not sockaddr:
            continue
        ip = ipaddress.ip_address(str(sockaddr[0]))
        if not ip.is_global:
            raise PipelineError(
                "安全のためローカル・プライベート・予約済みアドレスからの取得を拒否しました。"
                "必要な場合だけ --allow-private-url を指定してください。"
            )


def _parse_metadata(value: str | None) -> dict[str, object]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _string(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return re.sub(r"\s+", " ", value).strip()


def _fallback_title(url: str) -> str:
    parsed = urlparse(url)
    tail = parsed.path.rstrip("/").rsplit("/", 1)[-1]
    return tail.replace("-", " ").replace("_", " ").strip().title() or parsed.hostname or "Article"
