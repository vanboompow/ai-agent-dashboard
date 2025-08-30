import pytest
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.exc import IntegrityError

from app.models.agent import Agent, AgentStatus
from app.models.task import Task, TaskPriority, TaskStatus, TaskLog, SystemMetric
from tests.conftest import create_test_agent, create_test_task


class TestAgentModel:
    """Test suite for Agent model."""
    
    def test_create_agent(self, db_session, sample_agent_data):
        """Test creating an agent."""
        agent = Agent(**sample_agent_data)
        db_session.add(agent)
        db_session.commit()
        
        assert agent.agent_id is not None
        assert isinstance(agent.agent_id, uuid.UUID)
        assert agent.agent_type == "test_agent"
        assert agent.hostname == "test-host"
        assert agent.current_status == AgentStatus.idle
    
    def test_agent_status_enum(self, db_session):
        """Test agent status enum values."""
        agent_data = {
            "agent_type": "test_agent",
            "hostname": "test-host",
            "current_status": AgentStatus.working
        }
        agent = Agent(**agent_data)
        db_session.add(agent)
        db_session.commit()
        
        assert agent.current_status == AgentStatus.working
        assert agent.current_status.value == "working"
    
    def test_agent_unique_id(self, db_session):
        """Test that agent IDs are unique."""
        agent1 = create_test_agent(db_session, agent_type="agent1")
        agent2 = create_test_agent(db_session, agent_type="agent2")
        
        assert agent1.agent_id != agent2.agent_id
    
    def test_agent_required_fields(self, db_session):
        """Test that required fields are enforced."""
        with pytest.raises(IntegrityError):
            agent = Agent(agent_type=None, hostname="test-host", current_status=AgentStatus.idle)
            db_session.add(agent)
            db_session.commit()
    
    def test_agent_heartbeat_update(self, db_session):
        """Test updating agent heartbeat."""
        agent = create_test_agent(db_session)
        heartbeat_time = datetime.now(timezone.utc)
        
        agent.last_heartbeat = heartbeat_time
        db_session.commit()
        
        assert agent.last_heartbeat == heartbeat_time


class TestTaskModel:
    """Test suite for Task model."""
    
    def test_create_task(self, db_session, sample_task_data):
        """Test creating a task."""
        task = Task(**sample_task_data)
        db_session.add(task)
        db_session.commit()
        
        assert task.task_id is not None
        assert isinstance(task.task_id, uuid.UUID)
        assert task.description == "Test task description"
        assert task.sector == "test_sector"
        assert task.task_type == "test_type"
        assert task.token_usage == 1000
        assert task.estimated_cost_usd == Decimal('0.002')
    
    def test_task_with_agent_assignment(self, db_session):
        """Test assigning a task to an agent."""
        agent = create_test_agent(db_session)
        task = create_test_task(db_session, assigned_agent_id=agent.agent_id)
        
        assert task.assigned_agent_id == agent.agent_id
    
    def test_task_timestamps(self, db_session):
        """Test task timestamp functionality."""
        now = datetime.now(timezone.utc)
        task = create_test_task(
            db_session,
            created_at=now,
            started_at=now,
            completed_at=now
        )
        
        assert task.created_at == now
        assert task.started_at == now
        assert task.completed_at == now
    
    def test_task_cost_calculation(self, db_session):
        """Test task cost calculation with different values."""
        high_cost_task = create_test_task(
            db_session,
            token_usage=10000,
            estimated_cost_usd=Decimal('0.050')
        )
        
        assert high_cost_task.token_usage == 10000
        assert high_cost_task.estimated_cost_usd == Decimal('0.050')
    
    def test_task_optional_fields(self, db_session):
        """Test that optional fields can be None."""
        minimal_task = Task(description="Minimal task")
        db_session.add(minimal_task)
        db_session.commit()
        
        assert minimal_task.status_id is None
        assert minimal_task.priority_id is None
        assert minimal_task.assigned_agent_id is None


class TestTaskPriorityModel:
    """Test suite for TaskPriority model."""
    
    def test_create_task_priority(self, db_session):
        """Test creating a task priority."""
        priority = TaskPriority(priority_name="high")
        db_session.add(priority)
        db_session.commit()
        
        assert priority.priority_id is not None
        assert priority.priority_name == "high"
    
    def test_priority_name_unique(self, db_session):
        """Test that priority names are unique."""
        priority1 = TaskPriority(priority_name="critical")
        priority2 = TaskPriority(priority_name="critical")
        
        db_session.add(priority1)
        db_session.commit()
        
        with pytest.raises(IntegrityError):
            db_session.add(priority2)
            db_session.commit()


class TestTaskStatusModel:
    """Test suite for TaskStatus model."""
    
    def test_create_task_status(self, db_session):
        """Test creating a task status."""
        status = TaskStatus(status_name="in_progress")
        db_session.add(status)
        db_session.commit()
        
        assert status.status_id is not None
        assert status.status_name == "in_progress"
    
    def test_status_name_unique(self, db_session):
        """Test that status names are unique."""
        status1 = TaskStatus(status_name="completed")
        status2 = TaskStatus(status_name="completed")
        
        db_session.add(status1)
        db_session.commit()
        
        with pytest.raises(IntegrityError):
            db_session.add(status2)
            db_session.commit()


class TestTaskLogModel:
    """Test suite for TaskLog model."""
    
    def test_create_task_log(self, db_session):
        """Test creating a task log entry."""
        task = create_test_task(db_session)
        log_entry = TaskLog(
            task_id=task.task_id,
            timestamp=datetime.now(timezone.utc),
            message="Task started",
            log_level="INFO"
        )
        db_session.add(log_entry)
        db_session.commit()
        
        assert log_entry.log_id is not None
        assert log_entry.task_id == task.task_id
        assert log_entry.message == "Task started"
        assert log_entry.log_level == "INFO"
    
    def test_task_log_foreign_key(self, db_session):
        """Test foreign key relationship with tasks."""
        task = create_test_task(db_session)
        log1 = TaskLog(task_id=task.task_id, message="Log 1")
        log2 = TaskLog(task_id=task.task_id, message="Log 2")
        
        db_session.add_all([log1, log2])
        db_session.commit()
        
        assert log1.task_id == task.task_id
        assert log2.task_id == task.task_id
    
    def test_log_levels(self, db_session):
        """Test different log levels."""
        task = create_test_task(db_session)
        log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        
        logs = []
        for level in log_levels:
            log = TaskLog(
                task_id=task.task_id,
                message=f"{level} message",
                log_level=level
            )
            logs.append(log)
        
        db_session.add_all(logs)
        db_session.commit()
        
        for i, log in enumerate(logs):
            assert log.log_level == log_levels[i]


class TestSystemMetricModel:
    """Test suite for SystemMetric model."""
    
    def test_create_system_metric(self, db_session):
        """Test creating a system metric entry."""
        timestamp = datetime.now(timezone.utc)
        metric = SystemMetric(
            timestamp=timestamp,
            active_agents_count=5,
            tokens_per_second=100,
            cost_per_second_usd=Decimal('0.001'),
            tasks_completed_rate=10
        )
        db_session.add(metric)
        db_session.commit()
        
        assert metric.timestamp == timestamp
        assert metric.active_agents_count == 5
        assert metric.tokens_per_second == 100
        assert metric.cost_per_second_usd == Decimal('0.001')
        assert metric.tasks_completed_rate == 10
    
    def test_metric_precision(self, db_session):
        """Test decimal precision for cost metrics."""
        timestamp = datetime.now(timezone.utc)
        metric = SystemMetric(
            timestamp=timestamp,
            cost_per_second_usd=Decimal('0.12345678')
        )
        db_session.add(metric)
        db_session.commit()
        
        assert metric.cost_per_second_usd == Decimal('0.12345678')
    
    def test_metric_timeseries(self, db_session):
        """Test creating multiple metric entries for time series."""
        base_time = datetime.now(timezone.utc)
        metrics = []
        
        for i in range(3):
            metric = SystemMetric(
                timestamp=base_time.replace(second=i),
                active_agents_count=i + 1,
                tokens_per_second=100 * (i + 1)
            )
            metrics.append(metric)
        
        db_session.add_all(metrics)
        db_session.commit()
        
        for i, metric in enumerate(metrics):
            assert metric.active_agents_count == i + 1
            assert metric.tokens_per_second == 100 * (i + 1)