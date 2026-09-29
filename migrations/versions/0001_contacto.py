"""contact requests and status history"""
from alembic import op
import sqlalchemy as sa

revision = "0001_contacto"
down_revision = None
branch_labels = None
depends_on = None
contact_status = sa.Enum("NUEVA", "EN_REVISION", "RESPONDIDA", "CERRADA", name="contact_status")

def upgrade():
    contact_status.create(op.get_bind(), checkfirst=True)
    op.create_table("contact_requests", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("nombre", sa.String(120), nullable=False), sa.Column("email", sa.String(320), nullable=False), sa.Column("telefono", sa.String(30)), sa.Column("mensaje", sa.Text(), nullable=False), sa.Column("consentimiento_version", sa.String(40), nullable=False), sa.Column("consentimiento_at", sa.DateTime(timezone=True), nullable=False), sa.Column("status", contact_status, nullable=False, server_default="NUEVA"), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_contact_requests_status_created", "contact_requests", ["status", "created_at"])
    op.create_table("contact_status_history", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("request_id", sa.Integer(), sa.ForeignKey("contact_requests.id", ondelete="CASCADE"), nullable=False), sa.Column("from_status", contact_status), sa.Column("to_status", contact_status, nullable=False), sa.Column("changed_by_user_id", sa.Integer()), sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_contact_status_history_request", "contact_status_history", ["request_id", "changed_at"])

def downgrade():
    op.drop_index("ix_contact_status_history_request", table_name="contact_status_history")
    op.drop_table("contact_status_history")
    op.drop_index("ix_contact_requests_status_created", table_name="contact_requests")
    op.drop_table("contact_requests")
    contact_status.drop(op.get_bind(), checkfirst=True)
