from worker.chunking import chunk_text


def test_short_text_returns_single_chunk():
    text = "短文本"
    assert chunk_text(text, max_chars=6000) == [text]


def test_long_text_splits_into_multiple_chunks():
    text = "A" * 15000
    chunks = chunk_text(text, max_chars=6000, overlap_chars=400)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 6000


def test_chunks_overlap():
    text = "0123456789" * 1000  # 10000 chars
    chunks = chunk_text(text, max_chars=6000, overlap_chars=400)
    assert chunks[1][:400] == chunks[0][-400:]


def test_no_empty_chunks():
    text = "x" * 12001
    chunks = chunk_text(text, max_chars=6000, overlap_chars=400)
    assert all(len(c) > 0 for c in chunks)
