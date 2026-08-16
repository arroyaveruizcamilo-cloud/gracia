"""add stock_released and guest_token

Revision ID: 9c1e2d3f4a5b
Revises: 742a6c73a94d
Create Date: 2026-08-15 20:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9c1e2d3f4a5b'
down_revision: Union[str, None] = '742a6c73a94d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('orders', sa.Column('stock_released', sa.Boolean(), nullable=True,
                                      server_default=sa.text('0')))
    op.add_column('conversations', sa.Column('guest_token', sa.String(length=128),
                                             nullable=True))


def downgrade() -> None:
    op.drop_column('conversations', 'guest_token')
    op.drop_column('orders', 'stock_released')
