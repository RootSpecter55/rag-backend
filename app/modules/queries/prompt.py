from decimal import ROUND_HALF_UP, Decimal

from app.modules.chunks.schemas import RetrievedChunk

SYSTEM_PROMPT = (
    "You answer questions using only the numbered sources provided by the user. "
    "Cite the sources you use inline, like [1] or [2]. "
    "If the sources do not contain the answer, say that you could not find it in the documents "
    "instead of using outside knowledge. Keep answers short and factual."
)

NO_SOURCES_ANSWER = "I could not find anything about this in your documents."


def build_user_prompt(question: str, sources: list[RetrievedChunk]) -> str:
    """Numbered sources first, then the question, so citations map to the `sources` event."""
    blocks = [f"[{i}] ({source.filename})\n{source.text}" for i, source in enumerate(sources, 1)]
    return "Sources:\n\n" + "\n\n".join(blocks) + f"\n\nQuestion: {question}"


def estimate_cost(
    input_tokens: int, output_tokens: int, input_usd_per_mtok: float, output_usd_per_mtok: float
) -> Decimal:
    """Cost from token counts and the configured per-million-token prices, to 6 decimal places."""
    cost = (
        Decimal(input_tokens) * Decimal(str(input_usd_per_mtok))
        + Decimal(output_tokens) * Decimal(str(output_usd_per_mtok))
    ) / Decimal(1_000_000)
    return cost.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
