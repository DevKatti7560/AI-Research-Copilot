
"""add chunk embeddings

Revision ID: 2e72b399880f
Revises: d7b40f13030a
Create Date: 2026-10-10 19:21:23.493357
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = "2e72b399880f"
down_revision: Union[str, Sequence[str], None] = "d7b40f13030a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add nullable embedding storage to document chunks."""
    op.add_column(
        "document_chunks",
        sa.Column("embedding", Vector(384), nullable=True),
    )


def downgrade() -> None:
    """Remove embedding storage from document chunks."""
    op.drop_column("document_chunks", "embedding")
