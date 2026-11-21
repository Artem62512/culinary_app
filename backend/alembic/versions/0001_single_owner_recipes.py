"""Attach legacy recipes to the single existing owner.

Revision ID: 0001_single_owner
Revises:
Create Date: 2026-11-17
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_single_owner"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    required = {"users", "recipes"}
    missing = required - tables
    if missing:
        raise RuntimeError(
            "Single-owner migration stopped: missing tables: " + ", ".join(sorted(missing))
        )

    users = bind.execute(sa.text("SELECT id FROM users ORDER BY id")).scalars().all()
    if len(users) != 1:
        raise RuntimeError(
            f"Expected exactly one owner in users, found {len(users)}. "
            "No recipe ownership changes were applied."
        )
    owner_id = users[0]

    recipe_columns = {column["name"] for column in inspector.get_columns("recipes")}
    if "user_id" not in recipe_columns:
        raise RuntimeError("Single-owner migration stopped: recipes.user_id does not exist")

    # Preserve recipe IDs, content and ingredient rows. Only fill missing ownership.
    bind.execute(
        sa.text("UPDATE recipes SET user_id = :owner_id WHERE user_id IS NULL"),
        {"owner_id": owner_id},
    )


def downgrade() -> None:
    # Ownership assignment is intentionally retained on downgrade. Reverting it
    # would erase ownership for recipes created after this migration.
    pass
