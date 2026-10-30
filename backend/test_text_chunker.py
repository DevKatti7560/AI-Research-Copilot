
from app.services.text_chunker import split_text


def test_empty_text():
    assert split_text("") == []


def test_short_text():
    text = "This is a research paper."
    assert split_text(text) == [text]


def test_chunk_size():
    text = "A" * 2000
    chunks = split_text(text, chunk_size=800, overlap=150)

    assert all(len(chunk) <= 800 for chunk in chunks)
    assert len(chunks) == 3


def test_chunk_overlap():
    text = "ABCDEFGHIJKLMNOPQRSTUVWXYZ" * 50
    chunks = split_text(text, chunk_size=800, overlap=150)

    assert chunks[0][-150:] == chunks[1][:150]


def test_invalid_parameters():
    try:
        split_text("Example text", chunk_size=100, overlap=100)
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError")
