"""Initial schema: all entities.

Conventions (H-03/L-02): one statement per op.execute() (asyncpg rejects
multi-command strings); every UNIQUE/FK/CHECK explicitly named to match
SQLAlchemy metadata so `alembic check` is drift-free.
"""

from __future__ import annotations

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
CREATE TABLE users (
id UUID PRIMARY KEY,
username VARCHAR(100) NOT NULL,
email VARCHAR(255) NOT NULL,
password_hash TEXT NOT NULL,
first_name VARCHAR(100),
last_name VARCHAR(100),
is_active BOOLEAN NOT NULL DEFAULT true,
is_superuser BOOLEAN NOT NULL DEFAULT false,
last_login_at TIMESTAMPTZ NULL,
created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
CONSTRAINT uq_users_username UNIQUE (username),
CONSTRAINT uq_users_email UNIQUE (email)
)
        """
    )
    op.execute(
        """
CREATE TABLE roles (
id UUID PRIMARY KEY,
name VARCHAR(50) NOT NULL,
description TEXT,
created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
CONSTRAINT uq_roles_name UNIQUE (name)
)
        """
    )
    op.execute(
        """
CREATE TABLE permissions (
id UUID PRIMARY KEY,
code VARCHAR(100) NOT NULL,
description TEXT,
created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
CONSTRAINT uq_permissions_code UNIQUE (code)
)
        """
    )
    op.execute(
        """
CREATE TABLE user_roles (
user_id UUID NOT NULL,
role_id UUID NOT NULL,
CONSTRAINT fk_user_roles_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
CONSTRAINT fk_user_roles_role_id FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
PRIMARY KEY (user_id, role_id)
)
        """
    )
    op.execute(
        """
CREATE TABLE role_permissions (
role_id UUID NOT NULL,
permission_id UUID NOT NULL,
CONSTRAINT fk_role_permissions_role_id FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
CONSTRAINT fk_role_permissions_permission_id FOREIGN KEY (permission_id) REFERENCES permissions(id) ON DELETE CASCADE,
PRIMARY KEY (role_id, permission_id)
)
        """
    )
    op.execute(
        """
CREATE TABLE devices (
id UUID PRIMARY KEY,
serial_number VARCHAR(64) NOT NULL,
name VARCHAR(150) NULL,
model VARCHAR(100) NULL,
manufacturer VARCHAR(100) NOT NULL DEFAULT 'ZKTeco',
firmware_version VARCHAR(100) NULL,
platform VARCHAR(100) NULL,
push_protocol VARCHAR(50) NULL,
mac_address VARCHAR(50) NULL,
ip_address INET NULL,
port INTEGER NULL,
timezone VARCHAR(64) NOT NULL DEFAULT 'UTC',
last_activity_at TIMESTAMPTZ NULL,
registered_at TIMESTAMPTZ NULL,
last_registry_at TIMESTAMPTZ NULL,
last_cdata_at TIMESTAMPTZ NULL,
last_command_poll_at TIMESTAMPTZ NULL,
last_command_result_at TIMESTAMPTZ NULL,
status VARCHAR(20) NOT NULL DEFAULT 'unknown',
options JSONB NOT NULL DEFAULT '{}',
last_registry_payload JSONB NULL,
last_device_info JSONB NULL,
metadata JSONB NOT NULL DEFAULT '{}',
created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
CONSTRAINT uq_devices_serial_number UNIQUE (serial_number),
CONSTRAINT ck_devices_status CHECK (status IN ('unknown','online','offline','stale','disabled'))
)
        """
    )
    op.execute(
        """
CREATE INDEX ix_devices_status ON devices(status)
        """
    )
    op.execute(
        """
CREATE INDEX ix_devices_last_activity ON devices(last_activity_at)
        """
    )
    op.execute(
        """
CREATE TABLE device_users (
id UUID PRIMARY KEY,
device_id UUID NOT NULL,
pin VARCHAR(64) NOT NULL,
name VARCHAR(255) NOT NULL DEFAULT '',
privilege INTEGER NOT NULL DEFAULT 0,
card_number VARCHAR(128) NULL,
device_password TEXT NULL,
enabled BOOLEAN NOT NULL DEFAULT true,
raw_data JSONB NOT NULL DEFAULT '{}',
last_synced_at TIMESTAMPTZ NULL,
created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
CONSTRAINT fk_device_users_device_id FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE,
CONSTRAINT uq_device_users_device_pin UNIQUE (device_id, pin)
)
        """
    )
    op.execute(
        """
CREATE INDEX ix_device_users_device ON device_users(device_id)
        """
    )
    op.execute(
        """
CREATE TABLE adms_payloads (
id UUID PRIMARY KEY,
device_id UUID NULL,
endpoint VARCHAR(50) NOT NULL,
data_type VARCHAR(50) NULL,
content_type VARCHAR(100) NULL,
headers JSONB NULL,
query_params JSONB NULL,
raw_body TEXT NULL,
body_hash VARCHAR(64) NOT NULL,
received_at TIMESTAMPTZ NOT NULL,
processing_status VARCHAR(30) NOT NULL DEFAULT 'received',
processed_at TIMESTAMPTZ NULL,
error_message TEXT NULL,
CONSTRAINT fk_adms_payloads_device_id FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE SET NULL
)
        """
    )
    op.execute(
        """
CREATE INDEX ix_payloads_device_received ON adms_payloads(device_id, received_at)
        """
    )
    op.execute(
        """
CREATE TABLE attendance_logs (
id UUID PRIMARY KEY,
device_id UUID NOT NULL,
device_user_id UUID NULL,
device_user_pin VARCHAR(64) NOT NULL,
recorded_at TIMESTAMPTZ NOT NULL,
device_timezone VARCHAR(64) NULL,
status SMALLINT NOT NULL DEFAULT 0,
verify_mode SMALLINT NOT NULL DEFAULT 0,
work_code VARCHAR(32) NULL,
raw_line TEXT NULL,
raw_payload_id UUID NULL,
source VARCHAR(30) NOT NULL DEFAULT 'adms',
received_at TIMESTAMPTZ NOT NULL,
created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
CONSTRAINT fk_attendance_logs_device_id FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE,
CONSTRAINT fk_attendance_logs_device_user_id FOREIGN KEY (device_user_id) REFERENCES device_users(id) ON DELETE SET NULL,
CONSTRAINT fk_attendance_logs_raw_payload_id FOREIGN KEY (raw_payload_id) REFERENCES adms_payloads(id) ON DELETE SET NULL,
CONSTRAINT uq_attendance_dedup UNIQUE (device_id, device_user_pin, recorded_at, status, verify_mode, work_code)
)
        """
    )
    op.execute(
        """
CREATE INDEX ix_attendance_device ON attendance_logs(device_id)
        """
    )
    op.execute(
        """
CREATE INDEX ix_attendance_pin ON attendance_logs(device_user_pin)
        """
    )
    op.execute(
        """
CREATE INDEX ix_attendance_recorded ON attendance_logs(recorded_at)
        """
    )
    op.execute(
        """
CREATE INDEX ix_attendance_device_recorded ON attendance_logs(device_id, recorded_at)
        """
    )
    op.execute(
        """
CREATE TABLE device_commands (
id UUID PRIMARY KEY,
device_id UUID NOT NULL,
protocol_command_id BIGINT NOT NULL,
command_type VARCHAR(50) NOT NULL,
command TEXT NOT NULL,
payload JSONB NULL,
status VARCHAR(30) NOT NULL DEFAULT 'pending',
return_code INTEGER NULL,
queued_at TIMESTAMPTZ NOT NULL,
sent_at TIMESTAMPTZ NULL,
confirmed_at TIMESTAMPTZ NULL,
expires_at TIMESTAMPTZ NULL,
attempt_count INTEGER NOT NULL DEFAULT 0,
last_attempt_at TIMESTAMPTZ NULL,
response TEXT NULL,
error_message TEXT NULL,
created_by UUID NULL,
created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
CONSTRAINT fk_device_commands_device_id FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE,
CONSTRAINT fk_device_commands_created_by FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
CONSTRAINT ck_cmd_status CHECK (status IN ('pending','sent','confirmed','failed','expired','cancelled')),
CONSTRAINT uq_cmd_device_proto UNIQUE (device_id, protocol_command_id)
)
        """
    )
    op.execute(
        """
CREATE INDEX ix_cmd_device ON device_commands(device_id)
        """
    )
    op.execute(
        """
CREATE INDEX ix_cmd_status ON device_commands(status)
        """
    )
    op.execute(
        """
CREATE TABLE device_events (
id UUID PRIMARY KEY,
device_id UUID NULL,
event_type VARCHAR(80) NOT NULL,
severity VARCHAR(20) NOT NULL DEFAULT 'info',
payload JSONB NOT NULL DEFAULT '{}',
created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
CONSTRAINT fk_device_events_device_id FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE SET NULL
)
        """
    )
    op.execute(
        """
CREATE INDEX ix_events_device ON device_events(device_id)
        """
    )
    op.execute(
        """
CREATE INDEX ix_events_type ON device_events(event_type)
        """
    )
    op.execute(
        """
CREATE INDEX ix_events_created ON device_events(created_at)
        """
    )
    op.execute(
        """
CREATE TABLE audit_logs (
id UUID PRIMARY KEY,
user_id UUID NULL,
action VARCHAR(100) NOT NULL,
resource_type VARCHAR(100) NULL,
resource_id UUID NULL,
device_id UUID NULL,
ip_address INET NULL,
user_agent TEXT NULL,
request_id VARCHAR(100) NULL,
metadata JSONB NOT NULL DEFAULT '{}',
created_at TIMESTAMPTZ NOT NULL,
CONSTRAINT fk_audit_logs_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
CONSTRAINT fk_audit_logs_device_id FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE SET NULL
)
        """
    )
    op.execute(
        """
CREATE INDEX ix_audit_user ON audit_logs(user_id)
        """
    )
    op.execute(
        """
CREATE INDEX ix_audit_device ON audit_logs(device_id)
        """
    )
    op.execute(
        """
CREATE INDEX ix_audit_created ON audit_logs(created_at)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS audit_logs")
    op.execute("DROP TABLE IF EXISTS device_events")
    op.execute("DROP TABLE IF EXISTS device_commands")
    op.execute("DROP TABLE IF EXISTS attendance_logs")
    op.execute("DROP TABLE IF EXISTS adms_payloads")
    op.execute("DROP TABLE IF EXISTS device_users")
    op.execute("DROP TABLE IF EXISTS devices")
    op.execute("DROP TABLE IF EXISTS role_permissions")
    op.execute("DROP TABLE IF EXISTS user_roles")
    op.execute("DROP TABLE IF EXISTS permissions")
    op.execute("DROP TABLE IF EXISTS roles")
    op.execute("DROP TABLE IF EXISTS users")
