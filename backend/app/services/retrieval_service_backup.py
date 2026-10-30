
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chunk import DocumentChunk
from app.models.document import Document
from app.services.embedding_service import generate_embedding


STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "does",
    "for", "from", "how", "in", "into", "is", "it", "of",
    "on", "or", "that", "the", "their", "this", "to", "what",
    "when", "where", "which", "who", "why", "with",
}


REFERENCE_MARKERS = (
    "doi.org/",
    "isbn ",
    "in proceedings",
    "et al.",
    "accessed:",
    "arxiv.org/",
    "vol.",
    "pp.",
)


def _keywords(text: str) -> set[str]:
    """Extract useful words for lightweight lexical matching."""
    words = re.findall(r"\b[a-zA-Z0-9-]+\b", text.lower())

    return {
        word
        for word in words
        if len(word) > 2 and word not in STOP_WORDS
    }


def _looks_like_references(text: str) -> bool:
    """Identify chunks dominated by bibliographic information."""
    lowered = text.lower()

    marker_count = sum(
        lowered.count(marker)
        for marker in REFERENCE_MARKERS
    )

    year_citations = len(
        re.findall(r"\b(?:19|20)\d{2}\b", text)
    )

    # A single DOI or publication year is not enough to discard a passage.
    return marker_count >= 2 or (
        marker_count >= 1 and year_citations >= 3
    )


def retrieve_relevant_chunks(
    db: Session,
    user_id: int,
    question: str,
    top_k: int = 5,
) -> list[dict]:
    """Retrieve and rerank relevant chunks belonging to one user."""

    if not question or not question.strip():
        raise ValueError("Question cannot be empty.")

    if top_k < 1:
        raise ValueError("top_k must be greater than zero.")

    query_embedding = generate_embedding(question)
    query_keywords = _keywords(question)

    distance = DocumentChunk.embedding.cosine_distance(
        query_embedding
    )

    # Fetch more candidates than we intend to return.
    candidate_limit = min(max(top_k * 4, 20), 100)

    statement = (
        select(
            DocumentChunk.id,
            DocumentChunk.document_id,
            DocumentChunk.chunk_index,
            DocumentChunk.text,
            Document.filename,
            distance.label("distance"),
        )
        .join(
            Document,
            Document.id == DocumentChunk.document_id,
        )
        .where(
            Document.user_id == user_id,
            DocumentChunk.embedding.is_not(None),
        )
        .order_by(distance)
        .limit(candidate_limit)
    )

    rows = db.execute(statement).all()
    ranked_results = []

    for row in rows:
        similarity = round(1 - float(row.distance), 4)
        text = row.text or ""

        if not text.strip():
            continue

        chunk_keywords = _keywords(text)

        if query_keywords:
            keyword_overlap = (
                len(query_keywords & chunk_keywords)
                / len(query_keywords)
            )
        else:
            keyword_overlap = 0.0

        # Semantic similarity remains the main ranking signal.
        score = similarity + min(
            keyword_overlap * 0.12,
            0.12,
        )

        is_reference = _looks_like_references(text)

        if is_reference:
            score -= 0.25

        ranked_results.append(
            {
                "chunk_id": row.id,
                "document_id": row.document_id,
                "chunk_index": row.chunk_index,
                "filename": row.filename,
                "text": text,
                "similarity": similarity,
                "_score": score,
                "_is_reference": is_reference,
            }
        )

    # Prefer substantive passages over reference-list material.
    ranked_results.sort(
        key=lambda item: item["_score"],
        reverse=True,
    )

    # If enough substantive passages exist, leave references out.
    substantive_results = [
        result
        for result in ranked_results
        if not result["_is_reference"]
    ]

    selected = substantive_results[:top_k]

    # If too few substantive passages exist, fill remaining slots
    # with the best remaining candidates instead of returning nothing.
    if len(selected) < top_k:
        selected_ids = {
            result["chunk_id"]
            for result in selected
        }

        for result in ranked_results:
            if result["chunk_id"] not in selected_ids:
                selected.append(result)
                selected_ids.add(result["chunk_id"])

            if len(selected) >= top_k:
                break

    # Keep the public result format unchanged.
    return [
        {
            key: result[key]
            for key in (
                "chunk_id",
                "document_id",
                "chunk_index",
                "filename",
                "text",
                "similarity",
            )
        }
        for result in selected
    ]
