"""Initial Cloyst Schema Migration.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-11-23 18:50:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Nodes table
    op.create_table(
        'nodes',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('hostname', sa.String(), nullable=False),
        sa.Column('ip_address', sa.String(), nullable=False),
        sa.Column('status', sa.String(), default='online'),
        sa.Column('gpu_name', sa.String(), nullable=True),
        sa.Column('total_vram_mb', sa.Integer(), default=0),
        sa.Column('free_vram_mb', sa.Integer(), default=0),
        sa.Column('last_heartbeat', sa.DateTime(timezone=True), nullable=False),
    )

    # 2. Models table
    op.create_table(
        'models',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('artifact_path', sa.String(), nullable=False),
        sa.Column('min_vram_mb', sa.Integer(), nullable=False),
        sa.Column('min_disk_gb', sa.Float(), default=2.0),
        sa.Column('max_context_length', sa.Integer(), default=4096),
        sa.Column('engine_type', sa.String(), default='vllm'),
        sa.Column('quantization', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 3. Deployments table
    op.create_table(
        'deployments',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('model_id', sa.String(), sa.ForeignKey('models.id'), nullable=False),
        sa.Column('node_id', sa.String(), sa.ForeignKey('nodes.id'), nullable=False),
        sa.Column('status', sa.String(), default='pending'),
        sa.Column('port', sa.Integer(), default=8000),
        sa.Column('container_id', sa.String(), nullable=True),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 4. Projects table
    op.create_table(
        'projects',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('name', sa.String(), unique=True, nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 5. API Keys table
    op.create_table(
        'api_keys',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('key_hash', sa.String(), unique=True, index=True, nullable=False),
        sa.Column('prefix', sa.String(), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('project_id', sa.String(), sa.ForeignKey('projects.id'), nullable=True, index=True),
        sa.Column('role', sa.String(), default='inference'),
    )

    # 6. Audit Logs table (with cryptographic hash chain)
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('api_key_id', sa.String(), sa.ForeignKey('api_keys.id'), nullable=True, index=True),
        sa.Column('model_id', sa.String(), index=True, nullable=False),
        sa.Column('prompt_tokens', sa.Integer(), default=0),
        sa.Column('completion_tokens', sa.Integer(), default=0),
        sa.Column('total_tokens', sa.Integer(), default=0),
        sa.Column('latency_ms', sa.Float(), default=0.0),
        sa.Column('status_code', sa.Integer(), default=200),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), index=True, nullable=False),
        sa.Column('project_id', sa.String(), sa.ForeignKey('projects.id'), nullable=True, index=True),
        sa.Column('request_id', sa.String(), nullable=True, index=True),
        sa.Column('prev_record_hash', sa.String(), nullable=True),
        sa.Column('record_hash', sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_table('api_keys')
    op.drop_table('projects')
    op.drop_table('deployments')
    op.drop_table('models')
    op.drop_table('nodes')

