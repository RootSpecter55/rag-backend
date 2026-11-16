import re


def _split_long(paragraph: str, size: int) -> list[str]:
    """Splits one paragraph that is longer than `size` on word boundaries."""
    pieces: list[str] = []
    current = ""
    for word in paragraph.split():
        if current and len(current) + 1 + len(word) > size:
            pieces.append(current)
            current = word
        else:
            current = f"{current} {word}" if current else word
    if current:
        pieces.append(current)
    return pieces


def _tail(text: str, overlap: int) -> str:
    """The last ~`overlap` characters of `text`, starting at a word boundary."""
    if overlap == 0 or len(text) <= overlap:
        return text if overlap else ""
    tail = text[-overlap:]
    space = tail.find(" ")
    return tail[space + 1 :] if space != -1 else tail


def chunk_text(text: str, size: int, overlap: int) -> list[str]:
    """Splits text into chunks of about `size` characters for embedding.

    Paragraphs (separated by blank lines) are kept whole when they fit and packed together up to
    `size`. A paragraph longer than `size` is split on word boundaries. Each chunk after the first
    starts with the last ~`overlap` characters of the previous one, so a sentence cut at a
    boundary still appears whole in one of the two chunks.
    """
    paragraphs = [" ".join(p.split()) for p in re.split(r"\n\s*\n", text) if p.strip()]
    pieces = [
        piece for p in paragraphs for piece in (_split_long(p, size) if len(p) > size else [p])
    ]

    chunks: list[str] = []
    current = ""
    for piece in pieces:
        if current and len(current) + 2 + len(piece) > size:
            chunks.append(current)
            overlap_text = _tail(current, overlap)
            current = f"{overlap_text}\n\n{piece}" if overlap_text else piece
        else:
            current = f"{current}\n\n{piece}" if current else piece
    if current:
        chunks.append(current)
    return chunks
