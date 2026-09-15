"""Security PUSH registration/session state for access-control terminals."""

from __future__ import annotations

from alembic import op

revision = "0003_security_push"
down_revision = "0002_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE devices ADD COLUMN adms_registry_code VARCHAR(32) NULL")
    op.execute("ALTER TABLE devices ADD COLUMN adms_session_id VARCHAR(32) NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE devices DROP COLUMN adms_session_id")
    op.execute("ALTER TABLE devices DROP COLUMN adms_registry_code")
