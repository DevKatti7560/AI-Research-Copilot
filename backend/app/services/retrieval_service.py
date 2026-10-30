
import re

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models.chunk import DocumentChunk
from app.models.document import Document
from app.services.embedding_service import generate_embedding


STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by",
    "does", "for", "from", "how", "in", "into", "is",
    "it", "of", "on", "or", "that", "the", "their",
    "this", "to", "what", "when", "where", "which",
    "who", "why", "with", "about", "paper", "explain",
    "describe", "discuss", "tell", "me", "please",
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

PROBLEM_QUESTION_TERMS = {
    "problem", "problems", "challenge", "challenges",
    "motivation", "objective", "objectives", "purpose",
    "gap", "gaps", "address", "addresses", "research",
}

METHOD_QUESTION_TERMS = {
    "method", "methods", "methodology", "approach",
    "algorithm", "algorithms", "technique", "techniques",
    "implementation", "model", "pipeline", "extract",
    "extraction", "construct", "constructing",
}

RESULT_QUESTION_TERMS = {
    "result", "results", "finding", "findings",
    "accuracy", "performance", "evaluation",
    "experiment", "experiments", "dataset", "datasets",
}

LIMITATION_QUESTION_TERMS = {
    "limitation", "limitations", "weakness", "weaknesses",
    "drawback", "drawbacks", "shortcoming", "shortcomings",
}

METHOD_QUESTION_PHRASES = (
    "how does",
    "how do",
    "how is",
    "how are",
    "how did",
    "what method",
    "which method",
    "methodology",
    "proposed approach",
    "spaCy",
    "spacy",
    "feature extraction",
    "entity extraction",
    "relation extraction",
)

PROBLEM_QUESTION_PHRASES = (
    "research problem",
    "problem does",
    "problem addressed",
    "research gap",
    "why was",
    "why did",
)

CONTRIBUTION_QUESTION_PHRASES = (
    "contribution",
    "contributions",
    "main contribution",
    "key contribution",
    "what does the paper propose",
    "what does the paper contribute",
)

METHOD_CONTENT_TERMS = {
    "methodology", "algorithm", "approach", "pipeline",
    "spacy", "tokenization", "lemmatization",
    "tagging", "parser", "parsing", "ner",
    "entity", "entities", "relation", "relations",
    "extract", "extraction", "ngac", "neo4j",
    "obligation", "obligations", "prohibition",
    "prohibitions", "association", "associations",
    "assignment", "assignments",
}


def _keywords(text: str) -> set[str]:
    """Extract useful terms for lightweight lexical matching."""
    words = re.findall(r"\b[a-zA-Z0-9-]+\b", text.lower())

    return {
        word
        for word in words
        if len(word) > 2 and word not in STOP_WORDS
    }


def _looks_like_references(text: str) -> bool:
    """Identify chunks likely dominated by bibliographic information."""
    lowered = text.lower()

    marker_count = sum(
        lowered.count(marker)
        for marker in REFERENCE_MARKERS
    )

    year_citations = len(
        re.findall(r"\b(?:19|20)\d{2}\b", text)
    )

    return marker_count >= 2 or (
        marker_count >= 1 and year_citations >= 3
    )


def _question_intent(question: str) -> str:
    """Classify the question, prioritizing explicit question wording."""
    lowered = question.lower()
    words = _keywords(question)

    if any(
        phrase in lowered
        for phrase in CONTRIBUTION_QUESTION_PHRASES
    ):
        return "contribution"

    if (
        words & LIMITATION_QUESTION_TERMS
        or "future work" in lowered
        or "future research" in lowered
    ):
        return "limitations"

    if any(
        phrase in lowered
        for phrase in METHOD_QUESTION_PHRASES
    ):
        return "methods"

    if words & METHOD_QUESTION_TERMS:
        return "methods"

    if words & RESULT_QUESTION_TERMS:
        return "results"

    if (
        words & PROBLEM_QUESTION_TERMS
        or any(
            phrase in lowered
            for phrase in PROBLEM_QUESTION_PHRASES
        )
    ):
        return "problem"

    return "general"


def _section_boost(
    question: str,
    intent: str,
    chunk_index: int,
    text: str,
) -> float:
    """Adjust ranking using question intent and passage content."""
    lowered = text.lower()
    boost = 0.0

    if intent in {"problem", "contribution"}:
        if chunk_index == 1:
            boost += 0.12
        elif 2 <= chunk_index <= 6:
            boost += 0.06

        problem_phrases = (
            "we focus on",
            "our work focuses",
            "this paper addresses",
            "the problem",
            "research problem",
            "the challenge",
            "research gap",
            "we propose",
            "we aim to",
            "contribution",
        )

        if any(phrase in lowered for phrase in problem_phrases):
            boost += 0.08

        if "abstract" in lowered:
            boost += 0.04

    elif intent == "methods":
        passage_keywords = _keywords(text)
        question_keywords = _keywords(question)

        overlap = len(question_keywords & passage_keywords)

        method_phrases = (
            "we propose",
            "our approach",
            "we use",
            "we develop",
            "methodology",
            "algorithm",
            "implementation",
            "spaCy",
            "dependency parsing",
            "named entity recognition",
            "entity extraction",
            "relation extraction",
        )

        if any(phrase in lowered for phrase in method_phrases):
            boost += 0.06

        if overlap:
            boost += min(overlap * 0.015, 0.09)

        if any(term in lowered for term in METHOD_CONTENT_TERMS):
            boost += 0.03

    elif intent == "results":
        result_phrases = (
            "experimental results",
            "our results",
            "evaluation results",
            "we demonstrate",
            "we show",
            "accuracy",
            "performance",
            "f1",
            "precision",
            "recall",
            "completeness",
            "minimality",
        )

        if any(phrase in lowered for phrase in result_phrases):
            boost += 0.08

    elif intent == "limitations":
        limitation_phrases = (
            "limitation",
            "limitations",
            "future work",
            "further research",
            "future research",
            "limited to",
            "synthetic data",
        )

        if any(phrase in lowered for phrase in limitation_phrases):
            boost += 0.10

    return boost


def _fetch_intro_chunks(
    db: Session,
    user_id: int,
    limit: int = 7,
) -> list:
    """Fetch early chunks from documents belonging to this user."""
    statement = (
        select(
            DocumentChunk.id,
            DocumentChunk.document_id,
            DocumentChunk.chunk_index,
            DocumentChunk.text,
            Document.filename,
            DocumentChunk.embedding.cosine_distance(
                [0.0] * 384
            ).label("distance"),
        )
        .join(
            Document,
            Document.id == DocumentChunk.document_id,
        )
        .where(
            Document.user_id == user_id,
            DocumentChunk.chunk_index <= limit,
            DocumentChunk.embedding.is_not(None),
        )
        .order_by(
            DocumentChunk.document_id,
            DocumentChunk.chunk_index,
        )
    )

    # This helper is not used for retrieval because ranking must use
    # the actual question embedding. Kept out of the retrieval path.
    return db.execute(statement).all()


def _get_intro_chunks(
    db: Session,
    user_id: int,
    query_embedding: list[float],
    limit: int = 7,
) -> list:
    """Fetch early chunks ranked against the actual query embedding."""
    distance = DocumentChunk.embedding.cosine_distance(
        query_embedding
    )

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
            DocumentChunk.chunk_index <= limit,
            DocumentChunk.embedding.is_not(None),
        )
    )

    return db.execute(statement).all()


def _get_neighbor_chunks(
    db: Session,
    user_id: int,
    seed_rows: list,
    query_embedding: list[float],
    window: int = 1,
) -> list:
    """Fetch adjacent chunks from the same user's documents."""
    if not seed_rows:
        return []

    targets = {
        (row.document_id, row.chunk_index + offset)
        for row in seed_rows
        for offset in range(-window, window + 1)
        if row.chunk_index + offset >= 0
    }

    if not targets:
        return []

    conditions = [
        and_(
            DocumentChunk.document_id == document_id,
            DocumentChunk.chunk_index == chunk_index,
        )
        for document_id, chunk_index in targets
    ]

    distance = DocumentChunk.embedding.cosine_distance(
        query_embedding
    )

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
            or_(*conditions),
        )
    )

    return db.execute(statement).all()


def retrieve_relevant_chunks(
    db: Session,
    user_id: int,
    question: str,
    top_k: int = 5,
) -> list[dict]:
    """
    Retrieve and rerank research passages using semantic similarity,
    lexical overlap, question intent, and adjacent context.
    """

    if not question or not question.strip():
        raise ValueError("Question cannot be empty.")

    if top_k < 1:
        raise ValueError("top_k must be greater than zero.")

    query_embedding = generate_embedding(question)
    query_keywords = _keywords(question)
    intent = _question_intent(question)

    distance = DocumentChunk.embedding.cosine_distance(
        query_embedding
    )

    candidate_limit = min(max(top_k * 12, 60), 200)

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

    rows = list(db.execute(statement).all())

    # Include the opening passages for questions about the research
    # problem or the paper's contribution.
    if intent in {"problem", "contribution"}:
        intro_rows = _get_intro_chunks(
            db=db,
            user_id=user_id,
            query_embedding=query_embedding,
        )

        existing_ids = {row.id for row in rows}

        rows.extend(
            row for row in intro_rows
            if row.id not in existing_ids
        )

    # Methodology explanations often need adjacent passages because
    # a chunk can end in the middle of a sentence or procedure.
    if intent == "methods":
        seed_rows = rows[:5]

        neighbor_rows = _get_neighbor_chunks(
            db=db,
            user_id=user_id,
            seed_rows=seed_rows,
            query_embedding=query_embedding,
            window=1,
        )

        existing_ids = {row.id for row in rows}

        rows.extend(
            row for row in neighbor_rows
            if row.id not in existing_ids
        )

    ranked_results = []

    for row in rows:
        text = row.text or ""

        if not text.strip():
            continue

        similarity = round(1 - float(row.distance), 4)
        chunk_keywords = _keywords(text)

        if query_keywords:
            keyword_overlap = (
                len(query_keywords & chunk_keywords)
                / len(query_keywords)
            )
        else:
            keyword_overlap = 0.0

        score = similarity + min(
            keyword_overlap * 0.12,
            0.12,
        )

        score += _section_boost(
            question=question,
            intent=intent,
            chunk_index=row.chunk_index,
            text=text,
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

    ranked_results.sort(
        key=lambda item: item["_score"],
        reverse=True,
    )

    substantive_results = [
        result
        for result in ranked_results
        if not result["_is_reference"]
    ]

    selected = []
    seen_texts = set()

    # Avoid duplicate passages, including duplicate document uploads.
    for result in substantive_results:
        normalized_text = " ".join(
            result["text"].lower().split()
        )

        if normalized_text in seen_texts:
            continue

        selected.append(result)
        seen_texts.add(normalized_text)

        if len(selected) >= top_k:
            break

    # Fall back to the highest-ranked remaining passages when needed.
    if len(selected) < top_k:
        for result in ranked_results:
            normalized_text = " ".join(
                result["text"].lower().split()
            )

            if normalized_text in seen_texts:
                continue

            selected.append(result)
            seen_texts.add(normalized_text)

            if len(selected) >= top_k:
                break

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
