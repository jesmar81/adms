"""Corporate group, companies, sites, people and employments foundation."""

from __future__ import annotations

from alembic import op

revision = "0004_corporate_hr_foundation"
down_revision = "0003_security_push"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
CREATE TABLE corporate_groups (
id UUID PRIMARY KEY,
name VARCHAR(150) NOT NULL,
code VARCHAR(50) NOT NULL,
active BOOLEAN NOT NULL DEFAULT true,
created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
CONSTRAINT uq_corporate_groups_code UNIQUE (code)
)
        """
    )
    op.execute(
        """
CREATE TABLE companies (
id UUID PRIMARY KEY,
corporate_group_id UUID NOT NULL,
legal_name VARCHAR(255) NOT NULL,
trade_name VARCHAR(255) NULL,
tax_id VARCHAR(13) NULL,
employer_registration VARCHAR(32) NULL,
timezone VARCHAR(64) NOT NULL DEFAULT 'America/Mexico_City',
active BOOLEAN NOT NULL DEFAULT true,
created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
CONSTRAINT fk_companies_corporate_group_id FOREIGN KEY (corporate_group_id) REFERENCES corporate_groups(id) ON DELETE RESTRICT,
CONSTRAINT uq_companies_group_legal_name UNIQUE (corporate_group_id, legal_name)
)
        """
    )
    op.execute("CREATE INDEX ix_companies_group ON companies(corporate_group_id)")
    op.execute(
        """
CREATE TABLE sites (
id UUID PRIMARY KEY,
company_id UUID NOT NULL,
name VARCHAR(150) NOT NULL,
code VARCHAR(50) NOT NULL,
timezone VARCHAR(64) NOT NULL DEFAULT 'America/Mexico_City',
address TEXT NULL,
active BOOLEAN NOT NULL DEFAULT true,
created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
CONSTRAINT fk_sites_company_id FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE RESTRICT,
CONSTRAINT uq_sites_company_code UNIQUE (company_id, code)
)
        """
    )
    op.execute("CREATE INDEX ix_sites_company ON sites(company_id)")
    op.execute(
        """
CREATE TABLE people (
id UUID PRIMARY KEY,
corporate_group_id UUID NOT NULL,
first_name VARCHAR(100) NOT NULL,
last_name VARCHAR(100) NOT NULL,
second_last_name VARCHAR(100) NULL,
preferred_name VARCHAR(150) NULL,
email VARCHAR(255) NULL,
phone VARCHAR(32) NULL,
active BOOLEAN NOT NULL DEFAULT true,
created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
CONSTRAINT fk_people_corporate_group_id FOREIGN KEY (corporate_group_id) REFERENCES corporate_groups(id) ON DELETE RESTRICT
)
        """
    )
    op.execute("CREATE INDEX ix_people_group ON people(corporate_group_id)")
    op.execute(
        """
CREATE TABLE employments (
id UUID PRIMARY KEY,
person_id UUID NOT NULL,
company_id UUID NOT NULL,
employee_number VARCHAR(64) NOT NULL,
position VARCHAR(150) NULL,
department VARCHAR(150) NULL,
cost_center VARCHAR(100) NULL,
manager_person_id UUID NULL,
contract_type VARCHAR(80) NULL,
started_on DATE NOT NULL,
ended_on DATE NULL,
active BOOLEAN NOT NULL DEFAULT true,
created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
CONSTRAINT fk_employments_person_id FOREIGN KEY (person_id) REFERENCES people(id) ON DELETE RESTRICT,
CONSTRAINT fk_employments_company_id FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE RESTRICT,
CONSTRAINT fk_employments_manager_person_id FOREIGN KEY (manager_person_id) REFERENCES people(id) ON DELETE SET NULL,
CONSTRAINT uq_employments_company_number UNIQUE (company_id, employee_number)
)
        """
    )
    op.execute("CREATE INDEX ix_employments_person ON employments(person_id)")
    op.execute("CREATE INDEX ix_employments_company ON employments(company_id)")
    op.execute("ALTER TABLE devices ADD COLUMN site_id UUID NULL")
    op.execute(
        "ALTER TABLE devices ADD CONSTRAINT fk_devices_site_id FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE SET NULL"
    )
    op.execute("ALTER TABLE device_users ADD COLUMN person_id UUID NULL")
    op.execute(
        "ALTER TABLE device_users ADD CONSTRAINT fk_device_users_person_id FOREIGN KEY (person_id) REFERENCES people(id) ON DELETE SET NULL"
    )
    op.execute("CREATE INDEX ix_device_users_person ON device_users(person_id)")
    op.execute(
        """
CREATE TABLE work_schedules (
id UUID PRIMARY KEY,
company_id UUID NOT NULL,
name VARCHAR(150) NOT NULL,
timezone VARCHAR(64) NOT NULL,
version INTEGER NOT NULL DEFAULT 1,
active BOOLEAN NOT NULL DEFAULT true,
created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
CONSTRAINT fk_work_schedules_company_id FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE RESTRICT,
CONSTRAINT uq_work_schedules_company_name_version UNIQUE (company_id, name, version)
)
        """
    )
    op.execute("CREATE INDEX ix_work_schedules_company ON work_schedules(company_id)")
    op.execute(
        """
CREATE TABLE schedule_slots (
id UUID PRIMARY KEY,
work_schedule_id UUID NOT NULL,
day_of_week INTEGER NOT NULL,
kind VARCHAR(20) NOT NULL,
sequence INTEGER NOT NULL DEFAULT 1,
expected_at TIME NOT NULL,
window_start TIME NULL,
window_end TIME NULL,
tolerance_minutes INTEGER NOT NULL DEFAULT 0,
required BOOLEAN NOT NULL DEFAULT true,
created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
CONSTRAINT fk_schedule_slots_work_schedule_id FOREIGN KEY (work_schedule_id) REFERENCES work_schedules(id) ON DELETE CASCADE,
CONSTRAINT ck_schedule_slots_day_of_week CHECK (day_of_week BETWEEN 0 AND 6),
CONSTRAINT ck_schedule_slots_kind CHECK (kind IN ('entry','meal_out','meal_in','exit')),
CONSTRAINT ck_schedule_slots_tolerance CHECK (tolerance_minutes >= 0),
CONSTRAINT uq_schedule_slots_position UNIQUE (work_schedule_id, day_of_week, kind, sequence)
)
        """
    )
    op.execute("CREATE INDEX ix_schedule_slots_schedule ON schedule_slots(work_schedule_id)")
    op.execute(
        """
CREATE TABLE schedule_assignments (
id UUID PRIMARY KEY,
employment_id UUID NOT NULL,
work_schedule_id UUID NOT NULL,
effective_from DATE NOT NULL,
effective_to DATE NULL,
active BOOLEAN NOT NULL DEFAULT true,
created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
CONSTRAINT fk_schedule_assignments_employment_id FOREIGN KEY (employment_id) REFERENCES employments(id) ON DELETE RESTRICT,
CONSTRAINT fk_schedule_assignments_work_schedule_id FOREIGN KEY (work_schedule_id) REFERENCES work_schedules(id) ON DELETE RESTRICT,
CONSTRAINT ck_schedule_assignments_date_range CHECK (effective_to IS NULL OR effective_to >= effective_from)
)
        """
    )
    op.execute(
        "CREATE INDEX ix_schedule_assignments_employment ON schedule_assignments(employment_id)"
    )
    op.execute(
        """
CREATE TABLE enrollment_requests (
id UUID PRIMARY KEY,
employment_id UUID NOT NULL,
device_id UUID NOT NULL,
methods JSONB NOT NULL DEFAULT '{}',
status VARCHAR(32) NOT NULL DEFAULT 'requested',
requested_by UUID NULL,
approved_by UUID NULL,
completed_by UUID NULL,
note TEXT NULL,
created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
CONSTRAINT fk_enrollment_requests_employment_id FOREIGN KEY (employment_id) REFERENCES employments(id) ON DELETE RESTRICT,
CONSTRAINT fk_enrollment_requests_device_id FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE RESTRICT,
CONSTRAINT fk_enrollment_requests_requested_by FOREIGN KEY (requested_by) REFERENCES users(id) ON DELETE SET NULL,
CONSTRAINT fk_enrollment_requests_approved_by FOREIGN KEY (approved_by) REFERENCES users(id) ON DELETE SET NULL,
CONSTRAINT fk_enrollment_requests_completed_by FOREIGN KEY (completed_by) REFERENCES users(id) ON DELETE SET NULL,
CONSTRAINT ck_enrollment_requests_status CHECK (status IN ('requested','approved','awaiting_device_enrollment','verification_pending','completed','rejected','revoked'))
)
        """
    )
    op.execute(
        "CREATE INDEX ix_enrollment_requests_employment ON enrollment_requests(employment_id)"
    )
    op.execute("CREATE INDEX ix_enrollment_requests_device ON enrollment_requests(device_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS enrollment_requests")
    op.execute("DROP TABLE IF EXISTS schedule_assignments")
    op.execute("DROP TABLE IF EXISTS schedule_slots")
    op.execute("DROP TABLE IF EXISTS work_schedules")
    op.execute("DROP INDEX IF EXISTS ix_device_users_person")
    op.execute("ALTER TABLE device_users DROP CONSTRAINT IF EXISTS fk_device_users_person_id")
    op.execute("ALTER TABLE device_users DROP COLUMN IF EXISTS person_id")
    op.execute("ALTER TABLE devices DROP CONSTRAINT IF EXISTS fk_devices_site_id")
    op.execute("ALTER TABLE devices DROP COLUMN IF EXISTS site_id")
    op.execute("DROP TABLE IF EXISTS employments")
    op.execute("DROP TABLE IF EXISTS people")
    op.execute("DROP TABLE IF EXISTS sites")
    op.execute("DROP TABLE IF EXISTS companies")
    op.execute("DROP TABLE IF EXISTS corporate_groups")
