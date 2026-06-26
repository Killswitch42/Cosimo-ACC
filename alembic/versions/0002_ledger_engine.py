"""Ledger engine — journal_entries, journal_entry_lines, account_balances, fx_rates

Revision ID: 0002
Revises: 0001
Create Date: 2024-01-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "journal_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fiscal_period_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entry_number", sa.String(20), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column(
            "posting_date",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("entry_type", sa.String(15), nullable=False, server_default="STANDARD"),
        sa.Column("status", sa.String(10), nullable=False, server_default="draft"),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("source_type", sa.String(30), nullable=True),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reverses_entry_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="CZK"),
        sa.Column(
            "exchange_rate",
            sa.Numeric(15, 6),
            nullable=False,
            server_default="1.000000",
        ),
        sa.Column("posted_by", sa.String(100), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ai_classification_note", sa.Text(), nullable=True),
        sa.Column("ai_confidence_score", sa.Numeric(5, 4), nullable=True),
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
        sa.ForeignKeyConstraint(["fiscal_period_id"], ["fiscal_periods.id"]),
        sa.ForeignKeyConstraint(["reverses_entry_id"], ["journal_entries.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entry_number"),
    )
    op.create_index("ix_je_company_date", "journal_entries", ["company_id", "entry_date"])
    op.create_index(
        "ix_je_period_status", "journal_entries", ["fiscal_period_id", "status"]
    )
    op.create_index("ix_je_source", "journal_entries", ["source_type", "source_id"])

    op.create_table(
        "journal_entry_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_number", sa.String(10), nullable=False),
        sa.Column("side", sa.String(6), nullable=False),
        sa.Column("amount_foreign", sa.Numeric(18, 2), nullable=False),
        sa.Column("amount_czk", sa.Numeric(18, 2), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("cost_centre", sa.String(50), nullable=True),
        sa.Column("vat_rate", sa.Numeric(5, 2), nullable=True),
        sa.Column("line_order", sa.Integer(), nullable=False, server_default="0"),
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
        sa.ForeignKeyConstraint(["journal_entry_id"], ["journal_entries.id"]),
        sa.ForeignKeyConstraint(["account_number"], ["ledger_accounts.account_number"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_jel_entry_id", "journal_entry_lines", ["journal_entry_id"])
    op.create_index("ix_jel_account", "journal_entry_lines", ["account_number"])

    op.create_table(
        "account_balances",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fiscal_period_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_number", sa.String(10), nullable=False),
        sa.Column(
            "opening_balance_czk",
            sa.Numeric(18, 2),
            nullable=False,
            server_default="0.00",
        ),
        sa.Column(
            "period_debit_czk",
            sa.Numeric(18, 2),
            nullable=False,
            server_default="0.00",
        ),
        sa.Column(
            "period_credit_czk",
            sa.Numeric(18, 2),
            nullable=False,
            server_default="0.00",
        ),
        sa.Column(
            "closing_balance_czk",
            sa.Numeric(18, 2),
            nullable=False,
            server_default="0.00",
        ),
        sa.Column("entry_count", sa.Integer(), nullable=False, server_default="0"),
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
        sa.ForeignKeyConstraint(["fiscal_period_id"], ["fiscal_periods.id"]),
        sa.ForeignKeyConstraint(["account_number"], ["ledger_accounts.account_number"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "fiscal_period_id", "account_number", name="uq_balance_period_account"
        ),
    )
    op.create_index(
        "ix_ab_period_account", "account_balances", ["fiscal_period_id", "account_number"]
    )

    op.create_table(
        "fx_rates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("rate_date", sa.Date(), nullable=False),
        sa.Column("currency_code", sa.String(3), nullable=False),
        sa.Column("currency_name", sa.String(50), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("rate_czk", sa.Numeric(15, 6), nullable=False),
        sa.Column("unit_rate_czk", sa.Numeric(15, 6), nullable=False),
        sa.Column("source", sa.String(10), nullable=False, server_default="CNB"),
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
        sa.UniqueConstraint("rate_date", "currency_code", name="uq_fx_rate_date_currency"),
    )
    op.create_index("ix_fx_date", "fx_rates", ["rate_date"])

    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_posted_entry_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_TABLE_NAME = 'journal_entries' THEN
                IF OLD.status = 'posted'
                   AND NOT (
                       NEW.status = 'voided'
                       AND NEW.id = OLD.id
                       AND NEW.company_id = OLD.company_id
                       AND NEW.fiscal_period_id = OLD.fiscal_period_id
                       AND NEW.entry_number = OLD.entry_number
                       AND NEW.entry_date = OLD.entry_date
                       AND NEW.posting_date = OLD.posting_date
                       AND NEW.entry_type = OLD.entry_type
                       AND NEW.description = OLD.description
                       AND NEW.source_type IS NOT DISTINCT FROM OLD.source_type
                       AND NEW.source_id IS NOT DISTINCT FROM OLD.source_id
                       AND NEW.reverses_entry_id IS NOT DISTINCT FROM OLD.reverses_entry_id
                       AND NEW.currency = OLD.currency
                       AND NEW.exchange_rate = OLD.exchange_rate
                       AND NEW.posted_by IS NOT DISTINCT FROM OLD.posted_by
                       AND NEW.posted_at IS NOT DISTINCT FROM OLD.posted_at
                       AND NEW.ai_classification_note IS NOT DISTINCT FROM OLD.ai_classification_note
                       AND NEW.ai_confidence_score IS NOT DISTINCT FROM OLD.ai_confidence_score
                       AND NEW.created_at = OLD.created_at
                   ) THEN
                    RAISE EXCEPTION
                        'Czech zákon 563/1991 Sb. § 35: Posted journal entry % cannot be modified. Use opravný zápis.',
                        OLD.entry_number;
                END IF;
            END IF;

            IF TG_TABLE_NAME = 'journal_entry_lines' THEN
                IF EXISTS (
                    SELECT 1 FROM journal_entries
                    WHERE id = OLD.journal_entry_id AND status = 'posted'
                ) THEN
                    RAISE EXCEPTION
                        'Czech zákon 563/1991 Sb. § 35: Lines of posted entry cannot be modified. Use opravný zápis.';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_immutable_journal_entry
        BEFORE UPDATE ON journal_entries
        FOR EACH ROW EXECUTE FUNCTION prevent_posted_entry_modification();
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_immutable_journal_entry_lines
        BEFORE UPDATE ON journal_entry_lines
        FOR EACH ROW EXECUTE FUNCTION prevent_posted_entry_modification();
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_posted_entry_deletion()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_TABLE_NAME = 'journal_entries' THEN
                IF OLD.status = 'posted' THEN
                    RAISE EXCEPTION
                        'Czech zákon 563/1991 Sb. § 31: Posted journal entry % cannot be deleted. 10-year retention required.',
                        OLD.entry_number;
                END IF;
            END IF;
            RETURN OLD;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_no_delete_posted_entry
        BEFORE DELETE ON journal_entries
        FOR EACH ROW EXECUTE FUNCTION prevent_posted_entry_deletion();
        """
    )
    op.execute(
        """
        CREATE SEQUENCE IF NOT EXISTS journal_entry_seq
        START WITH 1 INCREMENT BY 1 NO CYCLE;
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_no_delete_posted_entry ON journal_entries")
    op.execute("DROP TRIGGER IF EXISTS trg_immutable_journal_entry ON journal_entries")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_immutable_journal_entry_lines ON journal_entry_lines"
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_posted_entry_modification()")
    op.execute("DROP FUNCTION IF EXISTS prevent_posted_entry_deletion()")
    op.execute("DROP SEQUENCE IF EXISTS journal_entry_seq")
    op.drop_index("ix_fx_date", table_name="fx_rates")
    op.drop_table("fx_rates")
    op.drop_index("ix_ab_period_account", table_name="account_balances")
    op.drop_table("account_balances")
    op.drop_index("ix_jel_account", table_name="journal_entry_lines")
    op.drop_index("ix_jel_entry_id", table_name="journal_entry_lines")
    op.drop_table("journal_entry_lines")
    op.drop_index("ix_je_source", table_name="journal_entries")
    op.drop_index("ix_je_period_status", table_name="journal_entries")
    op.drop_index("ix_je_company_date", table_name="journal_entries")
    op.drop_table("journal_entries")
