"""Ansatz personnalisés du client

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-08 05:39:09.840106
"""

from alembic import op
import sqlalchemy as sa


revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('custom_ansatz',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('format', sa.String(length=10), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('n_qubits', sa.Integer(), nullable=True),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('custom_ansatz', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_custom_ansatz_project_id'), ['project_id'], unique=False)



def downgrade() -> None:
    with op.batch_alter_table('custom_ansatz', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_custom_ansatz_project_id'))

    op.drop_table('custom_ansatz')
