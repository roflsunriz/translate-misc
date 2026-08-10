import pytest

from translation_pipeline.errors import PipelineError
from translation_pipeline.markdown_chunks import (
    chunk_markdown,
    protect_literals,
    restore_literals,
)


def test_code_fence_is_not_translated() -> None:
    chunks = chunk_markdown("Intro text.\n\n```python\nprint('hello')\n```\n\nLast text.", 500)

    assert [(chunk.translate, chunk.text) for chunk in chunks] == [
        (True, "Intro text."),
        (False, "```python\nprint('hello')\n```"),
        (True, "Last text."),
    ]


def test_chunks_do_not_exceed_limit_when_splittable() -> None:
    chunks = chunk_markdown("First sentence. Second sentence. Third sentence.", 20)

    assert all(len(chunk.text) <= 20 for chunk in chunks)
    assert " ".join(chunk.text for chunk in chunks) == (
        "First sentence. Second sentence. Third sentence."
    )


def test_literals_are_round_tripped() -> None:
    source = "Read [the article](https://example.com/a?q=1) and run `example --flag`."
    protected, values = protect_literals(source)

    assert "https://" not in protected
    assert "example --flag" not in protected
    assert restore_literals(protected, values) == source


def test_missing_protected_literal_is_rejected() -> None:
    protected, values = protect_literals("Read https://example.com")

    with pytest.raises(PipelineError, match="保護記号"):
        restore_literals(protected.replace("[[[LITERAL_0000]]]", ""), values)
