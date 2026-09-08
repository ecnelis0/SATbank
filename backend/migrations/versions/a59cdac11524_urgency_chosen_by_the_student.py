"""urgency chosen by the student

Revision ID: a59cdac11524
Revises: 5188c5e13f74
Create Date: 2026-09-08 00:18:25.886571

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# The models module defines custom column types (UtcDateTime) that autogenerate
# renders by their fully qualified name; without this import the migration is a
# NameError at run time.
import app.models


# revision identifiers, used by Alembic.
revision: str = "a59cdac11524"
down_revision: Union[str, Sequence[str], None] = "5188c5e13f74"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("mistakes", schema=None) as batch_op:
        # server_default, because the table already has rows and the column is NOT
        # NULL: without it this migration fails on any bank that is not empty.
        batch_op.add_column(
            sa.Column(
                "urgency_is_yours",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("mistakes", schema=None) as batch_op:
        batch_op.drop_column("urgency_is_yours")
