import itertools
import math
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.modules.chunks.chunker import chunk_text
from app.modules.chunks.schemas import RetrievedChunk
from app.modules.documents.service import safe_filename
from app.modules.queries.prompt import build_user_prompt, estimate_cost
from app.modules.queries.service import month_start
from app.modules.usage.service import month_bounds
from app.providers.embeddings.base import EMBEDDING_DIMENSION
from app.providers.embeddings.fake import FakeEmbeddings
from app.providers.llm.base import LLMUsage
from app.providers.llm.fake import FakeLLM


class TestChunker:
    def test_keeps_short_text_as_one_chunk(self) -> None:
        assert chunk_text("One paragraph.\n\nAnother one.", 200, 20) == [
            "One paragraph.\n\nAnother one."
        ]

    def test_packs_paragraphs_up_to_the_size_limit(self) -> None:
        paragraphs = [f"Paragraph {i} " + "word " * 15 for i in range(6)]
        chunks = chunk_text("\n\n".join(paragraphs), 200, 0)
        assert len(chunks) > 1
        assert all(len(chunk) <= 200 for chunk in chunks)
        assert "".join(chunks).count("Paragraph") == 6  # nothing lost, nothing repeated

    def test_splits_a_long_paragraph_on_word_boundaries(self) -> None:
        text = " ".join(f"w{i}" for i in range(300))
        chunks = chunk_text(text, 200, 0)
        words = " ".join(chunks).split()
        assert words == text.split()  # no word was cut in half

    def test_repeats_the_end_of_each_chunk_at_the_start_of_the_next(self) -> None:
        paragraphs = [f"Sentence number {i} is here." for i in range(30)]
        chunks = chunk_text("\n\n".join(paragraphs), 200, 60)
        for previous, current in itertools.pairwise(chunks):
            first_line = current.split("\n\n")[0]
            assert first_line in previous


class TestFakeEmbeddings:
    async def test_is_deterministic_normalised_and_the_right_size(self) -> None:
        [a, b] = await FakeEmbeddings().embed(["travel policy", "travel policy"])
        assert a == b
        assert len(a) == EMBEDDING_DIMENSION
        assert math.isclose(sum(v * v for v in a), 1.0)

    async def test_texts_sharing_words_are_closer_than_unrelated_texts(self) -> None:
        def cosine(x: list[float], y: list[float]) -> float:
            return sum(i * j for i, j in zip(x, y, strict=True))

        query, related, unrelated = await FakeEmbeddings().embed(
            [
                "how do I book flights",
                "flights are booked in the travel portal",
                "laptops are replaced every three years",
            ]
        )
        assert cosine(query, related) > cosine(query, unrelated)


class TestFakeLLM:
    async def test_answers_from_the_first_source_and_reports_usage(self) -> None:
        user = (
            "Sources:\n\n[1] (a.md)\n# Heading\n"
            "Flights need 14 days notice. More text.\n\nQuestion: x"
        )
        items = [item async for item in FakeLLM().stream("system", user)]
        text = "".join(i for i in items if isinstance(i, str))
        assert text == "According to [1]: Flights need 14 days notice."
        assert isinstance(items[-1], LLMUsage)
        assert items[-1].output_tokens == len(text.split(" "))


def test_user_prompt_numbers_sources_in_order() -> None:
    sources = [
        RetrievedChunk(
            id="00000000-0000-4000-8000-00000000000" + str(i),
            document_id="00000000-0000-4000-8000-000000000000",
            filename=f"doc{i}.md",
            ordinal=i,
            text=f"text {i}",
            distance=0.1 * i,
        )
        for i in (1, 2)
    ]
    prompt = build_user_prompt("What?", sources)
    assert prompt == (
        "Sources:\n\n[1] (doc1.md)\ntext 1\n\n[2] (doc2.md)\ntext 2\n\nQuestion: What?"
    )


def test_cost_uses_per_million_token_prices() -> None:
    assert estimate_cost(1_000_000, 0, 3.0, 15.0) == Decimal("3.000000")
    assert estimate_cost(1200, 300, 3.0, 15.0) == Decimal("0.008100")
    assert estimate_cost(500, 500, 0, 0) == Decimal("0.000000")


def test_month_helpers_use_utc_calendar_months() -> None:
    assert month_start(datetime(2026, 3, 31, 23, tzinfo=UTC)) == datetime(2026, 3, 1, tzinfo=UTC)
    now = datetime(2026, 6, 15, tzinfo=UTC)
    assert month_bounds("2026-12", now) == (
        datetime(2026, 12, 1, tzinfo=UTC),
        datetime(2027, 1, 1, tzinfo=UTC),
    )
    assert month_bounds(None, now)[0] == datetime(2026, 6, 1, tzinfo=UTC)


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("report.md", "report.md"),
        ("../../etc/passwd", "passwd"),
        ("my file (1).txt", "my_file__1_.txt"),
    ],
)
def test_safe_filename_never_returns_a_path(given: str, expected: str) -> None:
    assert safe_filename(given) == expected


BASE_SETTINGS = {
    "database_url": "postgresql+asyncpg://u:p@localhost/db",
    "admin_api_key": "x" * 32,
}


class TestSettings:
    def test_defaults_to_local_providers(self) -> None:
        settings = Settings(**BASE_SETTINGS)
        assert (settings.storage_provider, settings.embedding_provider, settings.llm_provider) == (
            "local",
            "fake",
            "fake",
        )
        assert settings.anthropic_model == "claude-opus-5-5"

    def test_requires_bucket_and_region_for_s3(self) -> None:
        with pytest.raises(ValidationError, match="S3_BUCKET and AWS_REGION"):
            Settings(**BASE_SETTINGS, storage_provider="s3")

    def test_requires_a_region_for_bedrock(self) -> None:
        with pytest.raises(ValidationError, match="Bedrock providers need AWS_REGION"):
            Settings(**BASE_SETTINGS, llm_provider="bedrock")

    def test_rejects_a_non_asyncpg_database_url(self) -> None:
        with pytest.raises(ValidationError):
            Settings(**{**BASE_SETTINGS, "database_url": "postgresql://u:p@localhost/db"})
