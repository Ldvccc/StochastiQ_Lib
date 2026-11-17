"""Problèmes du client (distributions cibles)

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-08 05:02:56.533228
"""

from alembic import op
import sqlalchemy as sa


revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('problems',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('n_qubits', sa.Integer(), nullable=False),
    sa.Column('origin', sa.String(length=20), nullable=False),
    sa.Column('probabilities', sa.JSON(), nullable=False),
    sa.Column('source_params', sa.JSON(), nullable=False),
    sa.Column('features', sa.JSON(), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('problems', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_problems_project_id'), ['project_id'], unique=False)



def downgrade() -> None:
    with op.batch_alter_table('problems', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_problems_project_id'))

    op.drop_table('problems')
