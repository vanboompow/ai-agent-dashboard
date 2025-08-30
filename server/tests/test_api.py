import pytest
import json
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient
from datetime import datetime, timezone

from app.models.agent import Agent, AgentStatus
from tests.conftest import create_test_agent, create_test_task


class TestHealthEndpoint:
    """Test suite for health check endpoints."""
    
    async def test_health_check(self, client: AsyncClient):
        """Test the health check endpoint."""
        response = await client.get("/healthz")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "ai-agent-dashboard"
    
    async def test_root_endpoint(self, client: AsyncClient):
        """Test the root endpoint."""
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "docs" in data
        assert "redoc" in data


class TestAgentsAPI:
    """Test suite for agents API endpoints."""
    
    async def test_get_agents_empty(self, client: AsyncClient):
        """Test getting agents when none exist."""
        with patch('app.api.agents.get_agents') as mock_get_agents:
            mock_get_agents.return_value = []
            
            response = await client.get("/api/agents")
            assert response.status_code == 200
            assert response.json() == []
    
    async def test_get_agents_with_data(self, client: AsyncClient):
        """Test getting agents with sample data."""
        sample_agents = [
            {
                "agent_id": "123e4567-e89b-12d3-a456-426614174000",
                "agent_type": "test_agent",
                "hostname": "test-host",
                "current_status": "idle"
            }
        ]
        
        with patch('app.api.agents.get_agents') as mock_get_agents:
            mock_get_agents.return_value = sample_agents
            
            response = await client.get("/api/agents")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["agent_type"] == "test_agent"
    
    async def test_get_agent_by_id(self, client: AsyncClient):
        """Test getting a specific agent by ID."""
        agent_id = "123e4567-e89b-12d3-a456-426614174000"
        sample_agent = {
            "agent_id": agent_id,
            "agent_type": "test_agent",
            "hostname": "test-host",
            "current_status": "idle"
        }
        
        with patch('app.api.agents.get_agent_by_id') as mock_get_agent:
            mock_get_agent.return_value = sample_agent
            
            response = await client.get(f"/api/agents/{agent_id}")
            assert response.status_code == 200
            data = response.json()
            assert data["agent_id"] == agent_id
            assert data["agent_type"] == "test_agent"
    
    async def test_get_agent_not_found(self, client: AsyncClient):
        """Test getting a non-existent agent."""
        agent_id = "123e4567-e89b-12d3-a456-426614174000"
        
        with patch('app.api.agents.get_agent_by_id') as mock_get_agent:
            mock_get_agent.return_value = None
            
            response = await client.get(f"/api/agents/{agent_id}")
            assert response.status_code == 404
    
    async def test_update_agent_status(self, client: AsyncClient):
        """Test updating an agent's status."""
        agent_id = "123e4567-e89b-12d3-a456-426614174000"
        update_data = {"status": "working"}
        
        with patch('app.api.agents.update_agent_status') as mock_update:
            mock_update.return_value = True
            
            response = await client.patch(f"/api/agents/{agent_id}/status", json=update_data)
            assert response.status_code == 200
    
    async def test_agent_heartbeat(self, client: AsyncClient):
        """Test agent heartbeat endpoint."""
        agent_id = "123e4567-e89b-12d3-a456-426614174000"
        heartbeat_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "working"
        }
        
        with patch('app.api.agents.update_agent_heartbeat') as mock_heartbeat:
            mock_heartbeat.return_value = True
            
            response = await client.post(f"/api/agents/{agent_id}/heartbeat", json=heartbeat_data)
            assert response.status_code == 200


class TestTasksAPI:
    """Test suite for tasks API endpoints."""
    
    async def test_get_tasks_empty(self, client: AsyncClient):
        """Test getting tasks when none exist."""
        with patch('app.api.tasks.get_tasks') as mock_get_tasks:
            mock_get_tasks.return_value = []
            
            response = await client.get("/api/tasks")
            assert response.status_code == 200
            assert response.json() == []
    
    async def test_get_tasks_with_pagination(self, client: AsyncClient):
        """Test getting tasks with pagination."""
        sample_tasks = [
            {
                "task_id": "123e4567-e89b-12d3-a456-426614174001",
                "description": "Test task 1",
                "status": "pending",
                "sector": "test"
            },
            {
                "task_id": "123e4567-e89b-12d3-a456-426614174002",
                "description": "Test task 2",
                "status": "completed",
                "sector": "test"
            }
        ]
        
        with patch('app.api.tasks.get_tasks') as mock_get_tasks:
            mock_get_tasks.return_value = sample_tasks
            
            response = await client.get("/api/tasks?limit=10&offset=0")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
    
    async def test_create_task(self, client: AsyncClient):
        """Test creating a new task."""
        task_data = {
            "description": "New test task",
            "sector": "test_sector",
            "task_type": "test_type",
            "priority": "medium"
        }
        
        created_task = {
            "task_id": "123e4567-e89b-12d3-a456-426614174003",
            **task_data,
            "status": "pending"
        }
        
        with patch('app.api.tasks.create_task') as mock_create:
            mock_create.return_value = created_task
            
            response = await client.post("/api/tasks", json=task_data)
            assert response.status_code == 201
            data = response.json()
            assert data["description"] == task_data["description"]
            assert data["task_id"] == created_task["task_id"]
    
    async def test_get_task_by_id(self, client: AsyncClient):
        """Test getting a specific task by ID."""
        task_id = "123e4567-e89b-12d3-a456-426614174001"
        sample_task = {
            "task_id": task_id,
            "description": "Test task",
            "status": "pending"
        }
        
        with patch('app.api.tasks.get_task_by_id') as mock_get_task:
            mock_get_task.return_value = sample_task
            
            response = await client.get(f"/api/tasks/{task_id}")
            assert response.status_code == 200
            data = response.json()
            assert data["task_id"] == task_id
    
    async def test_update_task_status(self, client: AsyncClient):
        """Test updating a task's status."""
        task_id = "123e4567-e89b-12d3-a456-426614174001"
        update_data = {"status": "in_progress"}
        
        with patch('app.api.tasks.update_task_status') as mock_update:
            mock_update.return_value = True
            
            response = await client.patch(f"/api/tasks/{task_id}/status", json=update_data)
            assert response.status_code == 200
    
    async def test_delete_task(self, client: AsyncClient):
        """Test deleting a task."""
        task_id = "123e4567-e89b-12d3-a456-426614174001"
        
        with patch('app.api.tasks.delete_task') as mock_delete:
            mock_delete.return_value = True
            
            response = await client.delete(f"/api/tasks/{task_id}")
            assert response.status_code == 204
    
    async def test_get_task_logs(self, client: AsyncClient):
        """Test getting task logs."""
        task_id = "123e4567-e89b-12d3-a456-426614174001"
        sample_logs = [
            {
                "log_id": 1,
                "task_id": task_id,
                "timestamp": "2024-01-01T12:00:00Z",
                "message": "Task started",
                "log_level": "INFO"
            }
        ]
        
        with patch('app.api.tasks.get_task_logs') as mock_get_logs:
            mock_get_logs.return_value = sample_logs
            
            response = await client.get(f"/api/tasks/{task_id}/logs")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["message"] == "Task started"


class TestSystemAPI:
    """Test suite for system control API endpoints."""
    
    async def test_system_run(self, client: AsyncClient):
        """Test system run command."""
        with patch('app.api.system.start_system') as mock_start:
            mock_start.return_value = True
            
            response = await client.post("/api/system/run")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "running"
    
    async def test_system_pause_all(self, client: AsyncClient):
        """Test system pause all command."""
        with patch('app.api.system.pause_all_agents') as mock_pause:
            mock_pause.return_value = True
            
            response = await client.post("/api/system/pause-all")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "paused"
    
    async def test_system_stop_new(self, client: AsyncClient):
        """Test system stop new tasks command."""
        with patch('app.api.system.stop_new_tasks') as mock_stop:
            mock_stop.return_value = True
            
            response = await client.post("/api/system/stop-new")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "stopped_new"
    
    async def test_set_throttle(self, client: AsyncClient):
        """Test setting system throttle."""
        throttle_data = {"rate": 0.5}
        
        with patch('app.api.system.set_throttle_rate') as mock_throttle:
            mock_throttle.return_value = True
            
            response = await client.post("/api/system/throttle", json=throttle_data)
            assert response.status_code == 200
    
    async def test_get_system_metrics(self, client: AsyncClient):
        """Test getting system metrics."""
        sample_metrics = {
            "active_agents_count": 5,
            "tokens_per_second": 100,
            "cost_per_second_usd": 0.001,
            "tasks_completed_rate": 10
        }
        
        with patch('app.api.system.get_system_metrics') as mock_metrics:
            mock_metrics.return_value = sample_metrics
            
            response = await client.get("/api/system/metrics")
            assert response.status_code == 200
            data = response.json()
            assert data["active_agents_count"] == 5
    
    async def test_get_system_status(self, client: AsyncClient):
        """Test getting system status."""
        sample_status = {
            "status": "running",
            "uptime": 3600,
            "version": "1.0.0",
            "agents_connected": 5,
            "tasks_queued": 10
        }
        
        with patch('app.api.system.get_system_status') as mock_status:
            mock_status.return_value = sample_status
            
            response = await client.get("/api/system/status")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "running"


class TestStreamAPI:
    """Test suite for streaming API endpoints."""
    
    async def test_stream_endpoint_connection(self, client: AsyncClient):
        """Test that stream endpoint is accessible."""
        # Note: Testing SSE endpoints is complex, this is a basic connectivity test
        response = await client.get("/api/stream")
        # SSE endpoints typically return 200 and keep connection open
        assert response.status_code in [200, 307]  # 307 for redirect in some setups
    
    async def test_stream_with_redis_mock(self, client: AsyncClient, redis_client):
        """Test stream functionality with mocked Redis."""
        # Mock Redis pubsub for testing
        mock_pubsub = AsyncMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_pubsub.get_message = AsyncMock(return_value=None)
        redis_client.pubsub = AsyncMock(return_value=mock_pubsub)
        
        response = await client.get("/api/stream")
        assert response.status_code in [200, 307]


class TestAPIErrorHandling:
    """Test suite for API error handling."""
    
    async def test_invalid_json_request(self, client: AsyncClient):
        """Test handling of invalid JSON in requests."""
        response = await client.post("/api/tasks", data="invalid json")
        assert response.status_code == 422  # Unprocessable Entity
    
    async def test_missing_required_fields(self, client: AsyncClient):
        """Test handling of missing required fields."""
        incomplete_task = {"description": ""}  # Missing required fields
        
        response = await client.post("/api/tasks", json=incomplete_task)
        assert response.status_code == 422
    
    async def test_invalid_uuid_format(self, client: AsyncClient):
        """Test handling of invalid UUID format."""
        invalid_id = "not-a-valid-uuid"
        
        response = await client.get(f"/api/agents/{invalid_id}")
        assert response.status_code == 422
    
    async def test_method_not_allowed(self, client: AsyncClient):
        """Test handling of unsupported HTTP methods."""
        response = await client.put("/api/tasks")  # PUT not supported for collection
        assert response.status_code == 405
    
    async def test_internal_server_error(self, client: AsyncClient):
        """Test handling of internal server errors."""
        with patch('app.api.agents.get_agents', side_effect=Exception("Database error")):
            response = await client.get("/api/agents")
            assert response.status_code == 500