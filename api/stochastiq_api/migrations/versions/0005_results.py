"""Base de résultats et partage des résultats d'un projet

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-08 07:56:17.959344
"""

from alembic import op
import sqlalchemy as sa


revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('results',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('source', sa.String(length=10), nullable=False),
    sa.Column('type', sa.String(length=20), nullable=False),
    sa.Column('config_key', sa.String(length=200), nullable=True),
    sa.Column('run_id', sa.Integer(), nullable=True),
    sa.Column('project_id', sa.Integer(), nullable=True),
    sa.Column('ansatz', sa.String(length=120), nullable=False),
    sa.Column('ansatz_fingerprint', sa.String(length=80), nullable=False),
    sa.Column('n_qubits', sa.Integer(), nullable=False),
    sa.Column('layers', sa.Integer(), nullable=False),
    sa.Column('circuit_features', sa.JSON(), nullable=False),
    sa.Column('problem_family', sa.String(length=40), nullable=True),
    sa.Column('problem_features', sa.JSON(), nullable=True),
    sa.Column('noise_profile', sa.JSON(), nullable=True),
    sa.Column('noise_topology', sa.String(length=10), nullable=True),
    sa.Column('quantities', sa.JSON(), nullable=False),
    sa.Column('library_version', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('config_key')
    )
    with op.batch_alter_table('results', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_results_ansatz_fingerprint'), ['ansatz_fingerprint'], unique=False)
        batch_op.create_index(batch_op.f('ix_results_project_id'), ['project_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_results_run_id'), ['run_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_results_source'), ['source'], unique=False)
        batch_op.create_index(batch_op.f('ix_results_type'), ['type'], unique=False)

    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.add_column(sa.Column('share_results', sa.Boolean(), server_default=sa.false(), nullable=False))



def downgrade() -> None:
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.drop_column('share_results')

    with op.batch_alter_table('results', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_results_type'))
        batch_op.drop_index(batch_op.f('ix_results_source'))
        batch_op.drop_index(batch_op.f('ix_results_run_id'))
        batch_op.drop_index(batch_op.f('ix_results_project_id'))
        batch_op.drop_index(batch_op.f('ix_results_ansatz_fingerprint'))

    op.drop_table('results')
