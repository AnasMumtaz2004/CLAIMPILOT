
"""rag chunks and ocr status

Revision ID: d08ee39f7eb2
Revises: f42d2f7cac3f
Create Date: 2026-11-07 13:00:30.694654

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector.sqlalchemy


# revision identifiers, used by Alembic.
revision: str = 'd08ee39f7eb2'
down_revision: Union[str, Sequence[str], None] = 'f42d2f7cac3f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # pgvector must be switched on before a vector column can be created
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "document_chunks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("document_type", sa.String(), nullable=False),
        sa.Column("insurance_domain", sa.String(), nullable=False),
        sa.Column("source_file", sa.String(), nullable=False),
        sa.Column("policy_number", sa.String(), nullable=True),
        sa.Column("product", sa.String(), nullable=True),
        sa.Column("version", sa.String(), nullable=True),
        sa.Column("effective_date", sa.String(), nullable=True),
        sa.Column("section_title", sa.String(), nullable=False),
        sa.Column("clause_number", sa.String(), nullable=True),
        sa.Column("clause_code", sa.String(), nullable=True),
        sa.Column("heading", sa.String(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("page_end", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(dim=384), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        op.f("ix_document_chunks_document_type"),
        "document_chunks",
        ["document_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_chunks_insurance_domain"),
        "document_chunks",
        ["insurance_domain"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_chunks_policy_number"),
        "document_chunks",
        ["policy_number"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_chunks_source_file"),
        "document_chunks",
        ["source_file"],
        unique=False,
    )

    # Existing documents are marked pending, because they were never read by OCR
    op.add_column(
        "claim_documents",
        sa.Column("ocr_status", sa.String(), server_default="pending", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("claim_documents", "ocr_status")
    op.drop_index(op.f("ix_document_chunks_source_file"), table_name="document_chunks")
    op.drop_index(op.f("ix_document_chunks_policy_number"), table_name="document_chunks")
    op.drop_index(op.f("ix_document_chunks_insurance_domain"), table_name="document_chunks")
    op.drop_index(op.f("ix_document_chunks_document_type"), table_name="document_chunks")
    op.drop_table("document_chunks")
