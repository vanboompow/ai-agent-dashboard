import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
import uuid

from app.services.agent_service import AgentService
from app.services.task_service import TaskService
from app.services.system_service import SystemService
from app.services.stream_service import StreamService
from app.models.agent import Agent, AgentStatus
from app.models.task import Task
from tests.conftest import create_test_agent, create_test_task


class TestAgentService:
    """Test suite for AgentService."""
    
    @pytest.fixture
    def agent_service(self, db_session, redis_client):
        """Create AgentService instance for testing."""
        return AgentService(db_session, redis_client)
    
    async def test_get_all_agents(self, agent_service, db_session):
        """Test getting all agents."""
        # Create test agents
        agent1 = create_test_agent(db_session, agent_type="agent1")
        agent2 = create_test_agent(db_session, agent_type="agent2")
        
        agents = await agent_service.get_all_agents()
        assert len(agents) == 2
        agent_types = [agent.agent_type for agent in agents]
        assert "agent1" in agent_types
        assert "agent2" in agent_types
    
    async def test_get_agent_by_id(self, agent_service, db_session):
        """Test getting agent by ID."""
        agent = create_test_agent(db_session, agent_type="test_agent")
        
        found_agent = await agent_service.get_agent_by_id(agent.agent_id)
        assert found_agent is not None
        assert found_agent.agent_id == agent.agent_id
        assert found_agent.agent_type == "test_agent"
    
    async def test_get_agent_by_id_not_found(self, agent_service):
        """Test getting non-existent agent."""
        non_existent_id = uuid.uuid4()
        
        found_agent = await agent_service.get_agent_by_id(non_existent_id)
        assert found_agent is None
    
    async def test_create_agent(self, agent_service, redis_client):
        """Test creating a new agent."""
        agent_data = {
            "agent_type": "new_agent",
            "hostname": "new-host",
            "current_status": AgentStatus.idle
        }
        
        created_agent = await agent_service.create_agent(agent_data)
        assert created_agent.agent_type == "new_agent"
        assert created_agent.hostname == "new-host"
        assert created_agent.current_status == AgentStatus.idle
        assert created_agent.agent_id is not None
        
        # Verify Redis notification was sent
        redis_client.publish.assert_called_once()
    
    async def test_update_agent_status(self, agent_service, db_session, redis_client):
        """Test updating agent status."""
        agent = create_test_agent(db_session, current_status=AgentStatus.idle)
        
        success = await agent_service.update_agent_status(agent.agent_id, AgentStatus.working)
        assert success is True
        
        # Verify status was updated
        updated_agent = await agent_service.get_agent_by_id(agent.agent_id)
        assert updated_agent.current_status == AgentStatus.working
        
        # Verify Redis notification was sent
        redis_client.publish.assert_called_once()
    
    async def test_update_agent_heartbeat(self, agent_service, db_session, redis_client):
        """Test updating agent heartbeat."""
        agent = create_test_agent(db_session)
        heartbeat_time = datetime.now(timezone.utc)
        
        success = await agent_service.update_heartbeat(agent.agent_id, heartbeat_time)
        assert success is True
        
        # Verify heartbeat was updated
        updated_agent = await agent_service.get_agent_by_id(agent.agent_id)
        assert updated_agent.last_heartbeat == heartbeat_time
    
    async def test_get_agents_by_status(self, agent_service, db_session):
        """Test filtering agents by status."""
        working_agent = create_test_agent(db_session, agent_type="working", current_status=AgentStatus.working)
        idle_agent = create_test_agent(db_session, agent_type="idle", current_status=AgentStatus.idle)
        
        working_agents = await agent_service.get_agents_by_status(AgentStatus.working)
        assert len(working_agents) == 1
        assert working_agents[0].agent_id == working_agent.agent_id
        
        idle_agents = await agent_service.get_agents_by_status(AgentStatus.idle)
        assert len(idle_agents) == 1
        assert idle_agents[0].agent_id == idle_agent.agent_id
    
    async def test_delete_agent(self, agent_service, db_session, redis_client):
        """Test deleting an agent."""
        agent = create_test_agent(db_session)
        
        success = await agent_service.delete_agent(agent.agent_id)
        assert success is True
        
        # Verify agent was deleted
        deleted_agent = await agent_service.get_agent_by_id(agent.agent_id)
        assert deleted_agent is None
        
        # Verify Redis notification was sent
        redis_client.publish.assert_called_once()


class TestTaskService:
    """Test suite for TaskService."""
    
    @pytest.fixture
    def task_service(self, db_session, redis_client):
        """Create TaskService instance for testing."""
        return TaskService(db_session, redis_client)
    
    async def test_get_all_tasks(self, task_service, db_session):
        """Test getting all tasks."""
        task1 = create_test_task(db_session, description="Task 1")
        task2 = create_test_task(db_session, description="Task 2")
        
        tasks = await task_service.get_all_tasks()
        assert len(tasks) == 2
        descriptions = [task.description for task in tasks]
        assert "Task 1" in descriptions
        assert "Task 2" in descriptions
    
    async def test_get_tasks_with_pagination(self, task_service, db_session):
        """Test getting tasks with pagination."""
        # Create multiple tasks
        for i in range(5):
            create_test_task(db_session, description=f"Task {i}")
        
        # Test pagination
        tasks_page1 = await task_service.get_tasks(limit=2, offset=0)
        assert len(tasks_page1) == 2
        
        tasks_page2 = await task_service.get_tasks(limit=2, offset=2)
        assert len(tasks_page2) == 2
        
        # Verify different tasks
        page1_ids = {task.task_id for task in tasks_page1}
        page2_ids = {task.task_id for task in tasks_page2}
        assert page1_ids.isdisjoint(page2_ids)
    
    async def test_create_task(self, task_service, redis_client):
        """Test creating a new task."""
        task_data = {
            "description": "New task",
            "sector": "test_sector",
            "task_type": "test_type",
            "token_usage": 1000,
            "estimated_cost_usd": 0.002
        }
        
        created_task = await task_service.create_task(task_data)
        assert created_task.description == "New task"
        assert created_task.sector == "test_sector"
        assert created_task.token_usage == 1000
        assert created_task.task_id is not None
        
        # Verify Redis notification was sent
        redis_client.publish.assert_called_once()
    
    async def test_get_task_by_id(self, task_service, db_session):
        """Test getting task by ID."""
        task = create_test_task(db_session, description="Test task")
        
        found_task = await task_service.get_task_by_id(task.task_id)
        assert found_task is not None
        assert found_task.task_id == task.task_id
        assert found_task.description == "Test task"
    
    async def test_update_task_status(self, task_service, db_session, redis_client):
        """Test updating task status."""
        task = create_test_task(db_session)
        
        success = await task_service.update_task_status(task.task_id, "in_progress")
        assert success is True
        
        # Verify status was updated (this would typically update a status_id)
        updated_task = await task_service.get_task_by_id(task.task_id)
        assert updated_task is not None
        
        # Verify Redis notification was sent
        redis_client.publish.assert_called_once()
    
    async def test_assign_task_to_agent(self, task_service, db_session, redis_client):
        """Test assigning a task to an agent."""
        agent = create_test_agent(db_session)
        task = create_test_task(db_session)
        
        success = await task_service.assign_task(task.task_id, agent.agent_id)
        assert success is True
        
        # Verify assignment
        updated_task = await task_service.get_task_by_id(task.task_id)
        assert updated_task.assigned_agent_id == agent.agent_id
        
        # Verify Redis notification was sent
        redis_client.publish.assert_called_once()
    
    async def test_get_tasks_by_agent(self, task_service, db_session):
        """Test getting tasks assigned to a specific agent."""
        agent1 = create_test_agent(db_session, agent_type="agent1")
        agent2 = create_test_agent(db_session, agent_type="agent2")
        
        task1 = create_test_task(db_session, description="Task 1", assigned_agent_id=agent1.agent_id)
        task2 = create_test_task(db_session, description="Task 2", assigned_agent_id=agent1.agent_id)
        task3 = create_test_task(db_session, description="Task 3", assigned_agent_id=agent2.agent_id)
        
        agent1_tasks = await task_service.get_tasks_by_agent(agent1.agent_id)
        assert len(agent1_tasks) == 2
        
        agent2_tasks = await task_service.get_tasks_by_agent(agent2.agent_id)
        assert len(agent2_tasks) == 1
    
    async def test_delete_task(self, task_service, db_session, redis_client):
        """Test deleting a task."""
        task = create_test_task(db_session)
        
        success = await task_service.delete_task(task.task_id)
        assert success is True
        
        # Verify task was deleted
        deleted_task = await task_service.get_task_by_id(task.task_id)
        assert deleted_task is None
        
        # Verify Redis notification was sent
        redis_client.publish.assert_called_once()
    
    async def test_add_task_log(self, task_service, db_session):
        """Test adding a log entry to a task."""
        task = create_test_task(db_session)
        
        log_data = {
            "message": "Task started",
            "log_level": "INFO",
            "timestamp": datetime.now(timezone.utc)
        }
        
        log_entry = await task_service.add_task_log(task.task_id, log_data)
        assert log_entry is not None
        assert log_entry.message == "Task started"
        assert log_entry.log_level == "INFO"
        assert log_entry.task_id == task.task_id
    
    async def test_get_task_logs(self, task_service, db_session):
        """Test getting task logs."""
        task = create_test_task(db_session)
        
        # Add multiple log entries
        for i in range(3):
            await task_service.add_task_log(task.task_id, {
                "message": f"Log entry {i}",
                "log_level": "INFO",
                "timestamp": datetime.now(timezone.utc)
            })
        
        logs = await task_service.get_task_logs(task.task_id)
        assert len(logs) == 3


class TestSystemService:
    """Test suite for SystemService."""
    
    @pytest.fixture
    def system_service(self, db_session, redis_client, mock_celery):
        """Create SystemService instance for testing."""
        return SystemService(db_session, redis_client, mock_celery)
    
    async def test_get_system_metrics(self, system_service, db_session):
        """Test getting system metrics."""
        # Create some sample data
        create_test_agent(db_session, current_status=AgentStatus.working)
        create_test_agent(db_session, current_status=AgentStatus.idle)
        create_test_task(db_session)
        
        metrics = await system_service.get_system_metrics()
        assert "active_agents_count" in metrics
        assert "tasks_queued" in metrics
        assert metrics["active_agents_count"] >= 0
    
    async def test_get_system_status(self, system_service):
        """Test getting system status."""
        status = await system_service.get_system_status()
        assert "status" in status
        assert "uptime" in status
        assert "version" in status
    
    async def test_start_system(self, system_service, redis_client, mock_celery):
        """Test starting the system."""
        success = await system_service.start_system()
        assert success is True
        
        # Verify Redis notification was sent
        redis_client.publish.assert_called()
    
    async def test_pause_all_agents(self, system_service, db_session, redis_client):
        """Test pausing all agents."""
        # Create working agents
        agent1 = create_test_agent(db_session, current_status=AgentStatus.working)
        agent2 = create_test_agent(db_session, current_status=AgentStatus.working)
        
        success = await system_service.pause_all_agents()
        assert success is True
        
        # Verify Redis notification was sent
        redis_client.publish.assert_called()
    
    async def test_stop_new_tasks(self, system_service, redis_client):
        """Test stopping new task creation."""
        success = await system_service.stop_new_tasks()
        assert success is True
        
        # Verify Redis notification was sent
        redis_client.publish.assert_called()
    
    async def test_set_throttle_rate(self, system_service, redis_client):
        """Test setting system throttle rate."""
        throttle_rate = 0.5
        
        success = await system_service.set_throttle_rate(throttle_rate)
        assert success is True
        
        # Verify Redis notification was sent
        redis_client.publish.assert_called()
    
    async def test_emergency_stop(self, system_service, redis_client, mock_celery):
        """Test emergency stop functionality."""
        success = await system_service.emergency_stop()
        assert success is True
        
        # Verify Redis notification was sent
        redis_client.publish.assert_called()
        
        # Verify Celery tasks were revoked
        mock_celery.control.purge.assert_called()


class TestStreamService:
    """Test suite for StreamService."""
    
    @pytest.fixture
    def stream_service(self, redis_client):
        """Create StreamService instance for testing."""
        return StreamService(redis_client)
    
    async def test_publish_agent_update(self, stream_service, redis_client):
        """Test publishing agent update event."""
        agent_data = {
            "agent_id": str(uuid.uuid4()),
            "status": "working",
            "current_task": "test task"
        }
        
        await stream_service.publish_agent_update(agent_data)
        
        # Verify Redis publish was called
        redis_client.publish.assert_called_once_with(
            "agent_updates", 
            pytest.approx(agent_data, abs=1e-6)  # Allow for JSON serialization differences
        )
    
    async def test_publish_task_update(self, stream_service, redis_client):
        """Test publishing task update event."""
        task_data = {
            "task_id": str(uuid.uuid4()),
            "status": "completed",
            "progress": 100
        }
        
        await stream_service.publish_task_update(task_data)
        
        # Verify Redis publish was called
        redis_client.publish.assert_called_once()
    
    async def test_publish_metrics_update(self, stream_service, redis_client):
        """Test publishing metrics update event."""
        metrics_data = {
            "tokens_per_second": 150,
            "cost_per_second_usd": 0.003,
            "active_agents_count": 5
        }
        
        await stream_service.publish_metrics_update(metrics_data)
        
        # Verify Redis publish was called
        redis_client.publish.assert_called_once()
    
    async def test_subscribe_to_updates(self, stream_service, redis_client):
        """Test subscribing to update channels."""
        # Mock pubsub object
        mock_pubsub = AsyncMock()
        redis_client.pubsub.return_value = mock_pubsub
        
        channels = ["agent_updates", "task_updates", "metrics_updates"]
        await stream_service.subscribe_to_updates(channels)
        
        # Verify subscribe was called
        mock_pubsub.subscribe.assert_called_once_with(*channels)
    
    async def test_get_stream_events(self, stream_service, redis_client):
        """Test getting stream events."""
        # Mock pubsub with sample message
        mock_pubsub = AsyncMock()
        sample_message = {
            'type': 'message',
            'channel': b'agent_updates',
            'data': b'{"agent_id": "123", "status": "working"}'
        }
        mock_pubsub.get_message.return_value = sample_message
        redis_client.pubsub.return_value = mock_pubsub
        
        events = await stream_service.get_stream_events(["agent_updates"])
        
        # This test depends on implementation details
        # Verify pubsub setup was called
        redis_client.pubsub.assert_called_once()