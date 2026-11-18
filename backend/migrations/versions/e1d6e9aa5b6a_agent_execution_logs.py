"""agent execution logs

Revision ID: e1d6e9aa5b6a
Revises: 0304e4ce4aff
Create Date: 2026-11-08 17:51:24.330036

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1d6e9aa5b6a'
down_revision: Union[str, Sequence[str], None] = '0304e4ce4aff'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
