"""Initial schema — companies, fiscal_periods, ledger_accounts

Revision ID: 0001
Revises:
Create Date: 2024-01-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("ico", sa.String(8), nullable=True),
        sa.Column("dic", sa.String(12), nullable=True),
        sa.Column("registered_office", sa.String(500), nullable=True),
        sa.Column("legal_form", sa.String(50), nullable=False, server_default="s.r.o."),
        sa.Column(
            "fiscal_year_start_month",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column("is_vat_payer", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "vat_filing_period",
            sa.String(10),
            nullable=False,
            server_default="monthly",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ico"),
        sa.UniqueConstraint("dic"),
    )

    op.create_table(
        "fiscal_periods",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("label", sa.String(20), nullable=False),
        sa.Column(
            "period_type",
            sa.String(10),
            nullable=False,
            server_default="annual",
        ),
        sa.Column("date_start", sa.Date(), nullable=False),
        sa.Column("date_end", sa.Date(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="draft"),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fiscal_periods_company_id", "fiscal_periods", ["company_id"])
    op.create_index("ix_fiscal_periods_status", "fiscal_periods", ["status"])

    op.create_table(
        "ledger_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_number", sa.String(10), nullable=False),
        sa.Column("name_cz", sa.String(255), nullable=False),
        sa.Column("name_en", sa.String(255), nullable=True),
        sa.Column("account_class", sa.Integer(), nullable=False),
        sa.Column("balance_type", sa.String(8), nullable=False),
        sa.Column("account_type", sa.String(15), nullable=False),
        sa.Column("parent_account_number", sa.String(10), nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_analytical", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("allows_posting", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_vat_account", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("vat_rate", sa.Numeric(5, 2), nullable=True),
        sa.Column("report_line_rozvaha", sa.String(10), nullable=True),
        sa.Column("report_line_vzz", sa.String(10), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("notes", sa.String(1000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_number"),
    )
    op.create_index("ix_ledger_accounts_number", "ledger_accounts", ["account_number"])
    op.create_index("ix_ledger_accounts_class", "ledger_accounts", ["account_class"])
    op.create_index("ix_ledger_accounts_type", "ledger_accounts", ["account_type"])


def downgrade() -> None:
    op.drop_index("ix_ledger_accounts_type", table_name="ledger_accounts")
    op.drop_index("ix_ledger_accounts_class", table_name="ledger_accounts")
    op.drop_index("ix_ledger_accounts_number", table_name="ledger_accounts")
    op.drop_table("ledger_accounts")
    op.drop_index("ix_fiscal_periods_status", table_name="fiscal_periods")
    op.drop_index("ix_fiscal_periods_company_id", table_name="fiscal_periods")
    op.drop_table("fiscal_periods")
    op.drop_table("companies")
