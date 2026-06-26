"""Invoice register and VAT register tables

Revision ID: 0003
Revises: 0002
Create Date: 2024-01-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("direction", sa.String(8), nullable=False),
        sa.Column("invoice_type", sa.String(15), nullable=False, server_default="STANDARD"),
        sa.Column("invoice_number", sa.String(50), nullable=False),
        sa.Column("internal_reference", sa.String(50), nullable=True),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("duzp", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("payment_date", sa.Date(), nullable=True),
        sa.Column("counterparty_name", sa.String(255), nullable=False),
        sa.Column("counterparty_ico", sa.String(8), nullable=True),
        sa.Column("counterparty_dic", sa.String(20), nullable=True),
        sa.Column("counterparty_address", sa.String(500), nullable=True),
        sa.Column("counterparty_country", sa.String(2), nullable=False, server_default="CZ"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="CZK"),
        sa.Column("exchange_rate", sa.Numeric(15, 6), nullable=False, server_default="1.000000"),
        sa.Column("total_net_foreign", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("total_vat_foreign", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("total_gross_foreign", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("total_net_czk", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("total_vat_czk", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("total_gross_czk", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("counterparty_is_vat_payer", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_reverse_charge", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_eu_supply", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("ares_validated", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("ares_validation_note", sa.String(500), nullable=True),
        sa.Column("status", sa.String(12), nullable=False, server_default="draft"),
        sa.Column("void_reason", sa.String(500), nullable=True),
        sa.Column("credits_invoice_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("document_path", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["credits_invoice_id"], ["invoices.id"]),
        sa.ForeignKeyConstraint(["journal_entry_id"], ["journal_entries.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_invoices_company_direction", "invoices", ["company_id", "direction"])
    op.create_index("ix_invoices_duzp", "invoices", ["duzp"])
    op.create_index("ix_invoices_status", "invoices", ["status"])
    op.create_index("ix_invoices_dic", "invoices", ["counterparty_dic"])
    op.create_index("ix_invoices_number", "invoices", ["invoice_number"])

    op.create_table(
        "invoice_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 4), nullable=False, server_default="1.0000"),
        sa.Column("unit", sa.String(20), nullable=True),
        sa.Column("unit_price_net", sa.Numeric(18, 4), nullable=False),
        sa.Column("vat_rate", sa.Numeric(5, 2), nullable=False, server_default="21.00"),
        sa.Column("line_net_czk", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("line_vat_czk", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("line_gross_czk", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("account_number", sa.String(10), nullable=True),
        sa.Column("cost_centre", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"]),
        sa.ForeignKeyConstraint(["account_number"], ["ledger_accounts.account_number"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_invoice_lines_invoice_id", "invoice_lines", ["invoice_id"])

    op.create_table(
        "vat_register",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vat_period", sa.String(7), nullable=False),
        sa.Column("direction", sa.String(8), nullable=False),
        sa.Column("invoice_number", sa.String(50), nullable=False),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("duzp", sa.Date(), nullable=False),
        sa.Column("counterparty_name", sa.String(255), nullable=False),
        sa.Column("counterparty_dic", sa.String(20), nullable=True),
        sa.Column("counterparty_country", sa.String(2), nullable=False, server_default="CZ"),
        sa.Column("vat_rate", sa.Numeric(5, 2), nullable=False),
        sa.Column("tax_base_czk", sa.Numeric(18, 2), nullable=False),
        sa.Column("tax_amount_czk", sa.Numeric(18, 2), nullable=False),
        sa.Column("kh_section", sa.String(3), nullable=False),
        sa.Column("kh_detail_required", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_reverse_charge", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_eu_supply", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("eu_supply_type", sa.Integer(), nullable=True),
        sa.Column("zdph_paragraph", sa.String(10), nullable=True),
        sa.Column("kh_submitted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("kh_submission_date", sa.Date(), nullable=True),
        sa.Column("priznani_submitted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("priznani_submission_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vat_period", "vat_register", ["company_id", "vat_period"])
    op.create_index("ix_vat_kh_section", "vat_register", ["kh_section", "kh_submitted"])
    op.create_index("ix_vat_direction", "vat_register", ["direction", "vat_period"])

    op.execute(
        """
        CREATE UNIQUE INDEX uq_received_invoice_dic_number
        ON invoices (company_id, counterparty_dic, invoice_number)
        WHERE direction = 'RECEIVED' AND status != 'voided';
        """
    )
    op.execute(
        """
        ALTER TABLE invoice_lines
        ADD CONSTRAINT ck_valid_vat_rate
        CHECK (vat_rate IN (0, 12, 21));
        """
    )
    op.execute(
        """
        ALTER TABLE vat_register
        ADD CONSTRAINT ck_vr_valid_vat_rate
        CHECK (vat_rate IN (0, 12, 21));
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_received_invoice_dic_number")
    op.drop_index("ix_vat_direction", table_name="vat_register")
    op.drop_index("ix_vat_kh_section", table_name="vat_register")
    op.drop_index("ix_vat_period", table_name="vat_register")
    op.drop_table("vat_register")
    op.drop_index("ix_invoice_lines_invoice_id", table_name="invoice_lines")
    op.drop_table("invoice_lines")
    op.drop_index("ix_invoices_number", table_name="invoices")
    op.drop_index("ix_invoices_dic", table_name="invoices")
    op.drop_index("ix_invoices_status", table_name="invoices")
    op.drop_index("ix_invoices_duzp", table_name="invoices")
    op.drop_index("ix_invoices_company_direction", table_name="invoices")
    op.drop_table("invoices")
