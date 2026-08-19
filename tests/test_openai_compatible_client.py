from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from translation_pipeline.errors import PipelineError
from translation_pipeline.models import Endpoint
from translation_pipeline.openai_compatible_client import OpenAICompatibleClient, _select_model_id


class _Handler(BaseHTTPRequestHandler):
    requests: list[tuple[str, dict[str, object]]] = []

    def do_GET(self) -> None:
        assert self.path == "/v1/models"
        self._json(
            {
                "data": [
                    {"id": "whisper-large-v3-turbo", "created": 30},
                    {"id": "multilingual-e5-large", "created": 20},
                    {"id": "loaded-model", "created": 10},
                ]
            }
        )

    def do_POST(self) -> None:
        length = int(self.headers["Content-Length"])
        body = json.loads(self.rfile.read(length))
        assert isinstance(body, dict)
        self.__class__.requests.append((self.path, body))
        if self.path == "/v1/completions":
            self._json({"choices": [{"text": "  訳文だ。  "}]})
        elif self.path == "/v1/chat/completions":
            self._json({"choices": [{"message": {"content": "  校閲後だ。  "}}]})
        else:
            self.send_error(404)

    def log_message(self, format: str, *args: object) -> None:
        del format, args

    def _json(self, value: object) -> None:
        payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


@pytest.fixture
def api_server() -> Iterator[str]:
    _Handler.requests = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1"
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def test_completions_and_chat_endpoints(api_server: str) -> None:
    client = OpenAICompatibleClient(Endpoint(api_server, None, "no-key", 5))

    assert client.model == "loaded-model"
    assert client.completion("prompt", stop=("stop",)) == "訳文だ。"
    assert client.chat("system", "user") == "校閲後だ。"
    assert [path for path, body in _Handler.requests] == [
        "/v1/completions",
        "/v1/chat/completions",
    ]
    assert _Handler.requests[0][1]["model"] == "loaded-model"


def test_missing_api_key_is_rejected_before_request(api_server: str) -> None:
    client = OpenAICompatibleClient(Endpoint(api_server, "model", "", 5))

    with pytest.raises(PipelineError, match="APIキー"):
        client.chat("system", "user")


def test_sakura_model_selection_is_stable_and_excludes_non_chat_models() -> None:
    models = [
        {"id": "preview/Qwen3-Embedding-4B-FP16", "created": 40},
        {"id": "preview/Kimi-K2.7-Code", "created": 30},
        {"id": "gpt-oss-120b", "created": 20},
        {"id": "llm-jp-3.1-8x13b-instruct4", "created": 10},
    ]

    base_url = "https://api.ai.sakura.ad.jp/v1"
    assert _select_model_id(models, base_url) == "llm-jp-3.1-8x13b-instruct4"
    assert _select_model_id(list(reversed(models)), base_url) == "llm-jp-3.1-8x13b-instruct4"
