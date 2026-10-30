
from pathlib import Path
from uuid import uuid4
import io

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.models.document import Document
from app.models.user import User
from app.models.chunk import DocumentChunk
from app.services.text_chunker import split_text
from app.services.embedding_service import generate_embeddings


router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
)

# Project backend directory
BACKEND_DIR = Path(__file__).resolve().parents[2]
UPLOAD_DIR = BACKEND_DIR / "uploads"

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_EXTRACTED_CHARACTERS = 2_000_000


@router.post("/upload", status_code=status.HTTP_201_CREATED)
def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A filename is required.",
        )

    if Path(file.filename).suffix.lower() != ".pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported.",
        )

    saved_path = None

    try:
        file_bytes = file.file.read(MAX_FILE_SIZE + 1)

        if not file_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded file is empty.",
            )

        if len(file_bytes) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="The PDF must be 10 MB or smaller.",
            )

        try:
            reader = PdfReader(io.BytesIO(file_bytes), strict=True)

            if reader.is_encrypted:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Password-protected PDFs are not supported.",
                )

            extracted_parts = []

            for page in reader.pages:
                extracted_parts.append(page.extract_text() or "")

                if sum(map(len, extracted_parts)) > MAX_EXTRACTED_CHARACTERS:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="The extracted PDF text exceeds the allowed limit.",
                    )

            extracted_text = "\n\n".join(extracted_parts).strip()

            if not extracted_text:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "No extractable text was found. "
                        "Scanned PDFs will need OCR support."
                    ),
                )

        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded file is not a valid, readable PDF.",
            ) from exc

        user_upload_dir = UPLOAD_DIR / str(current_user.id)
        user_upload_dir.mkdir(parents=True, exist_ok=True)

        stored_filename = f"{uuid4().hex}.pdf"
        saved_path = user_upload_dir / stored_filename

        with saved_path.open("wb") as output_file:
            output_file.write(file_bytes)

        document = Document(
            user_id=current_user.id,
            filename=file.filename,
            title=Path(file.filename).stem,
            file_path=str(saved_path.relative_to(BACKEND_DIR)),
            status="processed",
            extracted_text=extracted_text,
        )

        db.add(document)
        db.commit()
        db.refresh(document)

        return {
            "message": "PDF uploaded and text extracted successfully.",
            "document": {
                "id": document.id,
                "filename": document.filename,
                "title": document.title,
                "status": document.status,
                "text_characters": len(extracted_text),
                "created_at": document.created_at,
            },
        }

    except HTTPException:
        raise

    except Exception as exc:
        db.rollback()

        if saved_path and saved_path.exists():
            saved_path.unlink()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The document could not be saved.",
        ) from exc

    finally:
        file.file.close()


@router.get("/")
def list_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    documents = (
        db.query(Document)
        .filter(Document.user_id == current_user.id)
        .order_by(Document.created_at.desc())
        .all()
    )

    return {
        "documents": [
            {
                "id": document.id,
                "filename": document.filename,
                "title": document.title,
                "status": document.status,
                "text_characters": len(document.extracted_text or ""),
                "created_at": document.created_at,
            }
            for document in documents
        ],
        "total": len(documents),
    }


@router.get("/{document_id}/chunks")
def preview_document_chunks(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.user_id == current_user.id,
        )
        .first()
    )

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    chunks = split_text(
        document.extracted_text or "",
        chunk_size=800,
        overlap=150,
    )

    return {
        "document_id": document.id,
        "filename": document.filename,
        "total_chunks": len(chunks),
        "chunk_size": 800,
        "overlap": 150,
        "chunks_preview": [
            {
                "chunk_index": index,
                "text": chunk[:300],
                "characters": len(chunk),
            }
            for index, chunk in enumerate(chunks[:5])
        ],
    }


@router.post("/{document_id}/process")
def process_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.user_id == current_user.id,
        )
        .first()
    )

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    if not document.extracted_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No extracted text is available for this document.",
        )

    # Retrieve existing chunks without recreating them.
    existing_chunk_rows = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document.id)
        .order_by(DocumentChunk.chunk_index)
        .all()
    )

    if existing_chunk_rows:
        # Only generate embeddings for chunks that are missing them.
        missing_embedding_rows = [
            chunk
            for chunk in existing_chunk_rows
            if chunk.embedding is None
        ]

        if not missing_embedding_rows:
            return {
                "message": "Document chunks and embeddings already exist.",
                "document_id": document.id,
                "total_chunks": len(existing_chunk_rows),
                "embeddings_generated": 0,
                "created": False,
            }

        try:
            missing_texts = [
                chunk.text for chunk in missing_embedding_rows
            ]

            embeddings = generate_embeddings(missing_texts)

            if len(embeddings) != len(missing_embedding_rows):
                raise ValueError(
                    "Embedding count does not match the number of chunks."
                )

            for chunk, embedding in zip(
                missing_embedding_rows, embeddings
            ):
                chunk.embedding = embedding

            db.commit()

            return {
                "message": "Missing embeddings generated successfully.",
                "document_id": document.id,
                "total_chunks": len(existing_chunk_rows),
                "embeddings_generated": len(embeddings),
                "created": False,
            }

        except Exception as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate missing embeddings.",
            ) from exc

    # No existing chunks: split the extracted document text.
    chunks = split_text(
        document.extracted_text,
        chunk_size=800,
        overlap=150,
    )

    if not chunks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No text chunks could be generated.",
        )

    try:
        embeddings = generate_embeddings(chunks)

        if len(embeddings) != len(chunks):
            raise ValueError(
                "Embedding count does not match the number of chunks."
            )

        db.add_all(
            [
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=index,
                    text=chunk,
                    embedding=embedding,
                )
                for index, (chunk, embedding) in enumerate(
                    zip(chunks, embeddings)
                )
            ]
        )

        db.commit()

    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save document chunks and embeddings.",
        ) from exc

    return {
        "message": "Document chunks and embeddings saved successfully.",
        "document_id": document.id,
        "total_chunks": len(chunks),
        "embeddings_generated": len(embeddings),
        "created": True,
    }