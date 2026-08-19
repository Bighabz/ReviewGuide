"""Create kv_cache / kv_zset / kv_list — the Postgres KV layer replacing Redis.

2026-08-18 Redis retirement: app.core.pg_kv.PostgresKV serves the redis-py
method surface from these three tables. Reads filter on expires_at; a scheduler
job (pg_kv.sweep_expired) deletes expired rows.

Revision ID: 20260818_0001
Revises: 20260222_0001
Create Date: 2026-08-18
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260818_0001'
down_revision: Union[str, None] = '20260222_0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'kv_cache',
        sa.Column('key', sa.Text(), primary_key=True),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_kv_cache_expires_at', 'kv_cache', ['expires_at'])

    op.create_table(
        'kv_zset',
        sa.Column('key', sa.Text(), primary_key=True),
        sa.Column('member', sa.Text(), primary_key=True),
        sa.Column('score', sa.Float(precision=53), nullable=False),
    )
    op.create_index('ix_kv_zset_key_score', 'kv_zset', ['key', 'score'])

    op.create_table(
        'kv_list',
        sa.Column('key', sa.Text(), primary_key=True),
        sa.Column('seq', sa.BigInteger(), sa.Identity(always=False),
                  primary_key=True),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index('ix_kv_list_expires_at', 'kv_list', ['expires_at'])


def downgrade() -> None:
    op.drop_index('ix_kv_list_expires_at', table_name='kv_list')
    op.drop_table('kv_list')
    op.drop_index('ix_kv_zset_key_score', table_name='kv_zset')
    op.drop_table('kv_zset')
    op.drop_index('ix_kv_cache_expires_at', table_name='kv_cache')
    op.drop_table('kv_cache')
