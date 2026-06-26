"""Filing records table

Revision ID: 0005
Revises: 0004
Create Date: 2024-01-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('filing_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('filing_type', sa.String(20), nullable=False),
        sa.Column('period_label', sa.String(10), nullable=False),
        sa.Column('status', sa.String(15), nullable=False, server_default='draft'),
        sa.Column('reconciliation_passed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('reconciliation_detail', sa.Text(), nullable=True),
        sa.Column('file_path', sa.String(500), nullable=True),
        sa.Column('file_checksum_sha256', sa.String(64), nullable=True),
        sa.Column('deadline_date', sa.Date(), nullable=True),
        sa.Column('generated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('generated_by', sa.String(100), nullable=True),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('amends_filing_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
        sa.ForeignKeyConstraint(['amends_filing_id'], ['filing_records.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_filing_type_period', 'filing_records', ['filing_type', 'period_label'])
    op.create_index('ix_filing_status', 'filing_records', ['status'])
    op.execute("""
        CREATE UNIQUE INDEX uq_filing_type_period_active
        ON filing_records (company_id, filing_type, period_label)
        WHERE amends_filing_id IS NULL AND status != 'superseded';
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_filing_type_period_active")
    op.drop_table('filing_records')
