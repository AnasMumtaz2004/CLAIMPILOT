"""rag chunks and ocr status

Revision ID: c1d8c63adc00
Revises: d08ee39f7eb2
Create Date: 2026-11-07 13:34:17.710934

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1d8c63adc00'
down_revision: Union[str, Sequence[str], None] = 'd08ee39f7eb2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
