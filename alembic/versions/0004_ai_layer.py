"""AI layer — alerts, classification_logs, compliance_rules

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("category", sa.String(15), nullable=False),
        sa.Column("rule_code", sa.String(80), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("suggested_action", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(30), nullable=True),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deadline_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(15), nullable=False, server_default="open"),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.String(100), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("ai_generated", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("ai_confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_alerts_company_id", "alerts", ["company_id"])
    op.create_index("ix_alerts_severity", "alerts", ["severity"])
    op.create_index("ix_alerts_category", "alerts", ["category"])
    op.create_index("ix_alerts_rule_code", "alerts", ["rule_code"])
    op.create_index("ix_alerts_source_id", "alerts", ["source_id"])

    op.create_table(
        "classification_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("classification_type", sa.String(20), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("input_context", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("suggested_debit_account", sa.String(10), nullable=True),
        sa.Column("suggested_credit_account", sa.String(10), nullable=True),
        sa.Column("suggested_vat_rate", sa.Numeric(5, 2), nullable=True),
        sa.Column("suggested_cost_centre", sa.String(50), nullable=True),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("confidence_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("raw_response", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("was_accepted", sa.Boolean(), nullable=True),
        sa.Column("override_debit_account", sa.String(10), nullable=True),
        sa.Column("override_credit_account", sa.String(10), nullable=True),
        sa.Column("model_id", sa.String(50), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_classification_logs_company_id", "classification_logs", ["company_id"])
    op.create_index("ix_classification_logs_classification_type", "classification_logs", ["classification_type"])
    op.create_index("ix_classification_logs_source_id", "classification_logs", ["source_id"])

    op.create_table(
        "compliance_rules",
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name_cz", sa.String(255), nullable=False),
        sa.Column("name_en", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(15), nullable=False),
        sa.Column("default_severity", sa.String(10), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("code"),
    )
    op.create_index("ix_compliance_rules_category", "compliance_rules", ["category"])
    op.create_index("ix_compliance_rules_default_severity", "compliance_rules", ["default_severity"])


def downgrade() -> None:
    op.drop_index("ix_compliance_rules_default_severity", table_name="compliance_rules")
    op.drop_index("ix_compliance_rules_category", table_name="compliance_rules")
    op.drop_table("compliance_rules")
    op.drop_index("ix_classification_logs_source_id", table_name="classification_logs")
    op.drop_index("ix_classification_logs_classification_type", table_name="classification_logs")
    op.drop_index("ix_classification_logs_company_id", table_name="classification_logs")
    op.drop_table("classification_logs")
    op.drop_index("ix_alerts_source_id", table_name="alerts")
    op.drop_index("ix_alerts_rule_code", table_name="alerts")
    op.drop_index("ix_alerts_category", table_name="alerts")
    op.drop_index("ix_alerts_severity", table_name="alerts")
    op.drop_index("ix_alerts_company_id", table_name="alerts")
    op.drop_table("alerts")
