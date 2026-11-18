from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7f6a2d9c1b40"

# This follows the existing agent execution log migration.
down_revision: Union[str, Sequence[str], None] = "e1d6e9aa5b6a"

branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflow_events",

        sa.Column(
            "id",
            sa.String(length=36),
            primary_key=True,
            nullable=False
        ),

        sa.Column(
            "claim_id",
            sa.String(length=36),
            sa.ForeignKey("claims.id"),
            nullable=False
        ),

        sa.Column(
            "event_type",
            sa.String(),
            nullable=False
        ),

        sa.Column(
            "status",
            sa.String(),
            nullable=False,
            server_default="pending"
        ),

        sa.Column(
            "attempts",
            sa.Integer(),
            nullable=False,
            server_default="0"
        ),

        sa.Column(
            "claimed_at",
            sa.DateTime(timezone=True),
            nullable=True
        ),

        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True
        ),

        sa.Column(
            "last_error",
            sa.Text(),
            nullable=True
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False
        ),
    )

    op.create_index(
        "ix_workflow_events_claim_id",
        "workflow_events",
        ["claim_id"]
    )

    op.create_index(
        "ix_workflow_events_event_type",
        "workflow_events",
        ["event_type"]
    )

    op.create_index(
        "ix_workflow_events_status",
        "workflow_events",
        ["status"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_workflow_events_status",
        table_name="workflow_events"
    )

    op.drop_index(
        "ix_workflow_events_event_type",
        table_name="workflow_events"
    )

    op.drop_index(
        "ix_workflow_events_claim_id",
        table_name="workflow_events"
    )

    op.drop_table("workflow_events")