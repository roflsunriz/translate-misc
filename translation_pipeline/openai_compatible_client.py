from __future__ import annotations

import json
import time
from collections.abc import Mapping, Sequence
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from translation_pipeline.errors import PipelineError
from translation_pipeline.models import Endpoint


class OpenAICompatibleClient:
    """OpenAI互換の completions / chat completions を利用する最小クライアント。"""

    def __init__(self, endpoint: Endpoint) -> None:
        self.endpoint = endpoint
        self._model: str | None = endpoint.model

    @property
    def model(self) -> str:
        if self._model is None:
            self._model = self._discover_model()
        return self._model

    def completion(
        self,
        prompt: str,
        *,
        max_tokens: int = 4096,
        stop: Sequence[str] = (),
    ) -> str:
        response = self._request(
            "POST",
            "/completions",
            {
                "model": self.model,
                "prompt": prompt,
                "temperature": 0,
                "max_tokens": max_tokens,
                "stop": list(stop),
            },
        )
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            raise PipelineError("翻訳サーバーの応答に choices がありません。")
        first = choices[0]
        text_value = first.get("text") if isinstance(first, dict) else None
        if not isinstance(text_value, str):
            raise PipelineError("翻訳サーバーの応答本文を読み取れません。")
        return _clean_model_output(text_value)

    def chat(self, system: str, user: str, *, max_tokens: int = 4096) -> str:
        response = self._request(
            "POST",
            "/chat/completions",
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0,
                "max_tokens": max_tokens,
            },
        )
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            raise PipelineError("校閲サーバーの応答に choices がありません。")
        first = choices[0]
        message = first.get("message") if isinstance(first, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str):
            raise PipelineError("校閲サーバーの応答本文を読み取れません。")
        return _clean_model_output(content)

    def healthcheck(self) -> str:
        return self.model

    def _discover_model(self) -> str:
        response = self._request("GET", "/models")
        data = response.get("data")
        if not isinstance(data, list) or not data:
            raise PipelineError(f"{self.endpoint.base_url}/models にロード済みモデルがありません。")
        first = data[0]
        model_id = first.get("id") if isinstance(first, dict) else None
        if not isinstance(model_id, str):
            raise PipelineError("モデル一覧の形式を解釈できません。")
        return model_id

    def _request(
        self, method: str, path: str, body: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        if not self.endpoint.api_key:
            raise PipelineError(
                "校閲APIキーが設定されていません。Cerebrasなら CEREBRAS_API_KEY、"
                "さくらのAI Engineなら SAKURA_AI_API_KEY、OpenRouterなら "
                "OPENROUTER_API_KEY を環境変数に設定してください。"
            )
        url = f"{self.endpoint.base_url}{path}"
        encoded = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        request = Request(
            url,
            data=encoded,
            method=method,
            headers={
                "Authorization": f"Bearer {self.endpoint.api_key}",
                "Content-Type": "application/json",
            },
        )
        payload = self._send_with_retry(request)
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError as error:
            raise PipelineError("LLMサーバーから不正なJSON応答を受け取りました。") from error
        if not isinstance(parsed, dict):
            raise PipelineError("LLMサーバーのJSON応答がオブジェクトではありません。")
        return parsed

    def _send_with_retry(self, request: Request) -> str:
        for attempt in range(4):
            try:
                with urlopen(request, timeout=self.endpoint.timeout_seconds) as response:
                    raw = cast(bytes, response.read())
                    return raw.decode("utf-8")
            except HTTPError as error:
                detail = error.read().decode("utf-8", errors="replace")[:1000]
                if error.code not in {429, 500, 502, 503, 504} or attempt == 3:
                    raise PipelineError(
                        f"LLM APIが HTTP {error.code} を返しました: {detail}"
                    ) from error
                retry_after = error.headers.get("Retry-After")
                delay = _retry_delay(retry_after, attempt)
                time.sleep(delay)
            except (URLError, TimeoutError) as error:
                if attempt == 3:
                    raise PipelineError(
                        f"LLM API {self.endpoint.base_url} に接続できません。"
                    ) from error
                time.sleep(2**attempt)
        raise AssertionError("retry loop must return or raise")


def _clean_model_output(value: str) -> str:
    text = value.strip()
    if text.startswith("```markdown") and text.endswith("```"):
        text = text[len("```markdown") : -3].strip()
    elif text.startswith("```") and text.endswith("```"):
        text = text[3:-3].strip()
    if not text:
        raise PipelineError("LLMが空の応答を返しました。")
    return text


def _retry_delay(retry_after: str | None, attempt: int) -> float:
    if retry_after:
        try:
            return min(float(retry_after), 30.0)
        except ValueError:
            pass
    return float(2**attempt)
