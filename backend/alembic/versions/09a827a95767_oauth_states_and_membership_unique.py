"""oauth_states and membership unique constraint

Revision ID: 09a827a95767
Revises: 14a7b9398bb7
Create Date: 2026-04-18 22:47:50.464463

Adds:
- oauth_states table for PKCE code_verifier persistence across OAuth handshake
- projects.autonomy_confidence_threshold (was drifted into the model without a migration)
- users.password_hash (was drifted into the model without a migration)
- UNIQUE(workspace_id, user_id) on memberships for idempotent invitation accept

Note: the autogen initially proposed dropping three indexes from the prior
migration. Those are legitimate indexes declared in 14a7b9398bb7.upgrade()
via op.create_index(), not in the model __table_args__ — the detection
is a known false positive. We keep them.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "09a827a95767"
down_revision: Union[str, Sequence[str], None] = "14a7b9398bb7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "oauth_states",
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("code_verifier", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
        sa.PrimaryKeyConstraint("state"),
    )

    op.add_column("projects", sa.Column("autonomy_confidence_threshold", sa.Float(), nullable=True))
    op.add_column("users", sa.Column("password_hash", sa.String(), nullable=True))

    with op.batch_alter_table("memberships") as batch_op:
        batch_op.create_unique_constraint(
            "uq_memberships_workspace_user",
            ["workspace_id", "user_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("memberships") as batch_op:
        batch_op.drop_constraint("uq_memberships_workspace_user", type_="unique")
    op.drop_column("users", "password_hash")
    op.drop_column("projects", "autonomy_confidence_threshold")
    op.drop_table("oauth_states")
