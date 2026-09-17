"""Prevent more than one current schedule for the same employment."""

from __future__ import annotations

from alembic import op

revision = "0007_one_current_schedule_per_employment"
down_revision = "0006_hr_employment_confidential"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE UNIQUE INDEX uq_schedule_assignments_one_current_employment "
        "ON schedule_assignments (employment_id) "
        "WHERE active IS TRUE AND effective_to IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_schedule_assignments_one_current_employment")
