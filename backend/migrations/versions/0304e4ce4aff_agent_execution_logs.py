"""agent execution logs

Revision ID: 0304e4ce4aff
Revises: c1d8c63adc00
Create Date: 2026-11-08 17:37:05.536583

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0304e4ce4aff'
down_revision: Union[str, Sequence[str], None] = 'c1d8c63adc00'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_execution_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("claim_id", sa.String(length=36), nullable=False),
        sa.Column("agent_name", sa.String(), nullable=False),
        sa.Column("agent_version", sa.String(), nullable=False),
        sa.Column("model_name", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("input_summary", sa.JSON(), nullable=False),
        sa.Column("output", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_execution_logs_run_id"), "agent_execution_logs", ["run_id"], unique=False)
    op.create_index(op.f("ix_agent_execution_logs_claim_id"), "agent_execution_logs", ["claim_id"], unique=False)
    op.create_index(op.f("ix_agent_execution_logs_agent_name"), "agent_execution_logs", ["agent_name"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_agent_execution_logs_agent_name"), table_name="agent_execution_logs")
    op.drop_index(op.f("ix_agent_execution_logs_claim_id"), table_name="agent_execution_logs")
    op.drop_index(op.f("ix_agent_execution_logs_run_id"), table_name="agent_execution_logs")
    op.drop_table("agent_execution_logs")
