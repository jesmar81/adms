"""Device command counter + device-user sync lifecycle (M-03/M-08)."""

from __future__ import annotations

from alembic import op

revision = "0002_lifecycle"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE devices
        ADD COLUMN command_seq BIGINT NOT NULL DEFAULT 0
        """
    )
    op.execute(
        """
        ALTER TABLE device_users
        ADD COLUMN sync_state VARCHAR(20) NOT NULL DEFAULT 'synced'
        """
    )
    op.execute(
        """
        ALTER TABLE device_users
        ADD CONSTRAINT ck_device_users_sync_state
        CHECK (sync_state IN ('synced','pending','failed'))
        """
    )
    op.execute(
        """
        ALTER TABLE device_users
        ADD COLUMN pending_op JSONB NULL
        """
    )
    op.execute(
        """
        ALTER TABLE device_users
        ADD COLUMN last_protocol_command_id BIGINT NULL
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE device_users DROP COLUMN last_protocol_command_id")
    op.execute("ALTER TABLE device_users DROP COLUMN pending_op")
    op.execute("ALTER TABLE device_users DROP CONSTRAINT ck_device_users_sync_state")
    op.execute("ALTER TABLE device_users DROP COLUMN sync_state")
    op.execute("ALTER TABLE devices DROP COLUMN command_seq")
