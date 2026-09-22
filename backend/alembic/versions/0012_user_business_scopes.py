"""Add row-level corporate group and company scopes to admin users."""

from __future__ import annotations

from alembic import op

revision = "0012_user_business_scopes"
down_revision = "0011_attendance_attribution"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
CREATE TABLE user_group_scopes (
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  corporate_group_id UUID NOT NULL REFERENCES corporate_groups(id) ON DELETE CASCADE,
  PRIMARY KEY (user_id, corporate_group_id)
)
        """
    )
    op.execute(
        """
CREATE TABLE user_company_scopes (
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  PRIMARY KEY (user_id, company_id)
)
        """
    )
    # Preserve current visibility during rollout. Administrators can narrow
    # these explicit scopes after migration; newly created users start with
    # only the scopes selected in the user form.
    op.execute(
        """
INSERT INTO user_group_scopes (user_id, corporate_group_id)
SELECT users.id, corporate_groups.id FROM users CROSS JOIN corporate_groups
ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS user_company_scopes")
    op.execute("DROP TABLE IF EXISTS user_group_scopes")
