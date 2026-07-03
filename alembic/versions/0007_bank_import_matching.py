"""Bank import + matching: invoice variable_symbol, tx match_status, SET NULL FKs

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-03
"""
from alembic import op
import sqlalchemy as sa

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── invoices.variable_symbol (the Czech "golden key" for bank matching) ──
    op.add_column(
        'invoices',
        sa.Column('variable_symbol', sa.String(20), nullable=True),
    )
    op.create_index('ix_invoices_vs', 'invoices', ['variable_symbol'])

    # Backfill: derive VS from the digits of the invoice number where possible.
    op.execute(
        r"""
        UPDATE invoices
        SET variable_symbol = LEFT(regexp_replace(invoice_number, '\D', '', 'g'), 20)
        WHERE variable_symbol IS NULL
          AND regexp_replace(invoice_number, '\D', '', 'g') <> ''
        """
    )

    # ── bank_transactions.match_status (drives the reconciliation UI filter) ──
    op.add_column(
        'bank_transactions',
        sa.Column(
            'match_status', sa.String(15),
            nullable=False, server_default='UNMATCHED',
        ),
    )
    # Reflect the boolean already carried by the stub rows.
    op.execute(
        "UPDATE bank_transactions SET match_status = 'MATCHED' WHERE is_reconciled = true"
    )

    # ── Recreate the match FKs with ON DELETE SET NULL ──
    # 0006 created these as plain FKs (Postgres default names). SET NULL lets an
    # invoice/journal entry be deleted or voided without orphan-FK failures and
    # keeps the test-suite invoice cleanup safe regardless of ordering.
    op.drop_constraint(
        'bank_transactions_matched_invoice_id_fkey', 'bank_transactions',
        type_='foreignkey',
    )
    op.drop_constraint(
        'bank_transactions_matched_journal_entry_id_fkey', 'bank_transactions',
        type_='foreignkey',
    )
    op.create_foreign_key(
        'fk_bank_tx_invoice', 'bank_transactions', 'invoices',
        ['matched_invoice_id'], ['id'], ondelete='SET NULL',
    )
    op.create_foreign_key(
        'fk_bank_tx_journal', 'bank_transactions', 'journal_entries',
        ['matched_journal_entry_id'], ['id'], ondelete='SET NULL',
    )
    op.create_index('ix_bank_tx_match_status', 'bank_transactions', ['match_status'])


def downgrade() -> None:
    op.drop_index('ix_bank_tx_match_status', table_name='bank_transactions')
    op.drop_constraint('fk_bank_tx_journal', 'bank_transactions', type_='foreignkey')
    op.drop_constraint('fk_bank_tx_invoice', 'bank_transactions', type_='foreignkey')
    op.create_foreign_key(
        'bank_transactions_matched_journal_entry_id_fkey', 'bank_transactions',
        'journal_entries', ['matched_journal_entry_id'], ['id'],
    )
    op.create_foreign_key(
        'bank_transactions_matched_invoice_id_fkey', 'bank_transactions',
        'invoices', ['matched_invoice_id'], ['id'],
    )
    op.drop_column('bank_transactions', 'match_status')

    op.drop_index('ix_invoices_vs', table_name='invoices')
    op.drop_column('invoices', 'variable_symbol')
