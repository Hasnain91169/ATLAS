from atlas.tts.chunking import chunk_text


def test_chunk_text_respects_max_chars():
    text = ("a" * 2600) + "\n\n" + ("b" * 100)
    chunks = chunk_text(text, max_chars=2500)
    assert chunks
    assert all(len(c) <= 2500 for c in chunks)
