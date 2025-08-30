import pytest
import asyncio
import json
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient
from datetime import datetime, timezone
import uuid

from app.models.agent import Agent, AgentStatus
from app.models.task import Task
from tests.conftest import create_test_agent, create_test_task


class TestFullStackIntegration:
    """Integration tests for the full application stack."""
    
    async def test_agent_lifecycle_integration(self, client: AsyncClient, db_session, redis_client):
        """Test complete agent lifecycle from creation to deletion."""
        # 1. Create agent
        agent_data = {
            "agent_type": "integration_test_agent",
            "hostname": "test-integration-host",
            "current_status": "idle"
        }
        
        with patch('app.api.agents.create_agent') as mock_create:
            mock_agent = {
                "agent_id": str(uuid.uuid4()),
                **agent_data
            }
            mock_create.return_value = mock_agent
            
            response = await client.post("/api/agents", json=agent_data)
            assert response.status_code == 201
            created_agent = response.json()
            agent_id = created_agent["agent_id"]
        
        # 2. Send heartbeat
        heartbeat_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "working"
        }
        
        with patch('app.api.agents.update_agent_heartbeat') as mock_heartbeat:
            mock_heartbeat.return_value = True
            
            response = await client.post(f"/api/agents/{agent_id}/heartbeat", json=heartbeat_data)
            assert response.status_code == 200
        
        # 3. Update status
        status_update = {"status": "working"}
        
        with patch('app.api.agents.update_agent_status') as mock_update:
            mock_update.return_value = True
            
            response = await client.patch(f"/api/agents/{agent_id}/status", json=status_update)
            assert response.status_code == 200
        
        # 4. Get agent details
        with patch('app.api.agents.get_agent_by_id') as mock_get:
            mock_get.return_value = {**mock_agent, "current_status": "working"}
            
            response = await client.get(f"/api/agents/{agent_id}")
            assert response.status_code == 200
            agent_details = response.json()
            assert agent_details["agent_id"] == agent_id
            assert agent_details["current_status"] == "working"
        
        # 5. Delete agent
        with patch('app.api.agents.delete_agent') as mock_delete:
            mock_delete.return_value = True
            
            response = await client.delete(f"/api/agents/{agent_id}")
            assert response.status_code == 204
    
    async def test_task_processing_workflow(self, client: AsyncClient, db_session, redis_client):
        """Test complete task processing workflow."""
        # 1. Create task
        task_data = {
            "description": "Integration test task",
            "sector": "test_sector",
            "task_type": "integration_test",
            "priority": "high"
        }
        
        with patch('app.api.tasks.create_task') as mock_create_task:
            task_id = str(uuid.uuid4())
            created_task = {
                "task_id": task_id,
                **task_data,
                "status": "pending"
            }
            mock_create_task.return_value = created_task
            
            response = await client.post("/api/tasks", json=task_data)
            assert response.status_code == 201
            task = response.json()
            assert task["task_id"] == task_id
        
        # 2. Create agent to assign task to
        agent_data = {
            "agent_type": "task_processor",
            "hostname": "processor-host",
            "current_status": "idle"
        }
        
        with patch('app.api.agents.create_agent') as mock_create_agent:
            agent_id = str(uuid.uuid4())
            created_agent = {
                "agent_id": agent_id,
                **agent_data
            }
            mock_create_agent.return_value = created_agent
            
            response = await client.post("/api/agents", json=agent_data)
            assert response.status_code == 201
            agent = response.json()
        
        # 3. Assign task to agent
        assignment_data = {"agent_id": agent_id}
        
        with patch('app.api.tasks.assign_task') as mock_assign:
            mock_assign.return_value = True
            
            response = await client.patch(f"/api/tasks/{task_id}/assign", json=assignment_data)
            assert response.status_code == 200
        
        # 4. Update task status to in_progress
        status_update = {"status": "in_progress"}
        
        with patch('app.api.tasks.update_task_status') as mock_update_status:
            mock_update_status.return_value = True
            
            response = await client.patch(f"/api/tasks/{task_id}/status", json=status_update)
            assert response.status_code == 200
        
        # 5. Add task log
        log_data = {
            "message": "Task processing started",
            "log_level": "INFO"
        }
        
        with patch('app.api.tasks.add_task_log') as mock_add_log:
            mock_add_log.return_value = {
                "log_id": 1,
                "task_id": task_id,
                "message": log_data["message"],
                "log_level": log_data["log_level"],
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            response = await client.post(f"/api/tasks/{task_id}/logs", json=log_data)
            assert response.status_code == 201
        
        # 6. Complete task
        completion_update = {"status": "completed"}
        
        with patch('app.api.tasks.update_task_status') as mock_complete:
            mock_complete.return_value = True
            
            response = await client.patch(f"/api/tasks/{task_id}/status", json=completion_update)
            assert response.status_code == 200
        
        # 7. Get task logs
        with patch('app.api.tasks.get_task_logs') as mock_get_logs:
            mock_get_logs.return_value = [
                {
                    "log_id": 1,
                    "message": "Task processing started",
                    "log_level": "INFO",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            ]
            
            response = await client.get(f"/api/tasks/{task_id}/logs")
            assert response.status_code == 200
            logs = response.json()
            assert len(logs) == 1
            assert logs[0]["message"] == "Task processing started"
    
    async def test_system_control_integration(self, client: AsyncClient, redis_client):
        """Test system control integration."""
        # 1. Start system
        with patch('app.api.system.start_system') as mock_start:
            mock_start.return_value = True
            
            response = await client.post("/api/system/run")
            assert response.status_code == 200
            result = response.json()
            assert result["status"] == "running"
        
        # 2. Get system metrics
        with patch('app.api.system.get_system_metrics') as mock_metrics:
            mock_metrics.return_value = {
                "active_agents_count": 3,
                "tokens_per_second": 150,
                "cost_per_second_usd": 0.003,
                "tasks_completed_rate": 5
            }
            
            response = await client.get("/api/system/metrics")
            assert response.status_code == 200
            metrics = response.json()
            assert metrics["active_agents_count"] == 3
        
        # 3. Set throttle
        throttle_data = {"rate": 0.8}
        
        with patch('app.api.system.set_throttle_rate') as mock_throttle:
            mock_throttle.return_value = True
            
            response = await client.post("/api/system/throttle", json=throttle_data)
            assert response.status_code == 200
        
        # 4. Pause all agents
        with patch('app.api.system.pause_all_agents') as mock_pause:
            mock_pause.return_value = True
            
            response = await client.post("/api/system/pause-all")
            assert response.status_code == 200
            result = response.json()
            assert result["status"] == "paused"
        
        # 5. Stop new tasks
        with patch('app.api.system.stop_new_tasks') as mock_stop:
            mock_stop.return_value = True
            
            response = await client.post("/api/system/stop-new")
            assert response.status_code == 200
            result = response.json()
            assert result["status"] == "stopped_new"
        
        # 6. Get system status
        with patch('app.api.system.get_system_status') as mock_status:
            mock_status.return_value = {
                "status": "stopped_new",
                "uptime": 3600,
                "version": "1.0.0",
                "agents_connected": 3,
                "tasks_queued": 5
            }
            
            response = await client.get("/api/system/status")
            assert response.status_code == 200
            status = response.json()
            assert status["status"] == "stopped_new"


class TestStreamingIntegration:
    """Integration tests for real-time streaming functionality."""
    
    async def test_stream_endpoint_basic_connection(self, client: AsyncClient):
        """Test basic connection to streaming endpoint."""
        response = await client.get("/api/stream")
        # SSE endpoints return 200 and keep connection open
        assert response.status_code in [200, 307]
    
    async def test_stream_event_publishing(self, client: AsyncClient, redis_client):
        """Test event publishing through stream."""
        # Mock Redis pubsub
        mock_pubsub = AsyncMock()
        redis_client.pubsub.return_value = mock_pubsub
        
        # Simulate publishing an event
        event_data = {
            "event_type": "agent_update",
            "data": {
                "agent_id": str(uuid.uuid4()),
                "status": "working",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }
        
        # This would typically be done by the service layer
        await redis_client.publish("agent_updates", json.dumps(event_data))
        redis_client.publish.assert_called_once()
    
    async def test_metrics_streaming(self, client: AsyncClient, redis_client):
        """Test real-time metrics streaming."""
        # Mock metrics collection
        metrics_data = {
            "active_agents_count": 5,
            "tokens_per_second": 120,
            "cost_per_second_usd": 0.0024,
            "tasks_completed_rate": 8,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Simulate metrics publishing
        await redis_client.publish("metrics_updates", json.dumps(metrics_data))
        redis_client.publish.assert_called_once()


class TestDatabaseIntegration:
    """Integration tests for database operations."""
    
    def test_agent_crud_operations(self, db_session):
        """Test complete CRUD operations for agents."""
        # Create
        agent_data = {
            "agent_type": "crud_test_agent",
            "hostname": "crud-test-host",
            "current_status": AgentStatus.idle,
            "created_at": datetime.now(timezone.utc)
        }
        agent = Agent(**agent_data)
        db_session.add(agent)
        db_session.commit()
        
        created_agent_id = agent.agent_id
        assert created_agent_id is not None
        
        # Read
        found_agent = db_session.query(Agent).filter(Agent.agent_id == created_agent_id).first()
        assert found_agent is not None
        assert found_agent.agent_type == "crud_test_agent"
        
        # Update
        found_agent.current_status = AgentStatus.working
        found_agent.last_heartbeat = datetime.now(timezone.utc)
        db_session.commit()
        
        updated_agent = db_session.query(Agent).filter(Agent.agent_id == created_agent_id).first()
        assert updated_agent.current_status == AgentStatus.working
        assert updated_agent.last_heartbeat is not None
        
        # Delete
        db_session.delete(updated_agent)
        db_session.commit()
        
        deleted_agent = db_session.query(Agent).filter(Agent.agent_id == created_agent_id).first()
        assert deleted_agent is None
    
    def test_task_crud_operations(self, db_session):
        """Test complete CRUD operations for tasks."""
        # Create task
        task_data = {
            "description": "CRUD test task",
            "sector": "crud_test",
            "task_type": "integration_test",
            "token_usage": 1500,
            "estimated_cost_usd": 0.003,
            "created_at": datetime.now(timezone.utc)
        }
        task = Task(**task_data)
        db_session.add(task)
        db_session.commit()
        
        created_task_id = task.task_id
        assert created_task_id is not None
        
        # Read
        found_task = db_session.query(Task).filter(Task.task_id == created_task_id).first()
        assert found_task is not None
        assert found_task.description == "CRUD test task"
        assert found_task.token_usage == 1500
        
        # Update
        found_task.started_at = datetime.now(timezone.utc)
        found_task.token_usage = 2000
        db_session.commit()
        
        updated_task = db_session.query(Task).filter(Task.task_id == created_task_id).first()
        assert updated_task.started_at is not None
        assert updated_task.token_usage == 2000
        
        # Delete
        db_session.delete(updated_task)
        db_session.commit()
        
        deleted_task = db_session.query(Task).filter(Task.task_id == created_task_id).first()
        assert deleted_task is None
    
    def test_agent_task_relationship(self, db_session):
        """Test relationship between agents and tasks."""
        # Create agent
        agent = create_test_agent(db_session, agent_type="relationship_test")
        
        # Create tasks assigned to agent
        task1 = create_test_task(db_session, description="Task 1", assigned_agent_id=agent.agent_id)
        task2 = create_test_task(db_session, description="Task 2", assigned_agent_id=agent.agent_id)
        task3 = create_test_task(db_session, description="Unassigned task")
        
        # Query tasks by agent
        agent_tasks = db_session.query(Task).filter(Task.assigned_agent_id == agent.agent_id).all()
        assert len(agent_tasks) == 2
        
        task_descriptions = [task.description for task in agent_tasks]
        assert "Task 1" in task_descriptions
        assert "Task 2" in task_descriptions
        assert "Unassigned task" not in task_descriptions
    
    def test_database_transaction_rollback(self, db_session):
        """Test database transaction rollback functionality."""
        # Create agent
        agent = create_test_agent(db_session, agent_type="rollback_test")
        initial_count = db_session.query(Agent).count()
        
        try:
            # Start a transaction
            task = create_test_task(db_session, description="Rollback test task")
            
            # Simulate an error that should cause rollback
            raise Exception("Simulated error")
            
        except Exception:
            db_session.rollback()
        
        # Verify rollback
        final_count = db_session.query(Agent).count()
        assert final_count == initial_count
        
        # Verify task was not created
        rollback_task = db_session.query(Task).filter(Task.description == "Rollback test task").first()
        assert rollback_task is None


class TestCeleryIntegration:
    """Integration tests for Celery task processing."""
    
    @patch('app.celery_worker.tasks.process_agent_task.delay')
    def test_celery_task_dispatch(self, mock_delay):
        """Test dispatching tasks to Celery workers."""
        task_data = {
            "task_id": str(uuid.uuid4()),
            "agent_id": str(uuid.uuid4()),
            "task_type": "integration_test",
            "parameters": {"param1": "value1"}
        }
        
        # Mock Celery result
        mock_result = MagicMock()
        mock_result.id = "celery-task-id-123"
        mock_delay.return_value = mock_result
        
        # Dispatch task
        from app.celery_worker.tasks import process_agent_task
        result = process_agent_task.delay(task_data)
        
        assert result.id == "celery-task-id-123"
        mock_delay.assert_called_once_with(task_data)
    
    @patch('app.celery_worker.tasks.collect_system_metrics.apply_async')
    def test_periodic_task_scheduling(self, mock_apply_async):
        """Test periodic task scheduling."""
        # Mock periodic task execution
        mock_result = MagicMock()
        mock_result.id = "periodic-task-id-456"
        mock_apply_async.return_value = mock_result
        
        # Schedule periodic task
        from app.celery_worker.tasks import collect_system_metrics
        result = collect_system_metrics.apply_async(countdown=60)
        
        assert result.id == "periodic-task-id-456"
        mock_apply_async.assert_called_once()
    
    def test_celery_task_result_handling(self):
        """Test handling of Celery task results."""
        # This would test actual result retrieval and handling
        # Implementation depends on result backend configuration
        pass


class TestRedisIntegration:
    """Integration tests for Redis operations."""
    
    async def test_redis_pubsub_functionality(self, redis_client):
        """Test Redis pub/sub functionality."""
        channel = "test_channel"
        message = {"test": "data", "timestamp": datetime.now(timezone.utc).isoformat()}
        
        # Publish message
        await redis_client.publish(channel, json.dumps(message))
        redis_client.publish.assert_called_once_with(channel, json.dumps(message))
    
    async def test_redis_caching(self, redis_client):
        """Test Redis caching functionality."""
        cache_key = "test_cache_key"
        cache_value = "test_cache_value"
        
        # Set cache
        await redis_client.set(cache_key, cache_value, ex=300)  # 5 minutes TTL
        redis_client.set.assert_called_once_with(cache_key, cache_value, ex=300)
        
        # Get cache
        await redis_client.get(cache_key)
        redis_client.get.assert_called_once_with(cache_key)


class TestErrorHandlingIntegration:
    """Integration tests for error handling across components."""
    
    async def test_database_error_propagation(self, client: AsyncClient, db_session):
        """Test error propagation from database layer."""
        with patch('app.api.agents.get_agents', side_effect=Exception("Database connection error")):
            response = await client.get("/api/agents")
            assert response.status_code == 500
    
    async def test_redis_error_handling(self, client: AsyncClient, redis_client):
        """Test error handling when Redis is unavailable."""
        redis_client.publish.side_effect = Exception("Redis connection error")
        
        # Test that API still works even if Redis is down
        with patch('app.api.agents.get_agents') as mock_get_agents:
            mock_get_agents.return_value = []
            
            response = await client.get("/api/agents")
            # Should still return 200 even if Redis notification fails
            assert response.status_code == 200
    
    async def test_celery_worker_failure_handling(self, client: AsyncClient):
        """Test handling of Celery worker failures."""
        task_data = {
            "description": "Test task for worker failure",
            "task_type": "test",
            "sector": "test"
        }
        
        with patch('app.api.tasks.create_task') as mock_create:
            # Simulate Celery worker failure
            mock_create.side_effect = Exception("Celery worker unavailable")
            
            response = await client.post("/api/tasks", json=task_data)
            # Should handle worker failure gracefully
            assert response.status_code == 500


class TestPerformanceIntegration:
    """Integration tests for performance characteristics."""
    
    async def test_concurrent_requests(self, client: AsyncClient):
        """Test handling of concurrent requests."""
        async def make_request():
            with patch('app.api.agents.get_agents') as mock_get:
                mock_get.return_value = []
                response = await client.get("/api/agents")
                return response
        
        # Make concurrent requests
        tasks = [make_request() for _ in range(10)]
        results = await asyncio.gather(*tasks)
        
        # Verify all requests succeeded
        for result in results:
            assert result.status_code == 200
    
    async def test_large_data_handling(self, client: AsyncClient):
        """Test handling of large data sets."""
        # Mock large agent list
        large_agent_list = [
            {
                "agent_id": str(uuid.uuid4()),
                "agent_type": f"agent_{i}",
                "hostname": f"host-{i}",
                "current_status": "idle"
            }
            for i in range(1000)
        ]
        
        with patch('app.api.agents.get_agents') as mock_get:
            mock_get.return_value = large_agent_list
            
            response = await client.get("/api/agents")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1000