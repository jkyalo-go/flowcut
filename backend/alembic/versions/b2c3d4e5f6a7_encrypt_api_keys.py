"""Encrypt API keys at rest on ai_provider_credentials and ai_provider_configs

Revision ID: b2c3d4e5f6a7
Revises: 09a827a95767
Create Date: 2026-04-18 23:10:00.000000

Adds api_key_enc LargeBinary columns to both tables. Writes go there
(AES-GCM sealed). The legacy plaintext api_key columns become nullable
so new rows can skip them. A future migration after this is widely
deployed will drop the plaintext columns.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "09a827a95767"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ai_provider_credentials",
        sa.Column("api_key_enc", sa.LargeBinary(), nullable=True),
    )
    op.add_column(
        "ai_provider_configs",
        sa.Column("api_key_enc", sa.LargeBinary(), nullable=True),
    )
    # Relax the NOT NULL on the legacy plaintext column so new rows can
    # insert without it. Uses batch mode for SQLite compatibility.
    with op.batch_alter_table("ai_provider_credentials") as batch_op:
        batch_op.alter_column("api_key", existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("ai_provider_credentials") as batch_op:
        batch_op.alter_column("api_key", existing_type=sa.String(), nullable=False)
    op.drop_column("ai_provider_configs", "api_key_enc")
    op.drop_column("ai_provider_credentials", "api_key_enc")
