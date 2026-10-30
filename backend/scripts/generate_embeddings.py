

import sys
from pathlib import Path

# Add the backend directory to Python's import path.
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.chunk import DocumentChunk
from app.services.embedding_service import generate_embeddings


BATCH_SIZE = 16


def main() -> None:
    total_updated = 0

    with SessionLocal() as db:
        while True:
            chunks = db.scalars(
                select(DocumentChunk)
                .where(DocumentChunk.embedding.is_(None))
                .order_by(DocumentChunk.id)
                .limit(BATCH_SIZE)
            ).all()

            if not chunks:
                break

            texts = [chunk.text for chunk in chunks]
            embeddings = generate_embeddings(texts)

            for chunk, embedding in zip(chunks, embeddings):
                chunk.embedding = embedding

            db.commit()
            total_updated += len(chunks)

            print(
                f"Generated embeddings for {total_updated} chunks "
                f"in this run."
            )

    print(f"Finished. Total chunks updated: {total_updated}")


if __name__ == "__main__":
    main()
