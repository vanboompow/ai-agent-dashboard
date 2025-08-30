"""Initial comprehensive database schema

Revision ID: 001
Revises: 
Create Date: 2024-08-30 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create agents table
    op.create_table(
        'agents',
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('agent_name', sa.String(255), nullable=False),
        sa.Column('agent_type', sa.String(255), nullable=False),
        sa.Column('hostname', sa.String(255), nullable=False),
        sa.Column('version', sa.String(50), nullable=True),
        sa.Column('current_status', sa.Enum('idle', 'working', 'paused', 'error', 'offline', name='agentstatus'), nullable=False, default='idle'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('last_heartbeat', sa.TIMESTAMP(timezone=True), default=sa.func.now()),
        sa.Column('last_activity', sa.TIMESTAMP(timezone=True)),
        sa.Column('capabilities', sa.JSON, nullable=True),
        sa.Column('max_concurrent_tasks', sa.Integer, default=1),
        sa.Column('current_task_count', sa.Integer, default=0),
        sa.Column('total_tasks_completed', sa.Integer, default=0),
        sa.Column('total_tokens_processed', sa.Integer, default=0),
        sa.Column('total_processing_time_seconds', sa.Float, default=0.0),
        sa.Column('average_response_time_ms', sa.Float, nullable=True),
        sa.Column('cpu_usage_percent', sa.Float, nullable=True),
        sa.Column('memory_usage_mb', sa.Float, nullable=True),
        sa.Column('config', sa.JSON, nullable=True),
        sa.Column('metadata', sa.JSON, nullable=True),
        sa.Column('last_error', sa.Text, nullable=True),
        sa.Column('error_count', sa.Integer, default=0),
    )
    
    # Create agent indexes
    op.create_index('idx_agent_status_heartbeat', 'agents', ['current_status', 'last_heartbeat'])
    op.create_index('idx_agent_hostname', 'agents', ['hostname'])
    op.create_index('idx_agent_type', 'agents', ['agent_type'])
    op.create_index('idx_agent_last_activity', 'agents', ['last_activity'])
    
    # Create tasks table
    op.create_table(
        'tasks',
        sa.Column('task_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('parent_task_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tasks.task_id'), nullable=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('task_type', sa.Enum('text_processing', 'code_generation', 'data_analysis', 'web_scraping', 'api_call', 'file_processing', 'computation', name='tasktype'), nullable=False),
        sa.Column('sector', sa.String(100), nullable=True),
        sa.Column('status', sa.Enum('pending', 'assigned', 'running', 'paused', 'completed', 'failed', 'cancelled', 'retry', name='taskstatus'), nullable=False, default='pending'),
        sa.Column('priority', sa.Enum('critical', 'high', 'normal', 'low', name='taskpriority'), nullable=False, default='normal'),
        sa.Column('assigned_agent_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('agents.agent_id'), nullable=True),
        sa.Column('queue_name', sa.String(100), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('scheduled_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('started_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('completed_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('deadline', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('max_retries', sa.Integer, default=3),
        sa.Column('retry_count', sa.Integer, default=0),
        sa.Column('timeout_seconds', sa.Integer, nullable=True),
        sa.Column('input_data', sa.JSON, nullable=True),
        sa.Column('output_data', sa.JSON, nullable=True),
        sa.Column('progress_percent', sa.Integer, default=0),
        sa.Column('steps_completed', sa.Integer, default=0),
        sa.Column('total_steps', sa.Integer, nullable=True),
        sa.Column('token_usage', sa.BigInteger, default=0),
        sa.Column('estimated_cost_usd', sa.DECIMAL(10, 6), nullable=True),
        sa.Column('actual_cost_usd', sa.DECIMAL(10, 6), nullable=True),
        sa.Column('processing_time_seconds', sa.DECIMAL(10, 3), nullable=True),
        sa.Column('tokens_per_second', sa.DECIMAL(10, 2), nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('error_details', sa.JSON, nullable=True),
        sa.Column('config', sa.JSON, nullable=True),
        sa.Column('metadata', sa.JSON, nullable=True),
        sa.Column('tags', sa.JSON, nullable=True),
        sa.Column('created_by', sa.String(255), nullable=True),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # Create task indexes
    op.create_index('idx_task_status_created', 'tasks', ['status', 'created_at'])
    op.create_index('idx_task_agent_status', 'tasks', ['assigned_agent_id', 'status'])
    op.create_index('idx_task_priority_created', 'tasks', ['priority', 'created_at'])
    op.create_index('idx_task_type_sector', 'tasks', ['task_type', 'sector'])
    op.create_index('idx_task_queue', 'tasks', ['queue_name', 'status'])
    op.create_index('idx_task_parent', 'tasks', ['parent_task_id'])
    op.create_index('idx_task_scheduled', 'tasks', ['scheduled_at'])
    op.create_index('idx_task_deadline', 'tasks', ['deadline'])
    
    # Create task dependencies table
    op.create_table(
        'task_dependencies',
        sa.Column('task_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tasks.task_id'), primary_key=True),
        sa.Column('depends_on_task_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tasks.task_id'), primary_key=True),
    )
    op.create_index('idx_task_dependencies_task', 'task_dependencies', ['task_id'])
    op.create_index('idx_task_dependencies_depends', 'task_dependencies', ['depends_on_task_id'])
    
    # Create task_logs table
    op.create_table(
        'task_logs',
        sa.Column('log_id', sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tasks.task_id'), nullable=False),
        sa.Column('timestamp', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('log_level', sa.String(20), nullable=False),
        sa.Column('message', sa.Text, nullable=False),
        sa.Column('context', sa.JSON, nullable=True),
    )
    op.create_index('idx_task_log_task_timestamp', 'task_logs', ['task_id', 'timestamp'])
    op.create_index('idx_task_log_level_timestamp', 'task_logs', ['log_level', 'timestamp'])
    
    # Create task_templates table
    op.create_table(
        'task_templates',
        sa.Column('template_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False, unique=True),
        sa.Column('description', sa.Text),
        sa.Column('task_type', sa.Enum('text_processing', 'code_generation', 'data_analysis', 'web_scraping', 'api_call', 'file_processing', 'computation', name='tasktype'), nullable=False),
        sa.Column('default_priority', sa.Enum('critical', 'high', 'normal', 'low', name='taskpriority'), default='normal'),
        sa.Column('default_timeout_seconds', sa.Integer, nullable=True),
        sa.Column('default_max_retries', sa.Integer, default=3),
        sa.Column('input_schema', sa.JSON, nullable=True),
        sa.Column('default_config', sa.JSON, nullable=True),
        sa.Column('required_capabilities', sa.JSON, nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('created_by', sa.String(255), nullable=True),
        sa.Column('is_active', sa.Boolean, default=True),
    )
    
    # Create agent_metrics table
    op.create_table(
        'agent_metrics',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('timestamp', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('tasks_completed_count', sa.Integer, default=0),
        sa.Column('tokens_processed_count', sa.Integer, default=0),
        sa.Column('response_time_ms', sa.Float, nullable=True),
        sa.Column('throughput_tps', sa.Float, nullable=True),
        sa.Column('cpu_usage_percent', sa.Float, nullable=True),
        sa.Column('memory_usage_mb', sa.Float, nullable=True),
        sa.Column('estimated_cost_usd', sa.Float, nullable=True),
        sa.Column('custom_metrics', sa.JSON, nullable=True),
    )
    op.create_index('idx_agent_metrics_agent_timestamp', 'agent_metrics', ['agent_id', 'timestamp'])
    op.create_index('idx_agent_metrics_timestamp', 'agent_metrics', ['timestamp'])
    
    # Create system_metrics table
    op.create_table(
        'system_metrics',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('timestamp', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('active_agents_count', sa.Integer, default=0),
        sa.Column('idle_agents_count', sa.Integer, default=0),
        sa.Column('working_agents_count', sa.Integer, default=0),
        sa.Column('offline_agents_count', sa.Integer, default=0),
        sa.Column('error_agents_count', sa.Integer, default=0),
        sa.Column('pending_tasks_count', sa.Integer, default=0),
        sa.Column('running_tasks_count', sa.Integer, default=0),
        sa.Column('completed_tasks_count', sa.Integer, default=0),
        sa.Column('failed_tasks_count', sa.Integer, default=0),
        sa.Column('avg_response_time_ms', sa.Float, nullable=True),
        sa.Column('tokens_per_second', sa.Float, nullable=True),
        sa.Column('tasks_per_minute', sa.Float, nullable=True),
        sa.Column('avg_cpu_usage_percent', sa.Float, nullable=True),
        sa.Column('avg_memory_usage_mb', sa.Float, nullable=True),
        sa.Column('total_cost_usd', sa.Float, nullable=True),
        sa.Column('cost_per_token', sa.Float, nullable=True),
        sa.Column('hourly_burn_rate_usd', sa.Float, nullable=True),
        sa.Column('error_rate_percent', sa.Float, nullable=True),
        sa.Column('timeout_rate_percent', sa.Float, nullable=True),
        sa.Column('custom_metrics', sa.JSON, nullable=True),
    )
    op.create_index('idx_system_metrics_timestamp', 'system_metrics', ['timestamp'])
    
    # Create agent_performance_metrics table
    op.create_table(
        'agent_performance_metrics',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('agents.agent_id'), nullable=False),
        sa.Column('timestamp', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('tasks_completed', sa.Integer, default=0),
        sa.Column('tasks_failed', sa.Integer, default=0),
        sa.Column('avg_task_duration_seconds', sa.Float, nullable=True),
        sa.Column('tokens_processed', sa.BigInteger, default=0),
        sa.Column('tokens_per_second', sa.Float, nullable=True),
        sa.Column('avg_response_time_ms', sa.Float, nullable=True),
        sa.Column('min_response_time_ms', sa.Float, nullable=True),
        sa.Column('max_response_time_ms', sa.Float, nullable=True),
        sa.Column('p95_response_time_ms', sa.Float, nullable=True),
        sa.Column('success_rate_percent', sa.Float, nullable=True),
        sa.Column('retry_rate_percent', sa.Float, nullable=True),
        sa.Column('cpu_usage_percent', sa.Float, nullable=True),
        sa.Column('memory_usage_mb', sa.Float, nullable=True),
        sa.Column('cost_usd', sa.Float, nullable=True),
        sa.Column('cost_per_token', sa.Float, nullable=True),
    )
    op.create_index('idx_agent_perf_agent_timestamp', 'agent_performance_metrics', ['agent_id', 'timestamp'])
    op.create_index('idx_agent_perf_timestamp', 'agent_performance_metrics', ['timestamp'])
    
    # Create task_performance_metrics table
    op.create_table(
        'task_performance_metrics',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tasks.task_id'), nullable=False),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('agents.agent_id'), nullable=True),
        sa.Column('timestamp', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('queue_time_seconds', sa.Float, nullable=True),
        sa.Column('execution_time_seconds', sa.Float, nullable=True),
        sa.Column('total_time_seconds', sa.Float, nullable=True),
        sa.Column('tokens_processed', sa.BigInteger, nullable=True),
        sa.Column('tokens_per_second', sa.Float, nullable=True),
        sa.Column('completion_status', sa.String(50), nullable=True),
        sa.Column('retry_attempts', sa.Integer, default=0),
        sa.Column('cost_usd', sa.Float, nullable=True),
        sa.Column('error_type', sa.String(100), nullable=True),
        sa.Column('error_count', sa.Integer, default=0),
        sa.Column('custom_metrics', sa.JSON, nullable=True),
    )
    op.create_index('idx_task_perf_task_timestamp', 'task_performance_metrics', ['task_id', 'timestamp'])
    op.create_index('idx_task_perf_agent_timestamp', 'task_performance_metrics', ['agent_id', 'timestamp'])
    op.create_index('idx_task_perf_timestamp', 'task_performance_metrics', ['timestamp'])
    
    # Create cost_metrics table
    op.create_table(
        'cost_metrics',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('timestamp', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('entity_type', sa.Enum('system', 'agent', 'task', 'cost', 'performance', 'error', name='metrictype'), nullable=False),
        sa.Column('entity_id', sa.String(255), nullable=True),
        sa.Column('input_tokens', sa.BigInteger, default=0),
        sa.Column('output_tokens', sa.BigInteger, default=0),
        sa.Column('total_tokens', sa.BigInteger, default=0),
        sa.Column('input_cost_per_token', sa.Float, nullable=True),
        sa.Column('output_cost_per_token', sa.Float, nullable=True),
        sa.Column('input_cost_usd', sa.Float, nullable=True),
        sa.Column('output_cost_usd', sa.Float, nullable=True),
        sa.Column('total_cost_usd', sa.Float, nullable=True),
        sa.Column('compute_cost_usd', sa.Float, nullable=True),
        sa.Column('storage_cost_usd', sa.Float, nullable=True),
        sa.Column('bandwidth_cost_usd', sa.Float, nullable=True),
        sa.Column('model_name', sa.String(100), nullable=True),
        sa.Column('provider', sa.String(50), nullable=True),
        sa.Column('metadata', sa.JSON, nullable=True),
    )
    op.create_index('idx_cost_entity_timestamp', 'cost_metrics', ['entity_type', 'entity_id', 'timestamp'])
    op.create_index('idx_cost_timestamp', 'cost_metrics', ['timestamp'])
    op.create_index('idx_cost_model_timestamp', 'cost_metrics', ['model_name', 'timestamp'])
    
    # Create alert_metrics table
    op.create_table(
        'alert_metrics',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('timestamp', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('alert_type', sa.String(100), nullable=False),
        sa.Column('severity', sa.String(20), nullable=False),
        sa.Column('entity_type', sa.Enum('system', 'agent', 'task', 'cost', 'performance', 'error', name='metrictype'), nullable=True),
        sa.Column('entity_id', sa.String(255), nullable=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('message', sa.String(1000), nullable=False),
        sa.Column('threshold_value', sa.Float, nullable=True),
        sa.Column('actual_value', sa.Float, nullable=True),
        sa.Column('is_acknowledged', sa.Integer, default=0),
        sa.Column('acknowledged_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('acknowledged_by', sa.String(255), nullable=True),
        sa.Column('is_resolved', sa.Integer, default=0),
        sa.Column('resolved_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('resolution_notes', sa.String(1000), nullable=True),
        sa.Column('metadata', sa.JSON, nullable=True),
    )
    op.create_index('idx_alert_type_severity', 'alert_metrics', ['alert_type', 'severity'])
    op.create_index('idx_alert_timestamp', 'alert_metrics', ['timestamp'])
    op.create_index('idx_alert_unresolved', 'alert_metrics', ['is_resolved', 'timestamp'])
    op.create_index('idx_alert_entity', 'alert_metrics', ['entity_type', 'entity_id'])
    
    # Create system_logs table
    op.create_table(
        'system_logs',
        sa.Column('id', sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column('timestamp', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('level', sa.Enum('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL', name='loglevel'), nullable=False),
        sa.Column('category', sa.Enum('system', 'agent', 'task', 'api', 'security', 'performance', 'error', 'audit', name='logcategory'), nullable=False),
        sa.Column('message', sa.Text, nullable=False),
        sa.Column('source', sa.String(100), nullable=True),
        sa.Column('request_id', sa.String(100), nullable=True),
        sa.Column('session_id', sa.String(100), nullable=True),
        sa.Column('user_id', sa.String(100), nullable=True),
        sa.Column('context', sa.JSON, nullable=True),
        sa.Column('error_code', sa.String(50), nullable=True),
        sa.Column('stack_trace', sa.Text, nullable=True),
        sa.Column('duration_ms', sa.Integer, nullable=True),
        sa.Column('hostname', sa.String(255), nullable=True),
        sa.Column('process_id', sa.Integer, nullable=True),
        sa.Column('thread_id', sa.String(50), nullable=True),
    )
    op.create_index('idx_system_log_timestamp', 'system_logs', ['timestamp'])
    op.create_index('idx_system_log_timestamp_level', 'system_logs', ['timestamp', 'level'])
    op.create_index('idx_system_log_category_timestamp', 'system_logs', ['category', 'timestamp'])
    op.create_index('idx_system_log_source_timestamp', 'system_logs', ['source', 'timestamp'])
    op.create_index('idx_system_log_error_code', 'system_logs', ['error_code'])
    op.create_index('idx_system_log_request_id', 'system_logs', ['request_id'])
    
    # Create agent_logs table
    op.create_table(
        'agent_logs',
        sa.Column('id', sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column('timestamp', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('agents.agent_id'), nullable=False),
        sa.Column('level', sa.Enum('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL', name='loglevel'), nullable=False),
        sa.Column('category', sa.Enum('system', 'agent', 'task', 'api', 'security', 'performance', 'error', 'audit', name='logcategory'), nullable=False),
        sa.Column('message', sa.Text, nullable=False),
        sa.Column('event_type', sa.String(100), nullable=True),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tasks.task_id'), nullable=True),
        sa.Column('context', sa.JSON, nullable=True),
        sa.Column('cpu_usage_percent', sa.Integer, nullable=True),
        sa.Column('memory_usage_mb', sa.Integer, nullable=True),
        sa.Column('response_time_ms', sa.Integer, nullable=True),
        sa.Column('error_code', sa.String(50), nullable=True),
        sa.Column('error_details', sa.JSON, nullable=True),
    )
    op.create_index('idx_agent_log_agent_timestamp', 'agent_logs', ['agent_id', 'timestamp'])
    op.create_index('idx_agent_log_task_timestamp', 'agent_logs', ['task_id', 'timestamp'])
    op.create_index('idx_agent_log_level_timestamp', 'agent_logs', ['level', 'timestamp'])
    op.create_index('idx_agent_log_event_type', 'agent_logs', ['event_type'])
    op.create_index('idx_agent_log_category_timestamp', 'agent_logs', ['category', 'timestamp'])


def downgrade() -> None:
    # Drop all tables in reverse order
    op.drop_table('agent_logs')
    op.drop_table('system_logs')
    op.drop_table('alert_metrics')
    op.drop_table('cost_metrics')
    op.drop_table('task_performance_metrics')
    op.drop_table('agent_performance_metrics')
    op.drop_table('system_metrics')
    op.drop_table('agent_metrics')
    op.drop_table('task_templates')
    op.drop_table('task_logs')
    op.drop_table('task_dependencies')
    op.drop_table('tasks')
    op.drop_table('agents')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS metrictype')
    op.execute('DROP TYPE IF EXISTS logcategory')
    op.execute('DROP TYPE IF EXISTS loglevel')
    op.execute('DROP TYPE IF EXISTS tasktype')
    op.execute('DROP TYPE IF EXISTS taskstatus')
    op.execute('DROP TYPE IF EXISTS taskpriority')
    op.execute('DROP TYPE IF EXISTS agentstatus')