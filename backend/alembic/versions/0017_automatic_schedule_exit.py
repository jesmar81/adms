"""Allow schedules to synthesize the programmed end-of-shift mark."""

from alembic import op

revision = "0017_automatic_schedule_exit"
down_revision = "0016_sync_standard_rbac"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE work_schedules ADD COLUMN automatic_exit_enabled BOOLEAN NOT NULL DEFAULT FALSE"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE work_schedules DROP COLUMN automatic_exit_enabled")
