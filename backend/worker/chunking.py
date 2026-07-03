def chunk_text(text: str, max_chars: int = 6000, overlap_chars: int = 400) -> list[str]:
    """Approximate token-budget chunking by character count (~4 chars/token
    heuristic) since DeepSeek's tokenizer isn't published. Adjacent chunks
    overlap by `overlap_chars` so summaries don't lose context at a hard
    cut boundary."""
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    start = 0
    step = max_chars - overlap_chars
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start += step
    return chunks
