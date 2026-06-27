"""Users and bank_transactions (stub) tables

Revision ID: 0006
Revises: 0005
Create Date: 2024-01-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('role', sa.String(15), nullable=False, server_default='accountant'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
    )
    op.create_index('ix_users_email', 'users', ['email'])
    op.create_index('ix_users_company', 'users', ['company_id'])

    op.create_table(
        'bank_transactions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('bank_account_number', sa.String(50), nullable=False),
        sa.Column('transaction_date', sa.Date(), nullable=False),
        sa.Column('amount_czk', sa.Numeric(18, 2), nullable=False),
        sa.Column('direction', sa.String(6), nullable=False),
        sa.Column('counterparty_name', sa.String(255), nullable=True),
        sa.Column('counterparty_account', sa.String(50), nullable=True),
        sa.Column('variable_symbol', sa.String(20), nullable=True),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('matched_invoice_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('matched_journal_entry_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_reconciled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('import_source', sa.String(30), nullable=False, server_default='MANUAL_CSV'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
        sa.ForeignKeyConstraint(['matched_invoice_id'], ['invoices.id']),
        sa.ForeignKeyConstraint(['matched_journal_entry_id'], ['journal_entries.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_bank_tx_date', 'bank_transactions', ['transaction_date'])
    op.create_index('ix_bank_tx_reconciled', 'bank_transactions', ['is_reconciled'])


def downgrade() -> None:
    op.drop_table('bank_transactions')
    op.drop_table('users')
